"""The compiled model behind `gdmd view` and `gdmd graph` (spec §9.9.1, D-027).

`compile_tree(root)` runs load → parse with positions → IR. The IR is a list
of **blocks** (one role each, nested) plus every **reference occurrence** in
the tree, each located to a file line and attributed to the block that
contains it. The lowering to a view lives in `view_cmd.py`; the graph
algorithms in `graph_cmd.py`.

Reference semantics are the linter's, exactly (D-027 decision 4):
extraction is `walk_refs` over frontmatter values and `TOKEN_REF_RE` over
bodies, resolution is `Tree.has_token`, the context-local prefixes are
`linter.CONTEXT_LOCAL_PREFIXES`, and a token's backlinks are the
`orphaned-entity` predicate (`backlink_matches`).

Nothing is written anywhere; the model lives only in the calling process.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import loader
from .linter import CONTEXT_LOCAL_PREFIXES
from .refs import TOKEN_REF_RE
from .tree import SUBFILE_NAMESPACES, ParsedFile, Tree

ROLES = ("token", "invariant", "content-entity", "rationale", "impl", "meta")

# Top-level keys whose block is an `impl` block rather than `meta`.
IMPL_KEYS = ("implemented_in", "implementation_pointers")


@dataclass
class Block:
    role: str
    primary: str           # stable coordinate: "{ns.id}" or "<path>#<anchor>"
    path: str              # tree-relative POSIX path
    start: int             # 1-based, inclusive, whole-file line numbers
    end: int
    status: str | None = None
    parent: int | None = None
    children: list[int] = field(default_factory=list)
    token_id: str | None = None   # "ns.id" (own id; owning token's for an impl block)
    explains: str | None = None   # rationale attribution: "ns.id"
    index: int = -1               # position in Model.blocks

    @property
    def secondary(self) -> str:
        return f"{self.path}:{self.start}-{self.end}"

    @property
    def has_identity(self) -> bool:
        return self.role in ("token", "invariant", "content-entity")

    def header(self) -> str:
        parts = [f"[{self.role}]", self.primary, self.secondary]
        if self.status is not None:
            parts.append(f"status={self.status}")
        if self.explains:
            parts.append(f"explains={{{self.explains}}}")
        return " ".join(parts)


@dataclass
class Occurrence:
    ref: str               # the inner text of "{...}"
    path: str
    line: int              # 1-based file line
    kind: str              # "value" (frontmatter) | "prose" (body)
    field: str | None      # frontmatter field path, e.g. "rules.draw.do[0].sample"
    outcome: str           # "resolved" | "unresolved" | "context-local"
    target: str | None     # longest-prefix token id ("ns.id"), or None
    source: int | None     # index of the containing block; None on a gap line

    @property
    def pointer(self) -> str:
        return f"{self.path}:{self.line}"


@dataclass
class SourceFile:
    pf: ParsedFile
    path: str
    lines: list[str]              # lines[0] is file line 1
    fm_line_offset: int
    body_line_offset: int
    node: yaml.Node | None
    fm_text: str
    innermost: list[int | None] = field(default_factory=list)  # per line (index line-1)
    outermost: list[int | None] = field(default_factory=list)

    @property
    def n_lines(self) -> int:
        return len(self.lines)

    def slice(self, start: int, end: int) -> list[str]:
        return self.lines[start - 1:end]

    @property
    def pointer(self) -> str:
        return f"{self.path}:1-{self.n_lines}"


@dataclass
class Model:
    root: Path
    tree: Tree
    files: list[SourceFile]            # canonical order (spec §9.9.3 --full)
    blocks: list[Block]                # files in canonical order, blocks in pre-order
    occurrences: list[Occurrence]
    tree_sha: str
    by_id: dict[str, int]              # token id -> block index
    by_path: dict[str, SourceFile]

    # ---- navigation --------------------------------------------------------

    def ancestors(self, b: int) -> list[int]:
        out = []
        p = self.blocks[b].parent
        while p is not None:
            out.append(p)
            p = self.blocks[p].parent
        return out[::-1]

    def descendants(self, b: int) -> list[int]:
        out = []
        for c in self.blocks[b].children:
            out.append(c)
            out.extend(self.descendants(c))
        return out

    def occurrences_in(self, b: int) -> list[Occurrence]:
        """Occurrences attributed to block `b` or any block nested in it."""
        own = {b, *self.descendants(b)}
        return [o for o in self.occurrences if o.source in own]

    # ---- the reference graph (one definition for view --ref and graph) -------

    def _index(self) -> None:
        if getattr(self, "_by_source", None) is not None:
            return
        by_source: dict[int | None, list[Occurrence]] = {}
        by_prefix: dict[str, list[Occurrence]] = {}
        for o in self.occurrences:
            by_source.setdefault(o.source, []).append(o)
            parts = o.ref.split(".")
            for k in range(1, len(parts) + 1):
                by_prefix.setdefault(".".join(parts[:k]), []).append(o)
        self._by_source = by_source
        self._by_prefix = by_prefix

    def backlinks(self, token_id: str) -> list[Occurrence]:
        """Every occurrence `r` with `r == T` or `r` starting with `T.`: the
        `orphaned-entity` predicate (`backlink_matches`), resolved or not."""
        self._index()
        return list(self._by_prefix.get(token_id, []))

    def references(self, b: int) -> list[Occurrence]:
        """The occurrences block `b` itself contains (not its nested blocks')."""
        self._index()
        return list(self._by_source.get(b, []))

    def referrers(self, b: int) -> dict[int | None, list[Occurrence]]:
        """Reverse step: blocks whose references are uses of block `b`'s token,
        each with those occurrences. Key None collects gap-line occurrences.
        Blocks without a token identity have no referrers."""
        tid = self.blocks[b].token_id if self.blocks[b].has_identity else None
        out: dict[int | None, list[Occurrence]] = {}
        if tid:
            for o in self.backlinks(tid):
                out.setdefault(o.source, []).append(o)
        return out

    def targets(self, b: int) -> dict[int, list[Occurrence]]:
        """Forward step: blocks that block `b`'s references target (longest
        prefix), each with those occurrences."""
        out: dict[int, list[Occurrence]] = {}
        for o in self.references(b):
            t = self.by_id.get(o.target) if o.target else None
            if t is not None:
                out.setdefault(t, []).append(o)
        return out

    def bfs(self, start: int, direction: str, max_hops: int | None = None
            ) -> dict[int | tuple, tuple[int, list[Occurrence]]]:
        """Breadth-first over `referrers` ("back") or `targets` ("forward").

        Returns {node: (hop, occurrences that reached it)}. Gap-line
        referrers appear as ("gap", path, line) leaves. `start` is excluded.
        """
        seen: dict[int | tuple, tuple[int, list[Occurrence]]] = {}
        frontier = [start]
        hop = 0
        visited = {start}
        while frontier and (max_hops is None or hop < max_hops):
            hop += 1
            nxt: list[int] = []
            for node in frontier:
                step = self.referrers(node) if direction == "back" else self.targets(node)
                for other, occs in step.items():
                    if other is None:  # gap-line referrers: leaves
                        for o in occs:
                            key = ("gap", o.path, o.line)
                            if key not in seen:
                                seen[key] = (hop, [o])
                        continue
                    if other in visited:
                        if other in seen and seen[other][0] == hop:
                            seen[other][1].extend(occs)
                        continue
                    visited.add(other)
                    seen[other] = (hop, list(occs))
                    nxt.append(other)
            frontier = sorted(nxt)
        return seen

    def resolve_arg(self, arg: str) -> tuple[str, str | None] | None:
        """Resolve a `{ns.id...}` CLI argument (braces optional) the way lint
        resolves a reference. Returns `(token_id, sub_path)` or None."""
        ref = arg.strip()
        if ref.startswith("{") and ref.endswith("}"):
            ref = ref[1:-1]
        if not ref or ref.split(".", 1)[0] in CONTEXT_LOCAL_PREFIXES:
            return None
        if not self.tree.has_token(ref):
            return None
        target = longest_prefix_target(self.tree, ref)
        if target is None or target not in self.by_id:
            return None
        sub = ref[len(target) + 1:] if len(ref) > len(target) else None
        return target, sub


# ---- reference semantics (the linter's) --------------------------------------

def backlink_matches(ref: str, token_id: str) -> bool:
    """The `orphaned-entity` predicate: `ref` counts as a use of `token_id`."""
    return ref == token_id or ref.startswith(token_id + ".")


def longest_prefix_target(tree: Tree, ref: str) -> str | None:
    """The longest prefix of `ref` naming a registered token (top-level or a
    content entity), as `Tree.has_token` searches it."""
    ns = ref.split(".", 1)[0]
    table = tree.tokens.get(ns)
    if not table:
        return None
    parts = ref.split(".")
    for cut in range(len(parts), 1, -1):
        prefix = ".".join(parts[:cut])
        if prefix in table:
            return prefix
    return None


def _outcome(tree: Tree, ref: str) -> str:
    if ref.split(".", 1)[0] in CONTEXT_LOCAL_PREFIXES:
        return "context-local"
    return "resolved" if tree.has_token(ref) else "unresolved"


def format_field(path: tuple[str, ...]) -> str:
    out = ""
    for seg in path:
        if seg.startswith("["):
            out += seg
        else:
            out += ("." if out else "") + seg
    return out


# ---- tree_sha ----------------------------------------------------------------

def tree_sha(tree: Tree) -> str:
    """SHA-256 of the manifest of loaded files: one `<path>\\t<sha256>\\n`
    line per file, sorted by tree-relative POSIX path (spec §9.9.1)."""
    rows = sorted(
        (pf.rel_path.as_posix(), hashlib.sha256(pf.abs_path.read_bytes()).hexdigest())
        for pf in tree.files
    )
    manifest = "".join(f"{p}\t{h}\n" for p, h in rows)
    return hashlib.sha256(manifest.encode("utf-8")).hexdigest()


# ---- extents -----------------------------------------------------------------

def _is_blank(s: str) -> bool:
    return not s.strip()


def _is_comment(s: str) -> bool:
    return s.lstrip().startswith("#")


def _last_content_line(node: yaml.Node) -> int:
    """0-based YAML line of the last content in `node`'s value.

    Block-collection end marks point at the next token (past trailing
    comments and blank lines), so the end comes from the leaves: scalars and
    flow collections. An end mark at column 0 means the value ended on the
    previous line.
    """
    if isinstance(node, (yaml.MappingNode, yaml.SequenceNode)) and not node.flow_style \
            and node.value:
        last = node.start_mark.line
        items = node.value
        for item in items:
            if isinstance(item, tuple):
                k, v = item
                last = max(last, _last_content_line(k), _last_content_line(v))
            else:
                last = max(last, _last_content_line(item))
        return last
    end = node.end_mark
    line = end.line if end.column > 0 else end.line - 1
    return max(line, node.start_mark.line)


class _FileBuilder:
    """Blocks and occurrences for one file."""

    def __init__(self, model_blocks: list[Block], sf: SourceFile, tree: Tree):
        self.blocks = model_blocks
        self.sf = sf
        self.tree = tree
        self.path = sf.path
        self.pf = sf.pf

    # line mapping
    def fm_line(self, yaml_line: int) -> int:
        return self.sf.fm_line_offset + yaml_line + 1

    def _trim_end(self, start: int, end: int) -> int:
        while end > start and _is_blank(self.sf.lines[end - 1]):
            end -= 1
        return end

    def add(self, block: Block) -> int:
        block.index = len(self.blocks)
        self.blocks.append(block)
        if block.parent is not None:
            self.blocks[block.parent].children.append(block.index)
        return block.index

    # frontmatter -------------------------------------------------------------

    def pair_extent(self, k: yaml.Node, v: yaml.Node) -> tuple[int, int]:
        start = self.fm_line(k.start_mark.line)
        end = self.fm_line(max(k.start_mark.line, _last_content_line(v)))
        return start, self._trim_end(start, end)

    def leading_comments(self, start: int, floor: int) -> int:
        """Extend `start` upward over contiguous comment lines, not above `floor`."""
        s = start
        while s - 1 >= floor and _is_comment(self.sf.lines[s - 2]):
            s -= 1
        return s

    def impl_child(self, parent: int, value: yaml.Node, token_id: str | None,
                   primary: str) -> None:
        if not isinstance(value, yaml.MappingNode):
            return
        for k, v in value.value:
            if isinstance(k, yaml.ScalarNode) and k.value == "implemented_in":
                start, end = self.pair_extent(k, v)
                self.add(Block(role="impl", primary=primary, path=self.path,
                               start=start, end=end, parent=parent,
                               token_id=token_id))

    def frontmatter(self) -> None:
        node = self.sf.node
        if not isinstance(node, yaml.MappingNode):
            return
        ft = self.pf.file_type
        if ft == "content-entity":
            self.content_entity()
            return
        for k, v in node.value:
            key = k.value if isinstance(k, yaml.ScalarNode) else str(k.value)
            if ft == "subfile" and key in SUBFILE_NAMESPACES \
                    and isinstance(v, yaml.MappingNode):
                self.namespace(key, k, v)
                continue
            start, end = self.pair_extent(k, v)
            role = "impl" if key in IMPL_KEYS else "meta"
            self.add(Block(role=role, primary=f"{self.path}#{key}", path=self.path,
                           start=start, end=end))

    def namespace(self, ns: str, ns_key: yaml.Node, ns_val: yaml.MappingNode) -> None:
        values = self.pf.frontmatter.get(ns) or {}
        floor = self.fm_line(ns_key.start_mark.line) + 1
        for tk, tv in ns_val.value:
            tid = f"{ns}.{tk.value}"
            start, end = self.pair_extent(tk, tv)
            start = self.leading_comments(start, floor)
            val = values.get(tk.value) if isinstance(values, dict) else None
            status = val.get("status") if isinstance(val, dict) else None
            b = self.add(Block(
                role="invariant" if ns == "invariants" else "token",
                primary=f"{{{tid}}}", path=self.path, start=start, end=end,
                status=status if isinstance(status, str) else None, token_id=tid,
            ))
            self.impl_child(b, tv, tid, f"{{{tid}}}")
            floor = end + 1

    def content_entity(self) -> None:
        fm = self.pf.frontmatter
        kind = self.pf.rel_path.parent.name
        eid = fm.get("id")
        tid = f"entities.{kind}.{eid}" if isinstance(eid, str) else None
        end = len(self.sf.lines)
        while end > 1 and _is_blank(self.sf.lines[end - 1]):
            end -= 1
        status = fm.get("status")
        primary = f"{{{tid}}}" if tid else f"{self.path}#"
        b = self.add(Block(role="content-entity", primary=primary, path=self.path,
                           start=1, end=max(end, 1),
                           status=status if isinstance(status, str) else None,
                           token_id=tid))
        self.impl_child(b, self.sf.node, tid, primary)

    # body ---------------------------------------------------------------------

    _HEADING_RE = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
    _FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")

    def headings(self) -> list[tuple[int, int, str]]:
        """(file line, level, text) for every ATX heading outside code fences."""
        out = []
        fence: str | None = None
        first = self.sf.body_line_offset + 1
        for ln in range(first, len(self.sf.lines) + 1):
            line = self.sf.lines[ln - 1]
            m = self._FENCE_OPEN_RE.match(line)
            if fence is not None:
                if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) \
                        and not line.strip()[len(m.group(1)):].strip():
                    fence = None
                continue
            if m:
                fence = m.group(1)
                continue
            h = self._HEADING_RE.match(line)
            if h:
                text = re.sub(r"[ \t]+#+$", "", h.group(2) or "").strip()
                out.append((ln, len(h.group(1)), text))
        return out

    def rationale(self) -> None:
        if self.pf.abs_path.suffix != ".md" or self.pf.file_type == "content-entity":
            return
        hs = self.headings()
        own_ids = {b.token_id.split(".", 1)[1]: b.token_id for b in self.blocks
                   if b.path == self.path and b.role in ("token", "invariant")
                   and b.token_id}
        last = len(self.sf.lines)

        def section_end(i: int, level: int) -> int:
            nxt = next((ln for ln, lv, _ in hs[i + 1:] if lv <= level), last + 1)
            return nxt - 1

        h2: int | None = None
        h2_text = ""
        for i, (ln, level, text) in enumerate(hs):
            if level <= 2:
                h2 = None
            if level == 2:
                end = self._trim_end(ln, section_end(i, 2))
                h2 = self.add(Block(role="rationale", primary=f"{self.path}#{text}",
                                    path=self.path, start=ln, end=end))
                h2_text = text
            elif level == 3 and h2 is not None:
                end = self._trim_end(ln, section_end(i, 3))
                self.add(Block(role="rationale",
                               primary=f"{self.path}#{h2_text}/{text}",
                               path=self.path, start=ln, end=end, parent=h2,
                               explains=own_ids.get(text)))

    # occurrences ----------------------------------------------------------------

    def occurrences(self, out: list[Occurrence]) -> None:
        if self.sf.node is not None:
            for ref, path, line in self._node_refs(self.sf.node, ()):
                out.append(self._occ(ref, line, "value", format_field(path)))
        body = self.pf.body or ""
        for m in TOKEN_REF_RE.finditer(body):
            line = self.sf.body_line_offset + body.count("\n", 0, m.start()) + 1
            out.append(self._occ(m.group(1), line, "prose", None))

    def _occ(self, ref: str, line: int, kind: str, fld: str | None) -> Occurrence:
        # A value reference belongs to its outermost frontmatter block (the
        # token, entity or meta key); a prose reference to its innermost
        # rationale section. A reference on a gap line has no block.
        src = (self.sf.outermost if kind == "value" else self.sf.innermost)[line - 1]
        outcome = _outcome(self.tree, ref)
        target = None if outcome == "context-local" else longest_prefix_target(self.tree, ref)
        return Occurrence(ref=ref, path=self.path, line=line, kind=kind, field=fld,
                          outcome=outcome, target=target, source=src)

    def _node_refs(self, node: yaml.Node, path: tuple[str, ...]):
        """(ref, path, file line) in the order `walk_refs` yields them."""
        if isinstance(node, yaml.MappingNode):
            for k, v in node.value:
                yield from self._node_refs(v, path + (str(k.value),))
        elif isinstance(node, yaml.SequenceNode):
            for i, v in enumerate(node.value):
                yield from self._node_refs(v, path + (f"[{i}]",))
        elif isinstance(node, yaml.ScalarNode) and node.tag == "tag:yaml.org,2002:str":
            refs = [m.group(1) for m in TOKEN_REF_RE.finditer(node.value)]
            if not refs:
                return
            span = self.sf.fm_text[node.start_mark.index:node.end_mark.index]
            found = [(m.group(1), m.start()) for m in TOKEN_REF_RE.finditer(span)]
            if [r for r, _ in found] == refs:
                for r, off in found:
                    yl = self.sf.fm_text.count("\n", 0, node.start_mark.index + off)
                    yield r, path, self.fm_line(yl)
            else:  # escaped or otherwise rewritten scalar: fall back to its first line
                for r in refs:
                    yield r, path, self.fm_line(node.start_mark.line)


