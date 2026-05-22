"""End-to-end tests for `gdmd verify` against a Python fixture adapter.

The fixture adapter is a small Python script that implements the §9.5.6
contract (--target / --seed / --trajectory). Two variants:

  - SEED_OBEYING_ADAPTER — emits a different trajectory per seed (the
    expected behavior; negative control passes).
  - SEED_IGNORING_ADAPTER — emits the same trajectory regardless of seed
    (used to verify §9.5.7 catches an adapter that passes vacuously).

We don't shell out to xtreme here — those tests live in cargo. This suite
verifies the engine-neutral Python plumbing in verify_cmd.py.
"""
from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from game_design_md import verify_cmd
from game_design_md.tree import Tree


# An adapter that obeys --seed: trajectory varies by seed.
SEED_OBEYING_ADAPTER = """\
#!/usr/bin/env python3
import argparse, json
p = argparse.ArgumentParser()
p.add_argument("--target", required=True)
p.add_argument("--seed", type=int, required=True)
p.add_argument("--trajectory")
p.add_argument("--max-steps", type=int, default=100)
a = p.parse_args()
if a.target == "build_health":
    print(json.dumps({
        "results": [{"axis": "build_health", "target": "build_health",
                     "expected": {}, "observed": {"builds": True, "unresolved_refs": 0},
                     "pass": True, "notes": "ok"}],
        "summary": {"runs": 1, "passed": 1, "failed": 0, "skipped": 0},
    }))
else:
    n = 6
    lines = [json.dumps({"hp": 10 - t, "seed": a.seed, "tick": t},
                        separators=(",", ":"), sort_keys=True) for t in range(n)]
    if a.trajectory:
        with open(a.trajectory, "w", newline="\\n") as f:
            for line in lines:
                f.write(line + "\\n")
    print(json.dumps({
        "results": [{"axis": "behavioral_alignment", "target": a.target,
                     "expected": {}, "observed": {"trajectory_lines": len(lines)},
                     "pass": True, "notes": f"seed={a.seed}"}],
        "summary": {"runs": 1, "passed": 1, "failed": 0, "skipped": 0},
    }))
"""


# An adapter that IGNORES --seed: same trajectory regardless of seed.
SEED_IGNORING_ADAPTER = """\
#!/usr/bin/env python3
import argparse, json
p = argparse.ArgumentParser()
p.add_argument("--target", required=True)
p.add_argument("--seed", type=int, required=True)
p.add_argument("--trajectory")
p.add_argument("--max-steps", type=int, default=100)
a = p.parse_args()
n = 5
lines = [json.dumps({"tick": t}, separators=(",", ":"), sort_keys=True)
         for t in range(n)]
if a.trajectory:
    with open(a.trajectory, "w", newline="\\n") as f:
        for line in lines:
            f.write(line + "\\n")
print(json.dumps({
    "results": [{"axis": "behavioral_alignment", "target": a.target,
                 "expected": {}, "observed": {"trajectory_lines": len(lines)},
                 "pass": True, "notes": "seed-ignoring impl"}],
    "summary": {"runs": 1, "passed": 1, "failed": 0, "skipped": 0},
}))
"""


def _write_adapter(root: Path, source: str) -> Path:
    p = root / "tools" / "verify-adapter"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(source)
    p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return p


def _verification_md(verify_targets_yaml: str) -> str:
    return (
        "---\n"
        "spec: game-design.md\n"
        "spec_version: 0.2.0-alpha\n"
        "file_type: subfile\n"
        "status: implemented\n"
        'last_verified: "2026-05-22"\n'
        "verify_targets:\n"
        f"{verify_targets_yaml}"
        "adapters:\n"
        '  default: "./tools/verify-adapter"\n'
        "  presentation: null\n"
        "---\n"
        "\n"
        "## Tokens\n\nVerify config under test.\n"
    )


def _canonical_golden(rows: list[dict]) -> str:
    return "".join(
        json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n" for r in rows
    )


def test_verify_trajectory_match_and_negative_control(make_tree):
    """Primary trajectory byte-identical to golden → pass; negative_control
    seed produces a different trajectory → pass. End-to-end happy path."""
    root = make_tree({"gdd/verification.md": _verification_md(
        '  - axis: behavioral_alignment\n'
        '    target: "{loops.main}"\n'
        '    seed: 42\n'
        '    expect:\n'
        '      trajectory:\n'
        '        matches_golden: ./tests/golden.jsonl\n'
        '    negative_control:\n'
        '      seeds: [99]\n'
        '      expect: { trajectory_diverges_from_primary: true }\n'
    )})
    _write_adapter(root, SEED_OBEYING_ADAPTER)
    (root / "tests").mkdir()
    golden_rows = [{"hp": 10 - t, "seed": 42, "tick": t} for t in range(6)]
    (root / "tests" / "golden.jsonl").write_text(_canonical_golden(golden_rows))

    tree = Tree.load(root)
    targets, adapters = verify_cmd.collect_config(tree)
    assert len(targets) == 1
    adapter_path = verify_cmd.resolve_adapter(adapters["default"], tree.root)
    result = verify_cmd.run_all(targets, adapter_path, tree.root)
    assert result["summary"]["failed"] == 0
    assert result["summary"]["passed"] == 2  # primary + 1 negative_control
    assert verify_cmd.evaluate(result) == 0
    notes = result["results"][0]["notes"]
    assert "byte-identical" in notes


