"""Deterministic flattener: a conformant `game-design.md` tree → a single prose document.

This is **Layer 1** of the §B-construction contract in the Phase 5 pre-registration
(commit `27a4381`). The flattener produces the "B-condition" input that pairs with
the same tree's "A-condition" (the full tree itself) for the help-benchmark's
A-vs-B headline comparison.

**Fairness intent (pinned by pre-reg, audited by Layer 3).** The output MUST read
as a coherent prose brief — facts grouped by topic, sentences flowing naturally,
no token dumps in arbitrary order, no structural-syntax remnants. Concretely:
"what a competent person who knew the game and wrote a 5-page prose summary for
an implementer would produce." See `benchmark/tools/fairness_audit_prompt.md`
for the rubric used by the Layer-3 auxiliary-LLM judge to score this.

**Contract (verifier-checked).** Layer 2 (`verifier.py`) asserts:
  1. Every distinct numeric value in A's frontmatter appears at least once
     in B's prose, as a digit-for-digit literal.
  2. Every distinct `{namespace.id}` reference in A resolves and its
     resolved value appears in B.
  3. Every `rules.<id>.do[]` step appears in B as recognizable prose
     (verb name or structured-action expansion).
  4. Every distribution `type` appears in B by name.
  5. Every `balance_targets.<id>.target` value appears in B with its measure.
  6. Every state-machine transition (from/to/event triple) appears in B as a
     prose statement.

The flattener's job is to make these completeness checks pass *while also*
producing readable prose. It does NOT optimize for token efficiency, brevity,
or any other property — only completeness + readability.

**Determinism guarantee.** Run twice on the same input → byte-identical output.
No timestamps, no random salt, no path-order surprises. Uses sorted dict
iteration where ordering is not declaration-meaningful; uses declaration order
for namespaces that depend on it (e.g., `weighted.options` per D-017).

**Drop list** (these are spec-mechanical and don't carry game-design information):
  - `files:` map (the tree's navigation index — not needed in flat form)
  - `file_type:` discriminators (the flat form has no file boundaries)
  - `last_verified:` dates (drift-detection mechanism, not design content)
  - `status:` lifecycle markers (design-stage markers, not design content)
  - `implemented_in:` glob arrays (anti-drift pointers to code, not design content)
  - `spec:` and `spec_version:` (format markers)
  - Canonical section headers like `## Tokens` / `## Rationale` / `## Open Questions`
    (file-structure markers; their content is kept, the header isn't)
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path
from typing import Any

# Add the project root to path so we can import the gdmd loader
HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from game_design_md.tree import Tree, ParsedFile  # noqa: E402

# Subfile topic ordering: the order in which topics appear in the flattened output.
# Chosen to match the "reading order" the agent would follow into a fresh tree:
# pillars first, then loops (what does the game DO), then mechanics (what are the
# pieces), then systems/distributions/balance/feel/invariants as support.
TOPIC_ORDER = [
    "pillars",
    "loops",
    "entities",
    "verbs",
    "resources",
    "states",
    "events",
    "rules",
    "distributions",
    "balance_targets",
    "feel",
    "invariants",
]

# Frontmatter keys to drop (spec-mechanical, not design content)
DROP_KEYS = {
    "spec",
    "spec_version",
    "file_type",
    "status",
    "version",
    "last_updated",
    "last_verified",
    "implemented_in",
    "implementation_pointers",
    "files",
    "data_dir",  # path internal to the tree
    "count_target",  # implementation metadata
}

# Canonical section headers whose header is dropped but whose content is kept
DROP_HEADERS = {"## Tokens", "## Rationale", "## Open Questions", "## Change Log"}


def flatten_tree(tree_root: Path) -> str:
    """Walk a conformant `game-design.md` tree, return the flattened prose document.

    Determinism: byte-identical output on identical input.
    """
    tree = Tree.load(tree_root)
    parts: list[str] = []

    # --- 1. Game header ------------------------------------------------------
    parts.append(_render_game_header(tree))

    # --- 2. Topic-grouped frontmatter prose ----------------------------------
    for topic in TOPIC_ORDER:
        topic_tokens = tree.top_level_tokens(topic)
        if not topic_tokens:
            continue
        parts.append(_render_topic_section(tree, topic, topic_tokens))

    # --- 3. Content schemas + entities ---------------------------------------
    parts.append(_render_content(tree))

    # --- 4. Per-file rationale prose (verbatim, with headers normalized) ----
    parts.append(_render_rationale(tree))

    # Single trailing newline; concat with double-newline separators
    body = "\n\n".join(p for p in parts if p.strip())
    return body.rstrip() + "\n"


# ---------------------------------------------------------------------------
# Game header
# ---------------------------------------------------------------------------

def _render_game_header(tree: Tree) -> str:
    """Emit the game's headline prose: name, pitch, pillars, non-goals, etc."""
    if tree.core is None:
        return ""
    fm = tree.core.frontmatter
    out: list[str] = []

    name = fm.get("name", "(unnamed game)")
    pitch = fm.get("short_pitch", "")
    out.append(f"# {name}")
    if pitch:
        out.append(f"> {pitch}")

    genre = fm.get("genre_tags", [])
    if genre:
        out.append(f"This game is a {', '.join(genre)} project.")

    platforms = fm.get("target_platforms_neutral", [])
    if platforms:
        out.append(f"Target platforms (engine-neutral): {', '.join(platforms)}.")

    pillars = fm.get("pillars", [])
    if pillars:
        bullets = "\n".join(f"- {p}" for p in pillars)
        out.append(f"The game's pillars are:\n{bullets}")

    non_goals = fm.get("non_goals", [])
    if non_goals:
        bullets = "\n".join(f"- {p}" for p in non_goals)
        out.append(f"The game explicitly does NOT do these things:\n{bullets}")

    peg = fm.get("player_experience_goals", {})
    if peg:
        lines: list[str] = []
        primary = peg.get("primary", [])
        if primary:
            lines.append(f"Primary aesthetics (MDA): {', '.join(primary)}.")
        secondary = peg.get("secondary", [])
        if secondary:
            lines.append(f"Secondary aesthetics: {', '.join(secondary)}.")
        non_aesthetic = peg.get("explicit_non_goals", [])
        if non_aesthetic:
            lines.append(f"Explicitly non-goal aesthetics: {', '.join(non_aesthetic)}.")
        if lines:
            out.append(" ".join(lines))

    core_loop = fm.get("core_loop_ref", "")
    if core_loop:
        resolved = _resolve_ref(tree, core_loop)
        if resolved is not None:
            out.append(f"The core gameplay loop is {core_loop[1:-1]}, described below.")

    return "\n\n".join(out)


