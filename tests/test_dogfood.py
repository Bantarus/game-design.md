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
import re
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


def test_views_arm_is_the_spec_9_9_command_reference():
    # D-027 / review item 7: a neutral reference derived from §9.9, with
    # exactly the flags of §9.9's synopsis, no more and no fewer.
    import re
    spec = (REPO / "docs" / "spec.md").read_text()
    sec = spec[spec.index("### 9.9 "):]
    synopsis = sec[sec.index("```") + 3:]
    synopsis = synopsis[:synopsis.index("```")]
    flag = re.compile(r"--[a-z][a-z-]*")
    appended = (DOGFOOD / "arms" / "views.md").read_text()[
        len((DOGFOOD / "arms" / "baseline.md").read_text()):]
    assert set(flag.findall(appended)) == set(flag.findall(synopsis))
    for word in ("prefer", "instead of", "should"):
        assert word not in appended.lower(), f"arm text steers: {word!r}"


def test_views_arm_bytes_are_the_pinned_bytes():
    # D-025 amendment 4: editing arms/views.md needs a new amendment and pin.
    import hashlib
    data = (DOGFOOD / "arms" / "views.md").read_bytes()
    assert hashlib.sha256(data).hexdigest() == dogfood_run.ARM_PIN_SHA256["views"]
    assert dogfood_run.load_arm("views") == data.decode("utf-8")


def test_load_arm_refuses_a_changed_pinned_arm(tmp_path, monkeypatch):
    arms = tmp_path / "arms"
    shutil.copytree(DOGFOOD / "arms", arms)
    (arms / "views.md").write_text((arms / "views.md").read_text() + "\nPrefer views.\n")
    monkeypatch.setattr(fixture, "ARMS_DIR", arms)
    with pytest.raises(SystemExit, match="pinned SHA-256"):
        dogfood_run.load_arm("views")
    assert dogfood_run.load_arm("baseline")   # unpinned arms load as before


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




@pytest.mark.v03_world(venv=True)
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
spec_version: ROOT_SPEC_VERSION
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
    """The checker wants the card's spec_version to equal the tree root's, so the
    known-good card takes it from the copy (it read a fixed 0.3.0 until v0.4.0)."""
    root = (copy.root / "examples/deckbuilder/game-design.md").read_text()
    version = re.search(r"(?m)^spec_version:\s*(\S+)", root).group(1)
    (copy.root / "examples/deckbuilder/content/cards/kindle.yaml").write_text(
        text.replace("ROOT_SPEC_VERSION", version))


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
    (lambda t: t.replace("ROOT_SPEC_VERSION", "0.0.1"), "entity_header"),
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


@pytest.mark.parametrize("command, cwd, want_read, want_paths, want_cwd", [
    # D-025 amendment 3: Bash reads (non-gating secondaries)
    ("cat a.yaml b.yaml", "/c", True, ["/c/a.yaml", "/c/b.yaml"], "/c"),
    ("cd x && head -40 g.md; sed -n 1,20p y.md", "/c", True, ["/c/x/g.md", "/c/x/y.md"], "/c/x"),
    ("head -n 5 a.md", "/c", True, ["/c/a.md"], "/c"),
    ('grep -rniE "a|b" gdd/ | grep -v "^./c"', "/c", True, ["/c/gdd"], "/c"),
    ("grep -n 'x' -A 25 m.md | head -60", "/c", True, ["/c/m.md"], "/c"),
    ("ls content | head -30", "/c", False, [], "/c"),                  # pipe-fed head
    ("cat > k.yaml <<'EOF'\nid: x\nname: \"a|b\"\nEOF", "/c", False, [], "/c"),  # write
    ("sed -i 's/a/b/' x.md", "/c", False, [], "/c"),                 # write
    ("git show HEAD | head -200", "/c", True, [], "/c"),
    ("gdmd lint . 2>&1 | tail -5", "/c", False, [], "/c"),
    ("cd ../..; gdmd touch a.md", "/c/x/y", False, [], "/c"),
])
def test_bash_reads(command, cwd, want_read, want_paths, want_cwd):
    from extract import bash_reads
    assert bash_reads(command, cwd) == (want_read, want_paths, want_cwd)


