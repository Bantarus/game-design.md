"""gdmd hook — anti-drift pre-commit workflow (Task 4 v0.3).

The bidirectional contract on `implementation_pointers:` + `implemented_in:`
has two directions:

  - **verify-side (code drifted ahead of spec):** caught by
    `gdmd lint`'s `stale-section` rule (impl mtime > last_verified +
    `--stale-days`). Existing since v0.1; extended in Task 6 with
    configurable threshold + status-aware skip.

  - **commit-side (commit touches code referenced by spec):** caught by
    `gdmd hook check`, invoked by pre-commit on staged filenames. Surfaces
    affected spec sections + suggests the follow-up `gdmd touch` command
    to bump `last_verified:` once the dev re-verifies. THIS module.

The hook is informational (exit 0 always) so it doesn't block commits;
its job is to make the spec section affected by the change *visible*
before the author has merged. The `gdmd touch` follow-up bumps
`last_verified:` atomically — manual editing is friction that gets
skipped, so we provide a single-command path.

`gdmd hook install` writes/updates `.pre-commit-config.yaml` using the
pre-commit framework convention (a `local` hook entry invoking
`gdmd hook check`). Composes cleanly with other hooks the user runs;
idempotent.

Spec → code direction (spec edit implies impl may need updating) is a
separate workflow shape (closer to design-doc-driven-development) and
deferred to v0.4+ per the minimum-extension discipline — ship what's
demanded by the observed problem (code→spec), don't preempt.

Performance budget: pre-commit hooks that take >1s get disabled by
developers. The inverted index is O(N) over spec files at build time;
staged-file lookup is O(1) per file. For 6 trees with ~20 subfiles each
this is 50-100ms easily.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from .tree import SUBFILE_NAMESPACES, ParsedFile, Tree


@dataclass(frozen=True)
class Reference:
    """A spec section that references a code path via its
    `implemented_in:` glob or the root's `implementation_pointers:` map."""

    file: str       # spec file path relative to the tree root
    location: str   # "(file-level)" | "implementation_pointers.<key>" | "<ns>.<token>"


HOOK_ENTRY_ID = "gdmd-anti-drift"


def build_inverted_index(tree: Tree) -> dict[str, list[Reference]]:
    """Build the inverse map `{resolved_code_path: [Reference, ...]}` once
    at lookup time.

    Walks every ParsedFile in the tree, expanding each `implemented_in:`
    glob (subfile-level + per-token) and the core file's
    `implementation_pointers:` map into the set of files they currently
    resolve to. The resulting map lets `gdmd hook check` answer "which
    spec sections reference this code path?" in O(1) per staged file.
    """
    index: dict[str, list[Reference]] = defaultdict(list)

    def _add(pf: ParsedFile, patterns: list, location: str) -> None:
        for pat in patterns:
            if not isinstance(pat, str):
                continue
            try:
                matches = list(tree.root.glob(pat))
            except Exception:
                matches = []
            for src in matches:
                if not src.is_file():
                    continue
                try:
                    rel = str(src.relative_to(tree.root))
                except ValueError:
                    rel = str(src)
                index[rel].append(Reference(file=pf.rel_str, location=location))

    for pf in tree.files:
        impl = pf.frontmatter.get("implemented_in") if pf.frontmatter else None
        if isinstance(impl, list):
            _add(pf, impl, "(file-level)")
        if pf.file_type == "subfile":
            for ns in SUBFILE_NAMESPACES:
                block = pf.frontmatter.get(ns)
                if not isinstance(block, dict):
                    continue
                for tname, tok in block.items():
                    if not isinstance(tok, dict):
                        continue
                    tok_impl = tok.get("implemented_in")
                    if isinstance(tok_impl, list):
                        _add(pf, tok_impl, f"{ns}.{tname}")

    if tree.core is not None:
        ip = tree.core.frontmatter.get("implementation_pointers")
        if isinstance(ip, dict):
            for key, pat in ip.items():
                if isinstance(pat, str):
                    _add(tree.core, [pat], f"implementation_pointers.{key}")

    return dict(index)


