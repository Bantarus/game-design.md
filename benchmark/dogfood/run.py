#!/usr/bin/env python3
"""Dogfood orchestrator (D-023; locked rule D-025). Never runs in CI.

    python run.py --dry-run [--task T ...] [--arm A ...]   # no model calls
    python run.py --probe                                  # 1 call: model-id gate
    python run.py --import-probe                           # 2 calls: D-024 import size
    python run.py --pilot                                  # baseline x each task x 1
    python run.py --task T --arm A --repeats N             # any cell(s)

Each cell runs one headless Claude Code session in an isolated copy
(fixture.prepare_copy), then runs the task's deterministic checker, then
extracts metrics from the session JSONL with VCC (extract.py). Each cell
appends one line to results/<run_id>.jsonl. Session JSONLs and VCC views go
to results/sessions/<run_id>/ (gitignored; their SHA-256 is in the line).

The two arms are identical except for the text appended to the system prompt
(arms/<arm>.md): same task text (stdin), same fixture, same CLAUDE.md, same
flags, same tool allowlist.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import fixture
from extract import extract, load_vcc

RESULTS_DIR = fixture.DOGFOOD_DIR / "results"
DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_EFFORT = "high"            # mirrors the maintainer's interactive default
TOOLS = "Read,Grep,Glob,Edit,Write,Bash"
# Bash is limited to read-only inspection plus the gdmd CLI (both arms alike).
ALLOWED_BASH = [
    "Bash(gdmd:*)", "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
    "Bash(git show:*)", "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)",
    "Bash(wc:*)", "Bash(grep:*)", "Bash(sort:*)", "Bash(diff:*)",
]
ARMS = ("baseline", "views")


# ---- argv + flag validation ---------------------------------------------------

def session_argv(model: str, effort: str, session_id: str, arm_text: str,
                 budget_usd: float) -> list[str]:
    """argv for one dogfood session. The task prompt goes on stdin."""
    return [
        "claude", "-p",
        "--model", model,
        "--effort", effort,
        "--output-format", "stream-json", "--verbose",
        "--session-id", session_id,
        "--restricted",
        "--tools", TOOLS,
        "--allowedTools", *ALLOWED_BASH,
        "--permission-mode", "acceptEdits",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--max-budget-usd", f"{budget_usd:.2f}",
        "--append-system-prompt", arm_text,
    ]


def probe_argv(model: str) -> list[str]:
    return ["claude", "-p", "--model", model, "--output-format", "json",
            "--tools", "", "--restricted", "--strict-mcp-config",
            "--disable-slash-commands", "--no-session-persistence",
            "--max-budget-usd", "0.10"]


_OPT_LINE = re.compile(r"^\s{1,6}(-\w,\s+)?(--[A-Za-z][\w-]*)(?:,\s+(--[A-Za-z][\w-]*))?")


def listed_flags(help_text: str) -> set[str]:
    """Long options *defined* in `claude --help` (option lines, including
    aliases), not flags merely mentioned in some other option's description."""
    out: set[str] = set()
    for line in help_text.splitlines():
        m = _OPT_LINE.match(line)
        if m:
            out.update(g for g in m.groups()[1:] if g)
    return out


def validate_flags(argv: list[str], help_text: str) -> list[str]:
    """Return the argv long flags missing from `claude --help` (empty = OK)."""
    known = listed_flags(help_text)
    used = {a for a in argv if a.startswith("--")}
    return sorted(used - known)


def claude_help() -> str:
    return subprocess.run(["claude", "--help"], capture_output=True, text=True,
                          check=True).stdout


def claude_version() -> str:
    return subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()


# ---- one session --------------------------------------------------------------