@pytest.mark.parametrize("command,want", [
    ("gdmd view examples/deckbuilder", "overview"),
    ("gdmd view t --flat --role token --json", "overview"),
    ("gdmd view t --full | head -50", "full"),
    ('gdmd view t --grep "energy|mana" --ignore-case', "grep"),
    (".venv/bin/gdmd view t --grep=x", "grep"),
    ("gdmd view t --ref {resources.energy} --hops 2", "ref"),
    ("gdmd graph t --impact {x.y}", "graph"),
    ("uv run gdmd graph t --cycles --format dot", "graph"),
    ("PATH=/x:$PATH timeout 30 gdmd view t", "overview"),
    ("game-design.md view t --full", "full"),
    ("gdmd view --help", "other"),
    ("gdmd graph t --help", "other"),
    ("cd examples && gdmd view deckbuilder --grep x", "grep"),
    ("gdmd view t; gdmd graph t", "mixed"),
    # D-026 amendment 2: the command word may follow a shell keyword
    ('for v in a b; do gdmd view . --ref "{verbs.$v}" | sed -n 1,25p; done', "ref"),
    ("if true; then gdmd view t --full; fi", "full"),
    ("if false; then :; else gdmd graph t --cycles; fi", "graph"),
    ("( cd t && gdmd view . --grep x )", "grep"),
    ("{ gdmd view t; }", "overview"),
    ('grep -rn "gdmd view" docs', None),       # quoted: a pattern, not a command
    ("echo gdmd view", None),
    ("gdmd lint t", None),
])
def test_view_mode(command, want):
    # D-025 amendment 5: consultation bytes by view mode (non-gating).
    from extract import view_mode
    assert view_mode(command) == want


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


def test_extract_bash_reads_across_calls(tmp_path):
    # D-025 amendment 3: cwd persists across Bash calls; errored calls don't
    # read; Read and Bash reads share one copy-relative path space.
    from extract import extract, load_vcc
    try:
        vcc = load_vcc()
    except FileNotFoundError:
        pytest.skip("VCC.py not installed")
    usage = {"input_tokens": 1, "cache_creation_input_tokens": 0,
             "cache_read_input_tokens": 0, "output_tokens": 1}

    def turn(mid, tid, name, inp, text, err=False):
        return [_rec("assistant", id=mid, role="assistant", usage=usage,
                     content=[{"type": "tool_use", "id": tid, "name": name, "input": inp}]),
                {"type": "user", "message": {"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": tid, "content": text,
                     "is_error": err}]}}]
    recs = [{"type": "user", "message": {"role": "user", "content": "task"}},
            *turn("m1", "toolu_aaaaa1", "Bash", {"command": "cd gdd && cat loops.md"}, "L1"),
            *turn("m2", "toolu_aaaaa2", "Bash", {"command": "head -5 loops.md"}, "L1"),
            *turn("m3", "toolu_aaaaa3", "Read", {"file_path": "/copy/gdd/mechanics.md"}, "M"),
            *turn("m4", "toolu_aaaaa4", "Bash", {"command": "cat x.md"}, "denied", err=True)]
    session = tmp_path / "s.jsonl"
    session.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    m = extract(session, vcc, Path("/copy"), tmp_path / "views")
    assert (m["bash_read_calls"], m["bash_read_bytes"], m["bash_files_read"]) == (2, 4, 1)
    assert m["all_files_read_paths"] == ["gdd/loops.md", "gdd/mechanics.md"]
    assert (m["all_files_read"], m["all_re_reads"]) == (2, 1)
    assert (m["files_read"], m["re_reads"]) == (1, 0)          # Read-only secondaries unchanged
    assert m["view_mode_bytes"] == {} and m["view_mode_calls"] == {}


