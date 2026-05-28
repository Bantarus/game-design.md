"""gdmd init — per-genre starter scaffolding (Task 7 v0.3).

Surfaces the starter templates bundled in `templates/starters/<genre>/`
as a one-command tree initializer. Each starter is a descriptive scaffold
extracted from the corresponding canonical example (NOT a prescriptive
contract). The descriptive-scaffold framing is repeated in each starter's
root file's STARTER NOTE comment block.

Three command shapes:
  - `gdmd init --list`                          — list available genres.
  - `gdmd init --genre <name> [<dest>]`         — copy starter to <dest>.
  - `gdmd init [<dest>]`                        — interactive genre prompt.

All commands exit 0 on success, 1 on a usage/IO error.

Each starter lints clean as-is under default thresholds (Task 7 floor).
The descriptive-not-prescriptive discipline ([[discipline-applies-to-its-
own-artifacts]]) governs starter content: v0.3 vocab (clocks,
instance_container) appears in a starter only where the canonical example
demonstrated the closure, not preemptively.
"""
from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path

# Bundled starters live under the package data path. In a dev install
# (`pip install -e .`), the path resolves to the repo's templates/starters/
# directory; in a wheel install, it resolves to the same path inside the
# wheel's data tree.
def _starters_root() -> Path:
    """Return the templates/starters/ directory bundled with gdmd."""
    # First try: alongside the installed package (dev / editable install).
    pkg_dir = Path(__file__).parent
    candidate = pkg_dir.parent.parent / "templates" / "starters"
    if candidate.is_dir():
        return candidate
    # Fallback: package-data lookup (wheel install).
    try:
        with resources.as_file(
            resources.files("game_design_md") / ".." / "templates" / "starters"
        ) as p:
            if p.is_dir():
                return p
    except (ModuleNotFoundError, FileNotFoundError):
        pass
    raise FileNotFoundError(
        f"could not locate templates/starters/ — looked in {candidate}"
    )


def list_genres() -> list[str]:
    """Return the sorted list of available genre starters."""
    root = _starters_root()
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def render_genre_list() -> str:
    """Format the genre list for human reading."""
    genres = list_genres()
    if not genres:
        return "no starters available"
    lines = ["Available starter genres:"]
    for g in genres:
        lines.append(f"  {g}")
    lines.append("")
    lines.append("Usage:")
    lines.append("  gdmd init --genre <name> [<dest>]")
    lines.append("  gdmd init [<dest>]                  # interactive prompt")
    return "\n".join(lines)


def copy_starter(genre: str, dest: Path) -> tuple[Path, int]:
    """Copy the `genre` starter tree into `dest`. Returns (dest_path,
    file_count).

    Raises:
        FileNotFoundError if `genre` isn't a known starter.
        FileExistsError if `dest` exists and contains files (we refuse to
            overwrite — the user must clear it or pick a fresh directory).
    """
    root = _starters_root()
    src = root / genre
    if not src.is_dir():
        raise FileNotFoundError(
            f"unknown genre {genre!r}. Available: {', '.join(list_genres())}"
        )
    dest = Path(dest)
    if dest.exists():
        if dest.is_dir() and any(dest.iterdir()):
            raise FileExistsError(
                f"destination {dest} exists and is not empty. Pass a fresh "
                f"directory, or clear this one first."
            )
        if dest.is_file():
            raise FileExistsError(f"destination {dest} is a file, not a directory")
    dest.mkdir(parents=True, exist_ok=True)
    file_count = 0
    for src_file in src.rglob("*"):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src)
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, out)
        file_count += 1
    return dest, file_count
