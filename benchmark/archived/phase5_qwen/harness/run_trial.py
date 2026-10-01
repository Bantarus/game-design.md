"""Main trial-loop entry point.

Invokes the instrument once for one (subject × condition × task × game × seed)
cell, runs the objective checklist + the matches-intent rubric, and writes
a single TrialRecord to `benchmark/harness/trials/`.

The trial-runner is deliberately *atomic* per invocation — it does NOT loop
over N=20; the outer driver (a shell script or makefile or human) decides
which cells to run. This separation lets failed trials be re-run individually
without re-running the whole sweep, and lets the cell distribution be
parallelized trivially.

Usage:
  python -m benchmark.harness.run_trial \
      --subject qwen-pinned-bundle-id \
      --condition A \
      --task medium \
      --game platformer \
      --seed 42

Writes:
  benchmark/harness/trials/<subject>_<condition>_<task>_<game>_seed<seed>.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .checklist import ChecklistGrader, ChecklistVerdict
from .conditions import build_a, build_b, build_c, ConditionPayload
from .instrument import Instrument, InstrumentBundle, MockInstrument
from .judge import Judge, JudgeBundle, IntentScore, MockJudge
from .sanitization import sanitize_output, sanitization_sha256
from .tasks import Task, load_task


HARNESS_DIR = Path(__file__).resolve().parent
TRIALS_DIR = HARNESS_DIR / "trials"


@dataclass(frozen=True)
class TrialRecord:
    # Identity
    subject_bundle_id: str
    judge_bundle_id: str
    condition: str           # "A" | "B" | "C"
    task_cell_id: str        # e.g. "medium_platformer"
    game: str
    seed: int
    timestamp_iso: str

    # Lock SHAs at trial time (audit-trail)
    task_source_sha256: str
    payload_sha256: str
    flattener_sha256: str    # if condition == B; empty otherwise
    c_prompt_sha256: str     # if condition == C; empty otherwise

    # Outcome
    subject_output: str               # RAW — lossless audit trail
    subject_output_sanitized: str     # what the judge actually scored (v8)
    sanitization_sha256: str          # SHA of sanitization.py at trial time (v8)
    tokens_input: int
    tokens_output: int
    tool_steps: int
    wall_clock_seconds: float
    instrument_extra: dict            # per-instrument audit fields (v9.1: load-bearing
                                      # for harness/regime_constancy.py — stop_reason,
                                      # num_turns, subtype, is_error, cost, etc.)

    # Scoring
    checklist_verdict: dict  # serialized ChecklistVerdict
    intent_score: dict       # serialized IntentScore (with rationale)

    # Overall pass per pre-reg §"Judge": passes overall iff
    # (passes_checklist AND intent_score >= 4)
    passes_overall: bool


def run_trial(
    instrument: Instrument,
    judge: Judge,
    task: Task,
    condition: str,
    seed: int,
) -> TrialRecord:
    """Execute one trial cell. Returns the trial record."""
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Build the condition payload
    payload = _build_payload_for_condition(condition, task.game)

    # Get the appropriate SHA-lock fields
    flattener_sha = ""
    c_prompt_sha = ""
    if condition == "B":
        flattener_path = HARNESS_DIR.parent / "tools" / "flattener.py"
        flattener_sha = hashlib.sha256(flattener_path.read_bytes()).hexdigest()
    elif condition == "C":
        c_prompt_path = HARNESS_DIR.parent / "c-prompts" / f"{task.game}.md"
        c_prompt_sha = hashlib.sha256(c_prompt_path.read_bytes()).hexdigest()

    # Build the user prompt: payload + task brief
    user_prompt = (
        f"You are a coding agent. Below is the design context for the game "
        f"{task.game.upper()}; after the context is your task.\n\n"
        f"--- DESIGN CONTEXT ---\n"
        f"{payload.payload_text}\n\n"
        f"--- TASK ---\n"
        f"{task.brief}\n\n"
        f"Implement the task to the best of your ability, using the design "
        f"context as your source of truth. Show the new content and/or code "
        f"in your response."
    )

    # Invoke the instrument
    response = instrument.complete(
        system_prompt="You are an expert coding agent implementing game-design tasks from structured design documents.",
        user_prompt=user_prompt,
        seed=seed,
    )

    # Load the game's design brief for the matches-intent rubric ground truth
    brief_path = HARNESS_DIR.parent / "games" / task.game / "design-brief.md"
    game_brief = brief_path.read_text() if brief_path.exists() else ""

    # `response.text` is the FINAL IMPLEMENTATION text — the `result`
    # field from Claude Code's `--print --output-format json` envelope
    # (or the equivalent from QwenInstrument). It is explicitly NOT the
    # subject's internal reasoning trace. On the Claude side, Opus 4.7
    # at `--effort xhigh` produces a large internal extended-thinking
    # trace; that trace is NOT surfaced in `--print` output — only the
    # final assistant text reaches `result` and therefore `response.text`.
    # The scoring stack (sanitize → checklist judge → matches-intent
    # judge) operates purely on this final-implementation text, which
    # is what the benchmark intends to score.
    #
    # v8: sanitize the raw output once, score the SANITIZED form in every
    # judge call. The pre-reg's two-phase blinding-leak calibration validates
    # that the judge is (a) above chance on RAW outputs (Phase 1 / fitness)
    # and (b) at chance on SANITIZED outputs (Phase 2 / blinding gate). If
    # trial scoring used raw, Phase 1 just proved the judge can read condition
    # off raw outputs — un-blinding the scoring that counts and making the
    # blinding-leak calibration moot. Both judge calls below score sanitized.
    sanitized_output = sanitize_output(response.text)
    san_sha = sanitization_sha256()

    # Score with the objective checklist (judge call — sanitized)
    grader = ChecklistGrader(judge)
    verdict = grader.grade(task, sanitized_output)

    # Score with the matches-intent rubric (judge call — sanitized)
    intent = judge.score_matches_intent(
        task_brief=task.brief,
        subject_output=sanitized_output,
        game_brief=game_brief,
    )

    passes_overall = verdict.passes_checklist and intent.score >= 4

    return TrialRecord(
        subject_bundle_id=instrument.bundle.bundle_id(),
        judge_bundle_id=judge.bundle.bundle_id(),
        condition=condition,
        task_cell_id=task.cell_id,
        game=task.game,
        seed=seed,
        timestamp_iso=timestamp,
        task_source_sha256=task.source_sha256,
        payload_sha256=payload.payload_sha256,
        flattener_sha256=flattener_sha,
        c_prompt_sha256=c_prompt_sha,
        subject_output=response.text,
        subject_output_sanitized=sanitized_output,
        sanitization_sha256=san_sha,
        tokens_input=response.tokens_input,
        tokens_output=response.tokens_output,
        tool_steps=response.tool_steps,
        wall_clock_seconds=response.wall_clock_seconds,
        instrument_extra=dict(response.extra or {}),
        checklist_verdict=_serialize_verdict(verdict),
        intent_score=_serialize_intent(intent),
        passes_overall=passes_overall,
    )


def _build_payload_for_condition(condition: str, game: str) -> ConditionPayload:
    if condition == "A":
        return build_a(game)
    if condition == "B":
        return build_b(game)
    if condition == "C":
        return build_c(game)
    raise ValueError(f"Unknown condition: {condition!r} (expected A, B, or C)")


def _serialize_verdict(v: ChecklistVerdict) -> dict:
    return {
        "task_cell_id": v.task_cell_id,
        "passes_checklist": v.passes_checklist,
        "fraction_passing": v.fraction_passing(),
        "criteria": [
            {"criterion_id": c.criterion_id, "passed": c.passed, "rationale": c.rationale}
            for c in v.criteria
        ],
    }


def _serialize_intent(i: IntentScore) -> dict:
    return {
        "score": i.score,
        "rationale": i.rationale,
        "bundle_id": i.bundle_id,
    }


def write_trial_record(record: TrialRecord, out_dir: Path = TRIALS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_subject = record.subject_bundle_id.replace("/", "_")
    fname = f"{safe_subject}_{record.condition}_{record.task_cell_id}_seed{record.seed}.json"
    path = out_dir / fname
    path.write_text(json.dumps({
        f.name: getattr(record, f.name) for f in record.__dataclass_fields__.values()
    }, indent=2, default=str))
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--subject", required=True,
                        help="Subject instrument identifier (e.g. 'mock', 'qwen', 'claude')")
    parser.add_argument("--condition", required=True, choices=["A", "B", "C"],
                        help="Condition: A (full tree), B (flattened), C (minimal prompt)")
    parser.add_argument("--task", required=True, choices=["easy", "medium", "hard", "ambiguity"],
                        help="Task type")
    parser.add_argument("--game", required=True, choices=["platformer", "survival"],
                        help="Fresh-game subject")
    parser.add_argument("--seed", type=int, required=True,
                        help="Invocation seed (deterministic on instruments that support it)")
    parser.add_argument("--judge", default="mock",
                        help="Aux judge identifier (e.g. 'mock', 'gemini', 'openai')")
    parser.add_argument("--no-write", action="store_true",
                        help="Print the trial record to stdout instead of writing to disk.")
    args = parser.parse_args(argv)

    # Instantiate instrument + judge
    # NOTE: as of the harness-build commit, only MockInstrument + MockJudge are
    # wired up. Real instruments require external infra (see benchmark/README.md).
    if args.subject == "mock":
        instrument = MockInstrument()
    else:
        print(f"Subject '{args.subject}' is stubbed pending external infra wiring. "
              f"See benchmark/README.md for required setup.", file=sys.stderr)
        return 2

    if args.judge == "mock":
        judge = MockJudge()
    else:
        print(f"Judge '{args.judge}' is stubbed pending external infra wiring. "
              f"See benchmark/README.md for required setup.", file=sys.stderr)
        return 2

    task = load_task(args.task, args.game)
    record = run_trial(instrument, judge, task, args.condition, args.seed)

    if args.no_write:
        print(json.dumps({
            f.name: getattr(record, f.name) for f in record.__dataclass_fields__.values()
        }, indent=2, default=str))
    else:
        path = write_trial_record(record)
        print(f"Wrote trial record: {path}", file=sys.stderr)
        print(json.dumps({
            "trial_record_path": str(path),
            "passes_overall": record.passes_overall,
            "intent_score": record.intent_score["score"],
            "checklist_fraction_passing": record.checklist_verdict["fraction_passing"],
        }, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
