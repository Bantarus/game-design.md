# Dogfood study 1: projected views (Rule V) and the card ablation (Rule C)

> **Status: Rule V reported (2026-09-30). Rule C pending**, after the WS4 card build.
>
> The locked rules are [`DECISIONS.md`](../../DECISIONS.md) D-025 and its amendments 1–5, all committed before this data existed. Results are reported by the rule, including NULL and FAIL (spec §11.3). The protocol is D-023, and the harness is [`benchmark/dogfood/`](../../benchmark/dogfood/).

## Rule V: views vs baseline

### Verdict: **NULL**

| Condition (D-025) | Result |
| --- | --- |
| Primary: `R` = median over the 5 tasks of the per-task consultation-byte reduction `r_t` | **R = 15.6%**: above 0 and below the PASS threshold X = 30% |
| Non-inferiority clause 1: views' pooled success at most 10 points below baseline's | Holds: 15/15 vs 15/15 |
| Guarded tasks (`maintenance_drift`, `negative_control_no_drift`): `e_t` | 0 and 0: the clause holds, and the extension was not triggered |
| Apparatus: errors > 10%, contamination > 10% in an arm, manipulation check | None fired: 0 errors, 0 contaminated runs; the median view+graph calls per views run is 1, meeting the ≥ 1 floor |

`0 < R < 30%` with no FAIL condition is **NULL** in the verdict table. The verdict was computed by `benchmark/dogfood/analyze.py rule-v`, which was committed and tested before any matrix data (amendment 5).

**What NULL means here: inconclusive, not evidence of no effect.**
- The pre-registered rule does not support the claim that the v0.4 world with the views arm reduces consultation cost by the 30% it required. It does not show an increase either.
- With 3 repeats per cell and per-task `r_t` spanning −63% to +55%, this study cannot distinguish no effect from an effect smaller than 30%, or from one hidden by run-to-run variance. NULL is the absence of a supported claim in either direction.
- Under §11.3, no cost claim for `gdmd view` / `gdmd graph` enters the spec, the README or release notes from this result. The per-task numbers below are descriptive and gate nothing.

**What was tested: availability plus neutral documentation.**
- The views arm had the commands available, described neutrally in the pinned arm text and in AGENTS.md's command list, with no guidance on when to use them.
- Subjects used them sparingly (see Adoption below). So the result is about making views available, not about directing agents to use them.

**A confound Rule V cannot separate.** The v0.4 world's `spec.md` import is 5,837 tokens larger (the import probe). Every turn carries it, so per-turn occupancy and USD differ between the arms for a reason unrelated to consultation. The primary (consultation bytes) excludes it by construction. The occupancy and USD secondaries do not, and this study cannot split the two. Rule C measures the import directly.

### What was compared

- **Matrix:** 5 tasks × {`baseline`, `views`} × 3 repeats = 30 runs, run `rulev-20260930`, all at the matrix commit `e693f2a`.
- **Subject:** `claude-sonnet-5-5`, `--effort high`, via the pinned Claude Code CLI 2.1.285. Every run's assistant records came from that model alone.
- **Arms:**
  - `baseline` is the v0.3 world: the tooling and instruction layer from tag `v0.3.0` (overlay `61c95fe`), with `gdmd` from the v0.3.0 venv. It uses the arm text `arms/baseline.md`.
  - `views` is the v0.4 world at `e693f2a`. It uses the arm text `arms/views.md`, pinned at SHA-256 `f77848a6…d138712` and checked by the harness before any cell.
- **Context check:** all 30 runs passed it. `CLAUDE.md` was injected and auto-memory was off.
- **Time:** runs started between 17:10:48 and 17:19:05 UTC.
- **What Rule V measures** (D-025): the v0.4 world plus the views arm against the v0.3 world plus the baseline arm. It does not measure the view commands in isolation.
- **World size at the matrix commit** (import probe `probe3-20260930`): the `docs/spec.md` import is 51,807 tokens in the v0.4 world and 45,970 in the v0.3 world, and `spec.md` is 137,544 vs 121,539 bytes. This difference is not in the primary.

### Primary: consultation bytes per run

Consultation bytes are the UTF-8 bytes of every tool result returned to the model in a session, summed over all tools. The per-task medians are over repeats 1–3, and `r_t = 1 − median_views / median_baseline`.

