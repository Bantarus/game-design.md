"""All v0.1.1 linter rules.

Each `rule_<name>(tree)` returns a list[Finding]. `run_all(tree)` runs them
all and packages the result as a `LintResult` (whose `.to_dict()` matches
the JSON shape documented in `docs/spec.md` §9.1).
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable

from .findings import Finding, LintResult
from .refs import TOKEN_REF_RE, walk_refs
from .tree import SUBFILE_NAMESPACES, ParsedFile, Tree

# ---- Canonical section orders (spec §7.1) ---------------------------------------

CANONICAL_SECTIONS: dict[str, list[str]] = {
    "core": [
        "High Concept", "Pillars & Non-Goals", "Player Experience Goals",
        "Core Gameplay Loop", "Universal Surface",
        "How to Use This Document (for the Agent)", "Glossary",
    ],
    "subfile": ["Tokens", "Rationale", "Open Questions", "Change Log"],
    "content-schema": ["Schema", "Representative Example", "Balance Notes",
                       "Open Questions"],
}

STATUS_LEVELS = {
    "draft": 0, "prototyped": 1, "implemented": 2, "balanced": 3,
    "shipped": 4, "cut": -1,
}


def _extract_h2(body: str) -> list[tuple[str, int]]:
    """Return [(heading_text, line_no), ...] for every '## ...' heading."""
    headings = []
    for i, line in enumerate(body.splitlines(), 1):
        m = re.match(r"##\s+(.+?)\s*$", line)
        if m:
            headings.append((m.group(1).strip(), i))
    return headings


def _is_dist_ref(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("{distributions.")
        and value.endswith("}")
    )


def _collect_refs_in_block(value: Any) -> set[str]:
    return {ref for ref, _ in walk_refs(value)}


# ---- Rules --------------------------------------------------------------------

# D-012: context-local prefixes are NOT globally-resolvable namespaces. They
# are reserved placeholders bound at rule-evaluation time (e.g. `{actor.attack}`
# resolves to the acting unit's `attack` field when the consuming rule fires).
# The broken-ref rule skips refs whose first segment is one of these prefixes.
CONTEXT_LOCAL_PREFIXES: frozenset[str] = frozenset({"actor", "target"})


def _is_context_local(ref: str) -> bool:
    head = ref.split(".", 1)[0]
    return head in CONTEXT_LOCAL_PREFIXES


def rule_broken_ref(tree: Tree) -> list[Finding]:
    findings: list[Finding] = []
    for pf in tree.files:
        for ref, path in walk_refs(pf.frontmatter or {}):
            if _is_context_local(ref):
                continue
            if not tree.has_token(ref):
                findings.append(Finding(
                    rule="broken-ref", severity="error", file=pf.rel_str,
                    location="frontmatter:" + ".".join(path),
                    message=f"reference {{{ref}}} does not resolve",
                ))
        for m in TOKEN_REF_RE.finditer(pf.body or ""):
            ref = m.group(1)
            if _is_context_local(ref):
                continue
            if not tree.has_token(ref):
                line = (pf.body or "")[:m.start()].count("\n") + 1
                findings.append(Finding(
                    rule="broken-ref", severity="error", file=pf.rel_str,
                    location=f"body:line {line}",
                    message=f"reference {{{ref}}} does not resolve",
                ))
    return findings


def rule_missing_pillars(tree: Tree) -> list[Finding]:
    if not tree.core:
        return []
    pillars = tree.core.frontmatter.get("pillars") or []
    if not isinstance(pillars, list) or len(pillars) < 3:
        return [Finding(
            rule="missing-pillars", severity="error", file=tree.core.rel_str,
            location="pillars",
            message=f"core file requires >=3 pillars; got {len(pillars) if isinstance(pillars, list) else 0}",
        )]
    return []


def rule_missing_core_loop(tree: Tree) -> list[Finding]:
    if not tree.core:
        return []
    ref = tree.core.frontmatter.get("core_loop_ref")
    if not isinstance(ref, str):
        return [Finding(
            rule="missing-core-loop", severity="error", file=tree.core.rel_str,
            location="core_loop_ref",
            message="core file is missing core_loop_ref",
        )]
    m = re.match(r"^\{([a-z_][a-z0-9_.\-]+)\}$", ref)
    if not m or not tree.has_token(m.group(1)):
        return [Finding(
            rule="missing-core-loop", severity="error", file=tree.core.rel_str,
            location="core_loop_ref",
            message=f"core_loop_ref {ref!r} does not resolve",
        )]
    return []


def rule_missing_balance_targets(tree: Tree) -> list[Finding]:
    has_any = any(
        isinstance(pf.frontmatter.get("balance_targets"), dict)
        and pf.frontmatter["balance_targets"]
        for pf in tree.files if pf.file_type == "subfile"
    )
    if has_any:
        return []
    return [Finding(
        rule="missing-balance-targets", severity="error",
        file=tree.core.rel_str if tree.core else "",
        location="balance_targets",
        message="no balance_targets defined anywhere in the tree",
    )]


def rule_undefined_distribution(tree: Tree) -> list[Finding]:
    """Any rule.do[].sample step must point at a named {distributions.<id>}.

    `sample:` is the canonical key. Other stochastic verbs (`roll`, `random`,
    `draw`) are reserved; if they appear, they're checked too.
    """
    findings: list[Finding] = []
    stochastic_keys = ("sample", "roll", "random")
    for pf in tree.files:
        if pf.file_type != "subfile":
            continue
        rules = pf.frontmatter.get("rules")
        if not isinstance(rules, dict):
            continue
        for rname, rule in rules.items():
            if not isinstance(rule, dict):
                continue
            for i, step in enumerate(rule.get("do", []) or []):
                if not isinstance(step, dict):
                    continue
                for sk in stochastic_keys:
                    if sk in step and not _is_dist_ref(step[sk]):
                        findings.append(Finding(
                            rule="undefined-distribution", severity="error",
                            file=pf.rel_str,
                            location=f"rules.{rname}.do[{i}].{sk}",
                            message=(f"stochastic step '{sk}:' does not reference "
                                     f"a {{distributions.<id>}}; got {step[sk]!r}"),
                        ))
    return findings


def rule_inline_content_over_threshold(tree: Tree) -> list[Finding]:
    findings: list[Finding] = []
    for pf in tree.files:
        if pf.file_type != "content-schema":
            continue
        count = pf.frontmatter.get("count_target", 0) or 0
        data_dir = pf.frontmatter.get("data_dir")
        if count >= 20 and not data_dir:
            findings.append(Finding(
                rule="inline-content-over-threshold", severity="error",
                file=pf.rel_str, location="count_target",
                message=(f"count_target={count} >=20 requires data_dir to point "
                         f"at content/<kind>/*.yaml"),
            ))
    return findings


def rule_state_machine_coverage(tree: Tree) -> list[Finding]:
    findings: list[Finding] = []
    for pf in tree.files:
        if pf.file_type != "subfile":
            continue
        machines = pf.frontmatter.get("states")
        if not isinstance(machines, dict):
            continue
        for mname, m in machines.items():
            if not isinstance(m, dict):
                continue
            initial = m.get("initial")
            nodes = m.get("nodes") or []
            transitions = m.get("transitions") or []
            node_ids = {n["id"] for n in nodes
                        if isinstance(n, dict) and "id" in n}
            terminal_ids = {n["id"] for n in nodes
                            if isinstance(n, dict) and n.get("terminal")}

            loc_base = f"states.{mname}"
            if not initial or initial not in node_ids:
                findings.append(Finding(
                    rule="state-machine-coverage", severity="error",
                    file=pf.rel_str, location=f"{loc_base}.initial",
                    message=f"missing-initial: 'initial' missing or not in nodes ({initial!r})",
                ))
                continue

            for i, t in enumerate(transitions):
                if not isinstance(t, dict):
                    continue
                for key in ("from", "to"):
                    n = t.get(key)
                    if n is not None and n not in node_ids:
                        findings.append(Finding(
                            rule="state-machine-coverage", severity="error",
                            file=pf.rel_str,
                            location=f"{loc_base}.transitions[{i}].{key}",
                            message=f"undeclared-destination: {key}={n!r} not in nodes",
                        ))

            outgoing: dict[str, list[dict]] = defaultdict(list)
            for t in transitions:
                if isinstance(t, dict) and t.get("from"):
                    outgoing[t["from"]].append(t)

            for n in node_ids - terminal_ids:
                if not outgoing.get(n):
                    findings.append(Finding(
                        rule="state-machine-coverage", severity="error",
                        file=pf.rel_str, location=f"{loc_base}.nodes['{n}']",
                        message=(f"dead-end: non-terminal node '{n}' has no "
                                 f"outgoing transition"),
                    ))

            # D-005: undefined-event — transition `event:` values must be
            # {events.<id>} token refs. Bare strings are the v0.1.1 legacy
            # shape; flag them as warnings during the migration window. (A
            # {events.<id>} ref that does NOT resolve is already an error via
            # broken-ref.)
            for i, t in enumerate(transitions):
                if not isinstance(t, dict):
                    continue
                ev = t.get("event")
                if not isinstance(ev, str):
                    continue
                m = re.match(r"^\{(events\.[a-z0-9_][a-z0-9_-]*)\}$", ev)
                if m is None:
                    findings.append(Finding(
                        rule="state-machine-coverage", severity="warning",
                        file=pf.rel_str,
                        location=f"{loc_base}.transitions[{i}].event",
                        message=(f"undefined-event: event={ev!r} is a bare "
                                 f"string; promote to a {{events.<id>}} token "
                                 f"reference. Ratchets to error in v0.3."),
                    ))

            reachable = {initial}
            frontier = [initial]
            while frontier:
                cur = frontier.pop()
                for t in outgoing.get(cur, []):
                    to = t.get("to")
                    if to and to in node_ids and to not in reachable:
                        reachable.add(to)
                        frontier.append(to)
            for n in node_ids - reachable:
                findings.append(Finding(
                    rule="state-machine-coverage", severity="warning",
                    file=pf.rel_str, location=f"{loc_base}.nodes['{n}']",
                    message=f"unreachable-node: '{n}' not reachable from initial '{initial}'",
                ))
    return findings


def rule_section_order(tree: Tree) -> list[Finding]:
    findings: list[Finding] = []
    for pf in tree.files:
        if pf.file_type not in CANONICAL_SECTIONS:
            continue
        canonical = CANONICAL_SECTIONS[pf.file_type]
        headings = _extract_h2(pf.body or "")
        # Duplicate detection (hard error per spec §7.2)
        seen: dict[str, int] = {}
        for h, line in headings:
            if h in seen:
                findings.append(Finding(
                    rule="section-order", severity="error", file=pf.rel_str,
                    location=f"body:line {line}",
                    message=f"duplicate heading '## {h}' (first at line {seen[h]})",
                ))
            else:
                seen[h] = line
        # Canonical order: canonical headings appear in canonical order; any
        # non-canonical heading must come after every canonical heading.
        last_canonical_idx = -1
        unknown_opened = False
        for h, line in headings:
            if h in canonical:
                if unknown_opened:
                    findings.append(Finding(
                        rule="section-order", severity="error", file=pf.rel_str,
                        location=f"body:line {line}",
                        message=(f"canonical section '## {h}' appears after a "
                                 f"non-canonical section"),
                    ))
                    continue
                idx = canonical.index(h)
                if idx < last_canonical_idx:
                    findings.append(Finding(
                        rule="section-order", severity="error", file=pf.rel_str,
                        location=f"body:line {line}",
                        message=f"'## {h}' is out of canonical order",
                    ))
                last_canonical_idx = idx
            else:
                unknown_opened = True
    return findings


def rule_orphaned_entity(tree: Tree) -> list[Finding]:
    all_refs: set[str] = set()
    for pf in tree.files:
        for ref, _ in walk_refs(pf.frontmatter or {}):
            all_refs.add(ref)
        for m in TOKEN_REF_RE.finditer(pf.body or ""):
            all_refs.add(m.group(1))

    findings: list[Finding] = []
    # Verbs are covered by unreferenced-verb (stricter check); invariants and
    # pillars are not value-referenced by design. Everything else gets checked.
    # `clocks` joins at v0.3: a clock declared but unreferenced (no loop's
    # `clock:` field, no rule's `given.driver:`, no other consumer) is orphaned.
    checked = ("entities", "resources", "states", "rules", "loops",
               "distributions", "feel", "balance_targets", "events", "clocks")
    for ns in checked:
        for token, (pf, value) in tree.tokens.get(ns, {}).items():
            if ns == "entities" and token.count(".") > 1:
                continue  # per-content-entity registration; skip
            if isinstance(value, dict) and value.get("status") == "cut":
                continue
            if ns == "entities" and isinstance(value, dict) \
                    and value.get("type") == "actor":
                continue  # the player exemption (spec §8.2)
            referenced = any(
                ref == token or ref.startswith(token + ".")
                for ref in all_refs
            )
            if not referenced:
                findings.append(Finding(
                    rule="orphaned-entity", severity="warning", file=pf.rel_str,
                    location=token,
                    message=f"{token} is defined but not referenced anywhere",
                ))
    return findings


def rule_unreferenced_verb(tree: Tree) -> list[Finding]:
    invoking_refs: set[str] = set()
    for pf in tree.files:
        if pf.file_type != "subfile":
            continue
        for ns in ("loops", "rules"):
            block = pf.frontmatter.get(ns)
            if isinstance(block, dict):
                invoking_refs |= _collect_refs_in_block(block)

    findings: list[Finding] = []
    for verb_path, (pf, value) in tree.tokens.get("verbs", {}).items():
        if isinstance(value, dict) and value.get("status") == "cut":
            continue
        referenced = any(
            ref == verb_path or ref.startswith(verb_path + ".")
            for ref in invoking_refs
        )
        if not referenced:
            findings.append(Finding(
                rule="unreferenced-verb", severity="warning", file=pf.rel_str,
                location=verb_path,
                message=f"{verb_path} is defined but no loop or rule invokes it",
            ))
    return findings


def rule_broken_implementation_pointer(tree: Tree) -> list[Finding]:
    """Severity is `error` at v0.2 (D-002 ratchet). At v0.1.1 the rule was a
    warning because no example shipped real source; the tick-combat / xtreme
    Bevy ECS implementation + the verify-adapter binary close that gap, so
    the rule now blocks on prototyped+ entities whose implemented_in: paths
    don't resolve."""
    findings: list[Finding] = []
    severity = "error"  # D-002 ratcheted at v0.2.0-alpha Phase 3+

    def check_glob(pf: ParsedFile, pattern: str, location: str) -> None:
        try:
            matches = list(tree.root.glob(pattern))
        except Exception:
            matches = []
        if not matches:
            findings.append(Finding(
                rule="broken-implementation-pointer", severity=severity,
                file=pf.rel_str, location=location,
                message=f"glob {pattern!r} resolves to zero files",
            ))

    for pf in tree.files:
        status = pf.frontmatter.get("status") if pf.frontmatter else None
        level = STATUS_LEVELS.get(status or "draft", 0)
        impl = pf.frontmatter.get("implemented_in") if pf.frontmatter else None
        if isinstance(impl, list) and level >= 1:
            for i, pattern in enumerate(impl):
                if isinstance(pattern, str):
                    check_glob(pf, pattern, f"implemented_in[{i}]")
        if pf.file_type == "subfile":
            for ns in SUBFILE_NAMESPACES:
                block = pf.frontmatter.get(ns)
                if not isinstance(block, dict):
                    continue
                for k, v in block.items():
                    if not isinstance(v, dict):
                        continue
                    sub_level = STATUS_LEVELS.get(v.get("status") or "draft", 0)
                    sub_impl = v.get("implemented_in")
                    if isinstance(sub_impl, list) and sub_level >= 1:
                        for i, pat in enumerate(sub_impl):
                            if isinstance(pat, str):
                                check_glob(
                                    pf, pat,
                                    f"{ns}.{k}.implemented_in[{i}]",
                                )
    # The root-file `implementation_pointers:` map is also gated on the core
    # file's status. A design-stage tree (status: draft) is silent here — the
    # code isn't written yet; that's expected, not a defect.
    if tree.core:
        core_level = STATUS_LEVELS.get(tree.core.frontmatter.get("status") or "draft", 0)
        ip = tree.core.frontmatter.get("implementation_pointers")
        if isinstance(ip, dict) and core_level >= 1:
            for key, pat in ip.items():
                if isinstance(pat, str):
                    check_glob(tree.core, pat, f"implementation_pointers.{key}")
    return findings