def run_session(argv: list[str], prompt: str, cwd: Path, env: dict, *, turn_cap: int,
                timeout_s: float, stderr_path: Path) -> dict:
    """Run one headless session; enforce the turn cap and wall-clock timeout.
    A turn is one distinct assistant message id in the stream."""
    t0 = time.monotonic()
    with open(stderr_path, "w", encoding="utf-8") as err:
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=err, text=True,
                                start_new_session=True)
        proc.stdin.write(prompt)
        proc.stdin.close()
        state = {"turns": set(), "result": None, "stop": "completed"}

        def reader() -> None:
            for line in proc.stdout:
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("type") == "assistant":
                    mid = ev.get("message", {}).get("id")
                    if mid:
                        state["turns"].add(mid)
                        if len(state["turns"]) > turn_cap and state["stop"] == "completed":
                            state["stop"] = "turn_cap"
                            proc.kill()
                elif ev.get("type") == "result":
                    state["result"] = ev

        th = threading.Thread(target=reader, daemon=True)
        th.start()
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            state["stop"] = "timeout"
            proc.kill()
            proc.wait()
        th.join(timeout=10)
    res = state["result"] or {}
    if state["stop"] == "completed" and res.get("is_error"):
        state["stop"] = f"error:{res.get('subtype', 'unknown')}"
    return {"stop_reason": state["stop"], "wall_clock_s": round(time.monotonic() - t0, 2),
            "result_event": res, "exit_code": proc.returncode}


def find_session_jsonl(session_id: str) -> Path | None:
    hits = list((Path.home() / ".claude/projects").glob(f"*/{session_id}.jsonl"))
    return hits[0] if hits else None


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_cell(task: fixture.Task, arm: str, repeat: int, cfg: argparse.Namespace,
             run_id: str, work: Path) -> dict:
    cell_id = f"{task.task_id}__{arm}__r{repeat}"
    cell_dir = work / cell_id
    copy = fixture.prepare_copy(task, cell_dir)
    env = copy.env()
    if arm == "views":
        chk = subprocess.run(["gdmd", "view", "--help"], env=env, capture_output=True)
        if chk.returncode != 0:
            raise SystemExit("views arm refused: `gdmd view` is not available in the copy "
                             "(WS2 not implemented at this commit)")
    session_id = str(uuid.uuid4())
    arm_text = (fixture.ARMS_DIR / f"{arm}.md").read_text(encoding="utf-8")
    argv = session_argv(cfg.model, cfg.effort, session_id, arm_text, cfg.budget_usd)
    started = datetime.now(timezone.utc)
    out_dir = RESULTS_DIR / "sessions" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    sess = run_session(argv, task.prompt(), copy.root, env, turn_cap=cfg.turn_cap,
                       timeout_s=cfg.timeout_s, stderr_path=out_dir / f"{cell_id}.stderr.txt")

    chk = subprocess.run([sys.executable, str(task.checker_path), str(copy.root),
                          "--run-date", started.astimezone().date().isoformat()],
                         env=env, capture_output=True, text=True)
    try:
        checker = json.loads(chk.stdout)
    except json.JSONDecodeError:
        checker = {"success": False, "criteria": {}, "raw": (chk.stdout + chk.stderr)[-2000:]}

    src = find_session_jsonl(session_id)
    metrics, stored = {}, None
    if src:
        stored = out_dir / f"{cell_id}.jsonl"
        shutil.copy2(src, stored)
        metrics = extract(stored, load_vcc(cfg.vcc), copy.root, out_dir / "views")
        (out_dir / f"{cell_id}.metrics.json").write_text(json.dumps(metrics, indent=2))
    res = sess["result_event"]
    line = {
        "run_id": run_id, "cell_id": cell_id, "task_id": task.task_id, "mode": task.mode,
        "arm": arm, "repeat": repeat, "pilot": bool(cfg.pilot),
        "success": chk.returncode == 0 and bool(checker.get("success")),
        "checker_detail": checker.get("criteria", checker),
        "stop_reason": sess["stop_reason"], "wall_clock_s": sess["wall_clock_s"],
        "est_cost_usd": res.get("total_cost_usd"),
        "model_requested": cfg.model,
        "model_reported": sorted((res.get("modelUsage") or {}).keys()),
        "cli_version": claude_version(), "source_sha": copy.source_sha,
        "session_id": session_id,
        "session_jsonl": str(stored.relative_to(fixture.REPO_ROOT)) if stored else None,
        "session_sha256": sha256(stored) if stored else None,
        "started_at": started.isoformat(),
        **{k: metrics.get(k) for k in (
            "turns", "input_tokens", "output_tokens", "cache_read_tokens",
            "cache_creation_tokens", "tool_calls", "files_read", "bytes_read", "re_reads",
            "consultation_bytes", "median_turn_occupancy", "gdmd_view_calls",
            "gdmd_graph_calls")},
        "out_of_copy_access": len(metrics.get("out_of_copy_access", [])) if metrics else None,
    }
    if not cfg.keep_copies:
        shutil.rmtree(cell_dir, ignore_errors=True)
    return line


