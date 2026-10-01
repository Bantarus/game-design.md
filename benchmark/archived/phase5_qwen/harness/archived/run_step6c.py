"""Step 6c — Pre-sweep three-read pre-flight gate on Claude trials (pre-reg v12).

After steps 5 + 6 + 6b PASS but BEFORE step 12 (the full ~9-hour trial sweep),
this driver generates N=30 real Claude trials (easy task, 2 games × 3 conditions
× 5 seeds — drawn from the natural top of v9's N=12-30 range) and runs the three
pre-flight reads declared at v12 supersession of step 11b:

  (a) Sanitizer-generalization — does the v11 sanitizer-of-record blind real
      Claude outputs at chance? Pass: 95% Wilson CI on condition-prediction
      judge accuracy includes 1/3. Implementation:
      `harness/calibration.py::check_blinding_generalization` with
      `label='pre_sweep'`. Failure → sanitizer-iteration-stopping-rule.

  (b) Regime-constancy on the Claude arm — are per-(condition) `num_turns` /
      `tokens` / `cost` distributions comparable enough within Claude that the
      within-Claude cost-lift gate measures spec-format cost rather than
      condition-dependent agentic flailing? Advisory — flags fire at max/min
      cell-mean ratio ≥ 2.0x on any metric OR per-condition error-rate spread
      ≥ 10pp. Implementation: `harness/regime_constancy.analyze`. Flags
      reported in F-009 alongside the powered post-hoc result.

  (c) Opus-usage-rate extrapolation — project subscription cost from the N=30
      6c batch to the full 330-cell Claude sweep. Advisory; informs the
      subscription-vs-API-key fallback decision BEFORE step 12 commits (a
      mid-sweep rate-limit wall would correlate failures with sweep-ordering
      tail, structurally distorting the cost-lift gate).

Provenance rule (pre-committed at v12). The 6c trial records ARE valid
full-sweep trial data and fold into the F-009 dataset IFF (i) the v11
sanitizer-of-record SHA `e85c123f227d225a...` is unchanged at sweep time
AND (ii) sanitizer-generalization PASSES at pre-sweep. Sanitizer-iteration
+ new SHA → re-sanitize+re-score under new SHA (preferred) or discard.
Regime-constancy flags and Opus-usage-rate decisions are NOT fold-in
disqualifiers — they produce decisions and records, neither invalidates
trial data.

Step 12 (the full sweep) does NOT begin until all three reads have
produced their artifacts + decisions.

Run:
  python -m benchmark.tools.run_step6c
  python -m benchmark.tools.run_step6c --shuffle-seed 12345
  python -m benchmark.tools.run_step6c --skip-trials        # reads only on existing trials
  python -m benchmark.tools.run_step6c --skip-isolation-check
  python -m benchmark.tools.run_step6c --subscription-budget-usd 50

Outputs:
  benchmark/harness/trials/<subject>_{A,B,C}_easy_{platformer,survival}_seed*.json
  benchmark/harness/audits/generalization_check_pre_sweep_<judge>_<ts>.json
  benchmark/harness/audits/regime_constancy_pre_sweep_<ts>.json
  benchmark/harness/audits/opus_usage_extrapolation_pre_sweep_<ts>.json

Exit 0 iff sanitizer-generalization (read a) PASS. Reads (b) and (c) are
advisory; failures there are recorded as decisions, not gate failures.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from benchmark.harness.calibration import (
    check_blinding_generalization,
    write_generalization_check_result,
)
from benchmark.harness.archived.instrument_claude import (
    CLAUDE_TRANSFER_PROBE_BUNDLE,
    ClaudeInstrument,
)
from benchmark.harness.judge import GEMMA_JUDGE_BUNDLE, GemmaJudge
from benchmark.harness.regime_constancy import (
    analyze as regime_analyze,
    load_trials as regime_load_trials,
    write_result as regime_write_result,
    METRICS as REGIME_METRICS,
)
from benchmark.harness.run_trial import run_trial, write_trial_record
from benchmark.harness.sweep_plan import plan_sweep
from benchmark.harness.tasks import load_task

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
TRIALS_DIR = REPO_ROOT / "benchmark" / "harness" / "trials"
AUDITS_DIR = REPO_ROOT / "benchmark" / "harness" / "audits"
GEMMA_PORT = 8081

# Claude arm full-sweep N — locked at pre-reg v11 (sweep_plan: 330 cells).
CLAUDE_FULL_SWEEP_N = 330


def _resolve_gemma_gguf() -> str:
    path = os.environ.get("DRIFTWOOD_GEMMA_GGUF_PATH") or str(
        Path.home() / "llama.cpp/models" / "gemma-4-26B-A4B-it-UD-Q4_K_M.gguf"
    )
    if not Path(path).is_file():
        raise FileNotFoundError(f"Gemma GGUF not found: {path}")
    return path


# ---------------------------------------------------------------------------
# Read (c): Opus-usage-rate extrapolation
# ---------------------------------------------------------------------------

@dataclass
class OpusUsageExtrapolation:
    """Read (c) — projects full-sweep cost/usage from the 6c batch.

    Per pre-reg v12 §"Protocol" step 11b read (c). Advisory — informs the
    subscription-vs-API-key fallback decision before step 12.
    """
    label: str
    n_trials: int
    full_sweep_n: int
    timestamp_iso: str
    bundle_id: str

    # Per-trial cost + tokens (means + 95% bootstrap CI on cost)
    per_trial_cost_usd_mean: float
    per_trial_cost_usd_ci_low: float
    per_trial_cost_usd_ci_high: float
    per_trial_input_tokens_mean: float
    per_trial_output_tokens_mean: float
    per_trial_wall_clock_seconds_mean: float

    # Projections to full sweep
    projected_full_sweep_cost_usd: float
    projected_full_sweep_cost_usd_ci_low: float
    projected_full_sweep_cost_usd_ci_high: float
    projected_full_sweep_input_tokens: float
    projected_full_sweep_output_tokens: float
    projected_full_sweep_wall_clock_hours: float

    # Per-condition breakdown (regime-constancy cross-check)
    per_condition_cost_mean: dict
    per_condition_n: dict

    # Auth-path decision rule (pre-committed at v12)
    subscription_budget_usd: float
    projected_pct_of_budget: float
    decision_recorded: str   # "continue_subscription" | "monitor" | "flip_api_key"


def _bootstrap_ci(values: list[float], n_resamples: int = 1000,
                  alpha: float = 0.05, seed: int = 42) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_resamples):
        s = sum(values[rng.randrange(n)] for _ in range(n))
        means.append(s / n)
    means.sort()
    lo = means[int(n_resamples * alpha / 2)]
    hi = means[int(n_resamples * (1 - alpha / 2))]
    return (lo, hi)


def compute_opus_usage_extrapolation(
    trial_records: list[dict],
    full_sweep_n: int,
    subscription_budget_usd: float,
) -> OpusUsageExtrapolation:
    costs: list[float] = []
    inputs: list[float] = []
    outputs: list[float] = []
    walls: list[float] = []
    per_cond: dict[str, list[float]] = {"A": [], "B": [], "C": []}

    for r in trial_records:
        extra = r.get("instrument_extra", {}) or {}
        cost = extra.get("claude_code_total_cost_usd")
        if cost is not None:
            try:
                cv = float(cost)
                costs.append(cv)
                cond = r.get("condition")
                if cond in per_cond:
                    per_cond[cond].append(cv)
            except (TypeError, ValueError):
                pass
        inputs.append(float(r.get("tokens_input", 0) or 0))
        outputs.append(float(r.get("tokens_output", 0) or 0))
        walls.append(float(r.get("wall_clock_seconds", 0.0) or 0.0))

    n = len(trial_records)
    cost_mean = (sum(costs) / len(costs)) if costs else 0.0
    cost_lo, cost_hi = _bootstrap_ci(costs) if costs else (0.0, 0.0)
    in_mean = (sum(inputs) / n) if inputs else 0.0
    out_mean = (sum(outputs) / n) if outputs else 0.0
    wc_mean = (sum(walls) / n) if walls else 0.0

    proj_cost = cost_mean * full_sweep_n
    proj_cost_lo = cost_lo * full_sweep_n
    proj_cost_hi = cost_hi * full_sweep_n
    pct_budget = (proj_cost / subscription_budget_usd * 100) if subscription_budget_usd > 0 else 0.0

    if pct_budget < 30:
        decision = "continue_subscription"
    elif pct_budget < 80:
        decision = "monitor"
    else:
        decision = "flip_api_key"

    return OpusUsageExtrapolation(
        label="pre_sweep",
        n_trials=n,
        full_sweep_n=full_sweep_n,
        timestamp_iso=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        bundle_id=CLAUDE_TRANSFER_PROBE_BUNDLE.bundle_id(),
        per_trial_cost_usd_mean=round(cost_mean, 4),
        per_trial_cost_usd_ci_low=round(cost_lo, 4),
        per_trial_cost_usd_ci_high=round(cost_hi, 4),
        per_trial_input_tokens_mean=round(in_mean, 1),
        per_trial_output_tokens_mean=round(out_mean, 1),
        per_trial_wall_clock_seconds_mean=round(wc_mean, 1),
        projected_full_sweep_cost_usd=round(proj_cost, 2),
        projected_full_sweep_cost_usd_ci_low=round(proj_cost_lo, 2),
        projected_full_sweep_cost_usd_ci_high=round(proj_cost_hi, 2),
        projected_full_sweep_input_tokens=round(in_mean * full_sweep_n, 0),
        projected_full_sweep_output_tokens=round(out_mean * full_sweep_n, 0),
        projected_full_sweep_wall_clock_hours=round((wc_mean * full_sweep_n) / 3600.0, 2),
        per_condition_cost_mean={c: round(sum(v) / len(v), 4) if v else 0.0
                                  for c, v in per_cond.items()},
        per_condition_n={c: len(v) for c, v in per_cond.items()},
        subscription_budget_usd=subscription_budget_usd,
        projected_pct_of_budget=round(pct_budget, 1),
        decision_recorded=decision,
    )


def write_opus_usage_extrapolation(result: OpusUsageExtrapolation,
                                    out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())
    fname = f"opus_usage_extrapolation_{result.label}_{ts}.json"
    path = out_dir / fname
    path.write_text(json.dumps(asdict(result), indent=2, default=str))
    return path


# ---------------------------------------------------------------------------
# Trial generation
# ---------------------------------------------------------------------------

def run_isolation_check() -> bool:
    """Quick wiring check before generating the 30 trials."""
    print("[+] Pre-flight: ClaudeInstrument isolation check (~$0.10–$0.50)...",
          file=sys.stderr)
    rc = subprocess.call(
        [sys.executable, "-m", "benchmark.harness.archived.verify_claude_isolation"],
        cwd=str(REPO_ROOT),
    )
    return rc == 0


def generate_6c_trials(shuffle_seed: int, judge: GemmaJudge,
                       trials_dir: Path) -> list[dict]:
    """Generate the 30 Claude easy trials in sweep-plan order; return TrialRecord dicts."""
    cells = [c for c in plan_sweep(subject="claude", shuffle_seed=shuffle_seed)
             if c.task == "easy"]
    print(f"[+] step 6c: generating {len(cells)} Claude easy trials "
          f"(shuffle_seed={shuffle_seed})...", file=sys.stderr)

    instrument = ClaudeInstrument(CLAUDE_TRANSFER_PROBE_BUNDLE)

    written: list[dict] = []
    t0 = time.monotonic()
    for i, cell in enumerate(cells, 1):
        task = load_task(task_type=cell.task, game=cell.game)
        t_cell_0 = time.monotonic()
        prefix = (f"  [{i:2d}/{len(cells)}] {cell.condition} {cell.game} "
                  f"seed={cell.seed} (order={cell.order_index})")
        print(f"{prefix}...", file=sys.stderr, end=" ", flush=True)
        try:
            record = run_trial(instrument, judge, task, cell.condition, cell.seed)
            path = write_trial_record(record, out_dir=trials_dir)
            elapsed_cell = time.monotonic() - t_cell_0
            print(f"OK ({elapsed_cell:.1f}s; intent="
                  f"{record.intent_score['score']}, "
                  f"checklist={record.checklist_verdict['fraction_passing']:.2f})",
                  file=sys.stderr)
            written.append(json.loads(path.read_text()))
        except Exception as e:
            elapsed_cell = time.monotonic() - t_cell_0
            print(f"FAIL ({elapsed_cell:.1f}s): {type(e).__name__}: {e}",
                  file=sys.stderr)
            raise

    elapsed = time.monotonic() - t0
    print(f"[+] generation done: {len(cells)} trials in {elapsed:.1f}s "
          f"({elapsed/max(len(cells),1):.1f}s/call avg)", file=sys.stderr)
    return written


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _print_sanitizer_generalization(result) -> None:
    print()
    print("=== SANITIZER-GENERALIZATION (step 6c read a — GATE) ===")
    print(f"  judge:        {result.judge_bundle_id}")
    print(f"  sanitization: {result.sanitization_sha256[:16]}...")
    print(f"  n_outputs:    {result.n_outputs}")
    print(f"  accuracy:     {result.accuracy:.3f}")
    print(f"  95% Wilson CI: [{result.accuracy_95_ci_low:.3f}, "
          f"{result.accuracy_95_ci_high:.3f}]")
    print(f"  chance:       {result.chance_accuracy:.3f}")
    print(f"  pass criterion: CI includes 1/3")
    print(f"  PASS: {result.passed}")
    if result.notes:
        print(f"  notes: {result.notes}")


def _print_regime_constancy(result) -> None:
    print()
    print("=== REGIME-CONSTANCY ON CLAUDE ARM (step 6c read b — ADVISORY) ===")
    print(f"  label:    {result.label}")
    print(f"  n_trials: {result.n_trials_total}")
    print()
    for c in result.cells:
        print(f"  [{c.subject_bundle_id}] {c.condition}: n={c.n_trials}  "
              f"error_rate={c.error_rate:.3f}")
        for metric_name, _ in REGIME_METRICS:
            d = c.metrics[metric_name]
            if d.n == 0:
                continue
            print(f"    {metric_name}: n={d.n} mean={d.mean} "
                  f"median={d.median} p25={d.p25} p75={d.p75}")
        if c.stop_reason_counts:
            print(f"    stop_reason: {dict(c.stop_reason_counts)}")
        if c.subtype_counts:
            print(f"    subtype:     {dict(c.subtype_counts)}")
    print()
    if result.overall_comparable:
        print("  RESULT: NO FLAGS — distributions comparable within thresholds")
    else:
        print(f"  RESULT: {len(result.flags)} FLAG(S):")
        for f in result.flags:
            print(f"    flag: [{f.subject_bundle_id}] {f.metric}  "
                  f"means={f.cell_means}  ratio/spread={f.max_min_ratio}")
            print(f"          {f.rationale}")


def _print_opus_usage(r: OpusUsageExtrapolation) -> None:
    print()
    print("=== OPUS-USAGE-RATE EXTRAPOLATION (step 6c read c — ADVISORY) ===")
    print(f"  bundle:              {r.bundle_id}")
    print(f"  n_trials (6c batch): {r.n_trials}")
    print(f"  full sweep N:        {r.full_sweep_n}")
    print(f"  per-trial cost:      ${r.per_trial_cost_usd_mean:.4f}  "
          f"[${r.per_trial_cost_usd_ci_low:.4f}, "
          f"${r.per_trial_cost_usd_ci_high:.4f}]  (95% bootstrap CI)")
    print(f"  per-trial tokens:    in={r.per_trial_input_tokens_mean:.0f}  "
          f"out={r.per_trial_output_tokens_mean:.0f}")
    print(f"  per-trial wall:      {r.per_trial_wall_clock_seconds_mean:.1f}s")
    print()
    print(f"  PROJECTED FULL SWEEP (×{r.full_sweep_n}):")
    print(f"    cost:          ${r.projected_full_sweep_cost_usd:.2f}  "
          f"[${r.projected_full_sweep_cost_usd_ci_low:.2f}, "
          f"${r.projected_full_sweep_cost_usd_ci_high:.2f}]")
    print(f"    input tokens:  {r.projected_full_sweep_input_tokens:,.0f}")
    print(f"    output tokens: {r.projected_full_sweep_output_tokens:,.0f}")
    print(f"    wall clock:    {r.projected_full_sweep_wall_clock_hours:.1f}h")
    print()
    print(f"  subscription budget (weekly): ${r.subscription_budget_usd:.2f}")
    print(f"  projected pct of budget:      {r.projected_pct_of_budget:.1f}%")
    print(f"  DECISION (pre-committed rule): {r.decision_recorded.upper()}")
    rule = {
        "continue_subscription": "< 30% budget — continue on subscription",
        "monitor": "30–80% budget — continue on subscription with monitoring",
        "flip_api_key": "> 80% budget — flip to API-key fallback BEFORE step 12",
    }[r.decision_recorded]
    print(f"    rationale: {rule}")
    print()
    print("  Per-condition cost mean:")
    for c in ("A", "B", "C"):
        v = r.per_condition_cost_mean.get(c, 0.0)
        n = r.per_condition_n.get(c, 0)
        print(f"    {c}: ${v:.4f}  (n={n})")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--shuffle-seed", type=int, default=12345,
        help="Sweep-plan shuffle seed (default 12345; must match what trial zero "
             "will use for fold-in under the v12 provenance rule).",
    )
    parser.add_argument(
        "--subscription-budget-usd", type=float, default=50.0,
        help="User's weekly Claude Code subscription budget in USD "
             "(default $50/wk; adjust per actual plan).",
    )
    parser.add_argument(
        "--skip-trials", action="store_true",
        help="Skip trial generation; re-run reads on existing easy-task Claude "
             "trial records in --trials-dir.",
    )
    parser.add_argument(
        "--skip-isolation-check", action="store_true",
        help="Skip the ClaudeInstrument isolation pre-flight check (use only if "
             "verify_claude_isolation has already passed against the current bundle).",
    )
    parser.add_argument(
        "--trials-dir", type=Path, default=TRIALS_DIR,
        help="TrialRecord directory.",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=AUDITS_DIR,
        help="Audit artifact directory.",
    )
    args = parser.parse_args()

    args.trials_dir.mkdir(parents=True, exist_ok=True)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Pre-flight: isolation
    if not args.skip_trials and not args.skip_isolation_check:
        if not run_isolation_check():
            print("\nFAIL: isolation pre-flight check failed. Fix wiring before "
                  "generating 6c trials.", file=sys.stderr)
            return 1

    # Boot Gemma judge (trial-time scoring + sanitizer-generalization read)
    gguf_gemma = _resolve_gemma_gguf()
    print(f"\n[+] Judge: booting Gemma llama-server (--reasoning off)...",
          file=sys.stderr)
    t0 = time.monotonic()
    written_records: list[dict] = []
    gen_result = None
    with GemmaJudge(GEMMA_JUDGE_BUNDLE, gguf_path=gguf_gemma, port=GEMMA_PORT) as judge:
        if not args.skip_trials:
            written_records = generate_6c_trials(args.shuffle_seed, judge,
                                                  args.trials_dir)
        else:
            print(f"[+] --skip-trials: loading existing trial records from "
                  f"{args.trials_dir}", file=sys.stderr)
            all_records = regime_load_trials(args.trials_dir)
            written_records = [
                r for r in all_records
                if r.get("task_cell_id", "").startswith("easy_")
                and "claude" in (r.get("subject_bundle_id", "").lower())
            ]
            print(f"    loaded {len(written_records)} matching records",
                  file=sys.stderr)

        if not written_records:
            print("\nFAIL: no trial records to score.", file=sys.stderr)
            return 1

        # Read (a): sanitizer-generalization
        print(f"\n[+] Step 6c read (a): sanitizer-generalization on "
              f"{len(written_records)} trials...", file=sys.stderr)
        gen_inputs = [
            (i, r["condition"], r["subject_output"])
            for i, r in enumerate(written_records)
            if r.get("condition") and r.get("subject_output")
        ]
        gen_result = check_blinding_generalization(judge, gen_inputs,
                                                    label="pre_sweep")
    print(f"    Gemma phase total {time.monotonic() - t0:.1f}s; torn down",
          file=sys.stderr)

    # Read (b): regime-constancy (no judge needed)
    print(f"\n[+] Step 6c read (b): regime-constancy analysis...",
          file=sys.stderr)
    regime_result = regime_analyze(written_records, label="pre_sweep",
                                    trials_dir=args.trials_dir)

    # Read (c): Opus-usage-rate extrapolation
    print(f"\n[+] Step 6c read (c): Opus-usage-rate extrapolation...",
          file=sys.stderr)
    opus_result = compute_opus_usage_extrapolation(
        written_records,
        full_sweep_n=CLAUDE_FULL_SWEEP_N,
        subscription_budget_usd=args.subscription_budget_usd,
    )

    # Print + write artifacts
    _print_sanitizer_generalization(gen_result)
    gen_path = write_generalization_check_result(gen_result, args.out_dir)
    print(f"[+] artifact: {gen_path}", file=sys.stderr)

    _print_regime_constancy(regime_result)
    regime_path = regime_write_result(regime_result, args.out_dir)
    print(f"[+] artifact: {regime_path}", file=sys.stderr)

    _print_opus_usage(opus_result)
    opus_path = write_opus_usage_extrapolation(opus_result, args.out_dir)
    print(f"[+] artifact: {opus_path}", file=sys.stderr)

    # Summary
    print()
    print("=== STEP 6c SUMMARY ===")
    print(f"  (a) sanitizer-generalization: "
          f"{'PASS' if gen_result.passed else 'FAIL'}  (GATE — required for step 12)")
    print(f"      accuracy={gen_result.accuracy:.3f}, "
          f"CI=[{gen_result.accuracy_95_ci_low:.3f}, "
          f"{gen_result.accuracy_95_ci_high:.3f}], chance=0.333")
    flags_summary = ("NO FLAGS" if regime_result.overall_comparable
                     else f"{len(regime_result.flags)} FLAG(S)")
    print(f"  (b) regime-constancy:         {flags_summary}  "
          f"(ADVISORY — reported in F-009)")
    print(f"  (c) Opus-usage-rate decision: {opus_result.decision_recorded.upper()}  "
          f"(ADVISORY — auth-path)")
    print(f"      projected full sweep: ${opus_result.projected_full_sweep_cost_usd:.2f}  "
          f"({opus_result.projected_pct_of_budget:.1f}% of "
          f"${opus_result.subscription_budget_usd:.0f}/wk budget)")
    print()
    if gen_result.passed:
        print("PASS: sanitizer-generalization cleared. Step 12 unblocked pending "
              "decisions on (b) + (c).")
        print(f"Provenance: 6c trials valid under v11 sanitizer SHA "
              f"`{gen_result.sanitization_sha256[:16]}...`; fold into sweep dataset "
              f"at trial zero (per v12 provenance rule).")
        return 0
    else:
        print("FAIL: sanitizer-generalization did not pass. Apply the pre-committed "
              "sanitizer-iteration stopping rule:")
        print("  (1) diagnosis-driven (name the specific tell the judge cited)")
        print("  (2) closed-enumeration or structural drawn from spec vocabulary")
        print("  (3) Phase B passes (content-preservation counterweight holds)")
        print("Loop terminates by running out of principled fixes, NOT gate passing.")
        print("6c trials require re-sanitization + re-scoring under new SHA, OR discard.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
