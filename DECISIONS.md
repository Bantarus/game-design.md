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

## D-002 — `broken-implementation-pointer` ratcheted to error at v0.2.0-alpha Phase 3+

- **Status:** ratcheted to **error** on 2026-05-23 (Phase 3+ hardening pass).
- **Original decision:** 2026-05-21 — held at `warning` for v0.1.1.
- **Ratchet trigger:** the planned condition ("first example ships with real source OR with a real `gdmd verify` adapter that exercises the contract") was satisfied by Phase 2 / Phase 3:
  - `examples/tick-combat/impl/xtreme/` — Bevy ECS implementation with real source (Phase 2 — bc2250f, 319dfac).
  - `examples/tick-combat/tools/verify-adapter` + `impl/xtreme/src/bin/verify_adapter.rs` — real adapter exercising the §9.5.6 contract (Phase 3 — 36e4ff5).
- **Spec footprint:** §8.2 mechanism 1; §9.1 rule table.
- **Linter footprint:** `src/game_design_md/linter.py::rule_broken_implementation_pointer` — severity flipped from `warning` to `error`.

The rule's intended severity has always been `error`: an entity claiming `status: prototyped` or higher should point at real source. With tick-combat shipping real source and the other three examples (`deckbuilder`, `party-rpg`, `tcg`) holding their entities at `status: draft`, the draft-status gate ensures the ratchet doesn't fail their lints. Confirmation: `gdmd lint examples/{deckbuilder,tick-combat,party-rpg,tcg}` returns 0 errors / 0 warnings after the ratchet.

**Forward-promotion behavior.** Any future entity in any example whose `status:` advances to `prototyped` or higher and whose `implemented_in:` paths don't resolve will now block lint with an error. This is the intended discipline — the moment a designer claims a system is prototyped, the linter verifies code exists.

**No further ratchet planned.** D-002 is closed.

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

- **Status:** decided at v0.2.0-alpha (Phase 2.5). Implemented as the optional `params_from:` field on `Distribution`. Binding moment pinned at Phase 2.5+ (2026-05-22), see "Binding moment" below.
- **Decided:** 2026-05-22.
- **Source:** `docs/v0.2-phase2-spec-ambiguities.md` #8 — `{distributions.damage_roll}` is gaussian(mean=5, stddev=1) but unit stats include `attack`; the impl had to either ignore attack (making damage uniform across unit types) or invent a relationship. Binding-moment sub-question raised by user at Phase 2.5 checkpoint and tracked as #11.
- **Spec footprint:** §3 (context-local prefixes + binding-moment paragraph), §4.7 (templated parameters subsection + apply-time clause).
- **Schema footprint:** `Distribution.params_from: { type: object, additionalProperties: { type: string } }`.

`params_from:` lets a distribution declare which parameters are sourced from context (the acting unit, the target, the world tick number) rather than fixed in the YAML. Keys are parameter names of the distribution; values are `{namespace.id}`-shaped strings drawn from a context-local vocabulary the consuming rule binds. At v0.2.0-alpha the vocabulary is project-defined; v0.3 closes a normative set.

**Cross-engine implication.** Without templated parameters, every implementation would need to invent the actor-stat-to-damage mapping locally. The cross-engine bar requires this mapping in the spec.

### Binding moment — apply-time

The original D-012 entry pinned syntax + broken-ref handling for context-local refs but was silent on *when* `{actor.<field>}` and `{target.<field>}` are read relative to other mutations in the same firing. That silence is a #5-class invisible assumption: two engines that pick different reading moments (action-start vs. apply-time) produce different integer trajectories the moment any mid-firing mutation (a buff, a debuff, a damage-over-time that scales) exists. Tick-combat's current content never triggers this — so xtreme's tick-start snapshot is silently correct and the spec gap stayed invisible through Phase 2.5. Phase 4's Unreal port (or any future tick-combat content with mid-tick mutations) would pick the other reading and the trajectory would diverge, masquerading as a spec bug.

**Decision.** Both `{actor.<field>}` and `{target.<field>}` (and any future context-local prefix) are bound at **apply-time** — read live from the world at the specific `do:` step that references them. Three consequences:

1. **Symmetric semantics.** `{actor.<field>}` is read the same way `{target.<field>}` is read. The "target HP is live so accumulated damage kills" intuition extends uniformly. There is no implicit per-firing snapshot for either.
2. **Composability.** A rule's `do:` step N may mutate `{actor.<field>}` (e.g. via a future `set_resource` step kind), and step N+1 reads the post-mutation value. This is the only binding that makes intra-firing mutations composable.
3. **Snapshot optimization permitted.** Engines MAY internally snapshot when they can prove no in-firing mutations affect the reads. Tick-combat's xtreme reads `actor.attack` from a tick-start snapshot ([`impl/xtreme/src/rules.rs`](examples/tick-combat/impl/xtreme/src/rules.rs)) because tick-combat has no mid-tick attack mutations — the snapshot is provably equivalent to a live read at the sample step. The normative contract is "produces the value of a live read"; the strategy is engine-local. When future content introduces mid-firing mutations, snapshot-based engines must refactor to live reads.

