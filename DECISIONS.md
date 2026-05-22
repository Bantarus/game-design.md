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

---

## D-007 — Engine A is `xtreme` (Bevy ECS, Rust)

- **Status:** locked at v0.2 kickoff addendum.
- **Decided:** 2026-05-22.
- **Reference:** `docs/game-design-md-v0.2-kickoff-addendum.md` §1.

Engine A for the v0.2 reference implementation of `examples/tick-combat/` is the `xtreme` engine, built on Bevy ECS. Real dogfooding: this is the harness games we are also building will actually ship in. Rust, compiled, data-oriented, ECS — the strict version of the `data_behavior_separation` invariant.

Implementation lives under `examples/tick-combat/impl/xtreme/`. The `gdd/` tree above it remains engine-blind; `implemented_in:` pointers reach down into the impl directory.

**No ratchet planned.** Engine A is the home-engine pick for v0.2; future versions may add more engines without disturbing this one.

---

## D-008 — Engine B is Unreal Blueprints (and what that's *for*)

- **Status:** locked at v0.2 kickoff addendum. Phase 4 objective reframed.
- **Decided:** 2026-05-22.
- **Reference:** `docs/game-design-md-v0.2-kickoff-addendum.md` §§2–3, §6.

Engine B is **Unreal Engine Blueprints**. The original kickoff named TypeScript; that was wrong — TypeScript is a simulation host, not a game engine. Unity DOTS was also considered and rejected: DOTS is itself a data-oriented ECS, so DOTS-vs-xtreme would prove only "the spec works in two ECS engines" (the weak form of neutrality). Unreal Blueprints — visual dataflow over a GC'd actor/object model — is genuinely far from Rust ECS.

**Phase 4's objective is therefore reframed.** Blueprints accrete design into the node graph by default; the graph becomes a *de facto* design document. The Phase 4 win condition is forcing the Blueprint graph to be a pure *consumer* of the spec: every number, rule, balance value, and state transition stays in `.md`, and the graph points back at it via `implemented_in:`. If we can hold that line in the engine most prone to absorbing design, that is a stronger anti-drift result than two side-by-side ECS implementations would have been.

**The finding to watch:** does `data_behavior_separation` survive in a non-ECS, actor-based, visual-dataflow engine — or was it ECS smuggled in under a neutral name? Either answer is a first-class outcome for `docs/v0.2-findings.md`; failure to survive is not failure to hide.

**Cost note:** the Unreal verify adapter is materially heavier than the Bevy one (commandlet / `-nullrhi` / automation harness vs. a quick headless Bevy run). Standing up a headless deterministic Unreal sim is itself the first big Phase 4 milestone.

---

## D-009 — Determinism bar: byte-identical within engine, integer trajectory across engines

- **Status:** locked at v0.2 kickoff addendum.
- **Decided:** 2026-05-22.
- **Reference:** `docs/game-design-md-v0.2-kickoff-addendum.md` §4.
- **Spec footprint:** `examples/tick-combat/gdd/architecture-invariants.md` — `gameplay_state_is_integer` (renamed from `damage_is_integer`, scope broadened) and `deterministic_given_seed` (bar split into Phase-3 / Phase-4 variants).

Two corrections to the kickoff:

1. **Integer-domain simulation is a HARD requirement for tick-combat, not advisory.** The `numeric_domain` invariant's scope broadens from "damage + hp + gold" to *every* gameplay-affecting quantity, including resource values, entity stats, distribution sampling rounding, and rule output domains. `enforcement: lint`. Floats are forbidden in the simulation hot path — they are the canonical source of cross-engine replay drift between Rust and the Blueprint VM. We renamed the invariant from `damage_is_integer` to `gameplay_state_is_integer` so the token name matches the broader scope.

2. **The cross-engine bar (Phase 4) is "identical canonical integer state trajectory," not "byte-identical replay hash."** Byte-identical serialization across two engines is a red herring — different engines serialize the same logical state differently. What we prove instead: both engines walk the same action sequence and produce the same integer game state at each tick.

   - **Within a single engine (Phase 3):** byte-identical replay still applies; it is the correct in-engine determinism check.
   - **Fallback:** if per-tick trajectory capture proves impractical in a given engine's headless mode, terminal-state + action-sequence equality is acceptable. Use only when full instrumentation is unavailable.

**No further ratchet planned for v0.2.** Phase 3 will instrument the trajectory shape against engine A; Phase 4 will verify it across A and B.

---

## D-010 — Real-valued distributions feeding integer state declare `output_domain` and `round_mode`