def rule_stale_section(tree: Tree) -> list[Finding]:
    findings: list[Finding] = []
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
        impl = pf.frontmatter.get("implemented_in")
        if not isinstance(impl, list):
            continue
        for pat in impl:
            if not isinstance(pat, str):
                continue
            try:
                matches = list(tree.root.glob(pat))
            except Exception:
                matches = []
            for src in matches:
                if not src.is_file():
                    continue
                mtime = datetime.fromtimestamp(src.stat().st_mtime)
                if (mtime - lv).days > 30:
                    findings.append(Finding(
                        rule="stale-section", severity="warning",
                        file=pf.rel_str, location="last_verified",
                        message=(
                            f"source {src.relative_to(tree.root)} is "
                            f"{(mtime - lv).days} days newer than "
                            f"last_verified={lv_raw}"
                        ),
                    ))
                    break
    return findings


def rule_balance_target_untyped(tree: Tree) -> list[Finding]:
    """D-003: every `balance_targets.<id>` must declare `target_kind:`.

    Legacy v0.1.1 targets without a `target_kind` field are accepted with a
    warning. Ratchets to error in v0.3 once the deferral window closes.
    """
    findings: list[Finding] = []
    for pf in tree.files:
        if pf.file_type != "subfile":
            continue
        targets = pf.frontmatter.get("balance_targets")
        if not isinstance(targets, dict):
            continue
        for name, target in targets.items():
            if not isinstance(target, dict):
                continue
            if "target_kind" not in target:
                findings.append(Finding(
                    rule="balance-target-untyped", severity="warning",
                    file=pf.rel_str,
                    location=f"balance_targets.{name}",
                    message=(f"balance target '{name}' is missing target_kind: "
                             f"(one of scalar | range | distribution_over_categories). "
                             f"Permissive shape deprecated; ratchets to error in v0.3."),
                ))
    return findings


