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

# Open items

Known issues that are **logged, not decided**. Each one gets its own D-entry when it is resolved; the fix lands in its own commit. Ids are stable (`OI-NNN`) and are never reused.

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

## OI-006 — Lint does not validate frontmatter against the normative JSON Schema (spec §10); 10 blocks in 8 trees fail it

- **Logged:** 2026-09-30 (v0.4), found by the OI-005 pass. Evidence and reproduction are in [`docs/release-notes/v0.3-conformance-correction.md`](docs/release-notes/v0.3-conformance-correction.md).
- **Spec says:** §10 calls `schema/game-design.schema.json` "the normative frontmatter schema". §11 makes `gdmd lint` exit 0 the first conformance item.
- **Code does:** no schema validation at all (OI-005's `jsonschema` observation). Lint checks some required keys through individual rules, not the schema.
- **Found:** 10 of 158 frontmatter blocks fail, in 8 of the 12 trees; the four canonical examples pass. Three classes:
  - **A.** Whole-namespace `applies_to` refs (`"{resources}"`) in 8 `architecture-invariants.md` files. `$defs.TokenRef` needs 2–6 segments, yet **spec §4.11's own example uses the form**. So this is a spec↔schema contradiction first and a tree issue second.
  - **B.** `cost: { time_cost: …, consumes: … }` on 8 verbs of `benchmark/games/survival/gdd/mechanics.md`, outside `$defs.Cost`.
  - **C.** `templates/starters/party-rpg/gdd/content/heroes.md` lacks the required `data_dir` and `count_target` (the root of OI-005's unlinked entity).
- **Resolution:** per class, decide whether the tree or the schema/spec is wrong. Then decide whether lint should run the schema. Either changes lint behavior or tree content, so each gets its own D-entry and commit. Scheduled with OI-005, after v0.4 Checkpoint 3.