# ---- probes -----------------------------------------------------------------

def model_probe(model: str) -> int:
    argv = probe_argv(model)
    missing = validate_flags(argv, claude_help())
    if missing:
        print(f"flag validation failed: {missing}", file=sys.stderr)
        return 2
    proc = subprocess.run(argv, input="Reply with exactly: ok", capture_output=True, text=True)
    try:
        res = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(proc.stdout + proc.stderr, file=sys.stderr)
        return 1
    reported = sorted((res.get("modelUsage") or {}).keys())
    ok = proc.returncode == 0 and not res.get("is_error") and bool(reported)
    print(json.dumps({"ok": ok, "requested": model, "reported": reported,
                      "result": res.get("result"), "cost_usd": res.get("total_cost_usd")},
                     indent=2))
    return 0 if ok else 1


SPEC_IMPORT_LINE = "- Format definition: @docs/spec.md"


def import_probe(cfg: argparse.Namespace, work: Path) -> int:
    """D-024 2-call differential: turn-1 occupancy with vs without ONLY the
    `@docs/spec.md` import (schema, AGENTS.md, deckbuilder-root imports stay)."""
    task = fixture.Task("import_probe", "probe", "examples/deckbuilder", None)
    arm_text = (fixture.ARMS_DIR / "baseline.md").read_text(encoding="utf-8")
    out = {}
    for label in ("with_spec_import", "without_spec_import"):
        copy = fixture.prepare_copy(task, work / label)
        if label == "without_spec_import":
            cm = copy.root / "CLAUDE.md"
            text = cm.read_text(encoding="utf-8")
            if text.count(SPEC_IMPORT_LINE) != 1:
                raise SystemExit(f"CLAUDE.md no longer has exactly one {SPEC_IMPORT_LINE!r}")
            cm.write_text(text.replace(SPEC_IMPORT_LINE, "- Format definition: docs/spec.md"))
        sid = str(uuid.uuid4())
        argv = session_argv(cfg.model, cfg.effort, sid, arm_text, 0.50)
        sess = run_session(argv, "Reply with exactly: ok. Do not use any tools.", copy.root,
                           copy.env(), turn_cap=1, timeout_s=300,
                           stderr_path=work / f"{label}.stderr.txt")
        jsonl = find_session_jsonl(sid)
        occ = extract(jsonl, load_vcc(cfg.vcc), copy.root, work / "views")["per_turn_occupancy"] \
            if jsonl else []
        out[label] = {"turn1_occupancy": occ[0] if occ else None, "session_id": sid,
                      "stop_reason": sess["stop_reason"],
                      "cost_usd": sess["result_event"].get("total_cost_usd")}
    w = out["with_spec_import"]["turn1_occupancy"]
    wo = out["without_spec_import"]["turn1_occupancy"]
    out["spec_import_tokens"] = (w - wo) if (w is not None and wo is not None) else None
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"import-probe-{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    path.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    return 0 if out["spec_import_tokens"] is not None else 1