def rule_determinism_undetermined_rule(tree: Tree) -> list[Finding]:
    """D-011: a `do:` step that's a bare string inside a rule reachable from a
    deterministic loop is a *prose label*, not a computable procedure. Two
    engines may interpret it differently, breaking the cross-engine bar.

    Reachability heuristic (v0.2.0-alpha + F-010 v0.3 extension for clocks):
      1. Collect verbs invoked from any loop with `timescale: moment`.
      2. Collect clocks referenced (via the loop's `clock:` field) from any
         moment loop, and then the rules each clock drives (via the clock's
         `drives:` list).
      3. Collect rules whose `given.verb:` matches a moment verb OR whose
         `given.driver:` matches a moment clock OR which appear in any moment
         clock's `drives:` list.
      4. For each such rule, flag every `do[]` item that is a string (not a dict).

    Severity is `info` (advisory) at v0.2.0-alpha — visibility, not gate.
    Ratchets to `warning` in v0.3, `error` in v0.4 (per D-011).
    """
    # (1) Verbs referenced from moment loops.
    moment_verbs: set[str] = set()
    # (2a) Clocks referenced via the loop's `clock:` field on a moment loop.
    moment_clocks: set[str] = set()
    for loop_path, (_pf, loop) in tree.tokens.get("loops", {}).items():
        if not isinstance(loop, dict):
            continue
        if loop.get("timescale") != "moment":
            continue
        sequence = loop.get("sequence")
        if isinstance(sequence, list):
            for ref, _ in walk_refs(sequence):
                if ref.startswith("verbs."):
                    moment_verbs.add(ref)
        clock_ref = loop.get("clock")
        if isinstance(clock_ref, str):
            m = re.match(r"^\{([a-z_][a-z0-9_.\-]+)\}$", clock_ref)
            if m and m.group(1).startswith("clocks."):
                moment_clocks.add(m.group(1))

    # (2b) Rules listed in any moment clock's `drives:` array.
    moment_driver_rules: set[str] = set()
    for clock_path in moment_clocks:
        info = tree.tokens.get("clocks", {}).get(clock_path)
        if not info:
            continue
        _pf, clock = info
        if not isinstance(clock, dict):
            continue
        for drive_ref in clock.get("drives") or []:
            if not isinstance(drive_ref, str):
                continue
            m = re.match(r"^\{([a-z_][a-z0-9_.\-]+)\}$", drive_ref)
            if m and m.group(1).startswith("rules."):
                moment_driver_rules.add(m.group(1))

    # (3) Rules whose given.verb is in moment_verbs, OR given.driver is in
    # moment_clocks, OR which appear in a moment clock's drives: list.
    deterministic_rules: dict[str, tuple] = {}
    for rule_path, (pf, rule) in tree.tokens.get("rules", {}).items():
        if not isinstance(rule, dict):
            continue
        given = rule.get("given")
        if not isinstance(given, dict):
            continue
        verb_ref = given.get("verb")
        if isinstance(verb_ref, str):
            m = re.match(r"^\{([a-z_][a-z0-9_.\-]+)\}$", verb_ref)
            if m and m.group(1) in moment_verbs:
                deterministic_rules[rule_path] = (pf, rule)
                continue
        driver_ref = given.get("driver")
        if isinstance(driver_ref, str):
            m = re.match(r"^\{([a-z_][a-z0-9_.\-]+)\}$", driver_ref)
            if m and m.group(1) in moment_clocks:
                deterministic_rules[rule_path] = (pf, rule)
                continue
        if rule_path in moment_driver_rules:
            deterministic_rules[rule_path] = (pf, rule)

    # (4) Scan each deterministic rule's do[] for bare-string items.
    findings: list[Finding] = []
    for rule_path, (pf, rule) in deterministic_rules.items():
        do = rule.get("do")
        if not isinstance(do, list):
            continue
        rname = rule_path.split(".", 1)[1] if "." in rule_path else rule_path
        for i, step in enumerate(do):
            if isinstance(step, str):
                findings.append(Finding(
                    rule="determinism-undetermined-rule", severity="info",
                    file=pf.rel_str,
                    location=f"rules.{rname}.do[{i}]",
                    message=(
                        f"bare-string do[] step {step!r} in rule '{rname}' "
                        f"(reachable from a deterministic loop): prose labels "
                        f"don't constrain implementations. Restructure to a "
                        f"typed step (e.g. {{kind: <verb>, …}}). D-011."
                    ),
                ))
    return findings


