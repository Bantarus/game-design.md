"""Smoke tests for loot/drop_tables.py."""
import random

from lanternfall.loot import drop_tables


def test_quality_is_a_known_bucket():
    rng = random.Random(7)
    assert drop_tables.roll_quality(rng) in drop_tables.QUALITY_WEIGHTS


def test_drops_come_from_the_list():
    rng = random.Random(11)
    kept = drop_tables.roll_drops({"drops": ["a", "b", "c"]}, rng)
    assert all(item in ("a", "b", "c") for item, _ in kept)
