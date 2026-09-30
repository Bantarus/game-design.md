"""Strike resolution (rules.resolve_strike)."""
from __future__ import annotations

from lanternfall.rng.tables import strike_roll


def resolve_strike(actor: dict, target: dict, rng) -> int:
    """Damage = strike_roll + the actor's might; returns the target's remaining vigor."""
    damage = strike_roll(rng) + actor["might"]
    target["vigor"] = max(0, target["vigor"] - damage)
    return target["vigor"]
