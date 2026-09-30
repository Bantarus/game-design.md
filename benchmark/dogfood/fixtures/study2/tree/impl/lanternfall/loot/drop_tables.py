"""Drop-table sampling (rules.roll_drops, distributions.drop_quality)."""
from __future__ import annotations

QUALITY_WEIGHTS = {"worn": 60, "sound": 30, "gleaming": 10}


def roll_quality(rng) -> str:
    """Sample drop_quality: declaration order, first bucket above the roll."""
    roll = rng.randrange(100)
    for quality, weight in QUALITY_WEIGHTS.items():
        if roll < weight:
            return quality
        roll -= weight
    return "worn"


def roll_drops(monster: dict, rng) -> list[tuple[str, str]]:
    """Keep each listed drop on a one-in-three roll, then roll its quality."""
    kept = []
    for item in monster["drops"]:
        if rng.randrange(3) == 0:
            kept.append((item, roll_quality(rng)))
    return kept