# ---------------------------------------------------------------------------
# Topic sections (frontmatter prose grouped by topic)
# ---------------------------------------------------------------------------

def _render_topic_section(
    tree: Tree, topic: str, tokens: dict[str, tuple[ParsedFile, Any]]
) -> str:
    """Render every token in this topic as prose, in topic-sorted order."""
    out = [f"## {_topic_title(topic)}"]
    # Sort by token id for deterministic output, EXCEPT where order is
    # semantically meaningful (none of the namespace TOPIC_ORDER topics
    # currently carry order-dependent semantics at the topic-level).
    for token_id in sorted(tokens.keys()):
        _file, value = tokens[token_id]
        bare_id = token_id.split(".", 1)[1] if "." in token_id else token_id
        out.append(_render_token(tree, topic, bare_id, value))
    return "\n\n".join(out)


def _topic_title(topic: str) -> str:
    titles = {
        "pillars": "Pillars",
        "loops": "Loops",
        "entities": "Entities",
        "verbs": "Verbs (actions)",
        "resources": "Resources",
        "states": "State machines",
        "events": "Events",
        "rules": "Rules",
        "distributions": "Distributions (named randomness)",
        "balance_targets": "Balance targets",
        "feel": "Game feel",
        "invariants": "Architecture invariants",
    }
    return titles.get(topic, topic.replace("_", " ").title())


def _render_token(tree: Tree, topic: str, bare_id: str, value: Any) -> str:
    """Render one token as a prose paragraph."""
    if topic == "pillars":
        return f"Pillar: {value}"
    if topic == "loops":
        return _render_loop(tree, bare_id, value)
    if topic == "entities":
        return _render_entity(tree, bare_id, value)
    if topic == "verbs":
        return _render_verb(tree, bare_id, value)
    if topic == "resources":
        return _render_resource(tree, bare_id, value)
    if topic == "states":
        return _render_state(tree, bare_id, value)
    if topic == "events":
        return _render_event(tree, bare_id, value)
    if topic == "rules":
        return _render_rule(tree, bare_id, value)
    if topic == "distributions":
        return _render_distribution(tree, bare_id, value)
    if topic == "balance_targets":
        return _render_balance_target(tree, bare_id, value)
    if topic == "feel":
        return _render_feel(tree, bare_id, value)
    if topic == "invariants":
        return _render_invariant(tree, bare_id, value)
    # Fallback: just dump as prose
    return f"{bare_id}: {_yaml_to_prose(value)}"


