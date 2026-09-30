"""Rule V and Rule C verdicts, computed exactly as D-025 locks them.

    python analyze.py rule-v <results.jsonl> [<results.jsonl> ...]
    python analyze.py rule-c <results.jsonl> [...] --probe <import-probe.json>
    python analyze.py rule-v2 <results.jsonl> [...]                    # D-026 study 2
    python analyze.py rule-c2 <results.jsonl> [...] --probe <import-probe.json>

Rules V2 and C2 are D-025's computations unchanged, with study 2's guarded
tasks (D-026: "identical to D-025, including the extension"). Committed
before any study-2 data. Each command refuses lines from the other study.

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
GUARDED_S2 = ("s2_maintenance", "s2_negative_control")      # D-026
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


def rule_v(lines: list[dict], metrics_loader=metrics_for,
           guarded_tasks: tuple[str, ...] = GUARDED) -> dict:
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
    for t in guarded_tasks:
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


def rule_c(lines: list[dict], delta: float, metrics_loader=metrics_for,
           precondition_met: bool = True, guarded_tasks: tuple[str, ...] = GUARDED) -> dict:
    """Rule C (the card-import ablation), as D-025 locks it.

    Cells `import-full` (control) and `import-card` (treatment). Primary:
    median per-turn occupancy per run; per task, the median over repeats 1-3
    of each cell (`M_full,t`, `M_card,t`); `d_t = M_full,t - M_card,t`;
    `D` = the median over tasks of `d_t`. PASS needs `D >= 0.5 * delta`
    (delta = the matrix-world import probe's `spec_import_tokens` at the
    Rule C commit) and non-inferiority, with no guarded task left at e_t = 1.
    FAIL: clause 1 violated or a guarded task at e_t >= 2. Otherwise NULL,
    including an unmet precondition (D-024 §2; met at the pilot) or an
    apparatus NULL. The four resolutions of rule_v apply (amendment 5).
    """
    ctl, trt = "import-full", "import-card"
    eff = {k: v for k, v in effective(lines).items() if k[1] in (ctl, trt)}
    tasks = sorted({t for t, _, _ in eff})
    main = {k: v for k, v in eff.items() if k[2] <= 3}
    ext = {k: v for k, v in eff.items() if k[2] >= 4}
    contam = {k: contaminated(v, metrics_loader(v)) for k, v in eff.items()}

    def ok(k) -> bool:
        return eff[k]["outcome"] == "success" and not contam[k]

    n_main = len(main)
    errors = [k for k in main if main[k]["outcome"] == "error"]
    apparatus: list[str] = []
    if n_main and len(errors) / n_main > APPARATUS_MAX:
        apparatus.append(f"errors {len(errors)}/{n_main} > 10%")
    for arm in (ctl, trt):
        arm_keys = [k for k in main if k[1] == arm]
        c = [k for k in arm_keys if contam[k]]
        if arm_keys and len(c) / len(arm_keys) > APPARATUS_MAX:
            apparatus.append(f"contamination in {arm}: {len(c)}/{len(arm_keys)} > 10%")

    per_task, missing = {}, []
    for t in tasks:
        med = {}
        for arm in (ctl, trt):
            vals = []
            for r in (1, 2, 3):
                ln = main.get((t, arm, r))
                if ln is None or ln.get("median_turn_occupancy") is None:
                    missing.append(f"{t}/{arm}/r{r}")
                    continue
                vals.append(ln["median_turn_occupancy"])
            med[arm] = statistics.median(vals) if vals else None
        f, c = med[ctl], med[trt]
        d_t = (f - c) if None not in (f, c) else None
        per_task[t] = {"M_full": f, "M_card": c, "d_t": d_t,
                       "d_t_over_delta": (d_t / delta) if d_t is not None and delta else None,
                       "relative_reduction": (1 - c / f) if d_t is not None and f else None}
    ds = [d["d_t"] for d in per_task.values() if d["d_t"] is not None]
    D = statistics.median(ds) if ds else None
    threshold = 0.5 * delta

    succ = {arm: sum(1 for k in main if k[1] == arm and ok(k)) for arm in (ctl, trt)}
    runs = {arm: sum(1 for k in main if k[1] == arm) for arm in (ctl, trt)}
    rate = {arm: (succ[arm] / runs[arm] if runs[arm] else None) for arm in succ}
    clause1 = None if None in rate.values() else (rate[ctl] - rate[trt]) <= Y + 1e-9
    guarded, extension_required = {}, False
    for t in guarded_tasks:
        def not_success(arm, reps):
            return sum(1 for r in reps if (t, arm, r) in eff and not ok((t, arm, r)))
        e3 = not_success(trt, (1, 2, 3)) - not_success(ctl, (1, 2, 3))
        g = {"e_t_r1_3": e3}
        if e3 == 1:
            if all((t, a, r) in ext for a in (ctl, trt) for r in (4, 5)):
                e5 = not_success(trt, (1, 2, 3, 4, 5)) - not_success(ctl, (1, 2, 3, 4, 5))
                g["e_t_r1_5"] = e5
                g["state"] = "holds" if e5 <= 0 else ("FAIL" if e5 >= 2 else "NULL")
            else:
                extension_required = True
                g["state"] = "extension required"
        else:
            g["state"] = "holds" if e3 <= 0 else "FAIL"
        guarded[t] = g

    reasons: list[str] = []
    if not precondition_met:
        verdict, reasons = "NULL", ["precondition not met (D-024 §2)"]
    elif apparatus:
        verdict, reasons = "NULL (apparatus)", apparatus
    elif extension_required:
        verdict = "PENDING: run the pre-registered extension (repeats 4-5, guarded tasks)"
    else:
        fail = []
        if clause1 is False:
            fail.append("non-inferiority clause 1 violated")
        fail += [f"{t}: e_t >= 2" for t, g in guarded.items() if g["state"] == "FAIL"]
        if fail:
            verdict, reasons = "FAIL", fail
        elif D is not None and D >= threshold and clause1 and \
                all(g["state"] == "holds" for g in guarded.values()):
            verdict, reasons = "PASS", [f"D = {D:,.0f} >= 0.5 x delta = {threshold:,.0f}",
                                        "non-inferiority holds"]
        else:
            verdict = "NULL"
            if D is not None and D < threshold:
                reasons.append(f"D = {D:,.0f} < 0.5 x delta = {threshold:,.0f}")
            reasons += [f"{t}: e_t = 1 after the extension" for t, g in guarded.items()
                        if g["state"] == "NULL"]
            if D is None:
                reasons.append("D undefined (missing medians)")

    card_runs = [main[k] for k in main if k[1] == trt]
    section_calls = [ln.get("gdmd_spec_section_calls") or 0 for ln in card_runs]
    outcomes = {arm: {} for arm in (ctl, trt)}
    for k, ln in main.items():
        outcomes[k[1]][ln["outcome"]] = outcomes[k[1]].get(ln["outcome"], 0) + 1
    usd = {arm: statistics.median([main[k].get("est_cost_usd") or 0 for k in main if k[1] == arm])
           if runs[arm] else None for arm in (ctl, trt)}
    return {
        "verdict": verdict, "reasons": reasons, "D": D, "delta": delta,
        "threshold": threshold, "per_task": per_task,
        "non_inferiority": {"successes": succ, "runs": runs, "rates": rate,
                            "clause1_holds": clause1, "guarded": guarded},
        "secondaries": {"median_usd": usd,
                        "section_calls_total": sum(section_calls),
                        "runs_with_section_calls": sum(1 for n in section_calls if n),
                        "section_calls_per_run": (sum(section_calls) / len(section_calls)
                                                  if section_calls else None)},
        "apparatus": {"errors": [f"{t}/{a}/r{r}" for t, a, r in errors],
                      "contaminated": {f"{t}/{a}/r{r}": v for (t, a, r), v in contam.items()
                                       if v},
                      "missing_primary": missing},
        "outcomes": outcomes, "n_main": n_main, "n_extension": len(ext),
    }


def probe_delta(path: Path) -> float:
    """Rule C's delta: the matrix-world `spec_import_tokens` of the import
    probe run at the Rule C commit (D-025, "Probed delta")."""
    d = json.loads(Path(path).read_text())["worlds"]["matrix"]["spec_import_tokens"]
    if d is None:
        raise SystemExit(f"{path}: no matrix-world spec_import_tokens")
    return float(d)


def study_of(line: dict) -> int:
    """Lines written before study 2 carry no `study` field: they are study 1."""
    return int(line.get("study", 1))


def only_study(lines: list[dict], study: int) -> list[dict]:
    wrong = sorted({ln["task_id"] for ln in lines if study_of(ln) != study})
    if wrong:
        raise SystemExit(f"lines from another study than {study}: {wrong}")
    return lines


def rule_v2(lines: list[dict], metrics_loader=metrics_for) -> dict:
    """D-026 Rule V2: D-025 Rule V on study 2's lines, with its guarded tasks."""
    return rule_v(only_study(lines, 2), metrics_loader, guarded_tasks=GUARDED_S2)


def rule_c2(lines: list[dict], delta: float, metrics_loader=metrics_for) -> dict:
    """D-026 Rule C2: D-025 Rule C on study 2's lines, with its guarded tasks;
    delta is re-probed in the matrix world at the study-2 commit."""
    return rule_c(only_study(lines, 2), delta, metrics_loader, guarded_tasks=GUARDED_S2)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="D-025 / D-026 verdicts")
    ap.add_argument("rule", choices=["rule-v", "rule-c", "rule-v2", "rule-c2"])
    ap.add_argument("results", nargs="+", type=Path)
    ap.add_argument("--probe", type=Path,
                    help="rule-c / rule-c2: the import probe at the rule's commit")
    a = ap.parse_args(argv)
    lines = load(a.results)
    if a.rule in ("rule-v", "rule-v2"):
        res = rule_v(only_study(lines, 1)) if a.rule == "rule-v" else rule_v2(lines)
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0
    if a.probe is None:
        ap.error(f"{a.rule} needs --probe <import-probe json at the rule's commit>")
    delta = probe_delta(a.probe)
    res = rule_c(only_study(lines, 1), delta) if a.rule == "rule-c" else rule_c2(lines, delta)
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
