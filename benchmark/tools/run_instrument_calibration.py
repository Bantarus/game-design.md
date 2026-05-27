"""Step 5 — instrument calibration smoke run (pre-reg §"Protocol" step 11).

Exercises both pinned instrument bundles on the SHA-locked canary prompt
and asserts the three pass criteria per pre-reg:

  1. Structural validity. Output non-empty; balanced reasoning tags; no
     pathological repetition.
  2. Seed-sensitivity (the actual power guard). K=5 distinct seeds
     produce K distinct SHA-256 hashes AND min pairwise edit-distance
     ≥ 20% of the shortest output's length.
  3. Rubric reachability. The auxiliary judge scores each output ≥ 4 on
     the matches-intent rubric.

Auxiliary same-seed audit recorded but NOT a gate (GPU non-determinism
under stochastic sampling is expected; recorded for F-009).

GPU coexistence
---------------
Qwen Q4_K_M (~18.6 GB) and Gemma UD-Q4_K_M (~16.9 GB) do not coexist in
24 GB of VRAM. The driver sequences:

  Qwen arm:
    1. boot Qwen llama-server (port 8080)
    2. gather K + 2 canary responses
    3. tear down Qwen
    4. boot Gemma llama-server (port 8081)
    5. judge the gathered Qwen responses
    6. tear down Gemma
    7. compute the gates → write artifact

  Claude arm:
    Claude does not consume GPU; the Gemma llama-server can stay loaded
    across all Claude calls. The single-step `calibrate_instrument(...)`
    path is sufficient.

Run:
  python -m benchmark.tools.run_instrument_calibration                    # both arms
  python -m benchmark.tools.run_instrument_calibration --subject qwen     # one arm
  python -m benchmark.tools.run_instrument_calibration --subject claude

Outputs:
  benchmark/harness/audits/instrument_calibration_<bundle_id>_<ts>.json
  + console summary per arm with pass/fail per gate
  + overall exit code 0 iff every requested subject passed all three gates
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from benchmark.harness.calibration import (
    CALIBRATION_K,
    CalibrationResult,
    CanaryGather,
    compute_calibration_result,
    gather_canary_responses,
    score_canary_with_judge,
    write_calibration_result,
)
from benchmark.harness.instrument import (
    QWEN_HEADLINE_BUNDLE,
    QwenInstrument,
)
# Claude transfer-probe imports are deferred (loaded only when --subject claude)
# because the instrument is archived under v12-D scope reduction. The active
# benchmark execution runs Qwen-only; re-activation re-enables Claude via
# the archived module — see `benchmark/harness/archived/README.md`.
from benchmark.harness.judge import GemmaJudge, GEMMA_JUDGE_BUNDLE


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AUDITS_DIR = REPO_ROOT / "benchmark" / "harness" / "audits"

CANARY_SEEDS: tuple[int, ...] = (1001, 1002, 1003, 1004, 1005)

QWEN_PORT = 8080
GEMMA_PORT = 8081


def _print_result(label: str, result: CalibrationResult) -> None:
    print()
    print(f"=== {label} === bundle={result.bundle_id}")
    print(f"  canary_sha: {result.canary_prompt_sha256[:16]}...")
    print(f"  K={CALIBRATION_K} seeds={CANARY_SEEDS}")
    print()
    print("  STRUCTURAL VALIDITY:")
    for s in result.structural:
        flag = "PASS" if s.passed else "FAIL"
        print(f"    output {s.output_id}: {flag}  ({s.notes})")
    print()
    s = result.seed_sensitivity
    print(f"  SEED-SENSITIVITY: {'PASS' if s.passed else 'FAIL'}")
    print(f"    distinct_hashes: {s.distinct_hashes}/{s.total_outputs}")
    print(f"    shortest_output_length: {s.shortest_output_length}")
    print(f"    pairwise_floor (20%): {s.pairwise_floor}")
    print(f"    min_pairwise_edit_distance: {s.min_pairwise_edit_distance}")
    print()
    agg = result.rubric_aggregate
    print(f"  RUBRIC REACHABILITY (aggregate gate, v10):")
    print(f"    per-output scores:")
    for r in result.rubric_reachability:
        print(f"      output {r.output_id}: score={r.rubric_score}/5")
    print(f"    median: {agg.median_score}  (threshold ≥{agg.median_threshold})")
    print(f"    min:    {agg.min_score}  (threshold ≥{agg.min_threshold})")
    flag = "PASS" if agg.passed else "FAIL"
    print(f"    GATE:   {flag}")
    print()
    a = result.same_seed_audit
    print("  SAME-SEED AUDIT (not a gate):")
    print(f"    byte_identical: {a.byte_identical}")
    print(f"    divergence_char_count: {a.divergence_char_count}")
    print(f"    sha1: {a.same_seed_run_1_sha256[:16]}...  sha2: {a.same_seed_run_2_sha256[:16]}...")
    print()
    overall = "PASS" if result.passed else "FAIL"
    print(f"  OVERALL: {overall}")


def _resolve_gguf(env_var: str, default_filename: str) -> str:
    path = os.environ.get(env_var) or str(Path.home() / "llama.cpp/models" / default_filename)
    if not Path(path).is_file():
        raise FileNotFoundError(f"{env_var} GGUF not found: {path}")
    return path


def gather_qwen() -> CanaryGather:
    """Boot Qwen, gather K+2 canary responses, tear down."""
    from benchmark.harness.llama_server import LlamaServer

    gguf_qwen = _resolve_gguf("DRIFTWOOD_QWEN_GGUF_PATH", "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf")
    print(f"[+] Qwen: booting llama-server + gathering canary (K={CALIBRATION_K} + 2 same-seed)...", file=sys.stderr)
    t0 = time.monotonic()
    with LlamaServer(
        gguf_path=gguf_qwen,
        bundle_id=QWEN_HEADLINE_BUNDLE.bundle_id(),
        port=QWEN_PORT,
    ) as qwen_srv:
        inst = QwenInstrument(QWEN_HEADLINE_BUNDLE, server=qwen_srv, gguf_path=gguf_qwen)
        gather = gather_canary_responses(inst, seeds=CANARY_SEEDS)
    print(f"    Qwen arm gathered in {time.monotonic() - t0:.1f}s; server torn down", file=sys.stderr)
    return gather


def gather_claude() -> CanaryGather:
    """Run Claude's K+2 canary invocations. No llama-server involved.

    Imports deferred (v12-D): the Claude instrument lives at
    `benchmark/harness/archived/instrument_claude.py`. The active benchmark
    execution runs Qwen-only; this function is reachable only via the
    `--subject claude` path which is intended for re-activation, not the
    current execution. If the archived module has been moved or removed,
    ImportError surfaces here with a pointer back to v12-D's archival
    decision.
    """
    from benchmark.harness.archived.instrument_claude import (
        CLAUDE_TRANSFER_PROBE_BUNDLE,
        ClaudeInstrument,
    )
    print(f"[+] Claude: K={CALIBRATION_K} canary invocations + 2 same-seed via Claude Code CLI...", file=sys.stderr)
    print(f"    bundle: {CLAUDE_TRANSFER_PROBE_BUNDLE.bundle_id()}", file=sys.stderr)
    print(f"    NOTE: re-activation path — ClaudeInstrument archived at v12-D.",
          file=sys.stderr)
    t0 = time.monotonic()
    inst = ClaudeInstrument(CLAUDE_TRANSFER_PROBE_BUNDLE)
    gather = gather_canary_responses(inst, seeds=CANARY_SEEDS)
    print(f"    Claude arm gathered in {time.monotonic() - t0:.1f}s", file=sys.stderr)
    return gather


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--subject",
        choices=["qwen", "claude", "both"],
        default="both",
        help="Which instrument arm(s) to calibrate (default: both).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=AUDITS_DIR,
        help="Where to write the calibration JSON artifact(s).",
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1 — gather (instrument-up only, no judge needed).
    #
    # Order: Qwen first (GPU model — get it done before anything else
    # competes for VRAM), then Claude (CLI subprocess). The Gemma judge
    # is NOT loaded during gather, so all 24 GB of VRAM are available
    # to Qwen alone.
    gathers: dict[str, CanaryGather] = {}
    if args.subject in ("qwen", "both"):
        gathers["qwen"] = gather_qwen()
    if args.subject in ("claude", "both"):
        gathers["claude"] = gather_claude()

    # Phase 2 — judge (single Gemma session for everything).
    #
    # Loaded once, used to score both arms, then torn down. The
    # alternative — loading Gemma twice — wastes ~15s × 2 of boot time
    # per arm and risks VRAM fragmentation if a future arm gets added.
    gguf_gemma = _resolve_gguf("DRIFTWOOD_GEMMA_GGUF_PATH", "gemma-4-26B-A4B-it-UD-Q4_K_M.gguf")
    print(f"\n[+] Judge: booting Gemma llama-server (--reasoning off) for {len(gathers)} arm(s)...", file=sys.stderr)
    t1 = time.monotonic()
    rubric_scored: dict[str, tuple] = {}
    with GemmaJudge(GEMMA_JUDGE_BUNDLE, gguf_path=gguf_gemma, port=GEMMA_PORT) as judge:
        for name, gather in gathers.items():
            t_arm = time.monotonic()
            rubric_scored[name] = score_canary_with_judge(gather, judge)
            print(f"    scored {name} arm in {time.monotonic() - t_arm:.1f}s", file=sys.stderr)
    print(f"    judge phase total {time.monotonic() - t1:.1f}s; Gemma torn down", file=sys.stderr)

    # Phase 3 — compute results + write artifacts.
    failures: list[str] = []
    for name in gathers:
        result = compute_calibration_result(gathers[name], rubric_scored[name])
        _print_result(name.upper(), result)
        path = write_calibration_result(result, args.out_dir)
        print(f"[+] artifact: {path}", file=sys.stderr)
        if not result.passed:
            failures.append(name)

    print()
    if failures:
        print(f"FAIL: {', '.join(failures)} did not pass all three gates.")
        return 1
    print(f"PASS: {len(gathers)} subject(s) passed all three gates. Step 5 unblocked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
