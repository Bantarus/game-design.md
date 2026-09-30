"""Tests for the dogfood harness (benchmark/dogfood/, D-023). No model calls.

- Every checker passes a known-good solution and fails known-bad ones, and the
  failing criterion is the one the bad solution targets.
- Fixtures produce the intended signal: the maintenance patch makes exactly the
  affected section stale; the negative-control patch touches nothing the spec
  references.
- The frozen lookup answers match a code derivation. This cross-check runs
  once, here; the checker itself only reads the frozen file.
- The arms differ only by the appended views section; the maintenance and
  control prompts are identical.
- Metric extraction and flag validation work on synthetic inputs.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DOGFOOD = REPO / "benchmark" / "dogfood"
sys.path.insert(0, str(DOGFOOD))

import fixture  # noqa: E402
import run as dogfood_run  # noqa: E402

TASKS = fixture.load_tasks()

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


# ---- helpers ------------------------------------------------------------------

def make_copy(task_id: str, tmp_path: Path) -> fixture.PreparedCopy:
    return fixture.prepare_copy(TASKS[task_id], tmp_path / task_id)


def check(task_id: str, copy: fixture.PreparedCopy) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(TASKS[task_id].checker_path), str(copy.root)],
                          env=copy.env(), capture_output=True, text=True)
    return proc.returncode, json.loads(proc.stdout)


def failed(report: dict) -> set[str]:
    return {k for k, v in report["criteria"].items() if not v["pass"]}


def gdmd(copy: fixture.PreparedCopy, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["gdmd", *args], cwd=copy.root, env=copy.env(),
                          capture_output=True, text=True)


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{old!r} not unique in {path}"
    path.write_text(text.replace(old, new), encoding="utf-8")


def bump_core_version(copy: fixture.PreparedCopy, tree: str) -> None:
    from datetime import date
    core = copy.root / tree / "game-design.md"
    text = core.read_text(encoding="utf-8")
    import re
    text = re.sub(r"^version: (\d+)\.(\d+)\.(\d+)$",
                  lambda m: f"version: {m[1]}.{m[2]}.{int(m[3]) + 1}", text, count=1, flags=re.M)
    text = re.sub(r'^last_updated: "?\d{4}-\d{2}-\d{2}"?$',
                  f'last_updated: "{date.today().isoformat()}"', text, count=1, flags=re.M)
    core.write_text(text, encoding="utf-8")


# ---- structural properties ------------------------------------------------------

def test_arms_differ_only_by_appended_views_section():
    base = (DOGFOOD / "arms" / "baseline.md").read_text()
    views = (DOGFOOD / "arms" / "views.md").read_text()
    assert views.startswith(base) and len(views) > len(base)
    assert "gdmd view" not in base and "gdmd graph" not in base


def test_control_prompt_identical_to_maintenance_prompt():
    assert TASKS["maintenance_drift"].prompt() == TASKS["negative_control_no_drift"].prompt()


def test_every_task_has_prompt_and_checker():
    for t in TASKS.values():
        assert t.prompt_path.is_file() and t.checker_path.is_file()
        if t.fixture_patch:
            assert (fixture.TASKS_DIR / t.fixture_patch).is_file()


def test_copy_strips_harness_and_lives_outside_repo(tmp_path):
    copy = make_copy("lookup_refs", tmp_path)
    assert not (copy.root / "benchmark" / "dogfood").exists()
    assert not (copy.root / "tests" / "test_dogfood.py").exists()
    assert (copy.root / "CLAUDE.md").is_file()
    assert REPO not in copy.root.resolve().parents


def test_copy_gdmd_resolves_to_its_own_shim(tmp_path):
    # Regression: the shim *file* was once put on PATH, so `gdmd` silently fell
    # through to whatever install was on the caller's PATH (the real repo's).
    copy = make_copy("lookup_refs", tmp_path)
    found = subprocess.run(["sh", "-c", "command -v gdmd"], env=copy.env(),
                           capture_output=True, text=True).stdout.strip()
    assert Path(found) == copy.shim_dir / "gdmd"
    assert str(copy.root / "src") in Path(found).read_text()


needs_v03 = pytest.mark.skipif(not (fixture.V03_VENV / "bin" / "gdmd").is_file(),
                               reason="v0.3 venv not installed (see benchmark/dogfood/README)")


@needs_v03
def test_v03_world_replaces_only_the_tooling_layer(tmp_path):
    fixture.verify_v03_venv(scratch=tmp_path)
    sha = fixture.git(REPO, "rev-parse", "HEAD")
    judge = fixture.make_judge(tmp_path / "judge", sha)
    task = TASKS["maintenance_drift"]
    old = fixture.prepare_copy(task, tmp_path / "v03", ref=sha, world="v0.3", judge=judge)
    new = fixture.prepare_copy(task, tmp_path / "mat", ref=sha, world="matrix", judge=judge)
    tag = fixture.V03_TAG
    for rel in ("docs/spec.md", "CLAUDE.md", "AGENTS.md", "src/game_design_md/cli.py"):
        at_tag = subprocess.run(["git", "-C", str(REPO), "show", f"{tag}:{rel}"],
                                capture_output=True, check=True).stdout
        assert (old.root / rel).read_bytes() == at_tag, rel
    diff = subprocess.run(["diff", "-r", "-q", "--exclude=.git",
                           str(old.root / task.tree), str(new.root / task.tree)],
                          capture_output=True, text=True)
    assert diff.returncode == 0, diff.stdout
    found = subprocess.run(["sh", "-c", "command -v gdmd"], env=old.env(),
                           capture_output=True, text=True).stdout.strip()
    assert str(fixture.V03_VENV / "bin" / "gdmd") in Path(found).read_text()
    assert old.overlay_sha == fixture.git(REPO, "rev-parse", f"{tag}^{{commit}}")


def test_judge_disagreement_is_a_fixture_error(tmp_path):
    fake = tmp_path / "fake-judge"
    fake.write_text('#!/bin/sh\necho \'{"findings": [], "summary": {"errors": 0}}\'\n')
    fake.chmod(0o755)
    with pytest.raises(fixture.FixtureError, match="disagree"):
        fixture.prepare_copy(TASKS["lookup_refs"], tmp_path / "c", judge=fake)


def test_maintenance_fixture_makes_exactly_mechanics_stale(tmp_path):
    copy = make_copy("maintenance_drift", tmp_path)
    res = json.loads(gdmd(copy, "lint", "examples/tick-combat").stdout)
    warn = [(f["rule"], f["file"]) for f in res["findings"] if f["severity"] != "info"]
    assert warn == [("stale-section", "gdd/mechanics.md")]


def test_negative_control_fixture_is_invisible_to_spec(tmp_path):
    copy = make_copy("negative_control_no_drift", tmp_path)
    changed = fixture.git(copy.root, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert changed == ["examples/tick-combat/impl/xtreme/tests/golden_trajectory.rs"]
    res = json.loads(gdmd(copy, "lint", "examples/tick-combat").stdout)["summary"]
    assert (res["errors"], res["warnings"]) == (0, 0)
    hook = gdmd(copy, "hook", "check", "examples/tick-combat", *changed)
    assert hook.stdout.strip() == ""


# ---- lookup oracle cross-check (runs once, here; the checker never does this) ---

def test_lookup_expected_matches_code_derivation():
    from game_design_md.refs import walk_refs
    from game_design_md.tree import Tree
    tree = Tree.load(REPO / "examples" / "deckbuilder")
    q1 = sorted(tok for table in tree.tokens.values() for tok, (_pf, val) in table.items()
                if tok != "resources.energy"
                and any(r == "resources.energy" or r.startswith("resources.energy.")
                        for r, _ in walk_refs(val)))
    seq = tree.tokens["loops"]["loops.combat_turn"][1]["sequence"]
    verbs = {r for r, _ in walk_refs(seq) if r.startswith("verbs.")}
    q2 = sorted({r for v in verbs for r, _ in walk_refs(tree.tokens["verbs"][v][1]["effects"])
                 if r.startswith("rules.")})
    frozen = json.loads((fixture.TASKS_DIR / "lookup_refs.expected.json").read_text())
    assert (q1, q2) == (frozen["Q1"], frozen["Q2"])


# ---- checkers: known-good passes, known-bad fails on the targeted criterion ------

KINDLE = """\
spec: game-design.md
spec_version: 0.3.0
file_type: content-entity
id: kindle
status: draft
implemented_in: ["src/ember_ascent/cards/kindle.py"]
name: "Kindle"
cost: 1
type: skill
rarity: uncommon
tags: [skill, fire]
effects:
  - kind: apply_state
    state: "{states.enemy_lifecycle.burning}"
    duration: 3
    stacks: 2
  - kind: gain_block
    amount: 4
