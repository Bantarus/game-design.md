# Archived evidence apparatus

This directory holds evidence apparatus that is **retired from routine use but kept as the record**. Nothing here runs in CI, and nothing here should be re-run.

## `phase5_qwen/` — the v0.2 Phase 5 help-benchmark (F-009)

The single-subject Qwen3-Coder benchmark that produced [F-009](../../docs/case-studies/F-009.md) (trial zero, commit `37c004d`, 2026-05-28). It was retired as the routine gate at v0.4 by [`DECISIONS.md`](../../DECISIONS.md) D-023. The routine evidence surface is now the dogfood harness at `benchmark/dogfood/`.

**Status: frozen. Do not re-run.**
- F-009 stays on record as reported, and its numbers are not comparable to dogfood results (different model, harness and tasks; see D-023).
- A "re-run of F-009 under the new protocol" is explicitly not a thing.
- D-022 records that F-009's records cannot answer consultation-cost questions.

### What was moved (byte-preserving `git mv`, v0.4)

| Old path (as cited in the locked pre-registration) | New path |
| --- | --- |
| `benchmark/harness/` (code, `trials/`, `trial_gathers/`, `audits/`, `archived/`) | `benchmark/archived/phase5_qwen/harness/` |
| `benchmark/tools/` (flattener, verifier, prompt templates, drivers) | `benchmark/archived/phase5_qwen/tools/` |
| `benchmark/tasks/` | `benchmark/archived/phase5_qwen/tasks/` |
| `benchmark/c-prompts/` | `benchmark/archived/phase5_qwen/c-prompts/` |
| `benchmark/README.md` | `benchmark/archived/phase5_qwen/README.md` |

Not moved: `benchmark/games/platformer` and `benchmark/games/survival`. They were F-009's fresh games, but they are also live lint trees and `gdmd init` starter sources (spec §9.8), and they have changed since trial zero.

**Pinned SHAs survive the move.** The sanitizer-of-record (`harness/sanitization.py`, `e85c123f227d225a…`) and the flattener (`tools/flattener.py`, `54ef5ba3…`) hash identically at their new paths and at `37c004d`. The prompt templates and audit records are unchanged byte-for-byte.

**Documents that still cite the old paths, on purpose:**
- [`docs/v0.2-phase5-pre-registration.md`](../../docs/v0.2-phase5-pre-registration.md) is **locked** ("no further supersessions permitted" since trial zero). It is left untouched; its links resolve at its own commits. Use the table above to map them.
- Files inside `phase5_qwen/` describe themselves by their original paths. Some are SHA-pinned, so none were edited.
- [`docs/v0.2-findings.md`](../../docs/v0.2-findings.md) received path-only link fixes.

### Why it isn't runnable in place

The harness locates games, `src/` and the repo root through parent-relative paths, and the `tools/` drivers import `benchmark.harness.*`. Both assume the pre-v0.4 layout. After the move, the drivers fail at import and `conditions.build_a` fails with "Game tree not found", so the failure is loud rather than silently wrong. Faithful re-execution needs the original layout **and** the original trees, which only exist at the trial-zero commit:

```bash
git worktree add ../gdmd-trial-zero 37c004d   # original layout + original game trees
```

Re-activating the deferred Opus transfer probe (v12-D) follows `phase5_qwen/harness/archived/README.md` from such a checkout.

**What still runs from here:** three unit-test modules exercise pure harness logic (sweep planning, checklist wiring, instrument/judge wiring with mocks) through `benchmark.archived.phase5_qwen.harness`. They are `tests/test_sweep_plan.py`, `tests/test_checklist_wiring.py` and `tests/test_harness_wiring.py`. They stay in the suite because they guard the archived code against import rot; they make no model calls.
