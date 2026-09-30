#!/usr/bin/env python3
"""Dogfood orchestrator (D-023; locked rule D-025). Never runs in CI.

    python run.py --dry-run [--task T ...] [--arm A ...]   # no model calls
    python run.py --probe                                  # 1 call: model-id gate
    python run.py --import-probe                           # 4 calls: D-024 import size
    python run.py --pilot                                  # baseline x each task x 1
    python run.py --task T --arm A --repeats N [--repeat-start K]   # any cell(s)

Each cell runs one headless Claude Code session in an isolated copy
(fixture.prepare_copy), then runs the task's deterministic checker with the
fixed judge, then extracts metrics from the session JSONL with VCC
(extract.py). Arms (D-025):

- `baseline`: the v0.3 world (tooling layer and `gdmd` from `v0.3.0`),
  `arms/baseline.md`.
- `views`: the matrix-commit world, `arms/views.md`.

Same task text (stdin), same task trees, same flags, same tool allowlist.

Output:
- `results/<run_id>.jsonl`: one line per cell; committed.
- `results/<run_id>/metrics/`: per-cell extraction output; committed.
- `results/<run_id>/archive.json`: where the session logs went; committed.
- `results/sessions/<run_id>/`: session JSONLs, stderr, VCC views. Gitignored,
  and compressed into `ARCHIVE_DIR` (outside the repo) at the end of a run.
  Each line carries its session's SHA-256.

The CLI is a pinned binary (`CLAUDE_BIN`, checked by SHA-256 and version),
run with the auto-updater disabled. A run refuses to start if the harness
has uncommitted changes, and pins every copy to the commit it started at.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import fixture
from extract import extract, load_vcc

RESULTS_DIR = fixture.DOGFOOD_DIR / "results"
ARCHIVE_DIR = Path.home() / ".local/share/gdmd-dogfood/archive"
DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_EFFORT = "high"            # mirrors the maintainer's interactive default
CLAUDE_PIN_VERSION = "2.1.285"
CLAUDE_PIN_SHA256 = "33dad1ec615a2e08cc78b494f05c110e49916de2c79d78ec8799ebf46b233d29"
CLAUDE_BIN = Path.home() / ".local/share/gdmd-dogfood/claude" / f"claude-{CLAUDE_PIN_VERSION}"
TOOLS = "Read,Grep,Glob,Edit,Write,Bash"
# Bash is limited to read-only inspection plus the gdmd CLI (both arms alike).
ALLOWED_BASH = [
    "Bash(gdmd:*)", "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
    "Bash(git show:*)", "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)",
    "Bash(wc:*)", "Bash(grep:*)", "Bash(sort:*)", "Bash(diff:*)",
]
NO_AUTO_MEMORY = json.dumps({"autoMemoryEnabled": False})
ARM_WORLD = {"baseline": "v0.3", "views": "matrix"}
ARMS = tuple(ARM_WORLD)
OUTCOMES = ("success", "fail", "capped", "error")
HARNESS_PATHS = ["benchmark/dogfood", "tests/test_dogfood.py",
                 ":(exclude)benchmark/dogfood/results"]


# ---- the pinned CLI -----------------------------------------------------------

def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def claude_version() -> str:
    return subprocess.run([str(CLAUDE_BIN), "--version"], capture_output=True, text=True,
                          env=session_env()).stdout.strip()


def check_pinned_cli() -> str:
    """Refuse unless CLAUDE_BIN is the pinned binary; return its version string."""
    if not CLAUDE_BIN.is_file():
        raise SystemExit(f"pinned CLI missing: {CLAUDE_BIN} (copy the {CLAUDE_PIN_VERSION} "
                         "native build there; see README)")
    if sha256(CLAUDE_BIN) != CLAUDE_PIN_SHA256:
        raise SystemExit(f"{CLAUDE_BIN} does not match the pinned SHA-256")
    version = claude_version()
    if not version.startswith(CLAUDE_PIN_VERSION + " "):
        raise SystemExit(f"{CLAUDE_BIN} reports {version!r}, pinned {CLAUDE_PIN_VERSION}")
    return version


def session_env(base: dict | None = None) -> dict:
    env = dict(os.environ if base is None else base)
    env["DISABLE_AUTOUPDATER"] = "1"
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"   # D-025 amendment 1 (with --settings)
    return env


# ---- argv + flag validation ---------------------------------------------------

def session_argv(model: str, effort: str, session_id: str, arm_text: str,
                 budget_usd: float) -> list[str]:
    """argv for one dogfood session. The task prompt goes on stdin."""
    return [
        str(CLAUDE_BIN), "-p",
        "--model", model,
        "--effort", effort,
        "--output-format", "stream-json", "--verbose",
        "--session-id", session_id,
        # D-025 amendment 1: not --restricted, which also drops CLAUDE.md. Load
        # the copy's project/local sources only (no user settings), no auto-memory.
        "--setting-sources", "project,local",
        "--settings", NO_AUTO_MEMORY,
        "--tools", TOOLS,
        "--allowedTools", *ALLOWED_BASH,
        "--permission-mode", "acceptEdits",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--max-budget-usd", f"{budget_usd:.2f}",
        "--append-system-prompt", arm_text,
    ]


def probe_argv(model: str) -> list[str]:
    return [str(CLAUDE_BIN), "-p", "--model", model, "--output-format", "json",
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
    return subprocess.run([str(CLAUDE_BIN), "--help"], capture_output=True, text=True,
                          check=True, env=session_env()).stdout


# ---- run-level guards ------------------------------------------------------------

def harness_dirty() -> list[str]:
    out = fixture.git(fixture.REPO_ROOT, "status", "--porcelain", "--", *HARNESS_PATHS)
    return [ln for ln in out.splitlines() if ln.strip()]


def pin_source_sha(require_clean: bool) -> str:
    """The commit every copy of this run is exported from. Checkers, prompts and
    arm files are read from the working tree, so it must match that commit."""
    if require_clean and harness_dirty():
        raise SystemExit("harness has uncommitted changes; commit before a real run:\n"
                         + "\n".join(harness_dirty()))
    return fixture.git(fixture.REPO_ROOT, "rev-parse", "HEAD")


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


def classify(stop_reason: str, result_event: dict, *, session_found: bool,
             checker_parsed: bool, checker_success: bool, context_ok: bool = True) -> str:
    """D-025 outcome of one run: success | fail | capped | error.

    - capped: the harness turn cap, the wall-clock timeout, or the CLI's
      budget cap ended the session. Counts as not-success.
    - error: an apparatus failure, meaning no result event, any other CLI
      error, no session JSONL, a checker that emitted no report, or a context
      check failure (CLAUDE.md not loaded, or auto-memory on; amendment 1).
    - success / fail: the session completed and the checker ran.
    """
    if stop_reason in ("turn_cap", "timeout"):
        return "capped"
    if stop_reason.startswith("error:") and "budget" in stop_reason:
        return "capped"
    if (stop_reason != "completed" or not result_event or not session_found
            or not checker_parsed or not context_ok):
        return "error"
    return "success" if checker_success else "fail"


def find_session_jsonl(session_id: str) -> Path | None:
    hits = list((Path.home() / ".claude/projects").glob(f"*/{session_id}.jsonl"))
    return hits[0] if hits else None


def run_cell(task: fixture.Task, arm: str, repeat: int, cfg: argparse.Namespace,
             run: dict, work: Path) -> dict:
    cell_id = f"{task.task_id}__{arm}__r{repeat}"
    cell_dir = work / cell_id
    copy = fixture.prepare_copy(task, cell_dir, ref=run["source_sha"], world=ARM_WORLD[arm],
                                judge=run["judge"])
    env = session_env(copy.env())
    if arm == "views":
        chk = subprocess.run(["gdmd", "view", "--help"], env=env, capture_output=True)
        if chk.returncode != 0:
            raise SystemExit("views arm refused: `gdmd view` is not available in the copy "
                             "(WS2 not implemented at this commit)")
    version = claude_version()
    if version != run["cli_version"]:
        raise SystemExit(f"CLI version changed mid-run: {run['cli_version']!r} -> {version!r}")
    session_id = str(uuid.uuid4())
    arm_text = (fixture.ARMS_DIR / f"{arm}.md").read_text(encoding="utf-8")
    argv = session_argv(cfg.model, cfg.effort, session_id, arm_text, cfg.budget_usd)
    started = datetime.now(timezone.utc)
    sess_dir = RESULTS_DIR / "sessions" / run["run_id"]
    metrics_dir = RESULTS_DIR / run["run_id"] / "metrics"
    sess_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    sess = run_session(argv, task.prompt(), copy.root, env, turn_cap=cfg.turn_cap,
                       timeout_s=cfg.timeout_s, stderr_path=sess_dir / f"{cell_id}.stderr.txt")

    judge_env = dict(env, DOGFOOD_GDMD=str(run["judge"]))
    chk = subprocess.run([sys.executable, str(task.checker_path), str(copy.root),
                          "--run-date", started.astimezone().date().isoformat()],
                         env=judge_env, capture_output=True, text=True)
    try:
        checker = json.loads(chk.stdout)
        checker_parsed = isinstance(checker, dict) and "success" in checker
    except json.JSONDecodeError:
        checker, checker_parsed = {"raw": (chk.stdout + chk.stderr)[-2000:]}, False

    src = find_session_jsonl(session_id)
    metrics, stored = {}, None
    if src:
        stored = sess_dir / f"{cell_id}.jsonl"
        shutil.copy2(src, stored)
        metrics = extract(stored, load_vcc(cfg.vcc), copy.root, sess_dir / "views")
        (metrics_dir / f"{cell_id}.metrics.json").write_text(json.dumps(metrics, indent=2))
    res = sess["result_event"]
    context_ok = bool(metrics) and metrics["claude_md_loaded"] and not metrics["auto_memory_prompt"]
    outcome = classify(sess["stop_reason"], res, session_found=stored is not None,
                       checker_parsed=checker_parsed, context_ok=context_ok,
                       checker_success=chk.returncode == 0 and bool(checker.get("success")))
    line = {
        "run_id": run["run_id"], "cell_id": cell_id, "task_id": task.task_id,
        "mode": task.mode, "arm": arm, "world": copy.world, "repeat": repeat,
        "pilot": bool(cfg.pilot), "outcome": outcome, "success": outcome == "success",
        "checker_detail": checker.get("criteria", checker),
        "stop_reason": sess["stop_reason"], "wall_clock_s": sess["wall_clock_s"],
        "est_cost_usd": res.get("total_cost_usd"),
        "model_requested": cfg.model,
        "model_reported": sorted((res.get("modelUsage") or {}).keys()),
        "cli_version": version, "source_sha": copy.source_sha,
        "overlay_sha": copy.overlay_sha, "judge_sha": run["source_sha"],
        "session_id": session_id, "supersedes": cfg.supersedes,
        "session_jsonl": stored.name if stored else None,
        "session_sha256": sha256(stored) if stored else None,
        "started_at": started.isoformat(),
        **{k: metrics.get(k) for k in (
            "turns", "input_tokens", "output_tokens", "cache_read_tokens",
            "cache_creation_tokens", "tool_calls", "files_read", "bytes_read", "re_reads",
            "consultation_bytes", "median_turn_occupancy", "gdmd_view_calls",
            "gdmd_graph_calls", "claude_md_loaded", "auto_memory_prompt",
            "assistant_models", "bash_read_calls", "bash_read_bytes", "bash_files_read",
            "all_files_read", "all_re_reads")},
        "out_of_copy_access": len(metrics.get("out_of_copy_access", [])) if metrics else None,
    }
    if not cfg.keep_copies:
        shutil.rmtree(cell_dir, ignore_errors=True)
    return line


def archive_sessions(run_id: str) -> dict | None:
    """Compress results/sessions/<run_id>/ into ARCHIVE_DIR (outside the repo)
    and record where it went, with per-member SHA-256, in results/<run_id>/."""
    src = RESULTS_DIR / "sessions" / run_id
    if not src.is_dir():
        return None
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    dest = ARCHIVE_DIR / f"{run_id}.tar.xz"
    members = sorted(p for p in src.rglob("*") if p.is_file())
    with tarfile.open(dest, "w:xz") as tar:
        for p in members:
            tar.add(p, arcname=str(p.relative_to(src.parent)))
    info = {"archive": str(dest), "sha256": sha256(dest), "bytes": dest.stat().st_size,
            "members": {str(p.relative_to(src)): sha256(p) for p in members}}
    out = RESULTS_DIR / run_id / "archive.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(info, indent=2, sort_keys=True))
    return info


# ---- probes -----------------------------------------------------------------

def model_probe(model: str) -> int:
    version = check_pinned_cli()
    argv = probe_argv(model)
    missing = validate_flags(argv, claude_help())
    if missing:
        print(f"flag validation failed: {missing}", file=sys.stderr)
        return 2
    proc = subprocess.run(argv, input="Reply with exactly: ok", capture_output=True, text=True,
                          env=session_env())
    try:
        res = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(proc.stdout + proc.stderr, file=sys.stderr)
        return 1
    reported = sorted((res.get("modelUsage") or {}).keys())
    ok = proc.returncode == 0 and not res.get("is_error") and bool(reported)
    print(json.dumps({"ok": ok, "requested": model, "reported": reported,
                      "cli_version": version, "result": res.get("result"),
                      "cost_usd": res.get("total_cost_usd")}, indent=2))
    return 0 if ok else 1


SPEC_IMPORT_LINE = "- Format definition: @docs/spec.md"


def import_probe(cfg: argparse.Namespace, run: dict, work: Path) -> int:
    """D-024 differential, in both worlds: turn-1 occupancy with vs without ONLY
    the `@docs/spec.md` import (schema, AGENTS.md, deckbuilder-root imports
    stay). Four single-turn calls; also records each world's spec.md size."""
    task = fixture.Task("import_probe", "probe", "examples/deckbuilder", None)
    arm_text = (fixture.ARMS_DIR / "baseline.md").read_text(encoding="utf-8")
    out: dict = {"source_sha": run["source_sha"], "cli_version": run["cli_version"],
                 "model_requested": cfg.model, "effort": cfg.effort, "worlds": {}}
    for world in ("v0.3", "matrix"):
        w_out: dict = {}
        for label in ("with_spec_import", "without_spec_import"):
            copy = fixture.prepare_copy(task, work / f"{world}-{label}", ref=run["source_sha"],
                                        world=world, judge=run["judge"])
            w_out["spec_md_bytes"] = (copy.root / "docs/spec.md").stat().st_size
            w_out["overlay_sha"] = copy.overlay_sha
            if label == "without_spec_import":
                cm = copy.root / "CLAUDE.md"
                text = cm.read_text(encoding="utf-8")
                if text.count(SPEC_IMPORT_LINE) != 1:
                    raise SystemExit(f"CLAUDE.md no longer has exactly one {SPEC_IMPORT_LINE!r}")
                cm.write_text(text.replace(SPEC_IMPORT_LINE, "- Format definition: docs/spec.md"))
            sid = str(uuid.uuid4())
            argv = session_argv(cfg.model, cfg.effort, sid, arm_text, 0.50)
            sess = run_session(argv, "Reply with exactly: ok. Do not use any tools.", copy.root,
                               session_env(copy.env()), turn_cap=1, timeout_s=300,
                               stderr_path=work / f"{world}-{label}.stderr.txt")
            jsonl = find_session_jsonl(sid)
            m = extract(jsonl, load_vcc(cfg.vcc), copy.root, work / "views") if jsonl else {}
            occ = m.get("per_turn_occupancy") or []
            if not m.get("claude_md_loaded") or m.get("auto_memory_prompt"):
                raise SystemExit(f"import probe {world}/{label}: context check failed "
                                 f"(claude_md_loaded={m.get('claude_md_loaded')}, "
                                 f"auto_memory_prompt={m.get('auto_memory_prompt')})")
            w_out[label] = {"turn1_occupancy": occ[0] if occ else None, "session_id": sid,
                            "assistant_models": m.get("assistant_models"),
                            "stop_reason": sess["stop_reason"],
                            "model_reported": sorted(
                                (sess["result_event"].get("modelUsage") or {}).keys()),
                            "cost_usd": sess["result_event"].get("total_cost_usd")}
        w, wo = (w_out[k]["turn1_occupancy"] for k in ("with_spec_import", "without_spec_import"))
        w_out["spec_import_tokens"] = (w - wo) if (w is not None and wo is not None) else None
        out["worlds"][world] = w_out
    v03, mat = out["worlds"]["v0.3"], out["worlds"]["matrix"]
    out["spec_md_bytes_difference"] = mat["spec_md_bytes"] - v03["spec_md_bytes"]
    out["spec_import_tokens_difference"] = (
        mat["spec_import_tokens"] - v03["spec_import_tokens"]
        if None not in (mat["spec_import_tokens"], v03["spec_import_tokens"]) else None)
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"import-probe-{run['run_id']}.json"
    path.write_text(json.dumps(out, indent=2, sort_keys=True))
    print(json.dumps(out, indent=2))
    return 0 if None not in (v03["spec_import_tokens"], mat["spec_import_tokens"]) else 1


