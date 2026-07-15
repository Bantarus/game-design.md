# AGENTS.md

> Workflow guide for any coding agent working in this repository. This file describes **how to work**, not what the format is. The format itself is specified in `docs/spec.md`. Keep this file under ~200 lines.

## What this repo is

`game-design.md` is a specification + tooling project for an LLM-first, engine-neutral, genre-agnostic game design document standard. It is modeled on Google Labs' `DESIGN.md`. The primary consumer of a `game-design.md` file is a coding agent; a human is the second reader.

This repo contains: the spec (`docs/spec.md`), the frontmatter JSON Schema (`schema/`), a CLI (`game-design.md`), one canonical example per genre (`examples/` + `benchmark/games/`), and six per-genre starter templates (`templates/starters/`) surfaced via `gdmd init`.

## Read order when you start a task

1. This file (`AGENTS.md`).
2. `docs/spec.md` — the authoritative format definition.
3. The root `game-design.md` of whichever example you are touching — **always read it in full first.**
4. Only the `gdd/` subfiles relevant to the current task. Do not load the entire `gdd/` tree; use the `files:` map in the core file to find what you need.

## How to read a `game-design.md` tree

- **YAML frontmatter is normative.** Token values are the truth you compile against.
- **Markdown prose is rationale.** It explains *why* and is your fallback when no token covers a case — extrapolate from intent, do not invent.
- **Resolve `{namespace.id}` references by namespace.** Example: `{loops.combat_turn}` lives in `gdd/loops.md` frontmatter; `{resources.energy}` in `gdd/mechanics.md`; `{distributions.card_draw}` in `gdd/systems/distributions.md`.
- **Content-heavy types are external.** A `data_source:` field points to a directory of `*.yaml` files (e.g. `content/cards/`). Read individual entity files on demand; never assume the `gdd/content/*.md` subfile contains the full set.

## Hard rules (never violate)

1. **Engine-neutral.** Never assume Unity / Godot / Unreal / Bevy / Tauri / Flutter or any engine. Platforms are abstract (`desktop`, `handheld`, ...).
2. **Genre-neutral core.** Never add genre-specific tokens to `docs/spec.md` or `schema/`. Genre-specific concepts belong in an example's own subfiles as prose conventions. The universal surface (entities, verbs, resources, states, events, rules, loops, clocks, distributions + feel, balance_targets, invariants) is the whole value proposition — guard it.
3. **Tokens normative, prose rationale.** Do not encode authoritative numbers in prose, and do not encode rationale in tokens.
4. **Short core file.** The root `game-design.md` stays under ~200 lines. Push detail into subfiles.

## Three modes (the operating lens)

Every activity in this repo applies one of three disciplines. The modes are *activity-driven*, not time-driven — they interleave throughout a session. Recognizing which mode you're currently in is what lets you apply the matching prohibition. **The prohibitions are the load-bearing piece** — they hold under workload better than required-action lists, which fade.

### Authoring — designing or extending the vocabulary

**Mode signal.** You're editing `schema/`, `docs/spec.md`, or `DECISIONS.md`; you're proposing a new namespace, enum value, or lint-rule semantics; you're asking "should the spec support X?" or "is X expressible?"

**Forbidden:**
- **Adding genre-specific tokens to the core spec.** (Restates Hard Rule 2 at the mode level — most-violated rule, worth doubling.)
- **Preempting vocabulary growth.** A closed enum extends by *observed* use, not anticipated use. F-010 shipped `mode: continuous | per_verb_delta` only; `scheduled` was a watch-item, not a v0.3 addition.
- **Inventing new syntax when existing vocab + a normative semantics declaration closes the gap.** D-019's addressing DSL added zero new syntax; it specified binding semantics over existing `{actor.X}` / `{target.X}` refs.
- **Adding a vocabulary item without observed-use evidence.** D-020 added `experimental` + `deferred` because prose markers existed across 4 trees; `blocked` is deferred until live adoption surfaces it.
- **Imposing new shape engines must conform to.** Name observable shape engines already have. Verify-adapter PASS is then *expected*, not lucky. (Memory: `descriptive-not-prescriptive-vocabulary-extensions`.)
- **Calibrating defaults against the population you'd use them to validate.** Circular trap. Task 6 grounded `--stale-days` defaults in cadence assumptions, NOT the in-repo `last_verified` distribution.
- **Quietly dropping or silently swapping a validation claim.** Reframes get recorded in DECISIONS.md + spec text (D-021 + §11.2 pattern). Premise-correction is honest only when audit-lineage-preserved. (Memory: `premise-correction-reframe-is-gate-correction`.)

