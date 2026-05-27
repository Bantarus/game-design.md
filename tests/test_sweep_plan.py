"""Tests for benchmark.harness.sweep_plan.

The planner enforces the pairing-integrity discipline for the help-
benchmark sweep. These tests verify the discipline is structurally
held by the planner itself — so the discipline cannot regress silently.

What the planner promises (verified here):
  - For each subject: 4 task types × 2 games × n_per_cell instances,
    each contributing 3 cells (A, B, C) → 330 cells per subject at
    the pre-reg's n_per_cell={easy:5, medium/hard/ambiguity:20}.
  - For every instance, the A and B cells share a unit_id, share the
    same instance seed, and are at adjacent order_indices.
  - C cells are alone in their unit (never adjacent to A or B of the
    same instance unless by random shuffle outcome — but they are NOT
    in the same unit).
  - The plan is deterministic for fixed inputs.
  - Different shuffle_seeds produce different orderings.
"""
from __future__ import annotations

import pytest

from benchmark.harness.sweep_plan import (
    INSTANCE_SEED_BASE_BY_SUBJECT,
    TrialCell,
    plan_sweep,
)


@pytest.fixture(scope="module")
def qwen_plan():
    return plan_sweep(subject="qwen", shuffle_seed=12345)


@pytest.fixture(scope="module")
def qwen_plan():
    return plan_sweep(subject="qwen", shuffle_seed=12345)


def test_total_cells_per_subject(qwen_plan):
    """Per pre-reg §"Power, MDE, and the discordance assumption" line 341:
    per-subject total = 330 = 240 paired + 60 C (m/h/a) + 30 easy.

    Reconciled with the planner via C_N_PER_CELL_OVERRIDES, which halves
    N for C on medium/hard/ambiguity (n_c=10 instead of n_paired=20) so
    the pre-reg's stated total matches the planner's output exactly:

      paired m/h/a: 3 task types × 2 games × 20 N × 2 conditions = 240
      C m/h/a:      3 task types × 2 games × 10 N × 1 condition  =  60
      easy paired:  1 task type × 2 games × 5 N × 2 conditions   =  20
      easy C:       1 task type × 2 games × 5 N × 1 condition    =  10
                                                            total = 330

    v12-D: Claude arm deferred (archived under benchmark/harness/archived/);
    single-subject (Qwen) total is 330 by construction.
    """
    assert len(qwen_plan) == 330


def test_c_n_per_cell_overrides_applied(qwen_plan):
    """C cells run at half N for m/h/a (n_c=10) and full N for easy (n_c=5).

    Counts per (task, game) for C:
      easy:      5 per game × 2 games = 10
      medium:   10 per game × 2 games = 20
      hard:     10 per game × 2 games = 20
      ambiguity: 10 per game × 2 games = 20
                                  total = 70 C cells
    """
    c_counts: dict[str, int] = {}
    for cell in qwen_plan:
        if cell.condition == "C":
            c_counts[cell.task] = c_counts.get(cell.task, 0) + 1
    assert c_counts["easy"] == 10, f"easy C={c_counts['easy']} (expected 10)"
    assert c_counts["medium"] == 20, f"medium C={c_counts['medium']} (expected 20)"
    assert c_counts["hard"] == 20, f"hard C={c_counts['hard']} (expected 20)"
    assert c_counts["ambiguity"] == 20, f"ambiguity C={c_counts['ambiguity']} (expected 20)"
    assert sum(c_counts.values()) == 70


def test_per_instance_cell_count(qwen_plan):
    """Every instance contributes A and B (paired). C is contributed only
    by the first n_c instances per (task, game) — see
    C_N_PER_CELL_OVERRIDES. Instances beyond n_c get [A, B] but no C."""
    instances: dict[str, list[TrialCell]] = {}
    for cell in qwen_plan:
        instances.setdefault(cell.instance_id, []).append(cell)
    for iid, cells in instances.items():
        conds = sorted(c.condition for c in cells)
        # Every instance has A and B; some have C, some don't.
        assert "A" in conds and "B" in conds, (
            f"instance {iid} missing A or B: conditions={conds}"
        )
        assert conds in (["A", "B"], ["A", "B", "C"]), (
            f"instance {iid} has unexpected conditions {conds}"
        )