def test_verify_negative_control_catches_seed_ignoring_adapter(make_tree):
    """An adapter that ignores --seed passes the primary trajectory match
    vacuously (its golden was synthesized from the adapter's own output) but
    the negative_control catches it because seed 2 produces the same bytes."""
    root = make_tree({"gdd/verification.md": _verification_md(
        '  - axis: behavioral_alignment\n'
        '    target: "{loops.main}"\n'
        '    seed: 1\n'
        '    expect:\n'
        '      trajectory:\n'
        '        matches_golden: ./tests/golden.jsonl\n'
        '    negative_control:\n'
        '      seeds: [2]\n'
        '      expect: { trajectory_diverges_from_primary: true }\n'
    )})
    _write_adapter(root, SEED_IGNORING_ADAPTER)
    (root / "tests").mkdir()
    golden_rows = [{"tick": t} for t in range(5)]
    (root / "tests" / "golden.jsonl").write_text(_canonical_golden(golden_rows))

    tree = Tree.load(root)
    targets, adapters = verify_cmd.collect_config(tree)
    adapter_path = verify_cmd.resolve_adapter(adapters["default"], tree.root)
    result = verify_cmd.run_all(targets, adapter_path, tree.root)
    rows = result["results"]
    assert len(rows) == 2
    primary, nc = rows
    assert primary["pass"] is True, "primary trajectory matches the synthesized golden"
    assert nc["pass"] is False, "negative_control must catch the seed-ignoring adapter"
    assert "FAILED" in nc["notes"]
    assert "not responding to --seed" in nc["notes"]
    assert verify_cmd.evaluate(result) == 1


def test_verify_trajectory_mismatch_reports_first_divergence_line(make_tree):
    """Adapter output ≠ golden → primary fails, notes name the first
    diverging line."""
    root = make_tree({"gdd/verification.md": _verification_md(
        '  - axis: behavioral_alignment\n'
        '    target: "{loops.main}"\n'
        '    seed: 7\n'
        '    expect:\n'
        '      trajectory:\n'
        '        matches_golden: ./tests/golden.jsonl\n'
    )})
    _write_adapter(root, SEED_OBEYING_ADAPTER)
    (root / "tests").mkdir()
    # Deliberately wrong golden: hp values are off by one.
    bad_rows = [{"hp": 99 - t, "seed": 7, "tick": t} for t in range(6)]
    (root / "tests" / "golden.jsonl").write_text(_canonical_golden(bad_rows))

    tree = Tree.load(root)
    targets, adapters = verify_cmd.collect_config(tree)
    adapter_path = verify_cmd.resolve_adapter(adapters["default"], tree.root)
    result = verify_cmd.run_all(targets, adapter_path, tree.root)
    primary = result["results"][0]
    assert primary["pass"] is False
    assert "diverges" in primary["notes"]
    assert "first divergence line 1" in primary["notes"]
    assert verify_cmd.evaluate(result) == 1


def test_verify_build_health_only(make_tree):
    """A build_health target → one pass row, no trajectory, no negative
    control. Adapter still gets invoked; reaching the result IS success."""
    root = make_tree({"gdd/verification.md": _verification_md(
        '  - axis: build_health\n'
        '    expect: { builds: true, unresolved_refs: 0 }\n'
    )})
    _write_adapter(root, SEED_OBEYING_ADAPTER)

    tree = Tree.load(root)
    targets, adapters = verify_cmd.collect_config(tree)
    adapter_path = verify_cmd.resolve_adapter(adapters["default"], tree.root)
    result = verify_cmd.run_all(targets, adapter_path, tree.root)
    assert len(result["results"]) == 1
    assert result["results"][0]["pass"] is True
    assert result["results"][0]["axis"] == "build_health"
    assert verify_cmd.evaluate(result) == 0


def test_verify_adapter_missing_raises(make_tree):
    """Adapter executable absent → resolve_adapter raises VerifyError with
    the path that wasn't found."""
    root = make_tree({"gdd/verification.md": _verification_md(
        '  - axis: build_health\n'
        '    expect: { builds: true }\n'
    )})
    # Do not write the adapter.

    tree = Tree.load(root)
    _, adapters = verify_cmd.collect_config(tree)
    with pytest.raises(verify_cmd.VerifyError, match="adapter not found"):
        verify_cmd.resolve_adapter(adapters["default"], tree.root)


def test_verify_collect_targets_and_adapters_from_subfile(make_tree):
    """collect_config pulls verify_targets + adapters out of a subfile."""
    root = make_tree({"gdd/verification.md": _verification_md(
        '  - axis: behavioral_alignment\n'
        '    target: "{loops.main}"\n'
        '    seed: 1\n'
        '    expect: { foo: bar }\n'
    )})
    tree = Tree.load(root)
    targets, adapters = verify_cmd.collect_config(tree)
    assert len(targets) == 1
    assert targets[0].axis == "behavioral_alignment"
    assert targets[0].target == "{loops.main}"
    assert targets[0].seed == 1
    assert targets[0].target_ref == "{loops.main}"
    assert adapters["default"] == "./tools/verify-adapter"
