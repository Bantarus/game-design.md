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

## D-003 — Typed `target_kind:` vocabulary shipped at v0.2.0-alpha

- **Status:** shipped at v0.2.0-alpha. Lint rule `balance-target-untyped` is **warning** through v0.2; **ratchets to error in v0.3** once the migration window closes.
- **Decided:** 2026-05-21; landed 2026-05-22.
- **Spec:** §4.9; `$defs.BalanceTarget` in `schema/game-design.schema.json`.
- **Implementation:** `src/game_design_md/linter.py::rule_balance_target_untyped`; tests at `tests/test_lint.py::test_balance_target_untyped_warning` and `test_balance_target_typed_is_silent`.

`BalanceTarget` is now a discriminated union over `target_kind:`:

- `scalar` — number or string + 2-array `tolerance: [low, high]` (this is the v0.1.1 shape, just newly tagged).
- `range` — the target *is* a band; one of `{ between: [lo, hi] }` or `{ near: v, tolerance: t }`. No separate `tolerance:` field.
- `distribution_over_categories` — composite map; `target` and `tolerance` are both `{ <category>: <value>, ... }`.

Migration: the four examples are migrated; the deckbuilder demonstrates all three kinds (5× scalar, 1× range, 1× distribution_over_categories). A new `verify_target` at `examples/deckbuilder/gdd/verification.md` exercises the composite shape against an adapter contract.

**v0.3 ratchet:** `balance-target-untyped` becomes `error`; `target_kind` becomes structurally required by the loader (a tree without it fails to load instead of merely linting at warning). Schema is already strict — only the lint rule's severity is the soft path.

---

## D-005 — Events promoted to first-class tokens at v0.2.0-alpha

- **Status:** shipped at v0.2.0-alpha. `undefined-event` sub-finding is **warning** through v0.2; **ratchets to error in v0.3**.
- **Decided:** 2026-05-21; landed 2026-05-22.
- **Spec:** §3 (namespace ownership table), §4.4 (`events` namespace + transition syntax), §9.1 (`state-machine-coverage` row updated).
- **Implementation:** `src/game_design_md/tree.py::SUBFILE_NAMESPACES` (events added), `src/game_design_md/linter.py::rule_state_machine_coverage` (undefined-event sub-finding) + `rule_orphaned_entity` (events in the checked set); `$defs.Event` in `schema/game-design.schema.json`; tests at `tests/test_lint.py::test_undefined_event_on_bare_string`, `test_token_event_is_silent`, `test_broken_event_ref_is_error`, `test_orphaned_event_is_warning`.

Transition `event:` values are now `{events.<id>}` token references. Events live in their own namespace, owned by `gdd/mechanics.md`. Three lint behaviors follow:

- A `{events.<id>}` reference that doesn't resolve fires `broken-ref` at **error** (the existing rule, naturally extended).
- A bare-string `event:` (the v0.1.1 legacy shape) fires `state-machine-coverage` sub-finding `undefined-event` at **warning** — the migration backstop.
- An event defined but referenced by no transition joins `orphaned-entity` at **warning**.

The deeper cross-check the v0.1.1 deferral worried about — "every event a state reacts to must be *emitted* somewhere by a verb's effects or rule's outputs" — remains deferred. The v0.1.1 verb/rule shapes still don't have a normative "emits" field, so adding it now would still be premature. We picked the shape that's useful immediately (typed token tracking + orphan detection) and left the verb→event production cross-check for v0.3 once a real implementation (Phase 2 onwards) exercises which fields the engines actually need.

**v0.3 ratchet:** `undefined-event` becomes `error`; schema requires `event:` to match the `{events.<id>}` TokenRef pattern (currently it accepts any string for the migration window). Optionally, introduce an `emits:` field on `verbs` and `rules` and add the v0.1.1-deferred event-production cross-check then.

---

## D-006 — Packaging via `importlib.resources` shipped at v0.2.0-alpha

- **Status:** shipped at v0.2.0-alpha. Wheel installs now read packaged data; editable dev installs fall back to the canonical source paths.
- **Decided:** 2026-05-21; landed 2026-05-22.
- **Implementation:** `src/game_design_md/spec_cmd.py::spec_text` and `src/game_design_md/export_cmd.py::export_schema` both try `importlib.resources.files(game_design_md).joinpath("_data/...")` first, then fall back to the dev tree at `Path(__file__).parents[2..3]`. `pyproject.toml` uses Hatchling's `[tool.hatch.build.targets.wheel.force-include]` to copy `docs/spec.md` and `schema/game-design.schema.json` into the wheel at `game_design_md/_data/`. There is no source duplication: the canonical files live exactly where they always did.
- **Smoke test:** `tests/test_packaging.py::test_wheel_install_bundles_spec_and_schema` builds a wheel, installs it in a fresh venv, runs `gdmd spec` and `gdmd export ... --format schema` from a directory outside the source tree (so the dev-tree fallback cannot match), and asserts both produce content matching the canonical files. Skipped if `build` isn't installed.

**No further ratchet planned.** This is the long-term packaging story.

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