# ---- CLI ------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    tasks = fixture.load_tasks()
    ap = argparse.ArgumentParser(description="Dogfood harness (never in CI).")
    ap.add_argument("--task", action="append", choices=sorted(tasks))
    ap.add_argument("--arm", action="append", choices=ARMS)
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--pilot", action="store_true",
                    help="baseline arm, every task, 1 repeat; marked pilot (not evidence)")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate flags, prepare fixtures, print argv; no model calls")
    ap.add_argument("--probe", action="store_true", help="model-id probe (1 call)")
    ap.add_argument("--import-probe", action="store_true", help="D-024 import-size probe")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--effort", default=DEFAULT_EFFORT)
    ap.add_argument("--turn-cap", type=int, default=60)
    ap.add_argument("--timeout-s", type=float, default=1200)
    ap.add_argument("--budget-usd", type=float, default=3.0)
    ap.add_argument("--vcc", default=None, help="path to VCC.py")
    ap.add_argument("--workdir", type=Path,
                    default=Path(tempfile.gettempdir()) / "gdmd-dogfood")
    ap.add_argument("--keep-copies", action="store_true")
    ap.add_argument("--run-id", default=None)
    cfg = ap.parse_args(argv)

    if cfg.probe:
        return model_probe(cfg.model)
    run_id = cfg.run_id or ("pilot-" if cfg.pilot else "") + \
        datetime.now().strftime("%Y%m%dT%H%M%S")
    work = cfg.workdir / run_id
    if fixture.REPO_ROOT in work.resolve().parents:
        raise SystemExit("--workdir must be outside the repository (CLAUDE.md discovery)")
    if cfg.import_probe:
        return import_probe(cfg, work)

    if cfg.pilot:
        task_ids, arms, repeats = sorted(tasks), ["baseline"], 1
    else:
        task_ids, arms, repeats = cfg.task or sorted(tasks), cfg.arm or ["baseline"], cfg.repeats
    cells = [(t, a, r) for t in task_ids for a in arms for r in range(1, repeats + 1)]

    help_text = claude_help()
    sample = session_argv(cfg.model, cfg.effort, "00000000-0000-0000-0000-000000000000",
                          "<arm>", cfg.budget_usd)
    missing = validate_flags(sample, help_text)
    if missing:
        print(f"flag validation failed; not in `claude --help`: {missing}", file=sys.stderr)
        return 2

    if cfg.dry_run:
        for t, a, r in cells:
            cell = work / f"{t}__{a}__r{r}"
            copy = fixture.prepare_copy(tasks[t], cell)
            argv_shown = session_argv(cfg.model, cfg.effort, "<uuid>", f"<arms/{a}.md>",
                                      cfg.budget_usd)
            if a == "views" and subprocess.run(["gdmd", "view", "--help"], env=copy.env(),
                                               capture_output=True).returncode != 0:
                print(f"{t}__{a}__r{r}: views arm NOT runnable at this commit "
                      "(`gdmd view` unavailable; WS2 pending)", file=sys.stderr)
            print(json.dumps({"cell": f"{t}__{a}__r{r}", "cwd": str(copy.root),
                              "stdin": f"tasks/{t}.md", "argv": argv_shown,
                              "fixture_base": fixture.BASE_TAG, "source_sha": copy.source_sha}))
            if not cfg.keep_copies:
                shutil.rmtree(cell, ignore_errors=True)
        print(f"dry-run OK: {len(cells)} cell(s); flags validated against claude "
              f"{claude_version()}", file=sys.stderr)
        return 0

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"{run_id}.jsonl"
    for t, a, r in cells:
        line = run_cell(tasks[t], a, r, cfg, run_id, work)
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, sort_keys=True) + "\n")
        print(f"{line['cell_id']}: success={line['success']} stop={line['stop_reason']} "
              f"cost={line['est_cost_usd']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
