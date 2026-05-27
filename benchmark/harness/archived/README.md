# Archived components (v12-D scope reduction)

This directory holds Phase 5 harness components that are **pre-registered as
part of the design-of-record** but **constrained out of the current benchmark
execution**. They remain in the codebase, isolation-and-calibration-verified,
ready for re-activation under their original pre-registered identity.

## Why these files live here

The originally pre-registered Phase 5 design called for a two-subject benchmark:
**Qwen-Coder** (headline subject) and **Opus 4.7 at `--effort xhigh`** (transfer
probe, per pre-reg lines 99 + 133). The transfer probe was meant to answer the
capability-tier hypothesis: how does spec-helpfulness vary with model capability
tier, comparing a mid-tier code specialist against a frontier general model?

At trial-zero kickoff, step 6c's pre-committed FLIP_API_KEY rule fired at 100.4%
of the default $50/wk subscription budget (projected full Claude-arm cost
$50.18, 95% CI [$39.66, $61.85]; the 5h-rate-cap of ~240 Opus messages would
have been the binding constraint at this trial volume even with the weekly
budget set aside). The pre-committed rule's three branches were:

1. Continue on subscription (if user's actual budget covers it)
2. Flip to API-key fallback (requires harness wiring for ANTHROPIC_API_KEY)
3. **Defer the Opus transfer probe entirely**

The user chose branch 3. v12-D supersession (commit at `1bb0803 → …`) locked
the deferral. The Opus transfer-probe identity remains the named
transfer-probe-of-record; this benchmark execution simply doesn't run it.

**Critical distinction:** v12-D is a scope reduction, not a substitution. The
design-of-record stays intact in this directory. Re-activation re-runs the
*original* design unchanged.

## What's archived

| File | Role |
|---|---|
| [`instrument_claude.py`](instrument_claude.py) | `ClaudeInstrument` class + `CLAUDE_TRANSFER_PROBE_BUNDLE` + `CLAUDE_ANTI_FLAILING_SUFFIX`. Wires Claude Code CLI in headless mode (Opus 4.7 / xhigh, canonical-name pin, isolated tempdir cwd, anti-flailing system-prompt steer). |
| [`verify_claude_isolation.py`](verify_claude_isolation.py) | Required isolation smoke test (4 contamination probes). Must report 4/4 PASS before any Claude trial counts. Last run before archival: 4/4 PASS at `03c1c11`. |
| [`run_step6c.py`](run_step6c.py) | Driver for step 6c — the Claude-arm pre-sweep three-read pre-flight gate (sanitizer-generalization + regime-constancy + Opus-usage-rate). Last run at `03c1c11`: sanitizer-generalization PASS (accuracy 0.367, CI [0.219, 0.545] brackets 1/3); regime-constancy 3 advisory flags (all A-vs-C structural); Opus-usage-rate FLIP_API_KEY decision under default budget. |

## What's preserved at audit paths (NOT in this directory)

The following artifacts from prior Claude-arm runs stay in their original audit
locations under `benchmark/harness/audits/` so the chain-of-evidence is
preserved across the archival:

| Audit artifact | What it certifies |
|---|---|
| `instrument_calibration_claude-opus-4-7_*_2026-05-24T185331Z.json` (at commit `e5b3811`) | Step 5 PASS on the Claude arm: structural validity 5/5, seed-sensitivity 1236 vs 282 floor (4.4× margin), rubric reachability median 5 / min 5. |
| Isolation smoke 4/4 PASS captured in `e5b3811` commit message (no separate JSON artifact) | Step "11-precursor" isolation gate cleared under the new Opus 4.7 xhigh bundle. |
| `generalization_check_pre_sweep_*_2026-05-27T154347Z.json` (at commit `03c1c11`) | Step 6c read (a) PASS — sanitizer-generalization on real Claude outputs. |
| `regime_constancy_pre_sweep_2026-05-27T154347Z.json` (at commit `03c1c11`) | Step 6c read (b) 3 advisory flags (all on A-vs-C structural divergence; A-vs-B headline ratio 1.18×, clean). |
| `opus_usage_extrapolation_pre_sweep_2026-05-27T154347Z.json` (at commit `03c1c11`) | Step 6c read (c) FLIP_API_KEY decision. The constraint that triggered v12-D. |
| `benchmark/harness/trials/claude-opus-4-7_*_easy_*.json` (×30, at commit `03c1c11`) | 30 real Claude trial records (5 paired seeds × 3 conditions × 2 games on easy task). Under v12-D provenance rule, these records remain valid trial data **for any future re-activated Opus arm** — fold-in conditions (sanitizer SHA unchanged + sanitizer-generalization PASS at pre-sweep) hold at `03c1c11`'s SHA. |

## Re-activation procedure

To re-activate the Opus transfer probe under its original pre-registered
identity (the design-of-record stays unchanged; the apparatus simply
runs the full two-subject configuration):

### 1. Decide the auth path

The deferred constraint was the FLIP_API_KEY decision at trial-zero kickoff.
Re-activation must resolve it. Two paths:

- **Subscription** — confirm your weekly Claude Code subscription budget is
  ≥ ~$60-80/week (covers projected $50.18 with safety margin) AND the 5h
  rate-cap on your plan allows ~400 Opus-xhigh calls per 5h window OR pace
  the sweep with throttling. Re-run `python -m benchmark.harness.archived.run_step6c
  --skip-trials --subscription-budget-usd <your_actual>` to record the updated
  Opus-usage-rate decision under the new budget assumption.

- **API key** — wire an `ANTHROPIC_API_KEY`-based `ClaudeInstrument` variant.
  This requires either: (a) replacing the Claude Code CLI invocation with a
  direct Anthropic SDK call (preserves all other instrument behavior:
  isolation discipline, anti-flailing steer, audit fields, error_max_turns
  handling); or (b) running Claude Code in bare mode (`--bare`) with
  `ANTHROPIC_API_KEY` set in env. Path (a) is cleaner; path (b) loses the
  subscription-login path documented at `instrument_claude.py:392-396` so
  it's a harder swap. A re-activation that goes this route lands as a
  new pre-reg supersession (v12-D → v13) naming the auth-path change.

### 2. Re-import the archived module from the trial loop

- In `benchmark/harness/sweep_plan.py`, uncomment the `"claude": 2_000_000`
  entry in `INSTANCE_SEED_BASE_BY_SUBJECT` (the seed_base is preserved as
  a comment specifically so re-activation produces bit-identical seeds).
- In `benchmark/harness/instrument.py`, the module docstring already
  documents that re-activation re-imports from `archived/`. No changes
  needed to the active module — re-activation imports `ClaudeInstrument`
  and `CLAUDE_TRANSFER_PROBE_BUNDLE` directly from `archived/instrument_claude.py`
  in any tool that needs them.
- Trial-loop driver wiring: re-add `--subject claude` support to
  `benchmark/harness/run_trial.py`'s CLI (the function `run_trial(...)`
  itself is subject-agnostic; only the CLI's stubbed-pending block needs
  updating).