def check_staged(tree: Tree, staged_files: list[str],
                 cwd: Path | None = None) -> dict[str, list[Reference]]:
    """Intersect `staged_files` against the inverted index.

    Returns `{tree_relative_path: [Reference, ...]}` for each staged file
    referenced by at least one spec section. Files not referenced by any
    section are absent from the result (the hook stays silent on them).

    **Path normalization (pre-commit convention).** Pre-commit invokes
    hooks from the repo root and passes staged filenames as repo-relative
    paths. The inverted index is keyed by tree-relative paths. We bridge
    the two: each staged path is resolved against `cwd` (defaults to
    `Path.cwd()` — i.e. the repo root when pre-commit invoked us), then
    made relative to the tree root. Absolute staged paths and already-
    tree-relative staged paths both pass through naturally.
    """
    index = build_inverted_index(tree)
    if not index:
        return {}
    if cwd is None:
        cwd = Path.cwd()
    tree_root_abs = tree.root.resolve()
    result: dict[str, list[Reference]] = {}
    for sf in staged_files:
        p = Path(sf)
        try:
            abs_sf = (p if p.is_absolute() else (cwd / p)).resolve()
            rel = str(abs_sf.relative_to(tree_root_abs))
        except (ValueError, OSError):
            # Fallback: literal lookup (CWD already IS the tree root case).
            rel = sf
        if rel in index:
            result[rel] = index[rel]
    return result


def render_hook_output(matches: dict[str, list[Reference]],
                        tree_path: str | Path = ".") -> str:
    """Format the hook output for human reading.

    Empty matches → empty string (hook stays silent — most commits don't
    touch spec-referenced code paths, no need to spam every commit). Non-
    empty → list of affected spec files + their referenced locations,
    plus the suggested follow-up `gdmd touch` invocation.

    `tree_path` is the path the user passed to `gdmd hook check <path>`
    (e.g. `examples/tick-combat` when pre-commit invoked from repo root).
    The rendered `gdmd touch` command prefixes spec file paths with this
    so the suggestion is invocable from the user's CWD (typically the
    repo root) without rewriting.
    """
    if not matches:
        return ""

    by_spec_file: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for code_path, refs in matches.items():
        for r in refs:
            by_spec_file[r.file].append((code_path, r.location))

    tp = str(tree_path).rstrip("/")
    def _for_cmd(rel: str) -> str:
        if tp in ("", "."):
            return rel
        return f"{tp}/{rel}"

    lines = [
        "gdmd anti-drift: spec sections reference paths in your staged changes.",
        "",
    ]
    spec_files_sorted = sorted(by_spec_file)
    for sf in spec_files_sorted:
        locations = sorted({loc for _, loc in by_spec_file[sf]})
        codes = sorted({c for c, _ in by_spec_file[sf]})
        lines.append(f"  {_for_cmd(sf)}")
        lines.append(f"    locations:    {', '.join(locations)}")
        lines.append(f"    triggered by: {', '.join(codes)}")
    lines.append("")
    lines.append("If your code changes affect the design intent of these sections, re-verify")
    lines.append("and bump `last_verified:` via:")
    lines.append("")
    lines.append(f"  gdmd touch {' '.join(_for_cmd(s) for s in spec_files_sorted)}")
    return "\n".join(lines)


# ---- bump last_verified ------------------------------------------------------

_LAST_VERIFIED_RE = re.compile(
    r'(^last_verified:[ \t]*)("?\d{4}-\d{2}-\d{2}"?)([ \t]*)$',
    re.MULTILINE,
)


