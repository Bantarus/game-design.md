---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-09-30"
implemented_in: ["src/sim/*.py"]
entities:
  player:
    type: actor
    properties:
      focus: { from: "{resources.focus}" }
    status: draft
  relics:
    type: content_collection
    data_source: ../content/relics
    status: draft
verbs:
  study:
    actor: "{entities.player}"
    cost: { resource: "{resources.focus}", amount: 1 }
    target_schema: { type: "{entities.relics}" }
    effects:
      - resolve: "{rules.study_rule}"
    status: draft
    implemented_in: ["src/sim/study.py"]
  rest:
    actor: "{entities.player}"
    cost: 0
    target_schema: {}
    effects:
      - resolve: "{rules.rest_rule}"
    status: draft
    implemented_in: ["src/sim/rest.py"]
resources:
  # Focus is the only resource: every verb spends or restores it.
  focus:
    scope: per_turn
    min: 0
    max: 5
    velocity_target: "{balance_targets.focus_per_day}"
    visibility: hud
    note: |
      A block scalar.
      # This line is scalar content, not a YAML comment.
    status: draft
    implemented_in: ["src/sim/focus.py"]
rules:
  study_rule:
    given: { verb: "{verbs.study}" }
    do:
      - kind: spend
        amount: "{actor.focus_cost}"
      - kind: inspect
        target: "{entities.relics.lamp}"
    outputs: ["{events.studied}"]
    status: draft
    implemented_in: ["src/sim/rules.py"]
  rest_rule:
    given: { verb: "{verbs.rest}" }
    do:
      - kind: restore
        target: "{resources.focus.nonexistent}"
    outputs: []
    status: draft
    implemented_in: ["src/sim/rules.py"]
events:
  studied: { status: draft, description: "Emitted by {rules.study_rule}." }
# trailing comment after the last namespace
---

## Tokens

`{verbs.study}` and `{verbs.rest}` are the whole verb set.

## Rationale

Focus is scarce so that `{verbs.rest}` matters.

```yaml
## not a heading: inside a code fence
```

### study

Studying the lamp (`{entities.relics.lamp}`) is the core beat.