### 3. Re-run calibration steps for the Claude arm

The Claude arm's prior calibrations are preserved at audit paths but may
need re-running if instrument identity has rotated (Claude Code CLI
version, Anthropic point release behind the canonical name, etc.):

- **Step 11 (instrument calibration smoke):** `python -m benchmark.tools.run_instrument_calibration
  --subject claude` (the script's `gather_claude()` defers its import from
  `archived/instrument_claude.py`).
- **Step 11-precursor (isolation):** `python -m benchmark.harness.archived.verify_claude_isolation`.
  4/4 PASS required.
- **Step 6c (pre-sweep three-read pre-flight on the Claude arm):**
  `python -m benchmark.harness.archived.run_step6c` (the driver does
  isolation + 30 trials + three reads in one invocation).

### 4. Re-plan and re-run the full sweep

With `claude` re-added to `INSTANCE_SEED_BASE_BY_SUBJECT` and calibration
artifacts current, `plan_sweep(subject="claude", shuffle_seed=...)` produces
the 330 Claude cells; combined with the 330 Qwen cells, the full two-subject
sweep is 660 cells.

The seed allocation is bit-identical with the design-of-record because
`seed_base=2_000_000` is preserved.

## Why the design-of-record stays unchanged across deferral

The constraint that triggered v12-D was logistical (subscription rate-cap +
budget), not methodological. The pre-registered apparatus — instrument
isolation, calibration gates, sanitizer-generalization, regime-constancy,
the matched paired-McNemar headline metric — is identical whether the Opus
arm runs now or in a future re-activation. Archive preserves the path to
re-activation under the *original* design intent; that is the whole point
of pre-registration (the design is the design, regardless of which
executions instantiate it).

See:

- [`docs/v0.2-phase5-pre-registration.md`](../../../docs/v0.2-phase5-pre-registration.md)
  v12 → v12-D audit-trail row #22 — the constraint that triggered deferral
  and the constraint-genuine + re-scoping-honest test that licensed it.
- Project memory `constraint-driven-scope-reduction-vs-result-driven-gate-loosening`
  — the test distinction that prevents misclassifying v12-D as gerrymandering.
- Project memory `archive-not-delete-constrained-out-components` — the
  generalized archival discipline.
