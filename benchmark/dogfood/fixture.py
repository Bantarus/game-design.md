"""Isolated per-run copies of the repository for dogfood sessions (D-023).

Each run gets its own copy:

1. `git archive <ref>` of this repository, extracted outside the repo. The
   copy must live outside the repo: otherwise Claude Code's parent-directory
   discovery would load the real repo's CLAUDE.md on top of the copy's.
2. Harness files stripped (`EXCLUDE_FROM_COPY`), so the subject can't read
   tasks, checkers or frozen answers.
3. Every mtime set to `FIXTURE_MTIME`. `git archive` stamps files with the
   commit time, which would make every `prototyped` section look stale to
   `stale-section` (impl mtime vs `last_verified:`). With normalized mtimes
   the copy lints like the working tree it came from, and a fixture patch
   applied afterwards is the only fresh mtime, so it is the only drift
   signal.
4. A fresh `git init` with its own `.git` (not a worktree, whose shared
   `.git` would let a subject's commit land in the real repo). The task's
   fixture patch, if any, is applied as a teammate commit, then `BASE_TAG`
   marks the pre-session state that checkers diff against.

Two worlds (D-025):

- `matrix`: the copy is the matrix commit as-is. Its `gdmd` shim runs the
  copy's own `src/`, so the CLI is exactly the code at `<ref>`.
- `v0.3`: the same export, with the tooling-and-instructions layer
  (`V03_OVERLAY`) replaced by the `v0.3.0` tag. Its `gdmd` is a separate venv
  installed from the tag (`V03_VENV`), hash-checked against the tag's source.
  Task trees come from the matrix commit in both worlds, so task content is
  identical by construction.

Checkers never judge with the arm's own `gdmd`. They use one fixed judge, the
matrix commit's `src/` (`make_judge`). The preflight asserts that the arm's
`gdmd` and the judge lint the untouched fixture identically, both before and
after the fixture patch.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

DOGFOOD_DIR = Path(__file__).resolve().parent
REPO_ROOT = DOGFOOD_DIR.parents[1]
TASKS_DIR = DOGFOOD_DIR / "tasks"
ARMS_DIR = DOGFOOD_DIR / "arms"

EXCLUDE_FROM_COPY = ("benchmark/dogfood", "tests/test_dogfood.py")
FIXTURE_MTIME = datetime(2026, 5, 1).timestamp()
BASE_TAG = "dogfood-base"

WORLDS = ("matrix", "v0.3")
V03_TAG = "v0.3.0"
# The layer an agent learns the workflow and tooling from. Task trees are not in it.
V03_OVERLAY = ("CLAUDE.md", "AGENTS.md", "docs/spec.md", "schema", "src", "pyproject.toml")
V03_VENV = Path.home() / ".local/share/gdmd-dogfood/venvs/gdmd-v0.3.0"
_GIT_ID = ["-c", "user.name=dogfood", "-c", "user.email=dogfood@localhost",
           "-c", "commit.gpgsign=false"]


@dataclass(frozen=True)
class Task:
    task_id: str
    mode: str
    tree: str
    fixture_patch: str | None

    @property
    def prompt_path(self) -> Path:
        return TASKS_DIR / f"{self.task_id}.md"

    @property
    def checker_path(self) -> Path:
        return TASKS_DIR / f"{self.task_id}.check.py"

    def prompt(self) -> str:
        return self.prompt_path.read_text(encoding="utf-8")


def load_tasks() -> dict[str, Task]:
    data = yaml.safe_load((TASKS_DIR / "tasks.yaml").read_text(encoding="utf-8"))
    return {
        tid: Task(tid, spec["mode"], spec["tree"], spec.get("fixture_patch"))
        for tid, spec in data["tasks"].items()
    }


def git(root: Path, *args: str, identity: bool = False) -> str:
    cmd = ["git", "-C", str(root), *(_GIT_ID if identity else []), *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()


def export_ref(dest: Path, ref: str = "HEAD", repo: Path = REPO_ROOT,
               paths: tuple[str, ...] = ()) -> str:
    """Extract `git archive <ref> [paths]` of `repo` into `dest`; return the commit sha."""
    sha = git(repo, "rev-parse", f"{ref}^{{commit}}")
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", sha, *paths],
                             capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)
    return sha


def overlay_ref(root: Path, ref: str, paths: tuple[str, ...]) -> str:
    """Replace `paths` in `root` with their content at `ref` (whole subtrees)."""
    for rel in paths:
        p = root / rel
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    return export_ref(root, ref, paths=paths)


def _file_hashes(base: Path) -> dict[str, str]:
    return {str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(base.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


# pyproject's wheel force-include at the tag: source -> path inside the package.
_V03_FORCE_INCLUDE = {"docs/spec.md": "_data/spec.md",
                      "schema/game-design.schema.json": "_data/game-design.schema.json"}


def verify_v03_venv(venv: Path = V03_VENV, scratch: Path | None = None) -> dict:
    """Check the v0.3 venv: its `gdmd` exists and its installed `game_design_md`
    is byte-identical to `src/game_design_md` at `V03_TAG`. Raises FixtureError."""
    exe = venv / "bin" / "gdmd"
    if not exe.is_file():
        raise FixtureError(f"{exe} missing; create it with: python3 -m venv {venv} && "
                           f"{venv}/bin/pip install 'git+file://{REPO_ROOT}@{V03_TAG}'")
    installed = sorted(venv.glob("lib/python*/site-packages/game_design_md"))
    if len(installed) != 1:
        raise FixtureError(f"expected one installed game_design_md under {venv}, got {installed}")
    with tempfile.TemporaryDirectory(dir=scratch) as tmp:
        t = Path(tmp)
        sha = export_ref(t, V03_TAG, paths=("src/game_design_md", *_V03_FORCE_INCLUDE))
        want = _file_hashes(t / "src/game_design_md")
        for src, dest in _V03_FORCE_INCLUDE.items():
            want[dest] = hashlib.sha256((t / src).read_bytes()).hexdigest()
    got = _file_hashes(installed[0])
    if want != got:
        diff = sorted(set(want.items()) ^ set(got.items()))
        raise FixtureError(f"v0.3 venv does not match {V03_TAG} ({sha[:12]}): {diff[:5]}")
    return {"venv": str(venv), "tag": V03_TAG, "tag_sha": sha, "files": len(got)}


def make_judge(dest: Path, ref: str) -> Path:
    """The fixed checker judge: `src/` exported at `ref`, behind a `gdmd` shim.
    Returns the shim path (checkers read it from $DOGFOOD_GDMD)."""
    if dest.exists():
        raise FixtureError(f"{dest} already exists")
    export_ref(dest, ref, paths=("src",))
    return write_gdmd_shim(dest / "bin", dest)


def strip_excluded(root: Path) -> None:
    for rel in EXCLUDE_FROM_COPY:
        p = root / rel
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()


def normalize_mtimes(root: Path, when: float = FIXTURE_MTIME) -> None:
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for name in filenames:
            os.utime(Path(dirpath) / name, (when, when))


def init_repo(root: Path, message: str) -> None:
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message, identity=True)


def apply_fixture_patch(root: Path, patch: Path) -> None:
    """Apply a git-format-patch as a commit (its own author and message).
    The patched files get a fresh mtime, which is the intended drift signal."""
    git(root, "am", "-q", str(patch), identity=True)


def lint_summary(gdmd: list[str], tree_dir: Path, env: dict | None = None) -> dict:
    proc = subprocess.run([*gdmd, "lint", str(tree_dir)], capture_output=True,
                          text=True, env=env)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"summary": {"errors": -1, "warnings": -1}, "raw": proc.stdout + proc.stderr}


# D-025 Rule C: the import-card cell swaps only this line of the copy's CLAUDE.md.
SPEC_IMPORT_LINE = "- Format definition: @docs/spec.md"
CARD_IMPORT_LINE = "- Format definition: @docs/spec-card.md"


def swap_in_card(root: Path) -> str:
    """Rule C `import-card` cell construction (D-024 §3, D-025): generate
    `docs/spec-card.md` with the copy's own `src/` from the copy's own spec
    (`gdmd spec --card`), and replace only the `@docs/spec.md` import line in
    the copy's `CLAUDE.md`. Runs before the copy's baseline commit, so the
    swap is part of the fixture, not a subject edit. Returns the card's sha256."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONPATH"] = str(root / "src")
    proc = subprocess.run([sys.executable, "-m", "game_design_md", "spec", "--card"],
                          cwd=root, env=env, capture_output=True, text=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise FixtureError(f"gdmd spec --card failed in the copy: {proc.stderr[-500:]}")
    (root / "docs" / "spec-card.md").write_text(proc.stdout, encoding="utf-8")
    cm = root / "CLAUDE.md"
    text = cm.read_text(encoding="utf-8")
    if text.count(SPEC_IMPORT_LINE) != 1:
        raise FixtureError(f"CLAUDE.md does not have exactly one {SPEC_IMPORT_LINE!r}")
    cm.write_text(text.replace(SPEC_IMPORT_LINE, CARD_IMPORT_LINE), encoding="utf-8")
    return hashlib.sha256(proc.stdout.encode("utf-8")).hexdigest()


def write_gdmd_shim(bin_dir: Path, copy_root: Path, exe: Path | None = None) -> Path:
    """A `gdmd` executable: `exe` if given (the v0.3 venv), else the copy's own `src/`."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    shim = bin_dir / "gdmd"
    body = (f'exec "{exe}" "$@"\n' if exe else
            f'PYTHONPATH="{copy_root / "src"}" exec "{sys.executable}" -m game_design_md "$@"\n')
    shim.write_text("#!/bin/sh\nunset PYTHONPATH\n" + body if exe else "#!/bin/sh\n" + body,
                    encoding="utf-8")
    shim.chmod(0o755)
    return shim


@dataclass(frozen=True)
class PreparedCopy:
    root: Path
    source_sha: str
    shim_dir: Path
    world: str = "matrix"
    overlay_sha: str | None = None
    card_sha: str | None = None

    def env(self) -> dict:
        env = dict(os.environ)
        env["PATH"] = f"{self.shim_dir}{os.pathsep}{env.get('PATH', '')}"
        env.pop("PYTHONPATH", None)
        return env


class FixtureError(RuntimeError):
    pass


def _judge_agrees(copy: PreparedCopy, tree: str, judge: Path, when: str) -> None:
    arm = lint_summary(["gdmd"], copy.root / tree, env=copy.env())
    ref = lint_summary([str(judge)], copy.root / tree, env=copy.env())
    if arm != ref:
        raise FixtureError(f"judge and {copy.world} gdmd disagree on {tree} {when}: "
                           f"{arm.get('summary')} vs {ref.get('summary')}")


def prepare_copy(task: Task, cell_dir: Path, ref: str = "HEAD", world: str = "matrix",
                 judge: Path | None = None, card: bool = False) -> PreparedCopy:
    """Build the isolated copy for one run of `task` under `cell_dir`.

    Raises FixtureError if the task's tree doesn't lint 0/0 before the fixture
    patch (a dirty baseline would make "must lint clean" untestable), or, when
    a `judge` is given, if the arm's gdmd and the judge lint the fixture
    differently before or after the patch.
    """
    if world not in WORLDS:
        raise FixtureError(f"unknown world {world!r}")
    root = cell_dir / "repo"
    if root.exists():
        raise FixtureError(f"{root} already exists; cell directories are single-use")
    sha = export_ref(root, ref)
    overlay_sha = overlay_ref(root, V03_TAG, V03_OVERLAY) if world == "v0.3" else None
    strip_excluded(root)
    if card and world != "matrix":
        raise FixtureError("the card swap needs the matrix world (D-025 amendment 2)")
    card_sha = swap_in_card(root) if card else None
    normalize_mtimes(root)
    init_repo(root, f"fixture: game-design.md at {sha[:12]}"
                    + (f" with the {V03_TAG} tooling layer" if overlay_sha else "")
                    + (" with CLAUDE.md importing the generated card" if card else ""))
    exe = V03_VENV / "bin" / "gdmd" if world == "v0.3" else None
    copy = PreparedCopy(root=root, source_sha=sha, world=world, overlay_sha=overlay_sha,
                        shim_dir=write_gdmd_shim(cell_dir / "bin", root, exe).parent,
                        card_sha=card_sha)
    pre = lint_summary(["gdmd"], root / task.tree, env=copy.env())["summary"]
    if pre.get("errors") != 0 or pre.get("warnings") != 0:
        raise FixtureError(f"preflight lint of {task.tree} is not clean: {pre}")
    if judge:
        _judge_agrees(copy, task.tree, judge, "before the fixture patch")
    if task.fixture_patch:
        apply_fixture_patch(root, TASKS_DIR / task.fixture_patch)
        if judge:
            _judge_agrees(copy, task.tree, judge, "after the fixture patch")
    git(root, "tag", BASE_TAG)
    return copy
