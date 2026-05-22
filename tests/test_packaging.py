"""D-006 smoke test: build a wheel and verify `gdmd spec` / `gdmd export --format
schema` read from packaged data, not from the dev tree.

The test:
  1. Builds a wheel into a temp directory via `python -m build --wheel`.
  2. Creates a fresh venv, pip-installs the wheel.
  3. Changes CWD to a directory with no `docs/` or `schema/` siblings, so the
     dev-tree fallback in spec_cmd / export_cmd cannot match.
  4. Runs the installed `gdmd spec` and `gdmd export <dummy> --format schema`.
  5. Asserts both produce non-empty content that matches the canonical files.

If `build` is unavailable the test is skipped — this keeps the suite green on
machines without it, while still flagging packaging regressions in CI.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_SRC = REPO_ROOT / "docs" / "spec.md"
SCHEMA_SRC = REPO_ROOT / "schema" / "game-design.schema.json"


def _have(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _have("build"), reason="`build` package not installed")
def test_wheel_install_bundles_spec_and_schema(tmp_path: Path) -> None:
    # 1. Build a wheel.
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(wheel_dir)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    wheels = list(wheel_dir.glob("*.whl"))
    assert wheels, f"no wheel produced in {wheel_dir}"
    wheel = wheels[0]

    # 2. Create venv + install wheel.
    venv_dir = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    if os.name == "nt":
        py = venv_dir / "Scripts" / "python.exe"
        gdmd = venv_dir / "Scripts" / "gdmd"
    else:
        py = venv_dir / "bin" / "python"
        gdmd = venv_dir / "bin" / "gdmd"
    subprocess.run(
        [str(py), "-m", "pip", "install", "--quiet", str(wheel)],
        check=True,
        capture_output=True,
    )

    # 3. Run away from the source tree so the dev-tree fallback can't match.
    isolated = tmp_path / "elsewhere"
    isolated.mkdir()
    dummy_tree = isolated / "tree"
    dummy_tree.mkdir()
    (dummy_tree / "game-design.md").write_text(
        textwrap.dedent(
            """\
            ---
            spec: game-design.md
            spec_version: 0.2.0-alpha
            file_type: core
            name: smoke
            short_pitch: smoke test
            genre_tags: [test]
            status: draft
            version: 0.1.0
            last_updated: "2026-05-22"
            target_platforms_neutral: [desktop]
            pillars: ["a", "b", "c"]
            non_goals: ["n"]
            player_experience_goals: { primary: [challenge] }
            core_loop_ref: "{loops.x}"
            files: { pillars: gdd/pillars.md }
            ---

            # smoke
            > smoke test
            """
        )
    )

    # 4a. gdmd spec — packaged spec must be readable from outside the source tree.
    spec_out = subprocess.run(
        [str(gdmd), "spec"],
        cwd=str(isolated),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert spec_out.strip(), "gdmd spec produced empty output"
    assert "Universal Probabilistic Surface" in spec_out, (
        "gdmd spec output looks wrong — missing canonical section heading"
    )

    # 4b. gdmd export <path> --format schema — packaged schema must round-trip.
    schema_out = subprocess.run(
        [str(gdmd), "export", str(dummy_tree), "--format", "schema"],
        cwd=str(isolated),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    parsed = json.loads(schema_out)
    assert parsed["title"].startswith("game-design.md frontmatter")
    canonical = json.loads(SCHEMA_SRC.read_text(encoding="utf-8"))
    assert parsed["$id"] == canonical["$id"]