def test_extract_view_mode_bytes(tmp_path):
    # D-025 amendment 5: each view call's full result bytes, errors included
    # (as in the primary), go to its mode; other calls are not attributed.
    from extract import extract, load_vcc
    try:
        vcc = load_vcc()
    except FileNotFoundError:
        pytest.skip("VCC.py not installed")
    usage = {"input_tokens": 1, "cache_creation_input_tokens": 0,
             "cache_read_input_tokens": 0, "output_tokens": 1}
    calls = [("gdmd view t", "o" * 10, False), ("gdmd view t --full", "f" * 100, False),
             ("gdmd view t --grep x", "g" * 7, False), ("gdmd view t --grep y", "g" * 3, False),
             ("gdmd graph t --impact {a.b}", "does not resolve", True),
             ("cat gdd/loops.md", "c" * 50, False)]
    recs = [{"type": "user", "message": {"role": "user", "content": "task"}}]
    for i, (cmd, text, err) in enumerate(calls):
        tid = f"toolu_{i:06d}"
        recs += [_rec("assistant", id=f"m{i}", role="assistant", usage=usage,
                      content=[{"type": "tool_use", "id": tid, "name": "Bash",
                                "input": {"command": cmd}}]),
                 {"type": "user", "message": {"role": "user", "content": [
                     {"type": "tool_result", "tool_use_id": tid, "content": text,
                      "is_error": err}]}}]
    session = tmp_path / "s.jsonl"
    session.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    m = extract(session, vcc, Path("/copy"), tmp_path / "views")
    assert m["view_mode_bytes"] == {"overview": 10, "full": 100, "grep": 10, "graph": 16}
    assert m["view_mode_calls"] == {"overview": 1, "full": 1, "grep": 2, "graph": 1}
    assert m["consultation_bytes"] == 10 + 100 + 10 + 16 + 50


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


# ---- analyze.py: the Rule V verdict as D-025 locks it (amendment 5) ---------------

TASK_IDS = ("authoring_new_card", "lookup_refs", "maintenance_drift",
            "negative_control_no_drift", "operating_energy_budget")


def _lines(bytes_by_arm, fail=(), run_id="m", repeats=(1, 2, 3), outcome_over=None,
           views_calls=2):
    """Synthetic result lines: every cell succeeds unless listed in `fail`."""
    out = []
    for t in TASK_IDS:
        for arm in ("baseline", "views"):
            for r in repeats:
                o = "fail" if (t, arm, r) in fail else "success"
                if outcome_over and (t, arm, r) in outcome_over:
                    o = outcome_over[(t, arm, r)]
                out.append({"run_id": run_id, "cell_id": f"{t}__{arm}__r{r}", "task_id": t,
                            "arm": arm, "repeat": r, "outcome": o,
                            "consultation_bytes": bytes_by_arm[arm],
                            "gdmd_view_calls": views_calls if arm == "views" else 0,
                            "gdmd_graph_calls": 0, "supersedes": None})
    return out


def _rule_v(lines):
    import analyze
    return analyze.rule_v(lines, metrics_loader=lambda ln: None)


def test_rule_v_pass_fail_null_by_R():
    assert _rule_v(_lines({"baseline": 1000, "views": 600}))["verdict"] == "PASS"   # R = 0.4
    res = _rule_v(_lines({"baseline": 1000, "views": 800}))                         # R = 0.2
    assert res["verdict"] == "NULL" and res["R"] == pytest.approx(0.2)
    assert _rule_v(_lines({"baseline": 1000, "views": 1000}))["verdict"] == "FAIL"  # R = 0


def test_rule_v_zero_baseline_rule():
    import analyze
    res = analyze.rule_v(_lines({"baseline": 0, "views": 0}), metrics_loader=lambda ln: None)
    assert all(d["r_t"] == 0.0 for d in res["per_task"].values())
    res = analyze.rule_v(_lines({"baseline": 0, "views": 5}), metrics_loader=lambda ln: None)
    assert all(d["r_t"] == -1.0 for d in res["per_task"].values())


def test_rule_v_non_inferiority_clause_1():
    one = {("lookup_refs", "views", 1)}
    two = one | {("authoring_new_card", "views", 2)}
    assert _rule_v(_lines({"baseline": 1000, "views": 600}, fail=one))["verdict"] == "PASS"
    res = _rule_v(_lines({"baseline": 1000, "views": 600}, fail=two))
    assert res["verdict"] == "FAIL" and "non-inferiority clause 1 violated" in res["reasons"]


