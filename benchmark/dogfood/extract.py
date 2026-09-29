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
import statistics
from collections import OrderedDict
from pathlib import Path
from typing import Any

DEFAULT_VCC = Path.home() / ".claude/skills/conversation-compiler/scripts/VCC.py"
# Path-like tokens in a Bash command: absolute, home-relative, or with `..`.
_PATH_TOKEN = re.compile(r"(?:(?<=\s)|(?<=^)|(?<=[\"'=]))((?:/|~|\.\./)[^\s\"'|;&<>()]*)")
_HARMLESS_ABS = {"/dev/null", "/"}


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
    for tid, c in calls.items():
        inp = c["input"] if isinstance(c["input"], dict) else {}
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
        "out_of_copy_access": out_of_copy,
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
