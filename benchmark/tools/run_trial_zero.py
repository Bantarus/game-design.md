"""Trial zero — full sweep run on Qwen-Coder (single-subject, v12-D).

Phase 1 (Qwen up). Boot the Qwen3-Coder llama-server. Iterate the 330
sweep cells in `harness.sweep_plan` order (pairing-integrity preserved:
per-pair adjacency, within-pair coin, inter-unit shuffle, all seeded
per the pre-reg). For each cell, build the condition payload (A = full
spec tree, B = flattened spec, C = minimal-context prompt), invoke
`QwenInstrument.complete()` with the cell's seed, and persist an
intermediate `TrialGather` JSON record carrying subject_output (raw,
lossless) + sanitization-SHA + payload-SHA + flattener-SHA / c-prompt-
SHA + instrument metadata (tokens, num_turns, wall, extra). Tear down
Qwen.

Phase 2 (Gemma up). Boot the Gemma judge llama-server. Iterate the
persisted Phase-1 gathers, applying the SHA-locked v11 sanitizer per
the v8 trial-time sanitization-before-scoring discipline (the
`subject_output_sanitized` field is what the judge scores; the raw
output is preserved for the audit trail). For each gather, run the
ChecklistGrader against the task's `intent_checklist` and the judge's
matches-intent rubric against the task brief + game brief. Assemble
the final `TrialRecord` (identical shape to step 6c's records — see
`harness/run_trial.py::TrialRecord`); persist to `harness/trials/`.
Tear down Gemma.

Why split. Qwen Q4_K_M (~18.6 GB) and Gemma UD-Q4_K_M (~16.9 GB) cannot
coexist in a 24 GB RTX 4090 VRAM budget. Alternating per-trial would
add ~30 s × 2 × 330 = 5.5 h of pure boot/teardown overhead on top of
the ~5-8 h Qwen gather and the ~10-20 min Gemma scoring. Serial
gather → score is the right shape (each model boots once); total
wall ~6-9 h.

Resume safety. Phase 1 skips cells whose gather JSON already exists;
Phase 2 skips gathers whose final TrialRecord already exists. Both
phases are independently re-runnable, and a Phase-2 crash never loses
the Phase-1 Qwen work.

Pre-conditions (checked at start):
  - v11 sanitizer SHA `e85c123f227d225a...` unchanged
    (compared against the sanitization module's live SHA)
  - The pre-reg `docs/v0.2-phase5-pre-registration.md` is staged at
    v12-D (chain ends `1bb0803 → ...`); the current commit IS the
    pre-reg lock, and trial zero LOCKS IT (no further supersessions
    after this driver completes Phase 1).

Run:
  python -m benchmark.tools.run_trial_zero              # both phases
  python -m benchmark.tools.run_trial_zero --phase 1    # gather only
  python -m benchmark.tools.run_trial_zero --phase 2    # score only
  python -m benchmark.tools.run_trial_zero --shuffle-seed 12345
  python -m benchmark.tools.run_trial_zero --max-cells 3   # smoke (~5min)
  python -m benchmark.tools.run_trial_zero --dry-run       # validate wiring

Outputs:
  benchmark/harness/trial_gathers/qwen-coder-*_{A,B,C}_<task>_<game>_seed<seed>.json
  benchmark/harness/trials/qwen-coder-*_{A,B,C}_<task>_<game>_seed<seed>.json

THE MOMENT TRIAL ZERO FIRES, THE PRE-REGISTRATION FREEZES. No further
redirects after Phase 1 begins. Use --dry-run + --max-cells for sanity
checks without firing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from benchmark.harness.checklist import ChecklistGrader
from benchmark.harness.conditions import (
    ConditionPayload,
    build_a,
    build_b,
    build_c,
)
from benchmark.harness.instrument import (
    InstrumentResponse,
    QWEN_HEADLINE_BUNDLE,
    QwenInstrument,
)
from benchmark.harness.judge import GEMMA_JUDGE_BUNDLE, GemmaJudge
from benchmark.harness.llama_server import LlamaServer
from benchmark.harness.run_trial import TrialRecord, write_trial_record
from benchmark.harness.sanitization import sanitize_output, sanitization_sha256
from benchmark.harness.sweep_plan import TrialCell, plan_sweep
from benchmark.harness.tasks import load_task

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HARNESS_DIR = REPO_ROOT / "benchmark" / "harness"
TRIAL_GATHERS_DIR = HARNESS_DIR / "trial_gathers"
TRIALS_DIR = HARNESS_DIR / "trials"

QWEN_PORT = 8080
GEMMA_PORT = 8081

# v11 sanitizer SHA-of-record (per pre-reg v11/v12/v12-D supersessions).
# Computed at startup against `sanitization_sha256()` for a pre-condition
# check; mismatch halts trial zero before any cell runs.
V11_SANITIZER_SHA_PREFIX = "e85c123f227d225a"


# ---------------------------------------------------------------------------
# Phase 1: intermediate gather record
# ---------------------------------------------------------------------------

@dataclass
class TrialGather:
    """Phase-1 intermediate: cell context + raw instrument output, no scores.

    Carries all the fields a downstream TrialRecord will need EXCEPT the
    judge-derived scoring fields. Phase 2 loads these, runs the judge, and
    assembles the final TrialRecord.
    """
    # Identity
    subject_bundle_id: str
    condition: str
    task_cell_id: str
    game: str
    seed: int
    timestamp_iso: str
    order_index: int
    instance_id: str
    unit_id: str
    pair_role: str

    # SHA-locks at gather time
    task_source_sha256: str
    payload_sha256: str
    flattener_sha256: str
    c_prompt_sha256: str

    # Raw output + instrument metadata
    subject_output: str
    tokens_input: int
    tokens_output: int
    tool_steps: int
    wall_clock_seconds: float
    instrument_extra: dict

    # Sanitization SHA of the gather-time sanitizer; the eventual
    # TrialRecord.sanitization_sha256 should match this (the v8
    # discipline applies the same SHA at score time).
    sanitization_sha256_at_gather: str


def gather_filename(cell: TrialCell, bundle_id: str) -> str:
    safe = bundle_id.replace("/", "_")
    return f"{safe}_{cell.condition}_{cell.task}_{cell.game}_seed{cell.seed}.json"


def write_trial_gather(g: TrialGather, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = g.subject_bundle_id.replace("/", "_")
    fname = f"{safe}_{g.condition}_{g.task_cell_id}_seed{g.seed}.json"
    path = out_dir / fname
    path.write_text(json.dumps(asdict(g), indent=2, default=str))
    return path


def read_trial_gather(path: Path) -> TrialGather:
    data = json.loads(path.read_text())
    return TrialGather(**data)


# ---------------------------------------------------------------------------
# Shared: payload + user prompt construction (mirrors run_trial.py)
# ---------------------------------------------------------------------------

def _build_payload(condition: str, game: str) -> ConditionPayload:
    if condition == "A":
        return build_a(game)
    if condition == "B":
        return build_b(game)
    if condition == "C":
        return build_c(game)
    raise ValueError(f"Unknown condition: {condition!r}")


def _build_user_prompt(payload: ConditionPayload, task_brief: str, game: str) -> str:
    return (
        f"You are a coding agent. Below is the design context for the game "
        f"{game.upper()}; after the context is your task.\n\n"
        f"--- DESIGN CONTEXT ---\n"
        f"{payload.payload_text}\n\n"
        f"--- TASK ---\n"
        f"{task_brief}\n\n"
        f"Implement the task to the best of your ability, using the design "
        f"context as your source of truth. Show the new content and/or code "
        f"in your response."
    )


def _sha_for_condition(condition: str, game: str) -> tuple[str, str]:
    """Returns (flattener_sha, c_prompt_sha) per the run_trial convention."""
    flattener_sha = ""
    c_prompt_sha = ""
    if condition == "B":
        flattener_path = HARNESS_DIR.parent / "tools" / "flattener.py"
        flattener_sha = hashlib.sha256(flattener_path.read_bytes()).hexdigest()
    elif condition == "C":
        c_prompt_path = HARNESS_DIR.parent / "c-prompts" / f"{game}.md"
        c_prompt_sha = hashlib.sha256(c_prompt_path.read_bytes()).hexdigest()
    return (flattener_sha, c_prompt_sha)


SYSTEM_PROMPT = (
    "You are an expert coding agent implementing game-design tasks from "
    "structured design documents."
)


# ---------------------------------------------------------------------------
# Phase 1: Qwen gather
# ---------------------------------------------------------------------------

def _resolve_qwen_gguf() -> str:
    path = os.environ.get("DRIFTWOOD_QWEN_GGUF_PATH") or str(
        Path.home() / "llama.cpp/models" / "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"
    )
    if not Path(path).is_file():
        raise FileNotFoundError(f"Qwen GGUF not found: {path}")
    return path


def _resolve_gemma_gguf() -> str:
    path = os.environ.get("DRIFTWOOD_GEMMA_GGUF_PATH") or str(
        Path.home() / "llama.cpp/models" / "gemma-4-26B-A4B-it-UD-Q4_K_M.gguf"
    )
    if not Path(path).is_file():
        raise FileNotFoundError(f"Gemma GGUF not found: {path}")
    return path


def phase1_gather(
    cells: list[TrialCell],
    out_dir: Path,
    skip_existing: bool = True,
    dry_run: bool = False,
) -> int:
    """Boot Qwen, gather each cell's raw output, persist TrialGather records.

    Returns the count of cells gathered (or, if dry_run, the count that
    WOULD have been gathered).
    """
    bundle_id = QWEN_HEADLINE_BUNDLE.bundle_id()

    pending: list[TrialCell] = []
    skipped = 0
    for cell in cells:
        gather_path = out_dir / gather_filename(cell, bundle_id)
        if skip_existing and gather_path.exists():
            skipped += 1
            continue
        pending.append(cell)

    if skipped:
        print(f"[+] Phase 1: skipping {skipped} cells with existing gathers; "
              f"{len(pending)} pending", file=sys.stderr)
    else:
        print(f"[+] Phase 1: {len(pending)} cells to gather", file=sys.stderr)

    if dry_run:
        print(f"[+] --dry-run: would gather {len(pending)} cells", file=sys.stderr)
        return len(pending)

    if not pending:
        return 0

    gguf_qwen = _resolve_qwen_gguf()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[+] Phase 1: booting Qwen llama-server...", file=sys.stderr)
    t0 = time.monotonic()
    with LlamaServer(
        gguf_path=gguf_qwen,
        bundle_id=bundle_id,
        port=QWEN_PORT,
    ) as qwen_srv:
        inst = QwenInstrument(QWEN_HEADLINE_BUNDLE, server=qwen_srv,
                              gguf_path=gguf_qwen)
        for i, cell in enumerate(pending, 1):
            t_cell_0 = time.monotonic()
            prefix = (f"  [{i:3d}/{len(pending)}] {cell.condition} "
                      f"{cell.task} {cell.game} seed={cell.seed} "
                      f"(order={cell.order_index})")
            print(f"{prefix}...", file=sys.stderr, end=" ", flush=True)
            try:
                task = load_task(task_type=cell.task, game=cell.game)
                payload = _build_payload(cell.condition, cell.game)
                user_prompt = _build_user_prompt(payload, task.brief, cell.game)
                flattener_sha, c_prompt_sha = _sha_for_condition(
                    cell.condition, cell.game,
                )

                resp = inst.complete(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    seed=cell.seed,
                )

                g = TrialGather(
                    subject_bundle_id=bundle_id,
                    condition=cell.condition,
                    task_cell_id=task.cell_id,
                    game=cell.game,
                    seed=cell.seed,
                    timestamp_iso=time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                 time.gmtime()),
                    order_index=cell.order_index,
                    instance_id=cell.instance_id,
                    unit_id=cell.unit_id,
                    pair_role=cell.pair_role,
                    task_source_sha256=task.source_sha256,
                    payload_sha256=payload.payload_sha256,
                    flattener_sha256=flattener_sha,
                    c_prompt_sha256=c_prompt_sha,
                    subject_output=resp.text,
                    tokens_input=resp.tokens_input,
                    tokens_output=resp.tokens_output,
                    tool_steps=resp.tool_steps,
                    wall_clock_seconds=resp.wall_clock_seconds,
                    instrument_extra=dict(resp.extra or {}),
                    sanitization_sha256_at_gather=sanitization_sha256(),
                )
                write_trial_gather(g, out_dir)
                elapsed_cell = time.monotonic() - t_cell_0
                print(f"OK ({elapsed_cell:.1f}s; out={resp.tokens_output}t)",
                      file=sys.stderr)
            except Exception as e:
                elapsed_cell = time.monotonic() - t_cell_0
                print(f"FAIL ({elapsed_cell:.1f}s): "
                      f"{type(e).__name__}: {e}", file=sys.stderr)
                raise

    elapsed = time.monotonic() - t0
    print(f"[+] Phase 1: {len(pending)} gathers in {elapsed:.1f}s "
          f"({elapsed/max(len(pending),1):.1f}s/call avg)", file=sys.stderr)
    return len(pending)


# ---------------------------------------------------------------------------
# Phase 2: Gemma score
# ---------------------------------------------------------------------------

def _serialize_verdict(v) -> dict:
    return {
        "task_cell_id": v.task_cell_id,
        "passes_checklist": v.passes_checklist,
        "fraction_passing": v.fraction_passing(),
        "criteria": [
            {
                "criterion_id": c.criterion_id,
                "passed": c.passed,
                "rationale": c.rationale,
            }
            for c in v.criteria
        ],
    }


def _serialize_intent(i) -> dict:
    return {
        "score": i.score,
        "rationale": i.rationale,
        "bundle_id": i.bundle_id,
    }


def trial_record_filename(g: TrialGather) -> str:
    safe = g.subject_bundle_id.replace("/", "_")
    return f"{safe}_{g.condition}_{g.task_cell_id}_seed{g.seed}.json"


def phase2_score(
    gathers_dir: Path,
    trials_dir: Path,
    skip_existing: bool = True,
    dry_run: bool = False,
) -> int:
    """Boot Gemma, score each gather, persist final TrialRecord.

    Returns the count of trials scored (or, if dry_run, the count that
    WOULD have been scored).
    """
    pending_paths: list[Path] = []
    skipped = 0
    for gp in sorted(gathers_dir.glob("*.json")):
        g = read_trial_gather(gp)
        trial_path = trials_dir / trial_record_filename(g)
        if skip_existing and trial_path.exists():
            skipped += 1
            continue
        pending_paths.append(gp)

    if skipped:
        print(f"[+] Phase 2: skipping {skipped} gathers with existing "
              f"TrialRecords; {len(pending_paths)} pending", file=sys.stderr)
    else:
        print(f"[+] Phase 2: {len(pending_paths)} gathers to score",
              file=sys.stderr)

    if dry_run:
        print(f"[+] --dry-run: would score {len(pending_paths)} gathers",
              file=sys.stderr)
        return len(pending_paths)

    if not pending_paths:
        return 0

    gguf_gemma = _resolve_gemma_gguf()
    trials_dir.mkdir(parents=True, exist_ok=True)

    print(f"[+] Phase 2: booting Gemma llama-server (--reasoning off)...",
          file=sys.stderr)
    t0 = time.monotonic()
    with GemmaJudge(GEMMA_JUDGE_BUNDLE, gguf_path=gguf_gemma,
                     port=GEMMA_PORT) as judge:
        grader = ChecklistGrader(judge)
        for i, gp in enumerate(pending_paths, 1):
            t_cell_0 = time.monotonic()
            g = read_trial_gather(gp)
            prefix = (f"  [{i:3d}/{len(pending_paths)}] {g.condition} "
                      f"{g.task_cell_id} seed={g.seed}")
            print(f"{prefix}...", file=sys.stderr, end=" ", flush=True)
            try:
                task = load_task(task_type=g.task_cell_id.split("_")[0],
                                  game=g.game)
                sanitized = sanitize_output(g.subject_output)
                san_sha_now = sanitization_sha256()

                brief_path = (HARNESS_DIR.parent / "games" / g.game
                               / "design-brief.md")
                game_brief = brief_path.read_text() if brief_path.exists() else ""

                verdict = grader.grade(task, sanitized)
                intent = judge.score_matches_intent(
                    task_brief=task.brief,
                    subject_output=sanitized,
                    game_brief=game_brief,
                )

                passes_overall = verdict.passes_checklist and intent.score >= 4

                record = TrialRecord(
                    subject_bundle_id=g.subject_bundle_id,
                    judge_bundle_id=judge.bundle.bundle_id(),
                    condition=g.condition,
                    task_cell_id=g.task_cell_id,
                    game=g.game,
                    seed=g.seed,
                    timestamp_iso=g.timestamp_iso,
                    task_source_sha256=g.task_source_sha256,
                    payload_sha256=g.payload_sha256,
                    flattener_sha256=g.flattener_sha256,
                    c_prompt_sha256=g.c_prompt_sha256,
                    subject_output=g.subject_output,
                    subject_output_sanitized=sanitized,
                    sanitization_sha256=san_sha_now,
                    tokens_input=g.tokens_input,
                    tokens_output=g.tokens_output,
                    tool_steps=g.tool_steps,
                    wall_clock_seconds=g.wall_clock_seconds,
                    instrument_extra=g.instrument_extra,
                    checklist_verdict=_serialize_verdict(verdict),
                    intent_score=_serialize_intent(intent),
                    passes_overall=passes_overall,
                )
                write_trial_record(record, out_dir=trials_dir)
                elapsed_cell = time.monotonic() - t_cell_0
                print(f"OK ({elapsed_cell:.1f}s; intent={intent.score}, "
                      f"checklist={verdict.fraction_passing():.2f}, "
                      f"pass={passes_overall})", file=sys.stderr)
            except Exception as e:
                elapsed_cell = time.monotonic() - t_cell_0
                print(f"FAIL ({elapsed_cell:.1f}s): "
                      f"{type(e).__name__}: {e}", file=sys.stderr)
                raise

    elapsed = time.monotonic() - t0
    print(f"[+] Phase 2: {len(pending_paths)} TrialRecords in "
          f"{elapsed:.1f}s ({elapsed/max(len(pending_paths),1):.1f}s/call avg)",
          file=sys.stderr)
    return len(pending_paths)


# ---------------------------------------------------------------------------
# Pre-conditions
# ---------------------------------------------------------------------------

def _check_preconditions() -> None:
    live_sha = sanitization_sha256()
    if not live_sha.startswith(V11_SANITIZER_SHA_PREFIX):
        raise RuntimeError(
            f"Sanitizer SHA mismatch: expected v11 SHA prefix "
            f"`{V11_SANITIZER_SHA_PREFIX}...`, got `{live_sha[:16]}...`. "
            f"The v11 sanitizer-of-record changed; trial zero requires "
            f"a new pre-reg supersession + step-6c re-run + provenance-rule "
            f"re-evaluation BEFORE trial zero can proceed."
        )
    print(f"[+] Pre-condition: v11 sanitizer SHA `{live_sha[:16]}...` OK",
          file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--phase", choices=["1", "2", "both"], default="both",
        help="Which phase(s) to run: 1=Qwen gather, 2=Gemma score, "
             "both=full trial zero (default).",
    )
    parser.add_argument(
        "--shuffle-seed", type=int, default=12345,
        help="Sweep-plan shuffle seed (default 12345; locks the sweep order).",
    )
    parser.add_argument(
        "--max-cells", type=int, default=None,
        help="Cap on cells (for smoke testing). Default: no cap (all 330).",
    )
    parser.add_argument(
        "--gathers-dir", type=Path, default=TRIAL_GATHERS_DIR,
        help="Directory for Phase-1 intermediate gather records.",
    )
    parser.add_argument(
        "--trials-dir", type=Path, default=TRIALS_DIR,
        help="Directory for final TrialRecord JSON files.",
    )
    parser.add_argument(
        "--no-skip-existing", action="store_true",
        help="Re-run cells even if gather/TrialRecord already exists (overwrites).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate wiring + count pending work without running.",
    )
    args = parser.parse_args(argv)

    _check_preconditions()

    cells = plan_sweep(subject="qwen", shuffle_seed=args.shuffle_seed)
    if args.max_cells is not None:
        cells = cells[: args.max_cells]
    print(f"[+] Sweep: {len(cells)} cells "
          f"(subject=qwen, shuffle_seed={args.shuffle_seed})", file=sys.stderr)

    if args.dry_run:
        print("[+] --dry-run mode: no model boots, no instrument calls.",
              file=sys.stderr)

    skip = not args.no_skip_existing

    if args.phase in ("1", "both"):
        phase1_gather(
            cells=cells,
            out_dir=args.gathers_dir,
            skip_existing=skip,
            dry_run=args.dry_run,
        )

    if args.phase in ("2", "both"):
        phase2_score(
            gathers_dir=args.gathers_dir,
            trials_dir=args.trials_dir,
            skip_existing=skip,
            dry_run=args.dry_run,
        )

    print()
    print("Trial zero complete." if args.phase == "both"
          else f"Trial zero phase {args.phase} complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
