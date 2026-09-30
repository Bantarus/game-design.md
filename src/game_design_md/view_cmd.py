"""`gdmd view`: projected views over a compiled tree (spec §9.9.2–§9.9.3, D-027).

Every view lowers the IR from `ir.py` under the normative lowering rule
(§9.9.2): it emits only verbatim slices of tree files (whole source lines),
coordinates, and deterministic annotations. Every omission inside an
emitted block is an elision marker carrying the pointer of what it omits.

Text output is line-oriented, and every verbatim line's number can be read
off the output:
- In `--full`, `--grep` and `--ref`'s focus block, a header
  (`[role] <primary> <path>:<a>-<b>`), a `[gap] <path>:<a>-<b>` marker or an
  elision marker (`… N lines · <path>:<a>-<b>`) sets the position, and each
  following verbatim line is the next line of that file. `[file]` and
  `[view ...]` lines are annotations.
- In `--ref`'s listings, each referencing line is printed on the line after
  its `<path>:<line> <kind> <field>` pointer.
- The overview and `--flat` print no source lines.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import yaml

from .ir import Block, Model, Occurrence, SourceFile, _last_content_line
from .tree import SUBFILE_NAMESPACES


# ---- shared pieces ---------------------------------------------------------------

def elision(path: str, a: int, b: int) -> str:
    n = b - a + 1
    return f"… {n} line{'s' if n != 1 else ''} · {path}:{a}-{b}"


def view_header(mode: str, tree_arg: str, sha: str) -> str:
    return f"[view {mode}] {tree_arg} tree_sha={sha}"


def status_str(s: str | None) -> str:
    return s if s is not None else "-"


def flat_line(b: Block, extra: str = "") -> str:
    line = f"{b.role} {b.primary} {b.secondary} {status_str(b.status)}"
    return f"{line} {extra}" if extra else line


def block_meta(b: Block) -> dict:
    d = {"role": b.role, "id": b.primary, "pointer": b.secondary, "status": b.status}
    if b.explains:
        d["explains"] = "{" + b.explains + "}"
    return d


def occ_json(o: Occurrence, model: Model, with_text: bool = False) -> dict:
    d = {"ref": "{" + o.ref + "}", "pointer": o.pointer, "kind": o.kind,
         "outcome": o.outcome}
    if o.field is not None:
        d["field"] = o.field
    if o.target is not None:
        d["target"] = "{" + o.target + "}"
        t = model.by_id.get(o.target)
        if t is not None:
            d["target_pointer"] = model.blocks[t].secondary
    if with_text:
        d["text"] = model.by_path[o.path].lines[o.line - 1]
    return d


def role_ok(b: Block, roles: tuple[str, ...]) -> bool:
    return not roles or b.role in roles


def verbatim_block(model: Model, b: Block) -> list[str]:
    """Block `b`'s lines verbatim, with the headers of nested blocks inserted
    as annotations just before the line each nested block starts on."""
    sf = model.by_path[b.path]
    starts: dict[int, list[Block]] = {}
    for d in model.descendants(b.index):
        starts.setdefault(model.blocks[d].start, []).append(model.blocks[d])
    out = []
    for ln in range(b.start, b.end + 1):
        for nb in starts.get(ln, []):
            out.append(nb.header())
        out.append(sf.lines[ln - 1])
    return out


def ancestor_key_lines(sf: SourceFile, line: int) -> list[int]:
    """File lines of the mapping keys and sequence items that enclose `line`
    in the frontmatter (namespace → token → field …), outermost first."""
    node = sf.node
    if node is None:
        return []
    yline = line - sf.fm_line_offset - 1
    out: list[int] = []
    while isinstance(node, (yaml.MappingNode, yaml.SequenceNode)) and not node.flow_style:
        nxt = None
        if isinstance(node, yaml.MappingNode):
            for k, v in node.value:
                s = k.start_mark.line
                if s <= yline <= max(s, _last_content_line(v)):
                    if s < yline:
                        out.append(s)
                    nxt = v
                    break
        else:
            for item in node.value:
                s = item.start_mark.line
                if s <= yline <= _last_content_line(item):
                    if s < yline:
                        out.append(s)
                    nxt = item
                    break
        if nxt is None:
            break
        node = nxt
    return [sf.fm_line_offset + y + 1 for y in out]


def in_frontmatter(sf: SourceFile, line: int) -> bool:
    return sf.node is not None and line <= sf.body_line_offset if sf.path.endswith(".md") \
        else sf.node is not None


# ---- overview ---------------------------------------------------------------------

def view_overview(model: Model, tree_arg: str, roles: tuple[str, ...]) -> dict:
    files = []
    for sf in model.files:
        if sf.pf.file_type == "content-entity":
            continue
        fm = sf.pf.frontmatter
        lv = fm.get("last_verified")
        files.append({"path": sf.path, "file_type": sf.pf.file_type,
                      "status": fm.get("status") if isinstance(fm.get("status"), str) else None,
                      "last_verified": lv if isinstance(lv, str) else None,
                      "pointer": sf.pointer})
    namespaces: dict[str, list[dict]] = {}
    for ns in SUBFILE_NAMESPACES:
        role = "invariant" if ns == "invariants" else "token"
        if roles and role not in roles:
            continue
        rows = [block_meta(b) for b in model.blocks
                if b.role == role and b.token_id and b.token_id.split(".", 1)[0] == ns]
        if rows:
            namespaces[ns] = rows
    content = []
    if not roles or "content-entity" in roles:
        kinds: dict[str, list[Block]] = {}
        for b in model.blocks:
            if b.role == "content-entity":
                kinds.setdefault(model.by_path[b.path].pf.rel_path.parent.name, []).append(b)
        for kind, bs in kinds.items():
            by_status: dict[str, int] = {}
            for b in bs:
                by_status[status_str(b.status)] = by_status.get(status_str(b.status), 0) + 1
            schema = model.tree.content_schemas.get(kind)
            content.append({
                "kind": kind, "count": len(bs), "by_status": by_status,
                "schema_pointer": (model.by_path[schema.rel_path.as_posix()].pointer
                                   if schema is not None else None),
            })
    others = [block_meta(b) for b in model.blocks
              if roles and b.role in roles
              and b.role in ("rationale", "impl", "meta")]
    return {"files": files, "namespaces": namespaces, "content": content,
            "blocks": others}


def text_overview(model: Model, tree_arg: str, data: dict) -> list[str]:
    out = [view_header("overview", tree_arg, model.tree_sha), "files:"]
    for f in data["files"]:
        out.append(f"  {f['path']} {f['file_type']} status={status_str(f['status'])} "
                   f"last_verified={status_str(f['last_verified'])} {f['pointer']}")
    for ns, rows in data["namespaces"].items():
        out.append(f"{ns}:")
        for r in rows:
            out.append(f"  {r['id']} {status_str(r['status'])} {r['pointer']}")
    if data["content"]:
        out.append("content entities:")
        total = 0
        for c in data["content"]:
            total += c["count"]
            st = ", ".join(f"{k} {v}" for k, v in c["by_status"].items())
            out.append(f"  {c['kind']}: {c['count']} ({st}) schema "
                       f"{c['schema_pointer'] or '-'}")
        out.append(f"… {total} content entities · gdmd view {tree_arg} "
                   f"--flat --role content-entity")
    if data["blocks"]:
        out.append("blocks:")
        for r in data["blocks"]:
            out.append(f"  [{r['role']}] {r['id']} {r['pointer']}")
    return out


# ---- --full -----------------------------------------------------------------------

def full_items(model: Model, roles: tuple[str, ...]):
    """Yield ("file", sf) / ("block", b) / ("gap", sf, a, b) in canonical order."""
    for sf in model.files:
        items = []
        if not roles:
            ln = 1
            while ln <= sf.n_lines:
                b = sf.outermost[ln - 1]
                if b is not None:
                    blk = model.blocks[b]
                    items.append(("block", blk))
                    ln = blk.end + 1
                    continue
                a = ln
                while ln <= sf.n_lines and sf.outermost[ln - 1] is None:
                    ln += 1
                z = ln - 1
                while a <= z and not sf.lines[a - 1].strip():
                    a += 1
                while z >= a and not sf.lines[z - 1].strip():
                    z -= 1
                if a <= z:
                    items.append(("gap", sf, a, z))
        else:
            emitted: set[int] = set()
            for blk in model.blocks:
                if blk.path != sf.path or blk.role not in roles:
                    continue
                if any(a in emitted for a in model.ancestors(blk.index)):
                    continue
                emitted.add(blk.index)
                items.append(("block", blk))
        if items:
            yield ("file", sf)
            yield from items


def view_full(model: Model, tree_arg: str, roles: tuple[str, ...]):
    text = [view_header("full", tree_arg, model.tree_sha)]
    blocks, gaps = [], []
    for item in full_items(model, roles):
        if item[0] == "file":
            sf = item[1]
            text.append(f"[file] {sf.path} {sf.pf.file_type}")
        elif item[0] == "block":
            b = item[1]
            text.append(b.header())
            lines = verbatim_block(model, b)
            text.extend(lines)
            d = block_meta(b)
            d["source"] = "\n".join(model.by_path[b.path].slice(b.start, b.end))
            d["children"] = [block_meta(model.blocks[c]) for c in model.descendants(b.index)]
            blocks.append(d)
        else:
            _, sf, a, z = item
            text.append(f"[gap] {sf.path}:{a}-{z}")
            text.extend(sf.slice(a, z))
            gaps.append({"pointer": f"{sf.path}:{a}-{z}",
                         "source": "\n".join(sf.slice(a, z))})
    return text, {"blocks": blocks, "gaps": gaps}


# ---- --grep -----------------------------------------------------------------------

@dataclass
class _Unit:
    """One rendering unit of --grep: an outermost block and what it shows."""
    root: Block
    selected: set[int]
    lines: set[int]


def _select_block(model: Model, sf: SourceFile, line: int,
                  roles: tuple[str, ...]) -> int | None:
    """The innermost block containing `line` whose role is selected."""
    b = sf.innermost[line - 1]
    while b is not None and not role_ok(model.blocks[b], roles):
        b = model.blocks[b].parent
    return b


def _outermost(model: Model, b: int) -> Block:
    anc = model.ancestors(b)
    return model.blocks[anc[0] if anc else b]


def render_unit(model: Model, root: Block, show: set[int], headers: set[int]
                ) -> tuple[list[str], list[dict]]:
    """Lower `root` to: its header, the lines in `show` (verbatim), the
    headers of the nested blocks in `headers`, and one elision marker per
    maximal run of omitted lines."""
    path = root.path
    sf = model.by_path[path]
    starts: dict[int, list[Block]] = {}
    for h in sorted(headers):
        if h != root.index:
            starts.setdefault(model.blocks[h].start, []).append(model.blocks[h])
    out = [root.header()]
    elided: list[dict] = []
    run: int | None = None

    def flush(upto: int) -> None:
        nonlocal run
        if run is not None:
            out.append(elision(path, run, upto))
            elided.append({"pointer": f"{path}:{run}-{upto}", "lines": upto - run + 1})
            run = None

    for ln in range(root.start, root.end + 1):
        if ln in starts:
            flush(ln - 1)
            out.extend(nb.header() for nb in starts[ln])
        if ln in show:
            flush(ln - 1)
            out.append(sf.lines[ln - 1])
        elif run is None:
            run = ln
    flush(root.end)
    return out, elided


def view_grep(model: Model, tree_arg: str, pattern: str, ignore_case: bool,
              roles: tuple[str, ...]):
    rx = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    units: dict[int, _Unit] = {}

    def unit_for(root: Block) -> _Unit:
        if root.index not in units:
            units[root.index] = _Unit(root=root, selected=set(), lines=set())
        return units[root.index]

    for b in model.blocks:  # a match on a block's primary coordinate
        if role_ok(b, roles) and rx.search(b.primary):
            unit_for(_outermost(model, b.index)).selected.add(b.index)
    for sf in model.files:
        for ln in range(1, sf.n_lines + 1):
            if not rx.search(sf.lines[ln - 1]):
                continue
            b = _select_block(model, sf, ln, roles)
            if b is None:  # a gap line: --grep selects blocks only (§9.9.3)
                continue
            u = unit_for(_outermost(model, b))
            u.selected.add(b)
            u.lines.add(ln)

    text = [view_header("grep", tree_arg, model.tree_sha)]
    out_json = []
    current_file = None
    last_context: list[int] = []
    for k in sorted(units):  # block indices are in canonical order
        u = units[k]
        path = u.root.path
        sf = model.by_path[path]
        if path != current_file:
            text.append(f"[file] {path} {sf.pf.file_type}")
            current_file = path
            last_context = []
        show: set[int] = set(u.lines)
        headers: set[int] = set()
        for s in u.selected:
            headers.add(s)
            headers.update(model.ancestors(s))
        for ln in u.lines:
            if in_frontmatter(sf, ln):
                show.update(ancestor_key_lines(sf, ln))
            inner = sf.innermost[ln - 1]
            for a in model.ancestors(inner) + [inner]:
                if model.blocks[a].role == "rationale":
                    show.add(model.blocks[a].start)   # the section headings
        # Ancestor key lines outside the block (the namespace key) are gap
        # lines: each is printed with its own pointer, before the block, once
        # per run of consecutive blocks under it.
        context = sorted(ln for ln in show if not u.root.start <= ln <= u.root.end)
        if context and context != last_context:
            for ln in context:
                text.append(f"[gap] {path}:{ln}-{ln}")
                text.append(sf.lines[ln - 1])
            last_context = context
        rendered, elided = render_unit(model, u.root, show, headers)
        text.extend(rendered)
        d = block_meta(u.root)
        d["context"] = [{"pointer": f"{path}:{ln}-{ln}", "text": sf.lines[ln - 1]}
                        for ln in context]
        d["selected"] = [block_meta(model.blocks[s]) for s in
                         sorted(u.selected, key=lambda i: (model.blocks[i].start, i))]
        d["matches"] = sorted(u.lines)
        d["source"] = "\n".join(rendered[1:])
        d["elided"] = elided
        out_json.append(d)
    return text, {"blocks": out_json}


# ---- --ref ------------------------------------------------------------------------

def _node_header(model: Model, node) -> str:
    if isinstance(node, tuple):
        _, path, line = node
        return f"[gap] {path}:{line}-{line}"
    return model.blocks[node].header()


def _node_json(model: Model, node) -> dict:
    if isinstance(node, tuple):
        _, path, line = node
        return {"role": "gap", "pointer": f"{path}:{line}-{line}"}
    return block_meta(model.blocks[node])


def _node_role(model: Model, node) -> str:
    return "gap" if isinstance(node, tuple) else model.blocks[node].role


def _node_sort(model: Model, node):
    rank = {sf.path: i for i, sf in enumerate(model.files)}
    if isinstance(node, tuple):
        return (rank[node[1]], node[2], 1)
    b = model.blocks[node]
    return (rank[b.path], b.start, 0)


def view_ref(model: Model, tree_arg: str, focus: int, sub_path: str | None, hops: int,
             roles: tuple[str, ...]):
    fb = model.blocks[focus]
    text = [view_header("ref", tree_arg, model.tree_sha)]
    head = fb.header() + (f" sub_path={sub_path}" if sub_path else "")
    text.append(head)
    text.extend(verbatim_block(model, fb))
    fwd_occ = sorted(model.occurrences_in(focus), key=lambda o: (o.line, o.ref))
    forward_json = []
    text.append(f"forward ({len(fwd_occ)}):")
    for o in fwd_occ:
        t = model.by_id.get(o.target) if o.target else None
        if t is not None and roles and model.blocks[t].role not in roles:
            continue
        where = o.field if o.field is not None else "body"
        tgt = f" → {model.blocks[t].header()}" if t is not None else ""
        text.append(f"  {{{o.ref}}} {o.outcome} {where} {o.pointer}{tgt}")
        forward_json.append(occ_json(o, model))
    back = model.bfs(focus, "back", hops)
    fwd = model.bfs(focus, "forward", hops)
    neighbors_json = []

    def listing(label: str, found: dict, direction: str, hop: int) -> None:
        nodes = sorted((n for n, (h, _) in found.items() if h == hop
                        and (not roles or _node_role(model, n) in roles)),
                       key=lambda n: _node_sort(model, n))
        if hop == 1 and direction == "back":
            count = sum(len(found[n][1]) for n in nodes)
            text.append(f"{label} ({count}):")
        else:
            text.append(f"{label} ({len(nodes)}):")
        for n in nodes:
            occs = sorted(found[n][1], key=lambda o: (o.path, o.line, o.ref))
            text.append("  " + _node_header(model, n))
            seen_lines = set()
            for o in occs:
                if (o.path, o.line) in seen_lines:
                    continue
                seen_lines.add((o.path, o.line))
                where = o.field if o.field is not None else "body"
                text.append(f"    {o.pointer} {o.kind} {where}")
                text.append(model.by_path[o.path].lines[o.line - 1])
            neighbors_json.append({"hop": hop, "direction": direction,
                                   "block": _node_json(model, n),
                                   "via": [occ_json(o, model, with_text=True) for o in occs]})

    listing("backlinks", back, "back", 1)
    for hop in range(2, hops + 1):
        listing(f"hop {hop} forward", fwd, "forward", hop)
        listing(f"hop {hop} backward", back, "back", hop)
    focus_json = block_meta(fb)
    focus_json["source"] = "\n".join(model.by_path[fb.path].slice(fb.start, fb.end))
    data = {"focus": focus_json, "sub_path": sub_path, "forward": forward_json,
            "backlinks": [n for n in neighbors_json if n["hop"] == 1],
            "neighbors": [n for n in neighbors_json if n["hop"] > 1]}
    return text, data


# ---- --flat -----------------------------------------------------------------------

def flat_rows(model: Model, mode: str, roles: tuple[str, ...], grep_json=None,
              ref_ctx=None) -> list[tuple[Block, str]]:
    if mode in ("overview", "full"):
        return [(b, "") for b in model.blocks if role_ok(b, roles)]
    if mode == "grep":
        by_pointer = {(b.primary, b.secondary): b for b in model.blocks}
        rows = []
        for d in grep_json["blocks"]:
            for sel in d.get("selected", []):
                rows.append((by_pointer[(sel["id"], sel["pointer"])], ""))
        return rows
    focus, hops = ref_ctx
    rows = [(model.blocks[focus], "focus")]
    for direction, found in (("back", model.bfs(focus, "back", hops)),
                             ("forward", model.bfs(focus, "forward", hops))):
        for n in sorted((n for n in found if not isinstance(n, tuple)),
                        key=lambda n: (found[n][0], _node_sort(model, n))):
            if role_ok(model.blocks[n], roles):
                rows.append((model.blocks[n], f"hop={found[n][0]} {direction}"))
    return rows


# ---- entry point ------------------------------------------------------------------

class Unresolved(Exception):
    """A --ref argument that does not resolve (exit 2, spec §9.9.5)."""


def run_view(model: Model, tree_arg: str, *, full: bool = False, grep: str | None = None,
             ignore_case: bool = False, ref: str | None = None, hops: int = 1,
             flat: bool = False, roles: tuple[str, ...] = (), as_json: bool = False) -> str:
    roles = tuple(dict.fromkeys(roles))
    args: dict = {}
    if full:
        mode = "full"
    elif grep is not None:
        mode, args = "grep", {"regex": grep, "ignore_case": ignore_case}
    elif ref is not None:
        mode, args = "ref", {"ref": ref, "hops": hops}
    else:
        mode = "overview"
    if roles:
        args["roles"] = list(roles)
    if flat:
        args["flat"] = True

    ref_ctx = None
    if mode == "overview":
        data = view_overview(model, tree_arg, roles)
        text = text_overview(model, tree_arg, data)
    elif mode == "full":
        text, data = view_full(model, tree_arg, roles)
    elif mode == "grep":
        text, data = view_grep(model, tree_arg, grep, ignore_case, roles)
    else:
        res = model.resolve_arg(ref)
        if res is None:
            raise Unresolved(ref)
        tid, sub = res
        focus = model.by_id[tid]
        ref_ctx = (focus, hops)
        text, data = view_ref(model, tree_arg, focus, sub, hops, roles)

    if flat:
        rows = flat_rows(model, mode, roles, grep_json=data if mode == "grep" else None,
                         ref_ctx=ref_ctx)
        if as_json:
            out = {"view": mode, "tree": tree_arg, "tree_sha": model.tree_sha, "args": args,
                   "blocks": [dict(block_meta(b), **({"note": e} if e else {}))
                              for b, e in rows]}
            return json.dumps(out, indent=2, ensure_ascii=False)
        header = view_header(f"{mode} --flat", tree_arg, model.tree_sha)
        return "\n".join([header] + [flat_line(b, e) for b, e in rows])
    if as_json:
        out = {"view": mode, "tree": tree_arg, "tree_sha": model.tree_sha, "args": args}
        out.update(data)
        return json.dumps(out, indent=2, ensure_ascii=False)
    return "\n".join(text)
