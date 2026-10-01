"""Build A / B / C condition payloads for a (task × game) cell.

The three conditions per spec §"Conditions":
  - A: full conformant `game-design.md` tree (core + relevant subfiles +
       content for the fresh game) plus `AGENTS.md` and `CLAUDE.md`.
  - B: identical information content of A, mechanically flattened into a
       single unstructured prose document (via `benchmark/tools/flattener.py`).
  - C: a one-paragraph description of the game (the "vibe coding" baseline),
       authored from scratch and frozen before any trial.

The payload is what the subject (the LLM under test) sees, in the form of
a single text blob. The A payload includes a directory tree of files;
to send to a subject, we serialize it as concatenated files with clear
file-boundary markers. The B payload is just the flattened text.
The C payload is the C-prompt text.

All three payloads also include the task brief itself — that's the
question being asked. The condition just changes the BACKGROUND information
the subject can consult while answering.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


HARNESS_DIR = Path(__file__).resolve().parent
BENCHMARK_DIR = HARNESS_DIR.parent
PROJECT_ROOT = BENCHMARK_DIR.parent
GAMES_DIR = BENCHMARK_DIR / "games"
C_PROMPTS_DIR = BENCHMARK_DIR / "c-prompts"
FLATTENER = BENCHMARK_DIR / "tools" / "flattener.py"


@dataclass(frozen=True)
class ConditionPayload:
    condition: str          # "A" | "B" | "C"
    game: str               # "platformer" | "survival"
    payload_text: str       # the actual text sent to the subject as background
    payload_sha256: str     # SHA-256 of payload_text bytes
    payload_token_estimate: int  # rough token count (≈ 4 chars/token)


def build_a(game: str) -> ConditionPayload:
    """Condition A: concatenate the full game tree + AGENTS.md + CLAUDE.md."""
    game_root = GAMES_DIR / game
    if not game_root.exists():
        raise FileNotFoundError(f"Game tree not found: {game_root}")

    parts: list[str] = []
    # The two repo-root agent files first
    for repo_file in [PROJECT_ROOT / "AGENTS.md", PROJECT_ROOT / "CLAUDE.md"]:
        if repo_file.exists():
            parts.append(_file_block(repo_file.relative_to(PROJECT_ROOT), repo_file.read_text()))

    # Then walk the game tree in canonical order: core → gdd/* → content/*
    core = game_root / "game-design.md"
    if core.exists():
        parts.append(_file_block(core.relative_to(PROJECT_ROOT), core.read_text()))

    # gdd files in sorted path order
    gdd_dir = game_root / "gdd"
    if gdd_dir.exists():
        for f in sorted(gdd_dir.rglob("*.md")):
            parts.append(_file_block(f.relative_to(PROJECT_ROOT), f.read_text()))

    # content files in sorted path order
    content_dir = game_root / "content"
    if content_dir.exists():
        for f in sorted(content_dir.rglob("*.yaml")):
            parts.append(_file_block(f.relative_to(PROJECT_ROOT), f.read_text()))

    text = "\n\n".join(parts)
    return _make_payload("A", game, text)


def build_b(game: str) -> ConditionPayload:
    """Condition B: run the flattener over the game tree."""
    game_root = GAMES_DIR / game
    if not game_root.exists():
        raise FileNotFoundError(f"Game tree not found: {game_root}")

    # Invoke the flattener as a subprocess (its CLI writes to stdout when -o is omitted)
    result = subprocess.run(
        [sys.executable, str(FLATTENER), str(game_root)],
        capture_output=True,
        text=True,
        check=True,
    )
    text = result.stdout
    return _make_payload("B", game, text)


def build_c(game: str) -> ConditionPayload:
    """Condition C: read the C-prompt for this game."""
    c_prompt = C_PROMPTS_DIR / f"{game}.md"
    if not c_prompt.exists():
        raise FileNotFoundError(f"C-prompt not found: {c_prompt}")
    text = c_prompt.read_text()
    return _make_payload("C", game, text)


def _file_block(rel_path: Path, content: str) -> str:
    """A unique file-boundary marker the subject can parse."""
    return f"<<< FILE: {rel_path} >>>\n{content}\n<<< END FILE: {rel_path} >>>"


def _make_payload(condition: str, game: str, text: str) -> ConditionPayload:
    return ConditionPayload(
        condition=condition,
        game=game,
        payload_text=text,
        payload_sha256=hashlib.sha256(text.encode()).hexdigest(),
        payload_token_estimate=len(text) // 4,
    )
