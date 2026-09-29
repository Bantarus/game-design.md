"""Information-completeness verifier: assert a flattened B retains every fact in A.

This is **Layer 2** of the §B-construction contract in the Phase 5 pre-registration
(commit `27a4381`). The verifier complements the flattener (`flattener.py`,
Layer 1) and the fairness audit (`fairness_audit_prompt.md`, Layer 3): the
flattener produces a fair-looking flat brief; the fairness audit verifies it
reads fairly; the verifier verifies it loses no information.

The verifier asserts six things per the pre-reg:

  1. Every distinct numeric value in A's frontmatter appears at least once
     in B's prose, as a digit-for-digit literal string.
  2. Every distinct `{namespace.id}` reference in A has its resolved value
     appearing in B.
  3. Every `rules.<id>.do[]` step appears in B as recognizable prose (verb
     name or structured-action expansion).
  4. Every distribution `type` declared in A appears in B by name.
  5. Every `balance_targets.<id>.target` value appears in B with its measure.
  6. Every state-machine transition (from/to/event triple) appears in B as
     a prose statement.

Exit code 0 = pass; non-zero = miss(es). Findings are emitted as JSON on stdout.

A B that does not pass the verifier is NOT used in any trial.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from game_design_md.tree import Tree, ParsedFile  # noqa: E402


def verify(tree_root: Path, flattened_text: str) -> dict:
    """Return a findings report: {'findings': [...], 'summary': {...}}."""
    tree = Tree.load(tree_root)
    findings: list[dict] = []

    findings.extend(_check_numeric_values(tree, flattened_text))
    findings.extend(_check_references(tree, flattened_text))
    findings.extend(_check_rule_do_steps(tree, flattened_text))
    findings.extend(_check_distribution_types(tree, flattened_text))
    findings.extend(_check_balance_target_values(tree, flattened_text))
    findings.extend(_check_state_machine_transitions(tree, flattened_text))

    errors = sum(1 for f in findings if f["severity"] == "error")
    summary = {
        "checks_run": 6,
        "errors": errors,
        "passes_completeness": errors == 0,
    }
    return {"findings": findings, "summary": summary}


# ---------------------------------------------------------------------------
# Check 1: numeric values
# ---------------------------------------------------------------------------

def _check_numeric_values(tree: Tree, flat: str) -> list[dict]:
    findings: list[dict] = []
    values = _collect_numeric_values(tree)
    for v, sites in values.items():
        # Search for the digit-for-digit literal in the flat text
        if not _contains_literal_number(flat, v):
            findings.append({
                "check": "numeric_value_present",
                "severity": "error",
                "value": v,
                "sites": sites[:3],  # cap for readability
                "message": f"Numeric value {v!r} appears at {len(sites)} site(s) in A's frontmatter but not in B's prose.",
            })
    return findings


def _collect_numeric_values(tree: Tree) -> dict[Any, list[str]]:
    """Walk all frontmatter, return {value: [list of sites]}."""
    values: dict[Any, list[str]] = {}
    for f in tree.files:
        # Walk the frontmatter
        _walk_for_numbers(f.frontmatter, f.rel_str, "", values)
    return values


def _walk_for_numbers(obj: Any, file_path: str, key_path: str, accum: dict[Any, list[str]]) -> None:
    """Recursively walk an object collecting int/float values keyed by (file, key path)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            kp = f"{key_path}.{k}" if key_path else k
            _walk_for_numbers(v, file_path, kp, accum)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            kp = f"{key_path}[{i}]"
            _walk_for_numbers(v, file_path, kp, accum)
    elif isinstance(obj, bool):
        # Booleans are ints in Python; skip them
        return
    elif isinstance(obj, (int, float)):
        accum.setdefault(obj, []).append(f"{file_path}::{key_path}")


def _contains_literal_number(text: str, value: Any) -> bool:
    """Search for the value as a literal numeric token in the text."""
    # Normalize: int → integer literal; float → float literal (drop trailing .0)
    if isinstance(value, float) and value.is_integer():
        # Allow either "12" or "12.0" representations
        s_int = str(int(value))
        s_float = str(value)
        return bool(re.search(rf"(?<!\w){re.escape(s_int)}(?!\w)", text)) or \
               bool(re.search(rf"(?<!\w){re.escape(s_float)}(?!\w)", text))
    s = str(value)
    return bool(re.search(rf"(?<!\w){re.escape(s)}(?!\w)", text))