"""


def _write_card(copy, text=KINDLE):
    (copy.root / "examples/deckbuilder/content/cards/kindle.yaml").write_text(text)


def test_authoring_good(tmp_path):
    copy = make_copy("authoring_new_card", tmp_path)
    _write_card(copy)
    bump_core_version(copy, "examples/deckbuilder")
    rc, rep = check("authoring_new_card", copy)
    assert rc == 0, rep


@pytest.mark.parametrize("mutate, criterion", [
    (lambda t: t.replace("kind: gain_block\n    amount: 4", "kind: gain_block\n    amount: 3"),
     "effects_match_brief"),
    (lambda t: t.replace("rarity: uncommon", "rarity: epic"), "validates_against_schema"),
    (lambda t: t.replace("status: draft", "status: prototyped"), "status_draft"),
    (lambda t: t.replace("id: kindle", "id: kindle_card"), "entity_header"),
])
def test_authoring_bad_card(tmp_path, mutate, criterion):
    copy = make_copy("authoring_new_card", tmp_path)
    _write_card(copy, mutate(KINDLE))
    rc, rep = check("authoring_new_card", copy)
    assert rc == 1 and criterion in failed(rep), rep


def test_authoring_bad_extra_edit(tmp_path):
    copy = make_copy("authoring_new_card", tmp_path)
    _write_card(copy)
    edit(copy.root / "examples/deckbuilder/content/cards/bellows.yaml", "amount: 3", "amount: 4")
    rc, rep = check("authoring_new_card", copy)
    assert rc == 1 and "no_unexpected_changes" in failed(rep)


def _answer(copy, text):
    (copy.root / "answers").mkdir(exist_ok=True)
    (copy.root / "answers" / "lookup.txt").write_text(text)


def test_lookup_good_and_normalized(tmp_path):
    copy = make_copy("lookup_refs", tmp_path)
    _answer(copy, "Q1: {entities.player}, {rules.end_of_turn}, {states.card_lifecycle}, "
                  "{verbs.play_card}\nQ2: {rules.damage_resolution}, {rules.draw_card}, "
                  "{rules.end_of_turn}\n")
    assert check("lookup_refs", copy)[0] == 0
    copy2 = make_copy("lookup_refs", tmp_path / "b")
    _answer(copy2, "Q1: verbs.play_card, entities.player, `{states.card_lifecycle}`, "
                   "rules.end_of_turn\nQ2: rules.end_of_turn, rules.draw_card, "
                   "rules.damage_resolution\n")
    assert check("lookup_refs", copy2)[0] == 0


def test_lookup_bad_misses_embedded_string_ref(tmp_path):
    copy = make_copy("lookup_refs", tmp_path)
    _answer(copy, "Q1: {entities.player}, {rules.end_of_turn}, {verbs.play_card}\n"
                  "Q2: {rules.damage_resolution}, {rules.draw_card}, {rules.end_of_turn}\n")
    rc, rep = check("lookup_refs", copy)
    assert rc == 1 and failed(rep) == {"q1_correct"}
    assert rep["criteria"]["q1_correct"]["detail"]["missing"] == ["states.card_lifecycle"]


def test_lookup_bad_other_file_changed(tmp_path):
    copy = make_copy("lookup_refs", tmp_path)
    _answer(copy, "Q1: {entities.player}, {rules.end_of_turn}, {states.card_lifecycle}, "
                  "{verbs.play_card}\nQ2: {rules.damage_resolution}, {rules.draw_card}, "
                  "{rules.end_of_turn}\n")
    (copy.root / "notes.md").write_text("scratch\n")
    rc, rep = check("lookup_refs", copy)
    assert rc == 1 and failed(rep) == {"no_other_changes"}


def _raise_energy(copy, *, max_=True, target=True, tolerance=True):
    t = copy.root / "examples/deckbuilder"
    if max_:
        edit(t / "gdd/mechanics.md", "    max: 3\n", "    max: 4\n")
    econ = t / "gdd/economy-balance.md"
    text = econ.read_text()
    block_start = text.index("  energy_per_turn:")
    block_end = text.index("\n  ", text.index("status:", block_start))
    block = text[block_start:block_end]
    if target:
        block = block.replace("target: 3", "target: 4")
    if tolerance:
        block = block.replace("tolerance: [3, 3]", "tolerance: [4, 4]")
    econ.write_text(text[:block_start] + block + text[block_end:])


def test_operating_good(tmp_path):
    copy = make_copy("operating_energy_budget", tmp_path)
    _raise_energy(copy)
    bump_core_version(copy, "examples/deckbuilder")
    rc, rep = check("operating_energy_budget", copy)
    assert rc == 0, rep


def test_operating_bad_missed_propagation(tmp_path):
    copy = make_copy("operating_energy_budget", tmp_path)
    _raise_energy(copy, target=False, tolerance=False)
    rc, rep = check("operating_energy_budget", copy)
    assert rc == 1 and failed(rep) == {"balance_targets.energy_per_turn_updated"}


def test_operating_bad_half_propagated(tmp_path):
    copy = make_copy("operating_energy_budget", tmp_path)
    _raise_energy(copy, tolerance=False)
    rc, rep = check("operating_energy_budget", copy)
    assert rc == 1 and failed(rep) == {"balance_targets.energy_per_turn_updated"}


def test_operating_bad_band_instead_of_hard_target(tmp_path):
    # The task text fixes the end state: still a hard target, so [4, 4].
    copy = make_copy("operating_energy_budget", tmp_path)
    _raise_energy(copy, tolerance=False)
    edit(copy.root / "examples/deckbuilder/gdd/economy-balance.md",
         "    tolerance: [3, 3]\n", "    tolerance: [3, 4]\n")
    rc, rep = check("operating_energy_budget", copy)
    assert rc == 1 and failed(rep) == {"balance_targets.energy_per_turn_updated"}


def test_operating_bad_retuned_unrelated_target(tmp_path):
    # "Change nothing that doesn't restate it": average_card_cost stays.
    copy = make_copy("operating_energy_budget", tmp_path)
    _raise_energy(copy)
    econ = copy.root / "examples/deckbuilder/gdd/economy-balance.md"
    text = econ.read_text()
    start = text.index("  average_card_cost:")
    old = text[start:text.index("target:", start) + len("target:")]
    tail = text[start + len(old):]
    value_end = tail.index("\n")
    econ.write_text(text[:start] + old + " 2.5" + tail[value_end:])
    rc, rep = check("operating_energy_budget", copy)
    assert rc == 1 and failed(rep) == {"no_unexpected_token_changes"}


def test_operating_bad_changed_card_schema(tmp_path):
    copy = make_copy("operating_energy_budget", tmp_path)
    _raise_energy(copy)
    edit(copy.root / "examples/deckbuilder/gdd/content/cards.md",
         "minimum: 0, maximum: 3 }", "minimum: 0, maximum: 4 }")
    rc, rep = check("operating_energy_budget", copy)
    assert rc == 1 and "subfile_frontmatter_valid" in failed(rep)


def test_maintenance_good(tmp_path):
    copy = make_copy("maintenance_drift", tmp_path)
    assert gdmd(copy, "touch", "examples/tick-combat/gdd/mechanics.md").returncode == 0
    bump_core_version(copy, "examples/tick-combat")
    rc, rep = check("maintenance_drift", copy)
    assert rc == 0, rep


def test_maintenance_bad_no_touch(tmp_path):
    copy = make_copy("maintenance_drift", tmp_path)
    rc, rep = check("maintenance_drift", copy)
    assert rc == 1 and failed(rep) == {"touched_exactly_affected_sections", "lint_clean"}


def test_maintenance_bad_touches_too_much(tmp_path):
    copy = make_copy("maintenance_drift", tmp_path)
    gdmd(copy, "touch", "examples/tick-combat/gdd/mechanics.md",
         "examples/tick-combat/gdd/loops.md")
    rc, rep = check("maintenance_drift", copy)
    assert rc == 1 and failed(rep) == {"touched_exactly_affected_sections"}


def test_maintenance_bad_edits_implementation(tmp_path):
    copy = make_copy("maintenance_drift", tmp_path)
    gdmd(copy, "touch", "examples/tick-combat/gdd/mechanics.md")
    edit(copy.root / "examples/tick-combat/impl/xtreme/src/rules.rs",
         "const GOLD_DROPS_PER_COMBAT: usize = 6;", "const GOLD_DROPS: usize = 6;")
    rc, rep = check("maintenance_drift", copy)
    assert rc == 1 and "implementation_untouched" in failed(rep)


def test_negative_control_good_untouched(tmp_path):
    copy = make_copy("negative_control_no_drift", tmp_path)
    rc, rep = check("negative_control_no_drift", copy)
    assert rc == 0, rep


@pytest.mark.parametrize("churn", ["touch", "version"])
def test_negative_control_bad_churn(tmp_path, churn):
    copy = make_copy("negative_control_no_drift", tmp_path)
    if churn == "touch":
        gdmd(copy, "touch", "examples/tick-combat/gdd/mechanics.md")
    else:
        bump_core_version(copy, "examples/tick-combat")
    rc, rep = check("negative_control_no_drift", copy)
    assert rc == 1 and failed(rep) == {"repository_unchanged"}


# ---- run.py: flag validation ------------------------------------------------------

FAKE_HELP = """\
Options:
  -p, --print                           Print response and exit
  --allowedTools, --allowed-tools <tools...>
                                        Comma or space-separated list; see
                                        also --max-turns in older versions
  --model <model>                       Model for the current session
