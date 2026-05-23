---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-23"
implemented_in: ["src/driftwood/loops/**/*"]
loops:
  action:
    timescale: moment
    duration: "~5-30s"
    sequence:
      - choose: "{verbs.gather}"
      - choose: "{verbs.craft}"
      - choose: "{verbs.eat}"
      - choose: "{verbs.drink}"
      - choose: "{verbs.place_station}"
      - choose: "{verbs.sleep_through_night}"
      - tick:   "{verbs.advance_world_time}"
    intended_dynamics:
      - "each action costs in-game time; the budget across a day is finite"
      - "tool durability rewards batched gathering at the right tier of tool"
      - "spatial routes matter — actions near the camp are cheaper than actions across the island"
    intended_aesthetics: [challenge, expression]
    feel_priority: medium
    balance_targets:
      - "{balance_targets.in_game_hours_per_run}"
      - "{balance_targets.wall_clock_seconds_per_in_game_hour}"
    status: draft
    implemented_in: ["src/driftwood/loops/action.py"]
  day:
    timescale: session
    duration: "~6 min"
    sequence:
      - sunrise: "{verbs.start_day}"
      - actions: "{loops.action}"
      - sleep_or_perish: "{verbs.sleep_through_night}"
    intended_dynamics:
      - "the four day-parts (morning / afternoon / evening / night) shape the action budget"
      - "skipping sleep costs health; sleeping without a shelter costs more"
      - "the spring and tidepools are reliably accessible only in morning and afternoon"
    intended_aesthetics: [challenge, expression, discovery]
    feel_priority: high
    balance_targets:
      - "{balance_targets.in_game_hours_per_run}"
      - "{balance_targets.in_game_hours_per_day}"
      - "{balance_targets.day_part_hour_boundaries}"
      - "{balance_targets.skilled_player_pyre_completion_pct}"
    status: draft
    implemented_in: ["src/driftwood/loops/day.py"]
  run:
    timescale: meta
    duration: "~30 min"
    sequence:
      - days:      "{loops.day}"
      - assemble:  "{verbs.assemble_pyre}"
      - light:     "{verbs.light_pyre}"
    intended_dynamics:
      - "the five days are a route-planning puzzle the player composes once per run"
      - "knowledge of the island carries across runs; nothing else does"
      - "Day 1 is survey, Days 2-3 are tools and stockpile, Days 4-5 are the pyre"
    intended_aesthetics: [challenge, discovery]
    feel_priority: low
    balance_targets:
      - "{balance_targets.skilled_player_pyre_completion_pct}"
      - "{balance_targets.first_time_player_pyre_completion_pct}"
      - "{balance_targets.run_length_wall_clock_minutes}"
    status: draft
    implemented_in: ["src/driftwood/loops/run.py"]
---

## Tokens

Three loops at three nested timescales. Reading order when reasoning about the game: `action → day → run`. The action loop is the unit of *decision* — issue a verb, time advances, observe result. The day loop is the unit of *plan* — the player composes a sequence of actions against day-part availability and meter decay. The run loop is the unit of *strategy* — the five-day plan against the recipe tree's dependency structure.

## Rationale

**Action is the moment loop, not "tick" or "frame."** In-game time advances per-action (each verb declares its `time_cost` — see `gdd/mechanics.md`); there is no continuous-time simulation in the gameplay layer. A real-time-feeling day is achieved by mapping each in-game hour to ~15 seconds wall-clock, but the underlying model is action-driven, not clock-driven. The `tick:` step in `sequence:` is the friction artifact of the spec's verb-triggers-rule pattern applied to a time-advancing game — see the prose note in `gdd/mechanics.md` under `verbs.advance_world_time` for the v0.3 candidate finding about this.

**Day is a session, not a "stage."** The day is the planning unit. The four day-parts (morning, afternoon, evening, night) gate certain verbs: tidepool fishing only works at morning (low tide); sleep only at night; crafting at the sawhorse needs daylight or the campfire. A typical day is ~24 in-game hours = ~24 actions worth = 6 wall-clock minutes if the player is decisive. A first-time player spends extra wall-clock minutes per day deliberating; the in-game clock pauses during deliberation but the day's action budget is still 24 hours regardless of how long the player took to issue them.

**Run is a single session — there is no meta-loop in the design.** The brief explicitly forbids metagame progression: starting the game means starting on Day 1 of a new run, with the belt knife and nothing else; reaching Day 5 with the pyre lit ends the run with a win, and the next run starts at Day 1 again. Knowledge of the island (where the flint is, where the freshest berries cluster, the shortest path from spring to camp) is the only thing the player carries forward — and that knowledge is not represented in the game state, only in the player's head. The `timescale: meta` label is the spec's term for "above a single session," not a claim about persisted state across runs.

**Why no "encounter" or "combat" loop.** Driftwood has neither, by pillar. The verb vocabulary covers gathering, crafting, eating, drinking, sleeping, building, and the win action — no `attack`, no `defend`, no `flee`. The lack of a combat loop is the spec's silence-where-the-genre-default-would-fill-it; under the spec's "if it's not in the brief it isn't in the tree" discipline, no combat loop is the correct authoring.

## Open Questions

- Whether the in-game day should advance continuously in wall-clock time (15 s per in-game hour, ticking forward regardless of player action) instead of action-driven. Argument for: enforces decisiveness, matches real-time survival genre defaults. Argument against: punishes deliberation in a planning game where deliberation is the gameplay. Currently action-driven; flagged as a possible playtest revision.
- Whether to introduce a `weather` loop (rain on certain days reduces fire effectiveness; storms close the tidepools). Argument for: variety, replayability surface. Argument against: adds RNG to a deliberately low-RNG design. Currently no; revisit after playtest if runs feel too uniform.