def bump_last_verified(subfile_path: Path, today: date | None = None) -> bool:
    """Atomically update the YAML frontmatter's `last_verified:` to today.

    Returns True if the file was modified, False if no change was needed
    (`last_verified:` already equals today, or no `last_verified:` field
    in the frontmatter).

    Implementation is regex-based on the frontmatter slab to preserve YAML
    comments, formatting, and the author's quoting choice — round-tripping
    through pyyaml would lose those.

    Raises ValueError if the file has no frontmatter (no leading `---`)
    or the frontmatter isn't closed.
    """
    if today is None:
        today = date.today()
    today_str = today.isoformat()

    content = subfile_path.read_text()
    if not content.startswith("---\n"):
        raise ValueError(
            f"{subfile_path}: no YAML frontmatter (no leading '---')"
        )
    end = content.find("\n---\n", 4)
    if end == -1:
        raise ValueError(
            f"{subfile_path}: frontmatter not closed (no trailing '---')"
        )

    fm_slab = content[4:end]
    changed = False

    def _replace(m: re.Match) -> str:
        nonlocal changed
        prefix, old_val, suffix = m.group(1), m.group(2), m.group(3)
        quoted = old_val.startswith('"')
        new_val = f'"{today_str}"' if quoted else today_str
        if new_val == old_val:
            return m.group(0)
        changed = True
        return prefix + new_val + suffix

    new_fm = _LAST_VERIFIED_RE.sub(_replace, fm_slab, count=1)
    if not changed:
        return False

    new_content = content[:4] + new_fm + content[end:]
    subfile_path.write_text(new_content)
    return True


# ---- hook installation -------------------------------------------------------


def install_hook(tree_root: Path, repo_root: Path | None = None) -> tuple[Path, str]:
    """Write/update `.pre-commit-config.yaml` to include the gdmd anti-drift
    hook as a `local` repo entry.

    Returns `(config_path, status)` where `status` is one of:
      - "created"   — `.pre-commit-config.yaml` did not exist; written.
      - "updated"   — config existed, gdmd hook was not present, appended.
      - "unchanged" — config existed and already contains the gdmd hook.

    Idempotent: a second call against a config that already contains the
    hook leaves the file completely untouched (mtime unchanged).

    The hook entry uses `language: system` so it dispatches to the
    `gdmd` binary on PATH (i.e. the same install the user already has
    after `pip install -e ".[dev]"`); no separate pre-commit-managed
    venv needed.

    `pass_filenames: true` is the pre-commit-framework default — staged
    filenames arrive as positional args to `gdmd hook check <tree>`.

    `repo_root` defaults to the current working directory (the typical
    place a user invokes `gdmd hook install <tree>` from, and the root
    where pre-commit will read `.pre-commit-config.yaml`). Pass an
    explicit `repo_root` when invoking from outside the repo (e.g. tests).
    """
    if repo_root is None:
        repo_root = Path.cwd()
    config_path = repo_root / ".pre-commit-config.yaml"

    if config_path.exists():
        try:
            existing = yaml.safe_load(config_path.read_text()) or {}
        except Exception:
            existing = {}
        if not isinstance(existing, dict):
            existing = {}
        status_label = "updated"
    else:
        existing = {}
        status_label = "created"

    repos = existing.setdefault("repos", [])
    if not isinstance(repos, list):
        repos = []
        existing["repos"] = repos

    local_repo = None
    for repo in repos:
        if isinstance(repo, dict) and repo.get("repo") == "local":
            local_repo = repo
            break
    if local_repo is None:
        local_repo = {"repo": "local", "hooks": []}
        repos.append(local_repo)

    hooks = local_repo.setdefault("hooks", [])
    if not isinstance(hooks, list):
        hooks = []
        local_repo["hooks"] = hooks

    for h in hooks:
        if isinstance(h, dict) and h.get("id") == HOOK_ENTRY_ID:
            return config_path, "unchanged"  # idempotent — file untouched

    try:
        rel_tree = str(tree_root.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        rel_tree = str(tree_root)
    if rel_tree == ".":
        entry = "gdmd hook check ."
    else:
        entry = f"gdmd hook check {rel_tree}"

    hooks.append({
        "id": HOOK_ENTRY_ID,
        "name": "gdmd anti-drift check",
        "entry": entry,
        "language": "system",
        "pass_filenames": True,
        "always_run": False,
    })

    config_path.write_text(
        yaml.safe_dump(existing, sort_keys=False, default_flow_style=False)
    )
    return config_path, status_label