# ---- CLI ------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    tasks = fixture.load_tasks()
    ap = argparse.ArgumentParser(description="Dogfood harness (never in CI).")
    ap.add_argument("--task", action="append", choices=sorted(tasks))
    ap.add_argument("--arm", action="append", choices=ARMS)
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--repeat-start", type=int, default=1,
                    help="first repeat number (D-025's pre-registered extension uses 4)")
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
    ap.add_argument("--supersedes", default=None, metavar="RUN_ID/CELL_ID",
                    help="D-025 error re-run: the errored cell this run replaces")
    cfg = ap.parse_args(argv)
    if cfg.supersedes and (cfg.pilot or len(cfg.task or []) != 1 or len(cfg.arm or []) != 1
                           or cfg.repeats != 1):
        ap.error("--supersedes re-runs exactly one cell: one --task, one --arm, --repeats 1")

    if cfg.probe:
        return model_probe(cfg.model)
    cli_version = check_pinned_cli()
    run_id = cfg.run_id or ("pilot-" if cfg.pilot else "") + \
        datetime.now().strftime("%Y%m%dT%H%M%S")
    work = cfg.workdir / run_id
    if fixture.REPO_ROOT in work.resolve().parents:
        raise SystemExit("--workdir must be outside the repository (CLAUDE.md discovery)")
    if work.exists():
        raise SystemExit(f"{work} exists; run ids are single-use")
    source_sha = pin_source_sha(require_clean=not cfg.dry_run)
    fixture.verify_v03_venv()
    run = {"run_id": run_id, "source_sha": source_sha, "cli_version": cli_version,
           "judge": fixture.make_judge(work / "judge", source_sha)}
    if cfg.import_probe:
        return import_probe(cfg, run, work)

    if cfg.pilot:
        task_ids, arms, repeats = sorted(tasks), ["baseline"], range(1, 2)
    else:
        task_ids, arms = cfg.task or sorted(tasks), cfg.arm or ["baseline"]
        repeats = range(cfg.repeat_start, cfg.repeat_start + cfg.repeats)
    cells = [(t, a, r) for t in task_ids for a in arms for r in repeats]

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
            copy = fixture.prepare_copy(tasks[t], cell, ref=source_sha, world=ARM_WORLD[a],
                                        judge=run["judge"])
            argv_shown = session_argv(cfg.model, cfg.effort, "<uuid>", f"<arms/{a}.md>",
                                      cfg.budget_usd)
            if a == "views" and subprocess.run(["gdmd", "view", "--help"], env=copy.env(),
                                               capture_output=True).returncode != 0:
                print(f"{t}__{a}__r{r}: views arm NOT runnable at this commit "
                      "(`gdmd view` unavailable; WS2 pending)", file=sys.stderr)
            print(json.dumps({"cell": f"{t}__{a}__r{r}", "world": copy.world,
                              "cwd": str(copy.root), "stdin": f"tasks/{t}.md",
                              "argv": argv_shown, "fixture_base": fixture.BASE_TAG,
                              "source_sha": copy.source_sha, "overlay_sha": copy.overlay_sha}))
            if not cfg.keep_copies:
                shutil.rmtree(cell, ignore_errors=True)
        print(f"dry-run OK: {len(cells)} cell(s); flags validated against {cli_version}"
              + (" (harness has uncommitted changes)" if harness_dirty() else ""),
              file=sys.stderr)
        return 0

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"{run_id}.jsonl"
    try:
        for t, a, r in cells:
            line = run_cell(tasks[t], a, r, cfg, run, work)
            with open(out_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(line, sort_keys=True) + "\n")
            print(f"{line['cell_id']}: {line['outcome']} stop={line['stop_reason']} "
                  f"cost={line['est_cost_usd']}", file=sys.stderr)
    finally:
        if sha256(CLAUDE_BIN) != CLAUDE_PIN_SHA256:
            print("WARNING: pinned CLI binary changed during the run", file=sys.stderr)
        info = archive_sessions(run_id)
        if info:
            print(f"session logs archived to {info['archive']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