| Task | Median baseline | Median views | `r_t` |
| --- | ---: | ---: | ---: |
| `authoring_new_card` | 10,229 | 8,635 | +15.6% |
| `lookup_refs` | 12,672 | 5,716 | +54.9% |
| `maintenance_drift` | 10,708 | 8,524 | +20.4% |
| `negative_control_no_drift` | 1,750 | 2,851 | −62.9% |
| `operating_energy_budget` | 19,446 | 24,472 | −25.8% |
| **R (median of `r_t`)** | | | **+15.6%** |

Three tasks moved one way and two the other; none gates anything individually.
- **`negative_control_no_drift`**: the ratio is taken over small counts (medians of 1.7–2.9 KB), so a single extra `cat` moves it by tens of percent.
- **`operating_energy_budget`**: the views arm consulted more. Its three runs searched with a broad regex (`energy|\b3\b|three`), which matches every `3` in the tree; see the view-mode table below.

### Non-inferiority

| | Success | Fail | Capped | Error |
| --- | ---: | ---: | ---: | ---: |
| `baseline` | 15 | 0 | 0 | 0 |
| `views` | 15 | 0 | 0 | 0 |

- Clause 1 holds.
- Guarded-task `e_t` is 0 for both tasks, so the pre-registered extension (repeats 4–5) did not run.
- Every run succeeded, so success cannot separate the arms on these tasks. This is the ceiling effect the pilot foresaw, and the reason study 2 (D-026) exists.

### Manipulation check and covariate

- **Views arm:** the median of `gdmd_view_calls + gdmd_graph_calls` per run is **1**, so the check passes at exactly its floor.
  - The per-run counts range from 0 to 3.
  - Two runs made no view or graph call, both on `negative_control_no_drift`.
  - No run called `gdmd graph`.
- **Baseline arm:** 0 attempts to call `view` or `graph`. The README's verb list names them in both arms (amendment 4); no baseline subject tried them.

### Adoption (descriptive)

Tool use per arm, summed over the 15 runs. A call is counted under a category when it contains that command, so one Bash call can count under several.

