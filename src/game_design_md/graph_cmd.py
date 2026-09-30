"""`gdmd graph`: the reference graph of a compiled tree (spec §9.9.4, D-027).

The graph is the one `gdmd view` uses (`ir.Model.targets` / `referrers`),
rendered as structure. Nodes are blocks: every `token`, `invariant` and
`content-entity` block, plus the `rationale`, `meta` and `impl` blocks that
contain references. A reference on a gap line has no block; it appears as a
`gap` leaf. Edges run from the block containing a reference to its target
(the longest-prefix token); several references between the same two nodes
form one edge carrying every location.
"""
from __future__ import annotations

import json

from .ir import Model, Occurrence

Node = int | tuple   # block index, or ("gap", path, line)


def node_primary(model: Model, n: Node) -> str:
    return f"{n[1]}:{n[2]}" if isinstance(n, tuple) else model.blocks[n].primary


def node_secondary(model: Model, n: Node) -> str:
    return f"{n[1]}:{n[2]}-{n[2]}" if isinstance(n, tuple) else model.blocks[n].secondary


def node_header(model: Model, n: Node) -> str:
    return f"[gap] {node_secondary(model, n)}" if isinstance(n, tuple) \
        else model.blocks[n].header()


def node_json(model: Model, n: Node) -> dict:
    if isinstance(n, tuple):
        return {"role": "gap", "id": None, "pointer": node_secondary(model, n)}
    b = model.blocks[n]
    return {"role": b.role, "id": b.primary, "pointer": b.secondary, "status": b.status}


def node_key(model: Model, n: Node) -> tuple[str, str]:
    """Deterministic order: by primary coordinate, then pointer."""
    return (node_primary(model, n), node_secondary(model, n))


def occ_loc(o: Occurrence) -> dict:
    d = {"pointer": o.pointer, "ref": "{" + o.ref + "}", "kind": o.kind,
         "outcome": o.outcome}
    if o.field is not None:
        d["field"] = o.field
    return d


def build(model: Model) -> tuple[list[Node], dict[tuple[Node, int], list[Occurrence]]]:
    """All nodes (canonical order) and edges {(source, target): occurrences}."""
    edges: dict[tuple[Node, int], list[Occurrence]] = {}
    sources: set[Node] = set()
    for o in model.occurrences:
        t = model.by_id.get(o.target) if o.target else None
        if t is None:
            continue
        src: Node = o.source if o.source is not None else ("gap", o.path, o.line)
        sources.add(src)
        edges.setdefault((src, t), []).append(o)
    nodes: list[Node] = [b.index for b in model.blocks
                         if b.has_identity or b.index in sources]
    nodes += sorted((s for s in sources if isinstance(s, tuple)),
                    key=lambda s: (s[1], s[2]))
    return nodes, edges


def edge_json(model: Model, src: Node, dst: int, occs: list[Occurrence]) -> dict:
    return {"from": node_primary(model, src), "from_pointer": node_secondary(model, src),
            "to": node_primary(model, dst), "to_pointer": node_secondary(model, dst),
            "kinds": sorted({o.kind for o in occs}),
            "locations": [occ_loc(o) for o in sorted(occs, key=lambda o: (o.path, o.line))]}


def edge_text(model: Model, src: Node, dst: int, occs: list[Occurrence]) -> list[str]:
    kinds = ",".join(sorted({o.kind for o in occs}))
    out = [f"  {node_primary(model, src)} -> {node_primary(model, dst)} ({kinds})"]
    for o in sorted(occs, key=lambda o: (o.path, o.line)):
        where = o.field if o.field is not None else "body"
        out.append(f"    {o.pointer} {o.kind} {where}")
    return out


def dot(model: Model, nodes: list[Node], edges: dict) -> str:
    def q(s: str) -> str:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    lines = ["digraph gdmd {", f"  // tree_sha {model.tree_sha}"]
    for n in nodes:
        role = "gap" if isinstance(n, tuple) else model.blocks[n].role
        lines.append(f"  {q(node_secondary(model, n))} "
                     f"[label={q(node_primary(model, n))}, role={q(role)}];")
    for (src, dst), occs in edges.items():
        kinds = ",".join(sorted({o.kind for o in occs}))
        lines.append(f"  {q(node_secondary(model, src))} -> {q(node_secondary(model, dst))} "
                     f"[label={q(kinds)}];")
    lines.append("}")
    return "\n".join(lines)


