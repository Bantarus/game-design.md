# Changelog

All notable changes to `game-design.md` are recorded here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Pre-1.0.** Every `v0.x` release is pre-stable — substantial vocabulary changes are still in scope across minor versions. `v1.0` is the planned stable lock. Tree authors should expect to ratchet `spec_version:` declarations as vocabulary grows; the linter and the schema track the current minor.

## [Unreleased]

v0.4 vocabulary growth is gated on observed need from live adoption (see [docs/release-notes/v0.3.md](docs/release-notes/v0.3.md) "Queued for v0.4+"). v0.4 work in progress is tooling and evidence, not format. This section also carries the post-v0.3 documentation-drift sweep (external review findings, merged to `main` as #1).

### Added

- **`scripts/docs_lint.py`** — docs-consistency lint that drift-lints the project's own documentation: pyproject/README/spec version agreement, spec §9 + README CLI verb lists vs the registered click commands, the four-field stability guarantee in both AGENTS.md and the spec, and namespace validity of every `{ns.…}` reference AGENTS.md teaches. Each check exists because the corresponding drift actually happened once.
- **GitHub Actions CI** (`.github/workflows/ci.yml`) — pytest + `gdmd lint` over all six in-repo trees + `scripts/docs_lint.py` on push/PR, Python 3.10 and 3.12. CI badge added to the README.

- **D-022 + [`docs/case-studies/F-009-trace-analysis.md`](docs/case-studies/F-009-trace-analysis.md):** F-009 is recorded as not analyzable for consultation cost. It was single-turn and tool-less, stored no prompt text, and never had the spec in its payload. The v0.4 kickoff's reading of the 37.1% cost-lift as "agents opening whole files" is corrected; F-009 itself is unchanged.
- **D-023 + spec §11.3:** the dogfood harness (`benchmark/dogfood/`: headless coding-agent sessions on in-repo trees, deterministic checkers, a pre-registered locked rule) becomes the routine evidence surface. §11.3 forbids unmeasured cost or success claims, and states that dogfood results are not comparable to F-009.
- **D-024:** the WS4 compact-agent-card gate is corrected. Its original trigger (F-009 spec injection) was unsatisfiable; the gate now separates an ungated build (`gdmd spec --card` / `--section`, generated from the spec's structure) from an evidence-gated adoption (a dogfood ablation swapping only the `spec.md` import; primary = per-turn context occupancy). The precondition threshold (≥ 20% of median per-turn occupancy) is locked before any pilot.
- **Dogfood harness drafts** (`benchmark/dogfood/`, D-023). Contents:
  - Five tasks covering authoring, lookup, operating, maintenance and a negative control, each with a deterministic checker.
  - Isolated per-run repository copies: `git archive` export outside the repo, normalized mtimes, fresh `.git`, and a `gdmd` shim onto the copy's own `src/`.
  - VCC-based metric extraction, with per-turn occupancy and consultation bytes as the two pre-registered primaries, plus out-of-copy access detection.
  - An orchestrator whose `--dry-run` validates every CLI flag against `claude --help`, plus a model-id probe and the D-024 import-size probe.

  `tests/test_dogfood.py` shows that every checker passes known-good and fails known-bad solutions on the targeted criterion, and cross-checks the frozen lookup answers once against code. No model has been invoked; the locked rule (D-025) is committed before the pilot.
- **Dogfood views arm (`arms/views.md`):** a neutral command reference derived from spec §9.9, with no task-tuned advice. A test pins its flags to §9.9's synopsis. Its SHA-256 is recorded in a D-025 amendment before the Rule V matrix and reused unchanged for D-026's Rule V2.
- **`benchmark/dogfood/analyze.py`: the Rule V verdict, as code, before any data** (D-025 amendment 5). It computes the locked primary (median of per-task ratios), non-inferiority with the guarded-task extension trigger, the apparatus NULLs (errors, contamination, manipulation check) and `supersedes` re-runs. It resolves four points the locked text leaves open, recorded in the amendment. Tests cover every branch of the verdict table on synthetic results.
- **Dogfood secondary: consultation bytes by view mode** (D-025 amendment 5, non-gating). `extract.view_mode` classifies each Bash call's `gdmd view` / `gdmd graph` mode (overview, `--full`, `--grep`, `--ref`, graph, `--help`, mixed) and attributes the call's result bytes to it (`view_mode_bytes`, `view_mode_calls` on every result line). It lets the Rule V report show whether `--full` drove the views arm's cost.
- **`gdmd view --grep` shows matches outside blocks** (D-025 amendment 5; spec §9.9.3). A match on a gap line (a namespace key, a comment between tokens, a title or introduction) is a `gap` selection with its pointer, under its file, with its ancestor key lines; `--role` excludes them. Before this, `--grep` silently missed text that plain `grep` finds. A property test on all 12 trees checks that every match is shown exactly once.
- **WS2 goldens and budget (D-027 Tests).** Golden outputs for every `view` and `graph` mode, text and JSON (and DOT), on a hand-written fixture tree (`tests/fixtures/views/`), regenerated only with `GDMD_UPDATE_GOLDENS=1`. The in-process budget test holds compile + emit to ≤ 150 ms per in-repo tree (measured 12–42 ms). Graph determinism and no-writes tests.
- **`gdmd graph` (spec §9.9.4, D-027).** The reference graph `gdmd view` uses, as structure: `--impact` (transitive reverse closure, with prose sections as leaves), `--from/--to` (shortest paths, `--max-paths`, exact total in the elision), `--cycles` (value-edge SCCs and self-references), or the whole graph; `--format text|json|dot`. Exit 2 for an argument that does not resolve. Tests: on all 12 trees every targeted reference is on exactly one edge, and `--impact` contains `view --ref`'s backlinks for every token at 1–3 hops (`tests/test_graph.py`). `graph` joins the §9 and README verb lists.
- **`gdmd view` (spec §9.9.3, D-027).** Projected views over a tree: overview, `--full`, `--grep [--ignore-case]`, `--ref [--hops N]`, `--flat`, `--role`, `--json`. Every source line is verbatim with a derivable line number, every omission is a pointer-carrying elision, and nothing is stored. Exit 2 for a `--ref` that does not resolve. Property tests on all 12 trees: `--full` covers every non-blank line exactly once; every emitted line equals the file's line at its number; `--ref`'s backlinks are exactly the `orphaned-entity` predicate (`tests/test_view.py`). `view` joins the §9 and README verb lists.
- **WS2 block model (`src/game_design_md/ir.py`, D-027).** The compiled model behind `gdmd view` / `gdmd graph`: nested blocks with six roles, `<path>:<start>-<end>` pointers, every reference occurrence located to its line, and `tree_sha`. Each file is parsed once: `Tree.load` gains an optional `reader`, and `loader.read_positioned` returns `read`'s values plus the composed YAML node. Property tests on all 12 trees check the model against the loader and the linter's own data (`tests/test_ir.py`). No CLI change yet.
- **Spec §9.9 + D-027: `gdmd view` and `gdmd graph` specified** (v0.4 Checkpoint 3; not yet implemented).
  - Projected views over a tree: overview, `--full`, `--grep`, `--ref --hops`, `--flat`, `--role`, `--json`; graph `--impact`, `--from/--to` (shortest paths, `--max-paths`), `--cycles`.
  - The views use the linter's reference and backlink semantics exactly.
  - Normative lowering rule: select, truncate or annotate; token values verbatim; every elision carries a pointer.
  - Nested blocks with six roles. `--full` covers every non-blank line once. A `tree_sha` identifies the tree state behind each pointer.
  - Nothing is stored, and no cost claim is made (§11.3).
- **D-026: dogfood study 2 (consultation at scale), locked before any study-1 matrix data.**
  - **The tree:** a generated content-heavy dungeon-crawler tree (~320 entities, seed 20260930). Answers come from the generator's planted graph, independent of `gdmd` code.
  - **Tasks:** six, covering multi-hop lookup (forward and backward), impact (tokens and files), maintenance and a negative control.
  - **Rules:** V2 (views vs v0.3 baseline, consultation bytes, ≥ 30%) and C2 (card re-test, occupancy ≥ 0.5Δ), with study 1's non-inferiority.
  - **Card adoption:** a study-1 card PASS is re-tested; a C2 FAIL reverts it.
  - **Freeze:** fixtures are built and frozen before study 2's own pilot.
- **Dogfood copies in the matrix world force `CLAUDE.md`'s `@docs/spec.md` import** (`fixture.force_spec_import`), as D-026 requires for V2 and D-024 §4 for the views comparison. This keeps every locked cell's import intact after the repo adopts the card. `import-card` swaps to the card as before.
- **Dogfood study 2 fixture: the generated "Lanternfall" tree** (D-026 §§1–9; `benchmark/dogfood/fixtures/study2/`). `generate.py` (seed 20260930, fixed word lists, no wall-clock input) writes:
  - a dungeon-crawler tree with 320 content entities (140 items, 90 skills, 60 monsters, 30 encounters), 94 non-content tokens in 12 namespaces and 15 subfiles, a prototyped subset over a stub `impl/`;
  - the planted reference graph (`edges.json`), six task prompts, the two guarded tasks' teammate patches, and frozen answers computed from the planted edges only.

  `tests/test_dogfood_study2.py`:
  - the generator reproduces its output byte for byte;
  - the tree lints 0/0, identically, under the matrix and v0.3 `gdmd`; all 340 frontmatter blocks are schema-valid, and all 320 entities validate;
  - no tree token id occurs in what `CLAUDE.md` imports, except the exempt collection token `{entities.items}`;
  - the one-time oracle cross-check: planted edges equal the linter's value edges, and every answer matches `gdmd view` / `gdmd graph --impact`.
- **D-026 amendment 4: dogfood copies carry the card file only where their cell imports it** (`fixture.remove_unimported_card`). Since the card adoption the repo commits `docs/spec-card.md`, so every copy carried it, unimported, including the v0.3-world baseline. Study 2's `baseline`, `views` and `import-full` copies now drop it, as study 1's copies never had it. `import-card` copies still generate it in-copy.
- **Rule C addendum: the card import's own size** (descriptive, non-gating). A new two-call `run.py --card-probe` (with a probe-only `--ref`) measured the card's `@`-import at the adoption commit: 3,978 tokens, 68% of the 5,882-token gap between the full import (Δ) and the realized reduction (D). The rest follows the card cell's extra reading. The verdict is unchanged.
- **Dogfood study 1, Rule C result: PASS** ([`docs/case-studies/dogfood-01.md`](docs/case-studies/dogfood-01.md)). 30 runs at `b4b1596`: importing the generated agent card instead of the full spec cut median per-turn context occupancy by D = 46,769 tokens, against a pass threshold of 26,326 (half the 52,651-token spec import). Non-inferiority holds (15/15 successes in both cells), and no `--section` call was needed. Under D-024 the repository's `CLAUDE.md` switches to the card; study 2 re-tests it (C2).
- **D-025 amendment 6** (before any Rule C data) records the Rule C apparatus: the WS4 build, the cell construction, the card at the Rule C commit (8,491 bytes, SHA-256 `7c280fa1…`), `analyze.py rule-c` as the pre-registered computation, and the Rule C limits.
- **Rule C cell construction** (D-025, D-024 §3). Two new dogfood arms, `import-full` and `import-card`, both in the matrix world with the baseline arm text. `fixture.swap_in_card` generates each `import-card` copy's card with the copy's own `gdmd spec --card` and swaps only `CLAUDE.md`'s `@docs/spec.md` line, inside the fixture's baseline commit. A new secondary counts `gdmd spec --section` calls. `analyze.py rule-c` computes the locked verdict (Δ is read from the import probe), with every branch tested before any data.
- **`gdmd spec --card` / `--section <id>` (WS4 build, D-024 §1, D-029, spec §9.4).** `--section` prints one numbered section or appendix verbatim (fence-aware; exit 2 for an unknown id). `--card` prints an agent card generated from the spec's structure: verbatim §3 / §8.1 / §8.2 / §9.9 excerpts plus an index of every section with its RFC-2119 keyword count and `--section` pointer. It is about 6% of the spec's size. A test proves every uppercase RFC-2119 requirement is in the card or behind a pointer it lists. Nothing imports the card yet; adoption is gated by Rule C.
- **`gdmd hook check --show-tokens` (WS3, D-028, spec §9.7).** The pre-commit report can print the YAML a staged change may have made stale: token blocks, file-level `implemented_in:` declarations, content entities and `implementation_pointers`, verbatim from the view engine with pointers. It stays informational (exit 0, under 1 s, off by default), and without the flag the output is unchanged. Proof of fire on tick-combat's real engine paths.
- **D-026 amendment 3 + OI-007:** `gdmd view` / `gdmd graph` take bug fixes only until study 2's matrices complete, and lint-behavior changes (OI-003, OI-005, OI-006 class A) wait until then too. Tree-only fixes (OI-006 classes B and C) may land now. Usability ideas from study 1 (a `--grep` match cap, a count-only mode, `--full` header compaction, `-i` for `--ignore-case`) are queued in OI-007, not coded.
- **D-026 amendment 2: the view-mode parser skips shell keywords** (`do`, `then`, `else`, `{`, `(`) before the command word, so a `for …; do gdmd view …; done` call is attributed to its mode. Every study-1 session was re-extracted: only one run's view-mode secondary changes (a refused loop call now counts as `--ref`); the primary, the other secondaries and the manipulation check are identical, and the Rule V verdict stands.
- **Dogfood study 1, Rule V result: NULL** ([`docs/case-studies/dogfood-01.md`](docs/case-studies/dogfood-01.md)). 30 runs at `e693f2a`: R = 15.6% consultation-byte reduction (the median of per-task reductions), below the pre-registered 30% PASS threshold and above 0. Non-inferiority holds (15/15 successes in both arms; no guarded-task extension), and no apparatus NULL fired. Per §11.3, no cost claim for `gdmd view` / `gdmd graph` is made. Rule C is pending the WS4 build.
- **D-025 amendment 5** (before any matrix data), the WS2 review decisions: `--grep` shows matches outside blocks (a correctness fix); AGENTS.md lists `view` / `graph` (part of the v0.4 world; in the Rule V limits); `--full` stays unchanged, with a non-gating bytes-by-view-mode secondary; and `analyze.py` computes the verdict as locked. The views arm's `--grep` line changed, so its SHA-256 is re-pinned (`f77848a6…`).
- **D-025 amendment 4:** the views arm text (`arms/views.md`) is pinned by SHA-256 before any Rule V cell, as D-027 requires, and is reused unchanged for D-026's Rule V2. The harness refuses a pinned arm whose bytes changed (`run.load_arm`). The amendment also records two cross-arm facts for the Rule V limits: the README verb list names `view | graph` in both arms, and `CHANGELOG.md` / `DECISIONS.md` describe the views in both arms.
- **D-025 amendments 2 and 3.** Amendment 2 records explicitly that the card ablation runs on v0.4 tooling with the baseline arm text. Amendment 3 adds non-gating Bash-read secondaries (`bash_read_*`, `all_files_read`, `all_re_reads`), because pilot subjects read through `cat`/`head`/`sed`, not `Read`. The primaries are unchanged; re-extracting the pilot sessions leaves them byte-identical.
- **D-025 amendment 1 (before the pilot):** the locked session flags never loaded `CLAUDE.md`. `--restricted` drops project memory too, so the `spec.md` import that D-025 and D-024 assume was absent in every arm.
  - The import probe caught it: turn-1 occupancy was about 6.9k tokens with or without the ~30k-token spec import.
  - Sessions now use `--setting-sources project,local` (no user settings), with auto-memory off.
  - A per-run transcript check turns any run without an injected `CLAUDE.md`, or with auto-memory on, into an apparatus error.
  - No threshold, metric or verdict mapping changed.
- **D-025: the dogfood locked rules**, committed before the pilot.
  - **Rule V** (views vs baseline): consultation bytes; the median of per-task ratios; PASS at ≥ 30% reduction.
  - **Rule C** (the card ablation): realized per-turn occupancy reduction ≥ 50% of the probed spec-import delta.
  - **Shared non-inferiority:** at most a 10-point overall success drop. On the maintenance and negative-control tasks, one extra failure gives NULL plus one pre-registered extension to 5 repeats; two or more give FAIL.
  - **Outcomes:** success, fail, capped (not-success) or error; caps are identical across arms.
- **Dogfood harness, the apparatus D-025 locks:**
  - The baseline arm runs the **v0.3 world**: its tooling-and-instructions layer comes from `v0.3.0`, and its `gdmd` is a venv installed from the tag and hash-checked against it. The views arm runs the matrix commit.
  - Checkers use one fixed judge, the matrix commit's `src/`, and a preflight asserts judge/arm lint equivalence.
  - Every copy of a run is pinned to one commit, and real runs refuse a dirty harness.
  - The Claude Code CLI is a pinned 2.1.285 binary (SHA-256 checked), run with `DISABLE_AUTOUPDATER=1` and a per-cell version check.
  - Session logs are archived compressed outside the repo; results, extraction output and archive manifests are committed.
  - The import probe covers both worlds (4 calls).
- **`DECISIONS.md` Open items** (OI-001…OI-005): logged spec↔code drifts and a lint-rule vs schema mismatch, each to be resolved in its own D-entry.
- **[v0.3 conformance correction](docs/release-notes/v0.3-conformance-correction.md) + OI-006.** A read-only jsonschema pass (OI-005) finds lint-clean weaker than §11 conformance.
  - All 29 linked content entities validate. The party-rpg starter's `heroes` content-schema lacks `data_dir`, leaving its entity unlinked.
  - 10 of 158 frontmatter blocks, in 8 trees (both benchmark games and all six starters), fail the normative JSON Schema. One class, whole-namespace `applies_to` refs, is used by spec §4.11's own example.
  - Nothing is fixed yet; each class gets its own D-entry.

### Changed

- **AGENTS.md: spec edits start from the full sections.** A new Authoring-mode prohibition: never edit `docs/spec.md` or format semantics (the schema, what a namespace, enum value or lint rule means) from the card alone. Read every affected section with `gdmd spec --section <id>` first, and regenerate the card after a spec edit. It follows the card adoption: `CLAUDE.md` now imports only the card.
- **`CLAUDE.md` imports the generated agent card** (`@docs/spec-card.md`, 8.5 KB) instead of the full spec (`@docs/spec.md`, 140 KB). This is D-024's adoption consequence of the Rule C PASS: the same one-line swap the ablation tested, with the card committed byte-identical to the tested one. A test keeps `docs/spec-card.md` equal to `gdmd spec --card`, and AGENTS.md says to regenerate it after spec edits. The full spec stays authoritative (`gdmd spec --section <id>`). Study 2 re-tests it (C2), and a C2 FAIL reverts it.
- **AGENTS.md** lists `gdmd view` and `gdmd graph` in the Operating mode's CLI line, as a command-list entry like the others (what each returns, no guidance on when to use it). AGENTS.md's own rule requires every new CLI command to land there. It is part of the v0.4 world that Rule V measures, and is recorded in its limits (D-025 amendment 5).
- **Dogfood views arm:** now states that a pointer's path is relative to the tree root, as spec §9.9.1 defines it. Found when checking the arm text against the implementation before its SHA-256 is recorded; the text was ambiguous about which directory `gdd/mechanics.md:89-96` is in.
- **Dogfood operating task:** the task text now states the intended end state. The budget stays a fixed, exact 4 as a hard target, and only tokens that restate it change. "Propagate to every token whose value must change" admitted defensible alternatives, such as a `[3, 4]` band or a retuned `average_card_cost`, that the frozen oracle rejected. Two known-bad tests pin those alternatives as failures.
- **Qwen help-benchmark archived** to `benchmark/archived/phase5_qwen/` (byte-preserving move; pinned sanitizer and flattener SHAs verified unchanged). It is frozen and not runnable in place; faithful re-execution requires a checkout of trial-zero commit `37c004d`. Its three pure-logic test modules still run from the new import path. The locked pre-registration is left unedited, with the path mapping in `benchmark/archived/README.md`. `benchmark/games/` stays in place.

### Fixed

- **Starter schema guard (OI-006).** `tests/test_starter_schema.py` asserts that every starter's frontmatter validates against the JSON Schema. `gdmd init` copies starters into new trees, so their defects spread. The six class-A files (whole-namespace `applies_to`, held until after study 2) are strict expected failures, and a second test pins that this is their only error. A re-run of the one-off pass over the 12 trees finds only class A left: 8 of 158 blocks. All 30 linked content entities validate, and none is unlinked.
- **OI-006 class C (D-031): the party-rpg starter's heroes content-schema is complete.** `templates/starters/party-rpg/gdd/content/heroes.md` gains the required `data_dir: ../../content/heroes` and `count_target: 8`, restating the starter's own `entities.heroes` as the canonical example's `items.md` does. Its example hero is now linked to a content-schema and validates against it. **Trees scaffolded from the v0.3 party-rpg starter carry this defect**; the fix is those two keys in `gdd/content/heroes.md`, with the tree's own `count_target` ([v0.3 correction note](docs/release-notes/v0.3-conformance-correction.md)).
- **OI-006 class B (D-030): the survival benchmark's verbs are schema-valid.** In `benchmark/games/survival`, `time_cost` and `consumes` move out of `cost:` to the verb level, with `cost: 0`, as the survival starter already does. `$defs.Cost` admits only an integer, a string or `{resource, amount}`. All 9 player verbs were affected (OI-006 said 8). The move also makes the tree's prose path for the clock's delta (`time_cost.in_game_minutes`) exist, on 8 of the 9 verbs; the ninth, `sleep_through_night`, declares hours and is left as is. Root version 0.2.1.
- **AGENTS.md drift from the spec** (external review): stability guarantee restated as the spec's four fields (`core_loop_ref` was missing — an agent taught the three-field version would mutate it without a major bump); `{loop.combat_turn}` corrected to `{loops.combat_turn}` (the taught example would not resolve under our own linter); Hard Rule 2's universal-surface list updated to include `events`, `clocks`, `invariants`.
- **Spec §9 opening verb list** updated from the four v0.1 verbs to all nine shipped verbs (`lint | diff | export | spec | verify | status | hook | touch | init`).
- **Spec §2.2 required-vs-optional reconciliation** — "five conditionally-required files" corrected to four; `economy-balance.md` documented as effectively unconditional (`missing-balance-targets` is an unconditional error); `distributions.md` comment now states its condition.
- **Namespace-count reconciliation** (§1 / §4 intro / Appendix C / README) — "seven primitives" pinned to the original v0.1 core; Appendix C now enumerates the full twelve-namespace surface and recommends citing "the universal surface" over a number.
- **F-009 cost-as-amortized framing hardened** (case study + spec §11.2) — named explicitly as a *hypothesis generated by the gate failure*, not a clarification: per-session cost is real and paid up-front; amortization is queued for v0.4+ longitudinal validation. Applies the counterfactual-adoption test to the project's own reframe. Also added to F-009's does-not-establish list: condition B was information-equivalent flattened prose, not the messy real-world GDD counterfactual.
- **§4.8 `discrete_sum` variance formula** — unbalanced parenthesis corrected to `samples × ((range[1] − range[0] + 1)² − 1) / 12` (the worked value was already correct).
- **DECISIONS.md D-004 reordered** between D-003 and D-005 (all three decided 2026-05-21), restoring the front-to-back chronological reading the methodology doc promises.
- **Test-suite time-bomb defused** — `test_prototyped_without_pointer_silent_on_fresh_baseline` asserted the baseline fixture's baked `last_verified` dates were "fresh" against wall-clock today; it began failing 30 days after the dates were written. Now injects a fixed `now` like the rest of the anti-staleness tests.
- **`httpx` added to dev extras** — `benchmark/harness/llama_server.py` imports it; test collection failed without it.
- **pyproject `[project.urls]`** — added `Changelog` and `Issues`.
- **Dogfood copies ran the wrong `gdmd`.** `fixture.prepare_copy` put the shim *file* on `PATH` instead of its directory. So `gdmd` inside a copy fell through to whatever install was on the caller's `PATH`: during development, the real repository's editable install. Tests and the commit-5 dry run passed only because that install was the same code. No model session had run. A regression test pins resolution to the cell's own shim.

## [0.3.0] — 2026-05-29

The **living development surface** release. v0.3 closes the two F-008 / F-010 expressiveness gaps that surfaced during v0.2 Phase 5; ships the lifecycle-state expansion, anti-staleness lint rules, pre-commit hook + atomic `touch`, project dashboard view, six per-genre starter templates, and the three-mode agent companion; records the validation-bar reframe (premise-correction discipline) as decision-of-record D-021.

See [docs/release-notes/v0.3.md](docs/release-notes/v0.3.md) for the narrative summary and the three-claim validation surface.

### Added

- **`{clocks.<id>}` namespace** (§4.7) — first-class time-passage primitive distinct from player verbs. Two modes at v0.3: `continuous` (fixed-rate, e.g. 60 Hz physics) and `per_verb_delta` (advances after each verb by a context-local delta). Closed enum; future modes (`scheduled` for wave timers / day-night cycles) ratchet by observed use. Resolves F-010. (`84c3fba`)
- **`instance_container` entity type** (§4.1) — N owned instances each carrying per-instance runtime state, with `capacity:`, `holds_template_from:`, and `per_instance_state:` sub-schema. Completes entity-cardinality coverage (one / many-templated / many-instanced). Resolves F-008. (`60fe7dd`)
- **Addressing DSL for instance_container** (§3, §4.5, D-019) — binding semantics over existing `{actor.<field>}` / `{target.<field>}` refs through a documented lookup order (`per_instance_state` → template → container properties). Zero new syntax; spec-level normative declaration of binding semantics. Writes restricted to per_instance_state fields; `write-to-template-field` lint rule (`8eee42b`) enforces. (`f2572cc`)
- **`experimental` and `deferred` lifecycle states** (§8.1, D-020) — lateral non-canonical-path states. `experimental`: code exists, design under active evaluation. `deferred`: lifecycle progression paused, returning later. Spec lifecycle vocabulary closes for v0.3 around observed need; `blocked` deferred until live adoption surfaces it. (`9b8ee70`)
- **`gdmd status` CLI verb** (§9.6) — project dashboard projecting status counts, stale-sections, shipped-stale, active-without-impl per tree. Always exits 0 (informational, not a gate). `--json` for tooling. (`ae14877`)
- **`gdmd hook install` + `gdmd hook check` + `gdmd touch` CLI verbs** (§9.7) — commit-side of the bidirectional `implementation_pointers` anti-drift contract. `hook install` registers a pre-commit-framework entry; `hook check` surfaces affected spec sections on each commit (informational); `touch` atomically bumps `last_verified:` while preserving author quoting/formatting (regex-on-frontmatter, not pyyaml round-trip). Composes with `stale-section` lint to close the anti-drift ritual at every change point. (`2be0824`)
- **`gdmd init` CLI verb** (§9.8) — scaffolds new trees from per-genre starter templates. `--list`, `--genre <name> [<dest>]`, interactive prompt. Refuses non-empty destinations. (`efc8614`)
- **Six per-genre starter templates** under `templates/starters/`: deckbuilder, party-rpg, tcg, tick-combat, platformer, survival. All lint-clean (0 errors, 0 warnings) under default thresholds. Each is a *descriptive scaffold extracted from the corresponding canonical example*, not a *prescriptive contract* — v0.3 vocab inherited where the canonical example demonstrated closure. (`efc8614`)
- **Anti-staleness lint rule family** (§9.1) — `stale-section` extended with status-aware skip (`draft / cut / deferred` are exempt) and configurable `--stale-days` (default 30). Two new rules: `prototyped-without-pointer` (warning; active-status token with empty `implemented_in:` past `--prototyped-stale-days`, default 30) and `shipped-stale-doc` (warning; `status: shipped` file with `last_verified:` past `--shipped-stale-days`, default 180). Defaults grounded in reasonable maintenance-cadence assumptions, NOT in-repo `last_verified` distribution. (`3ba84b9`)
- **D-021 + spec §11.2** — deployment-surface reframe recorded as decision-of-record. Triangulates with D-016 (constraint-driven scope reduction) and gate-correction-vs-loosening as the three legitimate-cause-for-bar-movement disciplines, each with its own diagnostic test. (`37fd1fd`)
- **`docs/case-studies/F-009.md`** — worked example: hypothesis → methodology → supersession chain → null+cost-fail result → reframe. (this release)
- **`docs/methodology/README.md`** — framing layer pointing to spec §11.2, D-021, AGENTS.md three-mode lens, F-009 case study; the discipline framework as transferable artifact. (this release)
- **`docs/release-notes/v0.3.md`** — three-claim validation surface, queued-for-v0.4 list, reframe lineage. (this release)
- **`CHANGELOG.md`** — this file. (this release)
- **AGENTS.md three-mode operating lens** — authoring / operating / maintenance with mode-signal + forbidden-actions + CLI per mode. Adversarial 12-probe survey at authoring time: 10 caught, 2 documented as legitimate template edges (not defects). (`a88d490`)

### Changed

- `spec_version:` bumped from `0.2.0-alpha` to `0.3.0` across the spec, schema `$id`, and all 12 in-repo tree frontmatter declarations (166 files). `pyproject.toml` bumped to `0.3.0a1`. Schema title and `$id` URL updated; the schema accepts any semver for `spec_version:`, so trees declaring earlier versions remain readable but should ratchet to `0.3.0` when adopting v0.3 vocabulary.
- `examples/tick-combat/` retro-touched to use `{clocks.tick}` (F-010) and `instance_container` for deployed units (F-008); cross-engine verify-adapter gate (`gdmd verify`) clears byte-identical to the v0.2 golden trajectory at `seed=12345` after both retro-touches land. (`c13bc59`)
- Three other in-repo trees retro-touched to use v0.3 vocabulary where the canonical example demonstrated need: party-rpg + tcg + benchmark/games/survival for `instance_container`; benchmark/games/platformer + benchmark/games/survival for `{clocks.<id>}`. (`60fe7dd`, `84c3fba`)
- AGENTS.md restructured around the three-mode operating lens; the anti-drift ritual now references the v0.3 commit-side `gdmd hook` workflow. (`a88d490`, `2be0824`)
- README rewritten to lead with the **living-doc proposition** (closer analog: CLAUDE.md / AGENTS.md) — temporal axis as the differentiator. (this release)

### Validated (in-repo)

- **Vocabulary closure** — v0.3 vocabulary additions are expressible on real spec content across the 6 in-repo trees without local invention.
- **Cross-engine determinism preserved** — tick-combat's `gdmd verify` adapter gate clears byte-identical (xtreme/Bevy ECS + Godot/GDScript, same `seed=12345`) after F-008 + F-010 land; negative control diverges at `seed=99999` per §9.5.7.
- **Session-level maintenance** — the agent performs the anti-drift ritual end-to-end on the in-repo trees when actively prompted; `gdmd status` projects the staleness / pointer-health markers the ritual produces.

### Queued for v0.4+ (gated on observed need from live adoption)

- **Longitudinal living-doc property** — the doc stays current across weeks/months without continuous human review. The 6 in-repo trees can't validate this claim; they are spec-illustrations and benchmark targets, not games-in-development.
- **Cross-agent transfer of the three-mode operating lens** — AGENTS.md's adversarial probe was authored under Claude Code. Whether the discipline transfers to other agents is an empirical question awaiting cross-agent runs.
- **M1 / M2 watch-items** — two adversarial probes from the AGENTS.md Task 5 survey documented as legitimate template edges; promote or close based on live evidence.
- **Spec → code anti-drift direction** — Task 4 ships code → spec via pre-commit. The inverse (spec edit implies impl may need updating) is a different workflow shape, deferred until adoption surfaces a need.
- **Status vocabulary expansion (`blocked`, others)** — D-020 closed the v0.3 vocabulary around observed need from 4 trees. Future states ratchet by the same discipline.
- **`scheduled` clock mode** — F-010 closed at two modes (`continuous`, `per_verb_delta`). Wave-timer / day-night / scripted-event use cases are the watch-for-v0.4 candidates.

## [0.2.0-alpha] — 2026-05-22 → 2026-05-28

The **demonstration** release. v0.2 closed the gap between "is the spec well-formed" (v0.1.1, yes) and "does the spec drive working game code in any engine" (v0.2, demonstrated via reference implementations + cross-engine determinism + help-benchmark).

### Phase 1 — Decision-debt cleared

- D-003 (typed balance-target vocabulary), D-005 (events as first-class tokens), D-006 (packaging — `importlib.resources` for spec/schema export). All four canonical examples re-migrated. (`5f87cc3`)

### Phase 2 + 2.5 — First reference implementation (tick-combat / xtreme / Bevy ECS)

- xtreme reference implementation (Rust + Bevy ECS), drives behavior entirely from the spec tree.
- Phase 2 surfaced ten spec ambiguities; Phase 2.5 resolved 9 of 10 (the 10th deferred to v0.3 as D-005); locked golden trajectory at `seed=12345`. (`bc2250f`, `319dfac`, `9ef8831`)

### Phase 3 — `verify` adapter contract

- §9.5 contract authored: engine-neutral adapter invocation, `VerifyResult` JSON schema, canonical JSONL trajectory format.
- Trajectory-format hardening at Phase 3+ (array-ordering total-order requirement, integer-width declaration, ASCII-only locale handling); D-002 (`broken-implementation-pointer` warning → error) ratcheted. (`36e4ff5`, `497b43b`)

### Phase 4 + 4+ — Cross-engine determinism CLOSED

- Engine-B reference impl in Godot 4 / GDScript (substituted for Unreal Blueprints after the addendum's scope assessment).
- Cross-engine bar surfaces spec gaps #12–#15 (PRNG pin, uniform-int reduction normative form, weighted selection rule, threshold comparison direction) as designed.
- Both engines byte-identical at `seed=12345`. D-015 (PRNG pin: xoshiro256** + splitmix64 + reference vector), D-016 (`discrete_sum` integer-native distribution superseding `gaussian` for state-affecting use), D-017 (weighted selection rule normative), D-018 (uniform-int reduction reference vector). (`3f568e9`, `a9d23ad`, `cfbeb53`)

### Phase 5 — Help-benchmark (single-subject Qwen-Coder, scope reduced under v12-D)

- Pre-registration v1 → v14-D with full supersession chain recorded.
- F-009 reported by the locked rule: **NULL on success-lift** (−5.8pp, McNemar p=0.42, N=120 paired); **FAIL on cost-lift** (37.1%, lower-bounded by cap-truncation); apparatus limitations stated (post-hoc sanitizer leak ~19pp, cap-truncation on hard tasks, bounded-blinding ceiling, single-subject scope).
- See [docs/case-studies/F-009.md](docs/case-studies/F-009.md) for the worked example.
- F-010 (verb-centric friction surfaces in 2 fresh games) discovered; queued for v0.3. F-008 (per-instance owned-item state gap) discovered; queued for v0.3. (`37c004d` and the supersession chain commits before it)

## [0.1.1] — initial

The bootstrap release. Spec (911 lines), JSON Schema (31 `$defs`), CLI (`gdmd lint | diff | export | spec | verify` — `verify` contract-only at v0.1.1), four lint-clean canonical examples (deckbuilder, tick-combat, party-rpg, tcg), DECISIONS.md D-001 through D-006, benchmark harness scaffolding. (`0562909`)

---

[Unreleased]: https://github.com/bantarus/game-design.md/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/bantarus/game-design.md/releases/tag/v0.3.0
[0.2.0-alpha]: https://github.com/bantarus/game-design.md/compare/v0.1.1...v0.2.0-alpha
[0.1.1]: https://github.com/bantarus/game-design.md/releases/tag/v0.1.1