- **Status:** decided at v0.2.0-alpha (companion to D-009). Optional fields landed on tick-combat's `damage_roll`; structural schema enforcement is a v0.3 ratchet.
- **Decided:** 2026-05-22.
- **Reference:** `docs/game-design-md-v0.2-kickoff-addendum.md` §4.
- **Spec footprint:** `examples/tick-combat/gdd/systems/distributions.md` (the canonical example); spec §4.7 (`output_domain` + `round_mode` documented as optional Distribution fields with a soft contract).

**Framing.** Real-valued sampling (gaussian, uniform-over-floats) that feeds integer simulation state is not "an engine detail Phase 2 will discover." It is a **spec decision**: cross-engine determinism (D-009 Phase-4 bar) requires Rust and Unreal to round *identically*. If the rounding mode lives in each engine's code rather than in the `.md`, the spec is silent on the most consequential cross-engine variable and the divergence shows up at the worst possible moment — Phase 4 replay comparison — masquerading as a spec bug.

**Decision.** A distribution whose theoretical output is real-valued but whose use-site requires integer state MUST declare two optional fields:

- `output_domain: integer | real` — what the consuming simulation expects. Default `real` for backward-compatible reads. A distribution that participates in integer-domain state machines declares `integer`.
- `round_mode: half_to_even | half_up | floor | ceil | trunc` — required iff `output_domain: integer`. The canonical choice for unbiased numeric simulation is `half_to_even` (banker's rounding); other modes are accepted when an example needs them and justifies in prose.

The rounding happens **at the point of application**, not at sample time — sampling produces the canonical real-valued sample, the consuming rule rounds. This keeps the sampling PRNG output engine-portable and concentrates the divergence-prone step (rounding) at a single, declared boundary.

**Migration in v0.2.0-alpha.** Only `examples/tick-combat/gdd/systems/distributions.md::damage_roll` declares the new fields (gaussian, mean 5, stddev 1, clamp [1, 99], `output_domain: integer`, `round_mode: half_to_even`). The deckbuilder/party-rpg gaussians are not migrated this turn because their examples are not in the cross-engine implementation path; they may add the declaration as Phase 2/3 surfaces it. The Distribution `$defs` accepts `additionalProperties: true`, so the new fields are schema-legal without an explicit shape change.

**Uniform-with-threshold (Bernoulli idiom).** A separate but related case: `critical_hit: type: uniform, range: [0.0, 1.0], threshold: 0.10` produces a boolean output via float comparison; the comparison itself is the cross-engine divergence risk. The integer-domain reformulation is `range: [0, 99], threshold: 9` (10% crit when sample ≤ 9), avoiding floats entirely. This is the cleaner Phase-4 form. Not migrated this turn; Phase 2's xtreme implementation will test whether the float form holds up under deterministic seeds, and if it doesn't, the reformulation lands as part of that work.

**Ratchet plan in v0.3:** promote `output_domain` and `round_mode` to *required* schema fields on `Distribution` for `type: gaussian` and `type: uniform`; add a lint rule `distribution-output-undeclared` (warning, then error) that fires when a real-valued sampling distribution lacks the declaration. The current schema's permissive `additionalProperties: true` becomes a discriminated union once the field semantics are exercised in two engines.

---

## D-011 — Rules on deterministic loop paths require computable procedures, not prose labels

- **Status:** decided at v0.2.0-alpha (Phase 2.5). Implemented as the advisory lint rule `determinism-undetermined-rule`; ratchets to warning in v0.3, error in v0.4.
- **Decided:** 2026-05-22.
- **Source:** `docs/v0.2-phase2-spec-ambiguities.md`. Phase 2's archaeology surfaced #1, #5, #8, #9 as four instances of the same root cause — `{rules.X}.do[]` items written as bare prose strings (e.g. `resolve_unit_action`, `award_gold_to_winner`) instead of typed computable steps. The xtreme implementation had to *invent* what those strings meant; the Unreal implementation (Phase 4) would invent differently and the cross-engine integer trajectory would diverge.
- **Spec footprint:** §4.5 (computable-form requirement), §9.1 (new lint rule row).
- **Linter footprint:** `src/game_design_md/linter.py::rule_determinism_undetermined_rule` (added in this commit).
- **Implementation:** new linter rule scans each rule for bare-string `do[]` items; cross-references whether the rule is invoked from any loop with `timescale: moment`; emits `determinism-undetermined-rule` at severity `info` (advisory) for each hit.

**Headline framing.** "Turning Phase-2 archaeology into a Phase-1 automated signal is the project getting better at its own job." The standard's failure mode at v0.1.1 was that an LLM author could write `do: [resolve_unit_action, sample: "{distributions.X}"]` and the linter would happily pass it, even though `resolve_unit_action` is a free-form English phrase that two engines may interpret differently. From v0.2.0-alpha onwards the lint flag is the nudge that says "this resolution procedure isn't fully determined — a human must confirm." The lint can't *prove* a procedure is total or cross-engine-stable, but it can flag the signal at the canonical position.

**Ratchet plan:**

- **v0.2.0-alpha:** advisory (`info` severity), never affects exit code. Provides visibility.
- **v0.3:** warning. Authors must either restructure to a typed step or add a `# determinism-ok: <justification>` inline comment to silence (TBD comment syntax).
- **v0.4:** error. The current bare-string syntax becomes a hard-fail for any rule reachable from a deterministic loop.

**Out of scope for v0.2.0-alpha:** declaring the closed normative vocabulary of `do[]` step `kind:` values (e.g. `sample`, `select_target`, `apply_damage`, `gain_resource`, …). Each project defines its own vocabulary at v0.2.0-alpha; v0.3 ratchets one based on what the examples have actually used.

---

## D-012 — Distribution parameters templated from rule-evaluation context

- **Status:** decided at v0.2.0-alpha (Phase 2.5). Implemented as the optional `params_from:` field on `Distribution`.
- **Decided:** 2026-05-22.
- **Source:** `docs/v0.2-phase2-spec-ambiguities.md` #8 — `{distributions.damage_roll}` is gaussian(mean=5, stddev=1) but unit stats include `attack`; the impl had to either ignore attack (making damage uniform across unit types) or invent a relationship.
- **Spec footprint:** §4.7 (templated parameters subsection).
- **Schema footprint:** `Distribution.params_from: { type: object, additionalProperties: { type: string } }`.

`params_from:` lets a distribution declare which parameters are sourced from context (the acting unit, the target, the world tick number) rather than fixed in the YAML. Keys are parameter names of the distribution; values are `{namespace.id}`-shaped strings drawn from a context-local vocabulary the consuming rule binds. At v0.2.0-alpha the vocabulary is project-defined; v0.3 closes a normative set.

**Cross-engine implication.** Without templated parameters, every implementation would need to invent the actor-stat-to-damage mapping locally. The cross-engine bar requires this mapping in the spec.

---

## D-013 — `target_selection:` declared on rules with a closed vocabulary

- **Status:** decided at v0.2.0-alpha (Phase 2.5). Implemented as the optional `target_selection:` field on `Rule`.
- **Decided:** 2026-05-22.
- **Source:** `docs/v0.2-phase2-spec-ambiguities.md` #5 — `{rules.tick_resolution}.do[1]: resolve_unit_action` doesn't say who the target is.
- **Spec footprint:** §4.5 (new optional field).
- **Schema footprint:** `Rule.target_selection: enum [none | first_alive_opposite | lowest_hp_opposite | highest_hp_opposite | random_alive_opposite | self | explicit]`.

Target selection is a design lever, not an implementation detail. Two engines choosing different targets for the same seed produce different trajectories. The closed vocabulary captures the standard idioms; `explicit` is the escape hatch for rules that compute their target inline in a `do:` step.

---

## D-014 — Value-bearing `weighted` options (extension to category labels)

- **Status:** decided at v0.2.0-alpha (Phase 2.5). Implemented as the per-option `{ weight, value }` shape on `Distribution.type: weighted`.
- **Decided:** 2026-05-22.
- **Source:** `docs/v0.2-phase2-spec-ambiguities.md` #4 — `gold_drop.options: { small: 0.6, medium: 0.3, large: 0.1 }` returns labels, not gold; the impl had to invent values per category.
- **Spec footprint:** §4.7 (value-bearing options subsection).
- **Schema footprint:** `weighted.options.additionalProperties` becomes `oneOf: [number | { weight, value }]`.

Two shapes coexist: bare numbers (probability only, the v0.1 form) and `{ weight, value }` objects (probability + associated value). A given `options:` map is all-bare or all-objects; mixing is rejected. When values are absent and the consuming rule needs them, the resolution belongs in the spec — usually via D-014 — not invented per engine.

**Phase 2 carry-over (specific to tick-combat).** `examples/tick-combat/gdd/systems/distributions.md::gold_drop` migrated to value-bearing shape: `small: {weight: 0.6, value: 1}`, `medium: {weight: 0.3, value: 3}`, `large: {weight: 0.1, value: 10}`. The drop count per encounter is declared inline at the rule (D-013 step, not a distribution field) — `count: 6` on the gold_drop step gives expected gold ≈ 6 × 2.5 = 15, inside `balance_targets.gold_per_encounter`'s `[10, 20]` band.

