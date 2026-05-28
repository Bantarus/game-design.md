"""gdmd status — project dashboard view.

Aggregates status counts, staleness flags, and pointer health across a tree.
This is the projection of state implicit in `status:` + `last_verified:` +
`implemented_in:` markers. v0.2 had the markers; v0.3 surfaces them.

See spec §9.6.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from .tree import SUBFILE_NAMESPACES, Tree

# Canonical status order per spec §8.1 (forward path, then lateral, then cut).
_CANONICAL_STATUS_ORDER = (
    "draft", "prototyped", "implemented", "balanced", "shipped",
    "experimental", "deferred", "cut",
)

# Statuses at which a section is "active enough" that missing implementation_in
# is suspicious. cut + deferred + draft are exempt — code may legitimately not
# yet exist.
_ACTIVE_STATUSES = frozenset(
    {"prototyped", "implemented", "balanced", "shipped", "experimental"}
)


def _iter_tokens(tree: Tree):
    """Yield (file, namespace, token_name, token_value) for every per-namespace
    token in every subfile in the tree."""
    for pf in tree.files:
        if pf.file_type != "subfile":
            continue
        for ns in SUBFILE_NAMESPACES:
            block = pf.frontmatter.get(ns)
            if not isinstance(block, dict):
                continue
            for tname, token in block.items():
                if isinstance(token, dict):
                    yield pf, ns, tname, token


def collect_status_counts(tree: Tree) -> dict[str, int]:
    """Tally `status:` across every file (subfiles, content-schema, content-
    entity) AND every per-namespace token inside subfiles."""
    counts: dict[str, int] = defaultdict(int)

    for pf in tree.files:
        if pf.file_type in ("subfile", "content-schema", "content-entity"):
            s = pf.frontmatter.get("status")
            if isinstance(s, str):
                counts[s] += 1

    for _pf, _ns, _tname, token in _iter_tokens(tree):
        ts = token.get("status")
        if isinstance(ts, str):
            counts[ts] += 1

    return dict(counts)


def collect_stale_sections(tree: Tree, stale_days: int,
                           now: datetime | None = None) -> list[dict[str, Any]]:
    """File-level `last_verified:` older than `stale_days` vs current date.

    Distinct from the linter's `stale-section` rule (which compares
    last_verified to impl mtime); this checks the "doc hasn't been touched
    recently" axis instead.
    """
    findings: list[dict[str, Any]] = []
    if now is None:
        now = datetime.now()

    for pf in tree.files:
        if pf.file_type not in ("subfile", "content-schema", "content-entity"):
            continue
        lv_raw = pf.frontmatter.get("last_verified")
        if not isinstance(lv_raw, str):
            continue
        try:
            lv = datetime.strptime(lv_raw, "%Y-%m-%d")
        except ValueError:
            continue
        days_old = (now - lv).days
        if days_old > stale_days:
            findings.append({
                "file": pf.rel_str,
                "status": pf.frontmatter.get("status"),
                "last_verified": lv_raw,
                "days_old": days_old,
            })

    findings.sort(key=lambda f: -f["days_old"])
    return findings


def collect_shipped_stale(tree: Tree, threshold_days: int,
                          now: datetime | None = None) -> list[dict[str, Any]]:
    """Files at `status: shipped` whose `last_verified` is older than
    `threshold_days`. A subset of stale_sections, surfaced separately because
    shipped staleness is the highest-priority drift signal."""
    findings: list[dict[str, Any]] = []
    if now is None:
        now = datetime.now()

    for pf in tree.files:
        if pf.frontmatter.get("status") != "shipped":
            continue
        lv_raw = pf.frontmatter.get("last_verified")
        if not isinstance(lv_raw, str):
            continue
        try:
            lv = datetime.strptime(lv_raw, "%Y-%m-%d")
        except ValueError:
            continue
        days_old = (now - lv).days
        if days_old > threshold_days:
            findings.append({
                "file": pf.rel_str,
                "last_verified": lv_raw,
                "days_old": days_old,
            })

    findings.sort(key=lambda f: -f["days_old"])
    return findings


def collect_active_without_impl(tree: Tree) -> list[dict[str, Any]]:
    """Per-token: status in active set (prototyped+) but `implemented_in:` is
    empty or absent. Signals abandoned-prototype or undeclared-impl.

    `cut`, `deferred`, and `draft` tokens are exempt — code may not exist.
    """
    findings: list[dict[str, Any]] = []
    for pf, ns, tname, token in _iter_tokens(tree):
        ts = token.get("status")
        if ts not in _ACTIVE_STATUSES:
            continue
        impl = token.get("implemented_in")
        if not impl:  # None or empty list
            findings.append({
                "file": pf.rel_str,
                "token": f"{ns}.{tname}",
                "status": ts,
                "reason": "active status without implemented_in",
            })
    findings.sort(key=lambda f: (f["status"], f["file"], f["token"]))
    return findings


def status_report(tree: Tree, *, stale_days: int = 90,
                  shipped_stale_days: int = 180,
                  now: datetime | None = None) -> dict[str, Any]:
    """Build the full status report. JSON-serializable."""
    return {
        "tree_root": str(tree.root),
        "files_scanned": len(tree.files),
        "status_counts": collect_status_counts(tree),
        "stale_sections": collect_stale_sections(tree, stale_days, now),
        "shipped_stale": collect_shipped_stale(tree, shipped_stale_days, now),
        "active_without_impl": collect_active_without_impl(tree),
        "thresholds": {
            "stale_days": stale_days,
            "shipped_stale_days": shipped_stale_days,
        },
    }


def render_human(report: dict[str, Any]) -> str:
    """Render a status report for human reading. Stable column widths so
    pipes/grep work."""
    lines: list[str] = []
    lines.append(f"# gdmd status — {report['tree_root']}")
    lines.append(f"  files scanned: {report['files_scanned']}")
    lines.append("")

    lines.append("## Status counts")
    counts = report["status_counts"]
    total = sum(counts.values())
    for s in _CANONICAL_STATUS_ORDER:
        if s in counts:
            n = counts[s]
            bar = "#" * min(40, n)
            lines.append(f"  {s:14s} {n:4d}  {bar}")
    # Non-canonical values (shouldn't appear post-schema-enforcement).
    for s, n in sorted(counts.items()):
        if s not in _CANONICAL_STATUS_ORDER:
            lines.append(f"  {s:14s} {n:4d}  (non-canonical)")
    lines.append(f"  {'-' * 14} {'-' * 4}")
    lines.append(f"  {'total':14s} {total:4d}")
    lines.append("")

    stale = report["stale_sections"]
    th = report["thresholds"]["stale_days"]
    lines.append(f"## Stale sections (last_verified > {th} days ago) — {len(stale)} hits")
    if stale:
        for s in stale[:10]:
            status_str = s.get("status") or "?"
            lines.append(
                f"  {s['file']:55s} {status_str:14s} "
                f"{s['last_verified']} ({s['days_old']:4d}d)"
            )
        if len(stale) > 10:
            lines.append(f"  ... and {len(stale) - 10} more")
    lines.append("")

    shipped_stale = report["shipped_stale"]
    sth = report["thresholds"]["shipped_stale_days"]
    if shipped_stale:
        lines.append(
            f"## Shipped sections with last_verified > {sth} days ago "
            f"— {len(shipped_stale)} hits"
        )
        for s in shipped_stale[:10]:
            lines.append(
                f"  {s['file']:55s} {s['last_verified']} ({s['days_old']:4d}d)"
            )
        if len(shipped_stale) > 10:
            lines.append(f"  ... and {len(shipped_stale) - 10} more")
        lines.append("")

    active = report["active_without_impl"]
    if active:
        lines.append(
            f"## Active tokens (prototyped+) without implemented_in "
            f"— {len(active)} hits"
        )
        for a in active[:15]:
            lines.append(
                f"  {a['file']:35s} {a['token']:50s} status={a['status']}"
            )
        if len(active) > 15:
            lines.append(f"  ... and {len(active) - 15} more")

    return "\n".join(lines)
