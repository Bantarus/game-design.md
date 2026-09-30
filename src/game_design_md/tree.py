"""In-memory representation of a game-design.md tree.

`Tree.load(root)` walks a directory, parses every `.md` and `.yaml` file
with the shared `GdmdLoader`, classifies each file by `file_type:`, and
builds a token index. `Tree.has_token(ref)` answers whether a `{ns.id...}`
reference resolves.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import loader

# The value-bearing namespaces a subfile may declare in its frontmatter.
# `events` (D-005) joined the surface at v0.2.0-alpha: every state-machine
# transition's `event:` value resolves to a {events.<id>} token.
# `clocks` (F-010 resolution) joined at v0.3: first-class time-passage
# primitive distinct from player verbs.
SUBFILE_NAMESPACES = (
    "entities", "verbs", "resources", "states", "rules", "loops",
    "distributions", "feel", "balance_targets", "invariants", "events",
    "clocks",
)


def find_repo_root(path: Path) -> Path | None:
    """The git work tree containing `path`: the nearest ancestor (or `path`
    itself) holding a `.git` entry, a directory or, for a worktree or a
    submodule, a file. None when `path` is in no git repository (D-038)."""
    p = Path(path).resolve()
    for d in (p, *p.parents):
        if (d / ".git").exists():
            return d
    return None


@dataclass
class ParsedFile:
    abs_path: Path
    rel_path: Path
    frontmatter: dict
    body: str
    file_type: str | None = None

    @property
    def rel_str(self) -> str:
        return str(self.rel_path)


@dataclass
class Tree:
    root: Path
    files: list[ParsedFile] = field(default_factory=list)
    by_rel: dict[str, ParsedFile] = field(default_factory=dict)
    core: ParsedFile | None = None
    # ns -> { "ns.top_level_id": (defining_file, value) }
    tokens: dict[str, dict[str, tuple[ParsedFile, Any]]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    # collection_name -> list of ParsedFile (content-entity files)
    content_entities: dict[str, list[ParsedFile]] = field(
        default_factory=lambda: defaultdict(list)
    )
    # entity collection name -> ParsedFile (the content-schema file)
    content_schemas: dict[str, ParsedFile] = field(default_factory=dict)
    # Parser errors encountered during load.
    parse_errors: list[tuple[Path, str]] = field(default_factory=list)

    @classmethod
    def load(cls, root: Path, reader=None) -> "Tree":
        """Load every `.md` / `.yaml` file under `root`.

        `reader(path) -> (frontmatter, body)` defaults to `loader.read`. The
        views compiler (`ir.py`) passes a reader that also keeps positions,
        so each file is still parsed once.
        """
        reader = reader or loader.read
        tree = cls(root=Path(root))
        for p in sorted(tree.root.rglob("*")):
            if not p.is_file() or p.suffix not in (".md", ".yaml", ".yml"):
                continue
            try:
                fm, body = reader(p)
            except Exception as e:  # noqa: BLE001
                tree.parse_errors.append((p, str(e)))
                continue
            if fm is None:
                continue
            ft = fm.get("file_type") if isinstance(fm, dict) else None
            pf = ParsedFile(
                abs_path=p,
                rel_path=p.relative_to(tree.root),
                frontmatter=fm if isinstance(fm, dict) else {},
                body=body,
                file_type=ft,
            )
            tree.files.append(pf)
            tree.by_rel[pf.rel_str] = pf
            if ft == "core":
                tree.core = pf
            elif ft == "content-entity":
                tree.content_entities[p.parent.name].append(pf)
            elif ft == "content-schema":
                ent = pf.frontmatter.get("entity")
                if isinstance(ent, str):
                    tree.content_schemas[ent] = pf
        tree._index_tokens()
        return tree

    def _index_tokens(self) -> None:
        for pf in self.files:
            if pf.file_type != "subfile":
                continue
            for ns in SUBFILE_NAMESPACES:
                block = pf.frontmatter.get(ns)
                if not isinstance(block, dict):
                    continue
                for k, v in block.items():
                    self.tokens[ns][f"{ns}.{k}"] = (pf, v)
        # Content-entity files: `entities.<kind>.<id>`. These are not subject
        # to the orphan check individually (see linter.rule_orphaned_entity).
        for kind, entities in self.content_entities.items():
            for pf in entities:
                eid = pf.frontmatter.get("id")
                if isinstance(eid, str):
                    self.tokens["entities"][f"entities.{kind}.{eid}"] = (
                        pf, pf.frontmatter,
                    )

    # ---- Reference resolution ------------------------------------------------

    @staticmethod
    def has_namespace(ns: str) -> bool:
        """D-033: a whole-namespace reference `{ns}` resolves iff `ns` is a
        namespace the tree indexes, whether or not the tree declares a token
        in it yet (a starter's invariant may govern tokens still to come)."""
        return ns in SUBFILE_NAMESPACES

    def resolves(self, ref: str) -> bool:
        """The `broken-ref` predicate for any reference body walk_refs yields:
        a one-segment body is a whole-namespace reference (D-033)."""
        return self.has_namespace(ref) if "." not in ref else self.has_token(ref)

    def has_token(self, ref: str) -> bool:
        """True iff `ref` (e.g. "verbs.play_card", "entities.cards.ember_strike",
        "states.card_lifecycle.in_hand") resolves to a defined token or a
        sub-path of one."""
        ns = ref.split(".", 1)[0]
        if ns not in self.tokens:
            return False
        ns_table = self.tokens[ns]
        # Exact top-level hit.
        if ref in ns_table:
            return True
        # Sub-path of a registered top-level token.
        # Try progressively shorter prefixes.
        parts = ref.split(".")
        for cut in range(len(parts) - 1, 0, -1):
            prefix = ".".join(parts[:cut])
            if prefix in ns_table:
                rest = parts[cut:]
                _, value = ns_table[prefix]
                return self._walks(value, rest)
        return False

    @staticmethod
    def _walks(value: Any, rest: list[str]) -> bool:
        """Does `rest` (a list of segments) navigate a real sub-path inside `value`?"""
        cur = value
        for seg in rest:
            if isinstance(cur, dict):
                if seg in cur:
                    cur = cur[seg]
                    continue
                # For state machines: nodes is a list of {id: <seg>, ...}.
                if "nodes" in cur and isinstance(cur["nodes"], list):
                    matched = next(
                        (n for n in cur["nodes"]
                         if isinstance(n, dict) and n.get("id") == seg),
                        None,
                    )
                    if matched is not None:
                        cur = matched
                        continue
                return False
            if isinstance(cur, list):
                # Allow numeric index "0" through. Rarely needed.
                try:
                    cur = cur[int(seg)]
                    continue
                except (ValueError, IndexError):
                    return False
            return False
        return True

    # ---- Convenience accessors -----------------------------------------------

    def top_level_tokens(self, ns: str) -> dict[str, tuple[ParsedFile, Any]]:
        """Top-level tokens in `ns`. Excludes the per-content-entity registrations
        in `entities.<kind>.<id>` (those are filtered out)."""
        if ns != "entities":
            return dict(self.tokens.get(ns, {}))
        return {k: v for k, v in self.tokens.get(ns, {}).items()
                if k.count(".") == 1}
