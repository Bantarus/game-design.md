"""D-006 / D-050 smoke tests: build a wheel, install it in a fresh venv, and run
the installed `gdmd` from a directory outside the source tree, so that every
dev-tree fallback misses and only packaged data can answer.

- `gdmd spec` and `gdmd export --format schema` read the packaged spec and
  schema (D-006).
- `gdmd init` lists and scaffolds the packaged starters, and a scaffolded
  tree lints 0/0 (D-050, OI-012: through v0.3.0 the wheel carried no
  starters, so `init` failed outside an editable install).

The wheel and the venv are built once for the module. Without the `build`
package the tests skip locally and fail under CI (`$CI` set), so a CI run
cannot pass them by skipping.
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
STARTERS_SRC = REPO_ROOT / "templates" / "starters"


def _have(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


@pytest.fixture(scope="module")
def installed(tmp_path_factory) -> dict[str, Path]:
    """A wheel built from this checkout, installed in a fresh venv, and an
    empty working directory outside the source tree."""
    if not _have("build"):
        if os.environ.get("CI"):
            pytest.fail("`build` is not installed: the packaging tests must run in CI")
        pytest.skip("`build` package not installed")
    tmp = tmp_path_factory.mktemp("packaging")

    # 1. Build a wheel.
    wheel_dir = tmp / "dist"
    wheel_dir.mkdir()
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(wheel_dir)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    wheels = list(wheel_dir.glob("*.whl"))
    assert wheels, f"no wheel produced in {wheel_dir}"

    # 2. Create venv + install wheel.
    venv_dir = tmp / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    if os.name == "nt":
        py = venv_dir / "Scripts" / "python.exe"
        gdmd = venv_dir / "Scripts" / "gdmd"
    else:
        py = venv_dir / "bin" / "python"
        gdmd = venv_dir / "bin" / "gdmd"
    subprocess.run(
        [str(py), "-m", "pip", "install", "--quiet", str(wheels[0])],
        check=True,
        capture_output=True,
    )

    # 3. Run away from the source tree so the dev-tree fallbacks can't match.
    isolated = tmp / "elsewhere"
    isolated.mkdir()
    return {"py": py, "gdmd": gdmd, "isolated": isolated}


def _run(installed: dict[str, Path], *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(installed["gdmd"]), *args],
        cwd=str(installed["isolated"]),
        capture_output=True,
        text=True,
        check=check,
    )


def test_wheel_install_bundles_spec_and_schema(installed) -> None:
    dummy_tree = installed["isolated"] / "tree"
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

    # gdmd spec — packaged spec must be readable from outside the source tree.
    spec_out = _run(installed, "spec").stdout
    assert spec_out.strip(), "gdmd spec produced empty output"
    assert "Universal Probabilistic Surface" in spec_out, (
        "gdmd spec output looks wrong — missing canonical section heading"
    )

    # gdmd export <path> --format schema — packaged schema must round-trip.
    schema_out = _run(installed, "export", str(dummy_tree), "--format", "schema").stdout
    parsed = json.loads(schema_out)
    assert parsed["title"].startswith("game-design.md frontmatter")
    canonical = json.loads(SCHEMA_SRC.read_text(encoding="utf-8"))
    assert parsed["$id"] == canonical["$id"]


def test_wheel_install_bundles_the_init_starters(installed) -> None:
    """D-050 (OI-012): `gdmd init` works from the wheel alone."""
    starters = sorted(p.name for p in STARTERS_SRC.iterdir() if p.is_dir())
    assert len(starters) == 6

    # The starters are in the installed package's data, where the lookup reads first.
    data = subprocess.run(
        [str(installed["py"]), "-c",
         "from importlib import resources; "
         "print(resources.files('game_design_md').joinpath('_data/starters'))"],
        cwd=str(installed["isolated"]), capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert sorted(p.name for p in Path(data).iterdir() if p.is_dir()) == starters

    # gdmd init --list lists all six.
    listed = _run(installed, "init", "--list").stdout
    assert sorted(ln.strip() for ln in listed.splitlines()
                  if ln.startswith("  ") and ln.strip() in starters) == starters

    # gdmd init --genre party-rpg <tmp> scaffolds the starter, byte for byte.
    dest = installed["isolated"] / "new-party-rpg"
    res = _run(installed, "init", "--genre", "party-rpg", str(dest), check=False)
    assert res.returncode == 0, res.stderr
    src = STARTERS_SRC / "party-rpg"
    want = {p.relative_to(src): p.read_bytes() for p in src.rglob("*") if p.is_file()}
    got = {p.relative_to(dest): p.read_bytes() for p in dest.rglob("*") if p.is_file()}
    assert got == want

    # The scaffolded tree lints 0/0 under the installed gdmd.
    lint = _run(installed, "lint", str(dest), check=False)
    summary = json.loads(lint.stdout)["summary"]
    assert (lint.returncode, summary["errors"], summary["warnings"]) == (0, 0, 0), lint.stdout
