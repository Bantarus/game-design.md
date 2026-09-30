"""Trace-derived metrics for one dogfood session (Annex A.3), via VCC.

    python extract.py <session.jsonl> [--vcc PATH] [--copy-root DIR] [--views-dir DIR]

VCC (the View-oriented Conversation Compiler, lllyasviel/VCC) compiles the
session JSONL. Its full view (`.txt`) and brief view (`.min.txt`) are written
next to the session (or to `--views-dir`) so every number below can be audited.
Each tool call in the detail output carries its VCC full-view line range.

Where the numbers come from:
- Structure (which assistant turns and tool calls exist, and their order):
  VCC's lexer + `merge_chunks`, which reassembles an assistant message split
  across records, + its IR.
- Token usage: the raw `message.usage` of each assistant message id. VCC only
  emits session totals, and it sums over split records.
- Consultation bytes: the raw tool_result content as sent to the model. VCC's
  lowering strips Read's line-number prefixes, and those prefixes occupy
  context too.

Definitions are pre-registered in DECISIONS.md D-025; keep them in sync.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shlex
import statistics
from collections import OrderedDict
from pathlib import Path
from typing import Any

DEFAULT_VCC = Path.home() / ".claude/skills/conversation-compiler/scripts/VCC.py"
# Path-like tokens in a Bash command: absolute, home-relative, or with `..`.
_PATH_TOKEN = re.compile(r"(?:(?<=\s)|(?<=^)|(?<=[\"'=]))((?:/|~|\.\./)[^\s\"'|;&<>()]*)")
_HARMLESS_ABS = {"/dev/null", "/"}


# ---- Bash reads (D-025 amendment 3: non-gating secondaries) ----------------------
# Programs whose operands are files the model reads the content of. `git show`
# counts as a read call but yields no file operands.
_READ_PROGS = {"cat", "head", "tail", "sed", "grep", "nl", "less", "more", "awk"}
_OPTS_WITH_VALUE = {"head": {"-n", "-c"}, "tail": {"-n", "-c"}, "grep": {"-e", "-f", "-m", "-A",
                    "-B", "-C", "--include", "--exclude"}, "sed": {"-e", "-f"}, "awk": {"-f", "-F"}}
_SEPARATORS = {"&&", "||", ";", "|", "&", ";;", "|&"}


def _segments(command: str) -> list[list[str]]:
    """Split a shell command into simple-command word lists, quote-aware:
    `|` inside a quoted grep pattern is not a pipe. Unquoted newlines separate
    commands. Unparseable input falls back to whitespace splitting."""
    chars, quote = [], None
    for ch in command:
        if quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch == "\n":
            ch = ";"
        chars.append(ch)
    lex = shlex.shlex("".join(chars), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    out, seg = [], []
    try:
        for tok in lex:
            if tok in _SEPARATORS:
                out.append(seg)
                seg = []
            else:
                seg.append(tok)
    except ValueError:
        return [command.split()]
    out.append(seg)
    return [s for s in out if s]


def bash_reads(command: str, cwd: str) -> tuple[bool, list[str], str]:
    """(is a read call, file operands resolved against cwd, cwd after the call).

    Segments are split on `&&`, `||`, `;`, `|` and newlines. A segment counts
    as a read only if it names at least one file operand (a pipe-fed `head` or
    `grep` is not a file read); `git show` always counts. A segment with an
    output redirection (`>`) is a write, and so is `sed -i`. For `grep`/`awk`/
    `sed` the first non-option operand is the pattern/script, not a file.
    `cd` updates the working directory for later segments and calls.
    """
    is_read, paths = False, []
    for w in _segments(command):
        prog = os.path.basename(w[0])
        if prog == "cd":
            target = w[1] if len(w) > 1 else cwd
            cwd = os.path.normpath(target if os.path.isabs(target) else os.path.join(cwd, target))
            continue
        if prog == "git" and len(w) > 1 and w[1] == "show":
            is_read = True
            continue
        if prog not in _READ_PROGS or any(t.startswith(">") or t.endswith(">") for t in w[1:]):
            continue
        if prog == "sed" and any(t.startswith("-i") for t in w[1:]):
            continue
        operands, skip = [], False
        for t in w[1:]:
            if skip:
                skip = False
                continue
            if t.startswith("-") and len(t) > 1:
                skip = t in _OPTS_WITH_VALUE.get(prog, set())
                continue
            operands.append(t)
        if prog in ("grep", "awk") or (prog == "sed" and not any(
                t in ("-e", "-f") for t in w[1:])):
            operands = operands[1:]
        files = [o for o in operands if o != "-"]
        if not files:  # reading a pipe or stdin, not a file
            continue
        is_read = True
        paths += [os.path.normpath(o if os.path.isabs(o) else os.path.join(cwd, o))
                  for o in files]
    return is_read, paths, cwd


# ---- Consultation bytes by view mode (D-025 amendment 5: non-gating) -------------
# Which `gdmd view` / `gdmd graph` mode a Bash call runs, so the report can show
# which modes the views arm's consultation bytes came from.
VIEW_MODES = ("overview", "full", "grep", "ref", "graph", "other", "mixed")
_GDMD_PROGS = {"gdmd", "game-design.md"}
_WRAPPERS = {"env", "time", "timeout", "nice", "nohup", "command", "exec", "uv", "run"}
# D-026 amendment 2: shell keywords that can precede the command word in a
# segment (`for …; do gdmd view …; done`, `( gdmd view … )`).
_SHELL_KEYWORDS = {"do", "then", "else", "{", "("}
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _segment_view_mode(w: list[str]) -> str | None:
    i = 0
    while i < len(w) and (_ASSIGNMENT.match(w[i]) or os.path.basename(w[i]) in _WRAPPERS
                          or w[i] in _SHELL_KEYWORDS or w[i].startswith("-")
                          or w[i].isdigit()):
        i += 1
    if i >= len(w) or os.path.basename(w[i]) not in _GDMD_PROGS:
        return None
    args = w[i + 1:]
    sub = next((t for t in args if not t.startswith("-")), None)
    if sub not in ("view", "graph"):
        return None
    rest = args[args.index(sub) + 1:]
    if any(t in ("-h", "--help") for t in rest):
        return "other"
    if sub == "graph":
        return "graph"
    for flag, mode in (("--full", "full"), ("--grep", "grep"), ("--ref", "ref")):
        if any(t == flag or t.startswith(flag + "=") for t in rest):
            return mode
    return "overview"


def view_mode(command: str) -> str | None:
    """The view mode a Bash command runs: `overview`, `full`, `grep`, `ref`
    (for `gdmd view`), `graph` (any `gdmd graph`), `other` (`--help`), or
    `mixed` when one call runs more than one mode. None if it runs neither
    command. The program may follow env assignments and simple wrappers
    (`timeout 30`, `uv run`) and may be a path (`.venv/bin/gdmd`)."""
    modes = {m for w in _segments(command) if (m := _segment_view_mode(w))}
    if not modes:
        return None
    return modes.pop() if len(modes) == 1 else "mixed"


def _rel(path: str, root: str | None) -> str:
    if root and (path == root or path.startswith(root + os.sep)):
        return os.path.relpath(path, root)
    return path


def load_vcc(path: str | os.PathLike | None = None):
    p = Path(path or os.environ.get("DOGFOOD_VCC") or DEFAULT_VCC)
    if not p.is_file():
        raise FileNotFoundError(f"VCC.py not found at {p} (set --vcc or $DOGFOOD_VCC)")
    spec = importlib.util.spec_from_file_location("vcc_compiler", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _result_bytes(content: Any) -> int:
    """UTF-8 bytes of a tool_result's text content, as sent to the model.
    Non-text items (images, documents) count 0 and are reported separately."""
    if isinstance(content, str):
        return len(content.encode("utf-8"))
    if isinstance(content, list):
        return sum(len(i.get("text", "").encode("utf-8"))
                   for i in content if isinstance(i, dict) and i.get("type") == "text")
    return 0


def _vcc_pointers(vcc, session: Path, views_dir: Path) -> dict[str, str]:
    """{short tool id: "<file>.txt:start-end"} for each tool result block,
    compiled with VCC. Also writes the audit views."""
    out: dict[str, str] = {}
    for full_path, ir in vcc.compile_pass(str(session), str(views_dir), quiet=True):
        name = Path(full_path).name
        pending = None
        for node in ir:
            if node.get("type") == "meta_header":
                head = (node.get("content") or [""])[0]
                is_result = head.startswith(("[tool]", "[tool_error]"))
                pending = head.split(":")[-1] if is_result else None
            elif node.get("type") in ("tool_result", "tool_error") and pending:
                out[pending] = f"{name}:{node['start_line'] + 1}-{node['end_line'] + 1}"
                pending = None
    return out


def session_context(session: Path) -> dict:
    """What the session's context actually contained (D-025 amendment 1):
    whether the copy's CLAUDE.md was injected (an `instructions` attachment),
    whether the auto-memory section was in the system prompt, and which
    models wrote assistant records. Read from the raw JSONL, not VCC."""
    claude_md, memory, models = False, False, set()
    with open(session, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            a = r.get("attachment") if isinstance(r.get("attachment"), dict) else {}
            if a.get("type") == "instructions":
                claude_md = True
            if a.get("type") == "prompt_snapshot":
                memory = memory or any("\n# Memory\n" in f"\n{part}\n"
                                       for part in a.get("systemPrompt") or [])
            if r.get("type") == "assistant" and r.get("message", {}).get("model"):
                models.add(r["message"]["model"])
    return {"claude_md_loaded": claude_md, "auto_memory_prompt": memory,
            "assistant_models": sorted(models)}


def extract(session: Path, vcc=None, copy_root: Path | None = None,
            views_dir: Path | None = None) -> dict:
    vcc = vcc or load_vcc()
    raw = vcc.lex(str(session))

    # Per-turn usage: one turn = one assistant message id; the last record wins
    # (split records repeat the input-side counts; output_tokens is final last).
    usage: OrderedDict[str, dict] = OrderedDict()
    for r in raw:
        if r.get("type") == "assistant":
            m = r.get("message", {})
            if m.get("id") and isinstance(m.get("usage"), dict):
                usage[m["id"]] = m["usage"]
    occupancy = [int(u.get("input_tokens", 0)) + int(u.get("cache_creation_input_tokens", 0))
                 + int(u.get("cache_read_input_tokens", 0)) for u in usage.values()]

    merged = vcc.merge_chunks(raw)
    calls: OrderedDict[str, dict] = OrderedDict()
    for r in merged:
        if r.get("type") == "assistant":
            for b in r.get("message", {}).get("content", []):
                if b.get("type") == "tool_use":
                    calls[b.get("id", "")] = {"name": b.get("name"), "input": b.get("input", {}),
                                              "result_bytes": 0, "non_text_items": 0,
                                              "is_error": False}
        elif r.get("type") == "user":
            content = r.get("message", {}).get("content")
            if isinstance(content, list):
                for b in content:
                    if b.get("type") == "tool_result" and b.get("tool_use_id") in calls:
                        c = calls[b["tool_use_id"]]
                        c["result_bytes"] += _result_bytes(b.get("content"))
                        items = b.get("content") if isinstance(b.get("content"), list) else []
                        c["non_text_items"] += sum(1 for i in items if isinstance(i, dict)
                                                   and i.get("type") != "text")
                        c["is_error"] = c["is_error"] or bool(b.get("is_error"))

    pointers = _vcc_pointers(vcc, session, views_dir or session.parent)
    seen: set[str] = set()
    files_read, re_reads, bytes_read, out_of_copy = [], 0, 0, []
    root = str(copy_root.resolve()) if copy_root else None
    detail = []
    # amendment 3: Bash reads, and all reads (Read + Bash) by copy-relative path
    cwd = root or os.getcwd()
    bash_calls, bash_bytes, bash_paths = 0, 0, []
    all_seen: set[str] = set()
    all_re_reads = 0
    for tid, c in calls.items():
        inp = c["input"] if isinstance(c["input"], dict) else {}
        read_paths: list[str] = []
        if c["name"] == "Read" and not c["is_error"]:
            read_paths = [_rel(os.path.normpath(str(inp.get("file_path", ""))), root)]
        if c["name"] == "Bash" and not c["is_error"]:
            is_read, ops, cwd = bash_reads(str(inp.get("command", "")), cwd)
            if is_read:
                bash_calls += 1
                bash_bytes += c["result_bytes"]
                read_paths = [_rel(o, root) for o in ops]
                bash_paths += read_paths
        for rp in dict.fromkeys(read_paths):
            if rp in all_seen:
                all_re_reads += 1
            all_seen.add(rp)
        if c["name"] == "Read":
            fp = str(inp.get("file_path", ""))
            if fp in seen:
                re_reads += 1
            else:
                seen.add(fp)
                files_read.append(fp)
            bytes_read += c["result_bytes"]
        if root:
            for key in ("file_path", "path", "notebook_path"):
                v = inp.get(key)
                if isinstance(v, str) and os.path.isabs(v) and not v.startswith(root):
                    out_of_copy.append({"tool": c["name"], key: v})
            if c["name"] == "Bash":
                for tok in _PATH_TOKEN.findall(str(inp.get("command", ""))):
                    if tok.startswith("~") or ".." in tok.split("/") or \
                            (tok.startswith("/") and not tok.startswith(root)
                             and tok not in _HARMLESS_ABS):
                        out_of_copy.append({"tool": "Bash", "path": tok})
        detail.append({"tool": c["name"], "id": tid[-6:], "result_bytes": c["result_bytes"],
                       "is_error": c["is_error"], "vcc": pointers.get(tid[-6:])})

    # amendment 5: every call's full result bytes (errors included, as in the
    # primary) are attributed to the view mode its command runs.
    mode_bytes: dict[str, int] = {}
    mode_calls: dict[str, int] = {}
    for c in calls.values():
        if c["name"] != "Bash" or not isinstance(c["input"], dict):
            continue
        mode = view_mode(str(c["input"].get("command", "")))
        if mode:
            mode_bytes[mode] = mode_bytes.get(mode, 0) + c["result_bytes"]
            mode_calls[mode] = mode_calls.get(mode, 0) + 1

    def total(k: str) -> int:
        return sum(int(u.get(k, 0)) for u in usage.values())

    return {
        "turns": len(usage),
        "input_tokens": total("input_tokens"),
        "output_tokens": total("output_tokens"),
        "cache_read_tokens": total("cache_read_input_tokens"),
        "cache_creation_tokens": total("cache_creation_input_tokens"),
        "tool_calls": len(calls),
        "files_read": len(files_read),
        "bytes_read": bytes_read,
        "re_reads": re_reads,
        "consultation_bytes": sum(c["result_bytes"] for c in calls.values()),
        "non_text_result_items": sum(c["non_text_items"] for c in calls.values()),
        "median_turn_occupancy": statistics.median(occupancy) if occupancy else 0,
        "per_turn_occupancy": occupancy,
        "tool_counts": dict(sorted({c["name"]: sum(1 for x in calls.values()
                                                     if x["name"] == c["name"])
                                    for c in calls.values()}.items())),
        "gdmd_view_calls": sum(1 for c in calls.values() if c["name"] == "Bash"
                               and "gdmd view" in str(c["input"].get("command", ""))),
        "gdmd_graph_calls": sum(1 for c in calls.values() if c["name"] == "Bash"
                                and "gdmd graph" in str(c["input"].get("command", ""))),
        "view_mode_bytes": {m: mode_bytes[m] for m in VIEW_MODES if m in mode_bytes},
        "view_mode_calls": {m: mode_calls[m] for m in VIEW_MODES if m in mode_calls},
        "bash_read_calls": bash_calls,
        "bash_read_bytes": bash_bytes,
        "bash_files_read": len(set(bash_paths)),
        "all_files_read": len(all_seen),
        "all_re_reads": all_re_reads,
        "all_files_read_paths": sorted(all_seen),
        "out_of_copy_access": out_of_copy,
        **session_context(session),
        "tool_detail": detail,
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("session", type=Path)
    ap.add_argument("--vcc", default=None)
    ap.add_argument("--copy-root", type=Path, default=None)
    ap.add_argument("--views-dir", type=Path, default=None)
    a = ap.parse_args(argv)
    print(json.dumps(extract(a.session, load_vcc(a.vcc), a.copy_root, a.views_dir), indent=2))


if __name__ == "__main__":
    main()
