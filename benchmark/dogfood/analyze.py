"""Rule V verdict, computed exactly as D-025 locks it (views vs baseline).

    python analyze.py rule-v <results.jsonl> [<results.jsonl> ...] [--json]

Pass the matrix run's JSONL plus any `--supersedes` re-run files and the
guarded-task extension run (repeats 4-5). Committed before any matrix data
(D-025 amendment 5), so the verdict is not computed by code written after
the results were seen.

Resolutions of points the locked text leaves open (recorded in amendment 5):
- A cell's effective line is the last line that `supersedes` it; otherwise
  its own line. A second `error` stays an `error` (not-success).
- The primary median per task and arm is over the effective lines of
  repeats 1-3 that have a `consultation_bytes` value; a line without one
  (an `error` with no session) is listed and left out of the median.
- An apparatus NULL (errors > 10%, contamination > 10% in an arm, or the
  manipulation check failing) decides the verdict: the data cannot support
  PASS or FAIL.
- Contamination: an `out_of_copy_access` entry naming the harness
  (`benchmark/dogfood` or `test_dogfood.py`). Conservative: a denied attempt
  also counts, and every case is listed for review.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

DOGFOOD = Path(__file__).resolve().parent
RESULTS_DIR = DOGFOOD / "results"
GUARDED = ("maintenance_drift", "negative_control_no_drift")
X = 0.30          # PASS threshold on R
Y = 0.10          # non-inferiority margin on the pooled success rate
APPARATUS_MAX = 0.10
HARNESS_MARKERS = ("benchmark/dogfood", "test_dogfood.py")


def load(paths: list[Path]) -> list[dict]:
    lines = []
    for p in paths:
        lines += [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]
    return lines


def effective(lines: list[dict]) -> dict[tuple[str, str, int], dict]:
    """(task, arm, repeat) -> the line that counts, after `supersedes`."""
    by_cell_id = {f"{ln['run_id']}/{ln['cell_id']}": ln for ln in lines}
    out: dict[tuple[str, str, int], dict] = {}
    superseded = {ln["supersedes"] for ln in lines if ln.get("supersedes")}
    for ln in lines:
        key = (ln["task_id"], ln["arm"], ln["repeat"])
        if f"{ln['run_id']}/{ln['cell_id']}" in superseded:
            continue
        out[key] = ln
    for s in superseded:
        if s not in by_cell_id:
            raise SystemExit(f"supersedes {s!r}: no such line in the inputs")
    return out


def contaminated(line: dict, metrics: dict | None) -> list[str]:
    entries = (metrics or {}).get("out_of_copy_access") or []
    hits = []
    for e in entries:
        path = str(e.get("path") or e.get("file_path") or e.get("notebook_path") or "")
        if any(m in path for m in HARNESS_MARKERS):
            hits.append(path)
    return hits


def metrics_for(line: dict) -> dict | None:
    p = RESULTS_DIR / line["run_id"] / "metrics" / f"{line['cell_id']}.metrics.json"
    return json.loads(p.read_text()) if p.is_file() else None


def rule_v(lines: list[dict], metrics_loader=metrics_for) -> dict:
    eff = effective(lines)
    tasks = sorted({t for t, _, _ in eff})
    main = {k: v for k, v in eff.items() if k[2] <= 3}
    ext = {k: v for k, v in eff.items() if k[2] >= 4}

    contam = {k: contaminated(v, metrics_loader(v)) for k, v in eff.items()}

    def ok(k) -> bool:
        return eff[k]["outcome"] == "success" and not contam[k]

    # ---- apparatus ---------------------------------------------------------------
    n_main = len(main)
    errors = [k for k in main if main[k]["outcome"] == "error"]
    apparatus: list[str] = []
    if n_main and len(errors) / n_main > APPARATUS_MAX:
        apparatus.append(f"errors {len(errors)}/{n_main} > 10%")
    for arm in ("baseline", "views"):
        arm_keys = [k for k in main if k[1] == arm]
        c = [k for k in arm_keys if contam[k]]
        if arm_keys and len(c) / len(arm_keys) > APPARATUS_MAX:
            apparatus.append(f"contamination in {arm}: {len(c)}/{len(arm_keys)} > 10%")
    views_calls = [(main[k].get("gdmd_view_calls") or 0) + (main[k].get("gdmd_graph_calls") or 0)
                   for k in main if k[1] == "views"]
    manipulation = statistics.median(views_calls) if views_calls else 0
    if manipulation < 1:
        apparatus.append(f"manipulation check: median view+graph calls per views run "
                         f"= {manipulation} < 1")

    # ---- primary -----------------------------------------------------------------
    per_task = {}
    missing = []
    for t in tasks:
        med = {}
        for arm in ("baseline", "views"):
            vals = []
            for r in (1, 2, 3):
                ln = main.get((t, arm, r))
                if ln is None or ln.get("consultation_bytes") is None:
                    missing.append(f"{t}/{arm}/r{r}")
                    continue
                vals.append(ln["consultation_bytes"])
            med[arm] = statistics.median(vals) if vals else None
        b, v = med["baseline"], med["views"]
        if b is None or v is None:
            r_t = None
        elif b == 0:
            r_t = 0.0 if v == 0 else -1.0
        else:
            r_t = 1 - v / b
        per_task[t] = {"median_baseline": b, "median_views": v, "r_t": r_t}
    rs = [d["r_t"] for d in per_task.values() if d["r_t"] is not None]
    R = statistics.median(rs) if rs else None

    # ---- non-inferiority -----------------------------------------------------------
    succ = {arm: sum(1 for k in main if k[1] == arm and ok(k)) for arm in ("baseline", "views")}
    runs = {arm: sum(1 for k in main if k[1] == arm) for arm in ("baseline", "views")}
    rate = {arm: (succ[arm] / runs[arm] if runs[arm] else None) for arm in succ}
    clause1 = None if None in rate.values() else (rate["baseline"] - rate["views"]) <= Y + 1e-9

    guarded = {}
    extension_required = False
    for t in GUARDED:
        def not_success(arm, reps, pool):
            return sum(1 for r in reps if (t, arm, r) in pool and not ok((t, arm, r)))
        e3 = not_success("views", (1, 2, 3), eff) - not_success("baseline", (1, 2, 3), eff)
        g = {"e_t_r1_3": e3}
        if e3 == 1:
            have_ext = all((t, a, r) in ext for a in ("baseline", "views") for r in (4, 5))
            if have_ext:
                e5 = not_success("views", (1, 2, 3, 4, 5), eff) - \
                    not_success("baseline", (1, 2, 3, 4, 5), eff)
                g["e_t_r1_5"] = e5
                g["state"] = "holds" if e5 <= 0 else ("FAIL" if e5 >= 2 else "NULL")
            else:
                extension_required = True
                g["state"] = "extension required"
        else:
            g["state"] = "holds" if e3 <= 0 else "FAIL"
        guarded[t] = g

    # ---- verdict -------------------------------------------------------------------
    reasons = []
    if apparatus:
        verdict = "NULL (apparatus)"
        reasons = apparatus
    elif extension_required:
        verdict = "PENDING: run the pre-registered extension (repeats 4-5, guarded tasks)"
    else:
        fail = []
        if R is not None and R <= 0:
            fail.append(f"R = {R:.3f} <= 0")
        if clause1 is False:
            fail.append("non-inferiority clause 1 violated")
        fail += [f"{t}: e_t >= 2" for t, g in guarded.items() if g["state"] == "FAIL"]
        if fail:
            verdict, reasons = "FAIL", fail
        elif R is not None and R >= X and clause1 and \
                all(g["state"] == "holds" for g in guarded.values()):
            verdict, reasons = "PASS", [f"R = {R:.3f} >= {X}", "non-inferiority holds"]
        else:
            verdict = "NULL"
            if R is not None and 0 < R < X:
                reasons.append(f"0 < R = {R:.3f} < {X}")
            reasons += [f"{t}: e_t = 1 after the extension" for t, g in guarded.items()
                        if g["state"] == "NULL"]
            if R is None:
                reasons.append("R undefined (missing medians)")

    outcomes = {arm: {} for arm in ("baseline", "views")}
    for k, ln in main.items():
        o = outcomes[k[1]]
        o[ln["outcome"]] = o.get(ln["outcome"], 0) + 1
    return {
        "verdict": verdict, "reasons": reasons, "R": R, "X": X, "per_task": per_task,
        "non_inferiority": {"successes": succ, "runs": runs, "rates": rate,
                            "clause1_holds": clause1, "guarded": guarded},
        "manipulation_check": {"median_view_graph_calls_views": manipulation,
                               "baseline_attempts": sum(
                                   (main[k].get("gdmd_view_calls") or 0)
                                   + (main[k].get("gdmd_graph_calls") or 0)
                                   for k in main if k[1] == "baseline")},
        "apparatus": {"errors": [f"{t}/{a}/r{r}" for t, a, r in errors],
                      "contaminated": {f"{t}/{a}/r{r}": v for (t, a, r), v in contam.items()
                                       if v},
                      "missing_primary": missing},
        "outcomes": outcomes,
        "n_main": n_main, "n_extension": len(ext),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="D-025 Rule V verdict")
    ap.add_argument("rule", choices=["rule-v"])
    ap.add_argument("results", nargs="+", type=Path)
    a = ap.parse_args(argv)
    print(json.dumps(rule_v(load(a.results)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