def _render_loop(tree: Tree, lid: str, v: dict) -> str:
    parts = [f"**Loop `{lid}`** is a {v.get('timescale', '?')}-timescale loop"]
    if "duration" in v:
        parts.append(f"with duration {v['duration']}")
    parts.append(".")
    text = " ".join(parts)
    if "sequence" in v and v["sequence"]:
        text += " Its sequence is: "
        steps = []
        for step in v["sequence"]:
            if isinstance(step, dict):
                for k, ref in step.items():
                    resolved_name = _resolve_ref_name(tree, ref) if isinstance(ref, str) else str(ref)
                    steps.append(f"{k} {resolved_name}")
            else:
                steps.append(str(step))
        text += "; ".join(steps) + "."
    if "intended_dynamics" in v:
        text += " Intended dynamics: " + "; ".join(v["intended_dynamics"]) + "."
    if "intended_aesthetics" in v:
        text += " Intended aesthetics: " + ", ".join(v["intended_aesthetics"]) + "."
    if "feel_priority" in v:
        text += f" Feel priority: {v['feel_priority']}."
    if "balance_targets" in v:
        names = [_ref_to_path(r) for r in v["balance_targets"]]
        text += " Balance-tracked via: " + ", ".join(names) + "."
    return text


def _render_entity(tree: Tree, eid: str, v: dict) -> str:
    kind = v.get("type", "?")
    text = f"**Entity `{eid}`** is of type {kind}."
    if "properties" in v:
        text += " Properties: " + _props_to_prose(tree, v["properties"]) + "."
    if kind == "content_collection":
        if "data_source" in v:
            text += f" The collection's data is loaded from `{v['data_source']}`."
        if "count_target" in v:
            text += f" The collection ships approximately {v['count_target']} entries."
    return text


def _render_verb(tree: Tree, vid: str, v: dict) -> str:
    actor_ref = v.get("actor", "?")
    actor_name = _resolve_ref_name(tree, actor_ref) if isinstance(actor_ref, str) else str(actor_ref)
    text = f"**Action `{vid}`** is performed by {actor_name}."
    if "cost" in v:
        text += " Cost: " + _yaml_to_prose(v["cost"]) + "."
    if "target_schema" in v:
        text += " Targets: " + _target_schema_to_prose(tree, v["target_schema"]) + "."
    if "effects" in v:
        eff_parts: list[str] = []
        for eff in v["effects"]:
            if isinstance(eff, dict):
                for k, ref in eff.items():
                    if isinstance(ref, str) and ref.startswith("{"):
                        eff_parts.append(f"{k} {ref[1:-1]}")
                    else:
                        eff_parts.append(f"{k}={ref}")
            else:
                eff_parts.append(str(eff))
        text += " Effects: " + "; ".join(eff_parts) + "."
    if "feel" in v:
        text += f" Feel reference: {_ref_to_path(v['feel'])}."
    return text


def _render_resource(tree: Tree, rid: str, v: dict) -> str:
    text = f"**Resource `{rid}`** is scoped {v.get('scope', '?')}"
    if "min" in v and "max" in v:
        text += f", ranging from {v['min']} to {v['max']}"
    text += f". Visibility: {v.get('visibility', '?')}."
    if "velocity_target" in v:
        text += f" Velocity target: {_ref_to_path(v['velocity_target'])}."
    return text


