"""`gdmd verify` — experimental, contract-only.

Reads `verify_targets:` + `adapters:` (from `gdd/verification.md` subfile or
the core file), invokes the declared adapter executable, and validates its
stdout against the `VerifyResult` $def in the schema.

No bundled runner; the spec deliberately keeps `verify` engine-neutral.
See spec.md §9.5.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .tree import Tree


class VerifyError(RuntimeError):
    pass


def collect_config(tree: Tree) -> tuple[list[dict], dict[str, Any]]:
    """Pull verify_targets + adapters from either gdd/verification.md or core file."""
    targets: list[dict] = []
    adapters: dict[str, Any] = {}
    for pf in tree.files:
        if pf.file_type not in ("subfile", "core"):
            continue
        t = pf.frontmatter.get("verify_targets")
        a = pf.frontmatter.get("adapters")
        if isinstance(t, list):
            targets.extend(x for x in t if isinstance(x, dict))
        if isinstance(a, dict):
            adapters.update(a)
    return targets, adapters


def run_adapter(adapter_cmd: str, tree_root: Path) -> dict[str, Any]:
    """Invoke the adapter executable. Adapter writes a VerifyResult JSON to stdout.

    Adapter path is resolved relative to `tree_root` if not absolute.
    """
    cmd_path = Path(adapter_cmd)
    if not cmd_path.is_absolute():
        cmd_path = tree_root / cmd_path
    if not cmd_path.exists():
        raise VerifyError(
            f"adapter not found at {cmd_path}. "
            f"Provide an executable per spec §9.5 (verify is experimental in v0.1.1)."
        )
    try:
        proc = subprocess.run(
            [str(cmd_path)], cwd=tree_root, capture_output=True, text=True,
            check=False,
        )
    except OSError as e:
        raise VerifyError(f"failed to invoke adapter: {e}") from e
    if proc.returncode != 0:
        raise VerifyError(f"adapter exited {proc.returncode}: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise VerifyError(f"adapter output is not valid JSON: {e}") from e


def evaluate(result: dict[str, Any]) -> int:
    """Compute the verify exit code from a VerifyResult.

    Exit 1 if any build_health or behavioral_alignment target failed.
    Presentation-only regressions are exit 0 (warnings in notes).
    """
    fails = [r for r in result.get("results", []) if not r.get("pass")]
    blocking = [r for r in fails
                if r.get("axis") in ("build_health", "behavioral_alignment")]
    return 1 if blocking else 0