def rule_write_to_template_field(tree: Tree) -> list[Finding]:
    """D-019 (F-008 v0.3 addressing DSL): writes to instance_container fields
    are restricted to per_instance_state fields.

    A do[] step declaring `field: <name>` where <name> is not present in any
    instance_container's per_instance_state schema indicates either:
      (a) a write to a template field — templates are immutable per §6, the
          content_collection / instance_container separation is what makes the
          per_instance_state declaration load-bearing; mutating template state
          at runtime defeats it.
      (b) a write to an undeclared field — author probably typo or genuine
          omission; either way, the runtime-state shape must live in the
          per_instance_state schema or it's not contracted.

    The check is opt-in (fires only when `field:` is declared on a do[] step).
    Authors not declaring `field:` on mutation steps escape the check; that's
    the v0.3 / v0.4 ratchet path — declared-field becomes required in v0.4 once
    the discipline settles.
    """
    # Collect all writable per_instance_state field names across all
    # instance_containers in the tree.
    writable_fields: set[str] = set()
    for pf in tree.files:
        if pf.file_type != "subfile":
            continue
        entities = pf.frontmatter.get("entities")
        if not isinstance(entities, dict):
            continue
        for entity in entities.values():
            if not isinstance(entity, dict):
                continue
            if entity.get("type") != "instance_container":
                continue
            pis = entity.get("per_instance_state")
            if isinstance(pis, dict):
                writable_fields.update(pis.keys())

    # If no instance_containers exist in the tree, the rule is a no-op.
    if not writable_fields:
        return []

    findings: list[Finding] = []
    for pf in tree.files:
        if pf.file_type != "subfile":
            continue
        rules = pf.frontmatter.get("rules")
        if not isinstance(rules, dict):
            continue
        for rname, rule in rules.items():
            if not isinstance(rule, dict):
                continue
            do = rule.get("do") or []
            if not isinstance(do, list):
                continue
            for i, step in enumerate(do):
                if not isinstance(step, dict):
                    continue
                field = step.get("field")
                if not isinstance(field, str):
                    continue
                if field not in writable_fields:
                    findings.append(Finding(
                        rule="write-to-template-field", severity="error",
                        file=pf.rel_str,
                        location=f"rules.{rname}.do[{i}].field",
                        message=(
                            f"do[] step writes to field {field!r}, which is "
                            f"not declared in any instance_container's "
                            f"per_instance_state schema. Writes are restricted "
                            f"to per_instance_state fields (D-019); templates "
                            f"are immutable and container properties are "
                            f"likewise read-only. Add {field!r} to the target "
                            f"container's per_instance_state, or correct the "
                            f"field name."
                        ),
                    ))
    return findings


