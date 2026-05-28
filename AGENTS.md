# AGENTS.md

> Workflow guide for any coding agent working in this repository. This file describes **how to work**, not what the format is. The format itself is specified in `docs/spec.md`. Keep this file under ~150 lines.

## What this repo is

`game-design.md` is a specification + tooling project for an LLM-first, engine-neutral, genre-agnostic game design document standard. It is modeled on Google Labs' `DESIGN.md`. The primary consumer of a `game-design.md` file is a coding agent; a human is the second reader.

This repo contains: the spec (`docs/spec.md`), the frontmatter JSON Schema (`schema/`), a CLI (`game-design.md`), and one example per genre (`examples/`).

## Read order when you start a task

1. This file (`AGENTS.md`).
2. `docs/spec.md` — the authoritative format definition.
3. The root `game-design.md` of whichever example you are touching — **always read it in full first.**
4. Only the `gdd/` subfiles relevant to the current task. Do not load the entire `gdd/` tree; use the `files:` map in the core file to find what you need.

## How to read a `game-design.md` tree

- **YAML frontmatter is normative.** Token values are the truth you compile against.
- **Markdown prose is rationale.** It explains *why* and is your fallback when no token covers a case — extrapolate from intent, do not invent.
- **Resolve `{namespace.id}` references by namespace.** Example: `{loop.combat_turn}` lives in `gdd/loops.md` frontmatter; `{resources.energy}` in `gdd/mechanics.md`; `{distributions.card_draw}` in `gdd/systems/distributions.md`.
- **Content-heavy types are external.** A `data_source:` field points to a directory of `*.yaml` files (e.g. `content/cards/`). Read individual entity files on demand; never assume the `gdd/content/*.md` subfile contains the full set.

## Hard rules (never violate)

1. **Engine-neutral.** Never assume Unity / Godot / Unreal / Bevy / Tauri / Flutter or any engine. Platforms are abstract (`desktop`, `handheld`, ...).
2. **Genre-neutral core.** Never add genre-specific tokens to `docs/spec.md` or `schema/`. Genre-specific concepts belong in an example's own subfiles as prose conventions. The universal surface (entities, verbs, resources, states, rules, loops, distributions + feel, balance_targets) is the whole value proposition — guard it.
3. **Tokens normative, prose rationale.** Do not encode authoritative numbers in prose, and do not encode rationale in tokens.
4. **Short core file.** The root `game-design.md` stays under ~200 lines. Push detail into subfiles.

## Anti-drift ritual (run on every change)

When you modify a design or its implementation:

1. Update the affected entity's `status:` (`draft | prototyped | implemented | balanced | shipped | cut | experimental | deferred` — see spec §8.1; the lateral `experimental` + `deferred` states landed v0.3 per D-020).
2. Update `implemented_in:` if source locations changed.
3. Touch `last_verified:` on any section whose referenced code you changed.
4. Bump `version:` in the root `game-design.md` and update `last_updated:`.
5. Run `game-design.md lint <example-dir>` and fix all findings.
6. Run `game-design.md diff` if comparing against a release; treat a balance-target regression (exit code 1) as a blocker, not a warning.
7. Optionally run `gdmd status <example-dir>` to surface aggregate state (status counts, staleness flags, pointer health) — useful when picking up a tree cold or before a milestone commit.

Only `pillars`, `non_goals`, and `player_experience_goals` are stable for the life of a project. Everything else may drift — but must be re-validated when it does.

## Building & testing the CLI

- Language: **Python ≥3.10** (Hatchling build backend). Install with `pip install -e ".[dev]"` (or `uv pip install -e ".[dev]"`), test with `pytest`.
- After install, both `game-design.md` and the short alias `gdmd` are on `$PATH`. Either works.
- Linter rules to keep green: `broken-ref`, `orphaned-entity`, `unreferenced-verb`, `missing-pillars`, `missing-core-loop`, `missing-balance-targets`, `undefined-distribution`, `stale-section`, `section-order`.
- `lint` must emit structured JSON (`{ findings: [...], summary: {...} }`) so an agent can self-correct.
- Before committing CLI changes, run `gdmd lint examples/deckbuilder` and confirm it passes clean.

## Working style

- Use `web_fetch` on the real `DESIGN.md` spec and examples before changing our conventions. Match its structure where sensible; diverge only for game-specific needs and note why in the commit message.
- When a design decision is genuinely ambiguous, present 2–3 options and ask rather than guessing.
- Prefer a prose convention in an example subfile over a new core-spec token whenever tempted to add genre-specific structure.
- Commit in small, reviewable units with clear messages.
- Do not invent product features beyond what `docs/spec.md` and the active task describe.

## The success benchmark

The schema is working if, from a cold context, you can implement a correct new content entity (e.g. a card) from a `gdd/content/*.md` schema + one example `*.yaml` in a single session ≥80% of the time. If you drop below that, the schema is over- or under-specified — surface it rather than working around it.
