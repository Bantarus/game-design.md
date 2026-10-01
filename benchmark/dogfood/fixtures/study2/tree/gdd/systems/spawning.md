---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-04-18"
implemented_in: ["impl/lanternfall/spawning/**/*.py"]
rules:
  spawn_encounter:
    given:
      verb: "{verbs.descend_stair}"
    target_selection: none
    do:
      - sample: "{distributions.depth_band}"
        into: band
      - when_band: 1
        spawn_one_of:
          - "{entities.encounters.iron_ossuary}"
          - "{entities.encounters.lich_hollow}"
          - "{entities.encounters.lich_warren}"
          - "{entities.encounters.sable_alcove}"
          - "{entities.encounters.sable_nave}"
          - "{entities.encounters.sable_ossuary}"
          - "{entities.encounters.umber_alcove}"
          - "{entities.encounters.vesper_barrow}"
      - when_band: 2
        spawn_one_of:
          - "{entities.encounters.briny_alcove}"
          - "{entities.encounters.candle_den}"
          - "{entities.encounters.candle_gallery}"
          - "{entities.encounters.dusk_crypt}"
          - "{entities.encounters.fen_warren}"
          - "{entities.encounters.hollow_ossuary}"
          - "{entities.encounters.knell_vault}"
      - when_band: 3
        spawn_one_of:
          - "{entities.encounters.briny_den}"
          - "{entities.encounters.candle_nave}"
          - "{entities.encounters.grave_warren}"
          - "{entities.encounters.hollow_nave}"
          - "{entities.encounters.iron_hollow}"
          - "{entities.encounters.sable_gallery}"
          - "{entities.encounters.umber_den}"
      - when_band: 4
        spawn_one_of:
          - "{entities.encounters.fen_crypt}"
          - "{entities.encounters.lich_crypt}"
          - "{entities.encounters.pale_den}"
          - "{entities.encounters.vesper_hollow}"
          - "{entities.encounters.vesper_ossuary}"
          - "{entities.encounters.wick_pit}"
          - "{entities.encounters.yew_alcove}"
    outputs: [encounter_spawned]
    status: draft
    implemented_in: ["impl/lanternfall/spawning/spawn_encounter.py"]
  wandering_spawn:
    given:
      driver: "{clocks.lantern_burn}"
      state: "{states.lantern_state.dim}"
    target_selection: none
    do:
      - sample: "{distributions.wander_chance}"
        into: roll
      - { on_hit_spawn_from: "{entities.monsters}", tier: minion }
    outputs: [wanderer_spawned]
    status: draft
    implemented_in: ["impl/lanternfall/spawning/wandering_spawn.py"]
---

## Tokens

Two rules. `spawn_encounter` fires when the lamplighter descends: it samples a depth band, then one of that band's encounters. `wandering_spawn` fires on the lantern clock while the lantern is dim.

## Rationale

**Encounters are authored, spawns are rolled.** Every encounter in `content/encounters/` belongs to exactly one depth band here, except the sanctum, which is entered only through `{verbs.breach_sanctum}`.

**A dim lantern invites company.** Wandering spawns draw any minion from `{entities.monsters}`; they never carry the floor's loot, so fleeing from them is always an option.