def _split_lines(text: str) -> list[str]:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _canonical_files(tree: Tree) -> list[ParsedFile]:
    """Core file, then the core `files:` map order, then the other files by
    POSIX path, then content entities by kind and id (spec §9.9.3)."""
    by_posix = {pf.rel_path.as_posix(): pf for pf in tree.files}
    order: list[ParsedFile] = []
    seen: set[str] = set()

    def take(pf: ParsedFile) -> None:
        key = pf.rel_path.as_posix()
        if key not in seen:
            seen.add(key)
            order.append(pf)

    if tree.core is not None:
        take(tree.core)
        files_map = tree.core.frontmatter.get("files")
        if isinstance(files_map, dict):
            for v in files_map.values():
                if isinstance(v, str) and Path(v).as_posix() in by_posix:
                    take(by_posix[Path(v).as_posix()])
    for key in sorted(by_posix):
        if by_posix[key].file_type != "content-entity":
            take(by_posix[key])
    ents = sorted(
        (pf for pf in tree.files if pf.file_type == "content-entity"),
        key=lambda pf: (pf.rel_path.parent.name,
                        str(pf.frontmatter.get("id") or pf.rel_path.stem),
                        pf.rel_path.as_posix()),
    )
    for pf in ents:
        take(pf)
    return order