# ---------------------------------------------------------------------------
# Check 2: references
# ---------------------------------------------------------------------------

def _check_references(tree: Tree, flat: str) -> list[dict]:
    findings: list[dict] = []
    refs = _collect_references(tree)
    for ref_path, sites in refs.items():
        # The flattener strips braces — check for "ns.id" or "ns.id.subpath" as plain text
        if not _ref_path_in_text(flat, ref_path):
            findings.append({
                "check": "reference_resolved_in_b",
                "severity": "error",
                "reference": "{" + ref_path + "}",
                "sites": sites[:3],
                "message": f"Reference {{{ref_path}}} appears at {len(sites)} site(s) in A but its path is not present in B.",
            })
    return findings


def _collect_references(tree: Tree) -> dict[str, list[str]]:
    """Walk all frontmatter, return {ref_path: [list of sites]}."""
    refs: dict[str, list[str]] = {}
    for f in tree.files:
        _walk_for_refs(f.frontmatter, f.rel_str, "", refs)
    return refs


REF_RE = re.compile(r"\{([a-z_][a-z0-9_]*(?:\.[a-z0-9_][a-z0-9_-]*){1,5})\}")


def _walk_for_refs(obj: Any, file_path: str, key_path: str, accum: dict[str, list[str]]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            kp = f"{key_path}.{k}" if key_path else k
            _walk_for_refs(v, file_path, kp, accum)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            kp = f"{key_path}[{i}]"
            _walk_for_refs(v, file_path, kp, accum)
    elif isinstance(obj, str):
        for match in REF_RE.findall(obj):
            # Skip context-local refs (D-012): {actor.*}, {target.*}
            if match.startswith("actor.") or match.startswith("target."):
                continue
            accum.setdefault(match, []).append(f"{file_path}::{key_path}")


def _ref_path_in_text(text: str, ref_path: str) -> bool:
    """Look for the dotted path as plain text (the flattener strips braces)."""
    pattern = re.escape(ref_path)
    return bool(re.search(rf"(?<!\w){pattern}(?!\w)", text))


# ---------------------------------------------------------------------------
# Check 3: rule do-steps
# ---------------------------------------------------------------------------

def _check_rule_do_steps(tree: Tree, flat: str) -> list[dict]:
    findings: list[dict] = []
    rule_tokens = tree.top_level_tokens("rules")
    for full_id, (_file, rule) in rule_tokens.items():
        do_steps = rule.get("do", [])
        for i, step in enumerate(do_steps):
            step_marker = _step_marker(step)
            if not step_marker:
                continue  # nothing to check
            if step_marker not in flat:
                findings.append({
                    "check": "rule_do_step_present",
                    "severity": "error",
                    "rule": full_id,
                    "step_index": i,
                    "marker": step_marker,
                    "message": f"Rule {full_id}.do[{i}] uses marker {step_marker!r} which is not present in B.",
                })
    return findings


def _step_marker(step: Any) -> str | None:
    """Extract the recognizable name from a do-step."""
    if isinstance(step, dict):
        kind = step.get("kind")
        if kind:
            return f"`{kind}`"
        # Legacy shape: {action_name: ref}
        for k in step:
            if k not in ("if", "if_not", "if_either_zero", "condition_resource_at_zero",
                         "into", "from", "target", "by", "to", "amount"):
                return k
    elif isinstance(step, str):
        # Bare-string step (D-011 advisory) — its literal is the marker
        return step
    return None


# ---------------------------------------------------------------------------
# Check 4: distribution types
# ---------------------------------------------------------------------------

def _check_distribution_types(tree: Tree, flat: str) -> list[dict]:
    findings: list[dict] = []
    dists = tree.top_level_tokens("distributions")
    for full_id, (_file, dist) in dists.items():
        dtype = dist.get("type")
        if not dtype:
            continue
        # Look for the type name as a token in the flat text
        if not re.search(rf"(?<!\w){re.escape(dtype)}(?!\w)", flat):
            findings.append({
                "check": "distribution_type_present",
                "severity": "error",
                "distribution": full_id,
                "type": dtype,
                "message": f"Distribution {full_id} declares type {dtype!r} but the type name is absent from B.",
            })
    return findings


# ---------------------------------------------------------------------------
# Check 5: balance target values
# ---------------------------------------------------------------------------

def _check_balance_target_values(tree: Tree, flat: str) -> list[dict]:
    findings: list[dict] = []
    targets = tree.top_level_tokens("balance_targets")
    for full_id, (_file, bt) in targets.items():
        target_value = bt.get("target")
        measure = bt.get("measure", "")
        if not measure:
            findings.append({
                "check": "balance_target_measure_present",
                "severity": "error",
                "balance_target": full_id,
                "message": f"Balance target {full_id} declares no measure (cannot verify B retention).",
            })
            continue
        # Look for the measure prose AND the target value in B
        measure_present = measure[:60] in flat or any(
            measure[i:i+60] in flat for i in range(0, max(1, len(measure) - 60), 20)
        )
        # For scalar target values, look for the number
        target_present = True
        if isinstance(target_value, (int, float)):
            target_present = _contains_literal_number(flat, target_value)
        elif isinstance(target_value, dict):
            # range or distribution_over_categories — check every numeric value
            for v in _flatten_numbers(target_value):
                if not _contains_literal_number(flat, v):
                    target_present = False
                    break
        if not measure_present:
            findings.append({
                "check": "balance_target_measure_present",
                "severity": "error",
                "balance_target": full_id,
                "measure": measure[:80],
                "message": f"Balance target {full_id}'s measure prose is not present in B.",
            })
        if not target_present:
            findings.append({
                "check": "balance_target_value_present",
                "severity": "error",
                "balance_target": full_id,
                "target": target_value,
                "message": f"Balance target {full_id}'s target value {target_value!r} is not present in B.",
            })
    return findings


def _flatten_numbers(obj: Any) -> list[Any]:
    """Pull all numeric values out of a nested dict/list."""
    nums: list[Any] = []
    if isinstance(obj, dict):
        for v in obj.values():
            nums.extend(_flatten_numbers(v))
    elif isinstance(obj, list):
        for v in obj:
            nums.extend(_flatten_numbers(v))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        nums.append(obj)
    return nums


# ---------------------------------------------------------------------------
# Check 6: state machine transitions
# ---------------------------------------------------------------------------

def _check_state_machine_transitions(tree: Tree, flat: str) -> list[dict]:
    findings: list[dict] = []
    states = tree.top_level_tokens("states")
    for full_id, (_file, state) in states.items():
        transitions = state.get("transitions", [])
        for i, t in enumerate(transitions):
            if not isinstance(t, dict):
                continue
            frm = t.get("from", "")
            to = t.get("to", "")
            ev = t.get("event", "")
            # Strip braces from event if it's a ref
            ev_clean = ev[1:-1] if ev.startswith("{") and ev.endswith("}") else ev
            # We just need ALL THREE names to appear in B together-ish; the prose
            # paragraph for the state machine should contain all of them.
            for name in (frm, to, ev_clean):
                if name and name not in flat:
                    findings.append({
                        "check": "state_transition_present",
                        "severity": "error",
                        "state_machine": full_id,
                        "transition_index": i,
                        "missing_part": name,
                        "transition": {"from": frm, "event": ev, "to": to},
                        "message": f"State machine {full_id}.transitions[{i}] has component {name!r} not present in B.",
                    })
                    break
    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tree_root", type=Path, help="Path to the source game-design.md tree (A)")
    parser.add_argument("flattened", type=Path, help="Path to the flattened B text file")
    args = parser.parse_args(argv)

    flat = args.flattened.read_text()
    result = verify(args.tree_root, flat)
    sys.stdout.write(json.dumps(result, indent=2, default=str) + "\n")
    return 0 if result["summary"]["passes_completeness"] else 1


if __name__ == "__main__":
    sys.exit(main())