def _render_state(tree: Tree, sid: str, v: dict) -> str:
    text = f"**State machine `{sid}`** has initial node `{v.get('initial', '?')}`."
    nodes = v.get("nodes", [])
    if nodes:
        node_descs = []
        for n in nodes:
            if isinstance(n, dict):
                nid = n.get("id", "?")
                term = " (terminal)" if n.get("terminal") else ""
                node_descs.append(f"`{nid}`{term}")
            else:
                node_descs.append(str(n))
        text += " Nodes: " + ", ".join(node_descs) + "."
    transitions = v.get("transitions", [])
    if transitions:
        text += " Transitions:"
        for t in transitions:
            if isinstance(t, dict):
                ev = t.get("event", "?")
                ev_name = _resolve_ref_name(tree, ev) if isinstance(ev, str) else str(ev)
                text += f" from `{t.get('from')}` on event `{ev_name}` go to `{t.get('to')}`;"
        text = text.rstrip(";") + "."
    return text


def _render_event(tree: Tree, eid: str, v: dict) -> str:
    text = f"**Event `{eid}`**."
    if "description" in v:
        text += f" {v['description']}"
    return text


def _render_rule(tree: Tree, rid: str, v: dict) -> str:
    text = f"**Rule `{rid}`**."
    given = v.get("given", {})
    if given.get("verb"):
        text += f" Triggered by action {_ref_to_path(given['verb'])}."
    if given.get("state"):
        text += f" In state {_ref_to_path(given['state'])}."
    if v.get("target_selection"):
        text += f" Target selection: {v['target_selection']}."
    do_steps = v.get("do", [])
    if do_steps:
        text += " Steps:"
        for i, step in enumerate(do_steps, 1):
            if isinstance(step, dict):
                kind = step.get("kind", "?")
                # Serialize remaining keys as inline params
                params = {k: w for k, w in step.items() if k != "kind"}
                if params:
                    text += f" ({i}) `{kind}` with " + _params_to_prose(tree, params) + ";"
                else:
                    text += f" ({i}) `{kind}`;"
            else:
                text += f" ({i}) {step};"
        text = text.rstrip(";") + "."
    outputs = v.get("outputs", [])
    if outputs:
        text += " Outputs: " + ", ".join(str(o) for o in outputs) + "."
    return text


def _render_distribution(tree: Tree, did: str, v: dict) -> str:
    dtype = v.get("type", "?")
    text = f"**Distribution `{did}`** is of type `{dtype}`."
    if dtype == "uniform" and "range" in v:
        text += f" Range: {v['range']}."
        if "threshold" in v:
            text += f" Threshold: {v['threshold']}."
        if "selection_rule" in v:
            text += f" Selection rule: {v['selection_rule']}."
    if dtype == "weighted" and "options" in v:
        text += " Options (in declaration order): "
        opt_descs = []
        for k, opt in v["options"].items():
            if isinstance(opt, dict):
                w = opt.get("weight", "?")
                val = opt.get("value", "")
                opt_descs.append(f"`{k}` weight {w}" + (f" value {val}" if val != "" else ""))
            else:
                opt_descs.append(f"`{k}` weight {opt}")
        text += "; ".join(opt_descs) + "."
        if "selection_rule" in v:
            text += f" Selection rule: {v['selection_rule']}."
    if dtype == "shuffle_bag" and "of" in v:
        text += f" Of: {_ref_to_path(v['of'])}. Refill: {v.get('refill_when', '?')}."
    if dtype == "gaussian":
        if "mean" in v:
            text += f" Mean: {v['mean']}."
        if "stddev" in v:
            text += f" Standard deviation: {v['stddev']}."
        if "clamp" in v:
            text += f" Clamp: {v['clamp']}."
    if dtype == "pity_floor":
        if "table" in v:
            text += f" Table: {v['table']}."
        if "weights" in v:
            text += f" Weights: {v['weights']}."
        if "pity" in v:
            text += f" Pity rules: {v['pity']}."
    if dtype == "deterministic" and "sequence" in v:
        text += f" Sequence: {v['sequence']}."
    if dtype == "ordering_rule":
        if "over" in v:
            text += f" Over: {_ref_to_path(v['over'])}."
        if "sort" in v:
            text += f" Sort: {v['sort']}."
        if "filter" in v:
            text += f" Filter: {v['filter']}."
    if dtype == "discrete_sum":
        if "samples" in v:
            text += f" Samples: {v['samples']}."
        if "range" in v:
            text += f" Per-draw range: {v['range']}."
        if "mean" in v:
            text += f" Mean offset: {v['mean']}."
        if "clamp" in v:
            text += f" Clamp: {v['clamp']}."
    if "params_from" in v:
        text += " Templated parameters: " + ", ".join(
            f"{k}={ref}" for k, ref in v["params_from"].items()
        ) + "."
    if "seed" in v:
        text += f" Seed mode: {v['seed']}."
    return text