**CLI:** `gdmd spec` (read the spec back); `gdmd export --format schema` (validate the schema parses).

### Operating — implementing the design (CLI, lint rules, example trees, cross-engine adapters)

**Mode signal.** You're editing `src/game_design_md/` (CLI/lint impl), `examples/<game>/` or `benchmark/games/<game>/` (tree retro-touch), `examples/tick-combat/impl/` (cross-engine adapter); you're "implementing X" or "using the new vocabulary in Y."

**Forbidden:**
- **Committing with broken refs.** Every `{ns.id}` must resolve at lint time. `broken-ref` is an error, not a warning.
- **Committing through a broken verify-adapter** on a tree that has one. Tick-combat's `gdmd verify` gate is sacred — cross-engine byte-identity is the hardest gate the spec has; a regression there means the change broke determinism, not that the gate is too strict.
- **Polluting `examples/<game>/` to drive lint coverage.** Use `tests/fixtures/` for synthetic cases. (Memory: `examples_vs_fixtures`.)
- **Shipping vocabulary without retro-touching every tree that exhibits the friction it closes.** F-008 + F-010 updated 3 trees each; partial coverage would have left the convergence claim unverified.
- **Working around a bug instead of diagnosing the root cause.** When Task 4's hook check broke under pre-commit's CWD convention, the fix was path normalization in `check_staged`, not a workaround in the renderer.
- **Fabricating values.** When uncertain, reference an existing token, ask the user, or mark the entity `draft` with empty `implemented_in:`. Never invent numbers, never invent token names.

**CLI:** `gdmd lint <tree>` (verify the tree compiles after every edit); `gdmd verify <tree>` (for trees with adapters); `pytest` (for src/ + tests/ changes).

### Maintenance — pre-commit, status hygiene, audit lineage

**Mode signal.** You're updating `tests/`, `AGENTS.md`, `CLAUDE.md`; you're running the anti-drift ritual; you're drafting a commit message; phrases like "ready to commit," "sanity check," "what changed and what's next."

**Forbidden:**
- **Committing without a sanity sweep.** Pytest + `gdmd lint` on every touched tree + `gdmd verify` on tick-combat for any change that could affect determinism.
- **Shipping a new lint rule or behavior without a proof-of-fire.** Demonstrate the rule fires on shaped-like-real content, not just synthetic fixtures (Task 6 deckbuilder mutation; Task 4 tick-combat real paths). Synthetic-only tests prove mechanics; real-tree proof-of-fire proves the rule fits the population it's meant to govern.
- **Using `experimental` as an escape hatch for uncertainty.** It means "code exists, design under active evaluation." NOT "I'm not sure what status this is." (Spec §8.1 + D-020.)
- **Committing with a what-only message.** The *why* — which discipline applied, which calibration the choice rests on, which sister-disciplines apply — is the audit trail future agents need. Commit messages are first-class artifacts.
- **Silently calibrating against the population you'd validate.** Name the calibration source explicitly in the commit message (Task 6 named "defaults grounded in reasonable cadence, NOT in-repo distribution").
- **Changing the workflow without updating AGENTS.md.** Every new CLI command, every new ritual step, every new mode prohibition lands here too. (CLAUDE.md only if the change is Claude-specific.)
- **Deferring memory writes.** Save the discipline when it's concrete and worth saving for future sessions; deferred memory writes get forgotten. Save mid-flow, not at end-of-session.

