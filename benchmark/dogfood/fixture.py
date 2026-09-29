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

The CLI under test is the copy's own `src/`, reached through a `gdmd` shim
on PATH, so it is exactly the code at `<ref>`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
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


def export_ref(dest: Path, ref: str = "HEAD", repo: Path = REPO_ROOT) -> str:
    """Extract `git archive <ref>` of `repo` into `dest`; return the commit sha."""
    sha = git(repo, "rev-parse", ref)
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", sha],
                             capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)
    return sha


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


def write_gdmd_shim(bin_dir: Path, copy_root: Path) -> Path:
    """A `gdmd` executable that runs the copy's own `src/`."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    shim = bin_dir / "gdmd"
    shim.write_text(
        "#!/bin/sh\n"
        f'PYTHONPATH="{copy_root / "src"}" exec "{sys.executable}" -m game_design_md "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return shim


@dataclass(frozen=True)
class PreparedCopy:
    root: Path
    source_sha: str
    shim_dir: Path

    def env(self) -> dict:
        env = dict(os.environ)
        env["PATH"] = f"{self.shim_dir}{os.pathsep}{env.get('PATH', '')}"
        env.pop("PYTHONPATH", None)
        return env


class FixtureError(RuntimeError):
    pass


def prepare_copy(task: Task, cell_dir: Path, ref: str = "HEAD") -> PreparedCopy:
    """Build the isolated copy for one run of `task` under `cell_dir`.

    Raises FixtureError if the task's tree doesn't lint 0/0 before the fixture
    patch: a dirty baseline would make "must lint clean" untestable.
    """
    root = cell_dir / "repo"
    if root.exists():
        raise FixtureError(f"{root} already exists; cell directories are single-use")
    sha = export_ref(root, ref)
    strip_excluded(root)
    normalize_mtimes(root)
    init_repo(root, f"fixture: game-design.md at {sha[:12]}")
    copy = PreparedCopy(root=root, source_sha=sha,
                        shim_dir=write_gdmd_shim(cell_dir / "bin", root))
    pre = lint_summary(["gdmd"], root / task.tree, env=copy.env())["summary"]
    if pre.get("errors") != 0 or pre.get("warnings") != 0:
        raise FixtureError(f"preflight lint of {task.tree} is not clean: {pre}")
    if task.fixture_patch:
        apply_fixture_patch(root, TASKS_DIR / task.fixture_patch)
    git(root, "tag", BASE_TAG)
    return copy
