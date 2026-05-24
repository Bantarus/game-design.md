"""Step 6 — blinding-leak two-phase calibration (pre-reg §"Judge" Layer 3, v7→v8).
Step 6b — content-preservation Phase A + Phase B   (pre-reg §"Judge" Layer 3b, v8).

Both gates must pass before trial zero. They share the same Gemma judge,
so the driver gathers Qwen outputs for blinding-leak first (Qwen up),
tears down Qwen, then runs BOTH judge calibrations in one Gemma session
(content-preservation needs no instrument).

GPU coexistence
---------------
Qwen Q4_K_M (~18.6 GB) + Gemma UD-Q4_K_M (~16.9 GB) do not coexist in
24 GB VRAM. Sequence:

  1. boot Qwen
  2. gather 90 outputs for blinding-leak (30 each from build_a/b/c on
     the calibration task, interleaved per harness/sweep_plan discipline)
  3. tear down Qwen
  4. boot Gemma
  5. score blinding-leak Phase 1 (raw) + Phase 2 (sanitized) — 180 calls
  6. run content-preservation Phase A + Phase B on the anchor library —
     24 calls (3 correct + 3 incorrect × 2 phases × 2 games)
  7. tear down Gemma
  8. write artifacts

Calibration task default: `easy_platformer` (the v8 anchor library
coverage matches `easy_platformer` and `easy_survival`; blinding-leak
runs on one task, content-preservation runs on both via its anchor
library).

Run:
  python -m benchmark.tools.run_step6_calibrations
  python -m benchmark.tools.run_step6_calibrations --calibration-task easy_survival
  python -m benchmark.tools.run_step6_calibrations --gate blinding         # only step 6
  python -m benchmark.tools.run_step6_calibrations --gate content          # only step 6b
  python -m benchmark.tools.run_step6_calibrations --n-per-condition 10    # smoke (NOT pre-reg N=30)

Outputs:
  benchmark/harness/audits/blinding_leak_<bundle>_<ts>.json
  benchmark/harness/audits/content_preservation_<bundle>_<ts>.json

Exit code 0 iff every requested gate passes.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from benchmark.harness.calibration import (
    BlindingLeakResult,
    BlindingOutputs,
    gather_blinding_outputs,
    read_blinding_outputs,
    score_blinding,
    write_blinding_leak_result,
    write_blinding_outputs,
)
from benchmark.harness.content_preservation import (
    ContentPreservationResult,
    calibrate_content_preservation,
    write_content_preservation_result,
)
from benchmark.harness.instrument import (
    QWEN_HEADLINE_BUNDLE,
    QwenInstrument,
)
from benchmark.harness.judge import GemmaJudge, GEMMA_JUDGE_BUNDLE
from benchmark.harness.tasks import load_task

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AUDITS_DIR = REPO_ROOT / "benchmark" / "harness" / "audits"

QWEN_PORT = 8080
GEMMA_PORT = 8081


def _resolve_gguf(env_var: str, default_filename: str) -> str:
    path = os.environ.get(env_var) or str(Path.home() / "llama.cpp/models" / default_filename)
    if not Path(path).is_file():
        raise FileNotFoundError(f"{env_var} GGUF not found: {path}")
    return path


def _print_blinding(result: BlindingLeakResult) -> None:
    print()
    print(f"=== BLINDING-LEAK (step 6) ===")
    print(f"  judge:        {result.judge_bundle_id}")
    print(f"  sanitization: {result.sanitization_sha256[:16]}...")
    print(f"  chance:       1/3 = 0.333...")
    pc = result.positive_control
    print(f"\n  PHASE 1 (positive control / judge fitness, RAW outputs):")
    print(f"    n           = {pc.n_outputs}")
    print(f"    accuracy    = {pc.accuracy:.3f}")
    print(f"    95% Wilson CI = [{pc.accuracy_95_ci_low:.3f}, {pc.accuracy_95_ci_high:.3f}]")
    print(f"    pass criterion: CI lower > 1/3 (judge above chance on raw)")
    print(f"    PASS: {pc.passed}")
    bg = result.blinding_gate
    print(f"\n  PHASE 2 (blinding gate, SANITIZED outputs):")
    print(f"    n           = {bg.n_outputs}")
    print(f"    accuracy    = {bg.accuracy:.3f}")
    print(f"    95% Wilson CI = [{bg.accuracy_95_ci_low:.3f}, {bg.accuracy_95_ci_high:.3f}]")
    print(f"    pass criterion: CI includes 1/3 (judge at chance on sanitized)")
    print(f"    PASS: {bg.passed}")
    print(f"\n  OVERALL (both phases): {'PASS' if result.overall_passed else 'FAIL'}")


def _print_content_preservation(result: ContentPreservationResult) -> None:
    print()
    print(f"=== CONTENT-PRESERVATION (step 6b) ===")
    print(f"  judge:        {result.judge_bundle_id}")
    print(f"  sanitization: {result.sanitization_sha256[:16]}...")
    print(f"  anchor_set:   {result.anchor_set_sha256[:16]}...")
    for s in result.per_set:
        print(f"\n  SET ({s.game}, {s.task_cell_id}):")
        print(f"    PHASE A (raw anchors):")
        print(f"      correct: {s.raw_correct_scores}  median {s.raw_median_correct}")
        print(f"      incorrect: {s.raw_incorrect_scores}  median {s.raw_median_incorrect}")
        print(f"      gap: {s.raw_gap}")
        if s.anchor_sanity_failure_reasons:
            for r in s.anchor_sanity_failure_reasons:
                print(f"      FAIL: {r}")
        print(f"      Phase A PASS: {s.anchor_sanity_passed}")
        print(f"    PHASE B (sanitized anchors):")
        print(f"      correct:   {s.sanitized_correct_scores}  median {s.sanitized_median_correct}")
        print(f"      incorrect: {s.sanitized_incorrect_scores}  median {s.sanitized_median_incorrect}")
        print(f"      gap: {s.sanitized_gap}")
        if s.content_preservation_failure_reasons:
            for r in s.content_preservation_failure_reasons:
                print(f"      FAIL: {r}")
        print(f"      Phase B PASS: {s.content_preservation_passed}")
        print(f"    SET PASS: {s.set_passed}")
    print(f"\n  OVERALL (every set both phases): {'PASS' if result.overall_passed else 'FAIL'}")


def gather_qwen_blinding(calibration_task, n_per_condition: int) -> BlindingOutputs:
    from benchmark.harness.llama_server import LlamaServer
    gguf_qwen = _resolve_gguf("DRIFTWOOD_QWEN_GGUF_PATH", "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf")
    n_total = 3 * n_per_condition
    print(f"[+] Qwen: booting llama-server + gathering {n_total} outputs for blinding-leak...", file=sys.stderr)
    print(f"    task: {calibration_task.cell_id}  n_per_condition: {n_per_condition}", file=sys.stderr)
    t0 = time.monotonic()
    with LlamaServer(
        gguf_path=gguf_qwen,
        bundle_id=QWEN_HEADLINE_BUNDLE.bundle_id(),
        port=QWEN_PORT,
    ) as qwen_srv:
        inst = QwenInstrument(QWEN_HEADLINE_BUNDLE, server=qwen_srv, gguf_path=gguf_qwen)
        outs = gather_blinding_outputs(inst, calibration_task, n_per_condition=n_per_condition)
    elapsed = time.monotonic() - t0
    avg_per_call = elapsed / max(n_total, 1)
    print(f"    gathered {len(outs.outputs)} outputs in {elapsed:.1f}s ({avg_per_call:.1f}s/call avg); Qwen torn down", file=sys.stderr)
    return outs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--calibration-task",
        default="easy_platformer",
        choices=["easy_platformer", "easy_survival"],
        help="The (task_type, game) cell used for blinding-leak generation. content-preservation always runs on its full anchor library.",
    )
    parser.add_argument(
        "--gate",
        choices=["blinding", "content", "both"],
        default="both",
        help="Which gate(s) to run.",
    )
    parser.add_argument(
        "--n-per-condition",
        type=int,
        default=30,
        help="Outputs per condition for blinding-leak. Pre-reg locks N=30 (total N=90). Smaller is a smoke run that does NOT clear the gate.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=AUDITS_DIR,
    )
    parser.add_argument(
        "--replay-gather",
        type=Path,
        default=None,
        help="Skip the Qwen gather phase and replay from a previously-saved gather JSON. "
             "Use this after a Gemma-side failure to avoid re-running the ~20-min Qwen generation.",
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: gather Qwen outputs (only if running blinding-leak).
    # If --replay-gather, load from disk instead of re-running Qwen.
    qwen_outputs: BlindingOutputs | None = None
    if args.gate in ("blinding", "both"):
        if args.replay_gather:
            print(f"[+] Replaying Qwen gather from {args.replay_gather}", file=sys.stderr)
            qwen_outputs = read_blinding_outputs(args.replay_gather)
            print(f"    loaded {len(qwen_outputs.outputs)} outputs from {qwen_outputs.task_cell_id} "
                  f"(bundle: {qwen_outputs.instrument_bundle_id})", file=sys.stderr)
        else:
            task_type, game = args.calibration_task.split("_", 1)
            calibration_task = load_task(task_type=task_type, game=game)
            qwen_outputs = gather_qwen_blinding(calibration_task, args.n_per_condition)
            # Persist immediately so a Gemma-side crash doesn't lose ~20 min of Qwen work.
            gather_path = write_blinding_outputs(qwen_outputs, args.out_dir)
            print(f"[+] persisted gather: {gather_path}", file=sys.stderr)

    # Step 2: boot Gemma once for everything that needs the judge.
    gguf_gemma = _resolve_gguf("DRIFTWOOD_GEMMA_GGUF_PATH", "gemma-4-26B-A4B-it-UD-Q4_K_M.gguf")
    print(f"\n[+] Judge: booting Gemma llama-server (--reasoning off)...", file=sys.stderr)
    t1 = time.monotonic()
    blinding_result: BlindingLeakResult | None = None
    content_result: ContentPreservationResult | None = None
    with GemmaJudge(GEMMA_JUDGE_BUNDLE, gguf_path=gguf_gemma, port=GEMMA_PORT) as judge:
        if qwen_outputs is not None:
            ts = time.monotonic()
            print(f"[+] Step 6: scoring blinding-leak Phase 1 (raw) + Phase 2 (sanitized) — 2×{3 * args.n_per_condition} judge calls...", file=sys.stderr)
            blinding_result = score_blinding(qwen_outputs, judge)
            print(f"    blinding-leak scored in {time.monotonic() - ts:.1f}s", file=sys.stderr)
        if args.gate in ("content", "both"):
            ts = time.monotonic()
            print(f"[+] Step 6b: scoring content-preservation Phase A + Phase B on anchor library...", file=sys.stderr)
            content_result = calibrate_content_preservation(judge)
            print(f"    content-preservation scored in {time.monotonic() - ts:.1f}s", file=sys.stderr)
    print(f"    judge phase total {time.monotonic() - t1:.1f}s; Gemma torn down", file=sys.stderr)

    # Step 3: print + write artifacts.
    failures: list[str] = []
    if blinding_result is not None:
        _print_blinding(blinding_result)
        path = write_blinding_leak_result(blinding_result, args.out_dir)
        print(f"[+] artifact: {path}", file=sys.stderr)
        if not blinding_result.overall_passed:
            failures.append("blinding-leak")
    if content_result is not None:
        _print_content_preservation(content_result)
        path = write_content_preservation_result(content_result, args.out_dir)
        print(f"[+] artifact: {path}", file=sys.stderr)
        if not content_result.overall_passed:
            failures.append("content-preservation")

    print()
    if failures:
        print(f"FAIL: {', '.join(failures)} did not pass. Trial zero remains blocked.")
        return 1
    print(f"PASS: requested gate(s) passed. ", end="")
    if args.gate == "both":
        print("Step 6 + 6b unblocked. Pre-sweep generalization (step 6c) requires real trials first.")
    elif args.gate == "blinding":
        print("Step 6 unblocked.")
    else:
        print("Step 6b unblocked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
