"""The lantern clock and its oil check (clocks.lantern_burn, rules.gutter_check)."""
from __future__ import annotations

DIM_BELOW = 20


def burn(lantern: dict, oil_cost: int) -> str:
    """Advance the clock by one verb's oil cost; return the lantern state."""
    lantern["oil"] = max(0, lantern["oil"] - oil_cost)
    if lantern["oil"] == 0:
        return "guttered"
    return "dim" if lantern["oil"] < DIM_BELOW else "lit"
