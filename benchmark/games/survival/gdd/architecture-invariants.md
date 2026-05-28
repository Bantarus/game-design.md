---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-23"
implemented_in: ["src/driftwood/**/*"]
invariants:
  integer_resource_quantities:
    kind: numeric_domain
    rule: "All gameplay-state quantities — hp, hunger, thirst, inventory stacks per slot, tool remaining-durability, recipe input counts, world clock minutes, day counter, pyre assembled layers — use integer representation. Floating-point is forbidden anywhere in the inventory, crafting, meter, or world-time path. Presentation may render meter bars with sub-integer interpolation for visual smoothness, but the simulation's authoritative quantity is the integer."
    applies_to:
      - "{resources.hp}"
      - "{resources.hunger}"
      - "{resources.thirst}"
      - "{entities.player}"
      - "{entities.resource_node}"
      - "{entities.pyre}"
    enforcement: lint
    severity: error
  world_time_decoupled_from_wall_clock:
    kind: architectural_pattern
    rule: "The in-game world clock (minutes / hours / day-parts / days) is advanced exclusively by `{clocks.world_time}` (mode: per_verb_delta, spec §4.7) and the `{rules.advance_world_time}` rule it drives, in response to verb-issued `time_cost.in_game_minutes` deltas. No wall-clock timer (system tick, frame counter, real-time elapsed) feeds the world clock. The same player-action sequence produces the same world-clock progression regardless of how long the player took in wall-clock time to issue the actions."
    applies_to:
      - "{loops.action}"
      - "{loops.day}"
      - "{states.world_clock}"
      - "{clocks.world_time}"
    enforcement: lint
    severity: error
  recipe_data_immutable_at_runtime:
    kind: architectural_pattern
    rule: "All recipe data in `content/recipes/*.yaml` is loaded once at game start and treated as immutable thereafter. The runtime MUST NOT mutate recipe inputs, outputs, station_required, tool_required, or in_game_minutes_to_craft. Adding new recipes happens between releases via new YAML files, not at runtime."
    applies_to:
      - "{entities.recipes}"
    enforcement: lint
    severity: error
  data_behavior_separation:
    kind: architectural_pattern
    rule: "Simulation entities (player, resource_node, crafting_station, recipes, pyre) are data-only structures with no embedded methods. All simulation logic — gathering, crafting, eating, drinking, sleeping, station-placing, pyre assembly, time advancement, meter ticking — lives in stateless systems that query entity data and produce next-state data. No simulation logic embedded in renderer, asset pipeline, or input handler. The simulation is a pure function from (action sequence, initial world state) to (per-action state stream)."
    applies_to:
      - "{entities.player}"
      - "{entities.resource_node}"
      - "{entities.crafting_station}"
      - "{entities.pyre}"
      - "{rules}"
    enforcement: advisory
    severity: warning
  save_load_round_trip_complete:
    kind: determinism
    rule: "A run's full state (world clock, player position, inventory contents including per-item durability and per-stack counts, all crafting_station instances and their positions/durabilities, all resource_node remaining_harvests values, pyre.assembled_layers and pyre.lit, day counter, meters) can be serialized to a save file and deserialized back to a state byte-identical to the moment of save. Resuming a loaded run produces the same subsequent state stream as if the run had continued without saving, given the same subsequent action sequence."
    applies_to:
      - "{entities.player}"
      - "{entities.crafting_station}"
      - "{entities.resource_node}"
      - "{entities.pyre}"
      - "{states.world_clock}"
      - "{states.pyre_assembly}"
    enforcement: verify
    severity: error
---

## Tokens

Five invariants govern the codebase. Each declares a *property of the generated code*, not a tool used to generate it. The spec explicitly forbids naming engines, frameworks, or renderers here. Each invariant is anchored in either a specific brief claim or a universal genre necessity that a real engineering team would impose; the trace is in the per-invariant prose below. Per the three-act authoring protocol (pre-reg v6, commit `27a4381`), invariants whose trace reduces to "the spec defines this kind" are forbidden — the trace is the audit.

## Rationale

Per-invariant prose follows. Each `###` heading matches an invariant id in the frontmatter; if you add an invariant to the YAML, add a `###` section here with the same id. Every invariant carries a **brief trace** sentence naming the specific brief claim or universal genre necessity that forces this engineering choice.

### integer_resource_quantities

**Brief trace.** The brief says "Hunger and thirst both start at twelve units, both decrease by one per in-game hour" and "Both are integer counts, no fractions." It also says "wooden axe lasts twelve gathers; pickaxe lasts sixteen mines" and "Stackable raw materials stack eight per slot" — every gameplay-meaningful quantity in the brief is an integer count. Float would introduce drift across saves (a partially-decayed hunger meter saved at 7.4 and reloaded might land at 7.39999) and would push the recipe-input check into a floating-comparison-vs-integer-target ambiguity. The brief's stated integer semantics is the engineering posture.

**Why this specifically:** the same family of float-determinism failure the project fought at the cross-engine simulation layer (libm transcendental ULP drift, F-007 / D-016). The lesson applied here: integers don't drift, and a save-load contract that says "the loaded run resumes byte-identically" needs the underlying quantities to round-trip without precision loss. Integers do; floats don't.

**Statically checkable:** any numeric field in the simulation/inventory/world-time path whose declared type is `float`/`double`/`real` (rather than `int` or a fixed-width integer type) is a violation. The linter scans entity-property declarations, resource bounds, and rule-output types.

### world_time_decoupled_from_wall_clock

