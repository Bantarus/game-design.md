"""`gdmd diff` — token-level diff between two trees with balance-regression detection.

Exit code 1 if `balance_regressions` is non-empty (a balance_target moved
outside its previous tolerance band, or a status regressed from
balanced/shipped).
"""
from __future__ import annotations

from typing import Any

from .tree import SUBFILE_NAMESPACES, Tree

_BACKWARD_FROM = {"balanced", "shipped"}
_LIFECYCLE = {"draft": 0, "prototyped": 1, "implemented": 2, "balanced": 3, "shipped": 4}


def _flatten_tokens(tree: Tree) -> dict[str, Any]:
    """Map "ns.id" -> value, for top-level tokens across every namespace."""
    flat: dict[str, Any] = {}
    for ns in SUBFILE_NAMESPACES:
        for k, (_pf, v) in tree.tokens.get(ns, {}).items():
            flat[k] = v
    return flat


def _in_band(value: Any, tolerance: Any) -> bool | None:
    """Return True if `value` is inside the [low, high] tolerance band.
    `None` means "cannot compare" (composite target — see DECISIONS.md D-003)."""
    if not isinstance(tolerance, list) or len(tolerance) != 2:
        return None
    low, high = tolerance
    if all(isinstance(x, (int, float)) for x in (value, low, high)):
        return low <= value <= high
    return None


def diff_trees(old: Tree, new: Tree) -> dict[str, Any]:
    a = _flatten_tokens(old)
    b = _flatten_tokens(new)

    added = sorted(k for k in b if k not in a)
    removed = sorted(k for k in a if k not in b)
    changed: list[dict[str, Any]] = []
    balance_regressions: list[dict[str, Any]] = []
    status_regressions: list[dict[str, Any]] = []

    for k in sorted(set(a) & set(b)):
        if a[k] != b[k]:
            changed.append({"path": k, "from": a[k], "to": b[k]})

        # Balance-target regression check
        if k.startswith("balance_targets.") and isinstance(a[k], dict) \
                and isinstance(b[k], dict):
            a_target, b_target = a[k].get("target"), b[k].get("target")
            a_tol = a[k].get("tolerance")
            if a_target != b_target:
                in_band = _in_band(b_target, a_tol)
                if in_band is False:
                    balance_regressions.append({
                        "path": f"{k}.target",
                        "from": a_target, "to": b_target,
                        "previous_tolerance": a_tol,
                    })

        # Status regression check
        if isinstance(a[k], dict) and isinstance(b[k], dict):
            a_st, b_st = a[k].get("status"), b[k].get("status")
            if a_st in _BACKWARD_FROM and b_st in _LIFECYCLE \
                    and _LIFECYCLE.get(b_st, 99) < _LIFECYCLE[a_st]:
                status_regressions.append({
                    "path": f"{k}.status", "from": a_st, "to": b_st,
                })

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "balance_regressions": balance_regressions,
        "status_regressions": status_regressions,
    }
