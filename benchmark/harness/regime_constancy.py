"""Per-(subject, condition) regime-constancy check for trial outputs.

Verifies, post-trial, that num_turns / tokens / cost / stop_reason
distributions are comparable across A/B/C within each subject — turning
the cross-condition regime-constancy assumption into a measured fact.

Why this matters: the within-subject cost-lift gate is one of the two
headline gates (success-lift ≥ MDE AND cost-lift ≤ 25%). It's a ratio
on per-condition mean tokens / cost. If Claude under context-poor
prompts (C) triggers more agentic-flailing turns than under
context-rich prompts (A), per-condition costs diverge for reasons other
than what the spec actually costs — regime-distorting the cost-lift
gate rather than measuring it cleanly. Same logic applies to
stop_reason distributions, per-condition error_max_turns rates, and
turn counts.

Verification has the same shape as the calibration apparatus's other
generalization checks (see pre-reg §"Judge" Layer 3c, memory
`train-test-distribution-shift-sanitizer`): assumption → empirical
measurement on the actual data. Comparable distributions → cost-lift
gate is clean and you've SHOWN it. Divergent distributions → you've
found a confound on a headline gate before publishing it.

Two timepoints (the same shape as the sanitizer-generalization checks):

  Pre-sweep batch (N=12–30 real trials, before the full sweep). Wide
  CIs, advisory only — but a 5x divergence in cell means is visible at
  small N. Catches the regime problem early enough to mitigate (e.g.,
  tighten the anti-flailing steer) before committing to the full sweep.

  Post-hoc full-sweep sample (or all 660 trials). Tighter descriptives;
  recorded with F-009 as part of the cost-lift headline's evidence
  chain. A divergent regime here is reported as a stated limitation on
  the cost-lift gate, NOT as grounds for excluding trials (exclusion
  could itself be condition-dependent and bias the success-lift
  headline; see pre-reg §"Test subjects").

The advisory heuristics below flag cells where (max cell mean / min
cell mean) on any single metric exceeds 2.0x, OR per-condition error
rate spread exceeds 10pp. These are conservative thresholds appropriate
for the conservative MDE-25pp regime; they're guides, not gates.

Output: structured JSON artifact written to
`benchmark/harness/audits/regime_constancy_<ts>.json`.

CLI:
  python -m benchmark.harness.regime_constancy [--trials-dir <dir>] [--label <name>]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
TRIALS_DIR = HARNESS_DIR / "trials"
AUDITS_DIR = HARNESS_DIR / "audits"


# Pre-registered advisory thresholds (per-subject; flags only, not gates).
CELL_MEAN_RATIO_FLAG = 2.0          # max(cell_mean)/min(cell_mean) ≥ 2x → flag
ERROR_RATE_SPREAD_FLAG_PP = 10.0    # (max - min) error rate across cells ≥ 10pp → flag

# Metrics to compute per (subject, condition) cell.
# For each: pull the value from either the top-level TrialRecord JSON or from
# the instrument_extra dict.
METRICS: tuple[tuple[str, str], ...] = (
    ("tokens_input", "top"),
    ("tokens_output", "top"),
    ("wall_clock_seconds", "top"),
    ("tool_steps", "top"),
    ("claude_code_num_turns", "extra"),
    ("claude_code_total_cost_usd", "extra"),
    ("claude_code_duration_ms", "extra"),
    ("claude_code_cache_creation_input_tokens", "extra"),
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Descriptive:
    """Distribution summary for one metric in one (subject, condition) cell."""
    n: int
    mean: float | None
    median: float | None
    p25: float | None
    p75: float | None
    minimum: float | None
    maximum: float | None
    n_missing: int   # count of records where this metric was absent / null


@dataclass(frozen=True)
class CellSummary:
    """All metrics + error-state for one (subject, condition) cell."""
    subject_bundle_id: str
    condition: str
    n_trials: int
    metrics: dict[str, Descriptive]               # metric_name -> Descriptive
    error_rate: float                              # fraction is_error or non-success subtype
    stop_reason_counts: dict[str, int]             # counts of each stop_reason
    subtype_counts: dict[str, int]                 # counts of each subtype


@dataclass(frozen=True)
class WithinSubjectFlag:
    """One advisory flag for a within-subject regime divergence."""
    subject_bundle_id: str
    metric: str
    cell_means: dict[str, float | None]   # condition -> mean
    max_min_ratio: float | None
    flag_threshold: float
    rationale: str


@dataclass(frozen=True)
class RegimeConstancyResult:
    label: str                                  # "pre_sweep" | "post_hoc" | freeform
    trials_dir: str
    n_trials_total: int
    cells: list[CellSummary] = field(default_factory=list)
    flags: list[WithinSubjectFlag] = field(default_factory=list)
    overall_comparable: bool = True             # advisory verdict


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

def load_trials(trials_dir: Path) -> list[dict]:
    """Read every `*.json` under trials_dir; return list of TrialRecord dicts."""
    out: list[dict] = []
    for p in sorted(trials_dir.glob("*.json")):
        out.append(json.loads(p.read_text()))
    return out


def analyze(trials: list[dict], label: str = "post_hoc",
            trials_dir: Path = TRIALS_DIR) -> RegimeConstancyResult:
    """Compute per-(subject, condition) descriptives + flags."""
    # Group trials by (subject_bundle_id, condition)
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for t in trials:
        sub = t.get("subject_bundle_id", "<unknown>")
        cond = t.get("condition", "<unknown>")
        groups[(sub, cond)].append(t)

    cells: list[CellSummary] = []
    for (sub, cond), records in sorted(groups.items()):
        metrics_summary: dict[str, Descriptive] = {}
        for metric_name, source in METRICS:
            values = _extract_values(records, metric_name, source)
            metrics_summary[metric_name] = _describe(values, total_n=len(records))

        # Error rate: fraction of records with is_error=True OR subtype != "success"
        # (handles both Claude error_max_turns and other instruments' error modes).
        errors = 0
        for r in records:
            extra = r.get("instrument_extra", {}) or {}
            is_err = bool(extra.get("claude_code_is_error"))
            subtype = extra.get("claude_code_subtype")
            if is_err or (subtype is not None and subtype != "success"):
                errors += 1
        error_rate = errors / len(records) if records else 0.0

        # Categorical histograms
        stop_reasons = Counter(
            (r.get("instrument_extra", {}) or {}).get("claude_code_stop_reason", "<none>")
            for r in records
        )
        subtypes = Counter(
            (r.get("instrument_extra", {}) or {}).get("claude_code_subtype", "<none>")
            for r in records
        )

        cells.append(CellSummary(
            subject_bundle_id=sub,
            condition=cond,
            n_trials=len(records),
            metrics=metrics_summary,
            error_rate=error_rate,
            stop_reason_counts=dict(stop_reasons),
            subtype_counts=dict(subtypes),
        ))

    # Within-subject flags
    flags: list[WithinSubjectFlag] = []
    cells_by_subject: dict[str, list[CellSummary]] = defaultdict(list)
    for c in cells:
        cells_by_subject[c.subject_bundle_id].append(c)

    for sub, sub_cells in cells_by_subject.items():
        # Per-metric cell-mean ratio across conditions for this subject
        for metric_name, _src in METRICS:
            means = {
                c.condition: c.metrics[metric_name].mean
                for c in sub_cells
                if c.metrics[metric_name].mean is not None
            }
            if len(means) < 2:
                continue
            vals = [v for v in means.values() if v is not None and v > 0]
            if len(vals) < 2:
                continue
            ratio = max(vals) / min(vals)
            if ratio >= CELL_MEAN_RATIO_FLAG:
                flags.append(WithinSubjectFlag(
                    subject_bundle_id=sub,
                    metric=metric_name,
                    cell_means={c: round(v, 3) if v is not None else None
                                for c, v in means.items()},
                    max_min_ratio=round(ratio, 3),
                    flag_threshold=CELL_MEAN_RATIO_FLAG,
                    rationale=(
                        f"max/min ratio of cell means for {metric_name} = "
                        f"{ratio:.2f}x ≥ flag threshold {CELL_MEAN_RATIO_FLAG}x. "
                        "Within-subject regime divergence across conditions; "
                        "if this is on tokens or cost, the within-subject "
                        "cost-lift gate may be regime-distorted rather than "
                        "measuring spec-format cost cleanly."
                    ),
                ))

        # Per-subject error-rate spread across conditions
        err_rates = {c.condition: c.error_rate for c in sub_cells}
        if len(err_rates) >= 2:
            spread_pp = (max(err_rates.values()) - min(err_rates.values())) * 100
            if spread_pp >= ERROR_RATE_SPREAD_FLAG_PP:
                flags.append(WithinSubjectFlag(
                    subject_bundle_id=sub,
                    metric="error_rate",
                    cell_means={c: round(r, 4) for c, r in err_rates.items()},
                    max_min_ratio=round(spread_pp, 2),
                    flag_threshold=ERROR_RATE_SPREAD_FLAG_PP,
                    rationale=(
                        f"error rate spread across conditions = {spread_pp:.1f}pp "
                        f"≥ flag threshold {ERROR_RATE_SPREAD_FLAG_PP}pp. "
                        "Condition-dependent error rate; counts as failure "
                        "per pre-reg (no exclusion, no retry), but reported "
                        "alongside F-009 as a transfer-probe limitation if "
                        "the spread is on the Claude arm."
                    ),
                ))

    overall_comparable = len(flags) == 0
    return RegimeConstancyResult(
        label=label,
        trials_dir=str(trials_dir),
        n_trials_total=len(trials),
        cells=cells,
        flags=flags,
        overall_comparable=overall_comparable,
    )


def write_result(result: RegimeConstancyResult, out_dir: Path = AUDITS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())
    fname = f"regime_constancy_{result.label}_{ts}.json"
    path = out_dir / fname
    path.write_text(json.dumps(_to_jsonable(result), indent=2, default=str))
    return path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_values(records: list[dict], metric: str, source: str) -> list[float]:
    out: list[float] = []
    for r in records:
        if source == "top":
            v = r.get(metric)
        elif source == "extra":
            v = (r.get("instrument_extra", {}) or {}).get(metric)
        else:
            v = None
        if v is None:
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def _describe(values: list[float], total_n: int) -> Descriptive:
    if not values:
        return Descriptive(
            n=0, mean=None, median=None, p25=None, p75=None,
            minimum=None, maximum=None, n_missing=total_n,
        )
    s = sorted(values)
    n = len(s)
    mean = sum(s) / n
    median = _quantile(s, 0.5)
    p25 = _quantile(s, 0.25)
    p75 = _quantile(s, 0.75)
    return Descriptive(
        n=n, mean=round(mean, 4), median=round(median, 4),
        p25=round(p25, 4), p75=round(p75, 4),
        minimum=round(s[0], 4), maximum=round(s[-1], 4),
        n_missing=total_n - n,
    )


def _quantile(sorted_values: list[float], q: float) -> float:
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    pos = q * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def _to_jsonable(obj):
    from dataclasses import is_dataclass, fields
    if is_dataclass(obj):
        return {f.name: _to_jsonable(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(o) for o in obj]
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_report(result: RegimeConstancyResult) -> None:
    print(f"Regime constancy: label={result.label}  trials={result.n_trials_total}")
    print(f"  trials_dir: {result.trials_dir}")
    print()
    for c in result.cells:
        print(f"  [{c.subject_bundle_id}] {c.condition}: n={c.n_trials}  "
              f"error_rate={c.error_rate:.3f}")
        for metric_name, _ in METRICS:
            d = c.metrics[metric_name]
            if d.n == 0:
                continue
            print(f"    {metric_name}: n={d.n} mean={d.mean} median={d.median} "
                  f"p25={d.p25} p75={d.p75}  (missing={d.n_missing})")
        if c.stop_reason_counts:
            print(f"    stop_reason: {dict(c.stop_reason_counts)}")
        if c.subtype_counts:
            print(f"    subtype:     {dict(c.subtype_counts)}")
        print()

    print(f"OVERALL: {'COMPARABLE' if result.overall_comparable else 'FLAGS'} "
          f"({len(result.flags)} flag(s))")
    for f in result.flags:
        print(f"  flag: [{f.subject_bundle_id}] {f.metric}  "
              f"means={f.cell_means}  ratio/spread={f.max_min_ratio}")
        print(f"        {f.rationale}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--trials-dir", default=str(TRIALS_DIR),
                   help="Directory of TrialRecord *.json files.")
    p.add_argument("--label", default="post_hoc",
                   help="Label for the artifact (pre_sweep | post_hoc | freeform).")
    p.add_argument("--no-write", action="store_true",
                   help="Print report only; do not write JSON artifact.")
    args = p.parse_args(argv)

    trials_dir = Path(args.trials_dir)
    if not trials_dir.exists() or not list(trials_dir.glob("*.json")):
        print(f"No trial records found in {trials_dir}.", file=sys.stderr)
        return 2

    trials = load_trials(trials_dir)
    result = analyze(trials, label=args.label, trials_dir=trials_dir)
    _print_report(result)

    if not args.no_write:
        path = write_result(result)
        print(f"\nWrote: {path}")

    return 0 if result.overall_comparable else 1


if __name__ == "__main__":
    sys.exit(main())
