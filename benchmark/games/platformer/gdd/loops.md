---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-23"
implemented_in: ["src/embergrave/loops/**/*"]
loops:
  flight:
    timescale: moment
    duration: "~5-10s"
    sequence:
      - input:        "{verbs.jump}"
      - input:        "{verbs.dash}"
      - input:        "{verbs.glide}"
      - tick:         "{verbs.advance_tick}"
      - on_overlap:   "{verbs.refuel_ember}"
      - on_overlap:   "{verbs.touch_checkpoint}"
      - on_death:     "{verbs.restart_at_checkpoint}"
    intended_dynamics:
      - "ember scarcity forces commitment to a route; dash and glide are budgeted"
      - "the moth's six-frame jump arc is the entire vocabulary; mastery is timing, not options"
      - "darkness compounds error: a dim ember turns a known route into an unknown one"
    intended_aesthetics: [sensation, challenge]
    feel_priority: high
    balance_targets:
      - "{balance_targets.median_time_per_flight}"
      - "{balance_targets.ember_velocity}"
    status: draft
    implemented_in: ["src/embergrave/loops/flight.py"]
  level:
    timescale: session
    duration: "~3 min"
    sequence:
      - enter:    "{verbs.enter_level}"
      - traverse: "{loops.flight}"
      - exit:     "{verbs.exit_level}"
    intended_dynamics:
      - "checkpoint placement shapes the difficulty curve more than raw geometry does"
      - "ember-collection completionism creates a parallel route-finding game"
      - "first-clear and clean-clear are distinct player goals on the same level"
    intended_aesthetics: [challenge, discovery]
    feel_priority: medium
    balance_targets:
      - "{balance_targets.median_time_to_complete_level}"
      - "{balance_targets.median_deaths_per_level}"
      - "{balance_targets.ember_collected_pct_per_level}"
    status: draft
    implemented_in: ["src/embergrave/loops/level.py"]
  expedition:
    timescale: meta
    duration: "~30-90 min"
    sequence:
      - select_region: "{verbs.select_region}"
      - levels:        "{loops.level}"
      - reach_summit:  "{verbs.reach_summit}"
    intended_dynamics:
      - "the four regions are a difficulty curve; each region's last level is a soft gate"
      - "a session is a self-contained climb; expeditions do not persist mid-session state"
      - "ember-collection percentage is the soft-completionist meta layer"
    intended_aesthetics: [challenge, discovery]
    feel_priority: low
    balance_targets:
      - "{balance_targets.skilled_player_run_completion_pct}"
      - "{balance_targets.levels_per_region}"
    status: draft
    implemented_in: ["src/embergrave/loops/expedition.py"]
---

## Tokens

Three loops at three nested timescales. Reading order when reasoning about the game: `flight → level → expedition`. The flight loop is the unit of *commitment* — once the moth leaves the ground, its arc is fixed and the player observes the consequence. The level loop is the unit of *retry* — death respawns to the last checkpoint within the same level. The expedition loop is the unit of *progression* — the run-tracker's "where am I in the climb."

## Rationale

**Flight is the moment loop, not "frame" or "tick."** The simulation runs at 60Hz (fixed timestep — see `{invariants.fixed_timestep_simulation}`), but the *loop* the player experiences is "input commitment → physics-resolved consequence → land/die/checkpoint." A typical flight is 5–10 seconds and resolves with one of three outcomes: dies, reaches the next checkpoint, or completes the level segment. Verbs in `sequence:` are the input vocabulary, not a fixed order — the player issues `jump | dash | glide` in any order; the loop's job is to resolve them against physics.

**Level is a session, not a "stage" or "scene."** Levels are hand-crafted with 1–5 checkpoints depending on tier. The 3-minute target median is the design contract: any level routinely exceeding 5 minutes has a checkpoint missing or a difficulty miscalibration. The `feel_priority: medium` for level reflects that the level loop is felt less per-millisecond than flight but more per-attempt — completing a level is the satisfying beat.

**Expedition is a single session, not "career."** Embergrave deliberately rejects persistent meta-progression: starting the game means starting at the bottom of the climb; reaching the summit is the end. A session is 30–90 minutes for a skilled player, ~3–8 hours for first-time players spread across many sessions. Save/quit persistence is at the level boundary, not the expedition boundary — quitting mid-level resets to the level's first checkpoint, not mid-flight.

The boss equivalent (final summit level) is not a separate loop; it is a level in `content/levels/*.yaml` flagged as `region: summit` and `difficulty_tier: 5`. Treating it as a separate timescale would teach the player that "summit mode" is different, which we don't want. The challenge difference is in geometry, not loop semantics.

## Open Questions

- Whether to introduce a per-region "intermission" level (a calm, no-checkpoint, exploration-only segment that breaks up the tier-4-and-5 grinding). Argument for: pacing relief. Argument against: contradicts "the cave is the puzzle" by inserting non-puzzle space. Currently no; revisit after playtest.
- Whether `{loops.expedition}` should have a `feel:` block (currently `feel_priority: low` and no declaration). Argument for: the session-level rhythm is real (descent into darkness, ascent into light). Argument against: feel is per-verb in the spec, not per-loop. Currently no.
