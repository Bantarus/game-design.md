"""Salvage (rules.resolve_salvage)."""
from __future__ import annotations


def resolve_salvage(rng) -> int:
    """Grave coin for one worn item: two d4, clamped to 2..8."""
    return max(2, min(8, rng.randint(1, 4) + rng.randint(1, 4)))
