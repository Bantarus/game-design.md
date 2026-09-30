---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-04-18"
implemented_in: ["impl/lanternfall/bosses/**/*.py"]
rules:
  boss_awakening:
    given:
      verb: "{verbs.ring_the_knell}"
    target_selection: none
    do:
      - { awaken: "{entities.monsters.lamp_warden}", at_depth: 3 }
      - { awaken: "{entities.monsters.knell_mother}", at_depth: 4 }
    outputs: [boss_awakened]
    status: draft
    implemented_in: ["impl/lanternfall/bosses/awakening.py"]
  sanctum_trial:
    given:
      verb: "{verbs.breach_sanctum}"
    target_selection: none
    do:
      - { enter: "{entities.encounters.soot_sanctum}" }
      - { awaken: "{entities.monsters.soot_king}" }
      - { seal_exit_until: "{states.lantern_state.guttered}" }
    outputs: [sanctum_entered]
    status: draft
    implemented_in: ["impl/lanternfall/bosses/sanctum.py"]
---

## Tokens

Two rules. Ringing the knell wakes the two lair bosses at their depths; breaching the sanctum seals the lamplighter in with the last one.

## Rationale

**Bosses are opt-in until the end.** The lair bosses sleep until the knell is rung, so a cautious expedition can sweep their floors without waking them. The sanctum trial cannot be fled: its exit stays sealed until the lantern gutters or the king falls.