**CLI:** `gdmd status <tree>` (aggregate snapshot); `gdmd touch <subfile>` (atomic `last_verified` bump, formatting-preserving); `gdmd lint <tree>` (final sweep); `gdmd diff <old> <new>` (against release baseline); `pytest`.

## Anti-drift ritual (run on every change)

When you modify a design or its implementation:

1. Update the affected entity's `status:` (`draft | prototyped | implemented | balanced | shipped | cut | experimental | deferred` — see spec §8.1; the lateral `experimental` + `deferred` states landed v0.3 per D-020).
2. Update `implemented_in:` if source locations changed.
3. Touch `last_verified:` on any section whose referenced code you changed — `gdmd touch <subfile>` does this atomically (preserves quoting + frontmatter formatting).
4. Bump `version:` in the root `game-design.md` and update `last_updated:`.
5. Run `game-design.md lint <example-dir>` and fix all findings.
6. Run `game-design.md diff` if comparing against a release; treat a balance-target regression (exit code 1) as a blocker, not a warning.
7. Optionally run `gdmd status <example-dir>` to surface aggregate state (status counts, staleness flags, pointer health) — useful when picking up a tree cold or before a milestone commit.

**The pre-commit hook (Task 4 v0.3) automates the commit-side of this ritual.** Run `gdmd hook install <tree>` once per repo to register a `local` hook in `.pre-commit-config.yaml`. On every commit, `gdmd hook check` surfaces any spec sections whose `implemented_in:` / `implementation_pointers:` reference your staged files, with a copy-paste `gdmd touch <sections>` suggestion. The hook is informational (always exits 0); the agent or developer judges whether the change altered design intent and either runs `gdmd touch` or proceeds. See spec §9.7.

Only `pillars`, `non_goals`, `player_experience_goals`, and `core_loop_ref` are stable for the life of a project (spec §5.1 / §8.2). Everything else may drift — but must be re-validated when it does.

## Building & testing the CLI

- Language: **Python ≥3.10** (Hatchling build backend). Install with `pip install -e ".[dev]"` (or `uv pip install -e ".[dev]"`), test with `pytest`.
- After install, both `game-design.md` and the short alias `gdmd` are on `$PATH`. Either works.
- Linter rules to keep green: `broken-ref`, `orphaned-entity`, `unreferenced-verb`, `missing-pillars`, `missing-core-loop`, `missing-balance-targets`, `undefined-distribution`, `stale-section`, `section-order`.
- `lint` must emit structured JSON (`{ findings: [...], summary: {...} }`) so an agent can self-correct.
- Before committing CLI changes, run `gdmd lint examples/deckbuilder` and confirm it passes clean.
- Before committing changes to README.md, AGENTS.md, docs/spec.md, or the CLI verb set, run `python scripts/docs_lint.py` — it drift-lints the docs themselves (version agreement, §9 verb list vs the click registry, the four-field stability guarantee, namespace validity of taught refs). CI runs it on every push.

## Universal practice (across all three modes)

- **When a design decision is genuinely ambiguous, present 2–3 options and ask** rather than guessing. Auto-mode doesn't change this — auto-mode means "make the reasonable call and keep going" on operational choices, not "guess on ambiguous design intent."
- **`web_fetch` the real `DESIGN.md` spec** before changing our conventions to match upstream. Match its structure where sensible; diverge only for game-specific needs and note why in the commit message.
- **Commit in small, reviewable units with clear messages.** One discipline change per commit when feasible (D-021 alone, Task 6 alone, Task 4 alone — each a separate `37fd1fd → 3ba84b9 → 2be0824` step rather than one mega-commit).
- **Do not invent product features beyond what `docs/spec.md` and the active task describe.**

## The success benchmark

The schema is working if, from a cold context, you can implement a correct new content entity (e.g. a card) from a `gdd/content/*.md` schema + one example `*.yaml` in a single session ≥80% of the time. If you drop below that, the schema is over- or under-specified — surface it rather than working around it.
