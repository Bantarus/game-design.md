"""Tests for `gdmd init` (Task 7 v0.3)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from game_design_md import init_cmd, linter
from game_design_md.tree import Tree


# ---- list_genres -------------------------------------------------------------

EXPECTED_GENRES = {
    "deckbuilder", "party-rpg", "tcg", "tick-combat", "platformer", "survival",
}


def test_list_genres_includes_all_v0_3_starters():
    """The six v0.3 starters are present. Update this set when a v0.4
    starter is added (and trip this test as the reminder)."""
    found = set(init_cmd.list_genres())
    assert EXPECTED_GENRES <= found, (
        f"missing starters: {EXPECTED_GENRES - found}"
    )


def test_render_genre_list_includes_each_genre():
    out = init_cmd.render_genre_list()
    for g in EXPECTED_GENRES:
        assert g in out


# ---- copy_starter ------------------------------------------------------------

@pytest.mark.parametrize("genre", sorted(EXPECTED_GENRES))
def test_starter_copies_and_lints_clean(genre, tmp_path):
    """Every starter copies cleanly AND lints clean at the destination
    (Task 7 floor — calibration baseline)."""
    dest = tmp_path / "scaffolded"
    out_path, n = init_cmd.copy_starter(genre, dest)
    assert out_path == dest
    assert n >= 5, f"expected >=5 files for {genre} starter, got {n}"
    # The scaffolded tree must lint clean (0 errors AND 0 warnings).
    result = linter.run_all(Tree.load(dest))
    assert result.exit_code == 0, [
        f.message for f in result.findings if f.severity == "error"
    ]
    # No orphan or other warnings — starters must be clean baseline.
    non_info = [f for f in result.findings if f.severity != "info"]
    assert non_info == [], (
        f"{genre} starter has non-info findings:\n"
        + "\n".join(f"  [{f.severity}] {f.rule} @ {f.file}:{f.location}"
                    for f in non_info)
    )


def test_copy_starter_unknown_genre_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        init_cmd.copy_starter("not_a_genre", tmp_path / "dest")


def test_copy_starter_refuses_non_empty_destination(tmp_path):
    dest = tmp_path / "occupied"
    dest.mkdir()
    (dest / "existing.txt").write_text("don't clobber me")
    with pytest.raises(FileExistsError):
        init_cmd.copy_starter("deckbuilder", dest)


def test_copy_starter_accepts_empty_destination(tmp_path):
    """Empty directory IS allowed (the user pre-created the path)."""
    dest = tmp_path / "empty_but_exists"
    dest.mkdir()
    out_path, n = init_cmd.copy_starter("deckbuilder", dest)
    assert out_path == dest
    assert n > 0


def test_copy_starter_creates_new_destination(tmp_path):
    """If destination doesn't exist, it's created."""
    dest = tmp_path / "newly_created"
    assert not dest.exists()
    out_path, n = init_cmd.copy_starter("deckbuilder", dest)
    assert dest.exists()
    assert dest.is_dir()


# ---- CLI integration ---------------------------------------------------------

GDMD_BIN = Path(__file__).parent.parent / ".venv" / "bin" / "gdmd"


@pytest.mark.skipif(not GDMD_BIN.exists(), reason="gdmd binary not on path")
def test_cli_init_list_exits_zero():
    """`gdmd init --list` exits 0 and prints the genre list."""
    result = subprocess.run(
        [str(GDMD_BIN), "init", "--list"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    for g in EXPECTED_GENRES:
        assert g in result.stdout


@pytest.mark.skipif(not GDMD_BIN.exists(), reason="gdmd binary not on path")
def test_cli_init_genre_scaffolds_and_lints(tmp_path):
    """End-to-end: `gdmd init --genre X <dest>` scaffolds + lint-clean."""
    dest = tmp_path / "scaffolded"
    result = subprocess.run(
        [str(GDMD_BIN), "init", "--genre", "tick-combat", str(dest)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert dest.is_dir()
    assert (dest / "game-design.md").is_file()
    lint_result = subprocess.run(
        [str(GDMD_BIN), "lint", str(dest)],
        capture_output=True, text=True, timeout=10,
    )
    assert lint_result.returncode == 0, lint_result.stdout
