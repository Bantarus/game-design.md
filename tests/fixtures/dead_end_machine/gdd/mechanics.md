---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: prototyped
last_verified: "2026-05-21"
entities:
  player:
    type: actor
    properties: { hp: 10 }
    status: prototyped
    implemented_in: []
  cards:
    type: content_collection
    data_source: ../../content/cards
    count_target: 25
    status: prototyped
verbs:
  do_thing:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.do_thing_rule}" }
    status: prototyped
    implemented_in: []
resources:
  energy:
    scope: per_turn
    min: 0
    max: 1
    velocity_target: "{balance_targets.energy_target}"
    visibility: hud
    status: prototyped
    implemented_in: []
states:
  thing_state:
    initial: a
    nodes:
      - { id: a }
      - { id: trap }
      - { id: b, terminal: true }
    transitions:
      - { from: a, event: go, to: b }
rules:
  do_thing_rule:
    given:
      verb: "{verbs.do_thing}"
    do:
      - sample: "{distributions.test_dist}"
    outputs: []
    status: prototyped
    implemented_in: []
---

## Tokens

`{states.thing_state}` has a non-terminal node `trap` with no outgoing transition.
The linter should flag this with `state-machine-coverage` / `dead-end` at severity `error`.
