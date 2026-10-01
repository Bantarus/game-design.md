---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-22"
states:
  thing_state:
    initial: a
    nodes:
      - { id: a }
      - { id: b, terminal: true }
    transitions:
      - { from: a, event: go, to: b }
events:
  go:
    status: draft
    description: "Declared so {events.go} is a real token; but the transition uses bare 'go'."
---

## Tokens

The transition uses `event: go` (a bare string) rather than `event: "{events.go}"`. Since
D-046 that is a `schema-violation` error at the transition (the retired `undefined-event`
warning was a `state-machine-coverage` sub-finding), even though the event token *is*
declared in the events namespace — the check is on the *form* of the transition value,
not on whether the bare identifier happens to match a declared event.
