"""Sweep-execution planner — enumerates trial cells in pairing-integrity-preserving order.

PROBLEM (the execution-phase confound this module exists to defeat).

The headline gate is paired McNemar (A vs B per instance — see pre-reg
§"Power, MDE, and the discordance assumption"). The pair's statistical
validity depends on its two members (A_i and B_i for instance i) seeing
the *same* nuisance conditions — same time-of-run, same rate-limit
posture, same thermal/memory state. Two time-correlated nuisances are
present in this sweep:

  - **Claude arm**: `claude-opus-4-7 --effort xhigh` runs against the
    user's subscription usage limits (or, after June 2026, the Agent
    SDK credit). The full Claude arm is 330 trials × ~$0.007/call
    floor (heavier on bigger A trees), so a long sweep can wall on
    rate limits mid-run.
  - **Qwen arm**: local llama.cpp over a multi-hour run drifts —
    thermal throttling, memory fragmentation, anything that nudges
    latency or sampling. Over 330 trials at, say, 60s/call, the run
    is ~5.5 hours; drift is real at that scale.

If the harness runs all-A first and all-B later (the **blocked**
pattern), any time-correlated effect lands on the late-running condition
more than the early-running one. The McNemar headline then shows a
spurious A-vs-B difference that is actually a time-vs-time difference.
This is the standard ordering pitfall in paired designs; the fix is
also standard.

FIX (the pairing-integrity discipline).

1. **Per-pair interleaving.** For each instance i = (game, task, seed_n),
   emit A_i and B_i as a single **execution unit** that the driver runs
   back-to-back, so the time delta between A_i and B_i is one trial-
   wall-clock, not 100+ trials.

2. **Within-pair order randomization.** For each unit, flip a coin
   (seeded) on whether A or B runs first. Cheap insurance against any
   first-call vs second-call effect inside a pair (e.g., per-CLI-call
   warm-up, server-side cache priming on the very-first-call of an
   instance).

3. **Randomized inter-unit order.** Shuffle units across the sweep with
   a seeded RNG, so any monotonic time effect (rate-limit posture
   climbing toward the wall; thermal drift accumulating) hits each
   condition's pair members in expectation-equal ways.

4. **C cells are their own units.** C is unpaired (informational
   baseline against A and B for the per-subject context; not in the
   headline gate), so a C cell is emitted as a single-cell unit and
   shuffled into the sweep order independently. C cells DO NOT split
   A/B pairs.

SUBJECT ORDERING. The two subjects (Qwen, Claude) run in *contiguous
per-subject sweeps* (e.g., all of Qwen, then all of Claude). The
within-subject pairing integrity is what the McNemar headline depends
on; cross-subject lift-magnitude comparisons see a per-subject time
delta that is already named in F-009 transfer-probe caveats. Running
subjects sequentially also matches the operational shape — Qwen needs
the local GPU; Claude needs the Claude Code CLI subscription;
interleaving them across calls would add wiring complexity for no
statistical benefit. Sweep order WITHIN each subject is independently
planned via this module.

SEED DISCIPLINE.

- `shuffle_seed` controls the **unit-shuffle RNG** (the randomized
  inter-unit order). Different shuffle_seed values produce different
  unit orderings; the same seed reproduces the same ordering exactly
  (verified by `test_sweep_plan_determinism`).
- `within_pair_seed` controls the **per-pair A-first-vs-B-first coin**.
  Default 0; lifts independently of shuffle_seed.
- The instance seed (passed as `--seed` to `run_trial.py`) is
  `instance_seed_base + i` where `i` is the deterministic instance
  index — A_i and B_i of the same pair always share the same `--seed`.
  Qwen's llama.cpp respects this seed for reproducibility; Claude
  Code's CLI does not (the seed is recorded for audit, per pre-reg §11
  "auditability is recorded, not gated") — see also F-009 transfer-
  probe caveats.

The shuffle_seed used at trial zero is part of the harness-build SHA
discipline and is recorded in F-009 alongside the bundle SHAs. Re-runs
of the sweep against the same harness-build SHA + same shuffle_seed
produce the same execution order — necessary for any post-hoc
investigation of trial-i specifically.

CLI USAGE.

  python -m benchmark.harness.sweep_plan \\
      --subject claude \\
      --shuffle-seed 12345 \\
      [--within-pair-seed 0]

Writes JSONL to stdout, one cell per line, in execution order. A
trial driver consumes the plan and invokes `run_trial.py` per cell.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import random
import sys
from dataclasses import dataclass
from typing import Iterable

from .tasks import Task, load_all_tasks


# Deterministic instance-seed bases per subject. Chosen to be distant
# (well beyond any plausible n_per_cell) so per-subject seeds never
# collide. Recorded here as part of the planner contract; changes
# invalidate any prior plan.
INSTANCE_SEED_BASE_BY_SUBJECT: dict[str, int] = {
    "qwen": 1_000_000,
    "claude": 2_000_000,
}


# Per-task-type N override for the unpaired C condition. Reconciles
# the pre-reg arithmetic (§"Power, MDE, and the discordance assumption",
# line 341): the per-subject total is 330 = 240 paired + 60 C + 30 easy.
# The stated formula `3 × 2 × 20 × 1` for C resolves to 60 ONLY if the
# middle factor is 10, not 20 — i.e. C runs at half N for medium / hard
# / ambiguity. Easy already runs at N=5 across all three conditions
# (5 × 2 × 3 = 30 per the same line) so no override is needed there.
#
# Design rationale (named for the audit trail): C is the unpaired
# baseline against the headline paired A-vs-B gate; halving its N is
# defensible because the unpaired statistical demand is lower than the
# paired one, AND C is the most-expensive-per-call condition (most
# context-poor → most prone to Claude flailing, per the dynamic-overhead
# caveat). Capturing the explicit choice here so the planner output
# matches the pre-reg's stated per-subject total exactly.
C_N_PER_CELL_OVERRIDES: dict[str, int] = {
    "medium": 10,
    "hard": 10,
    "ambiguity": 10,
    # "easy" not overridden: uses task.n_per_cell (=5) for C as well.
}


@dataclass(frozen=True)
class TrialCell:
    """One cell in the sweep, with its execution position fixed.

    The cell carries everything `run_trial.py` needs to execute it,
    plus the planner's metadata so the driver can log / resume / audit
    the execution stream.
    """
    order_index: int       # 0-based position in the sweep
    subject: str           # "qwen" | "claude" (matches --subject on run_trial.py)
    condition: str         # "A" | "B" | "C"
    task: str              # "easy" | "medium" | "hard" | "ambiguity"
    game: str              # "platformer" | "survival"
    seed: int              # the --seed argument; paired cells share this seed
    instance_id: str       # uniquely identifies (game, task, seed_n)
    unit_id: str           # identifies the execution unit (back-to-back cells share this)
    pair_role: str         # "first_of_pair" | "second_of_pair" | "unpaired_c"

    def to_json_line(self) -> str:
        return json.dumps(dataclasses.asdict(self), separators=(",", ":"), sort_keys=True)


def plan_sweep(
    subject: str,
    shuffle_seed: int,
    within_pair_seed: int = 0,
    tasks: Iterable[Task] | None = None,
) -> list[TrialCell]:
    """Return the full sweep execution order for `subject`.

    Args:
      subject: which subject this sweep is for ("qwen" | "claude").
      shuffle_seed: RNG seed for the inter-unit shuffle. Different
        seeds produce different unit orderings; the same seed
        reproduces the same ordering exactly.
      within_pair_seed: RNG seed for the per-pair A-first-vs-B-first
        coin. Default 0.
      tasks: optional pre-loaded task list (for testing). If None,
        loads from benchmark/tasks/*.yaml.

    Returns the cell list in execution order, with `order_index` set.
    """
    if subject not in INSTANCE_SEED_BASE_BY_SUBJECT:
        raise ValueError(
            f"Unknown subject {subject!r}; expected one of "
            f"{sorted(INSTANCE_SEED_BASE_BY_SUBJECT)}"
        )
    seed_base = INSTANCE_SEED_BASE_BY_SUBJECT[subject]

    if tasks is None:
        tasks_list = load_all_tasks()
    else:
        tasks_list = list(tasks)

    # Deterministic instance ordering: (task_type, game, seed_n). Sort
    # before iteration so any change to load_all_tasks's order does not
    # change the planner output for the same inputs.
    task_order = sorted(tasks_list, key=lambda t: (t.task_type, t.game))

    # Build units. Each unit is a list of 1 or 2 cells that the driver
    # runs back-to-back (the planner emits them adjacent in the final
    # cell stream).
    units: list[list[TrialCell]] = []
    instance_idx = 0
    within_pair_rng = random.Random(within_pair_seed)

    for task in task_order:
        n_paired = task.n_per_cell
        n_c = C_N_PER_CELL_OVERRIDES.get(task.task_type, task.n_per_cell)
        # Sanity: C N must be ≤ paired N (the planner is not designed for
        # C to run at higher N than the paired conditions, and the pre-
        # reg does not contemplate that case).
        assert n_c <= n_paired, (
            f"C n_per_cell ({n_c}) > paired n_per_cell ({n_paired}) "
            f"for task {task.task_type} — planner contract violated"
        )

        for seed_n in range(n_paired):
            seed = seed_base + instance_idx
            instance_id = f"{task.task_type}_{task.game}_{seed_n:03d}"

            # Build the (A, B) paired unit. The cells inside the unit
            # initially carry order_index=-1; final indices are assigned
            # after the shuffle.
            cell_a = TrialCell(
                order_index=-1,
                subject=subject,
                condition="A",
                task=task.task_type,
                game=task.game,
                seed=seed,
                instance_id=instance_id,
                unit_id=f"{instance_id}_AB",
                pair_role="first_of_pair",   # placeholder; flipped below
            )
            cell_b = TrialCell(
                order_index=-1,
                subject=subject,
                condition="B",
                task=task.task_type,
                game=task.game,
                seed=seed,
                instance_id=instance_id,
                unit_id=f"{instance_id}_AB",
                pair_role="second_of_pair",  # placeholder; flipped below
            )

            # Within-pair coin: 50% A-first / 50% B-first. The seeded
            # RNG produces a deterministic sequence of coin flips across
            # the sweep; the same within_pair_seed reproduces the same
            # within-pair order.
            if within_pair_rng.random() < 0.5:
                pair = [cell_a, cell_b]
            else:
                pair = [cell_b, cell_a]
            # Fix pair_role after the coin flip so it reflects execution
            # order, not condition.
            pair[0] = dataclasses.replace(pair[0], pair_role="first_of_pair")
            pair[1] = dataclasses.replace(pair[1], pair_role="second_of_pair")
            units.append(pair)

            # C cells run at n_c per (game, task) — see C_N_PER_CELL_OVERRIDES.
            # Only the first n_c instances of this (task, game) get a C cell;
            # the remaining (n_paired - n_c) instances are paired-only. This
            # matches the pre-reg's stated total exactly (and the choice of
            # WHICH instances carry C is deterministic — the first n_c by
            # seed_n — so re-planning produces the same C coverage).
            if seed_n < n_c:
                cell_c = TrialCell(
                    order_index=-1,
                    subject=subject,
                    condition="C",
                    task=task.task_type,
                    game=task.game,
                    seed=seed,
                    instance_id=instance_id,
                    unit_id=f"{instance_id}_C",
                    pair_role="unpaired_c",
                )
                units.append([cell_c])

            instance_idx += 1

    # Shuffle units. The unit boundaries are preserved (each unit's
    # cells stay adjacent and in within-pair order); only the order
    # of UNITS changes.
    shuffle_rng = random.Random(shuffle_seed)
    shuffle_rng.shuffle(units)

    # Flatten with final order_index.
    cells: list[TrialCell] = []
    for unit in units:
        for cell in unit:
            cells.append(dataclasses.replace(cell, order_index=len(cells)))

    return cells


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--subject", required=True,
                        choices=sorted(INSTANCE_SEED_BASE_BY_SUBJECT),
                        help="Subject this sweep is for.")
    parser.add_argument("--shuffle-seed", type=int, required=True,
                        help="Seed for the inter-unit shuffle RNG. Part of the "
                             "harness-build SHA discipline; recorded in F-009.")
    parser.add_argument("--within-pair-seed", type=int, default=0,
                        help="Seed for the per-pair A-first-vs-B-first coin "
                             "(default 0).")
    args = parser.parse_args(argv)

    cells = plan_sweep(
        subject=args.subject,
        shuffle_seed=args.shuffle_seed,
        within_pair_seed=args.within_pair_seed,
    )
    for cell in cells:
        print(cell.to_json_line())
    return 0


if __name__ == "__main__":
    sys.exit(main())