def test_rule_v_guarded_extension_trigger_and_resolution():
    fail = {("maintenance_drift", "views", 2)}             # e_t = 1 on a guarded task
    main = _lines({"baseline": 1000, "views": 600}, fail=fail)
    assert _rule_v(main)["verdict"].startswith("PENDING")
    ext_ok = _lines({"baseline": 1000, "views": 600}, run_id="ext", repeats=(4, 5))
    ext_ok = [ln for ln in ext_ok if ln["task_id"] in ("maintenance_drift",
                                                       "negative_control_no_drift")]
    assert _rule_v(main + ext_ok)["verdict"] == "NULL"     # e_t stays 1 over r1-5
    ext_base_fails = [dict(ln, outcome="fail") if (ln["task_id"], ln["arm"], ln["repeat"])
                      == ("maintenance_drift", "baseline", 4) else ln for ln in ext_ok]
    assert _rule_v(main + ext_base_fails)["verdict"] == "PASS"   # e_t = 0 over r1-5
    two = fail | {("maintenance_drift", "views", 3)}
    res = _rule_v(_lines({"baseline": 1000, "views": 600}, fail=two))
    assert res["verdict"] == "FAIL" and "maintenance_drift: e_t >= 2" in res["reasons"]


def test_rule_v_apparatus_nulls_and_supersedes():
    errs = {(t, "views", 1): "error" for t in TASK_IDS[:4]}   # 4/30 > 10%
    res = _rule_v(_lines({"baseline": 1000, "views": 600}, outcome_over=errs))
    assert res["verdict"] == "NULL (apparatus)"
    lines = _lines({"baseline": 1000, "views": 600}, outcome_over=errs)
    reruns = [{**ln, "run_id": "rr", "outcome": "success",
               "supersedes": f"m/{ln['cell_id']}"} for ln in lines if ln["outcome"] == "error"]
    assert _rule_v(lines + reruns)["verdict"] == "PASS"
    res = _rule_v(_lines({"baseline": 1000, "views": 600}, views_calls=0))
    assert res["verdict"] == "NULL (apparatus)"
    assert "manipulation check" in res["reasons"][0]


def test_rule_v_contamination_is_not_success_and_listed():
    import analyze
    lines = _lines({"baseline": 1000, "views": 600})
    leak = {"out_of_copy_access": [{"tool": "Bash",
                                    "path": "/home/u/game-design/benchmark/dogfood/tasks/x"}]}
    hit = ("lookup_refs", "views", 1)
    res = analyze.rule_v(lines, metrics_loader=lambda ln: leak if (
        ln["task_id"], ln["arm"], ln["repeat"]) == hit else None)
    assert res["apparatus"]["contaminated"] == {"lookup_refs/views/r1": [
        "/home/u/game-design/benchmark/dogfood/tasks/x"]}
    assert res["non_inferiority"]["successes"]["views"] == 14


# ---- Rule C cell construction (D-025, D-024 §3) and analyze.rule_c ---------------

def test_the_judge_carries_the_schema_lint_reads(tmp_path):
    """D-034: lint validates against schema/game-design.schema.json, so a judge
    exported with `src/` alone would crash on every tree."""
    judge = fixture.make_judge(tmp_path / "judge", "HEAD")
    assert (tmp_path / "judge/schema/game-design.schema.json").is_file()
    proc = subprocess.run([str(judge), "lint", str(fixture.REPO_ROOT / "examples/deckbuilder")],
                          capture_output=True, text=True)
    assert proc.returncode == 0 and json.loads(proc.stdout)["summary"]["errors"] == 0


def test_import_card_copy_swaps_only_the_spec_import_in_the_baseline_commit(tmp_path):
    from game_design_md import spec_cmd
    card = fixture.prepare_copy(TASKS["maintenance_drift"], tmp_path / "card", card=True)
    full = fixture.prepare_copy(TASKS["maintenance_drift"], tmp_path / "full")
    cm_card = (card.root / "CLAUDE.md").read_text()
    cm_full = (full.root / "CLAUDE.md").read_text()
    assert fixture.CARD_IMPORT_LINE in cm_card and fixture.SPEC_IMPORT_LINE not in cm_card
    assert cm_card.replace(fixture.CARD_IMPORT_LINE, fixture.SPEC_IMPORT_LINE) == cm_full
    assert full.card_sha is None
    # D-026 amendment 4: the repo commits the card since the adoption, but an
    # import-full copy carries no card file (its cell doesn't import it).
    assert (REPO / "docs/spec-card.md").is_file()
    assert not (full.root / "docs/spec-card.md").exists()
    # the card is the copy's own `gdmd spec --card` over the copy's own spec
    spec = spec_cmd._FENCE_RE.sub("", (card.root / "docs/spec.md").read_text(), count=1).lstrip()
    assert (card.root / "docs/spec-card.md").read_text() == spec_cmd.card(spec)
    import hashlib
    assert card.card_sha == hashlib.sha256(spec_cmd.card(spec).encode()).hexdigest()
    # part of the fixture's baseline commit, so no checker sees it as an edit
    status = subprocess.run(["git", "status", "--porcelain"], cwd=card.root,
                            capture_output=True, text=True).stdout
    assert "CLAUDE.md" not in status and "spec-card.md" not in status
    # an untouched copy passes the negative control in the card cell too: the
    # swap is not a change the subject made
    neg = fixture.prepare_copy(TASKS["negative_control_no_drift"], tmp_path / "neg", card=True)
    rc, report = check("negative_control_no_drift", neg)
    assert rc == 0 and not failed(report), report