def _render_balance_target(tree: Tree, bid: str, v: dict) -> str:
    kind = v.get("target_kind", "?")
    text = f"**Balance target `{bid}`** is of kind `{kind}`."
    if "target" in v:
        text += f" Target value: {v['target']}."
    if "tolerance" in v:
        text += f" Tolerance: {v['tolerance']}."
    if "measure" in v:
        text += f" Measure: {v['measure']}."
    return text


def _render_feel(tree: Tree, fid: str, v: dict) -> str:
    text = f"**Game feel for action `{fid}`** (Swink six-dimension):"
    for dim in ["input", "response", "context", "polish", "metaphor", "rules"]:
        if dim in v and v[dim]:
            text += f" *{dim}*: {v[dim]}."
    return text


def _render_invariant(tree: Tree, iid: str, v: dict) -> str:
    kind = v.get("kind", "?")
    enforcement = v.get("enforcement", "?")
    severity = v.get("severity", "?")
    rule = v.get("rule", "")
    text = f"**Invariant `{iid}`** ({kind}, enforcement={enforcement}, severity={severity}): {rule}"
    return text


# ---------------------------------------------------------------------------
# Content (schemas + entities)
# ---------------------------------------------------------------------------

def _render_content(tree: Tree) -> str:
    """Emit each content-schema's schema + every entity in its collection."""
    out: list[str] = []
    # Find content-schema files
    schemas = [f for f in tree.files if f.file_type == "content-schema"]
    if not schemas:
        return ""
    for schema_file in sorted(schemas, key=lambda f: f.rel_str):
        out.append(_render_content_schema(tree, schema_file))
    return "\n\n".join(out)


def _render_content_schema(tree: Tree, schema_file: ParsedFile) -> str:
    fm = schema_file.frontmatter
    entity = fm.get("entity", "?")
    schema = fm.get("schema", {})
    count = fm.get("count_target", "?")
    out = [f"## Content collection: {entity} (~{count} entries)"]
    out.append(f"Schema definition (every entry in `{entity}` must conform):")
    if "required" in schema:
        out.append(f"Required fields: {', '.join(schema['required'])}.")
    if "properties" in schema:
        prop_lines = []
        for prop_name, prop_spec in schema["properties"].items():
            prop_lines.append(f"- `{prop_name}`: {_yaml_to_prose(prop_spec)}")
        out.append("Properties:\n" + "\n".join(prop_lines))
    if "balance_refs" in fm:
        out.append(f"Balance references: {', '.join(_ref_to_path(r) for r in fm['balance_refs'])}.")

    # Emit each entity in this collection
    entities = tree.content_entities.get(entity, [])
    if entities:
        out.append(f"\nThe `{entity}` collection contains the following entries:")
        for ent_file in sorted(entities, key=lambda f: f.rel_str):
            out.append(_render_content_entity(tree, ent_file))
    return "\n\n".join(out)