**Why apply-time and not action-start.** Action-start binding has surface appeal ("a unit's whole action uses the values it began with") but breaks symmetry with `{target.<field>}` and requires an implicit snapshot data structure in every engine. Apply-time has the simplest mental model (refs always read what's true right now), composes with mutations within a firing, and matches the semantics every existing engine uses for target-field reads.

**Out of scope at v0.2.0-alpha.** A normative escape hatch for "snapshot at action-start, use frozen values" — e.g. a `snapshot:` `do:` step kind plus a `{local.<name>}` ref pattern — is a v0.3+ concern, surfaced when actual content needs it.

**Cross-engine implication (Phase 4).** Unreal Blueprints must read `{actor.<field>}` live at each consuming step. If the Blueprint graph caches the value at action-start, the integer trajectory will diverge from xtreme's the moment a mid-firing mutation enters tick-combat's content — this is the canonical Phase-4 risk D-012 binding-moment locks down in advance.

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


---

## D-015 — PRNG pinned: xoshiro256** + splitmix64 (default), with reference vectors and per-game override

- **Status:** decided at v0.2.0-alpha Phase 4+ (2026-05-23). Resolves spec-ambiguity #12 surfaced by Phase 4 (Godot adapter against xtreme golden).
- **Decided:** 2026-05-23.
- **Spec footprint:** §4.7 (PRNG normative paragraph + reference-vector requirement + per-distribution override).
- **Schema footprint:** new `$defs.PrngSpec`; `Distribution.prng` and `Subfile.prng` reference it.

**Problem.** Spec §4.7 declared distribution *types* (`gaussian`, `uniform`, `weighted`, …) but was silent on the underlying PRNG. Phase 4's Godot adapter used Godot's built-in PCG-family `RandomNumberGenerator`; xtreme used ChaCha20 keyed by seed. Both spec-compliant; both deterministic within their engine. The cross-engine trajectory diverged at the very first sampling call. Without the spec pinning a PRNG, the D-009 cross-engine integer-trajectory bar is structurally unsatisfiable.

**Decision.** The default PRNG is **`xoshiro256_starstar` + `splitmix64` seeding**. Closed vocabulary at v0.2.0-alpha:

- `xoshiro256_starstar` (default) — Blackman & Vigna 2018. 4×u64 state, output `rotl(s1 * 5, 7) * 9`. Bit-identical-friendly: a handful of shifts/rotates/xors on u64s, no math-library dependency. Trivially portable across Rust, GDScript, and (importantly for D-008's Phase-4-Unreal aspiration) a Blueprint visual graph, where implementing ChaCha20's quarter-rounds would be miserable and error-prone.
- `chacha20` — D. J. Bernstein 2008. Per-game *override* for trees that need unpredictability (e.g. a 2-player TCG where seed prediction could become an exploit). The `prng: { algorithm: chacha20, ... }` declaration locks the choice in the spec; determinism holds regardless of which algorithm is chosen as long as it's pinned.
- `pcg32` / `pcg64` — reserved for v0.3 per-game opt-in; not the default because "PCG" is a family with multiple variants whose constants vary by library.

**Seeding.** `splitmix64` (Blackman & Vigna's reference) maps a single `u64` seed to four `u64`s that fill xoshiro256**'s state. All arithmetic is wrapping `u64`. The canonical `seed: deterministic_per_run` field on a distribution is the input to this procedure.

**Reference vector requirement (the self-validation hook).** Every `prng:` declaration MUST ship a `reference_vector:` of the first 5 raw `u64` outputs at a `canonical_seed:`. Engines self-validate against this vector at adapter startup — divergence in the vector means the engine has misimplemented the PRNG or seeding, surfacing the bug *before* any trajectory comparison runs. The vector lives in the spec, not in each adapter; an adapter that disagrees with the vector is incorrect *regardless* of whether its trajectory happens to match another engine.

**Per-game / per-distribution override.** `Subfile.prng:` declares the tree-level default. A `distributions.<id>.prng:` override lets a single distribution use a different generator (e.g. a card-shuffle distribution wants cryptographic unpredictability while damage rolls stay on the cheap pinned PRNG). The override declares the same three fields.

**Migration (tick-combat).** xtreme's ChaCha20 (`rand_chacha::ChaCha20Rng`) and Godot's PCG-family (`RandomNumberGenerator`) are both replaced by manually-implemented xoshiro256** + splitmix64 in their respective engines. The PRNG implementation is small enough (~40 LoC in Rust, ~50 LoC in GDScript) to author from scratch rather than depend on a library. The reference vector pinned in `examples/tick-combat/gdd/systems/distributions.md::prng` is verified against both engines.

**No further ratchet planned.** D-015 is closed. Future PRNG additions to the closed vocabulary (e.g. pcg64) require a new D-NNN.

---

## D-016 — Integer-native distributions for cross-engine state (deprecates float-then-round; folds spec-ambiguities #13 + #15)

- **Status:** decided at v0.2.0-alpha Phase 4+ (2026-05-23). Resolves spec-ambiguities #13 (gaussian sampling algorithm) and #15 (libm transcendental ULP drift) in one stroke.
- **Decided:** 2026-05-23.
- **Spec footprint:** §4.7 — `discrete_sum` type added; `gaussian` reserved for non-cross-engine cosmetic use; `uniform` integer-with-threshold reframed as normative for cross-engine boolean idioms; D-010's `round_mode` paragraph deprecated for state-affecting use.
- **Schema footprint:** `Distribution.type` enum adds `discrete_sum`; new conditional branch requires `samples` + `range` for `discrete_sum`.

**Problem.** The Phase-3 attempt at cross-engine integer-state determinism declared `output_domain: integer + round_mode: half_to_even` on continuous distributions (D-010). Phase 4's Godot adapter forced the deeper question: *even with the same PRNG and the same sampling method*, every float-gaussian implementation calls `log` / `exp` / `sin` / `cos` somewhere, and IEEE-754 does NOT mandate correctly-rounded transcendentals. Real libm implementations (Rust's, Godot's, MSVC's under a hypothetical Unreal port) differ in the last ULP. `round_mode: half_to_even` will eventually flip the rounded integer when a sample lands within ULP-distance of an x.5 boundary. Rare, unpredictable, exactly the "almost always deterministic" posture this project refuses.

**Decision.** For determinism-critical, integer-state-feeding randomness, use **integer-native distributions** — no continuous-then-rounded path:

- **`type: discrete_sum`** (new) — `result = (params_from.mean or 0) + sum(uniform_int(range[0], range[1]) for _ in 0..samples)`, then `clamp`. Pure integer arithmetic on the pinned PRNG's u64 outputs. By CLT, sums of uniform integers approach a gaussian; pick `samples` and `range` to land in the gameplay-feel band you want. Zero math-library dependency; bit-identical by construction across engines that agree on the pinned PRNG.
- **`type: uniform` with `output_domain: integer`** (existing, now normative for cross-engine) — `result = (rng.next_u64() mod (range[1] − range[0] + 1)) + range[0]`. Bernoulli-via-uniform idiom: pair with an integer `threshold:` and explicit `selection_rule:` (D-017).
- **`type: weighted` with integer weights** (existing, now normative for cross-engine) — D-014's value-bearing options with integer `weight:` fields. Combined with D-017's selection rule, fully integer-deterministic.

**`type: gaussian` is RESERVED for non-cross-engine, non-state-affecting use** (cosmetic jitter, presentation noise). The spec example carries a `cosmetic_jitter` distribution as the canonical safe use. `output_domain` and `round_mode` remain in the schema for backward compatibility and for these safe uses; they MUST NOT produce integer simulation state in any tree that declares cross-engine `verify_targets`.

**Why this folds #13 + #15.** #13 was "spec doesn't pin the gaussian sampling algorithm." #15 was "even with the algorithm pinned, transcendentals differ in the last ULP." Pinning `marsaglia_polar` would have resolved #13 alone and left #15 latent (the same near-x.5 boundary flip would surface eventually). Replacing the continuous gaussian with integer-native `discrete_sum` resolves both — there is no algorithm to pin because there is no continuous sampling step, and there are no transcendentals because there are no floats. The contradiction between "gaussian distribution" and "integer-deterministic cross-engine state" disappears.

**Migration (tick-combat).** `examples/tick-combat/gdd/systems/distributions.md::damage_roll` migrated from `type: gaussian + params_from.mean + round_mode: half_to_even` to `type: discrete_sum, samples: 3, range: [-1, 1], params_from.mean: {actor.attack}, clamp: [1, 99]`. Variance: 3 × (3²−1)/12 = 2; stddev ≈ √2 ≈ 1.41 (close to the original `stddev: 1` — gameplay-equivalent, golden re-locks). `critical_hit` migrated from `range: [0.0, 1.0], threshold: 0.10` to `range: [0, 9], threshold: 1, selection_rule: less_than` (1-in-10 = 10% crit). `gold_drop` migrated from float weights `{small: 0.6, medium: 0.3, large: 0.1}` to integer weights `{small: 60, medium: 30, large: 10}` with `selection_rule: declaration_order_first_above` (D-017).

**No further ratchet planned.** D-016 is closed. The legacy `output_domain + round_mode` fields remain documented in the spec as a deprecated cosmetic-only path.

---

## D-017 — `weighted.selection_rule` pinned: declaration_order_first_above

- **Status:** decided at v0.2.0-alpha Phase 4+ (2026-05-23). Resolves spec-ambiguity #14 surfaced by Phase 4.
- **Decided:** 2026-05-23.
- **Spec footprint:** §4.7 — new "Weighted selection rule" normative paragraph; `gold_drop` example updated.
- **Schema footprint:** `Distribution.selection_rule` field (string, free-form vocabulary at v0.2.0-alpha; closed by per-type interpretation in the spec).

**Problem.** `weighted.options` cumulative-sum sampling depends on (a) iteration order and (b) the comparison rule at the cumulative boundary. Phase 4 found both engines happened to agree at seed 12345 because both used insertion-order maps — but a hash-map-based engine would diverge silently, and the `>` vs `>=` boundary question is the same class as the crit `<` vs `<=` issue the spec already resolved at Phase 2.5 (#3). Two unspecified rules in one distribution type.

**Decision.** `weighted.options` MUST declare `selection_rule:`. The single normative value at v0.2.0-alpha Phase 4+ is **`declaration_order_first_above`**:

1. Compute integer total weight `W = sum(options[k].weight for k in YAML declaration order)`. Integer weights are normative for cross-engine determinism (D-016); float weights are forbidden in any tree with cross-engine `verify_targets`.
2. Draw `d = rng.next_u64() mod W`.
3. Walk options in YAML declaration order, maintaining a running cumulative sum `c`.
4. Select the **first** option whose `c > d` — **strict greater-than**.

**Strict `>` matters.** `c >= d` would shift mass at the cumulative boundary by one slot, divergent across engines that pick the other comparison. The strict-greater-than is the same discipline as #3's `sample <= threshold`: when two implementations could plausibly read the boundary differently, the spec picks.

**Why YAML declaration order is safe.** The standard's loader (`src/game_design_md/loader.py::GdmdLoader`, a `yaml.SafeLoader` subclass) preserves YAML map insertion order via Python 3.7+ dict semantics. PyYAML 5.1+ honors this. Engines reading `weighted.options` MUST iterate in the order the YAML map declares — never re-sort by key, never iterate via a hash-map. The discipline lives in the spec because the YAML itself is the canonical declaration surface.

**Per-uniform selection_rule.** The same `selection_rule:` field on `uniform` distributions carries the boolean-comparison vocabulary: `less_than`, `less_than_or_equal`, `greater_than`, `greater_than_or_equal`, `equal`. The Phase-2.5 normative `sample <= threshold` for crit (#3) is now structurally declared as `selection_rule: less_than_or_equal`; the migrated integer form in tick-combat uses `less_than` with threshold=1 (1-in-10 = 10% crit; semantically identical to the old `sample <= 0.10` on `[0.0, 1.0]`).

**No further ratchet planned.** D-017 is closed.

---

## D-018 — Reduction-layer reference vector normative (closes F-007 → spec contract; resolves spec-ambiguity #16)

- **Status:** decided at v0.2.0-alpha Phase 4++ (2026-05-23). Resolves spec-ambiguity #16 (the F-007 reduction bug as a spec gap, not a comment in `prng.gd`).
- **Decided:** 2026-05-23.
- **Spec footprint:** §4.7 — new "Uniform-int reduction is normative" paragraph + extended `uniform_int_reference_vector:` requirement on every `prng:` declaration.
- **Schema footprint:** `PrngSpec.uniform_int_reference_vector` array (multi-w entries, each with `canonical_seed`, `range`, integer `outputs`).

**Problem (the F-007 gap that the raw vector couldn't catch).** D-015 pinned the raw `u64` stream and shipped a `reference_vector:` so engines could self-validate at startup. Phase 4+'s cross-engine integer-trajectory work then surfaced a bug *one layer deeper*: GDScript's signed `int % w` on a high-bit-set raw silently gives the wrong reduction, but the engine had already passed the raw vector cleanly because the raw `u64`s were bit-identical. The divergence appeared only at trajectory tick 2 (tick 1 matched by luck — the first raw's low bits happened to be modulo-bias-friendly for the specific seed and `w` used in that sample). Without a reduction-layer contract, any future engine on a signed-int64 host (Lua, untyped JS, Blueprint visual graph, .NET under default int) would re-discover the bug at *its* tick N — exactly the "almost always deterministic" failure mode the project refuses.

**Decision.** Make the reduction layer a spec contract with three pieces:

1. **Normative reduction algorithm.** `uniform_int_inclusive(0, w-1) ≡ (rng.next_u64() as u64) mod (w as u64)`. The 32-bit-halves split is the prescribed *equivalent* form for signed-int64 hosts; naive `raw % w` and naive `((raw % w) + w) % w` are FORBIDDEN for cross-engine trees (the former gives negative results, the latter is correct only for pow-of-two `w`).
2. **Extended reference vector.** Every `prng:` declaration now ships a `uniform_int_reference_vector:` with at least **two entries**: one power-of-two `w` (validates the reduction itself, bias-free) and one non-power-of-two `w` (validates the engine handles `(2^64 mod w) ≠ 0` correctly — the bit that catches the naive-corrected form). At least one entry's draw #1 MUST be adversarial — chosen so a wrong reduction fails at startup, not at tick N.
3. **Engine self-validation contract.** Both the raw and reduction vectors are checked at adapter startup before any simulation work. An engine that disagrees with either vector is incorrect *regardless* of whether its trajectory happens to match.

**Why two w's and not one.** A single `w` can match by coincidence — exactly what happened in Phase 4+'s pre-fix Godot at tick 1. The pair `(pow-of-two w, non-pow-of-two w)` narrows the diagnosis:

- A no-correction-at-all impl fails on both.
- A naive-corrected impl (the `((raw % w) + w) % w` form that many programmers reach for) passes pow-of-two but **fails non-pow-of-two**, because `2^64 mod w = 0` only when `w` divides `2^64`.
- A correct 32-half-split impl passes both.

The non-pow-of-two entry is what makes the vector load-bearing.

**Why adversarial draw #1.** Phase 4+'s bug survived to tick 2 because draw #1 matched by luck. The reference vector's job is to remove that luck — if the first PRNG output has the high bit set AND the reduction would differ between the correct and naive forms for that specific `(raw, w)`, then any wrong implementation fails at adapter startup. The chosen `canonical_seed: 0` for tick-combat satisfies this: first raw is `0x860bfe4fec669882` (high bit set); `u64 % 7 = 1` vs naive-corrected = 6 vs no-correction = -1. Three distinguishable answers on draw #1.

**Modulo bias accepted at v0.2.0-alpha.** `next_u64() mod w` is slightly biased for non-pow-of-two `w` (the bias is `2^64 mod w` extra mass on the first `2^64 mod w` integers). For small `w` (the tick-combat ranges: `w ≤ 100`, plus the values declared in `weighted.options` summing to 100) the bias is negligible — `2^64 / 100 ≈ 1.84e17`, so the bias per option is `< 6e-18`. Unbiased reduction (Lemire 2019 multiply-shift; rejection sampling) becomes spec-relevant only when a distribution declares a `w` large enough for the bias to matter; at that point reduction algorithm becomes a per-distribution field. Not yet.

**Same-author-twice caveat (recorded in F-007 alongside this decision).** D-018 closes the spec-contract gap that F-007 named. It does NOT close the parallel rigor caveat — both engine A (xtreme) and engine B (Godot) were implemented by the same agent reading the same spec; shared interpretive blind spots survive both. A third-party implementation from spec alone remains the next rigor tier. The benefit of D-018: a future third-party implementer hits the reduction-layer self-check at adapter startup and fails fast on exactly the class of bug that took two engines to surface here.

**Migration (tick-combat).** `examples/tick-combat/gdd/systems/distributions.md::prng` gains a `uniform_int_reference_vector:` block with two entries at `canonical_seed: 0`: `range: [0, 7]` (pow-of-two, outputs `[2, 0, 1, 1, 7, 2, 5, 6]`) and `range: [0, 6]` (non-pow-of-two, outputs `[1, 1, 5, 6, 1, 5, 0, 3]`). Both engines compile the table into a static const + a self-check function called from `Simulation::new()` immediately after `reference_vector_self_check()`. The golden trajectory does NOT change (both engines were already producing correct reductions — D-018 codifies what was correct, not what was broken).

**No further ratchet planned.** D-018 is closed. The reduction-layer field is structurally required on every `prng:` declaration at v0.2.0-alpha; a future `Distribution.reduction:` opt-out for unbiased reductions would be a new D-NNN, not a backwards step here.

---

## D-019 — Per-instance addressing DSL (F-008 v0.3 binding semantics)

- **Status:** shipped at v0.3 (2026-05-28).
- **Decided:** 2026-05-28.
- **Spec:** §3 (context-local prefix binding for instance_container); §4.1 (instance_container entity type); §4.5 (per-instance addressing for rules); §9.1 lint rule `write-to-template-field`.
- **Implementation:** schema additions for `instance_container` + `per_instance_state`; linter rule `rule_write_to_template_field` in `src/game_design_md/linter.py`.
- **Tests:** `tests/test_lint.py::test_write_to_per_instance_state_is_silent`, `::test_write_to_template_field_fires_on_undeclared_field`, `::test_write_to_template_field_silent_without_instance_containers`.
- **Commits:** `f2572cc` (DSL lock) + `8eee42b` (lint addendum) + `c13bc59` (tick-combat retro-touch + verify-adapter PASS).

D-019 specifies the binding semantics of existing context-local refs (`{actor.<field>}` / `{target.<field>}`, D-012) against the new `instance_container` entity type. The addressing "DSL" required NO new syntax — only normative lookup order and write restriction on existing vocabulary. Closes F-008.

**Read lookup order:** `per_instance_state` → template (via `holds_template_from`) → container properties, first-match. Reading template-layer fields is normal (e.g., reading `actor.attack` from the template's immutable schema).

**Write restriction:** writes mutate `per_instance_state` fields ONLY. A do[] step declaring `field: <name>` where `<name>` is not declared in any instance_container's `per_instance_state` is a spec violation: templates (content_collection entries) are immutable per §6, container properties are likewise read-only. State-machine transitions on the instance fire via the same per_instance_state binding (e.g., `{target.lifecycle}` transitions via the `unit_lifecycle` machine — `lifecycle` MUST be in per_instance_state for the transition to be a legal write).

**Lint:** `write-to-template-field` (severity error) fires on do[] steps declaring `field: <name>` outside per_instance_state. Opt-in (only fires when the step declares `field:`); declared-`field:` becomes required on mutation steps in a v0.4 ratchet.

**Validated against verify-adapter on tick-combat (step 4 commit c13bc59):** trajectory byte-identical to golden seed=12345, negative_control seed=99999 diverges, build_health green. The cross-engine determinism gate confirms F-008's full closure (base shape + addressing DSL + write restriction) preserves the cross-engine trajectory contract.

**Descriptive-not-prescriptive (see memory `descriptive-not-prescriptive-vocabulary-extensions`).** The verify-adapter PASS was expected because the new vocab DESCRIBES existing engine reality (xtreme's ECS components already carry per-instance `hp` / `lifecycle`; the spec just hadn't had words for what was there). No engine refactor required.

**No further ratchet at v0.3.** Required-`field:` on mutation steps is a v0.4 concern.

---

## D-020 — Status lifecycle vocabulary expansion: `experimental` + `deferred` (v0.3)

- **Status:** shipped at v0.3 (2026-05-28).
- **Decided:** 2026-05-28.
- **Spec:** §8.1 (Status values + transition graph); `$defs.Status` in `schema/game-design.schema.json`.
- **Implementation:** schema enum extension; `STATUS_LEVELS` in `src/game_design_md/linter.py` extended (`experimental`: 1 = prototyped-equivalent for staleness; `deferred`: -1 = cut-equivalent).

**Evidence base (in-repo observed use).** A scan of `status:` declarations + prose markers across the 6 trees (4 canonical examples + 2 benchmark games) found:

- `experimental` declared in PROSE across 4 trees' `verification.md` files (`examples/deckbuilder`, `examples/tcg`, `examples/party-rpg`, `examples/tick-combat`). Each says **"Status: experimental"** because the canonical 5-state forward vocab (draft / prototyped / implemented / balanced / shipped) couldn't express "code or contract exists, design under evaluation, may revert."
- `deferred` used in PROSE for time-deferral in 2 places (`examples/deckbuilder/gdd/glossary.md` "Ascension ... deferred to v0.5", `examples/deckbuilder/gdd/systems/progression.md` "Difficulty ascensions ... deferred to v0.5").
- 240 declarations at `draft`, 7 at `prototyped` (all `tick-combat` with real impl), 0 at higher states or at `cut`. Most canonical examples haven't reached impl yet — the lifecycle is mostly aspirational for them.
- `blocked` and other candidate vocabulary terms NOT observed in any tree.

**Decision-of-record.** Add `experimental` and `deferred` to the canonical status vocab in v0.3; defer `blocked` until observed-use surfaces it. The closed-vocabulary-by-observed-need discipline (D-015 PRNG enum, D-017 weighted selection_rule, F-010 clocks mode, D-019 addressing DSL) applies: in-repo evidence is sufficient observed use to justify expansion in v0.3 — the canonical examples already need vocabulary the v0.2 surface couldn't express. Deployment-sweep evidence (live projects) would extend the evidence base; in-repo evidence is already clear enough to ship.

**Lifecycle additions:**

- `experimental` (lateral): entered from any non-terminal state; exits back to prior state OR to `cut`. Treated as level 1 (prototyped-equivalent) for `implemented_in:` staleness — implementation must exist.
- `deferred` (lateral): entered from any state; lifecycle paused; exits back to prior state. Treated as level -1 (cut-equivalent) for `implemented_in:` staleness — code is not required while deferred.

**Transition graph refinement.** Non-adjacent backward jumps along the canonical path (e.g., `shipped → prototyped`) now require an explicit intermediate: either route through `cut` and re-`draft` (the prior design is abandoned, starting over) OR route through `experimental` (the work exists but is under re-evaluation). `gdmd diff` catches the multi-step backward case via the existing `status-regression` finding; the new intermediate options give the author a semantically richer way to communicate intent.

**No new lint rule at v0.3.** Lifecycle transitions are a `gdmd diff` concern (it has a baseline; `lint` doesn't). Anti-staleness lint that builds on the new states (e.g., a `deferred` section deferred for more than 90 days; an `experimental` section whose status hasn't advanced in 60 days) is a Task 6 concern in the v0.3 docket.

**In-repo retro-touch (this commit):** the 3 verification.md files whose prose says the WHOLE file is experimental (`deckbuilder`, `tcg`, `party-rpg`) have their frontmatter `status:` updated from `draft` to `experimental`. The `tick-combat` verification.md is NOT updated (its prose flags specific verify_targets as experimental, not the whole file). The "deferred to v0.5" prose mentions in deckbuilder reference design features (ascensions) that don't have token entries; no frontmatter to update.

**Deferred to deployment sweep:** the `blocked` vocabulary addition pending observed use in live projects. If a future live adoption surfaces a "waiting on a dependency" marking need the current vocab can't express, add it via a future ratchet decision. (D-020 references to "Xenogrid / Mirrorbind / Rêverie" predated D-021's premise correction — those names were placeholders for live projects that don't have spec trees yet. The principle stands; the namelist doesn't.)

---

## D-021 — v0.3 deployment-surface reframe: premise-correction, not gate-loosening

- **Status:** shipped at v0.3 (2026-05-28).
- **Decided:** 2026-05-28.
- **Spec:** §11.2 (v0.3 scope and validation surface).
- **Implementation:** scoping text in §11.2 names the three v0.3-validated claims and the one v0.4+-queued claim; D-020 amended with a forward-pointer to this decision noting the deployment-sweep namelist was a placeholder.

The v0.3 kickoff set "at least one live project" as the validation bar — the working assumption being that Xenogrid / Mirrorbind / Rêverie had spec trees the v0.3 vocabulary would be deployed into. Mid-development, the user clarified those projects don't have spec trees: they were placeholder names for future live adoption, not extant validation targets. The bar was set against a factual premise that wasn't true.

**Decision-of-record.** Correcting the premise necessarily changes what the bar can mean. The restatement is **gate correction, not gate loosening**: the same discipline-pattern as the Phase 5 v12-D constraint-driven scope reduction (pre-reg commit `2b5d9a6`), with a different cause shape — there a logistical/feasibility constraint fired AS DESIGNED on a working gate; here a factual claim about project state turned out to be false and the bar simply couldn't be operationalized as written. Both are legitimate scope-reductions distinct from result-driven gate loosening (the counterfactual-adoption test). Neither sister discipline has a standalone DECISIONS.md entry — both are recorded as operational disciplines in commit lineage + methodology framing ([`docs/methodology/README.md`](docs/methodology/README.md)); D-021 is the first reframe of this family to rise to decision-of-record because it changes the spec's stated validation surface.

The corrected scoping (§11.2):

**Validated at v0.3 from in-repo evidence:**
1. **Vocabulary closure** — the closed-vocabulary additions (`{clocks.<id>}`, `instance_container`, addressing DSL, status lifecycle additions) are expressible on real spec content across the 6 in-repo trees without local invention.
2. **Cross-engine determinism preserved** — tick-combat's `gdmd verify` adapter gate stays byte-identical to v0.2 golden after F-008 + F-010 land.
3. **Session-level maintenance** — the agent performs the anti-drift ritual end-to-end on the in-repo trees when actively prompted.

**Queued for v0.4+ pending live adoption:**
- **Longitudinal living-doc property** — the doc stays current across weeks/months of game development without continuous human review. The 6 in-repo trees can't validate this claim; they are spec-illustrations and benchmark targets (mostly `draft`, see `gdmd status`), not games-in-development. This is a *scope statement*, not a failure: v0.3 ships the vocabulary and apparatus the longitudinal property would test; the test itself awaits the first live adopter.

**Why the distinction matters.** A future reader seeing "v0.3 validated on 6 in-repo trees" should be able to trace WHY that's the validation surface rather than wondering if the bar was quietly lowered. The premise-correction discipline:

- **Premise-genuine** — is the factual correction objectively verifiable? Yes here: the named projects don't have spec trees in this repo (or anywhere we can see).
- **Re-scoping-honest** — does the restatement carry the original ambition forward AS A NAMED LIMITATION, not silently swapped for weaker evidence? Yes: longitudinal claim is explicitly queued for v0.4+, named in §11.2 and in this decision, distinguished at the integrity bar from the three claims the in-repo surface does carry.
- **Audit lineage preserved** — the premise correction is recorded in DECISIONS.md (this entry) and surfaced in the spec text (§11.2). The lineage from the kickoff's bar through the corrected bar is reconstructible.

D-020's reference to specific deployment-sweep project names is now read as a placeholder list, not an extant validation target. The minimum-vocab discipline that governed `blocked`'s deferral (vocabulary grows by observed use) is unchanged; the trigger condition (a live project surfaces a need the current vocab can't express) is unchanged; only the assumed-imminence of that trigger is corrected.

**Related disciplines.**

- [[gate-correction-vs-gate-loosening]] (memory): the counterfactual-adoption test for result-driven gate widening. Doesn't fire here — there was no result this premise-correction is dodging; the bar simply couldn't be operationalized as written.
- [[constraint-driven-scope-reduction-vs-result-driven-gate-loosening]] (memory): the sister discipline for logistical constraints. Same family as D-021, different cause shape.
- [[premise-correction-reframe-is-gate-correction]] (memory, this session): the discipline named.

**No vocabulary changes at v0.3.** D-021 is a scoping decision that records the validation-surface reframe; it adds no schema, no lint rule, no spec syntax. The associated spec-text change (§11.2) is documentation of what v0.3 ships under, not a vocabulary extension. A future v0.4+ validation surface will be governed by what the first live adopter actually surfaces.

---

## D-022 — F-009 is not analyzable for consultation cost; the v0.4 kickoff's reading of F-009 is corrected

- **Status:** locked (2026-09-30).
- **Decided:** 2026-09-30, at v0.4 Checkpoint 1 (WS1 of the v0.4 kickoff).
- **Spec:** no change. **Code:** no change.
- **Evidence:** harness source at trial-zero commit `37c004d`: `benchmark/harness/instrument.py` (`QwenInstrument.complete`), `benchmark/harness/conditions.py` (`build_a` / `build_b`), and the pre-registration's §"Cost metric". It is **not** based on trace values; see "Provenance" below.

The v0.4 kickoff motivated a consultation-layer fix (`gdmd view`) with the reading "agents open whole files, and F-009 measured roughly +37% tokens per session against flattened prose". WS1 was to find where the +37% went, testing four hypotheses:
- full `gdmd spec` injection;
- whole-file reads;
- re-reads;
- reads of task-irrelevant files.

The method was to compile F-009's traces into VCC views.

**What the F-009 apparatus actually was.** Each fact below comes from the harness code at `37c004d`:

1. **Single-turn chat completion, no tools.** `QwenInstrument.complete()` sends one system and one user message to `llama-server` and sets `tool_steps=0` by construction ("llama.cpp serves chat-completions; no tool round-trips"). The subject never read a file: there were no reads, no re-reads, and no consultation choices.
2. **Fixed whole-tree payload.** The payloads were:
   - **Condition A:** `AGENTS.md` + `CLAUDE.md` + every file of the game tree, concatenated with file markers, regardless of task.
   - **Condition B:** the flattener's prose over the game tree only.

   `docs/spec.md` was never in any payload. `CLAUDE.md`'s `@docs/spec.md` line reached the subject as literal text, because `@`-import expansion is a Claude Code feature and the harness does not perform it.
3. **Prompt text is not stored.** Gather records hold `subject_output`, `tokens_input`, `tokens_output`, `payload_sha256` and pairing ids, but not the prompt.
4. **Cost-lift is total tokens.** It is `mean(tokens_in + tokens_out | A) / mean(… | B) − 1`.

**Consequences.**

- F-009's 37.1% cost-lift is payload size plus response length under a fixed, harness-built payload. It is **not** a measurement of consultation behavior.
- Of the four kickoff hypotheses:
  - spec injection is zero by construction;
  - whole-file reads and re-reads cannot occur without tools;
  - "task-irrelevant files" has only a structural analog. The harness shipped the whole tree for every task, which is a property of payload construction, not of an agent's choices.
- VCC cannot help. Upstream VCC compiles Claude Code JSONL; a one-prompt, one-response record has no block structure to project; and the prompt isn't stored.

**Decision-of-record (user, Checkpoint 1).** F-009 is recorded as **not analyzable under current tooling** for consultation questions. There is no pre-registration, no trace analysis, no VCC adapter, and no re-run; D-023 retires the Qwen protocol and forbids re-running it.

A deterministic token-accounting analysis was offered and declined. It would have rebuilt the payloads from git at `37c004d`, verified them against `payload_sha256`, and attributed A−B tokens to segments. It needs no model inference and remains available if a future question needs it.

**What this does NOT change.** F-009's finding, numbers, caveats and D-021 reframe stand exactly as recorded in [`docs/case-studies/F-009.md`](docs/case-studies/F-009.md) and [`docs/v0.2-findings.md`](docs/v0.2-findings.md). This entry corrects a *downstream reading* of F-009 (the v0.4 kickoff's). It does not reinterpret F-009.

**Consequences for v0.4.**
- F-009 neither motivates nor evaluates `gdmd view`. The consultation question ("where do an agent's tokens go when it works on a tree?") is carried forward to the dogfood harness (D-023), which produces agentic Claude Code traces VCC compiles natively.
- Any claim that views reduce session cost needs a new pre-registered rule on that harness (D-025) before it is stated anywhere.
- The WS4 trigger depended on WS1 and can no longer be satisfied as written. It is corrected separately in D-024.

**Premise-correction diagnostic** (D-021 family):
- **Premise-genuine:** yes. The facts are checkable in the harness source at the trial-zero commit.
- **Re-scoping-honest:** yes. The original question is re-homed on an apparatus that can answer it, not dropped.
- **Audit lineage preserved:** this entry plus [`docs/case-studies/F-009-trace-analysis.md`](docs/case-studies/F-009-trace-analysis.md).

**Provenance.** The correction was made before any dogfood evidence existed, and without computing anything on F-009 trace values. During orientation only field names and string lengths of one gather record were inspected. The two aggregates cited in the note, the 37.1% cost-lift and the 1.88× output ratio, were already published in the F-009 case study.

---

## D-023 — Dogfood harness replaces the Qwen help-benchmark as the routine evidence surface; the Qwen harness is archived

- **Status:** locked (2026-09-30).
- **Decided:** 2026-09-30, v0.4 Annex A.0, written before any dogfood harness code existed.
- **Spec:** §11.3 (new).
- **Implementation:**
  - Qwen harness moved to `benchmark/archived/phase5_qwen/`; provenance in `benchmark/archived/README.md`.
  - Dogfood harness at `benchmark/dogfood/` (subsequent commits).

**Why the protocol changes.**

1. **Cost and repeatability.**
   - *Phase 5 protocol:* a local 30B subject server, a separate judge model, a sanitizer with its own calibration chain, 330 trials, and a 16-version pre-registration supersession chain. A single cell could not be re-run cheaply.
   - *Dogfood:* 4–6 fixed tasks with deterministic checkers (no LLM judge), a small number of repeats per cell, and a CLI (`--task`, `--arm`, `--repeats`) to re-run one cell. It never runs in CI.
2. **The right trace shape for the open question.** D-022 moved the consultation question ("where do an agent's tokens go?") off F-009 because single-shot records cannot answer it. Headless Claude Code sessions produce session JSONL with every tool call, which VCC compiles natively into full / adaptive / transposed views. No adapter is needed.
3. **It exercises the operating reality.** The subject works on this repo's trees through the tool loop a real agent uses (reads, greps, `gdmd` commands) instead of receiving a harness-built payload.

**Subject.**
- `claude-sonnet-5-5` (Claude Sonnet 5.5), run headless (`claude -p`), is the subject under test only. Orchestration, checking and analysis subagents use Opus.
- The session that wrote this entry could not see the model id; the user confirmed that it exists. Per the recency-facts discipline, the id is still gated: the pilot's first real call is a one-call model-id probe that stops on failure.

**What dogfood does NOT claim.**
- **Not comparable to F-009.** The model (Sonnet 5.5 vs Qwen3-Coder-30B-A3B), harness (agentic tool loop vs single chat completion), tasks (in-repo authoring/lookup/operating/maintenance vs fresh-game implementation) and primary metrics all differ. No dogfood number is to be placed beside an F-009 number as a comparison, and no dogfood run is an "F-009 re-run".
- **F-009 stays on record as reported,** not reinterpreted. D-022 corrects only the v0.4 kickoff's downstream reading of it.
- **Its limits are named in every report:**
  - small n (the default is 3 repeats per cell);
  - a single model;
  - tasks designed by the format's author on the format's own trees.
- **Not longitudinal.** It does not test the longitudinal living-doc property, which stays queued (§11.2).

**What happens to the Qwen harness: archived, not deleted** (the archive-not-delete discipline).
- **Move:** `benchmark/{harness,tools,tasks,c-prompts,README.md}` moved byte-preserving to `benchmark/archived/phase5_qwen/`.
- **SHAs verified:** the pinned sanitizer (`e85c123f227d225a…`) and flattener (`54ef5ba3…`) hash identically at the new paths and at trial zero (`37c004d`).
- **Pre-registration left unedited:** `docs/v0.2-phase5-pre-registration.md` is locked, so its path citations stay as-is. The archive README maps old paths to new ones. `docs/v0.2-findings.md` received path-only link fixes.
- **Not runnable in place; fails loudly:** the drivers fail at import and `conditions.build_a` raises "Game tree not found". Faithful re-execution needs a `37c004d` checkout, with the original layout and original game trees.
- **Never re-run Qwen** (Annex A).
- **Tests keep running:** the three pure-logic test modules (sweep planning, checklist wiring, instrument/judge wiring with mocks) still run from the new import path, to guard against import rot. They make no model calls.
- **Games stay:** `benchmark/games/{platformer,survival}` are live lint trees and `gdmd init` starter sources.

**Methodology carried over from Phase 5** (made concrete in D-024 and D-025):
- A **locked rule** is written before the first real run. It states primaries per comparison, verdict mapping (PASS / NULL / FAIL) and stopping and reporting rules, and results are reported by the rule. No post-hoc metric switching.
- **Pilot first.** One baseline-arm run per task validates checkers, isolation and metric extraction, and estimates the full-matrix cost. Pilot results are not evidence and are never reported as such; there is a stop for approval before the full matrix.
- **Checkers are deterministic.** Each has a test showing it fails on a known-bad fixture. The lookup-task oracle is a frozen, hand-verified fixture, not computed at check time by code the views arm is built on.
- **Arms are isolated and identical except for the arm file.** Each run gets a fresh isolated copy, with the same `CLAUDE.md`, fixture and task text across arms. The spec import is held constant in the views-vs-baseline comparison.

**Counterfactual-adoption test.** Would the Qwen protocol be retired if F-009 had PASSED? **Yes.** The switch is driven by the question and not by the result: consultation cost cannot be observed in tool-less single completions whatever they score, and the cost and repeatability problem is independent of F-009's verdict. The switch leaves F-009's verdict and numbers untouched.

---

## D-024 — WS4 (compact agent card) gate: premise correction; build separated from adoption

- **Status:** locked (2026-09-30). Written before any dogfood run exists.
- **Adopted (2026-09-30), on D-025 Rule C PASS** (`rulec-20260930`: D = 46,769 ≥ 0.5 × Δ = 26,326, non-inferiority held).
  - The repository's `CLAUDE.md` now imports `@docs/spec-card.md` in place of `@docs/spec.md`, the exact one-line swap the ablation tested.
  - `docs/spec-card.md` is committed byte-identical to the tested card (SHA-256 `7c280fa1…a99f`). A pytest drift test and an AGENTS.md step keep it equal to `gdmd spec --card` after spec edits.
  - `docs/spec.md` remains the authoritative text, reachable through `gdmd spec --section`.
  - Reversible: D-026's C2 re-tests it, and a C2 FAIL reverts it. Study 2's copies force the full import where their cells need it (`fixture.force_spec_import`).
- **Decided:** 2026-09-30, v0.4 Checkpoint 1. The user's revised WS4 text, amended at plan approval.
- **Spec:** none yet. `gdmd spec --card` / `--section` get spec text when they are built (§9.4).
- **Related:** D-022 (why the original trigger is unsatisfiable), D-023 (dogfood protocol), D-025 (locked rules, including this ablation's numeric bounds).

**Premise correction.**
- The kickoff's WS4 trigger read "WS1 shows spec injection is a major cost driver". It cannot fire: F-009 never injected the spec (D-022).
- The concern is real but lives elsewhere. This repo's `CLAUDE.md` `@`-imports `docs/spec.md` (~121 KB, roughly 30k tokens) into every Claude Code session, and so into every dogfood run.
- The gate is re-pointed to dogfood evidence **before any dogfood evidence exists**. Premise-genuine (checkable in harness source and in `CLAUDE.md`), re-scoping-honest (the question is kept and moved to an apparatus that can see it), lineage preserved (this entry). It is not a loosening: no result exists to dodge.

**1. Build (ungated, cheap).** Building is not the decision that needs evidence; adoption is.
- `gdmd spec --card` emits a short agent-facing digest **generated from the spec's own structure**, never hand-written. It covers the namespace → owning-file table (§3), reference syntax (§3), the status lifecycle (§8.1), the maintenance ritual (§8.2 mechanism 4), and pointers to `gdmd view` and `gdmd graph` (WS2).
- `gdmd spec --section <§id>` returns the full normative text of one numbered section on demand.
- **Completeness test.** Every sentence in `docs/spec.md` carrying an uppercase RFC-2119 keyword (`MUST`, `MUST NOT`, `REQUIRED`, `SHALL`, `SHALL NOT`) is either in the card or inside a section the card lists a `--section` pointer to.
- **Stated limitation.** Lowercase normative "must" / "required" (common in the spec's tables) is not machine-identifiable, so the test does not cover it.
- **Timing.** Built after WS2, because the card points at `view` / `graph`.

**2. Precondition (a go/no-go pre-flight read on the pilot, not evidence).**
- **Measurand:** the share of per-turn context occupancy attributable to the `spec.md` import, in the baseline-arm pilot traces.
- **Threshold, locked here:** the share is ≥ **20%** of the median per-turn occupancy. Below that, record NULL and do not run the ablation.
- **Per-turn context occupancy** = `input_tokens + cache_creation_input_tokens + cache_read_input_tokens` of one API call. A "turn" is one assistant `message.id`; records sharing an id are deduplicated.
  - This refines the user's "input + cache_read". Without `cache_creation`, the first turn and every cache-miss turn undercount the prompt the model actually sees.
  - The import mostly lands in the cached prefix, which is why occupancy (the context burden) and not dollars is the right primary here.
- **Import size** comes from a **2-call differential probe that isolates `spec.md` alone**. Two isolated copies are identical except that one drops only the `@docs/spec.md` line from `CLAUDE.md`; the schema, `AGENTS.md` and deckbuilder-root imports stay in both. Each gets one trivial single-turn prompt, and import tokens = occupancy(with) − occupancy(without).
  - The probe is needed because imported `CLAUDE.md` content is injected context and is not reliably present as text in session JSONL.
- **Status of the read.** Annex A.5 says pilot results are not evidence. The precondition does not contradict that: it is a **pre-registered pre-flight read** deciding whether to spend on the ablation (the Phase 5 step 11b precedent). It is reported as a gating read, never as evidence for a claim.

**3. Adoption gate (a dogfood ablation under a locked rule).**
- **Cells:** `import-full` (status quo) vs `import-card`. The swap replaces **only** the `@docs/spec.md` line with an `@`-import of the generated card, and `--section` is available on demand. Schema, `AGENTS.md` and deckbuilder-root imports stay identical in both cells, so the ablation is not confounded. The swap happens inside each isolated copy, never in the repo.
- **Task set:** the Annex A.2 set, including the negative-control task, on the **baseline tool arm only**. The ablation is not crossed with `view` (a factorial crossing only if the pilot budget allows it, decided at the pilot-cost checkpoint).
- **Primary:** median per-turn context occupancy (definition above).
- **Secondaries:** estimated USD cost, and the `--section` call rate (a high rate means the card is missing things).
- **Non-inferiority:** the success rate may not drop by more than Y points overall, and there may be **no** drop on the maintenance and negative-control tasks, which are the tasks where a missing normative rule would show. X/Y and the verdict mapping are locked in D-025.
- **PASS:** switch the repo's `CLAUDE.md` from `@docs/spec.md` to the card. **NULL or FAIL:** keep the full import and record the result.
- **Starters:** `templates/starters/*` carry no `CLAUDE.md`, `AGENTS.md` or spec import today, so the adoption has nothing to switch there. Whether `gdmd init` should scaffold an agent file importing the card is a separate question that needs observed need; it is not part of this gate.

**4. Amendment to Annex A.2 / A.4 (views vs baseline).** The views comparison holds the spec import constant, with the full import in both arms. Otherwise the view effect and the import effect are confounded. Its primary is consultation tokens (tool-result tokens/bytes), not occupancy; D-025 states the two primaries separately and neither definition carries over into the other lock.

---

## D-025 — Dogfood locked rules: views vs baseline (Rule V) and the card-import ablation (Rule C)

- **Status:** locked (2026-09-30). Committed **before the pilot**, so no threshold can be calibrated on pilot numbers. The draft was reviewed at the combined Checkpoint 2 / Annex checkpoint A, and the review's ten amendments are incorporated below.
- **Scope:** two independent rules.
  - **Rule V** evaluates the WS2 claim "projected views reduce consultation cost without hurting success".
  - **Rule C** is the D-024 adoption gate for the compact agent card.

  They share the apparatus but **no metric definition**. Each rule has its own primary, and neither definition carries over into the other.
- **Related:** D-023 (protocol), D-024 (card gate; its 20% precondition is locked there), spec §11.3, OI-005 / OI-006.

### Shared apparatus (the pinned bundle)

- **Subject:** `claude-sonnet-5-5` via headless Claude Code, `--effort high`.
- **CLI (pinned):**
  - Version `2.1.285`, as a native binary copied outside the installer's reach (`run.py::CLAUDE_BIN`), SHA-256 `33dad1ec…b233d29` (`run.py::CLAUDE_PIN_SHA256`). `run.py` refuses to run on a SHA or version mismatch.
  - Sessions run with `DISABLE_AUTOUPDATER=1`. Each cell re-checks `--version` against the run's first value and stops the run on a change.
  - `claude --version` is recorded on every result line.
  - Why: the CLI auto-updated from 2.1.280 to 2.1.285 during the session that drafted this entry.
- **Worlds (the arms differ in the tooling-and-instructions layer):**
  - **`baseline` = the v0.3 world.**
    - `CLAUDE.md`, `AGENTS.md`, `docs/spec.md`, `schema/`, `src/` and `pyproject.toml` come from tag `v0.3.0` (`fixture.V03_OVERLAY`).
    - `gdmd` is a separate venv installed from the tag. `fixture.verify_v03_venv` checks it byte-for-byte against the tag's `src/game_design_md` plus the two force-included data files.
  - **`views` = the matrix-commit world**, with `gdmd` running the copy's own `src/`.
  - **Everything else, including every task tree, comes from the matrix commit in both arms,** so task content is identical by construction.
  - Why more than `gdmd` and `spec.md` are overlaid: a "v0.3" copy with v0.4 `src/` or v0.4 workflow docs would let the baseline read or run v0.4 tooling.
  - The spec-import size difference between the worlds is recorded: bytes per copy, and tokens from the import probe run in both worlds. It does not enter Rule V's primary (consultation bytes). At `3f035cf` the difference is 121,539 vs 122,948 bytes (§11.3); it grows with WS2's §9.9.
- **The judge:**
  - Checkers never use the arm's own `gdmd`. The judge is the matrix commit's `src/`, exported once per run (`fixture.make_judge`, `$DOGFOOD_GDMD`).
  - The preflight refuses a copy if the arm's `gdmd` and the judge lint the untouched fixture differently, before or after the fixture patch.
  - Residual: a lint rule added after `v0.3.0` could judge a subject's *new* content differently from what the baseline subject could see. OI-005 / OI-006 rules are scheduled after Checkpoint 3; if one lands before the Rule V matrix, this is reported as a limit.
- **One commit per matrix.** Every copy in a run is exported from the commit pinned when the run starts. A real run refuses to start if the harness (`benchmark/dogfood/`, `tests/test_dogfood.py`, results excepted) has uncommitted changes. That commit's SHA, the overlay SHA and the judge SHA are on every line.
- **Flags and isolation:** exactly `run.py::session_argv` at the lock commit (**amended before the pilot: see Amendment 1**, which replaces `--restricted`):
  - `--restricted`;
  - `--tools Read,Grep,Glob,Edit,Write,Bash`, with the Bash allowlist in `run.py::ALLOWED_BASH`;
  - `--permission-mode acceptEdits`, `--strict-mcp-config`, `--disable-slash-commands`;
  - a stream-json session with a pinned `--session-id`;
  - a per-run isolated copy (`fixture.py`), with the task prompt on stdin and the arm text via `--append-system-prompt`.
- **Tasks:** the five in `benchmark/dogfood/tasks/tasks.yaml` at the lock commit.
  - The operating task states its intended end state explicitly (review item 8, commit `3f035cf`).
  - The maintenance fixture's Rust refactor was compile-checked once (review item 9): in a scratch export with the patch applied, `cargo check --offline --all-targets` and `cargo test --offline` pass, all 7 tests including `golden_trajectory_seed_12345`. So the teammate's change really preserves behavior.
- **Repeats:** **3 per cell.** This is small and says so: results are descriptive, and no significance test is claimed.
- **Caps:**
  - A turn cap of 60 (enforced by the harness on the stream), 1200 s of wall-clock, and `--max-budget-usd 3.00` per run.
  - They are **identical across arms and rules**.
  - A cap may be raised **at most once, only upward**, after the pilot and only if the pilot shows it binding. The change is recorded as an amendment to this entry before any full matrix runs.
- **Outcomes:** every run is exactly one of four (`run.py::classify`).
  - `success`: the session completed and the checker passed.
  - `fail`: the session completed and the checker failed.
  - `capped`: the turn cap, the timeout or the budget cap ended the session. **It counts as not-success.** Capped runs are never retried or excluded, because a cap binding can depend on the arm.
  - `error`: an apparatus failure, meaning no result event, a CLI error other than the budget cap, no session JSONL, or a checker that emitted no report.
- **Error handling:**
  - An `error` cell is re-run **once**, after a harness fix is committed if the cause is in the harness. The original line is kept unchanged. The re-run's line records `supersedes: <run_id>/<cell_id>` (`run.py --supersedes`).
  - A second `error` counts as not-success.
  - If more than 10% of a rule's runs end in `error` after re-runs, that rule's verdict is **NULL (apparatus)**.
- **Contamination:**
  - A run that reads anything under the real repository's `benchmark/dogfood/` or `tests/test_dogfood.py` (as `out_of_copy_access` reports) counts as not-success and is listed.
  - If more than 10% of the runs in any arm are contaminated, that rule's verdict is **NULL (apparatus)**.
  - Other out-of-copy reads, such as the v0.3 venv behind the baseline shim, are listed but not penalized.
- **Logs:**
  - Session JSONLs, stderr and VCC views are gitignored. Each result line carries its session's SHA-256.
  - After each run they are compressed to `~/.local/share/gdmd-dogfood/archive/<run_id>.tar.xz`, outside the repo.
  - Committed: the results JSONL, the per-cell extraction output (`results/<run_id>/metrics/`), `results/<run_id>/archive.json` (archive path and SHA-256, plus a SHA-256 per member), and the import-probe JSON.

### Non-inferiority (both rules)

Here "treatment" means `views` in Rule V and `import-card` in Rule C; "control" means `baseline` and `import-full`.

1. **Overall:** the treatment's success rate (pooled over all tasks, repeats 1–3; 15 runs) is at most **10 points** below the control's. At n = 15 that means at most one fewer success.
2. **Guarded tasks** (`maintenance_drift`, `negative_control_no_drift`), per task: `e_t` = not-success count of the treatment minus that of the control, over repeats 1–3.
   - `e_t ≤ 0`: the clause holds.
   - `e_t ≥ 2`: **FAIL**.
   - `e_t = 1`: **NULL pending the extension.** The pre-registered extension runs **once**: repeats 4 and 5 of both guarded tasks, in both cells (8 runs), whenever any guarded task has `e_t = 1`. `e_t` is then recomputed over repeats 1–5. `≤ 0` holds; `= 1` is **NULL** (final, no further extension); `≥ 2` is **FAIL**.
   - Extension repeats enter only this clause. The primary metric and clause 1 always use repeats 1–3; the extension runs are reported descriptively.

### Rule V — views vs baseline

- **Cells:** 5 tasks × {`baseline` (v0.3 world), `views` (matrix world)} × 3 = 30 runs. `CLAUDE.md`'s `@docs/spec.md` import is present in both arms, each world's own version (the D-024 §4 amendment).
- **Primary metric: consultation bytes per run.** The UTF-8 byte count of every raw `tool_result` content returned to the model in the session (`extract.py::consultation_bytes`), summed over all tools.
- **Aggregation:**
  1. Per task and arm, take the median over repeats 1–3.
  2. The per-task ratio is `ρ_t = median_views / median_baseline`, and the reduction is `r_t = 1 − ρ_t`. If `median_baseline = 0`, then `r_t = 0` when `median_views = 0` too, and `r_t = −1` otherwise.
  3. The headline is `R = median over the 5 tasks of r_t`, i.e. 1 − the median of the per-task ratios.
  4. The per-task `r_t` values are reported **descriptively** and gate nothing individually.
- **Manipulation check:**
  - The median of `gdmd_view_calls + gdmd_graph_calls` per views-arm run must be ≥ 1. Otherwise the arm manipulation did not take, and the verdict is **NULL (apparatus)**.
  - In the baseline arm those commands don't exist (v0.3 `gdmd`). Attempts to call them are counted and reported as a covariate.
- **Verdict:**

  | Verdict | Condition |
  | --- | --- |
  | **FAIL** | `R ≤ 0` (views consult more), **or** non-inferiority clause 1 violated, **or** a guarded task ends at `e_t ≥ 2`. |
  | **PASS** | `R ≥ X = 30%`, **and** both non-inferiority clauses hold, with no guarded task left at `e_t = 1`. |
  | **NULL** | Otherwise: `0 < R < 30%` with no FAIL condition; a guarded task at `e_t = 1` after the extension; or any apparatus NULL. |

- **Secondaries** (reported, not gating): median per-turn occupancy; input, output, cache-read and cache-creation tokens; turns; tool calls; files read; re-reads; wall-clock; estimated USD; outcome counts per arm.
- **What Rule V measures.** Given item 1, it compares **the v0.4 tooling with view instructions against the v0.3 tooling**, not the view commands in isolation. The report says so.
- **Why X = 30%, Y = 10 points.** Both were set a priori, not from pilot data.
  - X is the smallest reduction worth changing the documented workflow for. At n = 3 per cell, smaller effects would not be separable from the run-to-run variance of agentic sessions anyway.
  - Y allows at most one extra failure in 15 runs.

### Rule C — card-import ablation (D-024 adoption gate)

- **World:** the matrix world with `arms/baseline.md`. D-024 (locked) puts the ablation on the baseline *tool arm*, and the card needs v0.4 tooling (`gdmd spec --card` / `--section`), so it cannot run in the v0.3 world.
- **Precondition** (threshold locked in D-024):
  - `spec_import_tokens` is the import probe's **v0.3-world** value, because the pilot runs in that world.
  - M is the median per-turn occupancy, pooled over **all turns of all baseline pilot runs**.
  - If `spec_import_tokens / M < 20%`, record NULL and do not run the ablation. This is reported as a gating read, never as evidence.
- **Cells:** 5 tasks × {`import-full`, `import-card`} × 3 = 30 runs, at one commit. They are run fresh, not reused from Rule V.
  - The cell construction (the swap below) lands with the WS4 build, in its own commit, before any Rule C run. `session_argv` stays unchanged.
- **Swap:** in each `import-card` copy, `CLAUDE.md`'s `- Format definition: @docs/spec.md` becomes `- Format definition: @docs/spec-card.md`. `docs/spec-card.md` is `gdmd spec --card` output, generated in that copy from the copy's own `src/`. Nothing else changes; the schema, `AGENTS.md` and deckbuilder-root imports stay.
- **Probed delta Δ (review item 3):**
  - Δ = the import probe's **matrix-world** `spec_import_tokens`: turn-1 occupancy with the `spec.md` import minus without it.
  - It is re-probed at the Rule C matrix commit, immediately before the Rule C cells, because WS2 grows the spec after the pilot.
  - What is fixed here is the measurement procedure, not a number read after results.
- **Primary metric: median per-turn context occupancy per run.** Occupancy is `input + cache_creation + cache_read` tokens per assistant message id, deduplicated (`extract.py::per_turn_occupancy`).
- **Aggregation:**
  1. Per task and cell, take the median over repeats 1–3: `M_full,t` and `M_card,t`.
  2. The realized reduction is `d_t = M_full,t − M_card,t`, in tokens.
  3. The headline is `D = median over tasks of d_t`.
  4. The card's own size and any extra `--section` calls count against `D`, by design: the target is the spec import's weight actually removed from every turn.
  5. Per-task `d_t / Δ` and relative reductions `1 − M_card,t / M_full,t` are reported descriptively.
- **Verdict:**

  | Verdict | Condition |
  | --- | --- |
  | **FAIL** | Non-inferiority clause 1 violated, **or** a guarded task ends at `e_t ≥ 2`. |
  | **PASS** | `D ≥ 0.5 × Δ`, **and** both non-inferiority clauses hold, with no guarded task left at `e_t = 1`. |
  | **NULL** | Otherwise: `D < 0.5 × Δ` with no FAIL condition; a guarded task at `e_t = 1` after the extension; the precondition not met; or any apparatus NULL. |

- **Secondaries:** estimated USD per run; the `gdmd spec --section` call rate (Bash calls containing `gdmd spec --section`), where a high rate means the card is missing content; plus the Rule V secondaries.
- **On PASS:** a separate commit switches the repo's `CLAUDE.md` to the card and cites this result. The starters are unaffected (they carry no agent file; see D-024).

### Stopping and reporting

1. **Order of operations.**
   1. Dry run → model-id probe → import probe (both worlds) → pilot (baseline arm, one run per task).
   2. Stop with the cost estimate and the Rule C precondition read, **and wait for approval**.
   3. Rule V's full matrix runs once WS2 is implemented (after Checkpoint 3); Rule C's, after the WS4 build if the precondition holds.

   Pilot results are **not evidence**. They are reported only as apparatus validation, as a cost estimate, and as the precondition read.
2. **Each rule's full matrix runs once.** Beyond the one `error` re-run and the pre-registered guarded-task extension, nothing is re-run, added or dropped after results are seen.
3. **Reporting.** Results are reported **by the rule** in `docs/case-studies/dogfood-01.md`, including NULL and FAIL. The report contains:
   - the raw results table, one row per run, with its outcome;
   - the per-task values;
   - each rule's verdict;
   - the limits: small n; a single model; tasks designed by the format's own author on its own trees; a possible awareness effect from reading `DECISIONS.md`; the world difference in Rule V; the judge residual; no comparability with F-009.
4. **No post-hoc metric switching.** Any reframe of a rule faces the counterfactual-adoption test and gets its own DECISIONS entry. The spec, README and release notes state no cost or success claim beyond what a verdict here supports (§11.3).

### Resolved at review (from the draft's open points)

- **(a) Baseline contamination after WS2:** resolved by item 1. The baseline runs the v0.3 world, so it cannot discover v0.4 views.
- **(b) Thresholds:** X = 30% (Rule V). Rule C's flat 10% is replaced by 0.5 × Δ. Y = 10 points, with the guarded-task mapping above. 3 repeats. Caps as stated.
- **(c) Logs:** gitignored plus a SHA per line plus an external compressed archive; results and extraction output are committed.

### Amendment 1 (2026-09-30, before the pilot): the locked flags did not load `CLAUDE.md`

- **Found by** the pre-registered import probe, its first run at the lock commit `79a1827`. The raw result is in `benchmark/dogfood/results/import-probe-probe-20260930.json`.
- **What the probe showed:** turn-1 occupancy was 6,904 tokens with the `spec.md` import and 6,909 without it (v0.3 world), and 6,887 vs 6,888 (matrix world). The ~30k-token spec was absent in both conditions. The transcripts carry no `CLAUDE.md` content.
- **Cause:** `--restricted` "ignores user, project and local settings files". In practice it also drops project memory (`CLAUDE.md` and its `@`-imports), and `--setting-sources project` does not restore it under `--restricted`.
- **Why it matters:** the locked text contradicted itself. It pinned `--restricted` **and** asserted the `@docs/spec.md` import is present in both arms (Rule V cells; D-024 §4). Under those flags, no arm saw `CLAUDE.md`, `AGENTS.md` (as an import), the schema or the spec. The Rule C precondition would have read ~0 by construction.
- **Flag variants probed** (single-turn, matrix world, with the spec import):

  | Variant | Turn-1 occupancy |
  | --- | --- |
  | `--restricted` | 6,973 |
  | `--restricted --setting-sources project` | 6,987 |
  | no `--restricted`, `--setting-sources ""` | 7,728 |
  | no `--restricted`, `--setting-sources project,local` | 73,772 |
  | the same + auto-memory off | 72,927 |

  - The `project` source is what loads `CLAUDE.md`.
  - Dropping `--restricted` also adds Claude Code's auto-memory section, which offers the subject a writable memory directory outside the copy.
  - No user skills or plugins appear in any variant.
- **Change:**
  - `session_argv` drops `--restricted` and adds `--setting-sources project,local` plus `--settings '{"autoMemoryEnabled": false}'`.
  - Sessions also run with `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`.
  - User settings stay excluded. The repo tracks no `.claude/` settings, and there is no user `CLAUDE.md`, so the project source loads exactly the copy's `CLAUDE.md`.
- **New per-run apparatus check:** `extract.session_context` reads the raw JSONL. A run is an `error` (apparatus) if the `instructions` attachment (the injected `CLAUDE.md`) is absent, or if the auto-memory section is in the system prompt. `claude_md_loaded`, `auto_memory_prompt` and `assistant_models` are on every result line. The import probe refuses to report if the check fails in any of its four calls.
- **What `--restricted` provided that is now lost:** confinement of the file tools to the copy. The other properties are kept by `--tools` (only the named tools exist) and `--setting-sources` (no user settings). Out-of-copy reads were already detected rather than prevented for Bash (`out_of_copy_access`). That detection now covers the file tools' only remaining escape too, and the contamination rule above is unchanged.
- **Observation, no change:** `modelUsage` also reports `claude-haiku-4-5` (Claude Code background calls). Only `claude-sonnet-5-5` writes assistant records, so occupancy and consultation metrics are unaffected. Estimated USD, a secondary metric, includes the background calls.
- **Discipline:**
  - This is an apparatus correction that makes the harness match the locked text. It does not reframe a rule: no threshold, metric, cell, aggregation or verdict mapping changes.
  - No pilot or matrix run existed. The only runs before it were the model-id probe and the import probe, whose job is exactly this read.
  - Premise-genuine (the transcripts and the table above), re-scoping-honest (the rule is unchanged; the harness now does what the rule said), lineage preserved (this amendment, and the unedited locked bullet it supersedes).

### Pilot reads (2026-09-30), not evidence

The pilot is run `pilot-20260930`: baseline arm (v0.3 world), one run per task, at `337a72b`, CLI 2.1.285. Results are in `benchmark/dogfood/results/pilot-20260930*`; the import probe is `import-probe-probe2-20260930.json`. Per stopping rule 1, these are reported only as apparatus validation, a cost estimate and the Rule C precondition read.

- **Apparatus:**
  - 5 of 5 runs completed and passed the context check (`CLAUDE.md` injected, no auto-memory); every checker emitted a report.
  - The judge preflight passed on every copy, and the logs were archived outside the repo (20 files).
  - One `out_of_copy_access` entry is a detector false positive: a denied `cd ../..` from inside the copy's tree. It is in the listed-not-penalized category.
  - Subjects read files mostly through Bash (`cat`, `head`, `sed -n`), not `Read`. The `Read`-based secondaries (`files_read`, `bytes_read`, `re_reads`) therefore under-report; the primary (all tool results) is unaffected.
- **Caps:** none bound. The maxima were 8 of 60 turns, 26 of 1200 s and $0.46 of $3.00. **No cap is raised.**
- **Rule C precondition:** v0.3-world `spec_import_tokens` = 45,975. M = the median over all 28 pilot turns = 77,484. The share is **59.3% ≥ 20%, so the precondition is met.** The ablation may run after the WS4 build.
- **World difference (review item 1):** `spec.md` is 121,539 bytes (v0.3) vs 122,948 (matrix at `337a72b`), and the spec import is 45,975 vs 46,475 tokens.
- **Cost estimate** (each task's pilot cost standing in for every cell of that task):
  - Rule V: ≈ $11.6 for 30 runs, plus ≈ $2.7 if the extension triggers.
  - Rule C: the same.
  - About 15 minutes of wall-clock per matrix.

### Amendment 2 (2026-09-30, after the pilot, before any matrix): Rule C runs on v0.4 tooling, recorded explicitly

- **Decided:** approved by the user at the post-pilot review. The Rule C "World" bullet above already said this at the lock commit `79a1827`, as an inference. This amendment records it as an explicit decision with its rationale, before any Rule C cell exists.
- **Decision:** both Rule C cells (`import-full` and `import-card`) run in the **matrix world** (the v0.4 tooling layer at the Rule C commit) with `arms/baseline.md`. They do not run in the v0.3 world that Rule V's `baseline` arm uses.
- **Rationale:**
  1. **D-024 (locked) fixes the tool arm, not the world.** It puts the ablation "on the baseline tool arm only", which means the arm text without view instructions. The v0.3 world is Rule V's device for keeping the baseline from discovering v0.4 views (review item 1). It answers a different question.
  2. **The card cannot exist in the v0.3 world.** `gdmd spec --card` and `--section` are v0.4 commands. The card is generated from the v0.4 spec's structure and points at `gdmd view` / `gdmd graph`. An `import-card` subject must be able to call `--section`, so the copy's `gdmd` must be v0.4.
  3. **The comparison needs one world across both cells.** With the world held fixed, the `@`-import line is the only difference between cells, as D-024 §3 requires.
  4. **The adoption question lives in v0.4.** A PASS switches the repo's `CLAUDE.md` in v0.4, so the ablation measures the card where it would be used.
- **Consequences:**
  - Rule C's `import-full` cells differ from Rule V's `baseline` cells (world) and from Rule V's `views` cells (arm text). None are reused, as already locked.
  - The precondition read used the v0.3-world import (45,975 tokens). The matrix world's import is 46,475, 1.1% larger, which cannot flip a 59.3%-vs-20% gate.
  - Δ for the PASS threshold is re-probed in the matrix world at the Rule C commit, as already locked.
- **Not changed:** thresholds, metrics, cells, aggregation, non-inferiority and verdict mapping.

### Amendment 3 (2026-09-30, before any matrix data): Bash-read secondaries (definitions; non-gating)

- **Decided:** approved by the user at the post-pilot review. It adds secondary metrics only. No primary, threshold, cell or verdict mapping changes, and the new metrics gate nothing.
- **Why:** the pilot (not evidence) showed that subjects read files mostly through Bash (`cat`, `head`, `sed -n`, `grep`), not the `Read` tool. The locked `Read`-based secondaries (`files_read`, `bytes_read`, `re_reads`) therefore under-report reading. They stay, unchanged, and the metrics below are added beside them.
- **Definitions** (`extract.bash_reads`, `extract.extract`):
  - A Bash command is split into simple commands, quote-aware: a `|` inside a quoted pattern is not a pipe, and unquoted newlines separate commands.
  - A simple command is a **file read** if its program is one of `cat`, `head`, `tail`, `sed`, `grep`, `nl`, `less`, `more`, `awk` **and** it names at least one file operand.
    - Options are skipped, including their values for options that take one.
    - The first operand of `grep`/`awk`/`sed` is the pattern or script, not a file.
    - `sed -i` and any segment with an output redirection are writes.
    - A pipe-fed `head`/`grep` names no file, so it is not a read.
  - `git show` counts as a read call with no file operands.
  - `cd` updates the working directory for later commands **and later calls**, as Claude Code's Bash tool does. Operands resolve against it.
  - Calls whose result is an error (including permission denials) read nothing.
- **The new secondaries, per run:**

  | Metric | Definition |
  | --- | --- |
  | `bash_read_calls` | Non-errored Bash calls with at least one read. |
  | `bash_read_bytes` | Their tool-result bytes. This is a subset of consultation bytes, not an addition to it. |
  | `bash_files_read` | Distinct operand paths read through Bash. |
  | `all_files_read` | Distinct copy-relative paths read through `Read` or Bash. A directory operand (`grep -r dir`) counts as one path. |
  | `all_re_reads` | Reads, by either tool, of a path already read earlier in the run (counted once per call). |
  | `all_files_read_paths` | The path list itself; in the metrics file only. |

- **Validation:**
  - Parser cases and a cross-call integration test are in `tests/test_dogfood.py`.
  - Re-extracting the five pilot sessions leaves consultation bytes and per-turn occupancy byte-identical (asserted).
  - The pilot sessions go from `files_read` of 0–3 to `all_files_read` of 0–7. Example: authoring reads 0 files through `Read` and 5 through Bash, with 1 re-read.
  - Known limits: shell globs are not expanded, and a directory operand counts as one path.

### Lineage note (2026-09-30): the branch was rebased onto `main`

- **What happened.** `v0.4-views` forked at `61c95fe` (tag `v0.3.0`). `main` then gained `db1950e`, a post-v0.3 docs-drift sweep (PR #1). At the user's request, before the Checkpoint 3 commit, the branch was rebased onto `origin/main`. This rewrote every branch commit's SHA.
- **Pre-rebase history is preserved.** The tag `v0.4-views-prerebase` points at `1665b0e`.
- **Citations stay as they are.** The SHAs cited in this entry, in OI-003, in the v0.3 conformance correction and in `benchmark/dogfood/results/` are the commits the work and the runs actually used. The pilot ran at `337a72b`, whose tree differs from its rebased twin, which also contains `db1950e`. Result files are data and are not edited.
- **Old → rebased:**

  | Old | Rebased | Old | Rebased |
  | --- | --- | --- | --- |
  | `19bce45` (D-022) | `2cefcb2` | `3f035cf` (operating task) | `06e86a2` |
  | `efb05d9` (OI-001..004) | `e61f40c` | `9998502` (shim fix) | `985424a` |
  | `b2f098d` (D-023) | `99f9013` | `79a1827` (**D-025 lock**) | `fa48944` |
  | `8761ae8` (D-024) | `fffc2c1` | `337a72b` (**amendment 1; pilot source**) | `7c04c1c` |
  | `b1cd860` (OI-005) | `0d95860` | `e045ef1` (pilot results) | `e2fd99c` |
  | `3e44035` (harness drafts) | `31e8922` | `15faca6` (amendment 2) | `e442041` |
  | `8537ddb` (OI-006, correction) | `d7269a0` | `e9ecff5` (amendment 3) | `ab52140` |
  | `f43d357` (time-bomb test fix) | dropped: `db1950e` made the identical fix | `1665b0e` (D-026) | `d590d1d` |

- **Order preserved.** Every lock still precedes the runs it governs. The pre-rebase history shows it with the original commit times, and the rebase kept author dates. No run happened after the rebase.
- **Effect on the worlds (item 1).**
  - The v0.3 world is the tag, so it is unchanged.
  - The matrix world now also carries `db1950e`'s fixes: AGENTS.md's four-field stability guarantee and its corrected `{loops.combat_turn}` example, and spec §1, §2.2, §4, §4.8, §9, §11.2 and Appendix C.
  - Re-recorded sizes at the rebased head `d590d1d`:

    | File | v0.3.0 | Pre-rebase | Rebased head |
    | --- | --- | --- | --- |
    | `spec.md` | 121,539 | 122,948 | **124,279** bytes |
    | `AGENTS.md` | 12,197 | 12,197 | **12,580** bytes |

    `CLAUDE.md`, `schema/` and `src/` are unchanged.
  - The pilot reads' token figures (45,975 / 46,475) describe the pre-rebase commit. The import probe is re-run at each matrix commit, and its JSON is committed with that matrix's results. Rule C's Δ is re-probed there anyway, as locked.

#### Addendum (2026-09-30, after the push)

- **The force-push was verified after the fact, not by the pre-push check.**
  - The agreed pre-push check (`git merge-base --is-ancestor origin/v0.4-views v0.4-views-prerebase`) can only pass before a force-push. It was run after the push had already happened, so it failed by construction.
  - The verification is therefore GitHub's branch activity (`gh api repos/{owner}/{repo}/activity?ref=refs/heads/v0.4-views`):

    | Time (UTC) | Event | Before | After |
    | --- | --- | --- | --- |
    | 16:01:53 | branch created | — | `e9ecff5` |
    | 16:22:20 | force push | `e9ecff5` | `7c4a254` |

    Nothing else was pushed to the branch in between. So `e9ecff5` is the only remote state the force-push overwrote.
  - `git merge-base --is-ancestor e9ecff5 v0.4-views-prerebase` exits 0: `e9ecff5` is an ancestor of the tag. The tag (`1665b0e`) is on the remote (`git ls-remote`), so every pre-rebase commit remains reachable.
- **"Lock precedes run" is verifiable only against the tag's history.**
  - The rebase kept author dates but rewrote committer dates: every rebased commit carries committer date 2026-09-30 18:14:42 +0200, later than every run.
  - In the tag's history the order is visible: the lock `79a1827` was committed at 08:17:58 +0200 and amendment 1 `337a72b` at 08:23:47 +0200; the pilot's first `started_at` is 06:24:22 UTC (08:24:22 +0200). The probes carry no timestamps; their `source_sha` is the commit they ran on (`79a1827` for the first import probe, `337a72b` for the second and for every pilot line), all in the tag's history.
  - **The tag `v0.4-views-prerebase` must never be deleted or moved.** A GitHub tag ruleset ("protect v0.4-views-prerebase", id 24259648, active, no bypass actors) blocks its deletion, update and non-fast-forward on the remote.
- **Forward-only from the first full-matrix run.** From the first Rule V or Rule C full-matrix run onward, `v0.4-views` only moves forward. Changes from `main` come in by merge, never by rebase, so every matrix's `source_sha` stays on the branch's history.
- **Rule V limits.** The views world now also carries `db1950e`'s docs-drift fixes to `docs/spec.md` and `AGENTS.md` (listed above); the baseline's v0.3 world does not. The Rule V report lists this in its limits (stopping rule 3), alongside the v0.3/v0.4 world difference. It is part of what Rule V compares, not a separate effect it can isolate.

### Amendment 4 (2026-09-30, after WS2, before any matrix): the views arm text is pinned

- **Decided:** as D-027 requires ("Consequences"), approved at Checkpoint 3. The arm text is fixed by hash before any Rule V cell, and the same bytes are reused unchanged for D-026's Rule V2.
- **The pin:** `benchmark/dogfood/arms/views.md` at commit `85fe4c9`, SHA-256 `1db2d1b83c911857612e7de0f0ba3b9af2d9c6ed66caf045ce23e9cab6eadc98`.
- **One change before pinning.** Checked against the implementation, the text was accurate but did not say which directory a pointer's path is relative to. A subject running `gdmd view examples/deckbuilder` receives `gdd/mechanics.md:89-96` and could look for it at the repository root. `85fe4c9` adds "the path is relative to the tree root", which is §9.9.1's definition. The arm is still a neutral §9.9 reference: the flag-parity and steering-word tests pass.
- **Enforced by the harness.** `run.ARM_PIN_SHA256` holds the hash. `run.load_arm` refuses an arm whose bytes differ, and every arm in a run is checked before any cell, including a dry run. Tests: the committed bytes equal the pin, and a changed `views.md` is refused. Changing the arm text again needs a new amendment and a new pin.
- **Cross-arm facts known before the matrix,** for the Rule V limits (stopping rule 3):
  - `README.md` is not in the v0.3 overlay (`fixture.V03_OVERLAY`), so baseline copies carry the matrix README. `scripts/docs_lint.py` requires its verb list to equal the registered commands, so it names `view | graph` in both arms, while the baseline's v0.3 `gdmd` has neither. Attempts are the locked covariate (Rule V manipulation check).
  - `CHANGELOG.md` and `DECISIONS.md` also come from the matrix commit in both arms and describe the views. This is the awareness effect already listed in the limits.
- **Preconditions for the Rule V matrix, as of this amendment:**
  - The views are implemented: `041e158` (block model), `18f6084` (`view`), `2f62191` (`graph`) and `da6cb9d` (goldens and budget).
  - `docs_lint` is green with `view` and `graph` registered.
  - The arm text is pinned.
  - A dry run at `85fe4c9` prepared a `baseline` and a `views` cell, and `gdmd view` ran in the views copy.

  The matrix commit is not chosen yet. The import probe is re-run there, as the lineage note requires.
- **Not changed:** thresholds, metrics, cells, aggregation, non-inferiority and verdict mapping.

### Amendment 5 (2026-09-30, before any matrix data): review decisions on `--grep`, AGENTS.md and `--full`

- **Decided:** by the user at the WS2 review. The rule applied: **correctness is fixed before the matrix; anything that would only make the views arm score better on the primary waits.**
- **1. `--grep` shows matches outside blocks (correctness, fixed).**
  - The first `--grep` selected blocks only, as §9.9.3 then said. It silently missed a namespace key, a comment between tokens, or a title or introduction that plain `grep` finds. A search command that misses text is a trap for any agent. That this also biased the result against views is not the reason for the fix.
  - `709dee0`: a gap-line match is a `gap` selection, with its pointer, under its file, and with its ancestor key lines; `--role` excludes gap selections. §9.9.3 gains one sentence. A property test on all 12 trees checks that every match is shown exactly once. Goldens were regenerated, and the diff adds exactly the gap selections.
  - `arms/views.md`'s `--grep` line describes the selection, so it now adds "and matching lines outside any block, each with its pointer".
  - **The new pin** replaces amendment 4's: `arms/views.md` SHA-256 `f77848a6452dcca3d7480cfa1b835e915be2b8846a8960f28f14b01a7d138712`, at the commit carrying this amendment. `run.ARM_PIN_SHA256` holds it. D-026's Rule V2 reuses these bytes.
- **2. AGENTS.md lists `view` and `graph` (world, not arm).**
  - AGENTS.md's own rule requires every new CLI command to land there, and a v0.4 that broke it would be an unrealistic v0.4.
  - `d7533b8` adds a command-list entry shaped like its neighbours, saying what each command returns, with no when-to-use guidance. It sits in the Operating mode's `**CLI:**` line, beside `gdmd lint <tree>` and `gdmd verify <tree>`.
  - It is part of the v0.4 world, which the views arm runs in; the baseline's AGENTS.md is v0.3's (overlay). It joins the Rule V limits below.
- **3. `--full` stays as it is; a non-gating secondary measures it.**
  - `--full` is 23–38% larger than the files it projects (D-027 implementation notes). Compacting it now would be motivated by a byte count that is Rule V's primary, the one kind of pre-matrix change the locks exist to prevent. `--full` is also not the main consultation path.
  - `a47080e` adds **consultation bytes by view mode**: `view_mode_bytes` and `view_mode_calls` attribute each Bash call's full result bytes (errors included, as in the primary) to the mode its command runs. The modes are `overview`, `full`, `grep`, `ref`, `graph`, `other` (`--help`) and `mixed` (more than one mode in one call). The report shows it descriptively. It gates nothing, and the locked manipulation check keeps its substring counts.
  - Any compaction of `--full` is a post-study-1 v0.4.x change, evaluated in study 2.
- **The verdict computation is committed before the data.** `234d618` adds `benchmark/dogfood/analyze.py rule-v`, which implements this entry's Rule V as locked, with every branch of the verdict table tested on synthetic results. It resolves four points the locked text leaves open:
  1. A cell's effective line is the last line that `supersedes` it. A second `error` stays not-success.
  2. A line with no `consultation_bytes` (an `error` with no session) is listed and left out of its task-arm median.
  3. An apparatus NULL (errors > 10%, contamination > 10% in an arm, or the manipulation check failing) decides the verdict, as the error-handling and manipulation-check bullets say ("that rule's verdict is NULL").
  4. Contamination is an `out_of_copy_access` entry naming the harness (`benchmark/dogfood`, `test_dogfood.py`). It is counted conservatively, including a denied attempt, and every case is listed.
- **The Rule V limits, consolidated for the report** (stopping rule 3):
  - Rule V compares the v0.4 world plus the views arm with the v0.3 world plus the baseline arm, not the view commands in isolation.
  - The v0.4 world includes `db1950e`'s spec and AGENTS.md fixes, and AGENTS.md's `view` / `graph` entry.
  - README's verb list names `view | graph` in both arms. `CHANGELOG.md` and `DECISIONS.md` describe the views in both arms.
  - The standing limits: small n, a single model, tasks written by the format's own author on its own trees, the judge residual, and no comparability with F-009.
- **Order from here:** full sweep → `git push origin v0.4-views` (plain) → the import probe at this amendment's commit → the Rule V matrix, 30 runs, once, plus the guarded extension only if `analyze.py` reports it pending → report by the rule in `docs/case-studies/dogfood-01.md` → stop.
- **Not changed:** thresholds, primary metrics, cells, aggregation, non-inferiority and verdict mapping.

### Rule V result (2026-09-30): **NULL**

- **Run** `rulev-20260930` at the matrix commit `e693f2a`: 30 runs, CLI 2.1.285, `claude-sonnet-5-5`. The report is [`docs/case-studies/dogfood-01.md`](docs/case-studies/dogfood-01.md) (Rule V section), and the data is in `benchmark/dogfood/results/rulev-20260930*`.
- **Verdict:** R = 15.6%, with 0 < R < X = 30%, so **NULL**.
  - Non-inferiority holds: 15/15 successes in each arm, and guarded `e_t` = 0 for both tasks, so the extension did not run.
  - No apparatus NULL: 0 errors, 0 contaminated runs, and the manipulation-check median is 1.
  - Computed by `analyze.py` as committed before the data (`234d618`). Nothing was re-run, added or dropped.
- **Consequence:** under §11.3, no claim that views reduce session cost enters the spec, the README or release notes.
- **Descriptive only (gates nothing):**
  - Per-task `r_t` ranges from −62.9% to +54.9%.
  - `--full` was never used; `--grep` produced 42.6% of the views arm's consultation bytes.
  - The views arm's per-turn occupancy and USD are higher, by about the world difference in spec-import size (5,837 tokens).
- **From this run on, `v0.4-views` moves forward only** (lineage addendum).

### Amendment 6 (2026-09-30, after the WS4 build, before any Rule C data): the Rule C cells and computation

- **Decided:** by the user at the Rule V review ("the WS4 build, then the cell construction commit, the import probe at the Rule C commit (Δ), the Rule C matrix, once, as locked"). This records the apparatus the Rule C matrix runs on. No rule changes.
- **Built:**
  - WS4 (`abb13e0`, D-029): `gdmd spec --card` / `--section`, with D-024's completeness test.
  - The cell construction (`0b8419d`):
    - arms `import-full` and `import-card`, both in the matrix world with `arms/baseline.md`;
    - `fixture.swap_in_card`, which generates each `import-card` copy's `docs/spec-card.md` with the copy's own `gdmd spec --card` and swaps only `CLAUDE.md`'s `@docs/spec.md` line, inside the copy's baseline commit;
    - the `--section` call counter;
    - `analyze.py rule-c`.
  - A dry run at `0b8419d` prepared all 10 cells, and every card was identical.
- **The card at the Rule C commit:** 8,491 bytes, SHA-256 `7c280fa1dbf1f4631438fff238347d7e5c564fda88d0248062c515f82184a99f`, generated from a 139,743-byte spec. Every `import-card` result line carries the card's hash.
- **The computation is fixed before the data.** `analyze.py rule-c` implements this entry's Rule C. Rule V's four resolutions apply unchanged (amendment 5): supersedes, missing values, apparatus-NULL precedence and contamination. In addition:
  - A line with no `median_turn_occupancy` is listed and left out of its task-cell median.
  - Δ is read from the matrix world of the import probe run at the Rule C commit (`--probe`), as locked ("Probed delta").
  - The precondition is the pilot's gating read (59.3% ≥ 20%, met). Rule C has no manipulation check in this entry, and none is added.
- **The Rule C limits, for the report:**
  - small n and a single model;
  - tasks written by the format's own author;
  - both cells run in the v0.4 world, where `gdmd view` / `graph` exist and AGENTS.md lists them;
  - the card's §9.9 synopsis names them in the `import-card` cell only, while the full spec in `import-full` contains all of §9.9;
  - the precondition was read in the v0.3 world at the pilot, and Δ is re-probed in the matrix world;
  - the judge residual;
  - no comparability with F-009.
- **Order from here:** full sweep → `git push origin v0.4-views` (plain) → the import probe at this amendment's commit → the Rule C matrix, 30 runs, once, plus the guarded extension only if `analyze.py rule-c` reports it pending → report by the rule in `docs/case-studies/dogfood-01.md` (Rule C section) → D-024's adoption consequence, only on PASS, in its own commit → stop.
- **Not changed:** thresholds, the primary, cells, aggregation, non-inferiority and verdict mapping.

### Rule C result (2026-09-30): **PASS**

- **Run** `rulec-20260930` at the Rule C commit `b4b1596`: 30 runs. The report is [`docs/case-studies/dogfood-01.md`](docs/case-studies/dogfood-01.md) (Rule C section), and the data is in `benchmark/dogfood/results/rulec-20260930*`.
- **Verdict:** D = 46,769 tokens, against 0.5 × Δ = 26,326 (Δ = 52,651 from `import-probe-probe4-20260930`), so **PASS**.
  - The per-task `d_t` ran from 45,267 to 48,650 tokens, 86–92% of Δ.
  - Non-inferiority holds: 15/15 successes in each cell, and guarded `e_t` = 0 for both tasks, so no extension ran.
  - No apparatus NULL: 0 errors and 0 contaminated runs.
  - Computed by `analyze.py rule-c` as committed before the data (`0b8419d`). Nothing was re-run, added or dropped.
- **Descriptive:**
  - No `import-card` run called `gdmd spec --section`, and none read `docs/spec.md` directly.
  - The card cell consulted slightly more tree text (13.0 vs 9.3 KB per run) and cost less ($0.17 vs $0.42 per run, median).
  - Every run succeeded, so non-inferiority was held on easy tasks. Study 2's C2 is the harder re-test.
- **Consequence (D-024 §3):** the repository's `CLAUDE.md` switches to the card, in its own commit citing this result. Per D-026:
  - a C2 FAIL reverts it;
  - study 2's copies force the `@docs/spec.md` import where its cells require the full import.
- **Addendum (descriptive, non-gating; the user's Rule C review):** a two-call probe at the adoption commit `49b53b4` (`card-probe-cardprobe-20260930`) puts the card import at **3,978 tokens**. That is 68% of the 5,882-token gap between Δ and D. The remaining 1,904 tokens follow the card cell's extra reading per task (23 tokens on the negative control, up to 3,406 on `lookup_refs`). No verdict change. The details are in the report's Rule C addendum.

---

## D-026 — Dogfood study 2 (consultation at scale): locked design

- **Status:** locked (2026-09-30), **before any study-1 matrix data exists**. The only dogfood runs so far are the probes and the study-1 pilot (baseline arm; not evidence).
  - Locked here: hypotheses, primaries, thresholds, task classes, and the fixture's construction parameters.
  - The fixtures are built from these parameters and **frozen before study 2's own pilot**. A D-026 amendment records the freeze hashes.
- **Decided:** 2026-09-30, by the user at the post-pilot review ("study 1 runs as locked; lock study 2's design before any study-1 matrix data").
- **Related:** D-023 (protocol), D-024 (card adoption rule, unchanged), D-025 and its amendments (the apparatus inherited here), spec §11.3.
- **Lineage (why a second study):**
  - Study 1's pilot, read only as an apparatus observation, showed small workloads: every task finished in 3–8 turns and consumed 1.5–16 KB of tool results, next to ~77k tokens of context per turn.
  - Study 1 stays as locked and reports by its rule (D-025).
  - Study 2 targets the regime projected views are designed for: a content-heavy tree, where answers require multi-hop traversal.
  - It is a **new pre-registered study, not an amendment to study 1**. It is locked before any views-arm or card data exists, so no comparison result informs it.

### Hypotheses

- **H2-V (views at scale).** On a content-heavy tree, for multi-hop lookup and impact tasks, the views arm consumes fewer consultation bytes than the v0.3 baseline, without a loss of success.
- **H2-C (card re-test at scale).** On the same tasks, importing the card instead of the full spec lowers per-turn context occupancy without a loss of success. This is the D-024 gate, re-tested.

### Fixture: the study-2 tree (construction parameters locked; content built later and frozen)

1. **One new tree, built by a committed generator.** `benchmark/dogfood/fixtures/study2/` holds the generator, its frozen output and the frozen answers.
   - The source lives under `benchmark/dogfood/`, so it is excluded from every copy. Reading it from the real repo counts as contamination (D-025).
   - `fixture.py` places the frozen tree in each copy at `examples/lanternfall/`, inside the copy's base commit, so it looks native to the subject.
   - It is never added to the repo's real `examples/`, which stay realistic hand-authored trees, not benchmark fixtures.
2. **Genre:** a dungeon-crawler RPG ("Lanternfall"). It is deliberately **not** a deckbuilder, because the deckbuilder root is `@`-imported into every session by `CLAUDE.md`.
3. **Size:** about **320 content entities** in four content-heavy kinds (`count_target ≥ 20`, `data_dir` pattern per §6):

   | Kind | Count |
   | --- | --- |
   | `items` | 140 |
   | `skills` | 90 |
   | `monsters` | 60 |
   | `encounters` | 30 |

   Plus core subfiles (pillars, loops, mechanics, architecture invariants, distributions, economy-balance, feel if any verb declares one, a glossary), with **≥ 60 non-content tokens across ≥ 8 namespaces**.
4. **Planted reference graph.** Every edge is a `{ns.id}` ref written by the generator from its own edge list. Edge types:
   - `monsters → items` (drops, 1–3)
   - `monsters → skills` (1–2)
   - `items → skills` (grants, 0–1)
   - `skills → distributions` (1) and `skills → states` nodes (0–1)
   - `encounters → monsters` (2–4) and `encounters → distributions` (1)
   - rules and verbs → encounters and monsters (boss and spawn rules)
   - balance targets referenced from loops and content schemas

   Some reverse closure must reach **depth ≥ 4**.
5. **Determinism:** generator seed **20260930**, fixed word lists, and no wall-clock inputs. Re-running the generator reproduces the frozen output byte-for-byte (a pytest checks this).
6. **Lint:** the tree lints 0 errors / 0 warnings under both the v0.3 `gdmd` and the matrix-commit `gdmd`. The judge preflight must pass on every task copy.
7. **No leak from the in-context spec.** The build script asserts that:
   - no token id of the tree occurs in any file `CLAUDE.md` imports, in either world;
   - each lookup and impact answer's evidence (the lines carrying its edges) spans **≥ 3 files**;
   - task prompts name only the start token(s) and the relation.
8. **Oracle independence** (the frozen-fixtures rule).
   - Answers are computed from the generator's planted edge list, never by parsing the tree with `gdmd` code, which the views arm uses.
   - A pytest cross-checks them **once** against `gdmd graph` / `gdmd view` and `refs.walk_refs`.
   - A disagreement is a generator or tool bug. It is fixed at its source before the freeze, never by editing answers to match the tool.
   - One question per task is also hand-traced by reading the files. The trace is recorded in the freeze amendment.
9. **Statuses and implementation:** mostly `draft`, with a `prototyped` subset whose `implemented_in` points at a small stub `impl/` tree under `examples/lanternfall/`. That subset supports the maintenance tasks.
10. **Freeze:** before study 2's pilot, a D-026 amendment records:
    - the generator commit;
    - the SHA-256 of the frozen tree (a sorted-path manifest) and of the answer files;
    - the hand traces.

    Any change to a locked parameter above is itself an amendment that faces the counterfactual-adoption test and is recorded before the pilot.

### Task classes (6 tasks; prompts written at build, from these templates)

| Task | Class | Question / success (deterministic checker) |
| --- | --- | --- |
| `s2_lookup_forward` | lookup, multi-hop forward | Two questions. From a named start token, list the tokens of a named kind reached by following **exactly k** planted forward edges (k = 2 and k = 3). Answer sets have 3–12 items. |
| `s2_lookup_backward` | lookup, multi-hop backward | Two questions. List the content entities that reach a named token within **≤ k** edges (k = 2 and k = 3). Answer sets have 3–15 items. |
| `s2_impact_tokens` | impact | "The value of `{X}` is about to change: list every token and content entity whose value references it, directly or transitively." That is the reverse closure over value edges, with 10–40 items spanning ≥ 3 files and ≥ 2 content kinds. |
| `s2_impact_files` | impact (ritual-shaped) | "`{Y}` is about to change: list every subfile whose `last_verified:` must be re-checked." That is the set of subfiles containing the reverse closure's non-content tokens, 4–10 files. |
| `s2_maintenance` | maintenance (**guarded**) | A teammate's behavior-preserving refactor under an `implemented_in` path referenced by tokens in exactly 2 of the ≥ 12 subfiles. Success means those two are touched, with no token churn, the impl untouched, and lint 0/0. |
| `s2_negative_control` | negative control (**guarded**) | The same prompt as `s2_maintenance`; the change is in a file no token references. Success means the copy is unchanged. |

- **Answer formats** are fixed per task, like study 1's `lookup_refs`: `answers/<task>.txt`, one `{ns.id}` or path per line, under `Q<n>:` headers.
- **Success is exact set equality for every question.** Per-question Jaccard similarity is reported descriptively.

### Cells, primaries and verdicts

- **Apparatus:** D-025's shared apparatus as amended (1–3): pinned CLI, worlds, fixed judge, one commit per run, flags, outcomes (success / fail / capped / error), error handling, contamination, logs. The only change is the caps, **80 turns, 1800 s and $5.00 per run**, which are identical across arms. They may be raised at most once, upward, after study 2's pilot, and only if the pilot shows one binding.
- **Repeats:** 3 per cell. This is small, and the report says so.
- **Rule V2.**
  - Cells: 6 tasks × {`baseline` (v0.3 world, `baseline.md`), `views` (matrix world, `views.md`)} × 3 = 36 runs.
  - **Both arms' copies force the `CLAUDE.md` import line to `@docs/spec.md`.** This holds the import constant even if a card adoption has switched the repo.
  - Primary: **consultation bytes**, as defined in D-025.
  - Aggregation: as D-025 Rule V (median over repeats → per-task ratio → median over tasks), with per-task values descriptive.
  - Manipulation check: as D-025 Rule V.
  - **PASS:** `R ≥ 30%` and non-inferiority holds. **FAIL:** `R ≤ 0`, or non-inferiority violated. **NULL:** otherwise.
- **Rule C2.**
  - Cells: 6 × {`import-full`, `import-card`} × 3 = 36 runs, in the matrix world with `baseline.md` (as D-025 amendment 2).
  - Primary: median per-turn occupancy.
  - Δ is re-probed in the matrix world at the study-2 commit.
  - **PASS:** `D ≥ 0.5 × Δ` and non-inferiority holds. **FAIL:** non-inferiority violated. **NULL:** otherwise.
- **Non-inferiority:** identical to D-025, including the extension. The overall success drop is at most 10 points (18 runs per arm, so at most one fewer success). Guarded tasks `s2_maintenance` and `s2_negative_control`: `e_t = 1` gives NULL plus one extension to 5 repeats on those tasks only; `e_t ≥ 2` gives FAIL.
- **Why the same thresholds as study 1:** so the two studies are directly comparable. At this scale larger effects are plausible, but the thresholds are not raised or lowered on that expectation.

### Adoption linkage (D-024 unchanged)

- D-024's rule stands: a card PASS switches the repo's `CLAUDE.md` to the card, in its own commit citing the result. The switch is reversible.
- **Study 2 re-tests a study-1 card PASS.**
  - C2 **PASS:** the card stays. It is adopted now if study 1 was not a PASS, because D-024 applies to any locked ablation.
  - C2 **FAIL:** revert `CLAUDE.md` to the full import, in its own commit citing D-026.
  - C2 **NULL:** no change to whatever state exists.
- Rule V2 has no adoption consequence. A PASS licenses a views-cost claim scoped "on content-heavy trees", in the §11.3 sense.

### Order, stopping and reporting

1. **Order of operations.**
   1. Study 1 completes: WS2 → Rule V matrix; WS4 build → Rule C matrix.
   2. Then the study-2 generator, build and cross-check, followed by the freeze amendment.
   3. Then the dry run → import probe → study-2 pilot (baseline arm, 1 run per task; not evidence).
   4. Then the cost estimate, and a **stop for approval**.
   5. Then the Rule V2 and Rule C2 matrices, once each.
2. **Nothing is re-run, added or dropped after results,** beyond D-025's single error re-run and the guarded-task extension.
3. **Report** in `docs/case-studies/dogfood-02.md`, by the rule, including NULL and FAIL:
   - the raw table, per-task values and per-question Jaccard;
   - the limits: a generated, synthetic tree; small n; a single model; tasks and generator by the format's own author (oracle independence is at the code-path level only); the same world difference as study 1; no comparability with F-009.
4. **No post-hoc metric switching;** any reframe gets its own DECISIONS entry and faces the counterfactual-adoption test.

### Amendment 1 (2026-09-30, before any study-2 build): impact prompts are worded in value references

- **Decided:** by the user at Checkpoint 3 review, before the generator or any prompt exists.
- **Why:** the locked oracle for both impact tasks is the reverse closure over **value** edges, the `{ns.id}` references in frontmatter and content-entity files. The template wording ("references it"; "must be re-checked") also admits prose mentions and judgment calls, which the oracle excludes. A subject that includes a `rationale` section, or reasons about re-checking, would fail on the wording, not on the task. `gdmd graph --impact` also includes prose leaves (D-027), so the prompt must say which edges count.
- **Prompt templates (replacing the table wording):**
  - `s2_impact_tokens`: "The value of `{X}` is about to change. List every token and content entity **whose value references `{X}`, directly or transitively** (through the values of other tokens and content entities)." The oracle is unchanged: the reverse closure of `{X}` over value edges.
  - `s2_impact_files`: "`{Y}` is about to change. List every subfile that contains **a token whose value references `{Y}`, directly or transitively**." The oracle is made explicit: the set of `file_type: subfile` files that define a top-level token in the value-edge reverse closure of `{Y}`. Content-entity and content-schema files are not subfiles.
- **Not changed:** the task classes, answer-set size ranges, success criterion, cells, primaries, thresholds and verdict mapping.

### Amendment 2 (2026-09-30, after study 1's Rule V, before any study-2 build): the view-mode parser skips shell keywords

- **Decided:** by the user at the Rule V review. It is recorded here because study 2 reports the same secondary (consultation bytes by view mode, D-025 amendment 5) and relies on it.
- **The defect:** `extract.view_mode` read the first word of each shell segment as the program. A command behind a shell keyword (`for v in …; do gdmd view … ; done`) was not attributed to a mode. Study 1's Rule V matrix had one such call: `lookup_refs` views r2, refused by Claude Code before it ran (25 bytes of error text).
- **The fix:** before the command word, the parser now skips `do`, `then`, `else`, `{` and `(`, as it already skipped env assignments and simple wrappers. There are five new classification tests.
- **Re-extraction** (`benchmark/dogfood/results/rulev-20260930/reextract-d026a2.json`): every study-1 session was re-extracted with the fixed extractor and compared field by field with the committed metrics.
  - **Rule V matrix (30 sessions):** exactly one field pair differs. In `lookup_refs` views r2, `view_mode_calls` goes from `ref` 1 to 2 and `view_mode_bytes` from `ref` 4,241 to 4,266. Consultation bytes, occupancy, every other secondary and the substring counts behind the manipulation check are identical.
  - **Pilot (5 sessions):** no committed field differs. The only additions are fields introduced after the pilot (amendments 3 and 5).
- **Not changed:** the Rule V verdict (NULL) and its inputs. The committed result files are data and are not edited; the report carries a descriptive addendum.

### Amendment 3 (2026-09-30, after study 1's Rule V, before any study-2 build): tool freeze and lint hold until study 2's matrices complete

- **Decided:** by the user at the Rule V review.
- **Tool freeze.** Until study 2's matrices (V2 and C2) complete, `gdmd view` and `gdmd graph` receive **bug fixes only**.
  - A bug is output that contradicts §9.9, a crash, or a wrong pointer.
  - A bug fix gets its own D-entry, states its effect on the pinned arm text (normally none), and regenerates the goldens with the diff reviewed.
  - A usability change waits, even one study 1 motivates. Such ideas are queued in OI-007, not coded.
  - Why: study 2 measures the same tool study 1 measured, with the same pinned arm text (`f77848a6…`). Changing the tool between the studies would make V2 a different treatment.
- **Lint hold.** Changes to lint *behavior* wait until after study 2: OI-003, OI-005 and OI-006 class A (the schema / `applies_to` decision).
  - Why: the judge is the matrix commit's lint, and D-025's judge residual assumes no rule is added between `v0.3.0` and the studies.
  - **Tree-only fixes may land now,** each with its own D-entry: OI-006 classes B and C, including the party-rpg starter's `data_dir`. None of the study-1 task trees is touched by them.
- **Not changed:** study 2's design, cells, primaries, thresholds and verdict mapping.

### Amendment 4 (2026-09-30, after study 1, before the study-2 freeze): a copy carries the card file only if its cell imports it

- **Decided:** by the user at the Rule C review, before any study-2 build or data.
- **The defect:** the card adoption (`49b53b4`, D-024) committed `docs/spec-card.md` to the repository. From then on every copy exported from the repo carried it, including cells that do not import it:
  - both V2 arms, including the v0.3-world baseline, where `V03_OVERLAY` leaves the file in place because it did not exist at `v0.3.0`;
  - C2's `import-full` cell.

  A subject in those cells could read the card, and in the v0.3 world it describes v0.4's `view` / `graph` (its §9.9 synopsis).
- **The change:** `fixture.remove_unimported_card` deletes `docs/spec-card.md` from every copy whose cell does not import it: `baseline`, `views` and `import-full`, plus the probes' spec-import copies.
  - `import-card` copies keep generating the card in-copy from the copy's own `src/` and spec (`swap_in_card`), as Rule C did.
- **Why:**
  - It restores the conditions D-026 was locked under, when no card file existed.
  - It matches study 1 exactly: Rule V (`e693f2a`) and Rule C (`b4b1596`) both ran before the file was committed, so no study-1 copy outside `import-card` had it.
  - It keeps a v0.4 file out of the v0.3 world.
- **Tests:** in `tests/test_dogfood.py`:
  - for `views`, `import-full` and `import-card`, the card file exists (and is tracked in the copy) exactly when `CLAUDE.md` imports it;
  - a v0.3-world copy has no card file.
- **Not changed:** the cells, primaries, thresholds and verdict mapping. The Δ re-probe (C2) now runs on copies without the card file, like probe4.

### Amendment 5 (2026-09-30): the freeze, before study 2's pilot

- **Decided:** under D-026 §10, after the build and the one-time cross-check and before any study-2 run. The user's Rule C review ordered it: generator → build → oracle cross-check → freeze amendment → dry run → import probe → pilot, then stop.
- **Commits:**
  - generator and frozen output: `e851a4d`;
  - harness (placement, tasks, checkers, `--study` caps): `4e2f498`;
  - the V2/C2 verdict code: `048fc32`;
  - the freeze: this amendment's commit, which also pins the tree in `fixture.FIXTURE_TREE_SHA256` and the other frozen files in a test.

#### What was frozen

| Artifact | SHA-256 |
| --- | --- |
| `fixtures/study2/tree/`: the sorted-path manifest of its 351 files (151,138 bytes); one `<sha256>  <path>` line per file | `718e52d2dcacd8834ae3458ce53353f6e1881049af7e7eb22a7394f9357b0f47` |
| `answers/s2_lookup_forward.json` | `1691637f…d399d` |
| `answers/s2_lookup_backward.json` | `66c4bea7…65942` |
| `answers/s2_impact_tokens.json` | `2f69fe27…1cf63` |
| `answers/s2_impact_files.json` | `b631b174…21fc61` |
| `answers/s2_maintenance.json` | `3dfc8b51…403b9` |
| `answers/s2_negative_control.json` | `b1cb282a…883aa` |
| `edges.json` (669 planted edges, 414 nodes) | `e46319f0…f2f9b` |
| `generate.py` | `16a4b17e…379ec` |

The full hashes of the answers, prompts, patches and `edges.json` are pinned in `tests/test_dogfood_study2.py`. `fixture.prepare_copy` refuses a placed tree whose manifest differs.

#### The build, against the locked parameters

- **§3 size:** 140 items, 90 skills, 60 monsters, 30 encounters, each kind with `count_target ≥ 20` and a `data_dir`. 94 non-content tokens in 12 namespaces. 15 subfiles.
- **§4 graph:** the locked edge types and degrees are asserted at build. The deepest reverse closure is ≥ 4.
- **§5 determinism:** `generate.py --check` and a pytest reproduce the output byte for byte.
- **§6 lint:** 0 errors and 0 warnings under both the matrix `gdmd` and the v0.3 `gdmd`, with identical JSON output (2 info findings, both advisory invariants).
  - The judge agrees on every study-2 copy, in both worlds, before and after both patches.
  - Beyond the lock: all 340 frontmatter blocks validate against the JSON Schema, and all 320 entities validate against their content-schemas.
- **§9 statuses:** 7 prototyped tokens in 5 prototyped subfiles, each with `implemented_in` pointing at an existing stub under `impl/lanternfall/`:
  - `clocks.lantern_burn`, `rules.gutter_check`, `rules.resolve_strike`, `rules.roll_drops`, `rules.resolve_salvage`, `distributions.drop_quality`, `distributions.strike_roll`;
  - every other token and all 320 entities are `draft`.
- **§8 cross-check:** it ran once and agreed on the first run, so nothing was fixed.
  - Planted edges equal the linter's value edges (`walk_refs` + `Tree` resolution).
  - The lookups match `gdmd view`'s BFS; the impact answers match `gdmd graph --impact`.

#### The questions

Each question was chosen deterministically, by the seeded RNG, among the candidates meeting the locked ranges.

| Task | Question | Answer | Candidates | Evidence files |
| --- | --- | ---: | ---: | ---: |
| `s2_lookup_forward` | Q1: items exactly 2 from `{entities.encounters.lich_hollow}` | 4 | 29 | 3 |
| | Q2: distributions exactly 3 from `{entities.encounters.pale_den}` | 4 | 24 | 8 |
| `s2_lookup_backward` | Q1: content entities within 2 of `{distributions.candlegrit_roll}` | 6 | 9 | 6 |
| | Q2: content entities within 3 of `{entities.skills.fen_wail}` | 6 | 53 | 6 |
| `s2_impact_tokens` | value-edge reverse closure of `{distributions.barrowchill_roll}` | 12, 4 content kinds | 9 | 10 |
| `s2_impact_files` | subfiles of the closure of `{entities.items.iron_buckler}` | 4 | 10 | 10 |
| `s2_maintenance` | the refactored `impl/lanternfall/loot/drop_tables.py`; touch `gdd/systems/loot.md` and `gdd/systems/distributions.md` | 2 | | |
| `s2_negative_control` | a docstring in `impl/lanternfall/tests/test_drop_tables.py`; touch nothing | 0 | | |

#### Hand traces (one question per task, read from the frozen files with `cat` and `grep`; no generator or `gdmd` code)

1. **`s2_lookup_forward` Q1.**
   - `content/encounters/lich_hollow.yaml:11-12` lists `lich_lurker` and `tallow_shade`, and `:13` names `shallows_pack`, whose definition carries no references.
   - `lich_lurker.yaml:14` drops `umber_ring`.
   - `tallow_shade.yaml:14-16` drops `dusk_dirk`, `iron_sigil` and `sable_sigil`.
   - Items at exactly 2: those 4. Equal to the frozen answer.
2. **`s2_lookup_backward` Q1.**
   - Hop 1: `grave_sear` and `sable_bolt` are the only files whose values name `{distributions.candlegrit_roll}`; no subfile value does.
   - Hop 2: `grave_sear` is used by `gloam_revenant`, `moth_hound` and `wick_shade`; `sable_bolt` by `vesper_ghoul`. No item grants either skill.
   - 2 skills + 4 monsters. Equal.
3. **`s2_impact_tokens`.** The reverse closure, hop by hop, excluding prose:
   - `ochre_sear` and `ashen_ward` (their `roll:`);
   - `fen_mantle` (grants `ashen_ward`, and is dropped by nothing) and `briny_wisp` (uses `ochre_sear`);
   - encounters `knell_vault` and `soot_sanctum`;
   - `rules.spawn_encounter` (`spawning.md:34`), `verbs.breach_sanctum` (`mechanics.md:130`) and `rules.sanctum_trial` (`bosses.md:24`);
   - `verbs.descend_stair` (`mechanics.md:57`) and `loops.expedition` (`loops.md:51`);
   - `loops.floor_sweep` (`loops.md:30`).

   `loops.expedition` has only prose referrers. 12 tokens. Equal.
4. **`s2_impact_files`.**
   - `iron_buckler` is dropped by `briny_wisp` and `tallow_drudge`.
   - Their encounters are `knell_vault`, `soot_sanctum`, `yew_alcove` and `candle_den` (`spawning.md:52`, `:29`).
   - The closure's tokens sit in exactly `gdd/systems/spawning.md`, `gdd/mechanics.md`, `gdd/systems/bosses.md` and `gdd/loops.md`. Equal.
5. **`s2_maintenance`.** Every `implemented_in` and pointer naming `loot/` or `drop_tables`:
   - `loot.md:7` (file glob `impl/lanternfall/loot/**/*.py`) and `:20` (`rules.roll_drops`);
   - `distributions.md:7` (file entry) and `:225` (`distributions.drop_quality`);
   - the root pointer `game-design.md:46`, where the root has no `last_verified`.

   No other file-level glob matches. Equal.
6. **`s2_negative_control`.**
   - The 12 file-level entries (in 11 subfiles) and 4 root pointers name `wick.py`, `spawning/`, `balance/`, `feel/`, `core/loops/`, `core/`, `combat/`, `lantern/`, `bosses/`, `rng/`, `loot/drop_tables.py` and `loot/`.
   - Token-level entries are all explicit files.
   - Nothing covers `impl/lanternfall/tests/`.

#### Construction decisions and one exception, recorded before the pilot

1. **§7 leak rule: an exception for the collection tokens.**
   - **What hit:** the check finds one tree token id in what `CLAUDE.md` imports, `{entities.items}`. It is in spec §4.1's `instance_container` example (`docs/spec.md:231`), in both worlds.
   - **Why it is exempted:** `entities.items` is the collection token whose name §3 fixes. It is never a question's start or answer, and no answer depends on it:
     - collection tokens carry no references, so no reverse closure passes through them;
     - the test asserts it is in no start and no answer.
   - **Scope:** the exemption covers the four collection tokens only; every other id, full or bare (compound), is checked in both worlds.
   - **Counterfactual adoption:** it is decided before any study-2 data, and renaming a locked kind to avoid it would itself be a change to §3. It would be adopted whatever the results.
2. **Construction choices within §4 and the task table (not changes to locked parameters):**
   - Forward "exactly k" questions also require the walk set to equal the BFS layer, so the literal and shortest-path readings agree.
   - Verb↔rule pairs are 1:1. Clock-driven rules reference the monster collection, not individual monsters, so no content closure runs through the clock↔rule cycle.
   - The four answer tasks use distinct start tokens.
   - Answer parsing tolerates braces, backticks, bullets, one-line comma lists and repo-relative paths, as study 1's `lookup_refs` did.
   - Content entities carry `last_verified` (§2.3).

#### The worlds at the freeze

- **V2 `views`, C2 `import-full`:** the matrix-world `CLAUDE.md` is forced to `@docs/spec.md`.
- **C2 `import-card`:** swaps in the in-copy card. Only its copies carry `docs/spec-card.md` (amendment 4).
- **Matrix-world `AGENTS.md`:** carries the view/graph line and the spec-editing rule (`4905b97`).
- **V2 `baseline`:** runs on the `v0.3.0` layer.
- **Caps:** 80 turns, 1800 s and $5.00 per run (`run.py --study 2`).
- **Δ:** re-probed at this commit, before the pilot.

**Not changed:** the hypotheses, cells, primaries, thresholds and verdict mapping.

### Pilot reads (2026-09-30), not evidence

The pilot is run `pilot-s2-20260930`: the baseline arm (v0.3 world), one run per study-2 task, at the freeze commit `e429173`, CLI 2.1.285, caps 80 turns / 1800 s / $5.00. Results are in `benchmark/dogfood/results/pilot-s2-20260930*`. As in study 1, these are read only as apparatus validation and a cost estimate.

- **Dry run first** (no model calls): all 24 cells (6 tasks × `baseline`, `views`, `import-full`, `import-card`) built at `e429173`, with the judge agreeing on every copy. Flags validated against 2.1.285. Every `import-card` copy carries the card `7c280fa1…`, the one Rule C used.
- **Δ re-probed at the freeze commit** (`import-probe-probe5-20260930.json`):
  - matrix world: **52,645 tokens**, so C2's PASS threshold is 26,322;
  - v0.3 world: 45,975;
  - probe4 at the Rule C commit read 52,651. The copies differ in AGENTS.md (the card-regeneration line and the new authoring rule), which both sides of the differential carry.
- **Apparatus:**
  - 6 of 6 runs completed, passed the context check and produced a checker report.
  - Logs archived outside the repo (24 files, `pilot-s2-20260930.tar.xz`).
  - **Out-of-copy access:** 20 entries, none naming the harness, so no contamination. Most are a category study 1 did not show: on these larger tasks the subject wrote intermediate lists to Claude Code's own per-session scratchpad (`/tmp/claude-1000/<copy>/<session>/`, outside the copy) and read them back. It is per session, so nothing carries between runs, and the checkers only see the copy. The rest are one mistyped copy path and one `../..`. Listed, not penalized, as D-025 prescribes.
- **Outcomes:** 6 of 6 successes, every question exact (Jaccard 1.0). The maintenance run bumped exactly `loot.md` and `distributions.md`; the control run left the copy unchanged.
- **Caps:** none bound. The maxima were 15 of 80 turns, 95 of 1800 s and $0.70 of $5.00. **No cap is raised.**
- **Workload:** 3–15 turns and 6.0–32.7 KB of tool results per run, against 1.5–16 KB in study 1's pilot. Median per-turn occupancy was 74.9k–85.7k tokens. Descriptive only; the baseline alone says nothing about H2-V.
- **Cost estimate** (each task's pilot cost standing in for its cells; $3.21 for one run of each of the six tasks):
  - **V2 (36 runs):** ≈ $20, taking the views arm about 7% above baseline as in study 1. Plus ≈ $2.9 if the guarded extension triggers (8 runs).
  - **C2 (36 runs):** ≈ $14.
    - `import-full` ≈ $10: the matrix-world spec import is about 7% larger than v0.3's.
    - `import-card` ≈ $4: Rule C's median card/full cost ratio is 0.40.
    - Upper bound at baseline cost for every cell: $19.3. Plus ≈ $2.9 for the extension.
  - **Total:** ≈ $34, at most about $45 with both extensions.
  - **Wall-clock:** about 27 minutes per matrix, run sequentially.
- **Stop:** per the order of operations, the study-2 matrices wait for approval.

### Amendment 6 (2026-09-30, after the study-2 pilot, before any study-2 matrix data): copies carry no file that names study 2's questions

- **Found:** while preparing the matrices, after the user approved them and before any matrix run. This change was not part of that approval; it is recorded here before any matrix data and reported at the post-matrix review.
- **The defect:** every copy carried `DECISIONS.md`.
  - Since the freeze (`e429173`), its amendment 5 names every question's start token (the question table). Its hand traces give the full answers to 4 of the 6 answer questions (both lookup Q1s and both impact tasks), and the table names the maintenance and control tasks' expected edits.
  - A `grep -rn <start token> .` from the copy root would have returned them.
  - D-026 §1 keeps the generator and the answers out of every copy. §7's leak check covered only what `CLAUDE.md` imports, so it could not see a file the subject has to go and read.
  - `tests/test_dogfood_study2.py` was in every copy too. It names no tree id, but it is harness.
- **Nothing so far was affected:** none of the 71 dogfood sessions (study 1's pilot and both of its matrices, study 2's pilot) read `DECISIONS.md` or received any of its text in a tool result. Study 2's pilot subjects kept their searches inside `examples/lanternfall/`.
- **The change:**
  - `fixture.EXCLUDE_FROM_COPY` gains `DECISIONS.md` and `tests/test_dogfood_study2.py`, for every copy in both worlds.
  - D-025's contamination rule extends to them: an out-of-copy access naming `DECISIONS.md` or `test_dogfood_study2.py` counts (`analyze.HARNESS_MARKERS`).
  - `run.py` treats the study-2 test as harness, so a real run refuses to start while it has uncommitted changes.
- **Why remove the file rather than redact it:**
  - Redacting amendment 5's question table and hand traces would keep the rest of the file. But every later note that names an id would need the same care, and the copy would carry a partial file.
  - No subject read the file in 71 sessions, so removing it takes away nothing a subject was observed to use.
  - It also takes v0.4's design text (D-027) out of the v0.3 world.
- **Tests** (`tests/test_dogfood_study2.py`):
  - **Every study-2 cell type:** baseline (v0.3 world), views and import-full (matrix world), and import-card with its card. No copy file outside `examples/lanternfall/` names a question's start, answer or impact closure, by §7's convention (the full id, or the bare id when compound).
    - Three files match by coincidence: `loops.expedition` in the platformer benchmark (two files) and `rules.spawn_encounter` in the party-rpg example. These are those trees' own tokens, which predate the generator (May 2026), and they are pinned.
  - **Proof of fire:** the same scan finds more than 30 question ids in the repo's `DECISIONS.md`.
  - **Contamination:** reading the real repo's `DECISIONS.md` or the study-2 test counts.
- **Study 1 is unaffected.** Its runs are complete, and its verdicts recomputed with the new markers are byte-identical (Rule V NULL, Rule C PASS).
- **Counterfactual adoption:** decided before any study-2 matrix data, and identical across arms and cells. It would be adopted whatever the results.
- **Report limit, reworded:** study 1's "possible awareness effect from reading `DECISIONS.md`" becomes, for study 2, awareness from `CHANGELOG.md` and the case studies. They describe study 2 but name no question id.
- **Not changed:**
  - the tree (manifest `718e52d2…`), tasks, prompts, answers, cells, primaries, thresholds and verdict mapping;
  - Δ: `DECISIONS.md` is not imported, and the import layer (`CLAUDE.md`, `AGENTS.md`, the spec, the schema, the deckbuilder root, `src/`) is unchanged.
- **Approved retroactively** by the user at the study-2 review (2026-09-30), after both matrices.
- **Process note (every future dogfood or benchmark run).** An apparatus problem found between a run's approval and the run means **stop and ask**, unless the fix is purely mechanical.
  - **Purely mechanical** means the fix changes none of these:
    - what a copy contains;
    - what a cell, arm or task is;
    - what a rule, metric, threshold or classification computes;
    - what a subject can see or do.

    A crash fix, a path typo in the harness, or a log-format fix qualifies.
  - **Anything else is an apparatus decision** and goes back to the person who approved the run, even when the fix seems obvious.
  - **Amendment 6 was not mechanical.** It removed a file from every copy. It should have been asked about before the matrices, not reported after them.
  - Why: an approval covers the apparatus as it stood when it was given, and a pre-registered design is only as good as the approvals behind its changes.

### Amendment 7 (2026-09-30, before any study-2 matrix data): another session's scratchpad is contamination

- **Decided:** by the user at the pilot review: "before the matrices, verify each run touches only its own session's scratchpad directory. Extend the out-of-copy detector: access to another session's scratchpad counts as contamination under D-025's rule, and is tested. Own-session scratchpad use stays listed, not penalized."
- **Why:**
  - Claude Code keeps a scratchpad per session outside the copy, at `/tmp/claude-<uid>/<cwd slug>/<session id>/`, and the directories outlive their sessions. The study-2 pilot's are still on disk, with the subjects' scripts and intermediate lists.
  - A run that read another session's directory, above all another repeat of the same task, would be reading another subject's work.
- **The rule** (`analyze.scratchpad_access`, applied by `analyze.contaminated`):
  - **Scratchpad paths** are paths with a `claude-<uid>` component, absolute or relative, including a glob on the uid.
  - **Own:** the next component is the directory Claude Code keys by the run's copy: the slug of `<workdir>/<run_id>/<cell_id>/repo`, with every non-alphanumeric character turned into `-`.
    - Copy paths are single-use, so this directory holds only this run's sessions: the subject's (its pinned `--session-id`) and an empty one the CLI creates at startup.
    - "Own" means that directory rather than the session-id directory, because the empty startup directory belongs to the same run.
  - **Other:** any other directory under the root, or the root itself, whose listing shows every other session. It is contamination under D-025: the run is not-success and listed, and more than 10% in an arm makes the verdict NULL (apparatus). A denied attempt also counts.
  - **Residual:** a search rooted above the root (for example `grep -r … /tmp`) is listed as out-of-copy access but not counted, because its path does not name the scratchpad root. The report lists every such case.
- **Verification on the existing runs:**
  - **Study 2's pilot:** 18 scratchpad accesses in 3 runs (`s2_impact_files` 6, `s2_impact_tokens` 5, `s2_lookup_backward` 7). Every one is inside the run's own session-id directory; none is anywhere else.
  - **Study 1 (65 runs):** no scratchpad access. Its verdicts, recomputed, are byte-identical.
- **Tests** (`tests/test_dogfood_study2.py`):
  - 13 classified paths: the subject's file, the CLI's startup directory and the copy's own directory are own. The next repeat, another run's cell, the operator's session, the root with and without a slash, and globs on the slug or uid are other, and so is a relative `../../claude-1000/…`. Paths outside the scratchpad root are neither.
  - Rule V2 counts another session's scratchpad as not-success and lists only that path; the run's own use is not listed.
  - **The pilot's real paths:** all 18 are own. Re-keyed to the next repeat's cell, the same 18 are contamination (proof of fire).
- **Not changed:** the copies, cells, primaries, thresholds and verdict mapping.

### Review decisions at the pilot (2026-09-30), before any matrix data

The user accepted items 1–6 of the Rule C review and the study-2 freeze, then decided:

1. **The `{entities.items}` leak exemption:** accepted as amendment 5 records it.
2. **Tasks the pilot's baseline answered exactly:** no change; the tasks run as locked.
   - `dogfood-02.md` states this limit: at ceiling success, the non-inferiority clause is weak. It allows one fewer success out of 18, which few failures can test. So C2 is a weaker re-test of the card than designed.
   - The limit is recorded here before any matrix data. The report states it whatever the results.
3. **Scratchpads:** the check is amendment 7.
4. **Clock-driven rules reference the monster collection.**
   - Amendment 5 records this as a construction choice made before the pilot ("Construction decisions and one exception, recorded before the pilot", item 2).
   - The depth ≥ 4 check ran on the output that includes it: the generator's build refuses a tree whose deepest reverse closure is below 4. Amendment 5 states "≥ 4" but gives neither the number nor its relation to the choice. That link is recorded here as a note before the matrices, with no tree change; the manifest `718e52d2…` stands.
   - **Measured now** by a BFS over the frozen `edges.json` (not generator code):
     - the deepest reverse closure is **7**, from `{entities.skills.yew_bolt}`;
     - it is still 7 with the clock node removed, so the depth does not come from the clock↔rule cycle;
     - 285 of the 414 nodes have a reverse closure of depth ≥ 4;
     - the two impact questions' closures reach depths 6 (`{distributions.barrowchill_roll}`) and 5 (`{entities.items.iron_buckler}`), and neither contains a clock node.
5. **The survival tree's `sleep_through_night`:** logged as OI-008, a tree fix for later.

**The matrix commit.** The matrices run at the commit that carries this note (HEAD when each run starts), because amendments 6 and 7 must be committed before a real run. A copy at that commit carries the same files as a copy at the freeze commit `e429173`, with two differences:

- `CHANGELOG.md` has these entries;
- `DECISIONS.md` and the study-2 test are no longer carried (amendment 6).

The tree, the tooling layer, the import layer and every task file are byte-identical to `e429173`. So Δ, re-probed at `e429173`, stands: 52,645 tokens, and C2's PASS threshold is 26,322.

### Rule V2 result (2026-09-30): **PASS**

- **Run** `rulev2-20260930` at `68b15eb`: 36 runs, CLI 2.1.285, `claude-sonnet-5-5`. The report is [`docs/case-studies/dogfood-02.md`](docs/case-studies/dogfood-02.md), and the data is in `benchmark/dogfood/results/rulev2-20260930*` (`7f2b1b4`).
- **Verdict:** R = 33.3% ≥ X = 30%, so **PASS**.
  - With six tasks the median is the mean of the middle two per-task values, +7.4% and +59.3%. The 30% line falls between them.
  - Non-inferiority holds. Views had 18/18 successes. Baseline had 18/18 completed successes but 17/18 counted, because one run is contaminated under amendment 7 (below). Guarded `e_t` = 0 for both tasks, so no extension ran.
  - No apparatus NULL: 0 errors, 1/18 contaminated in the baseline arm (5.6%), and a manipulation-check median of 1.
  - Computed by `analyze.py rule-v2` as committed before any study-2 data (`048fc32`). Nothing was re-run, added or dropped.
- **The contaminated run** (`s2_lookup_backward` baseline r3):
  - It is a denied `python3 /tmp/claude-1000/*/2ff46112*/scratchpad/g.py`. The glob sits in the copy-key position and is combined with the run's own session id, so it could only match the run's own directory.
  - The rule as committed counts it, and it is reported that way. Its effect on the verdict is nil: contamination does not enter `R`, and non-inferiority holds with either classification.
  - **Refined afterwards by amendment 8,** for future runs. Recomputed with the refined detector, V2 counts 0 contaminated runs and baseline 18/18, with the verdict unchanged. This recorded result stands as committed.
- **Consequence:** no adoption consequence (D-026).
  - The PASS licenses a views-cost claim scoped as measured: on a content-heavy tree, on these six tasks, the v0.4 world with the views arm consumed a median 33% fewer consultation bytes than the v0.3 baseline, without loss of success.
  - Where the claim is stated (README, release notes) is left for review.
- **Descriptive only:**
  - `r_t` is +59% to +92% on the three graph-shaped tasks (both impact tasks and the backward lookup), +7.4% on the forward lookup, and −53% and −126% on the guarded tasks, where views added one overview or `--grep` call.
  - `graph` produced 22.2% of the views arm's consultation bytes; `--full` was never used.

### Rule C2 result (2026-09-30): **PASS**

- **Run** `rulec2-20260930` at `68b15eb`, the same commit as V2: 36 runs. The report is [`docs/case-studies/dogfood-02.md`](docs/case-studies/dogfood-02.md), and the data is in `benchmark/dogfood/results/rulec2-20260930*` (`c2291f2`).
- **Verdict:** D = 47,158.5 tokens against 0.5 × Δ = 26,322.5 (Δ = 52,645, `import-probe-probe5-20260930`), so **PASS**.
  - Per-task `d_t` runs from 44,619 to 49,157 tokens, 85–93% of Δ. Study 1's Rule C measured D = 46,769.
  - Non-inferiority holds: 18/18 successes in each cell, and guarded `e_t` = 0 for both tasks, so no extension ran.
  - No apparatus NULL: 0 errors and 0 contaminated runs.
  - Computed by `analyze.py rule-c2` as committed before any study-2 data (`048fc32`). Nothing was re-run, added or dropped.
- **Consequence (the adoption linkage above):** C2 PASS means the card stays. `CLAUDE.md` has imported the card since `49b53b4`, so nothing changes and there is no commit.
- **Descriptive:**
  - No `import-card` run called `gdmd spec --section`, and neither cell read any file under `docs/`.
  - The card cell consulted more tree text (11.3 vs 8.4 KB per run, median) and cost less ($0.19 vs $0.42).
  - Both cells used `view` / `graph` without being told to (33 and 22 calls, 12 of 18 runs each). Study 1's Rule C had none.
- **Limit recorded at the pilot review:** every run succeeded, so non-inferiority was tested only at the ceiling. C2 is a weaker re-test of the card than designed.

### Amendment 8 (2026-09-30, after study 2's results; effective for future runs): the scratchpad detector recognizes a glob that names the run's own session

- **Decided:** by the user at the study-2 review: "apply the own-session-id glob fix with tests, as an amendment effective for future runs. V2's recorded result stays as committed."
- **The defect:**
  - Amendment 7 counts any scratchpad path whose copy-key component is not the run's own as another session's.
  - In V2 one subject ran `python3 /tmp/claude-1000/*/2ff46112*/scratchpad/g.py`: a glob in the copy-key position followed by the first 8 characters of its own session id. Claude Code refused it.
  - That pattern can only match the run's own session directory, but the rule counted it as contamination.
- **The change** (`analyze.scratchpad_access`): a glob in the copy-key position is own use when the next component names the run's own session id.
  - Its literal prefix, before the first glob character, must be at least 8 characters of that id (32 bits of a UUIDv4), and the whole pattern must match the id.
  - Everything else amendment 7 counts is unchanged: a literal other copy key, the root, globs that stop short of 8 characters or name another id, and `*/*`.
- **Effect on recorded results: none.**
  - V2's result above stands as committed.
  - Recomputed with the refined detector, V2 gives PASS with R unchanged, 0 contaminated runs and baseline 18/18 (a pinned test).
  - C2 and both study-1 verdicts recompute byte-identical.
- **Tests:** six new classified paths (the V2 case, a uid glob with the full id, too short a prefix, another session's prefix, `*/*`, and a literal other key with the own id), plus the V2 recomputation.
- **Counterfactual adoption:** made after the results, but it changes no recorded verdict, and it applies only to runs not yet made.

---

## D-027 — `gdmd view` + `gdmd graph`: projected views over a tree (WS2)

- **Status:** decided (2026-09-30) at v0.4 Checkpoint 3. The draft was reviewed by the user; the review's changes are incorporated below, and its answers to the open points are recorded at the end. Implementation follows in its own commits.
- **Spec:** §9.9.
- **Related:** kickoff WS2 and plan amendments 4 (`graph`) and 8 (`decision` deferred); D-024 (the card points at both commands); D-025 / D-026 (the views arm); OI-001, OI-002, OI-004, OI-006 (resolution constraints).

### Decisions

1. **Tooling, not format.**
   - No namespace, schema field or tree file is added. A v0.3 tree is viewable unchanged.
   - Views are a consultation interface over the existing format, which is why the spec text lives in §9 (CLI), not §2–§8.
2. **One compiler, several consumers.** One IR and one reference graph serve `view`, `graph`, WS3's `hook check --show-tokens` (whose `Reference.location` is already the primary coordinate) and the WS4 card's pointers. The pipeline mirrors VCC's lex → parse → IR → lower → emit.
3. **Positions come from composing, not from a second parser.**
   - Frontmatter is composed with `GdmdLoader` (`yaml.compose`) and constructed from the node graph, so each file is parsed once and keeps its YAML-1.1 boolean and timestamp strictness (D-001, D-004).
   - The Markdown fence offset (+1 line) maps frontmatter lines to file lines.
   - **Feasibility checked before drafting** (a read-only prototype, not committed), on all 12 in-repo trees:
     - compose + construct equals `loader.read` for every file;
     - all 452 namespace tokens have a line range whose verbatim slice re-parses to the identical value;
     - that slice equals the file's lines at the pointer.

     It took about 50 ms per tree, including the re-parse check.
4. **Reference semantics are the linter's, exactly.**
   - Extraction: `walk_refs` for frontmatter, `TOKEN_REF_RE` for bodies.
   - Resolution: `Tree.has_token`, with the longest-prefix target.
   - Context-local exclusion: `CONTEXT_LOCAL_PREFIXES`.
   - The backlink predicate is the `orphaned-entity` predicate.
   - Why: the backlink-completeness test compares against lint's own data. Two definitions would make that test compare different things, and a view and `lint` could disagree about the tree.
   - Consequences: content entities resolve by parent directory (OI-001). Globs resolve against the tree root (OI-002). Core frontmatter is not tokenized (OI-004). Whole-namespace strings like `"{resources}"` are not references (OI-006 class A); if class A is later decided as a schema fix, views change in the same commit as lint.
5. **Coordinates.**
   - Primary: `{ns.id}` where a token identity exists, otherwise a file anchor (`<path>#<key>`, `<path>#<heading>`).
   - Secondary: `<path>:<start>-<end>`, whole-file 1-based lines, recomputed on every compile. It is the only pointer target.
   - Field paths (`do[0].sample`) are annotations, not coordinates: the reference syntax caps depth at 6 segments, and list indices would make coordinates unstable across edits.
6. **Roles** (closed set): `token`, `invariant`, `content-entity`, `rationale`, `impl`, `meta`.
   - `decision` is deferred, as agreed at plan approval: no game tree has a DECISIONS file, and the root one records format decisions.
   - `meta` is **new relative to the kickoff's list** (approved at review, point (a)). It covers every top-level frontmatter key outside a namespace:
     - file metadata: `status`, `last_verified`, `files`, `core_loop_ref`, content-schema `schema` / `balance_refs` / `data_dir`;
     - the **normative non-namespace keys**: `prng` (D-015 / D-018), `trajectory` (§9.5.5), `verify_targets` and `adapters` (§9.5).

     Without `meta`, the views could not serve the maintenance ritual (`last_verified` with a pointer), and the normative verification and PRNG contracts would have no coordinate.
7. **Nesting, gaps and coverage** (review items 2 and 3).
   - Blocks nest: an `impl` block for a token- or entity-level `implemented_in:` lies inside its token or entity block, and a `###` rationale block lies inside its `##`.
   - `--full` emits each line once, inside its outermost block. `--grep` selects the innermost matching block and shows its ancestors.
   - **Gap lines**, meaning lines outside every outermost block (fences, namespace key lines, comments between tokens, body text before the first `##`), are emitted by `--full` verbatim or as pointer-carrying elisions.
   - So `--full` **covers every non-blank line of every loaded file exactly once**, and a property test enforces it. This closes the gap a block-only projection would leave: an agent using `--full` in place of reading files would otherwise never see a tree's title or its namespace keys.
8. **`tree_sha`** (review item 4). It is the SHA-256 of the sorted manifest of `<tree-relative path>\t<sha256 of bytes>` over the files the loader classifies. It appears in every JSON output and in the `--full` header. It identifies the tree state a pointer belongs to, so a consumer can detect stale pointers without recompiling.
9. **Block extents.**
   - Token blocks include contiguous comment lines directly above the key, because several trees explain tokens in YAML comments (e.g. `distributions.md`), and dropping them would lose authored rationale.
   - Trailing blank and comment lines after the value are excluded; they belong to the gap.
10. **The lowering rule is normative (MUST) in §9.9.2.** Select, truncate, annotate; token values verbatim; every elision carries a pointer. JSON's optional `value` is the loader's own parse, the data lint compiles against, so it is not a second rendering.
11. **Views.**
   - Overview, `--full`, `--grep`, `--ref [--hops N]`, `--flat` and `--json`, as in the kickoff.
   - Plus `--role`, a selection filter that works with every view.
   - The overview lists content entities per kind (count, counts by status, pointer), not one line each. On a D-026-sized tree, per-entity listing would make the overview the largest view. The elision marker names the view that lists them.
12. **Graph.**
    - `--impact` is the reverse closure over all edges, with `rationale` nodes as leaves.
    - `--from/--to` gives shortest paths only, capped by `--max-paths` (default 20). The paths are chosen in a deterministic lexicographic order, and an elision annotation gives the total when there are more (review point (c)).
    - `--cycles` gives SCCs over `value` edges.
    - Formats: `text | json | dot`.
    - The graph is structure only; it adds no semantics (no "depends-on" typing beyond the edge kind).
13. **Determinism and storage.** Output is a pure function of the tree bytes and the arguments. Nothing is written; memoization is in-process only.
14. **Budget** (review point (f)).
    - The spec states only a SHOULD. The numbers live here: **compile + emit ≤ 150 ms in-process per in-repo tree**, which leaves room under a 200 ms CLI wall-clock target that includes interpreter start-up.
    - The measurement is the in-process pytest only; there is no wall-clock CI gate, because wall-clock is machine-dependent.
    - For reference, the Checkpoint 3 prototype composed, constructed and re-parsed all 12 trees in 634 ms total (about 50 ms per tree) on the maintainer's machine.
    - Once D-026's Lanternfall tree is frozen, it joins the budget test, and its timing is reported descriptively in the D-026 freeze amendment. It is not a gate, because the budget was set before that tree existed.
15. **Exit codes.** `2` for a non-resolving `--ref` / `--impact` / `--from` / `--to` argument; otherwise `0`. Views never fail on lint findings.

### Tests (all run in pytest; no model calls)

- **Fixture per view:** golden outputs, text and JSON, for overview, `--full`, `--grep`, `--ref --hops 1/2`, `--flat`, `--role`, and each `graph` mode, on `tests/fixtures/`, not on `examples/` (the "examples realistic, fixtures exhaustive" rule).
- **Verbatim property:** on all 12 trees, every emitted source line equals the file's line at its number, and every token block's slice re-parses to the token's value.
- **Pointer round-trip:** every pointer in every view resolves to exactly the block it claims.
- **Backlink completeness:**
  - For each token `orphaned-entity` checks: zero backlinks ⇔ an orphan finding.
  - Each backlink's reference satisfies the predicate.
  - Every unresolved edge is a `broken-ref` finding, and vice versa.
- **`graph --impact X` ⊇ `view --ref X --hops N` backlinks,** for every token X and N ∈ {1, 2, 3}.
- **Compose equivalence:** the constructed values equal `loader.read`, for every file in the 12 trees.
- **Coverage:** on all 12 trees, every non-blank line of every loaded file appears in `--full` exactly once, verbatim at its line number or inside an elision pointer.
- **Nesting:** no line is emitted twice by `--full`. `--grep` on a line inside an `impl` block selects that `impl` block and shows its token's header.
- **`tree_sha`:** stable across runs; changes when any byte of any loaded file changes; unchanged by an edit to a file the loader does not classify.
- **`--max-paths`:** on a fixture with more shortest paths than the cap, exactly N paths are emitted, in lexicographic order, with the total in the elision annotation.
- **Determinism:** two compiles give byte-identical output.
- **No writes:** the tree's mtimes and file list are unchanged after every command.
- **Budget:** the in-process check above.

### Consequences for the dogfood studies and the docs

- **`arms/views.md`** (review item 7) becomes a **neutral command reference derived from §9.9**: what each command returns, with no advice tuned to any task.
  - A test checks that every flag it names is in §9.9's synopsis.
  - Its SHA-256 is recorded in a D-025 amendment before the Rule V matrix, and the same bytes are reused unchanged for D-026's Rule V2.
  - The harness already refuses the views arm until `gdmd view --help` succeeds in a copy.
- **The v0.3 world** carries none of this, by construction (D-025 item 1).
- **The verb lists** (review item 5).
  - After the rebase onto `main` (D-025 lineage note), §9's list already names all nine shipped verbs.
  - `view` and `graph` join it, and the README's list, **in the commit that registers them**. `scripts/docs_lint.py` (CI) requires both lists to equal the registered click commands, so listing them earlier would turn CI red.

### Review answers (Checkpoint 3, 2026-09-30)

Every point below was answered at review. The draft text follows the answers as recorded.

- **(a) The `meta` role.** File-level frontmatter keys outside namespaces (`status`, `last_verified`, `files`, `core_loop_ref`, content-schema `schema` / `balance_refs`) need a block. Without one, the overview can't show a file's `last_verified` with a pointer, and the core `files:` map has no coordinate.
  - Alternatives: omit them (the views can't serve the maintenance ritual), or fold them into `token` (a role that then no longer means "§3 token").
  - My lean is `meta`. It is observed need: the pilot's maintenance task hinges on `last_verified`.
  - **Answer:** yes. It also covers the normative non-namespace keys (Decision 6).
- **(b) `--impact` includes prose.** `rationale` nodes are included as leaves. My lean is yes: a prose section that names a changing token is exactly what the anti-drift ritual must re-check. `--role` can exclude it. **Answer:** yes.
- **(c) Shortest paths only for `--from/--to`.** All simple paths grow exponentially on dense trees such as D-026's. My lean is shortest only, with `--impact` for "everything reachable". **Answer:** shortest only, plus `--max-paths` (default 20) with an elision annotation giving the total.
- **(d) The overview elides content entities per kind** (Decision 11). **Answer:** yes.
- **(e) Leading comments belong to the token below them** (Decision 9). **Answer:** yes.
- **(f) Budget measurement.** The in-process pytest, plus the spec's CLI wall-clock statement. My lean is not to make wall-clock a hard CI gate. **Answer:** the in-process test only. The spec states a SHOULD with no machine reference, and the numbers live here (Decision 14).
- **Also required at review, and applied:** block nesting (Decision 7); `--full` coverage of gap lines, with a property test (Decisions 7 and 8 and Tests); `tree_sha` (Decision 8); the verb-list update and "DRAFT" dropped from §9.9 (Consequences); a neutral `arms/views.md` whose hash is recorded before the Rule V matrix (Consequences); and a check that the branch was based on current `main` (it was not; it has been rebased; see the D-025 lineage note).

### Implementation notes (WS2)

Choices the spec leaves to the implementation, recorded as they land. None changes a §9.9 rule.

- **Block model** (`src/game_design_md/ir.py`):
  - **One parse per file.** `Tree.load` takes an optional `reader`; the compiler passes `loader.read_positioned`, which returns `read`'s exact values plus the composed node and line offsets. The `Tree` the views use is therefore the `Tree` lint uses, built from the same parse.
  - **Value extents come from the leaves.** A block collection's YAML end mark points at the next token, past trailing comments and blank lines, so a value's last line is the last line of its last scalar or flow collection. A block scalar keeps its `#`-prefixed content lines.
  - **Leading comments** attach to a token only between the previous token's last line and its key line; a comment directly under the namespace key belongs to the first token.
  - **Headings** are ATX headings outside fenced code blocks. Setext headings are not blocks, matching lint's `section-order`, which reads ATX `##` only.
  - **Attribution of references.** A value reference belongs to its outermost frontmatter block (the token, entity or `meta` key), including one inside a nested `impl` block. A prose reference belongs to its innermost rationale section. A prose reference on a gap line (none exist in the 12 trees) has no block; the graph shows it as a `gap` leaf.
  - **A token defined twice** (the same id in two files) resolves to the definition `Tree` registered, the last one loaded, as in lint.
  - **Line numbers** count lines of the file read in text mode (universal newlines), as the loader reads it.
  - **`tree_sha`'s manifest** ends every line, including the last, with `\n`.
  - **Measured:** compile takes 14–44 ms per in-repo tree. On all 12 trees, the 452 token blocks re-parse to their values, value references equal `walk_refs` in order and path, unresolved references equal `broken-ref` findings, and backlinks agree with `orphaned-entity` for every checked token.
- **Views** (`src/game_design_md/view_cmd.py`):
  - **Every verbatim line's number is readable from the output.** A header, a `[gap] <path>:<a>-<b>` marker or an elision marker sets the position, and each following verbatim line is the next line of that file. In `--grep`, an ancestor key line outside the selected block (the namespace key) is therefore printed as a `[gap]` line with its own pointer before the block; printing it after the header would misnumber it.
  - **`--grep` shows matches on gap lines** (D-025 amendment 5; §9.9.3 amended). The first implementation selected blocks only, as §9.9.3 then said, so a namespace key, a comment between tokens or a title that plain `grep` finds was missing: a correctness gap, fixed before any matrix. Contiguous matching gap lines form one `gap` selection, printed under its `[file]` with a `[gap] <path>:<a>-<b>` pointer and its ancestor key lines. `--role` excludes gap selections. Context lines (the namespace key) print once per file, so no line is printed twice; a property test checks every match is shown exactly once on all 12 trees.
  - **Primary-coordinate matches** select a block with no matching lines; it is shown as its header plus one elision marker.
  - **`--ref`** lists the forward references of the focus block (with nested blocks), then its backlinks (hop 1). With `--hops N`, each further hop lists the forward and the backward neighbors separately, so every backward entry is a pure reverse chain, as `graph --impact` computes it.
  - **`--role`** filters what each view selects: overview sections (other roles are listed under `blocks:`), `--full`'s blocks (with no gap lines), `--grep`'s innermost selection, `--ref`'s neighbors (the focus is always shown), and `--flat`'s rows.
  - **The overview's file list** omits content-entity files, which are counted per kind (Decision 11).
  - **Headers** append `status=<status>` when the block has one and `explains={ns.id}` for an attributed rationale section. Both are annotations.
  - **Measured:** `--full` is 23–38% larger than the files it projects (deckbuilder: 68,282 vs 49,343 bytes), mostly block headers; every one-line `meta` key gets its own header. The overview is 4–6 KB.
- **Graph** (`src/game_design_md/graph_cmd.py`):
  - **One step definition for both directions.** `graph` and `view --ref` call the same `Model.targets` (forward: an occurrence's longest-prefix target) and `Model.referrers` (backward: the backlink predicate). The two directions are not mirror images: a reference to `{entities.cards.ember_strike}` is an edge to the entity, and it is also a backlink of `{entities.cards}`, because the predicate is a prefix match. `--impact` follows the predicate, so it contains every `--ref` backlink.
  - **Edges** exist only for references whose target is a registered token. A `broken-ref` with a valid token prefix is on the edge to that token and keeps its `unresolved` outcome; a reference with no token prefix has no edge.
  - **`--from/--to`** counts every shortest path by dynamic programming and enumerates only the first `--max-paths`, depth-first in lexicographic order of (primary, pointer). The count is exact even when enumerating every path would be exponential.
  - **`--cycles`** runs Tarjan's algorithm over edges that carry at least one `value` reference; a self-referencing node is a cycle of one.
  - **In the in-repo trees**, `--cycles` finds 56 components. 50 are the two-way links the format declares by design: 46 verb ↔ rule pairs (a verb's `effects` resolve a rule whose `given.verb` names the verb) and 4 clock ↔ rule pairs (`drives` / `given.driver`, §4.7). One is a `resources` ↔ `balance_targets` pair. Five are larger components that also run through `states` and `events` (up to 22 nodes). Cycles are structure, reported without judgment; no lint rule concerns them.
- **Tests** (all of D-027's list, in pytest, no model calls):
  - Properties on the 12 trees: `tests/test_ir.py`, `tests/test_view.py` and `tests/test_graph.py`.
  - Goldens: `tests/test_views_golden.py` pins every view and graph mode, text and JSON (plus DOT for graph), on the hand-written tree `tests/fixtures/views/tree/`. The tree carries a gap-line reference, resolved / unresolved / context-local references, nested `impl` blocks, an attributed `###` section, a leading comment, a block scalar with a `#` line, two content entities, and two shortest paths between one pair. A guard test checks that these are present. `GDMD_UPDATE_GOLDENS=1` regenerates; the diff is reviewed before it is committed.
  - Budget: compile + `--full --json` + the whole graph, best of 3, is 12–42 ms per in-repo tree against the 150 ms budget.

---

## D-028 — `gdmd hook check --show-tokens` (WS3)

- **Status:** decided and implemented (2026-09-30).
- **Spec:** §9.7 ("`--show-tokens` (v0.4)").
- **Related:** kickoff WS3 ("print the affected tokens' YAML via the view engine, next to the staged paths; the hook must stay informational: exit 0, under 1 s"); D-027 decision 2 (one compiler for view, graph, the hook and the card); OI-001 / OI-002 (resolution semantics inherited unchanged).

### Decisions

1. **The view engine, not a second renderer.** With the flag, `hook check` compiles the tree once (`ir.compile_tree`) and matches staged paths against that model's `Tree`. It prints blocks with `view_cmd.verbatim_block` under their §9.9 headers. The §9.9.2 lowering rule therefore applies: verbatim lines, and every block carries its pointer. Without the flag, the hook loads the tree as before and its output is byte-identical to v0.3's (tested).
2. **What each reference kind prints:**
   - A token-level `<ns>.<token>` reference prints that token's block, including its nested `impl` header.
   - A file-level reference in a subfile prints that file's `implemented_in:` declaration. Every token in the file may be affected, and printing them all would turn the hook into a `--full` of the file; `gdmd view <tree> --grep` or `--ref` is the follow-up.
   - A file-level reference on a content-entity file prints the whole entity, which is its own token.
   - `implementation_pointers.<key>` prints the core file's `implementation_pointers:` block.
3. **Placement.** Blocks follow each spec file's `locations` / `triggered by` lines, deduplicated and in source order, so the report keeps its v0.3 shape with blocks inserted.
4. **Informational and opt-in.** The command always exits 0, and `gdmd hook install` does not add the flag to the pre-commit entry. Adoption stays the user's choice, and the default hook output does not grow.
5. **Budget.** Under 1 s on every in-repo tree (tested), with the stated 1 s limit as the bound. It takes about 0.16 s wall-clock on tick-combat's real engine paths.

### Tests

`tests/test_hook_show_tokens.py`:
- **Proof of fire on a real tree:** tick-combat's `impl/xtreme/src/rules.rs` prints the core pointer block, the file-level declaration and the `rules.tick_resolution` / `rules.combat_resolution` token blocks, every line verbatim at its number.
- **Default output unchanged:** with the blocks removed, `--show-tokens` output equals the flagless output.
- **All three reference kinds** on the views fixture tree.
- **No match:** silent, exit 0.
- **Under 1 s** on all 12 trees.

---

## D-029 — `gdmd spec --card` / `--section`: the WS4 build

- **Status:** built (2026-09-30), as D-024 §1's ungated build. Adoption stays gated by D-025 Rule C; nothing in the repo imports the card.
- **Spec:** §9.4.
- **Related:** D-024 (the gate, the contents, the completeness test), D-025 (Rule C, whose `import-card` cells generate the card in each copy), D-027 (the card points at `view` / `graph`), D-028.

### Decisions

1. **Selected by structure, copied verbatim.** Every excerpt is chosen by section number plus one of the spec's own lead-in labels. Examples: §3's `**Namespace ownership.**` paragraph with its table, or §8.2's `4. **The session-end agent ritual.**` item. The excerpt is then copied line for line. The card's only fixed text is its labels, its provenance line and its pointers.
2. **Contents** are D-024's list:
   - §3: the opening sentence, the namespace-ownership table, and the resolution, unresolved-reference and context-local paragraphs;
   - §8.1: the status table;
   - §8.2: mechanism 4, the ritual;
   - §9.9: the synopsis of `view` and `graph`.

   Then comes an **index of every numbered section and appendix**, each with its uppercase RFC-2119 keyword count (subsections included) and its `gdmd spec --section <id>` pointer.
   - §1's principles, including "tokens win on conflict", are not excerpted, because D-024's list does not name them. They are reachable through `--section 1`, and both Rule C cells import AGENTS.md, which states them.
3. **Completeness reduces to the index.** Because the index points to every section, D-024's test checks three things:
   - every keyword line lies inside some section the card points to, and that section's `--section` output contains the line;
   - any keyword line outside every section (the preamble has none today) must be in the card itself, or the test fails;
   - the index lists every section, once, in order.
4. **A keyword inside an inline code span is a mention, not a requirement.** An example is §9.4's own sentence listing `` `MUST` ``. It is not counted and is not subject to the test.
5. **Fail loudly.** A missing anchor raises `CardAnchorMissing`, so a spec edit cannot silently empty the card (tested by removing one label).
6. **Provenance:** the card names the sha256 prefix of the spec text it was generated from.
7. **`--section`:**
   - It prints the heading through the line before the next heading of the same or a higher level, trailing blank lines trimmed.
   - Ids are section numbers (with or without `§` or a trailing dot) and appendix letters.
   - Headings inside fenced code blocks, such as the `## High Concept` lines in §5.2 and §7.1, are not sections.
   - An unknown id exits 2.
8. **Not a committed file.** The card is generated on demand. Rule C's `import-card` cells generate it inside each copy from that copy's own `src/` and spec, as D-025 locks.
9. **Size:** 8,491 bytes, against the spec's 139,743 (about 6%).

### Tests

`tests/test_spec_card.py`:
- **Completeness:** all 29 keywords, on 27 lines.
- **Code-span mentions** are skipped.
- **Every excerpt paragraph** is a verbatim substring of the spec.
- **The index** lists every section once, in order.
- **Fence-aware sections;** id forms; subsections are included.
- **A missing anchor** raises.
- **Size under 10% of the spec,** with the provenance hash.
- **CLI:** `--card`, `--section`, exit 2, and mutual exclusion.

---

# Open items

Known issues that are **logged, not decided**. Each one gets its own D-entry when it is resolved; the fix lands in its own commit. Ids are stable (`OI-NNN`) and are never reused.

## D-030 — OI-006 class B: the survival benchmark's verbs declare `time_cost` and `consumes` at the verb level

- **Status:** decided (2026-09-30). A tree-only fix, which D-026 amendment 3 lets land before study 2.
- **Decided:** by the user at the Rule C review: "tree fix in `benchmark/games/survival`, matching the survival starter's schema-valid placement of `time_cost`/`consumes`".
- **Related:** OI-006 (class B), spec §4.2, §4.7 and §10; `$defs.Cost` and `$defs.Verb`; D-012.

### The defect

- **What failed:** the player verbs of `benchmark/games/survival/gdd/mechanics.md` nested `time_cost` (and, on five of them, `consumes`) inside `cost:`.
- **Why it fails:** `$defs.Cost` admits only an integer, a string, or `{resource, amount}`.
- **Count correction:** all **9** player verbs failed, not 8 as OI-006 and the v0.3 correction note said. A recount of the schema errors at `19f6e59` finds the error on every verb, `start_day` included. Both texts are corrected when OI-006 is updated.

### The fix

- **The change:** every verb now has `cost: 0`, with `time_cost:` and `consumes:` as verb-level keys, which `$defs.Verb` admits (`additionalProperties: true`).
  - This is where `templates/starters/survival` puts `time_cost`, also with `cost: 0`.
  - The starter has no `consumes`; it follows `time_cost` to the verb level.
- **Unchanged:** values, token names and references.
- **Why the tree and not the schema:**
  - The starter for the same genre already has the schema-valid shape for the same concept.
  - `cost` is a resource cost. Time and consumed recipe inputs are not `resources` tokens in this tree.
  - Widening `$defs.Cost` to admit arbitrary objects would loosen the schema for one tree.
- **Ritual:** root `version` 0.2.0 → 0.2.1 and `last_updated` 2026-09-30. `last_verified` is not touched, because no referenced code changed (the tree has no implementation).
- **Verification:**
  - The file's schema errors go from 1 (spanning the 9 verbs) to 0.
  - Lint stays 0/0.
  - The all-trees schema pass is re-run after OI-006 class C (see OI-006).

### The clock check (asked at review)

`{clocks.world_time}` declares `delta_source: "actor.last_action_time_cost"`. That is a value captured on the actor, not a verb path. The tree's prose defines it as the fired verb's `time_cost.in_game_minutes`, in five places: `clocks.md`, `loops.md`, `mechanics.md`, `systems/world_time.md`, and the `architecture-invariants.md` rule text.

- **The old nesting disagreed with it.** The value sat at `cost.time_cost.in_game_minutes`, so the path the prose names existed on no verb.
- **After the fix it exists on 8 of the 9 verbs.** `sleep_through_night` declares `time_cost: { in_game_hours: hours_until_dawn }`, a different unit with a symbolic value, so it still has no `time_cost.in_game_minutes`. How the clock reads a sleep is a content question, not a placement one, and it is not changed here.
- **The capture itself is only in prose.** The starter reads the verb directly (`delta_source: "verb.time_cost.in_game_minutes"`); the benchmark reads through the actor, whose entity does not declare `last_action_time_cost`. Context-local references are bound at apply time (D-012) and lint does not resolve them. Not changed.

**Observed, not changed:** the file's `## Tokens` counts are stale. For example, it says "11 verbs", and the file declares 9.

## D-031 — OI-006 class C: the party-rpg starter's heroes content-schema gets `data_dir` and `count_target`

- **Status:** decided (2026-09-30). A tree-only fix, which D-026 amendment 3 lets land before study 2.
- **Decided:** by the user at the Rule C review: "tree fix in the party-rpg starter's `heroes.md`: add `data_dir` and `count_target`, mirroring the canonical party-rpg example", with a release-notes line for scaffolded trees.
- **Related:** OI-006 (class C), OI-005 (the unlinked entity), spec §6.1, §9.8 and §11 item 4; `$defs.ContentSchemaFile`.

### The defect

- **What was missing:** `templates/starters/party-rpg/gdd/content/heroes.md` had no `data_dir` and no `count_target`. `$defs.ContentSchemaFile` requires both.
- **Consequences:**
  - `content/heroes/example_hero.yaml` was linked to no content-schema. It was OI-005's one unlinked entity.
  - §11 item 4 failed for the starter and for every tree `gdmd init --genre party-rpg` scaffolded from it.

### The fix

- **The change:** `data_dir: ../../content/heroes` and `count_target: 8`, placed after `schema:`.
- **What "mirroring the canonical example" means here.** `examples/party-rpg` has no heroes collection. Its one content-schema, `items.md`, restates its mechanics entity:
  - `data_dir` is the entity's `data_source`;
  - `count_target` is the entity's own (50 in both);
  - both sit after `schema:`.

  The starter's `heroes.md` now does the same for the starter's own `entities.heroes` (`data_source: ../../content/heroes`, `count_target: 8`). So no value is new. The starter's `items.md` already follows this pattern (30 in both files).
- **Split threshold:** 8 is below §6's mandatory-split threshold of 20. The split is still allowed, and the starter already uses it.
- **Verification:**
  - `heroes.md` now validates against the JSON Schema.
  - `data_dir` resolves to `content/heroes/`. There, `example_hero.yaml` validates against the `schema:`, its `id` equals the file stem, and it has `status` and `implemented_in`.
  - Lint stays 0/0, and its output is unchanged: lint does not read `data_dir` (OI-001).
- **Ritual:**
  - The starter's root `version` stays 0.1.0. A starter's version is the starting version of every tree scaffolded from it, not a revision counter, and all six starters share it.
  - `last_verified` is not touched, because no code changed.
- **Release notes:** the v0.3 correction note gains a section for trees already scaffolded from the v0.3 party-rpg starter, with the fix.

## D-032 — Where the dogfood results may be stated, and how

- **Status:** decided (2026-09-30) by the user at the study-2 review.
- **Related:** D-025 (Rules V and C), D-026 (Rules V2 and C2), spec §9.9.5 and §11.3; `docs/release-notes/v0.4.md`; README.

### Decisions

1. **The spec states no empirical claim.** §9.9.5 keeps deferring to §11.3 ("this section makes no such claim"). It is unchanged.
2. **The v0.4 release notes state the views results together:**
   - study 1 Rule V **NULL**, on the repository's own small trees;
   - study 2 Rule V2 **PASS**, on a content-heavy synthetic tree: a median 33.3% fewer consultation bytes, against a 30% threshold. It was driven by the graph-shaped tasks, the guarded tasks consulted more, and it is not a session-cost claim.
3. **The card result:** Rule C and Rule C2 **PASS**, about 47k fewer tokens per turn. Non-inferiority was tested only at the ceiling.
4. **One descriptive note:** on the large tree, subjects in both C2 cells used `view` / `graph` without the arm text prompting them.
5. **The pairing rule:** study 2's V2 PASS is **never cited without study 1's NULL**, anywhere: README, release notes, commit messages, talks. AGENTS.md lists this as a Maintenance-mode prohibition.
6. **README:** one line in "What's been demonstrated" links both case studies, with the same pairing.

### Why

- The two views results measure the same pinned treatment on two tree regimes. Either one alone misstates what is known.
  - V2 alone reads as "views save a third" without its scope: a synthetic, content-heavy tree, with the effect carried by graph-shaped tasks.
  - V1 alone reads as "views do nothing".
- The spec is normative. An empirical number there would present a measured, scoped, small-n result as a property of the format.

## OI-001 — Content-entity refs resolve by parent directory, not by `data_source` / `data_dir`

- **Logged:** 2026-09-30 (v0.4 WS0).
- **Spec says** (§3 "References into `content/*/*.yaml`"): `{entities.<kind>.<id>}` resolves through the `data_source:` of the matching content-schema file.
- **Code does:** `Tree.load` registers each content-entity file under `p.parent.name` (`src/game_design_md/tree.py`), and `_index_tokens` keys it `entities.<parent-dir>.<id>`. Neither `data_source` nor `data_dir` is consulted.
- **The spec names the field inconsistently:** `data_source` (§3, §4.1, §6 prose, Appendix B) vs `data_dir` (§2.3 table, §6.1 example, the schema's `ContentSchemaFile`, and every in-repo tree).
- **Impact today:** none. In all 12 trees each `data_dir` basename equals the directory name.
- **Constraint for v0.4:** `gdmd view` / `gdmd graph` reuse `Tree` resolution exactly, so the backlink oracle stays one definition. The fix is a separate commit (either the spec text or the code), not part of WS2.

## OI-002 — `implemented_in` globs: the spec says workspace-relative, the code resolves them against the tree root

- **Logged:** 2026-09-30 (v0.4 WS0).
- **Spec says:** "workspace-relative path globs" (§2.3, schema `$defs.ImplementedIn`).
- **Code does:** `rule_broken_implementation_pointer`, `rule_stale_section` and `hook_cmd.build_inverted_index` all expand with `tree.root.glob(pattern)`. They agree with each other, not with the spec. The in-repo trees depend on tree-root semantics, e.g. tick-combat points at `impl/xtreme/...` inside its tree.
- **Constraint for v0.4:** same as OI-001. WS3's `hook check --show-tokens` inherits the current semantics unchanged.

## OI-003 — `prototyped-without-pointer` fires on `balance_targets`, whose schema forbids `implemented_in`

- **Logged:** 2026-09-30 (v0.4 WS0), found while fixing the time-dependent test (commit `f43d357`).
- **Symptom:**
  - The rule iterates every `SUBFILE_NAMESPACES` block and flags active-status tokens with no `implemented_in` on stale files.
  - `$defs.BalanceTarget` has `additionalProperties: false` and no `implemented_in`.
  - So a `balanced` target on a stale file can only be silenced by `gdmd touch`; the §9.1 remedy of a placeholder `implemented_in` is schema-illegal.
  - `invariants` are unaffected: they have no `status`.
- **Impact today:** none in the 12 trees, whose balance targets are all `draft`. It will fire once a tree's targets advance.
- **Proposed fix:** exempt namespaces whose schema forbids `implemented_in` (today, `balance_targets`), plus a test. It changes lint-rule behavior, so it needs its own D-entry. It is scheduled after v0.4 Checkpoint 3.

## OI-004 — Namespaces in the §3 ownership table that `Tree` does not index

- **Logged:** 2026-09-30 (v0.4 WS0).
- **Spec says:** §3's namespace table lists `pillars` and `player_experience_goals` as namespaces (owned by the root / `gdd/pillars.md`), plus `verify_targets` / `adapters`. The §4.1 example uses `schema_ref: "{content_schema.cards}"`.
- **Code does:** `SUBFILE_NAMESPACES` omits all of these, and the core file's frontmatter is not tokenized. A ref such as `{pillars.<id>}` would fire `broken-ref`.
- **Impact today:** none. No in-repo tree references these namespaces.
- **Constraint for v0.4:** views do not index them either (same single-definition constraint as OI-001). The resolution is either to index them or to trim the table. The observed-need discipline applies.

## OI-005 — Lint does not validate content entities against their content-schema (spec §6.2, §11 item 4)

- **Logged:** 2026-09-30 (v0.4, found while designing the dogfood authoring checker).
- **Spec says:** §6.2: "The linter (a) validates each entity against the content-schema-file `schema:`, (b) requires `id` to match the filename stem, and (c) enforces presence of `status` and `implemented_in`." §11 conformance item 4 repeats (a).
- **Code does:** `linter.ALL_RULES` has no such rule. `jsonschema` is a declared runtime dependency (`pyproject.toml`) that nothing in `src/` imports. A card that violates its schema (a wrong `kind`, a missing `rarity`, a mismatched `id`) lints clean unless another rule happens to trip on it.
- **Impact today:** none observed on the 12 in-repo trees. It does matter as a false sense of safety: "lint clean" is weaker than the spec claims.
- **Consequence for v0.4:** the dogfood authoring checker validates new entities against the content-schema itself (jsonschema, id == stem, required keys) instead of trusting lint.
- **Resolution:** a new lint rule. It changes lint behavior, so it needs its own D-entry and commit, with proof-of-fire on real trees (the AGENTS.md maintenance-mode rule). Scheduled after v0.4 Checkpoint 3, alongside OI-003.
- **One-off pass (2026-09-30, read-only, at `3e44035`; requested before the dogfood pilot): not clean.**
  - All 29 entities linked through a content-schema's `data_dir` pass (a) jsonschema validation, (b) `id` == stem, and (c) `status` + `implemented_in`.
  - One entity is linked to no schema. `templates/starters/party-rpg/gdd/content/heroes.md` has no `data_dir`, so `content/heroes/example_hero.yaml` is unchecked (it would validate if linked).
  - A correction note for v0.3's §11 conformance claim is at [`docs/release-notes/v0.3-conformance-correction.md`](docs/release-notes/v0.3-conformance-correction.md). No lint rule is added yet.
  - **Update (2026-09-30):** D-031 links the entity. A re-run at `326cd50` finds 30 linked entities, all passing, and none unlinked (OI-006 progress). The lint rule itself still waits until after study 2.

## OI-006 — Lint does not validate frontmatter against the normative JSON Schema (spec §10); 10 blocks in 8 trees fail it

- **Logged:** 2026-09-30 (v0.4), found by the OI-005 pass. Evidence and reproduction are in [`docs/release-notes/v0.3-conformance-correction.md`](docs/release-notes/v0.3-conformance-correction.md).
- **Spec says:** §10 calls `schema/game-design.schema.json` "the normative frontmatter schema". §11 makes `gdmd lint` exit 0 the first conformance item.
- **Code does:** no schema validation at all (OI-005's `jsonschema` observation). Lint checks some required keys through individual rules, not the schema.
- **Found:** 10 of 158 frontmatter blocks fail, in 8 of the 12 trees; the four canonical examples pass. Three classes:
  - **A.** Whole-namespace `applies_to` refs (`"{resources}"`) in 8 `architecture-invariants.md` files. `$defs.TokenRef` needs 2–6 segments, yet **spec §4.11's own example uses the form**. So this is a spec↔schema contradiction first and a tree issue second.
  - **B.** `cost: { time_cost: …, consumes: … }` on the verbs of `benchmark/games/survival/gdd/mechanics.md`, outside `$defs.Cost`. Logged as 8 verbs; it was all 9 (D-030).
  - **C.** `templates/starters/party-rpg/gdd/content/heroes.md` lacks the required `data_dir` and `count_target` (the root of OI-005's unlinked entity).
- **Resolution:** per class, decide whether the tree or the schema/spec is wrong. Then decide whether lint should run the schema. Either changes lint behavior or tree content, so each gets its own D-entry and commit. Scheduled with OI-005, after v0.4 Checkpoint 3.
- **Progress (2026-09-30): classes B and C are fixed; class A remains.**
  - **B:** fixed in the tree by D-030. **C:** fixed in the starter by D-031, which also links OI-005's unlinked entity.
  - **Re-run of the one-off pass** at `326cd50`, both steps, all 12 trees:
    - 158 frontmatter blocks, **8 fail**. All 8 are class A, the `architecture-invariants.md` files of the 2 benchmark games and the 6 starters, and each fails only on whole-namespace `applies_to` items.
    - 16 content-schemas link 30 entities, and all 30 pass §6.2 (a)–(c). No content entity is unlinked.
  - **Guard:** `tests/test_starter_schema.py`.
    - Every starter's frontmatter must validate. The 6 class-A starter files are strict xfails, so the xfail fails the day one of them validates.
    - A second test pins that whole-namespace `applies_to` is their only error, so the xfail cannot hide another defect.
    - Proof of fire: the pre-D-031 `heroes.md` fails the guard, and an invalid `enforcement:` injected into a class-A file fails the second test.
  - **Remaining, after study 2 (D-026 amendment 3):** the class A decision (spec §4.11's example vs `$defs.TokenRef`), then whether lint runs the schema.

## OI-007 — `gdmd view` / `gdmd graph` usability ideas from study 1 (queued; tool freeze)

- **Logged:** 2026-09-30, from study 1's Rule V traces. These are descriptive observations, not evidence. Under D-026 amendment 3 they wait until study 2's matrices complete; none is in code.
- **Candidates**, each needing observed need and its own D-entry when taken up:
  1. **A `--grep` match cap** (for example `--max-matches N`, with an elision giving the total). One task's subjects searched `energy|\b3\b`, and single calls returned 8–18 KB.
  2. **A count-only mode** (matches per block or file, no lines), so a search can be sized before its lines are fetched.
  3. **`--full` header compaction.** One-line `meta` keys each carry a header, which makes `--full` 23–38% larger than the files (D-025 amendment 5). No study-1 run used `--full`.
  4. **`-i` as an alias of `--ignore-case`.** One subject wrote `--grep -i '<pattern>'`, and `-i` became the pattern.
  5. **Cosmetic, harness only:** under the dogfood shim, click's usage line names `python -m game_design_md` instead of `gdmd`.
- **Evaluation:** any change to view or graph output is a v0.4.x change, evaluated in a later study, never retrofitted into study 1's or study 2's result.

## OI-008 — Survival benchmark: the clock's delta cannot read `sleep_through_night`'s hours-based `time_cost`

- **Logged:** 2026-09-30, from D-030's clock check. The user ruled at the study-2 pilot review that it is a tree fix for later, not now.
- **The tree says:**
  - `{clocks.world_time}` (`benchmark/games/survival/gdd/clocks.md`) declares `delta_source: "actor.last_action_time_cost"`.
  - The tree's prose defines that value as the fired verb's `time_cost.in_game_minutes`.
  - `{verbs.sleep_through_night}` (`gdd/mechanics.md`) declares `time_cost: { in_game_hours: hours_until_dawn }`: another unit, and a symbolic value rather than a number.
- **So:** under the tree's own definition, the clock has no delta to read when the player sleeps. The other 8 verbs declare `time_cost.in_game_minutes` (D-030).
- **Not a schema or lint issue.**
  - `time_cost` is a free verb-level key (`$defs.Verb` admits additional properties).
  - `delta_source` is a context-local path, which lint does not resolve (D-012).
  - The tree lints 0/0 and validates.
- **Resolution (later, its own D-entry):** a tree-content fix, such as expressing the sleep's delta in minutes or making the clock's capture rule explicit for sleep. It is decided with the tree's other stale content, such as the `## Tokens` counts D-030 observed.
  - The benchmark tree is not a study-2 task tree, so study 2 does not block the fix. It is scheduled after study 2 with the lint-hold items, to keep the pre-matrix change set to the decided items.