# ---- modes -----------------------------------------------------------------------

def impact(model: Model, focus: int) -> list[tuple[Node, int, list[Occurrence]]]:
    """Transitive reverse closure: (node, hop, occurrences that reached it)."""
    found = model.bfs(focus, "back", None)
    return sorted(((n, h, occs) for n, (h, occs) in found.items()),
                  key=lambda x: (x[1], node_key(model, x[0])))


def shortest_paths(model: Model, a: int, b: int, max_paths: int
                   ) -> tuple[list[list[int]], int]:
    """Up to `max_paths` shortest forward paths a → b, in lexicographic order
    of node primary coordinates, and the total number of shortest paths."""
    if a == b:
        return [[a]], 1
    dist = {a: 0}
    frontier = [a]
    while frontier and b not in dist:
        nxt = []
        for u in frontier:
            for v in model.targets(u):
                if v not in dist:
                    dist[v] = dist[u] + 1
                    nxt.append(v)
        frontier = nxt
    if b not in dist:
        return [], 0
    total_len = dist[b]
    # nodes on some shortest path: reachable to b within the remaining budget
    memo: dict[int, int] = {b: 1}

    def count(u: int) -> int:
        if u in memo:
            return memo[u]
        c = 0
        if dist.get(u, total_len + 1) < total_len:
            for v in model.targets(u):
                if dist.get(v) == dist[u] + 1:
                    c += count(v)
        memo[u] = c
        return c

    total = count(a)
    paths: list[list[int]] = []

    def walk(u: int, acc: list[int]) -> None:
        if len(paths) >= max_paths:
            return
        if u == b:
            paths.append(acc)
            return
        succ = [v for v in model.targets(u) if dist.get(v) == dist[u] + 1 and count(v) > 0]
        for v in sorted(succ, key=lambda v: node_key(model, v)):
            walk(v, acc + [v])

    walk(a, [a])
    return paths, total


def cycles(model: Model, nodes: list[Node], edges: dict) -> list[list[Node]]:
    """Strongly connected components of more than one node, plus
    self-referencing nodes, over `value` edges (Tarjan, iterative)."""
    adj: dict[Node, list[Node]] = {n: [] for n in nodes}
    self_loops = set()
    for (src, dst), occs in edges.items():
        if not any(o.kind == "value" for o in occs):
            continue
        if src == dst:
            self_loops.add(src)
        else:
            adj.setdefault(src, []).append(dst)
    for n in adj:
        adj[n].sort(key=lambda v: node_key(model, v))
    index: dict[Node, int] = {}
    low: dict[Node, int] = {}
    on_stack: set[Node] = set()
    stack: list[Node] = []
    out: list[list[Node]] = []
    counter = 0
    for root in sorted(adj, key=lambda v: node_key(model, v)):
        if root in index:
            continue
        work = [(root, 0)]
        while work:
            v, i = work.pop()
            if i == 0:
                index[v] = low[v] = counter
                counter += 1
                stack.append(v)
                on_stack.add(v)
            recurse = False
            nbrs = adj.get(v, [])
            while i < len(nbrs):
                w = nbrs[i]
                i += 1
                if w not in index:
                    work.append((v, i))
                    work.append((w, 0))
                    recurse = True
                    break
                if w in on_stack:
                    low[v] = min(low[v], index[w])
            if recurse:
                continue
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1 or v in self_loops:
                    out.append(sorted(comp, key=lambda n: node_key(model, n)))
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[v])
    return sorted(out, key=lambda c: node_key(model, c[0]))


class Unresolved(Exception):
    """An --impact / --from / --to argument that does not resolve (exit 2)."""


def _resolve(model: Model, arg: str) -> int:
    res = model.resolve_arg(arg)
    if res is None:
        raise Unresolved(arg)
    return model.by_id[res[0]]