def test_paired_cells_adjacent_and_same_unit(qwen_plan):
    """For every (game, task, seed_n) instance, A and B are adjacent
    in execution order AND share the same unit_id."""
    by_instance: dict[str, list[TrialCell]] = {}
    for cell in qwen_plan:
        by_instance.setdefault(cell.instance_id, []).append(cell)

    for iid, cells in by_instance.items():
        # Find the A and B cells
        ab_cells = [c for c in cells if c.condition in ("A", "B")]
        assert len(ab_cells) == 2, f"instance {iid} has {len(ab_cells)} A/B cells, expected 2"
        ab_sorted = sorted(ab_cells, key=lambda c: c.order_index)
        # They must share unit_id
        assert ab_sorted[0].unit_id == ab_sorted[1].unit_id, (
            f"instance {iid} A/B cells in different units: "
            f"{ab_sorted[0].unit_id} vs {ab_sorted[1].unit_id}"
        )
        # They must be at adjacent order_indices
        assert ab_sorted[1].order_index - ab_sorted[0].order_index == 1, (
            f"instance {iid} A/B cells not adjacent: "
            f"indices {ab_sorted[0].order_index} and {ab_sorted[1].order_index}"
        )
        # Pair roles must be first/second
        assert ab_sorted[0].pair_role == "first_of_pair"
        assert ab_sorted[1].pair_role == "second_of_pair"
        # Same seed (this is the paired-design contract)
        assert ab_sorted[0].seed == ab_sorted[1].seed


def test_c_cells_unpaired_role(qwen_plan):
    """C cells carry pair_role='unpaired_c' and are alone in their unit."""
    unit_to_cells: dict[str, list[TrialCell]] = {}
    for cell in qwen_plan:
        unit_to_cells.setdefault(cell.unit_id, []).append(cell)

    for cell in qwen_plan:
        if cell.condition == "C":
            assert cell.pair_role == "unpaired_c"
            unit_members = unit_to_cells[cell.unit_id]
            assert len(unit_members) == 1, (
                f"C cell {cell.instance_id} unit has {len(unit_members)} "
                f"cells (expected 1)"
            )


def test_within_pair_coin_flips(qwen_plan):
    """The within-pair coin should produce a mix of A-first and B-first
    orderings across the sweep (not deterministic A-first).

    With 130 paired units (3 m/h/a × 2 games × 20 N + 1 easy × 2 games
    × 5 N = 120 + 10 = 130) and a 50/50 coin, expect ~65 each. Allow
    ±25 slack so the test isn't flaky on edge cases.
    """
    a_first = 0
    b_first = 0
    by_unit: dict[str, list[TrialCell]] = {}
    for cell in qwen_plan:
        by_unit.setdefault(cell.unit_id, []).append(cell)
    for unit_id, cells in by_unit.items():
        if len(cells) == 2:  # paired unit
            cells_sorted = sorted(cells, key=lambda c: c.order_index)
            if cells_sorted[0].condition == "A":
                a_first += 1
            else:
                b_first += 1
    assert a_first + b_first == 130, (
        f"expected 130 paired units, got {a_first + b_first}"
    )
    assert 40 <= a_first <= 90, f"a_first={a_first} out of 130 pairs (expected ~65)"
    assert 40 <= b_first <= 90, f"b_first={b_first} out of 130 pairs (expected ~65)"


def test_plan_is_deterministic():
    """Same inputs → same plan, byte-for-byte."""
    p1 = plan_sweep(subject="qwen", shuffle_seed=12345)
    p2 = plan_sweep(subject="qwen", shuffle_seed=12345)
    assert len(p1) == len(p2)
    for c1, c2 in zip(p1, p2):
        assert c1 == c2