"""


def test_listed_flags_reads_option_lines_not_descriptions():
    flags = dogfood_run.listed_flags(FAKE_HELP)
    assert flags == {"--print", "--allowedTools", "--allowed-tools", "--model"}
    assert dogfood_run.validate_flags(["claude", "-p", "--max-turns", "5", "--model", "x"],
                                      FAKE_HELP) == ["--max-turns"]


@pytest.mark.skipif(not dogfood_run.CLAUDE_BIN.is_file(), reason="pinned claude CLI not installed")
def test_session_and_probe_argv_flags_exist_in_installed_cli():
    help_text = dogfood_run.claude_help()
    argv = dogfood_run.session_argv("m", "high", "sid", "arm", 1.0)
    assert dogfood_run.validate_flags(argv, help_text) == []
    assert dogfood_run.validate_flags(dogfood_run.probe_argv("m"), help_text) == []


@pytest.mark.parametrize("stop, result, kw, want", [
    ("completed", {"subtype": "success"}, {}, "success"),
    ("completed", {"subtype": "success"}, {"checker_success": False}, "fail"),
    ("turn_cap", {}, {}, "capped"),
    ("timeout", {}, {"session_found": False}, "capped"),
    ("error:error_max_budget_usd", {"is_error": True}, {}, "capped"),
    ("error:error_during_execution", {"is_error": True}, {}, "error"),
    ("completed", {}, {}, "error"),                       # no result event
    ("completed", {"subtype": "success"}, {"session_found": False}, "error"),
    ("completed", {"subtype": "success"}, {"checker_parsed": False}, "error"),
])
def test_classify_outcomes(stop, result, kw, want):
    # (context_ok defaults to True; its failure is tested below)
    args = {"session_found": True, "checker_parsed": True, "checker_success": True, **kw}
    assert dogfood_run.classify(stop, result, **args) == want


def test_classify_context_failure_is_error():
    assert dogfood_run.classify("completed", {"subtype": "success"}, session_found=True,
                                checker_parsed=True, checker_success=True,
                                context_ok=False) == "error"


def test_session_argv_loads_claude_md_without_user_settings_or_memory():
    # D-025 amendment 1: --restricted also dropped CLAUDE.md and its @-imports.
    argv = dogfood_run.session_argv("m", "high", "sid", "arm", 1.0)
    assert "--restricted" not in argv
    assert argv[argv.index("--setting-sources") + 1] == "project,local"
    assert json.loads(argv[argv.index("--settings") + 1]) == {"autoMemoryEnabled": False}
    env = dogfood_run.session_env({})
    assert env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] == "1" and env["DISABLE_AUTOUPDATER"] == "1"


def test_session_context_reads_injected_context(tmp_path):
    from extract import session_context

    def write(records):
        f = tmp_path / f"s{len(list(tmp_path.iterdir()))}.jsonl"
        f.write_text("".join(json.dumps(r) + "\n" for r in records))
        return f
    snap = {"type": "attachment", "attachment": {"type": "prompt_snapshot",
            "systemPrompt": ["\nYou are an agent.\n", "# Memory\n\nYou have a memory at x"]}}
    asst = {"type": "assistant", "message": {"model": "claude-sonnet-5-5", "id": "m1"}}
    loaded = write([{"type": "attachment", "attachment": {"type": "instructions"}}, asst])
    assert dogfood_ctx(session_context(loaded)) == (True, False, ["claude-sonnet-5-5"])
    missing_with_memory = write([snap, asst])
    assert dogfood_ctx(session_context(missing_with_memory)) == (False, True,
                                                                ["claude-sonnet-5-5"])


def dogfood_ctx(c):
    return c["claude_md_loaded"], c["auto_memory_prompt"], c["assistant_models"]


def test_archive_sessions_outside_repo_with_member_hashes(tmp_path, monkeypatch):
    import tarfile
    monkeypatch.setattr(dogfood_run, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(dogfood_run, "ARCHIVE_DIR", tmp_path / "archive")
    sess = tmp_path / "results" / "sessions" / "r1"
    (sess / "views").mkdir(parents=True)
    (sess / "a.jsonl").write_text('{"x": 1}\n')
    (sess / "views" / "a.txt").write_text("view\n")
    info = dogfood_run.archive_sessions("r1")
    assert Path(info["archive"]).parent == tmp_path / "archive"
    assert set(info["members"]) == {"a.jsonl", "views/a.txt"}
    assert info["members"]["a.jsonl"] == dogfood_run.sha256(sess / "a.jsonl")
    with tarfile.open(info["archive"]) as tar:
        assert sorted(tar.getnames()) == ["r1/a.jsonl", "r1/views/a.txt"]
    recorded = json.loads((tmp_path / "results" / "r1" / "archive.json").read_text())
    assert recorded["sha256"] == dogfood_run.sha256(Path(info["archive"]))


def test_harness_dirty_ignores_results_only(tmp_path):
    marker = DOGFOOD / "results" / "_pytest_marker.jsonl"
    marker.write_text("{}\n")
    try:
        assert not any("_pytest_marker" in ln for ln in dogfood_run.harness_dirty())
    finally:
        marker.unlink()


# ---- extract.py on a synthetic session ------------------------------------------------

def _rec(kind, **msg):
    return {"type": kind, "message": msg, "uuid": msg.pop("_uuid", None), "timestamp":
            "2026-09-30T00:00:00Z"}


def test_extract_synthetic_session(tmp_path):
    from extract import extract, load_vcc
    try:
        vcc = load_vcc()
    except FileNotFoundError:
        pytest.skip("VCC.py not installed")
    usage1 = {"input_tokens": 10, "cache_creation_input_tokens": 1000,
              "cache_read_input_tokens": 0, "output_tokens": 5}
    usage2 = {"input_tokens": 20, "cache_creation_input_tokens": 50,
              "cache_read_input_tokens": 1000, "output_tokens": 7}
    read = lambda tid: {"type": "tool_use", "id": tid, "name": "Read",  # noqa: E731
                        "input": {"file_path": "/copy/gdd/loops.md"}}
    result = lambda tid, text: {"type": "tool_result", "tool_use_id": tid,  # noqa: E731
                                "content": text}
    recs = [
        {"type": "user", "message": {"role": "user", "content": "task"}},
        # turn 1 split across two records with the same message id
        _rec("assistant", id="m1", role="assistant", usage=usage1,
             content=[{"type": "text", "text": "reading"}]),
        _rec("assistant", id="m1", role="assistant", usage=usage1, content=[read("toolu_aaaaaa")]),
        {"type": "user", "message": {"role": "user",
                                     "content": [result("toolu_aaaaaa", "1→abc\n2→def")]}},
        _rec("assistant", id="m2", role="assistant", usage=usage2, content=[read("toolu_bbbbbb")]),
        {"type": "user", "message": {"role": "user",
                                     "content": [result("toolu_bbbbbb", "1→abc")]}},
    ]
    session = tmp_path / "s.jsonl"
    session.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    m = extract(session, vcc, Path("/copy"), tmp_path / "views")
    assert m["turns"] == 2
    assert m["per_turn_occupancy"] == [1010, 1070]
    assert m["tool_calls"] == 2 and m["files_read"] == 1 and m["re_reads"] == 1
    assert m["consultation_bytes"] == len("1→abc\n2→def".encode()) + len("1→abc".encode())
    assert m["output_tokens"] == 12
    assert m["out_of_copy_access"] == []
    assert all(d["vcc"] for d in m["tool_detail"])


def test_extract_flags_out_of_copy_bash_paths(tmp_path):
    from extract import extract, load_vcc
    try:
        vcc = load_vcc()
    except FileNotFoundError:
        pytest.skip("VCC.py not installed")
    usage = {"input_tokens": 1, "cache_creation_input_tokens": 0,
             "cache_read_input_tokens": 0, "output_tokens": 1}
    cmds = ["cat /copy/gdd/loops.md", "cat /home/x/repo/benchmark/dogfood/tasks/a.json",
            "grep -r energy ../other", "ls ~/secrets", "gdmd lint examples/deckbuilder 2>/dev/null"]
    recs = [{"type": "user", "message": {"role": "user", "content": "task"}}]
    for i, cmd in enumerate(cmds):
        tid = f"toolu_{i:06d}"
        recs.append({"type": "assistant", "message": {
            "id": f"m{i}", "role": "assistant", "usage": usage,
            "content": [{"type": "tool_use", "id": tid, "name": "Bash",
                         "input": {"command": cmd}}]}})
        recs.append({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tid, "content": "x"}]}})
    session = tmp_path / "s.jsonl"
    session.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    flagged = [e["path"] for e in extract(session, vcc, Path("/copy"),
                                          tmp_path / "views")["out_of_copy_access"]]
    assert flagged == ["/home/x/repo/benchmark/dogfood/tasks/a.json", "../other", "~/secrets"]
