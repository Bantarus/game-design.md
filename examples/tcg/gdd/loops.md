---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-22"
implemented_in: []
loops:
  turn:
    timescale: moment
    duration: "~30s"
    sequence:
      - draw:     "{verbs.draw_card}"
      - play:     "{verbs.play_card}"
      - attack:   "{verbs.attack}"
      - finalize: "{verbs.end_turn}"
    intended_dynamics:
      - "phase order is fixed; a player can't skip combat to play more cards"
      - "mana caps tempo decisions; spending all mana now means none next turn"
    intended_aesthetics: [challenge, expression]
    feel_priority: medium
    balance_targets:
      - "{balance_targets.average_match_duration}"
    status: draft
    implemented_in: []
  game:
    timescale: session
    duration: "~7 min"
    sequence:
      - mulligan: "{verbs.mulligan}"
      - turns:    "{loops.turn}"
    intended_dynamics:
      - "mulligans set the opening hand; opening hand sets the strategy"
      - "life-total pressure builds across turns, not in single spikes"
    intended_aesthetics: [challenge]
    feel_priority: low
    balance_targets:
      - "{balance_targets.average_game_turns}"
    status: draft
    implemented_in: []
  match:
    timescale: meta
    duration: "~20 min"
    sequence:
      - start: "{verbs.start_game}"
      - games: "{loops.game}"
    intended_dynamics:
      - "best-of-three rewards sideboarding (cut + add between games)"
    intended_aesthetics: [challenge, fellowship]
    feel_priority: low
    balance_targets:
      - "{balance_targets.win_rate_archetype_neutral}"
    status: draft
    implemented_in: []
---

## Tokens

Three loops nested at three timescales: `{loops.turn}` (moment) inside `{loops.game}` (session) inside `{loops.match}` (meta).

## Rationale

`{loops.turn}` enforces the fixed phase order — draw → play → attack → end. No skipping; a player can't open combat first. This is what makes the *commitment* feel real: once you've spent mana on a card, attacking afterwards is non-trivial.

`{loops.game}` is one game-of-three. Mulligan is the opening choice (reshuffle the hand, draw one fewer).

`{loops.match}` is a full match (best-of-three).