def compile_tree(root: Path) -> Model:
    """Compile a tree into the view IR. Pure: reads files, writes nothing."""
    positioned: dict[Path, loader.Positioned] = {}

    def reader(p: Path):
        r = loader.read_positioned(p)
        positioned[p] = r
        return r.frontmatter, r.body

    tree = Tree.load(Path(root), reader=reader)
    blocks: list[Block] = []
    files: list[SourceFile] = []
    builders: list[_FileBuilder] = []
    for pf in _canonical_files(tree):
        pos = positioned[pf.abs_path]
        sf = SourceFile(pf=pf, path=pf.rel_path.as_posix(), lines=_split_lines(pos.text),
                        fm_line_offset=pos.fm_line_offset,
                        body_line_offset=pos.body_line_offset,
                        node=pos.node, fm_text=pos.fm_text)
        fb = _FileBuilder(blocks, sf, tree)
        first = len(blocks)
        fb.frontmatter()
        fb.rationale()
        # per-line innermost / outermost block
        sf.innermost = [None] * sf.n_lines
        sf.outermost = [None] * sf.n_lines
        for b in blocks[first:]:
            for ln in range(b.start, b.end + 1):
                sf.innermost[ln - 1] = b.index      # pre-order: children overwrite
                if b.parent is None:
                    sf.outermost[ln - 1] = b.index
        files.append(sf)
        builders.append(fb)
    occurrences: list[Occurrence] = []
    for fb in builders:
        fb.occurrences(occurrences)

    # The block a token id resolves to is the one `Tree` registered (the last
    # definition wins there, as in lint).
    identity = {(b.token_id, b.path): b.index for b in reversed(blocks)
                if b.has_identity and b.token_id}
    by_id: dict[str, int] = {}
    for table in tree.tokens.values():
        for tid, (pf, _) in table.items():
            b = identity.get((tid, pf.rel_path.as_posix()))
            if b is not None:
                by_id[tid] = b
    return Model(root=Path(root), tree=tree, files=files, blocks=blocks,
                 occurrences=occurrences, tree_sha=tree_sha(tree), by_id=by_id,
                 by_path={sf.path: sf for sf in files})
