"""`gdmd verify` — exercise the project's adapter against declared verify_targets.

Spec §9.5. Reads `verify_targets:` + `adapters:` from `gdd/verification.md`
(or the core file), invokes the project's adapter once per target (and once
per negative-control seed, §9.5.7), compares trajectories byte-for-byte
against goldens (§9.5.5), aggregates a single `VerifyResult` (§9.5.3) to
stdout. The standard owns the contract; the project owns the adapter. This
module is engine-free — it shells out to whatever executable the project
declares under `adapters: default:`.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .tree import Tree


class VerifyError(RuntimeError):
    pass


@dataclass
class VerifyTarget:
    axis: str
    target: str | None
    seed: int | None
    expect: dict
    negative_control: dict | None
    sessions: int | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "VerifyTarget":
        return cls(
            axis=d.get("axis", ""),
            target=d.get("target"),
            seed=d.get("seed"),
            expect=d.get("expect") if isinstance(d.get("expect"), dict) else {},
            negative_control=d.get("negative_control")
                if isinstance(d.get("negative_control"), dict) else None,
            sessions=d.get("sessions"),
        )

    @property
    def target_ref(self) -> str:
        """The `--target` value passed to the adapter. Token ref if declared,
        else the literal axis name (e.g. 'build_health')."""
        return self.target or self.axis


def collect_config(tree: Tree) -> tuple[list[VerifyTarget], dict[str, Any]]:
    """Pull verify_targets + adapters from any subfile or the core file."""
    targets: list[VerifyTarget] = []
    adapters: dict[str, Any] = {}
    for pf in tree.files:
        if pf.file_type not in ("subfile", "core"):
            continue
        t = pf.frontmatter.get("verify_targets")
        a = pf.frontmatter.get("adapters")
        if isinstance(t, list):
            for x in t:
                if isinstance(x, dict):
                    targets.append(VerifyTarget.from_dict(x))
        if isinstance(a, dict):
            adapters.update(a)
    return targets, adapters


def resolve_adapter(adapter_cmd: str, tree_root: Path) -> Path:
    p = Path(adapter_cmd)
    if not p.is_absolute():
        p = (tree_root / p).resolve()
    if not p.exists():
        raise VerifyError(
            f"adapter not found at {p}. "
            f"Provide an executable per spec §9.5.6, or declare a different "
            f"path under `adapters: default:` in gdd/verification.md."
        )
    return p


def invoke_adapter(
    adapter_path: Path,
    tree_root: Path,
    target_ref: str,
    seed: int,
    trajectory_path: Path | None = None,
    max_steps: int | None = None,
) -> dict[str, Any]:
    """Run the adapter once for one (target, seed). Parses stdout as JSON
    conforming to VerifyResult ($defs.VerifyResult)."""
    cmd: list[str] = [str(adapter_path), "--target", target_ref,
                      "--seed", str(seed)]
    if trajectory_path is not None:
        cmd += ["--trajectory", str(trajectory_path)]
    if max_steps is not None:
        cmd += ["--max-steps", str(max_steps)]
    try:
        proc = subprocess.run(
            cmd, cwd=tree_root, capture_output=True, text=True, check=False,
        )
    except OSError as e:
        raise VerifyError(f"failed to invoke adapter {adapter_path}: {e}") from e
    if proc.returncode != 0:
        tail = proc.stderr.strip()[-1000:]
        raise VerifyError(
            f"adapter exited {proc.returncode} for "
            f"--target {target_ref} --seed {seed}: {tail}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise VerifyError(
            f"adapter output is not valid JSON for "
            f"--target {target_ref} --seed {seed}: {e}\n"
            f"stdout (truncated): {proc.stdout[:500]}"
        ) from e


def _first_divergence_line(actual: bytes, golden: bytes) -> int | None:
    """1-indexed line number of the first divergent line, or None if equal."""
    a_lines = actual.split(b"\n")
    g_lines = golden.split(b"\n")
    for i, (a, g) in enumerate(zip(a_lines, g_lines)):
        if a != g:
            return i + 1
    if len(a_lines) != len(g_lines):
        return min(len(a_lines), len(g_lines)) + 1
    return None


def run_target(
    target: VerifyTarget,
    adapter_path: Path,
    tree_root: Path,
) -> list[dict[str, Any]]:
    """Run one verify_target. Returns a list of result rows — the primary
    invocation plus one row per negative_control seed."""
    results: list[dict[str, Any]] = []
    expect_traj = (target.expect.get("trajectory")
                   if isinstance(target.expect, dict) else None)
    primary_traj: Path | None = None
    if expect_traj is not None:
        fd, name = tempfile.mkstemp(suffix=".jsonl", prefix="verify_primary_")
        Path(name).touch()  # ensure exists
        # close the fd; we'll let the adapter create/write the file
        import os
        os.close(fd)
        primary_traj = Path(name)

    primary_seed = target.seed if target.seed is not None else 0
    primary_raw = invoke_adapter(
        adapter_path, tree_root, target.target_ref, primary_seed,
        trajectory_path=primary_traj,
    )

    # Pull the first result row (adapter returns 1 row per invocation).
    if not primary_raw.get("results"):
        raise VerifyError(
            f"adapter returned no results for --target {target.target_ref}"
        )
    primary_row: dict[str, Any] = dict(primary_raw["results"][0])
    primary_row["expected"] = target.expect

    # Trajectory comparison (if expected).
    if expect_traj is not None and primary_traj is not None:
        golden_rel = expect_traj.get("matches_golden") if isinstance(expect_traj, dict) else None
        if not golden_rel:
            raise VerifyError(
                f"target {target.target_ref}: expect.trajectory must "
                f"declare 'matches_golden: <path>'."
            )
        golden_path = (tree_root / golden_rel).resolve()
        try:
            golden_bytes = golden_path.read_bytes()
        except OSError as e:
            raise VerifyError(
                f"golden fixture not readable at {golden_path}: {e}"
            ) from e
        try:
            actual_bytes = primary_traj.read_bytes()
        except OSError as e:
            raise VerifyError(
                f"adapter did not produce a trajectory at {primary_traj}: {e}"
            ) from e
        if actual_bytes == golden_bytes:
            primary_row["pass"] = True
            primary_row["notes"] = (
                (primary_row.get("notes", "") + " ").lstrip()
                + f"trajectory byte-identical to {golden_rel}."
            )
        else:
            line = _first_divergence_line(actual_bytes, golden_bytes)
            primary_row["pass"] = False
            primary_row["notes"] = (
                f"trajectory diverges from {golden_rel}: "
                f"actual {len(actual_bytes)}B vs golden {len(golden_bytes)}B"
                + (f", first divergence line {line}." if line else ".")
                + " " + primary_row.get("notes", "")
            ).strip()

    results.append(primary_row)

    # Negative control: run per alt seed; primary trajectory must differ from
    # each alt-seed trajectory byte-for-byte.
    if target.negative_control is not None and primary_traj is not None:
        nc_seeds = target.negative_control.get("seeds", [])
        primary_bytes = primary_traj.read_bytes() if primary_traj.exists() else b""
        for nc_seed in nc_seeds:
            fd, nc_name = tempfile.mkstemp(
                suffix=".jsonl", prefix=f"verify_nc{nc_seed}_"
            )
            import os
            os.close(fd)
            nc_traj = Path(nc_name)
            try:
                invoke_adapter(
                    adapter_path, tree_root, target.target_ref, nc_seed,
                    trajectory_path=nc_traj,
                )
                nc_bytes = nc_traj.read_bytes()
            finally:
                try:
                    nc_traj.unlink()
                except OSError:
                    pass
            diverged = nc_bytes != primary_bytes
            nc_row = {
                "axis": target.axis,
                "target": f"{target.target_ref} [negative_control seed={nc_seed}]",
                "expected": target.negative_control.get("expect", {}),
                "observed": {
                    "trajectory_diverges_from_primary": diverged,
                    "primary_seed": primary_seed,
                    "negative_control_seed": nc_seed,
                },
                "pass": diverged,
                "notes": (
                    f"negative control passed: trajectory at seed {nc_seed} "
                    f"differs from primary at seed {primary_seed}."
                    if diverged
                    else f"negative control FAILED: trajectory at seed {nc_seed} "
                         f"is byte-identical to primary at seed {primary_seed} — "
                         f"adapter is provably not responding to --seed."
                ),
            }
            results.append(nc_row)

    if primary_traj is not None:
        try:
            primary_traj.unlink()
        except OSError:
            pass

    return results


def run_all(
    targets: list[VerifyTarget],
    adapter_path: Path,
    tree_root: Path,
) -> dict[str, Any]:
    """Run every target, aggregate into a single VerifyResult."""
    all_rows: list[dict[str, Any]] = []
    for t in targets:
        try:
            rows = run_target(t, adapter_path, tree_root)
        except VerifyError as e:
            all_rows.append({
                "axis": t.axis,
                "target": t.target_ref,
                "expected": t.expect,
                "observed": {},
                "pass": False,
                "notes": f"adapter error: {e}",
            })
            continue
        all_rows.extend(rows)

    passed = sum(1 for r in all_rows if r.get("pass"))
    failed = sum(1 for r in all_rows if not r.get("pass"))
    return {
        "results": all_rows,
        "summary": {
            "runs": len(all_rows),
            "passed": passed,
            "failed": failed,
            "skipped": 0,
        },
    }


def evaluate(result: dict[str, Any]) -> int:
    """Spec §9.5.4: exit 1 iff any build_health or behavioral_alignment
    target failed. presentation_usability regressions are exit 0."""
    fails = [r for r in result.get("results", []) if not r.get("pass")]
    blocking = [r for r in fails
                if r.get("axis") in ("build_health", "behavioral_alignment")]
    return 1 if blocking else 0


# Back-compat shim — older CLI imports `run_adapter` directly. New code uses
# `invoke_adapter` (per target+seed) or `run_all` (per tree).
def run_adapter(adapter_cmd: str, tree_root: Path) -> dict[str, Any]:
    """Legacy single-call interface; invokes adapter with no args. Retained
    for backwards-compat with v0.1.1 callers; new code should use `run_all`."""
    adapter = resolve_adapter(adapter_cmd, tree_root)
    proc = subprocess.run(
        [str(adapter)], cwd=tree_root, capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise VerifyError(f"adapter exited {proc.returncode}: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise VerifyError(f"adapter output is not valid JSON: {e}") from e