**Brief trace.** The brief says "a real-time day is about six minutes wall-clock" — but the *gameplay* is "the in-game day-budget of 24 hours stays fixed" regardless of how long the player took to issue them. The brief explicitly frames the game as a planning game ("Skill is route-planning across the five days") where deliberation is the gameplay. A wall-clock-driven world timer would either: (a) punish a player for thinking (the day ends before they've planned), turning the game into a real-time-survival twitch test the brief explicitly forbids, OR (b) require pausing the world clock on every UI interaction, which is a leakier abstraction than just driving the clock from verb cost.

The brief's commitment that "the in-game clock pauses during deliberation but the day's action budget is still 24 hours regardless of how long the player took to issue them" is the engineering posture. The world clock is action-driven; wall-clock is presentation-only.

**Statically checkable:** scan the world-time advancement code path. The only call site that mutates the world clock minutes/hours/day-part state is `rules.advance_world_time` (which is driven by `{clocks.world_time}`); any other writer to that state is a violation. The linter can verify this once a project's `implementation_pointers` declare the world-time module.

### recipe_data_immutable_at_runtime

**Brief trace.** The brief says "Recipes are fixed and known — there is no recipe discovery, no random outcomes, no failure chance" and "The recipe tree is shown to the player in a recipes panel from the start of run one; nothing is hidden." A runtime-mutable recipe system would invalidate both commitments: it would allow recipe inputs/outputs to change mid-run (failing "fixed and known"), and would make the recipes-panel a moving target (failing "shown from the start").

The engineering posture: recipe YAML files are loaded once at startup into a read-only registry; all `craft_resolution` lookups go through that registry; the registry has no `mutate` method. A new recipe ships as a new YAML file in a release, not at runtime.

**Statically checkable:** scan the recipe-handling code path for any `write`/`update`/`mutate` calls on the recipe registry; any such call is a violation.

### data_behavior_separation

**Brief trace** (universal genre necessity). The brief says "the run saves periodically" — and a save serializer needs to walk the world state and write it to disk. If world state is embedded in objects with methods that have closure-captured renderer or audio state, serialization is intractable: the serializer either tries to save the closure (which fails) or has to special-case unwrap every method-bearing object (which is fragile and breaks every time a new entity type is added). The clean engineering posture for any non-trivial game with mid-run save is **data-only entities + stateless logic in systems** — the save serializer walks the data, no method-state to capture.

**Universal genre necessity** (rule b of the trace discipline). Driftwood's brief doesn't explicitly call for headless replay verification the way Embergrave's does, but the brief's "the run saves periodically" creates the same engineering pressure via a different route: any save-load implementation for a non-trivial world state is much simpler (and much more correct) if entities are pure data and logic is in stateless systems. A real survival-genre team would impose this on day one of engineering planning, even if the brief never said the word "ECS" or "data-oriented." The portfolio also matters: Embergrave covers `data_behavior_separation` under a replay-verification trace; Driftwood covers it under a save-load trace; two different brief-roots leading to the same engineering pattern is itself a finding (this pattern is robust across the two fresh games' design needs).

**Advisory** at v0.2.0-alpha. Static detection requires identifying which source files belong to "simulation entities" vs. "systems" vs. "presentation," which depends on project layout conventions. Promotable to `lint` once a project's `implementation_pointers` declare the layers.

### save_load_round_trip_complete

**Brief trace.** The brief says "the run autosaves periodically — losing twenty minutes of careful gathering to a crash is intolerable" and "The game must be safely interruptible at any in-game moment." A save-load implementation that *loses information* — even a single byte's worth — violates this commitment: the player loaded run is not the same as the saved run, and the careful gathering they preserved across the save is silently corrupted.

The engineering posture: every piece of world state listed in the rule (world clock, player position, inventory including per-item runtime state, all crafting_station instances, all resource_node remaining harvests, pyre layers and lit-flag, day counter, meters) is part of the save format and round-trips byte-identical. Any state the simulation reads but the save doesn't capture is a save-load drift bug — either the state needs to be in the save, or it needs to be derivable from saved state deterministically.

**Why this specifically:** Driftwood's run is thirty minutes; a save-load round-trip that *almost* works (loses 1 hunger unit per load, or shifts a station position by half a tile, or forgets a tool's remaining durability) would make the game's "safely interruptible" promise a lie that the player only discovers after losing a run to it. Like the cross-engine byte-identity bar (D-009, F-007), almost-deterministic is the worst place to be — it works long enough to be trusted and fails after the player has invested.

**Deferred to verify** because static reasoning about save-round-trip completeness requires running the code. The verify adapter would: (1) start a run, run N actions, save; (2) load the save; (3) compare the post-load state to the pre-save state byte-for-byte; (4) run M more actions on both branches and confirm they remain byte-identical. A `gdmd verify` target along these lines is the obvious Phase-3 work for this game.

## Open Questions

- Whether `world_time_decoupled_from_wall_clock` should be `enforcement: advisory` (current is `lint`) given that static detection requires a declared world-time module. Currently lint with the understanding that the project's `implementation_pointers.time:` glob enables the check; an unscoped layout might need to ratchet to advisory until layers are declared.
- Whether `save_load_round_trip_complete` should declare a `verify_target` in `gdd/verification.md` (not yet authored for Driftwood — the verification surface is for Phase 3). v0.1: invariant only; verify target authored in a separate commit when the verification.md file is added.
- Whether to add `state_not_in_presentation` (Embergrave-style layer_boundary) for Driftwood. The brief is silent on a sim/presentation split; the save-load invariant covers most of the practical concern (the save format defines what's "real" world state); adding a separate layer_boundary invariant would be coverage-driven rather than brief-traceable. Currently not declared; explicit choice under the trace rule.