def _render_content_entity(tree: Tree, ent_file: ParsedFile) -> str:
    fm = ent_file.frontmatter
    eid = fm.get("id", "?")
    out = [f"### Entry `{eid}`"]
    for key, value in fm.items():
        if key in DROP_KEYS or key == "id":
            continue
        out.append(f"- {key}: {_yaml_to_prose(value)}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Per-file rationale prose (verbatim, with headers normalized)
# ---------------------------------------------------------------------------

def _render_rationale(tree: Tree) -> str:
    """Emit each subfile's prose body verbatim, in canonical file order."""
    # Order files by core → subfile (topic order) → content-schema
    out: list[str] = ["## Design rationale (per-section prose from the original tree)"]
    # Subfiles in topic order
    subfiles = [f for f in tree.files if f.file_type == "subfile"]
    # Sort subfiles by topic-of-primary-namespace; fallback to path order
    subfiles_sorted = sorted(subfiles, key=lambda f: (_subfile_topic_order(f), f.rel_str))
    for f in subfiles_sorted:
        if f.body.strip():
            out.append(f"### Rationale from `{f.rel_str}`")
            out.append(_strip_dropped_headers(f.body))
    # Content-schema bodies (the schema files themselves have prose)
    cs = [f for f in tree.files if f.file_type == "content-schema"]
    for f in sorted(cs, key=lambda f: f.rel_str):
        if f.body.strip():
            out.append(f"### Rationale from `{f.rel_str}`")
            out.append(_strip_dropped_headers(f.body))
    # Core file body
    if tree.core and tree.core.body.strip():
        out.append(f"### Rationale from `{tree.core.rel_str}`")
        out.append(_strip_dropped_headers(tree.core.body))
    return "\n\n".join(out)


def _subfile_topic_order(f: ParsedFile) -> int:
    """Heuristic: order subfiles by the topic of their primary namespace."""
    for i, topic in enumerate(TOPIC_ORDER):
        if topic in f.frontmatter:
            return i
    return len(TOPIC_ORDER)


def _strip_dropped_headers(body: str) -> str:
    """Remove canonical structural headers (`## Tokens`, etc.) from a prose body."""
    out_lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped in DROP_HEADERS:
            continue
        out_lines.append(line)
    return "\n".join(out_lines).strip()


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _ref_to_path(ref: Any) -> str:
    """Strip {ns.id} → ns.id; leave non-ref values untouched."""
    if isinstance(ref, str) and ref.startswith("{") and ref.endswith("}"):
        return ref[1:-1]
    return str(ref)


def _resolve_ref(tree: Tree, ref: str) -> Any | None:
    """Resolve a `{ns.id...}` reference to its frontmatter value, or None."""
    if not (isinstance(ref, str) and ref.startswith("{") and ref.endswith("}")):
        return None
    path = ref[1:-1].split(".")
    if len(path) < 2:
        return None
    ns, top_id = path[0], path[1]
    tokens = tree.top_level_tokens(ns)
    full_id = f"{ns}.{top_id}"
    if full_id not in tokens:
        return None
    _file, value = tokens[full_id]
    for seg in path[2:]:
        if not isinstance(value, dict):
            return None
        if seg not in value:
            return None
        value = value[seg]
    return value


def _resolve_ref_name(tree: Tree, ref: str) -> str:
    """Resolve a ref to a name (the resolved value if scalar, else the path)."""
    resolved = _resolve_ref(tree, ref)
    if resolved is None:
        return _ref_to_path(ref)
    if isinstance(resolved, (str, int, float, bool)):
        return str(resolved)
    return _ref_to_path(ref)


def _yaml_to_prose(value: Any) -> str:
    """Convert a YAML value to a prose-readable form."""
    if isinstance(value, dict):
        parts = []
        for k, w in value.items():
            parts.append(f"{k}={_yaml_to_prose(w)}")
        return "{" + ", ".join(parts) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_yaml_to_prose(v) for v in value) + "]"
    if isinstance(value, str):
        if value.startswith("{") and value.endswith("}"):
            return value[1:-1]  # strip ref braces
        return value
    return json.dumps(value)


def _props_to_prose(tree: Tree, props: dict) -> str:
    """Render an entity properties dict as prose."""
    parts = []
    for k, v in props.items():
        if isinstance(v, dict) and "from" in v:
            parts.append(f"`{k}` (from {_ref_to_path(v['from'])})")
        else:
            parts.append(f"`{k}`={_yaml_to_prose(v)}")
    return ", ".join(parts)


def _target_schema_to_prose(tree: Tree, schema: dict) -> str:
    """Render a verb's target_schema as prose."""
    parts = []
    for k, v in schema.items():
        if isinstance(v, str):
            parts.append(f"{k}={_resolve_ref_name(tree, v)}")
        else:
            parts.append(f"{k}={_yaml_to_prose(v)}")
    return ", ".join(parts)


def _params_to_prose(tree: Tree, params: dict) -> str:
    """Render rule-step parameters as prose."""
    parts = []
    for k, v in params.items():
        if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
            parts.append(f"{k}={v[1:-1]}")
        else:
            parts.append(f"{k}={_yaml_to_prose(v)}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tree_root", type=Path, help="Path to a game-design.md tree root")
    parser.add_argument("-o", "--output", type=Path, help="Output file (default: stdout)")
    args = parser.parse_args(argv)
    flat = flatten_tree(args.tree_root)
    if args.output:
        args.output.write_text(flat)
    else:
        sys.stdout.write(flat)
    return 0


if __name__ == "__main__":
    sys.exit(main())
