# Dogfood study 2: consultation at scale (Rule V2) and the card re-test (Rule C2)

> **Status: both rules reported (2026-09-30).** Rule V2: **PASS**. Rule C2: **PASS**, so the card stays (D-026's adoption linkage; no commit needed).
>
> The locked design is [`DECISIONS.md`](../../DECISIONS.md) D-026 and its amendments 1–7, all committed before this data existed. The apparatus is D-025's as amended, and the protocol is D-023. Results are reported by the rule, including where they are narrow (spec §11.3). This report names no question token: the questions and their hand traces are in D-026 amendment 5.

## The study

- **Tree:** "Lanternfall", a dungeon-crawler tree generated from seed 20260930 (D-026 §§1–9):
  - 320 content entities (140 items, 90 skills, 60 monsters, 30 encounters), 94 other tokens in 12 namespaces, 15 subfiles;
  - 351 files, 151 KB, frozen by manifest SHA-256 `718e52d2…` (amendment 5);
  - placed in every copy at `examples/lanternfall/`.
- **Tasks:** six.
  - Forward and backward multi-hop lookups, two questions each.
  - Two impact tasks: the tokens in a value-reference closure, and the subfiles holding it.
  - Two guarded tasks: a maintenance refactor under an `implemented_in` path, and a negative control whose change nothing references.
  - Answers come from the generator's planted edge list, cross-checked once against `gdmd` code before the freeze. Success is exact set equality on every question.
- **Commit:** both matrices ran at `68b15eb`.
  - It carries amendments 6–7 and the pilot review's decisions on top of the freeze commit `e429173`.
  - A copy at `68b15eb` differs from one at `e429173` only in `CHANGELOG.md` and the two files amendment 6 removes; it was checked by diffing copies of each cell type.
  - The tree, the tooling layer, the import layer and every task file are byte-identical.
- **Subject:** `claude-sonnet-5-5`, `--effort high`, via the pinned Claude Code CLI 2.1.285. Every assistant record in all 72 runs came from that model.
- **Caps:** 80 turns, 1800 s and $5.00 per run. None bound: the maxima were 14 turns, 69 s and $0.65.
- **Context check:** all 72 runs passed. `CLAUDE.md` was injected and auto-memory was off.

## Rule V2: views vs baseline, on a content-heavy tree

### Verdict: **PASS**

| Condition (D-026 Rule V2 = D-025 Rule V) | Result |
| --- | --- |
| Primary: `R` = median over the 6 tasks of the per-task consultation-byte reduction `r_t` | **R = 33.3%**, against the PASS threshold X = 30% |
| Non-inferiority clause 1: views' pooled success at most 10 points below baseline's | Holds: views 18/18; baseline 17/18 with one run counted contaminated (below) |
| Guarded tasks (`s2_maintenance`, `s2_negative_control`): `e_t` | 0 and 0: the clause holds, and the extension was not triggered |
| Apparatus: errors > 10%, contamination > 10% in an arm, manipulation check | None fired: 0 errors; 1 of 18 baseline runs contaminated (5.6%); median view+graph calls per views run 1, meeting the ≥ 1 floor |

`R ≥ 30%` with both non-inferiority clauses holding is **PASS** in the verdict table. `analyze.py rule-v2` computed the verdict; it was committed and tested before any study-2 data (`048fc32`). Nothing was re-run, added or dropped.

**How narrow this PASS is.**
- With six tasks, the median is the mean of the two middle values. Those are `s2_lookup_forward` at +7.4% and `s2_impact_files` at +59.3%, giving 33.3%. The 30% line falls between them.
- The per-task values split three ways:
  - **Three graph-shaped tasks drop sharply.** The two impact tasks and the backward lookup fall 59–92%: the views arm answered each with one to three `gdmd graph` calls.
  - **The forward lookup barely moves** (+7.4%). The views arm walked it with `view --ref`, and its runs consulted 9.7 to 41.7 KB each.
  - **Both guarded tasks consult more under views** (−53% and −126%). The views arm added one overview call (about 8 KB) or `--grep` call (about 14 KB) to the same workflow the baseline used.
- The rule is a median over tasks, locked before the data, and it is reported as computed. A different task mix could land on either side of 30%.

**What PASS licenses (D-026, §11.3).**
- A views-cost claim scoped to what was measured: on a content-heavy tree, on these six tasks, the v0.4 world with the views arm consumed a median 33% fewer consultation bytes than the v0.3 baseline, with no loss of success.
- It is not a session-cost claim. Occupancy and USD are secondaries, and the world difference moves them (below).
- Rule V2 has no adoption consequence. Whether and where the scoped claim is stated (README, release notes) is for review.

**What was compared.** 6 tasks × {`baseline`, `views`} × 3 repeats = 36 runs, run `rulev2-20260930`, at `68b15eb`, started 19:49–20:04 UTC.
- `baseline` is the v0.3 world: the tooling and instruction layer from tag `v0.3.0` (overlay `61c95fe`) and `gdmd` from the v0.3.0 venv, with `arms/baseline.md`.
- `views` is the v0.4 world with `arms/views.md`, pinned at SHA-256 `f77848a6…`, the same arm text as study 1.
- Both arms import the full `spec.md`: D-026 forces the import in the matrix world.

As in study 1, Rule V2 compares the v0.4 world plus the views arm against the v0.3 world plus the baseline arm, not the view commands in isolation.
- The v0.4 world's `spec.md` import is 6,670 tokens larger: 52,645 vs 45,975 tokens, and 139,852 vs 121,539 bytes (`import-probe-probe5-20260930`).
- That import rides on every turn. It is not in the primary, but it is in the occupancy and USD secondaries.

### Primary: consultation bytes per run

Consultation bytes are the UTF-8 bytes of every tool result returned to the model in a session, summed over all tools. Medians are over repeats 1–3, and `r_t = 1 − median_views / median_baseline`.

| Task | Median baseline | Median views | `r_t` |
| --- | ---: | ---: | ---: |
| `s2_impact_files` | 19,313 | 7,868 | +59.3% |
| `s2_impact_tokens` | 26,224 | 2,122 | +91.9% |
| `s2_lookup_backward` | 16,811 | 4,044 | +75.9% |
| `s2_lookup_forward` | 22,110 | 20,478 | +7.4% |
| `s2_maintenance` | 10,443 | 16,017 | −53.4% |
| `s2_negative_control` | 4,678 | 10,550 | −125.5% |
| **R (median of `r_t`)** | | | **+33.3%** |

### Non-inferiority

| | Success | Fail | Capped | Error | Counted successes |
| --- | ---: | ---: | ---: | ---: | ---: |
| `baseline` | 18 | 0 | 0 | 0 | 17 (1 contaminated) |
| `views` | 18 | 0 | 0 | 0 | 18 |

Every answer in both arms was exact. Every question's Jaccard similarity was 1.00 in all 24 answer-task runs, and both guarded tasks passed every criterion in all 12 runs.

### The contaminated run: a conservative false positive, reported by the rule

- **What happened:** `s2_lookup_backward`, baseline, repeat 3.
  - The subject wrote a helper script to its own scratchpad by full path.
  - It then ran `python3 /tmp/claude-1000/*/2ff46112*/scratchpad/g.py`: a glob in the directory-key position, combined with the first 8 characters of its own session id (`2ff46112-…`).
  - Claude Code refused the command, since it needed approval. The subject then ran the script by its full own path.
- **Why it counts:** amendment 7 counts any path under the scratchpad root whose next component is not the run's own copy key. That includes globs, and a denied attempt counts too. So the rule as committed counts this run as contaminated.
- **What the glob could actually reach:** only session directories starting with the run's own session id, which in practice is its own. So by intent it is own-session use.
- **Effect on the verdict: none.**
  - Contamination does not enter the primary: `R` is 33.3% either way.
  - Non-inferiority holds either way: baseline 17 or 18 of 18, views 18 of 18.
  - One run in 18 (5.6%) is below the 10% apparatus threshold.
- **Proposed for review, not applied:** a slug glob whose session component names the run's own session id counts as own use.

### Manipulation check and adoption (descriptive)

The manipulation check passed at its floor: the median is 1 view/graph call per views run. Every views run made at least one; 26 calls in total across 18 runs.

| Summed over the arm's 18 runs | `baseline` | `views` |
| --- | ---: | ---: |
| `gdmd view` / `gdmd graph` calls | 0 | 26 |
| Runs with at least one `view` / `graph` call | 0 of 18 | 18 of 18 |
| `Read` tool calls | 34 | 1 |
| `Grep` tool calls | 34 | 3 |
| Bash calls | 109 | 73 |
| of which contain `cat` / `grep` / `python` | 50 / 49 / 16 | 25 / 15 / 5 |
| Distinct files read (`Read` + Bash), summed | 139 | 32 |
| All tool calls | 190 | 85 |

Baseline attempts at `view` / `graph` (they don't exist in v0.3): 0.

**Views-arm consultation bytes by view mode** (D-025 amendment 5; the arm's total is 210,280 bytes):

| Mode | Calls | Result bytes | Share |
| --- | ---: | ---: | ---: |
| `graph` | 14 | 46,591 | 22.2% |
| overview | 4 | 31,972 | 15.2% |
| `--grep` | 2 | 27,942 | 13.3% |
| `--ref` | 5 | 16,221 | 7.7% |
| mixed | 1 | 1,725 | 0.8% |
| `--full` | 0 | 0 | 0% |

### Secondaries (descriptive, not gating)

| Median per run | `baseline` | `views` |
| --- | ---: | ---: |
| Per-turn occupancy (tokens) | 80,828 | 84,058 |
| Cache-read tokens | 694,412 | 339,524 |
| Cache-creation tokens | 81,288 | 79,650 |
| Output tokens | 3,757 | 1,590 |
| Turns | 10 | 5 |
| Tool calls | 12 | 4 |
| Distinct files read (`Read` + Bash) | 6 | 1 |
| Consultation bytes | 18,617 | 8,960 |
| Wall-clock (s) | 30 | 14 |
| Estimated USD | 0.52 | 0.40 |

- **Occupancy** is higher in views by about the world difference in spec-import size. Views sessions were shorter (5 vs 10 turns), so their cache-read tokens and cost are lower.
- These are secondaries, and none is a claim.
- **Cost:** $8.70 for the 18 baseline runs, $7.54 for the 18 views runs, and $16.24 for the matrix.

### Raw results (one row per run)

| Task | Arm | Rep | Outcome | Consultation bytes | Turns | Tool calls | view+graph | `--section` | Median occupancy | Wall (s) | USD | Jaccard |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `s2_impact_files` | baseline | 1 | success | 19,313 | 12 | 12 | 0 | 0 | 83,296 | 50 | 0.57 | 1.00 |
| `s2_impact_files` | baseline | 2 | success | 25,663 | 9 | 9 | 0 | 0 | 84,254 | 26 | 0.49 | 1.00 |
| `s2_impact_files` | baseline | 3 | success | 18,398 | 8 | 12 | 0 | 0 | 77,436 | 28 | 0.46 | 1.00 |
| `s2_impact_files` | views | 1 | success | 7,282 | 5 | 4 | 3 | 0 | 83,135 | 12 | 0.40 | 1.00 |
| `s2_impact_files` | views | 2 | success | 8,175 | 3 | 2 | 1 | 0 | 83,936 | 10 | 0.36 | 1.00 |
| `s2_impact_files` | views | 3 | success | 7,868 | 7 | 6 | 3 | 0 | 84,180 | 17 | 0.44 | 1.00 |
| `s2_impact_tokens` | baseline | 1 | success | 26,224 | 13 | 12 | 0 | 0 | 84,817 | 38 | 0.58 | 1.00 |
| `s2_impact_tokens` | baseline | 2 | success | 20,349 | 11 | 15 | 0 | 0 | 80,829 | 45 | 0.56 | 1.00 |
| `s2_impact_tokens` | baseline | 3 | success | 29,505 | 11 | 12 | 0 | 0 | 86,081 | 35 | 0.55 | 1.00 |
| `s2_impact_tokens` | views | 1 | success | 2,122 | 5 | 4 | 1 | 0 | 81,957 | 16 | 0.39 | 1.00 |
| `s2_impact_tokens` | views | 2 | success | 2,122 | 5 | 4 | 1 | 0 | 81,920 | 14 | 0.39 | 1.00 |
| `s2_impact_tokens` | views | 3 | success | 2,122 | 5 | 4 | 1 | 0 | 82,049 | 14 | 0.39 | 1.00 |
| `s2_lookup_backward` | baseline | 1 | success | 16,811 | 12 | 16 | 0 | 0 | 81,545 | 54 | 0.58 | 1.00 / 1.00 |
| `s2_lookup_backward` | baseline | 2 | success | 21,146 | 14 | 18 | 0 | 0 | 83,830 | 69 | 0.65 | 1.00 / 1.00 |
| `s2_lookup_backward` | baseline | 3 | success (contaminated: counted not-success) | 12,313 | 13 | 14 | 0 | 0 | 78,624 | 53 | 0.56 | 1.00 / 1.00 |
| `s2_lookup_backward` | views | 1 | success | 4,044 | 6 | 5 | 1 | 0 | 83,118 | 24 | 0.41 | 1.00 / 1.00 |
| `s2_lookup_backward` | views | 2 | success | 4,030 | 5 | 4 | 1 | 0 | 82,991 | 14 | 0.39 | 1.00 / 1.00 |
| `s2_lookup_backward` | views | 3 | success | 14,056 | 5 | 4 | 3 | 0 | 86,446 | 14 | 0.41 | 1.00 / 1.00 |
| `s2_lookup_forward` | baseline | 1 | success | 18,836 | 10 | 18 | 0 | 0 | 80,828 | 46 | 0.54 | 1.00 / 1.00 |
| `s2_lookup_forward` | baseline | 2 | success | 22,110 | 8 | 15 | 0 | 0 | 81,046 | 25 | 0.47 | 1.00 / 1.00 |
| `s2_lookup_forward` | baseline | 3 | success | 26,658 | 11 | 13 | 0 | 0 | 81,195 | 32 | 0.54 | 1.00 / 1.00 |
| `s2_lookup_forward` | views | 1 | success | 20,478 | 8 | 7 | 3 | 0 | 84,190 | 31 | 0.50 | 1.00 / 1.00 |
| `s2_lookup_forward` | views | 2 | success | 41,726 | 7 | 7 | 1 | 0 | 83,470 | 33 | 0.53 | 1.00 / 1.00 |
| `s2_lookup_forward` | views | 3 | success | 9,745 | 6 | 5 | 1 | 0 | 86,284 | 26 | 0.44 | 1.00 / 1.00 |
| `s2_maintenance` | baseline | 1 | success | 10,443 | 5 | 4 | 0 | 0 | 76,416 | 15 | 0.37 | – |
| `s2_maintenance` | baseline | 2 | success | 11,718 | 7 | 6 | 0 | 0 | 76,477 | 17 | 0.40 | – |
| `s2_maintenance` | baseline | 3 | success | 9,717 | 8 | 7 | 0 | 0 | 76,918 | 22 | 0.42 | – |
| `s2_maintenance` | views | 1 | success | 30,083 | 8 | 7 | 1 | 0 | 94,248 | 22 | 0.50 | – |
| `s2_maintenance` | views | 2 | success | 12,736 | 5 | 5 | 1 | 0 | 86,022 | 14 | 0.41 | – |
| `s2_maintenance` | views | 3 | success | 16,017 | 7 | 6 | 1 | 0 | 87,983 | 24 | 0.45 | – |
| `s2_negative_control` | baseline | 1 | success | 4,707 | 3 | 2 | 0 | 0 | 74,505 | 8 | 0.31 | – |
| `s2_negative_control` | baseline | 2 | success | 4,678 | 3 | 2 | 0 | 0 | 74,338 | 8 | 0.31 | – |
| `s2_negative_control` | baseline | 3 | success | 3,840 | 4 | 3 | 0 | 0 | 73,882 | 11 | 0.33 | – |
| `s2_negative_control` | views | 1 | success | 10,550 | 3 | 3 | 1 | 0 | 85,505 | 9 | 0.36 | – |
| `s2_negative_control` | views | 2 | success | 5,161 | 5 | 4 | 1 | 0 | 82,402 | 12 | 0.39 | – |
| `s2_negative_control` | views | 3 | success | 11,963 | 4 | 4 | 1 | 0 | 85,831 | 10 | 0.38 | – |

## Rule C2: the card re-test

### Verdict: **PASS**

| Condition (D-026 Rule C2 = D-025 Rule C) | Result |
| --- | --- |
| Primary: `D` = median over the 6 tasks of `d_t = M_full,t − M_card,t` (median per-turn occupancy, tokens) | **D = 47,158.5**, against the PASS threshold 0.5 × Δ = 26,322.5 |
| Δ: the matrix-world `spec.md` import, probed at the study-2 commit | 52,645 tokens (`import-probe-probe5-20260930`, at `e429173`; the import layer at `68b15eb` is byte-identical) |
| Non-inferiority clause 1 | Holds: 18/18 vs 18/18 |
| Guarded tasks: `e_t` | 0 and 0: the clause holds, and the extension was not triggered |
| Apparatus: errors, contamination | None: 0 errors, 0 contaminated runs |

`analyze.py rule-c2` computed the verdict; it was committed and tested before any study-2 data (`048fc32`). Nothing was re-run, added or dropped.

**What PASS means here.**
- On the content-heavy tree, importing the generated card instead of the full spec cut median per-turn occupancy by about 47k tokens, with no loss of success.
  - That is 85–93% of the probed import size on every task.
  - It is a relative reduction of 55–59%.
- Study 1's Rule C measured D = 46,769 on its five tasks. The two studies agree to within 400 tokens.
- **Adoption linkage (D-026):** C2 PASS means the card stays. The repository's `CLAUDE.md` has imported `@docs/spec-card.md` since `49b53b4`, so nothing changes and there is no commit.

**How strongly non-inferiority was tested: weakly.** Recorded before any matrix data, at the pilot review.
- Every run in both cells succeeded, as the pilot's baseline had.
- At ceiling success the clause is weak: it allows one fewer success out of 18, and tasks that nobody fails cannot show whether the card loses anything.
- So C2 is a weaker re-test of the card than designed. It confirms the occupancy reduction on a larger tree, but it adds little evidence that the card is safe on tasks that need spec text beyond it.
- Both guarded tasks held in all runs.

### What was compared

- **Matrix:** 6 tasks × {`import-full`, `import-card`} × 3 repeats = 36 runs, run `rulec2-20260930`, at `68b15eb`, started 20:05–20:19 UTC.
- **Both cells:** the v0.4 world with `arms/baseline.md` (D-025 amendment 2). Both copies' `CLAUDE.md` was forced to `@docs/spec.md` first (D-026); `import-card` then swaps in the card.
- **The only difference between the cells:** `CLAUDE.md`'s format-definition import.
  - `import-full` imports `@docs/spec.md` (139,852 bytes) and carries no card file (amendment 4).
  - `import-card` imports `@docs/spec-card.md`, which the copy's own `gdmd spec --card` generated. It is 8,491 bytes, and every `import-card` line carries its SHA-256 `7c280fa1…a99f`, the card Rule C used.

### Primary: median per-turn occupancy

| Task | `M_full` | `M_card` | `d_t` | `d_t` / Δ | Relative reduction |
| --- | ---: | ---: | ---: | ---: | ---: |
| `s2_impact_files` | 82,510 | 37,164 | 45,346 | 86.1% | 55.0% |
| `s2_impact_tokens` | 81,395 | 36,776 | 44,619 | 84.8% | 54.8% |
| `s2_lookup_backward` | 85,029 | 38,618 | 46,411 | 88.2% | 54.6% |
| `s2_lookup_forward` | 85,602 | 37,696 | 47,906 | 91.0% | 56.0% |
| `s2_maintenance` | 84,387 | 35,230 | 49,157 | 93.4% | 58.3% |
| `s2_negative_control` | 81,604 | 33,192.5 | 48,411.5 | 92.0% | 59.3% |
| **D (median of `d_t`)** | | | **47,158.5** | 89.6% | |

### Non-inferiority

| | Success | Fail | Capped | Error |
| --- | ---: | ---: | ---: | ---: |
| `import-full` | 18 | 0 | 0 | 0 |
| `import-card` | 18 | 0 | 0 | 0 |

Every question's Jaccard similarity was 1.00 in all 24 answer-task runs, and both guarded tasks passed every criterion in all 12 runs.

### Secondaries (descriptive, not gating)

| Median per run | `import-full` | `import-card` |
| --- | ---: | ---: |
| Per-turn occupancy (tokens) | 83,234 | 36,874 |
| Cache-read tokens | 420,163 | 197,120 |
| Cache-creation tokens | 79,270 | 32,057 |
| Output tokens | 1,680 | 1,749 |
| Turns | 6 | 6 |
| Tool calls | 5 | 6 |
| Consultation bytes | 8,426 | 11,348 |
| Distinct files read (`Read` + Bash) | 2 | 4 |
| Wall-clock (s) | 17 | 17 |
| Estimated USD | 0.42 | 0.19 |

- **`gdmd spec --section` calls: 0 in all 18 `import-card` runs.** As in study 1, zero cannot distinguish "the card sufficed" from "the subject did not look".
- **No direct reads of `docs/spec.md`**, or of any other file under `docs/`, in either cell.
- **More tree reading in the card cell:** 11.3 KB vs 8.4 KB of consultation per run, and 4 vs 2 distinct files. As in study 1, that reading is already counted inside the occupancy primary.
- **`gdmd view` / `graph` were used in both cells:** 33 calls in 12 of 18 `import-full` runs, and 22 calls in 12 of 18 `import-card` runs.
  - Their arm text is the baseline's, which does not mention views. In the matrix world, though, AGENTS.md lists the commands, and the full spec (§9.9) or the card's §9.9 synopsis describes them.
  - In study 1's Rule C no run called them. On this larger tree they were found without being pointed to.
  - This is descriptive and changes no primary: the use is present in both cells.
- **Cost:** $7.70 for the 18 `import-full` runs, $3.45 for the 18 `import-card` runs, and $11.15 for the matrix.

### Raw results (one row per run)

| Task | Arm | Rep | Outcome | Consultation bytes | Turns | Tool calls | view+graph | `--section` | Median occupancy | Wall (s) | USD | Jaccard |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `s2_impact_files` | import-full | 1 | success | 8,860 | 6 | 6 | 3 | 0 | 83,288 | 22 | 0.42 | 1.00 |
| `s2_impact_files` | import-full | 2 | success | 5,333 | 7 | 7 | 3 | 0 | 82,510 | 16 | 0.43 | 1.00 |
| `s2_impact_files` | import-full | 3 | success | 3,210 | 4 | 4 | 1 | 0 | 81,112 | 16 | 0.37 | 1.00 |
| `s2_impact_files` | import-card | 1 | success | 10,468 | 7 | 6 | 2 | 0 | 35,656 | 16 | 0.19 | 1.00 |
| `s2_impact_files` | import-card | 2 | success | 11,752 | 5 | 4 | 1 | 0 | 37,217 | 21 | 0.18 | 1.00 |
| `s2_impact_files` | import-card | 3 | success | 14,313 | 5 | 5 | 1 | 0 | 37,164 | 14 | 0.18 | 1.00 |
| `s2_impact_tokens` | import-full | 1 | success | 4,730 | 5 | 4 | 3 | 0 | 81,354 | 18 | 0.39 | 1.00 |
| `s2_impact_tokens` | import-full | 2 | success | 4,713 | 5 | 4 | 3 | 0 | 81,395 | 17 | 0.39 | 1.00 |
| `s2_impact_tokens` | import-full | 3 | success | 7,568 | 6 | 5 | 3 | 0 | 83,082 | 17 | 0.42 | 1.00 |
| `s2_impact_tokens` | import-card | 1 | success | 11,362 | 6 | 5 | 1 | 0 | 36,971 | 24 | 0.19 | 1.00 |
| `s2_impact_tokens` | import-card | 2 | success | 11,020 | 5 | 4 | 1 | 0 | 36,560 | 14 | 0.17 | 1.00 |
| `s2_impact_tokens` | import-card | 3 | success | 10,986 | 6 | 5 | 1 | 0 | 36,776 | 16 | 0.18 | 1.00 |
| `s2_lookup_backward` | import-full | 1 | success | 9,437 | 6 | 5 | 2 | 0 | 85,029 | 24 | 0.43 | 1.00 / 1.00 |
| `s2_lookup_backward` | import-full | 2 | success | 7,040 | 6 | 5 | 2 | 0 | 83,860 | 15 | 0.42 | 1.00 / 1.00 |
| `s2_lookup_backward` | import-full | 3 | success | 22,421 | 7 | 8 | 3 | 0 | 90,229 | 36 | 0.49 | 1.00 / 1.00 |
| `s2_lookup_backward` | import-card | 1 | success | 18,855 | 8 | 8 | 3 | 0 | 38,618 | 23 | 0.23 | 1.00 / 1.00 |
| `s2_lookup_backward` | import-card | 2 | success | 12,669 | 8 | 8 | 4 | 0 | 37,826 | 20 | 0.21 | 1.00 / 1.00 |
| `s2_lookup_backward` | import-card | 3 | success | 14,231 | 8 | 7 | 2 | 0 | 39,045 | 32 | 0.22 | 1.00 / 1.00 |
| `s2_lookup_forward` | import-full | 1 | success | 18,635 | 9 | 9 | 5 | 0 | 89,438 | 44 | 0.51 | 1.00 / 1.00 |
| `s2_lookup_forward` | import-full | 2 | success | 12,226 | 12 | 15 | 4 | 0 | 85,602 | 47 | 0.58 | 1.00 / 1.00 |
| `s2_lookup_forward` | import-full | 3 | success | 10,570 | 9 | 10 | 1 | 0 | 83,053 | 36 | 0.50 | 1.00 / 1.00 |
| `s2_lookup_forward` | import-card | 1 | success | 12,209 | 7 | 8 | 3 | 0 | 37,357 | 21 | 0.21 | 1.00 / 1.00 |
| `s2_lookup_forward` | import-card | 2 | success | 15,514 | 8 | 8 | 1 | 0 | 40,048 | 32 | 0.23 | 1.00 / 1.00 |
| `s2_lookup_forward` | import-card | 3 | success | 11,158 | 13 | 13 | 2 | 0 | 37,696 | 41 | 0.28 | 1.00 / 1.00 |
| `s2_maintenance` | import-full | 1 | success | 10,941 | 7 | 6 | 0 | 0 | 84,393 | 31 | 0.44 | – |
| `s2_maintenance` | import-full | 2 | success | 10,397 | 7 | 6 | 0 | 0 | 84,387 | 16 | 0.44 | – |
| `s2_maintenance` | import-full | 3 | success | 9,734 | 5 | 4 | 0 | 0 | 83,808 | 22 | 0.40 | – |
| `s2_maintenance` | import-card | 1 | success | 11,334 | 7 | 6 | 0 | 0 | 34,845 | 17 | 0.18 | – |
| `s2_maintenance` | import-card | 2 | success | 11,456 | 9 | 9 | 0 | 0 | 35,402 | 17 | 0.20 | – |
| `s2_maintenance` | import-card | 3 | success | 10,832 | 6 | 6 | 0 | 0 | 35,230 | 18 | 0.18 | – |
| `s2_negative_control` | import-full | 1 | success | 1,861 | 4 | 3 | 0 | 0 | 79,938 | 15 | 0.36 | – |
| `s2_negative_control` | import-full | 2 | success | 5,283 | 3 | 2 | 0 | 0 | 81,604 | 10 | 0.35 | – |
| `s2_negative_control` | import-full | 3 | success | 7,991 | 4 | 4 | 0 | 0 | 83,180 | 11 | 0.37 | – |
| `s2_negative_control` | import-card | 1 | success | 5,877 | 4 | 3 | 0 | 0 | 33,380 | 9 | 0.14 | – |
| `s2_negative_control` | import-card | 2 | success | 3,994 | 4 | 3 | 0 | 0 | 32,470 | 11 | 0.14 | – |
| `s2_negative_control` | import-card | 3 | success | 6,123 | 4 | 3 | 0 | 0 | 33,192 | 10 | 0.14 | – |

## Apparatus (both matrices)

- **Errors, re-runs, extension:** no `error` and no `capped` outcome in 72 runs. Nothing was re-run, and neither rule triggered the guarded extension.
- **Contamination:** one run, V2 `s2_lookup_backward` baseline repeat 3, the scratchpad glob discussed above. No run accessed the harness, `DECISIONS.md` or the study-2 test.
- **Scratchpads (the pilot review's item 3; amendment 7):**
  - V2: 24 own-scratchpad accesses in 6 runs. C2: 11 in 3 runs.
  - Every one was inside the run's own session-id directory.
  - The only path that did not name the run's own copy key is the glob above.
- **Other out-of-copy entries, listed and not penalized:**
  - V2 has 28 entries:
    - 17 relative paths issued from inside the tree (`../..`, `../gdd`, `../../answers`, `../items`), which resolve within the copy;
    - 9 `sed` address patterns the detector reads as paths (`/^forward/,/^backlinks/p`, `/impl/`);
    - 2 references to `/tmp/g.py`. That write was refused (the Bash allowlist is read-only), and the file does not exist.
  - C2 has 14 entries:
    - 3 relative paths;
    - 10 `sed` or `grep` patterns;
    - 1 mistyped copy path (`/tmp/gdmd-dogfood-rulec2-…` for `/tmp/gdmd-dogfood/rulec2-…`).
- **Files:**
  - **Results:** `benchmark/dogfood/results/rulev2-20260930.jsonl` and `rulec2-20260930.jsonl`, with per-cell metrics under `results/<run>/metrics/`.
  - **Import probe:** `results/import-probe-probe5-20260930.json`.
  - **Session logs,** archived outside the repository, each with a SHA-256 per member in `results/<run>/archive.json`:
    - `rulev2-20260930.tar.xz`: SHA-256 `4bc5c6a1…fffffd`, 144 members;
    - `rulec2-20260930.tar.xz`: SHA-256 `32199605…ebc92018`, 144 members.
- **Total cost:** $27.39 for 72 runs, against the ≈ $34 estimate.

## Limits

- **A generated, synthetic tree.** It is content-heavy by construction, with a planted reference graph. Real trees may be shaped differently.
- **Small n and one model:** 3 repeats per cell and `claude-sonnet-5-5` alone. The results are descriptive, and no significance test is claimed.
- **Tasks and generator by the format's own author.** Oracle independence is at the code-path level only: the answers come from the planted edge list, not from `gdmd` code, but one author designed both.
- **Ceiling success weakens non-inferiority** (recorded at the pilot review, before the data). Every run in both matrices succeeded except the one counted contaminated. The clause allows one fewer success out of 18 and is barely tested at the ceiling, so C2 is a weaker re-test of the card than designed.
- **The same world difference as study 1** (Rule V2): the v0.4 world also carries a spec import 6,670 tokens larger, and AGENTS.md's `view` / `graph` entry.
- **What subjects could read.** Copies carried no `DECISIONS.md` (amendment 6). `CHANGELOG.md` and the case studies describe study 2 but name no question token, so the subject could tell it was being benchmarked, in both arms equally.
- **Judge residual:** the judge is the matrix commit's `src/`. No lint rule has been added since `v0.3.0` (the lint hold, D-026 amendment 3).
- **The manipulation check passed at its floor** (median 1 call per views run), as in study 1.
- **No comparability with F-009** (D-022).

## What this does not say

- **It does not say views reduce session cost.** V2's primary is consultation bytes. The USD and turn medians favour views here, but they are secondaries and carry the world difference.
- **It does not say views help on small trees.** Study 1's Rule V was NULL on the repo's own trees, and study 2 does not overturn it.
- **It does not say views help on every task shape.** The reduction came from the three graph-shaped tasks. The forward lookup was flat, and the two guarded tasks consulted more.
- **It says nothing about tasks that need spec text beyond the card.** No `import-card` run reached for `--section` on these tasks, and nobody failed any of them.
