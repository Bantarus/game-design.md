---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: prototyped
last_verified: "2026-04-24"
implemented_in: ["impl/lanternfall/lantern/wick.py"]
clocks:
  lantern_burn:
    mode: per_verb_delta
    delta_source: verb.oil_cost
    drives:
      - "{rules.gutter_check}"
      - "{rules.affliction_tick}"
      - "{rules.wandering_spawn}"
    status: prototyped
    implemented_in: ["impl/lanternfall/lantern/wick.py"]
---

## Tokens

One clock, `lantern_burn`, in `per_verb_delta` mode: after each verb fires, the clock advances by the verb's `oil_cost:` and drives its rules in the declared order.

## Rationale

**Oil is time.** A per-verb delta, not a real-time rate: a careful player and a hasty one burn the same oil for the same actions. The three driven rules run in order: the lantern checks its oil, afflictions tick, and a dim lantern may draw a wandering spawn.