@pytest.mark.v03_world
def test_card_swap_refuses_the_v03_world(tmp_path):
    with pytest.raises(fixture.FixtureError, match="matrix world"):
        fixture.prepare_copy(TASKS["lookup_refs"], tmp_path / "c", world="v0.3", card=True)


def test_rule_c_arms_use_the_baseline_text_in_the_matrix_world():
    assert dogfood_run.ARM_WORLD["import-full"] == dogfood_run.ARM_WORLD["import-card"] == "matrix"
    base = dogfood_run.load_arm("baseline")
    assert dogfood_run.load_arm("import-full") == dogfood_run.load_arm("import-card") == base


def _c_lines(occ_by_arm, fail=(), run_id="c", repeats=(1, 2, 3), outcome_over=None,
             section_calls=0):
    out = []
    for t in TASK_IDS:
        for arm in ("import-full", "import-card"):
            for r in repeats:
                o = "fail" if (t, arm, r) in fail else "success"
                if outcome_over and (t, arm, r) in outcome_over:
                    o = outcome_over[(t, arm, r)]
                out.append({"run_id": run_id, "cell_id": f"{t}__{arm}__r{r}", "task_id": t,
                            "arm": arm, "repeat": r, "outcome": o,
                            "median_turn_occupancy": occ_by_arm[arm], "est_cost_usd": 0.4,
                            "gdmd_spec_section_calls": section_calls if arm == "import-card"
                            else 0, "supersedes": None})
    return out


def _rule_c(lines, delta=50_000, **kw):
    import analyze
    return analyze.rule_c(lines, delta, metrics_loader=lambda ln: None, **kw)


def test_rule_c_verdicts():
    full = 80_000
    assert _rule_c(_c_lines({"import-full": full, "import-card": full - 30_000}))["verdict"] \
        == "PASS"                                                   # D = 30k >= 25k
    res = _rule_c(_c_lines({"import-full": full, "import-card": full - 20_000}))
    assert res["verdict"] == "NULL" and res["D"] == 20_000         # D < 0.5 x delta
    two = {("lookup_refs", "import-card", 1), ("authoring_new_card", "import-card", 2)}
    res = _rule_c(_c_lines({"import-full": full, "import-card": full - 30_000}, fail=two))
    assert res["verdict"] == "FAIL"
    one = {("negative_control_no_drift", "import-card", 1)}
    assert _rule_c(_c_lines({"import-full": full, "import-card": full - 30_000},
                            fail=one))["verdict"].startswith("PENDING")
    errs = {(t, "import-card", 1): "error" for t in TASK_IDS[:4]}
    assert _rule_c(_c_lines({"import-full": full, "import-card": full - 30_000},
                            outcome_over=errs))["verdict"] == "NULL (apparatus)"
    assert _rule_c(_c_lines({"import-full": full, "import-card": full - 30_000}),
                   precondition_met=False)["verdict"] == "NULL"


def test_rule_c_ignores_rule_v_lines_and_reports_section_calls():
    lines = _c_lines({"import-full": 80_000, "import-card": 50_000}, section_calls=2) + \
        _lines({"baseline": 1000, "views": 600})
    res = _rule_c(lines)
    assert res["n_main"] == 30 and res["verdict"] == "PASS"
    assert res["secondaries"]["section_calls_total"] == 30
    assert res["per_task"]["lookup_refs"]["d_t_over_delta"] == pytest.approx(0.6)


