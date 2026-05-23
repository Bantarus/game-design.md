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