def rule_invariant_violation(tree: Tree) -> list[Finding]:
    findings: list[Finding] = []
    for pf in tree.files:
        if pf.file_type != "subfile":
            continue
        invs = pf.frontmatter.get("invariants")
        if not isinstance(invs, dict):
            continue
        for name, inv in invs.items():
            if not isinstance(inv, dict):
                continue
            enforcement = inv.get("enforcement")
            severity = inv.get("severity", "warning")
            if enforcement == "advisory":
                findings.append(Finding(
                    rule="invariant-violation", severity="info",
                    file=pf.rel_str, location=f"invariants.{name}",
                    message=(f"advisory invariant '{name}' declared; review "
                             f"in code review"),
                ))
            elif enforcement == "lint":
                for v_file, v_loc, v_msg in _check_lint_invariant(tree, name, inv):
                    findings.append(Finding(
                        rule="invariant-violation", severity=severity,
                        file=v_file, location=v_loc,
                        message=f"invariant '{name}' violated: {v_msg}",
                    ))
            # enforcement == "verify": no-op in lint
    return findings


def _is_int(value) -> bool:
    """True iff `value` is a Python int and not a bool (bool subclasses int)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _check_lint_invariant(tree: Tree, name: str, inv: dict) -> Iterable[tuple[str, str, str]]:
    """Run the statically-checkable subset of invariant.kind.

    For `numeric_domain` (D-009 scope at v0.2.0-alpha), three checks:
      1. Every `effects[].amount` in a content-entity is an integer (when the
         effect kind is `damage` or `gain_block`).
      2. For each `{entities.<kind>}` referenced in `applies_to:`, every content
         entity in that collection has integer values for every field that the
         content-schema declares `type: integer`.
      3. For each `{resources.<id>}` referenced in `applies_to:`, the resource's
         `min:` and `max:` bounds are integers.
    """
    kind = inv.get("kind")
    if kind == "numeric_domain":
        # (1) effects[].amount
        for collection, files in tree.content_entities.items():
            for pf in files:
                effects = pf.frontmatter.get("effects") or []
                if not isinstance(effects, list):
                    continue
                for i, eff in enumerate(effects):
                    if not isinstance(eff, dict):
                        continue
                    if eff.get("kind") in ("damage", "gain_block"):
                        amt = eff.get("amount")
                        if amt is not None and not _is_int(amt):
                            yield (str(pf.rel_path), f"effects[{i}].amount",
                                   f"amount={amt!r} is not an integer")

        applies_to = inv.get("applies_to") or []

        # (2) entity property integerness — driven by the content-schema's
        # `type: integer` fields. If the invariant lists {entities.<kind>}, walk
        # every content-entity in that collection.
        entity_kinds: set[str] = set()
        for ref in applies_to:
            if not isinstance(ref, str):
                continue
            m = re.match(r"^\{entities\.([a-z_][a-z0-9_]*)\}$", ref)
            if m:
                entity_kinds.add(m.group(1))
        for kind_name in entity_kinds:
            schema_pf = tree.content_schemas.get(kind_name)
            if not schema_pf:
                continue
            block_schema = schema_pf.frontmatter.get("schema") or {}
            properties = block_schema.get("properties") or {}
            integer_fields = sorted(
                field for field, spec in properties.items()
                if isinstance(spec, dict) and spec.get("type") == "integer"
            )
            for entity_pf in tree.content_entities.get(kind_name, []):
                for field in integer_fields:
                    v = entity_pf.frontmatter.get(field)
                    if v is None:
                        continue
                    if not _is_int(v):
                        yield (str(entity_pf.rel_path), field,
                               f"{field}={v!r} is not an integer")

        # (3) resource min/max integerness.
        resource_refs: set[str] = set()
        for ref in applies_to:
            if not isinstance(ref, str):
                continue
            m = re.match(r"^\{(resources\.[a-z_][a-z0-9_]*)\}$", ref)
            if m:
                resource_refs.add(m.group(1))
        for token_path in sorted(resource_refs):
            info = tree.tokens.get("resources", {}).get(token_path)
            if not info:
                continue
            pf, value = info
            if not isinstance(value, dict):
                continue
            for bound in ("min", "max"):
                v = value.get(bound)
                if v is None:
                    continue
                if not _is_int(v):
                    yield (str(pf.rel_path), f"{token_path}.{bound}",
                           f"{bound}={v!r} is not an integer")
    elif kind == "layer_boundary":
        # Statically checkable iff implementation_pointers.presentation is
        # declared. Out of scope for v0.1.1 — no presentation pointer in any
        # example. Returning empty is correct (and silent).
        return
    # numeric_domain / layer_boundary are the only lint-checkable kinds at
    # v0.2.0-alpha; others (architectural_pattern, communication) are typically
    # advisory and verify, respectively.


# ---- Dispatch -----------------------------------------------------------------

ALL_RULES: list[Callable[[Tree], list[Finding]]] = [
    rule_broken_ref,
    rule_missing_pillars,
    rule_missing_core_loop,
    rule_missing_balance_targets,
    rule_undefined_distribution,
    rule_inline_content_over_threshold,
    rule_state_machine_coverage,
    rule_section_order,
    rule_orphaned_entity,
    rule_unreferenced_verb,
    rule_broken_implementation_pointer,
    rule_stale_section,
    rule_balance_target_untyped,
    rule_determinism_undetermined_rule,
    rule_write_to_template_field,
    rule_invariant_violation,
]


def run_all(tree: Tree) -> LintResult:
    findings: list[Finding] = []
    for parse_err_path, msg in tree.parse_errors:
        try:
            rel = str(parse_err_path.relative_to(tree.root))
        except ValueError:
            rel = str(parse_err_path)
        findings.append(Finding(
            rule="parse-error", severity="error", file=rel,
            location="", message=msg,
        ))
    for r in ALL_RULES:
        findings.extend(r(tree))
    result = LintResult(findings=findings, files_scanned=len(tree.files))
    return result