def test_extract_counts_spec_section_calls(tmp_path):
    from extract import extract, load_vcc
    try:
        vcc = load_vcc()
    except FileNotFoundError:
        pytest.skip("VCC.py not installed")
    usage = {"input_tokens": 1, "cache_creation_input_tokens": 0,
             "cache_read_input_tokens": 0, "output_tokens": 1}
    cmds = ["gdmd spec --section 4.8", "gdmd spec --card | head", "gdmd spec --section 3; ls"]
    recs = [{"type": "user", "message": {"role": "user", "content": "task"}}]
    for i, cmd in enumerate(cmds):
        tid = f"toolu_{i:06d}"
        recs += [_rec("assistant", id=f"m{i}", role="assistant", usage=usage,
                      content=[{"type": "tool_use", "id": tid, "name": "Bash",
                                "input": {"command": cmd}}]),
                 {"type": "user", "message": {"role": "user", "content": [
                     {"type": "tool_result", "tool_use_id": tid, "content": "x"}]}}]
    session = tmp_path / "s.jsonl"
    session.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    assert extract(session, vcc, Path("/copy"), tmp_path / "v")["gdmd_spec_section_calls"] == 2


def test_force_spec_import(tmp_path):
    # D-026 / D-024 §4: matrix copies start from the full import even after
    # the repo's CLAUDE.md adopts the card.
    cm = tmp_path / "CLAUDE.md"
    cm.write_text("# x\n" + fixture.CARD_IMPORT_LINE + "\n- Schema: @schema/x.json\n")
    fixture.force_spec_import(tmp_path)
    assert cm.read_text() == "# x\n" + fixture.SPEC_IMPORT_LINE + "\n- Schema: @schema/x.json\n"
    fixture.force_spec_import(tmp_path)                      # idempotent
    assert fixture.SPEC_IMPORT_LINE in cm.read_text()
    cm.write_text("# no import line\n")
    with pytest.raises(fixture.FixtureError, match="exactly one"):
        fixture.force_spec_import(tmp_path)
    cm.write_text(fixture.SPEC_IMPORT_LINE + "\n" + fixture.CARD_IMPORT_LINE + "\n")
    with pytest.raises(fixture.FixtureError, match="exactly one"):
        fixture.force_spec_import(tmp_path)


def test_matrix_copies_import_the_full_spec(tmp_path):
    for task in ("lookup_refs", "maintenance_drift"):
        c = fixture.prepare_copy(TASKS[task], tmp_path / task)
        assert (c.root / "CLAUDE.md").read_text().count(fixture.SPEC_IMPORT_LINE) == 1


def test_ref_is_for_probes_only():
    with pytest.raises(SystemExit):
        dogfood_run.main(["--ref", "HEAD", "--dry-run"])


def test_only_import_card_copies_carry_the_card_file(tmp_path):
    """D-026 amendment 4: the card file exists only where the cell imports it.
    Matrix-world copies (views, import-full, and the probes' copies) drop it;
    the v0.3-world copy is tested below, where the venv exists."""
    task = TASKS["lookup_refs"]
    for arm in ("views", "import-full", "import-card"):
        c = fixture.prepare_copy(task, tmp_path / arm, world=dogfood_run.ARM_WORLD[arm],
                                 card=arm in dogfood_run.CARD_ARMS)
        tracked = fixture.git(c.root, "ls-files", "docs").splitlines()
        imports_card = fixture.CARD_IMPORT_LINE in (c.root / "CLAUDE.md").read_text()
        assert ("docs/spec-card.md" in tracked) == imports_card == (arm == "import-card"), arm
        assert (c.root / "docs/spec-card.md").exists() == imports_card, arm


@pytest.mark.v03_world(venv=True)
def test_v03_world_copy_has_no_card_file(tmp_path):
    c = fixture.prepare_copy(TASKS["lookup_refs"], tmp_path / "b",
                             world=dogfood_run.ARM_WORLD["baseline"])
    assert c.world == "v0.3"
    assert not (c.root / "docs/spec-card.md").exists()
    # the v0.3 CLAUDE.md imports the full spec and nothing else of docs/
    assert fixture.SPEC_IMPORT_LINE in (c.root / "CLAUDE.md").read_text()
    assert "spec-card" not in (c.root / "CLAUDE.md").read_text()
