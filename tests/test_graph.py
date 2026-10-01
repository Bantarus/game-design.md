"""`gdmd graph` (spec §9.9.4, D-027).

The graph is the one `gdmd view` uses. On all 12 in-repo trees: every
reference with a target is on exactly one edge, and `--impact X` contains
every backlink `view --ref X --hops N` reports, for every token and
N ∈ {1, 2, 3}. Path and cycle cases use a hand-written tree under tmp_path.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from game_design_md.cli import main
from game_design_md.graph_cmd import build, run_graph
from game_design_md.ir import compile_tree
from game_design_md.view_cmd import run_view
from tests.conftest import IN_REPO_TREES, REPO_ROOT

TREES = [REPO_ROOT / t for t in IN_REPO_TREES]


@pytest.fixture(scope="module", params=TREES, ids=list(IN_REPO_TREES))
def model(request):
    return compile_tree(request.param)


def test_every_targeted_reference_is_on_exactly_one_edge(model):
    _, edges = build(model)
    on_edges = [id(o) for occs in edges.values() for o in occs]
    assert len(on_edges) == len(set(on_edges))
    targeted = [o for o in model.occurrences if o.target and o.target in model.by_id]
    assert sorted(on_edges) == sorted(id(o) for o in targeted)
    for (src, dst), occs in edges.items():
        for o in occs:
            assert model.by_id[o.target] == dst
            assert (o.source if o.source is not None else ("gap", o.path, o.line)) == src


def test_impact_contains_every_ref_backlink_at_every_hop_count(model):
    for tid in model.by_id:
        impact = json.loads(run_graph(model, "T", impact_arg="{" + tid + "}", fmt="json"))
        got = {n["pointer"] for n in impact["impact"]}
        hop1 = {n["pointer"] for n in impact["impact"] if n["hop"] == 1}
        direct = {model.blocks[o.source].secondary if o.source is not None
                  else f"{o.path}:{o.line}-{o.line}" for o in model.backlinks(tid)}
        assert hop1 == direct - {model.blocks[model.by_id[tid]].secondary}, tid
        for hops in (1, 2, 3):
            ref = json.loads(run_view(model, "T", ref="{" + tid + "}", hops=hops,
                                      as_json=True))
            back = {n["block"]["pointer"] for n in ref["backlinks"] + ref["neighbors"]
                    if n["direction"] == "back"}
            assert back <= got, (tid, hops, back - got)


# ---- paths and cycles on a hand-written tree -------------------------------------

def _subfile(ns_blocks: str) -> str:
    return ('---\nspec: game-design.md\nspec_version: 0.3.0\nfile_type: subfile\n'
            'status: draft\nlast_verified: "2026-05-21"\n' + ns_blocks + "---\n\n## Rationale\n")


GRAPH_TREE = {
    "game-design.md": ('---\nspec: game-design.md\nspec_version: 0.3.0\nfile_type: core\n'
                       'status: draft\ncore_loop_ref: "{loops.main}"\n---\n\n# G\n'),
    "gdd/loops.md": _subfile(
        "loops:\n"
        "  main:\n"
        '    sequence: ["{verbs.v5}", "{verbs.v3}", "{verbs.v1}", "{verbs.v4}", "{verbs.v2}"]\n'
        "    status: draft\n"
    ),
    "gdd/mechanics.md": _subfile(
        "verbs:\n"
        + "".join(f'  v{i}:\n    cost: {{ resource: "{{resources.mana}}" }}\n' for i in range(1, 6))
        + '  v6:\n    effects: ["{rules.long}"]\n'
        "resources:\n"
        "  mana:\n"
        "    max: 3\n"
        "rules:\n"
        '  long:\n    do: ["{rules.longer}"]\n'
        '  longer:\n    do: ["{resources.mana}"]\n'
        '  ping:\n    do: ["{rules.pong}"]\n'
        '  pong:\n    do: ["{rules.ping}"]\n'
        '  selfish:\n    do: ["{rules.selfish.do}"]\n'
    ).replace("## Rationale\n", "## Rationale\n\n`{rules.pong}` and `{rules.ping}` talk in prose too.\n"),
}


@pytest.fixture
def gtree(tmp_path: Path) -> Path:
    for rel, text in GRAPH_TREE.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return tmp_path


def test_max_paths_emits_the_first_n_shortest_in_lexicographic_order(gtree):
    m = compile_tree(gtree)
    data = json.loads(run_graph(m, "T", from_arg="{loops.main}", to_arg="{resources.mana}",
                                max_paths=3, fmt="json"))
    assert data["total"] == 5 and data["emitted"] == 3
    assert [[n["id"] for n in p["nodes"]] for p in data["paths"]] == [
        ["{loops.main}", f"{{verbs.v{i}}}", "{resources.mana}"] for i in (1, 2, 3)]
    text = run_graph(m, "T", from_arg="{loops.main}", to_arg="{resources.mana}", max_paths=3)
    assert text.split("\n")[-1] == "… 3 of 5 shortest paths"
    everything = json.loads(run_graph(m, "T", from_arg="{loops.main}",
                                      to_arg="{resources.mana}", fmt="json"))
    assert everything["total"] == everything["emitted"] == 5
    # the longer route through v6 -> long -> longer is never a shortest path
    assert all(len(p["nodes"]) == 3 for p in everything["paths"])


def test_no_path_is_empty_output_and_exit_0(gtree):
    r = CliRunner().invoke(main, ["graph", str(gtree), "--from", "{resources.mana}",
                                  "--to", "{loops.main}", "--format", "json"])
    assert r.exit_code == 0
    assert json.loads(r.output)["paths"] == [] and json.loads(r.output)["total"] == 0


def test_cycles_are_value_sccs_plus_self_references(gtree):
    m = compile_tree(gtree)
    data = json.loads(run_graph(m, "T", want_cycles=True, fmt="json"))
    assert [[n["id"] for n in c["nodes"]] for c in data["cycles"]] == [
        ["{rules.ping}", "{rules.pong}"], ["{rules.selfish}"]]


def test_impact_reaches_prose_leaves_and_transitive_referrers(gtree):
    m = compile_tree(gtree)
    data = json.loads(run_graph(m, "T", impact_arg="{rules.longer}", fmt="json"))
    assert [(n["id"], n["hop"]) for n in data["impact"]] == [
        ("{rules.long}", 1), ("{verbs.v6}", 2)]
    ping = json.loads(run_graph(m, "T", impact_arg="{rules.ping}", fmt="json"))
    roles = {(n["role"], n["hop"]) for n in ping["impact"]}
    assert ("rationale", 1) in roles and ("token", 1) in roles


def test_cli_graph_exit_codes_and_formats(gtree):
    r = CliRunner()
    assert r.invoke(main, ["graph", "--help"]).exit_code == 0
    res = r.invoke(main, ["graph", str(gtree), "--impact", "{rules.nope}"])
    assert res.exit_code == 2 and "{rules.nope} does not resolve" in res.output
    assert r.invoke(main, ["graph", str(gtree), "--from", "{loops.main}"]).exit_code == 2
    assert r.invoke(main, ["graph", str(gtree), "--cycles", "--impact",
                           "{rules.ping}"]).exit_code == 2
    dot = r.invoke(main, ["graph", str(gtree), "--format", "dot"])
    assert dot.exit_code == 0 and dot.output.startswith("digraph gdmd {")
    assert "tree_sha" in dot.output
    whole = json.loads(r.invoke(main, ["graph", str(gtree), "--format", "json"]).output)
    assert whole["tree_sha"] == compile_tree(gtree).tree_sha