def test_different_seeds_produce_different_orders():
    """Different shuffle_seeds → measurably different orderings."""
    p1 = plan_sweep(subject="qwen", shuffle_seed=12345)
    p2 = plan_sweep(subject="qwen", shuffle_seed=67890)
    # Same cell set (same conditions × tasks × games × seeds), but
    # different order.
    assert set((c.instance_id, c.condition) for c in p1) == \
           set((c.instance_id, c.condition) for c in p2)
    # At least 80% of order_indices should differ — random.shuffle on
    # 260+ units is well beyond the ε where most positions move.
    differing = sum(
        1 for c1, c2 in zip(p1, p2)
        if (c1.instance_id, c1.condition) != (c2.instance_id, c2.condition)
    )
    assert differing >= int(0.80 * len(p1)), (
        f"only {differing}/{len(p1)} positions differ; shuffle seems weak"
    )


def test_within_pair_seed_is_independent_of_shuffle_seed():
    """Changing only within_pair_seed flips coins but the inter-unit
    order should depend only on shuffle_seed — verify the two seeds
    are independent levers."""
    p1 = plan_sweep(subject="qwen", shuffle_seed=12345, within_pair_seed=0)
    p2 = plan_sweep(subject="qwen", shuffle_seed=12345, within_pair_seed=99)
    # Same unit-shuffle order: extracting unit_ids in order should match.
    units_p1 = []
    seen = set()
    for c in p1:
        if c.unit_id not in seen:
            units_p1.append(c.unit_id)
            seen.add(c.unit_id)
    units_p2 = []
    seen = set()
    for c in p2:
        if c.unit_id not in seen:
            units_p2.append(c.unit_id)
            seen.add(c.unit_id)
    assert units_p1 == units_p2, (
        "within_pair_seed should not affect inter-unit order"
    )


def test_qwen_seed_base_isolated_from_reserved_claude_range():
    """v12-D scope reduction archived the Claude transfer probe; the Claude
    `seed_base=2_000_000` is preserved as a RESERVED comment in
    INSTANCE_SEED_BASE_BY_SUBJECT so re-activation produces bit-identical
    seeds. This test verifies that Qwen's seed range never collides with
    the reserved Claude range — re-activation can re-add `"claude": 2_000_000`
    without seed collisions.

    Qwen seeds: 1_000_000 + instance_idx (0..329) → 1_000_000..1_000_329.
    Reserved Claude range: 2_000_000..2_000_329 (same allocation pattern).
    """
    qp = plan_sweep(subject="qwen", shuffle_seed=0)
    qwen_seeds = {c.seed for c in qp}
    reserved_claude_range = set(range(2_000_000, 2_000_000 + 330))
    assert not (qwen_seeds & reserved_claude_range), (
        "Qwen seeds collide with the reserved Claude range — re-activation "
        "would produce non-deterministic seed allocation"
    )


def test_no_duplicate_cells(qwen_plan):
    """No (subject, condition, task, game, seed) tuple appears twice."""
    keys = [
        (c.subject, c.condition, c.task, c.game, c.seed) for c in qwen_plan
    ]
    assert len(keys) == len(set(keys))


def test_order_indices_are_contiguous(qwen_plan):
    """order_index is 0..N-1 with no gaps."""
    indices = sorted(c.order_index for c in qwen_plan)
    assert indices == list(range(len(qwen_plan)))


def test_unknown_subject_raises():
    with pytest.raises(ValueError):
        plan_sweep(subject="gpt", shuffle_seed=0)


def test_cli_emits_jsonl(tmp_path, capsys):
    """The CLI emits one JSON object per line, in execution order."""
    from benchmark.harness.sweep_plan import main as cli_main
    rc = cli_main(["--subject", "qwen", "--shuffle-seed", "0"])
    assert rc == 0
    captured = capsys.readouterr()
    lines = captured.out.strip().splitlines()
    assert len(lines) == 330
    # Each line is parseable JSON
    import json
    for i, line in enumerate(lines):
        obj = json.loads(line)
        assert obj["order_index"] == i
        assert obj["subject"] == "qwen"
        assert obj["condition"] in ("A", "B", "C")