| | `baseline` | `views` |
| --- | ---: | ---: |
| `gdmd view` / `gdmd graph` calls | 0 | 18 |
| Runs with at least one `view` / `graph` call | 0 of 15 | 13 of 15 |
| Bash calls containing `cat` | 12 | 14 |
| Bash calls containing `grep` (the shell's) | 21 | 15 |
| `Read` tool calls | 14 | 2 |
| `Grep` tool calls | 9 | 2 |
| Bash file-read calls (amendment 3 definition) | 30 | 26 |
| Distinct files read, summed over runs | 68 | 41 |
| All tool calls | 98 | 93 |

- Views did not replace plain reads. The views arm still issued 26 Bash file reads and 14 `cat` calls.
- `Read` and `Grep` tool calls fell from 23 to 4, and distinct files read fell from 68 to 41.
- The views arm's 18 view calls averaged 1.2 per run.

### Secondaries (descriptive, not gating)

Medians per run over repeats 1–3:

| Metric | `baseline` | `views` |
| --- | ---: | ---: |
| Median per-turn occupancy (tokens) | 77,031 | 82,512 |
| Cache-read tokens | 309,332 | 332,414 |
| Cache-creation tokens | 72,689 | 77,505 |
| Output tokens | 1,700 | 1,369 |
| Turns | 5 | 5 |
| Tool calls | 6 | 5 |
| Distinct files read (`Read` + Bash) | 5 | 2 |
| Re-reads | 0 | 0 |
| Bash read calls | 2 | 2 |
| Bash read bytes | 3,908 | 2,759 |
| Wall-clock (s) | 17 | 14 |
| Estimated USD | 0.37 | 0.39 |

- Total estimated cost: $5.67 (baseline) and $6.20 (views), $11.87 for the matrix.
- **Occupancy and USD are confounded by the world difference.** The views arm's median per-turn occupancy is about 5.5k tokens higher. That is the size of the difference between the two worlds' spec imports (5,837 tokens, import probe above), which every turn carries. It is not consultation; Rule V's primary excludes it by construction, and this study cannot separate the two. Rule C, the card ablation, is the pre-registered measurement of the spec import's weight.

**Consultation bytes by view mode** (amendment 5), views arm, summed over its 15 runs:

| Mode | Calls | Result bytes | Share of the arm's consultation bytes (145,305) |
| --- | ---: | ---: | ---: |
| `overview` | 1 | 7,945 | 5.5% |
| `--full` | 0 | 0 | 0% |
| `--grep` | 12 | 61,921 | 42.6% |
| `--ref` | 4 | 12,799 | 8.8% |
| `graph` | 0 | 0 | 0% |

- **`--full` did not drive cost:** no run used it.
- **`--grep` carried most of the view bytes.** Of those, 39,255 came from the `operating_energy_budget` runs' four `--grep` calls: three returned the broad regex's output, and one was the usage slip below.
- **`--ref` was used on `lookup_refs`** (`--ref '{resources.energy}' --hops 1`). That is the task with the largest reduction.
- **Two view calls failed on the subject's side:**
  - a `cd examples/deckbuilder` issued when the shell was already there;
  - `--grep -i '<pattern>'`, which passed `-i` as the pattern.

  Their error text is counted in the bytes above, as the primary counts it.
- The baseline arm made no view calls.
- **One call is not attributed to a mode.** In `lookup_refs` views r2, a `for v in …; do gdmd view . --ref "{verbs.$v}"; done` loop was refused by Claude Code before it ran (`Contains simple_expansion`, 25 bytes of error text). The mode parser stops at the shell keyword `do`, so the table leaves it out. The locked substring counter `gdmd_view_calls` does count it. Without it, the manipulation-check median would still be 1. The fix (skip shell keywords before the program) was applied afterwards; see the addendum below.

### Raw results (one row per run)

| Task | Arm | Rep | Outcome | Consultation bytes | Turns | Tool calls | view+graph calls | Median occupancy | Wall (s) | USD |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `authoring_new_card` | baseline | 1 | success | 9,064 | 6 | 7 | 0 | 77,031 | 17 | 0.39 |
| `authoring_new_card` | baseline | 2 | success | 10,609 | 7 | 7 | 0 | 77,775 | 17 | 0.41 |
| `authoring_new_card` | baseline | 3 | success | 10,229 | 6 | 6 | 0 | 77,062 | 20 | 0.39 |
| `authoring_new_card` | views | 1 | success | 7,086 | 7 | 8 | 1 | 82,595 | 17 | 0.44 |
| `authoring_new_card` | views | 2 | success | 8,635 | 7 | 9 | 2 | 83,555 | 24 | 0.44 |
| `authoring_new_card` | views | 3 | success | 11,188 | 7 | 8 | 1 | 84,714 | 18 | 0.44 |
| `lookup_refs` | baseline | 1 | success | 9,235 | 5 | 4 | 0 | 76,963 | 17 | 0.37 |
| `lookup_refs` | baseline | 2 | success | 12,672 | 4 | 5 | 0 | 76,601 | 14 | 0.36 |
| `lookup_refs` | baseline | 3 | success | 18,702 | 4 | 6 | 0 | 78,006 | 14 | 0.37 |
| `lookup_refs` | views | 1 | success | 5,716 | 7 | 7 | 3 | 82,512 | 14 | 0.42 |
| `lookup_refs` | views | 2 | success | 5,698 | 5 | 5 | 2 | 81,842 | 12 | 0.39 |
| `lookup_refs` | views | 3 | success | 5,870 | 5 | 4 | 1 | 82,385 | 12 | 0.39 |
| `maintenance_drift` | baseline | 1 | success | 10,708 | 6 | 6 | 0 | 76,824 | 15 | 0.38 |
| `maintenance_drift` | baseline | 2 | success | 12,379 | 5 | 5 | 0 | 77,285 | 15 | 0.37 |
| `maintenance_drift` | baseline | 3 | success | 6,742 | 5 | 4 | 0 | 74,827 | 18 | 0.36 |
| `maintenance_drift` | views | 1 | success | 7,340 | 4 | 3 | 1 | 81,474 | 12 | 0.37 |
| `maintenance_drift` | views | 2 | success | 8,547 | 5 | 4 | 1 | 83,019 | 18 | 0.39 |
| `maintenance_drift` | views | 3 | success | 8,524 | 5 | 5 | 1 | 82,099 | 13 | 0.39 |
| `negative_control_no_drift` | baseline | 1 | success | 1,750 | 3 | 2 | 0 | 72,776 | 7 | 0.31 |
| `negative_control_no_drift` | baseline | 2 | success | 1,541 | 3 | 2 | 0 | 73,088 | 7 | 0.31 |
| `negative_control_no_drift` | baseline | 3 | success | 3,908 | 4 | 3 | 0 | 74,196 | 8 | 0.33 |
| `negative_control_no_drift` | views | 1 | success | 2,851 | 4 | 3 | 0 | 80,407 | 14 | 0.35 |
| `negative_control_no_drift` | views | 2 | success | 1,541 | 3 | 2 | 0 | 79,794 | 7 | 0.33 |
| `negative_control_no_drift` | views | 3 | success | 3,702 | 4 | 3 | 1 | 80,208 | 12 | 0.36 |
| `operating_energy_budget` | baseline | 1 | success | 15,896 | 9 | 17 | 0 | 81,798 | 29 | 0.48 |
| `operating_energy_budget` | baseline | 2 | success | 20,577 | 6 | 13 | 0 | 81,358 | 22 | 0.43 |
| `operating_energy_budget` | baseline | 3 | success | 19,446 | 6 | 11 | 0 | 81,856 | 25 | 0.42 |
| `operating_energy_budget` | views | 1 | success | 17,359 | 8 | 11 | 1 | 87,454 | 29 | 0.49 |
| `operating_energy_budget` | views | 2 | success | 26,776 | 8 | 11 | 2 | 90,587 | 24 | 0.51 |
| `operating_energy_budget` | views | 3 | success | 24,472 | 7 | 10 | 1 | 90,320 | 31 | 0.49 |

### Apparatus

- **Errors, re-runs, extension:** no `error` outcome, so nothing was re-run. No `capped` run. No guarded extension.
- **Out-of-copy access:** 7 entries, listed and not penalized. None names the harness, so no run is contaminated.
  - 5 are the detector matching `/last_updated:` inside a `sed` expression.
  - 2 are `../..` or `../../src` issued from `examples/deckbuilder`, which resolves to the copy's own root.
- **Files:**
  - Results: `benchmark/dogfood/results/rulev-20260930.jsonl`, with per-cell extraction under `results/rulev-20260930/metrics/`.
  - Import probe: `results/import-probe-probe3-20260930.json`.
  - Session logs: archived outside the repository at `~/.local/share/gdmd-dogfood/archive/rulev-20260930.tar.xz`, SHA-256 `1e57bad1…6bc6bd`. The archive holds 120 members, each with its own SHA-256 in `results/rulev-20260930/archive.json`.

### Limits

- **Small n and one model:** 3 repeats per cell and a single model (`claude-sonnet-5-5`). The results are descriptive, and no significance test is claimed.
- **Who wrote the tasks:** the tasks were written by the format's own author, on the format's own trees. They are easy: every run succeeded.
- **What Rule V compares:** the v0.4 world plus the views arm against the v0.3 world plus the baseline arm.
  - The v0.4 world also carries `db1950e`'s spec and AGENTS.md fixes, AGENTS.md's `view` / `graph` entry, and a spec import 5,837 tokens larger.
  - The occupancy and USD secondaries carry that difference.
- **What both arms could read:** README's verb list names `view | graph`, and `CHANGELOG.md` and `DECISIONS.md` describe the views, in both arms. This is a possible awareness effect.
- **Judge residual:** the judge is the matrix commit's `src/`. No lint rule was added after `v0.3.0` that judges new content differently; the OI-005 / OI-006 rules have not landed.
- **The manipulation check passed at its floor.** Views were used, but sparingly: the median is 1 call per run, and 2 of 15 runs made none.
- **No comparability with F-009** (D-022).

### What this does not say

- **It does not say views reduce session cost.** NULL supports no cost claim, and §11.3 forbids stating one.
- **It says nothing about larger trees.** These trees are small (tens of KB), and study 2 (D-026) tests consultation at scale on a generated ~320-entity tree with rule V2, reusing the same pinned arm text.
- **It says nothing about the card.** Rule C is pending the WS4 build; its precondition was met at the pilot.

### Addendum (2026-09-30): view-mode parser fix and re-extraction

After the review, the view-mode parser was fixed to skip shell keywords (`do`, `then`, `else`, `{`, `(`) before the command word (D-026 amendment 2). Every study-1 session was then re-extracted and compared field by field with the committed metrics (`results/rulev-20260930/reextract-d026a2.json`).

- **Rule V matrix:** one run changes, in the view-mode secondary only. In `lookup_refs` views r2, the refused loop call is now attributed to `--ref`. The views arm's `--ref` row becomes 5 calls and 12,824 bytes (8.8% of the arm's consultation bytes, unchanged to one decimal place). Every other number in this section, including consultation bytes and occupancy, is identical, and so are the manipulation check's inputs.
- **Pilot:** no committed field changes.

The verdict stays as recorded: **NULL**.

## Rule C: card-import ablation

Pending: runs after the WS4 build (D-024, D-025 amendment 2).
