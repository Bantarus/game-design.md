"""Strike roll (distributions.strike_roll)."""
from __future__ import annotations


def strike_roll(rng) -> int:
    """Three d4, clamped to 3..12."""
    return max(3, min(12, sum(rng.randint(1, 4) for _ in range(3))))
