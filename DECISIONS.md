# DECISIONS

Explicit, dated calls made during `game-design.md` development. Each entry: what we decided, why, and when it ratchets. **This file is normative for the project, not the spec** — spec changes live in `docs/spec.md`.

---

## D-001 — `event:` not `on:` for `StateTransition` (v0.1.1)

- **Status:** locked.
- **Decided:** 2026-05-21.
- **Spec:** §4.4.

The transition trigger key in a `states.<machine>.transitions[*]` entry is `event:`, not `on:`. YAML 1.1 (still the default loader behavior in PyYAML and many other libraries) implicitly coerces unquoted `on`, `off`, `yes`, `no` to booleans, so `{ from: x, on: draw, to: y }` parses as `{ 'from': 'x', True: 'draw', 'to': 'y' }` and silently breaks every downstream check. `event:` is foolproof regardless of YAML mode and semantically clearer.

**Ratchet plan:** revisit if/when the ecosystem moves to YAML 1.2-only loaders. Until then `event:` is normative; `on:` is rejected by the schema.

---

## D-002 — `broken-implementation-pointer` is a warning in v0.1.1 (was: error)

- **Status:** locked for v0.1.1, ratchets to **error** in v0.2.
- **Decided:** 2026-05-21.
- **Spec:** §8.2 mechanism 1; §9.1 rule table.

The rule's *intended* severity is `error`: an entity claiming `status: prototyped` or higher should point at real source. But the included examples (`examples/deckbuilder/`, soon `party-rpg/`, `tick-combat/`, `tcg/`) declare their `implemented_in:` paths against fictional source trees that do not ship in this repo — the examples are pedagogical, not running code. Holding them to `error` would fail `gdmd lint examples/deckbuilder` on every entity.

**Ratchet plan:** when the first example ships with real source (or with a real `gdmd verify` adapter that exercises the contract), promote the rule to `error`. Track via PR labeled `ratchet-D-002`.

---

## D-003 — Composite `balance_targets.*` is permissive in v0.1.1

- **Status:** locked for v0.1.1, ratchets to **typed vocabulary** in v0.2.
- **Decided:** 2026-05-21.
- **Spec:** §4.9; `$defs.BalanceTarget` in `schema/game-design.schema.json`.

The schema's `BalanceTarget.target` is permissive (`{ }` — accept any JSON value) so that composites like `cards_per_rarity: { common: 110, uncommon: 80, rare: 30 }` can be authored today. This means:

- `lint` cannot statically verify that the value type is comparable against `tolerance`.
- `gdmd diff` can detect changes in composite targets but cannot detect *regressions* (the "moved outside tolerance" check is meaningless for composites in v0.1.1).
- `gdmd verify`'s `behavioral_alignment` axis cannot meaningfully validate composite targets — the adapter has to special-case each one in project code.

**Ratchet plan in v0.2:** introduce a typed `target_kind:` discriminator on `BalanceTarget`, with three v0.2 values:

- `scalar` — single number/string + scalar tolerance. The current default.
- `range` — explicit `{ low, high }` with a tolerance band on each.
- `distribution_over_categories` — composite like `cards_per_rarity`; tolerance is per-category.

Once the discriminator exists, `lint` enforces per-kind shape, `diff` enforces per-kind regression detection, and `verify`'s contract on `expect:` shorthands (`{ between, near, equals }`) extends naturally.

---

## D-005 — Transition events stay strings (not tokens) in v0.1.1

- **Status:** locked for v0.1.1; revisit in v0.2 once verb/event topology is mature.
- **Decided:** 2026-05-21.
- **Spec:** §4.4; `state-machine-coverage` `undefined-event` sub-finding.

A `states.<machine>.transitions[*].event` value is a free-form string identifier — `event: draw`, not `event: "{events.draw}"`. The deeper question is whether transition events should be first-class tokens with their own namespace (`{events.draw}`), which would let `lint` cross-check that every event a state machine reacts to is *produced* somewhere (by a verb's `effects`, by a rule's `outputs`, by an external input). That cross-check is the substance of the deferred `undefined-event` sub-finding under `state-machine-coverage`.

**Why deferred at v0.1.1:** the existing verb/rule shapes don't have a normative "this event is emitted" field, so the cross-check would either fire vacuously or generate noisy false-positives. Adding the namespace prematurely locks in a vocabulary that may not match the v0.2 verb model.

**Ratchet plan in v0.2:** introduce an `events` namespace + `{events.<id>}` syntax; have verb `effects` and rule `outputs` enumerate emitted events; promote `undefined-event` to a real cross-reference check that resolves through that vocabulary. This also unifies with the `verify` adapter's behavioral-alignment observations.

---

## D-006 — Packaging via `importlib.resources` at v0.2

- **Status:** v0.1.1 ships dev-install-only; v0.2 must work from a wheel.
- **Decided:** 2026-05-21.
- **Implementation:** `src/game_design_md/spec_cmd.py`, `src/game_design_md/export_cmd.py`.

`gdmd spec` and `gdmd export --format schema` currently locate `docs/spec.md` and `schema/game-design.schema.json` via `Path(__file__).resolve().parents[2]`. This works for `pip install -e .` from the repo root (the editable install we use today) but breaks for a real wheel install where the source files live outside the package directory.

**Ratchet plan in v0.2:** package both files as `game_design_md/_data/` package data, read via `importlib.resources.files(game_design_md).joinpath("_data/spec.md")`. Update `pyproject.toml` `[tool.hatch.build]` to include them. Same change applies if/when we publish to PyPI.

---

## D-004 — Strict YAML loader is shared across all CLI verbs

- **Status:** locked.
- **Decided:** 2026-05-21.
- **Implementation:** `src/game_design_md/loader.py`.

`lint`, `diff`, `export`, and `verify` all use the same `GdmdLoader` (subclass of `yaml.SafeLoader`) which strips YAML 1.1's implicit boolean-alias and timestamp resolvers and re-adds only the YAML 1.2 boolean tag (`true|false`). Effect:

- `last_verified: 2026-05-21` parses as the ISO string `"2026-05-21"`, matching the schema's `ISODate` pattern.
- `event: on` parses as the string `"on"`, not `True`.
- `disabled: yes` parses as the string `"yes"`, not `True`.

This makes `event:` (D-001) belt-and-suspenders instead of load-bearing: even if a future author writes `on:`, the loader keeps it as a string. We still recommend `event:` for clarity, and the schema still rejects `on:` to keep authors honest.

**No ratchet needed.** This is the long-term loader.