def run_graph(model: Model, tree_arg: str, *, impact_arg: str | None = None,
              from_arg: str | None = None, to_arg: str | None = None,
              max_paths: int = 20, want_cycles: bool = False, fmt: str = "text") -> str:
    nodes, edges = build(model)
    head = {"tree": tree_arg, "tree_sha": model.tree_sha}

    if impact_arg is not None:
        focus = _resolve(model, impact_arg)
        rows = impact(model, focus)
        if fmt == "json":
            return json.dumps({"graph": "impact", **head, "args": {"impact": impact_arg},
                               "focus": node_json(model, focus),
                               "impact": [dict(node_json(model, n), hop=h,
                                               kinds=sorted({o.kind for o in occs}),
                                               via=[occ_loc(o) for o in occs])
                                          for n, h, occs in rows]},
                              indent=2, ensure_ascii=False)
        if fmt == "dot":
            keep = {focus} | {n for n, _, _ in rows}
            return dot(model, [n for n in nodes if n in keep],
                       {k: v for k, v in edges.items() if k[0] in keep and k[1] in keep})
        out = [f"[graph impact] {tree_arg} tree_sha={model.tree_sha}",
               node_header(model, focus), f"impact ({len(rows)}):"]
        for n, h, occs in rows:
            kinds = ",".join(sorted({o.kind for o in occs}))
            out.append(f"  hop {h} {node_header(model, n)} ({kinds})")
        return "\n".join(out)

    if from_arg is not None:
        a, b = _resolve(model, from_arg), _resolve(model, to_arg)
        paths, total = shortest_paths(model, a, b, max_paths)

        def steps(p: list[int]) -> list[dict]:
            return [{"from": node_primary(model, u), "to": node_primary(model, v),
                     "locations": [occ_loc(o) for o in edges[(u, v)]]}
                    for u, v in zip(p, p[1:])]

        if fmt == "json":
            return json.dumps({"graph": "paths", **head,
                               "args": {"from": from_arg, "to": to_arg, "max_paths": max_paths},
                               "total": total, "emitted": len(paths),
                               "paths": [{"nodes": [node_json(model, n) for n in p],
                                          "steps": steps(p)} for p in paths]},
                              indent=2, ensure_ascii=False)
        if fmt == "dot":
            keep = {n for p in paths for n in p}
            pe = {(u, v) for p in paths for u, v in zip(p, p[1:])}
            return dot(model, [n for n in nodes if n in keep],
                       {k: v for k, v in edges.items() if k in pe})
        out = [f"[graph paths] {tree_arg} tree_sha={model.tree_sha}"]
        for i, p in enumerate(paths, 1):
            out.append(f"path {i} ({len(p) - 1} hops): "
                       + " -> ".join(node_primary(model, n) for n in p))
            for u, v in zip(p, p[1:]):
                for o in sorted(edges[(u, v)], key=lambda o: (o.path, o.line)):
                    where = o.field if o.field is not None else "body"
                    out.append(f"  {node_primary(model, u)} -> {node_primary(model, v)} "
                               f"{o.pointer} {o.kind} {where}")
        if total > len(paths):
            out.append(f"… {len(paths)} of {total} shortest paths")
        return "\n".join(out)

    if want_cycles:
        comps = cycles(model, nodes, edges)
        if fmt == "json":
            return json.dumps({"graph": "cycles", **head, "args": {"cycles": True},
                               "cycles": [{"nodes": [node_json(model, n) for n in c],
                                           "edges": [edge_json(model, s, d, o)
                                                     for (s, d), o in edges.items()
                                                     if s in c and d in c]}
                                          for c in comps]},
                              indent=2, ensure_ascii=False)
        if fmt == "dot":
            keep = {n for c in comps for n in c}
            return dot(model, [n for n in nodes if n in keep],
                       {k: v for k, v in edges.items() if k[0] in keep and k[1] in keep
                        and any(o.kind == "value" for o in v)})
        out = [f"[graph cycles] {tree_arg} tree_sha={model.tree_sha}",
               f"cycles ({len(comps)}):"]
        for c in comps:
            out.append("  " + " , ".join(node_primary(model, n) for n in c))
        return "\n".join(out)

    if fmt == "json":
        return json.dumps({"graph": "all", **head, "args": {},
                           "nodes": [node_json(model, n) for n in nodes],
                           "edges": [edge_json(model, s, d, o) for (s, d), o in edges.items()]},
                          indent=2, ensure_ascii=False)
    if fmt == "dot":
        return dot(model, nodes, edges)
    out = [f"[graph all] {tree_arg} tree_sha={model.tree_sha}", f"nodes ({len(nodes)}):"]
    out += ["  " + node_header(model, n) for n in nodes]
    out.append(f"edges ({len(edges)}):")
    for (s, d), occs in edges.items():
        out += edge_text(model, s, d, occs)
    return "\n".join(out)
