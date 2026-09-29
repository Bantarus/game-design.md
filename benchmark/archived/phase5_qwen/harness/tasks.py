"""Task loading + freezing.

Tasks live at `benchmark/tasks/<task_type>_<game>.yaml`. Each task carries:
  - task_type: easy | medium | hard | ambiguity
  - game:      platformer | survival
  - n_per_cell: int (5 for easy, 20 for medium/hard/ambiguity per pre-reg)
  - headline:  bool (only medium/hard/ambiguity are headline)
  - brief:     str (the brief the subject sees)
  - intent_checklist: list of {id, description}
  - notes: str (author notes, not sent to subject)

At trial-zero time, the task file's SHA at HEAD is the frozen task. Any change
to the task file after trial zero invalidates the trial set (the harness
records the task SHA per trial).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml


HARNESS_DIR = Path(__file__).resolve().parent
TASKS_DIR = HARNESS_DIR.parent / "tasks"


@dataclass(frozen=True)
class ChecklistCriterion:
    id: str
    description: str


@dataclass(frozen=True)
class Task:
    task_type: str   # easy | medium | hard | ambiguity
    game: str        # platformer | survival
    n_per_cell: int
    headline: bool
    brief: str
    intent_checklist: tuple[ChecklistCriterion, ...]
    notes: str
    source_sha256: str  # SHA-256 of the task file's bytes at load time

    @property
    def cell_id(self) -> str:
        return f"{self.task_type}_{self.game}"


def load_task(task_type: str, game: str) -> Task:
    path = TASKS_DIR / f"{task_type}_{game}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Task definition not found: {path}")
    text = path.read_text()
    sha = hashlib.sha256(text.encode()).hexdigest()
    data = yaml.safe_load(text)
    return Task(
        task_type=data["task_type"],
        game=data["game"],
        n_per_cell=int(data["n_per_cell"]),
        headline=bool(data["headline"]),
        brief=data["brief"].rstrip(),
        intent_checklist=tuple(
            ChecklistCriterion(c["id"], c["description"])
            for c in data["intent_checklist"]
        ),
        notes=data.get("notes", "").rstrip(),
        source_sha256=sha,
    )


def load_all_tasks() -> list[Task]:
    """Load every task definition under benchmark/tasks/."""
    tasks: list[Task] = []
    for f in sorted(TASKS_DIR.glob("*.yaml")):
        # Filename convention: <task_type>_<game>.yaml
        stem = f.stem
        # Split on the LAST underscore (handles task_types with no underscore)
        parts = stem.rsplit("_", 1)
        if len(parts) != 2:
            continue
        task_type, game = parts
        tasks.append(load_task(task_type, game))
    return tasks
