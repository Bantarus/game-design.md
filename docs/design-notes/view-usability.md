# Design note: `gdmd view` usability candidates (OI-007)

> **Status:** design note only (D-042). Nothing here changes `gdmd view` or `gdmd graph`, and nothing here is a claim that any candidate would lower consultation cost. Any change to view output needs its own pre-registered measurement before a claim is made anywhere (the user's rule at the post-study-2 review, and spec §11.3).

This note collects what the two dogfood studies showed about how subjects used the views, lists the candidate changes queued in OI-007, and says for each one what it would change, what it would risk, and what would have to be measured before it ships.

## Ground rules any candidate must keep

- **The lowering rule (spec §9.9.2).** A view may select, truncate or annotate source lines, never rewrite them. Every elision carries a `<path>:<start>-<end>` pointer. A candidate that shortens output does it by eliding with pointers, not by summarizing.
- **One reference semantics (D-027).** Views use the linter's resolution and backlink definitions. No candidate adds its own.
- **No retrofitting.** Study 1's and study 2's results stand as measured with the views they ran (D-025, D-026). A later change is a v0.4.x change, evaluated in a later study.
- **The views arm is pinned.** The dogfood views arm text is pinned by SHA-256 (D-025 amendment 4). A new flag changes what the arm can document, so a new study needs a new pinned arm.

## What the studies showed (descriptive)

Consultation bytes are the tool-result bytes returned to the model, the primary of Rules V and V2.

| Mode | Study 1, views arm (15 runs) | Study 2, views arm (18 runs) |
| --- | --- | --- |
| overview | 1 call, 7,945 B (5.5%) | 4 calls, 31,972 B (15.2%) |
| `--grep` | 12 calls, 61,921 B (42.6%) | 2 calls, 27,942 B (13.3%) |
| `--ref` | 4 calls, 12,799 B (8.8%) | 5 calls, 16,221 B (7.7%) |
| `graph` | 0 | 14 calls, 46,591 B (22.2%) |
| `--full` | 0 | 0 |

Sources: [`dogfood-01.md`](../case-studies/dogfood-01.md) (view-mode table) and [`dogfood-02.md`](../case-studies/dogfood-02.md) (view-mode table).

- **Broad searches were the largest single cost in study 1.** The `operating_energy_budget` runs searched `energy|\b3\b|three`, which matches every `3` in the tree. Their four `--grep` calls returned 39,255 bytes. Re-run today on the deckbuilder, that regex returns **18,142 bytes in 58 blocks**; `--grep energy` alone returns 4,200 bytes in 13 blocks.
- **In study 2, the two guarded tasks consulted more under views** (−53% and −126%): the arm added one overview call (about 8 KB) or one `--grep` call (about 14 KB) to the workflow the baseline also used.
- **What the overview is made of.** On the study-2 tree, the overview is 8,448 bytes in 134 lines. The file list is 1,932 bytes. The per-token lines for its 94 tokens are about 6,000 bytes. The 320 content entities are already collapsed to four per-kind lines (365 bytes).
- **`--full` was never used.** It is 68,283 bytes on the deckbuilder, against 49,344 bytes for the files themselves (+38%): each one-line `meta` key carries its own header.
- **`--flat` already sizes a search.** `--grep 'energy|\b3\b|three' --flat` lists the same 58 blocks, one line each, in 4,111 bytes (23% of the full output). No subject in either study used `--flat`.

## Candidates

### 1. A `--grep` match cap

- **What:** `--max-blocks N` (name to be settled). The first N selected blocks are lowered as today. The rest are listed as `--flat` lines, each with its pointer, under a line giving the total ("58 blocks; 12 shown in full; rerun with `--max-blocks 0` for all").
- **Why it fits the lowering rule:** the blocks beyond N are elided with pointers, not dropped, so nothing becomes unreachable.
- **Motivation:** the study-1 broad regex above. With N = 12, the output would be the first 12 blocks plus 46 one-line entries. How many bytes that saves depends on which blocks come first, and is not claimed here.
- **Risks:**
  - The answer may sit in block N+1. Canonical order (core, `files:` order, path order) does not rank by relevance, and a cap must not pretend to.
  - A default cap changes the output of every existing `--grep` call. Opt-in avoids that, but then subjects must know to use it.
- **Measurement before any claim:** a pre-registered rule over tasks that need a broad search, with the answer placed both before and after the cap. Primary: consultation bytes. Guard: success, including runs whose answer is in the elided part.

### 2. A count-only mode

- **What:** `--grep <regex> --count`: per file, the number of matching lines and blocks, and nothing else. A search can be sized before its lines are fetched.
- **What exists:** `--flat` already gives the block list at about a quarter of the size. A count mode would be smaller again (one line per file), but it duplicates most of what `--flat` does.
- **The first question is not a build question:** would subjects use a sizing step at all? None used `--flat`. A study arm that documents `--flat` as the way to size a search answers that without new code.
- **Measurement before any claim:** as candidate 1, with and without the sizing step documented.

### 3. A lighter overview

- **What:** an overview that lists, per namespace, the token count and the pointer to the owning file instead of one line per token (for example `gdmd view <path> --summary`, or per-namespace collapsing above a threshold, as content entities are collapsed today). The elided per-token lines are named by the view that lists them (`--flat --role token`).
- **Size, from the measured composition:** on the study-2 tree, dropping the per-token lines leaves the file list, one line per namespace and the content-entity lines: roughly 2.5 KB of the 8.4 KB. This is an estimate from the breakdown above, not a measurement of an implementation.
- **Risks:**
  - The per-token lines are the index a subject uses to choose a `--ref` or `graph` target. Without them, a subject may need a second call, which could cost more than it saves.
  - In study 2, the graph tasks' largest reductions came from one to three `gdmd graph` calls, often with no overview at all. A lighter overview helps only workflows that start with one.
- **Measurement before any claim:** the guarded maintenance and negative-control tasks, where the overview was the added cost, plus a lookup task where the per-token index is what the subject needs.

### 4. `-i` as an alias of `--ignore-case`

- **What was logged:** one subject wrote `--grep -i '<pattern>'`, and `-i` became the pattern.
- **An alias would not have prevented it.** `--grep` takes a value, so click consumes the next token, `-i`, as the regex whether or not `-i` is also an option. Checked with click 8.4: with an alias defined, `--grep -i energy` still fails with "unexpected extra argument (energy)". The alias only helps `-i --grep energy`.
- **What would address the observed slip:** rejecting a `--grep` value that is exactly a known option (`-i`, `--ignore-case`, `--flat`, …) with a message naming the likely intent. Today the call already fails with a usage error, so the cost of the slip was one retried call.
- **Measurement:** none needed for a usage error message, which does not change any view's output. It still needs its own D-entry, since it changes CLI behavior.

### 5. `--full` header compaction

- **What:** fold the headers of consecutive one-line `meta` blocks into one, which is where most of `--full`'s 38% overhead comes from.
- **Evidence of need:** none. No run in either study used `--full`, so by the observed-need discipline this is last.
- **Constraint:** the §9.9.3 guarantee that every non-blank line appears exactly once must hold, and the WS2 goldens (`tests/fixtures/views/golden/`) would be regenerated.

### 6. The usage line under the dogfood shim (harness only)

Under the dogfood shim, click's usage line names `python -m game_design_md` instead of `gdmd`. It is cosmetic and affects only harness copies. Setting click's program name in the shim's invocation would fix it. It is not a view change.

## If any of this is taken up

- **Order by evidence, not by ease:** candidates 1 and 3 have observed cost behind them (study 1's broad search, study 2's guarded tasks). Candidate 2 first needs the question of whether subjects size searches at all. Candidate 5 has no observed need.
- **Each change:** its own D-entry, the spec §9.9.3 text, goldens and tests, and a pre-registered rule run on a new pinned arm, before any statement that it reduces cost.
