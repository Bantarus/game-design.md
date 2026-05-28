"""Tests for `gdmd hook check`, `gdmd touch`, and `gdmd hook install`
(Task 4 v0.3). The bidirectional anti-drift contract's commit-side."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from game_design_md import hook_cmd
from game_design_md.tree import Tree


_SUBFILE_WITH_IMPL = """\
---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: prototyped
last_verified: "2026-05-21"
implemented_in: ["src/loops/**/*.py"]
loops:
  main:
    timescale: moment
    duration: "1s"
    sequence: [{ do: "{verbs.do_thing}" }]
    intended_dynamics: ["test"]
    intended_aesthetics: [challenge]
    status: prototyped
    implemented_in: ["src/loops/main.py"]
---

## Tokens
"""


# ---- inverted index ----------------------------------------------------------

def test_inverted_index_picks_up_subfile_level_implemented_in(make_tree, tmp_path):
    """The subfile-level `implemented_in:` glob (NOT a per-token one) is
    walked and indexed at the `(file-level)` location."""
    root = make_tree({"gdd/loops.md": _SUBFILE_WITH_IMPL})
    impl = root / "src" / "loops" / "main.py"
    impl.parent.mkdir(parents=True, exist_ok=True)
    impl.write_text("# stub\n")
    tree = Tree.load(root)
    index = hook_cmd.build_inverted_index(tree)
    refs = index.get("src/loops/main.py", [])
    assert refs, f"expected ref to src/loops/main.py; index keys: {list(index.keys())[:10]}"
    assert any(r.location == "(file-level)" for r in refs)
    assert any(r.location == "loops.main" for r in refs)


def test_inverted_index_picks_up_per_token_implemented_in(make_tree):
    """Per-token `implemented_in:` globs are indexed at `<ns>.<tname>`."""
    mech = """\
---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: prototyped
last_verified: "2026-05-21"
entities:
  player:
    type: actor
    properties: { hp: 10 }
    status: prototyped
    implemented_in: ["src/entities/player.py"]
verbs:
  do_thing:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: system }
    effects: [{ kind: noop }]
    status: prototyped
    implemented_in: ["src/verbs/do_thing.py"]
resources:
  energy:
    scope: per_turn
    min: 0
    max: 3
    visibility: hud
    status: prototyped
    implemented_in: ["src/resources/energy.py"]
---

## Tokens
"""
    root = make_tree({"gdd/mechanics.md": mech})
    for rel in ("src/entities/player.py", "src/verbs/do_thing.py",
                "src/resources/energy.py"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# stub\n")
    tree = Tree.load(root)
    index = hook_cmd.build_inverted_index(tree)
    refs_player = index.get("src/entities/player.py", [])
    assert any(r.location == "entities.player" for r in refs_player)
    refs_verb = index.get("src/verbs/do_thing.py", [])
    assert any(r.location == "verbs.do_thing" for r in refs_verb)
    refs_res = index.get("src/resources/energy.py", [])
    assert any(r.location == "resources.energy" for r in refs_res)


def test_inverted_index_picks_up_implementation_pointers_map(make_tree):
    """The root file's `implementation_pointers:` map is indexed."""
    core = (make_tree() / "game-design.md").read_text()
    # The baseline already has a working core; we just need it to declare
    # an implementation_pointers map. Inject one.
    core_with_ip = core.replace(
        "core_loop_ref:",
        "implementation_pointers:\n  engine_a: \"src/engine_a/*.py\"\n"
        "core_loop_ref:",
    )
    root = make_tree({"game-design.md": core_with_ip})
    impl = root / "src" / "engine_a" / "main.py"
    impl.parent.mkdir(parents=True, exist_ok=True)
    impl.write_text("# stub\n")
    tree = Tree.load(root)
    index = hook_cmd.build_inverted_index(tree)
    refs = index.get("src/engine_a/main.py", [])
    assert any(r.location == "implementation_pointers.engine_a" for r in refs)
    assert any(r.file == "game-design.md" for r in refs)


# ---- check_staged ------------------------------------------------------------

def test_check_staged_empty_when_no_files_match(make_tree):
    """A staged file not referenced by any spec section produces no output."""
    root = make_tree()
    tree = Tree.load(root)
    matches = hook_cmd.check_staged(tree, ["nope/not/in/tree.py"])
    assert matches == {}


def test_check_staged_fires_on_referenced_file(make_tree, monkeypatch):
    """A staged file matching a real glob surfaces the spec section(s)."""
    root = make_tree({"gdd/loops.md": _SUBFILE_WITH_IMPL})
    impl = root / "src" / "loops" / "main.py"
    impl.parent.mkdir(parents=True, exist_ok=True)
    impl.write_text("# stub\n")
    tree = Tree.load(root)
    monkeypatch.chdir(root)
    matches = hook_cmd.check_staged(tree, ["src/loops/main.py"])
    assert "src/loops/main.py" in matches
    refs = matches["src/loops/main.py"]
    assert refs


def test_check_staged_handles_absolute_paths(make_tree):
    """Pre-commit harnesses that pass absolute paths still resolve correctly."""
    root = make_tree({"gdd/loops.md": _SUBFILE_WITH_IMPL})
    impl = root / "src" / "loops" / "main.py"
    impl.parent.mkdir(parents=True, exist_ok=True)
    impl.write_text("# stub\n")
    tree = Tree.load(root)
    matches = hook_cmd.check_staged(tree, [str(impl.resolve())])
    assert "src/loops/main.py" in matches


def test_check_staged_handles_repo_root_relative_paths(make_tree, tmp_path,
                                                       monkeypatch):
    """When pre-commit is invoked from repo root and the tree is a
    subdirectory, staged paths arrive as `<tree>/...`. Bridge that with
    CWD-relative resolution.

    We construct an isolated layout (NOT using make_tree's location)
    because make_tree uses tmp_path itself and we need a parent dir to
    play the repo role.
    """
    repo = tmp_path / "alt_repo"
    repo.mkdir()
    tree_root = repo / "spec-tree"
    tree_root.mkdir()
    # Build a minimal valid tree by hand using BASELINE_FILES verbatim.
    from .conftest import BASELINE_FILES
    for rel, content in BASELINE_FILES.items():
        p = tree_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    # Overlay the impl-pointing subfile + the actual file.
    (tree_root / "gdd" / "loops.md").write_text(_SUBFILE_WITH_IMPL)
    impl = tree_root / "src" / "loops" / "main.py"
    impl.parent.mkdir(parents=True, exist_ok=True)
    impl.write_text("# stub\n")
    tree = Tree.load(tree_root)
    monkeypatch.chdir(repo)
    matches = hook_cmd.check_staged(tree, ["spec-tree/src/loops/main.py"])
    assert "src/loops/main.py" in matches


# ---- render_hook_output ------------------------------------------------------

def test_render_hook_output_empty_when_no_matches():
    assert hook_cmd.render_hook_output({}) == ""


def test_render_hook_output_includes_touch_suggestion():
    matches = {
        "src/foo.py": [hook_cmd.Reference(file="gdd/mechanics.md", location="entities.player")],
    }
    out = hook_cmd.render_hook_output(matches, tree_path="examples/sample")
    assert "examples/sample/gdd/mechanics.md" in out
    assert "entities.player" in out
    assert "gdmd touch examples/sample/gdd/mechanics.md" in out


def test_render_hook_output_with_dot_tree_path_omits_prefix():
    matches = {
        "src/foo.py": [hook_cmd.Reference(file="gdd/mechanics.md", location="entities.player")],
    }
    out = hook_cmd.render_hook_output(matches, tree_path=".")
    # No "./" prefix; raw tree-relative
    assert "gdd/mechanics.md" in out
    assert "./gdd/mechanics.md" not in out


# ---- bump_last_verified ------------------------------------------------------

def test_bump_last_verified_modifies_old_date(tmp_path):
    f = tmp_path / "sub.md"
    f.write_text("""---
spec: game-design.md
file_type: subfile
status: prototyped
last_verified: "2026-01-15"
---

body
""")
    today = date(2026, 5, 28)
    result = hook_cmd.bump_last_verified(f, today=today)
    assert result is True
    assert 'last_verified: "2026-05-28"' in f.read_text()


def test_bump_last_verified_idempotent_when_already_today(tmp_path):
    today = date(2026, 5, 28)
    f = tmp_path / "sub.md"
    f.write_text(f"""---
spec: game-design.md
file_type: subfile
status: prototyped
last_verified: "2026-05-28"
---

body
""")
    before = f.stat().st_mtime
    result = hook_cmd.bump_last_verified(f, today=today)
    assert result is False
    # Idempotent: no write, mtime stable.
    after = f.stat().st_mtime
    assert before == after


def test_bump_last_verified_preserves_quoting_style(tmp_path):
    """Unquoted dates stay unquoted; quoted dates stay quoted."""
    today = date(2026, 5, 28)

    f_q = tmp_path / "quoted.md"
    f_q.write_text("""---
last_verified: "2026-01-15"
---
""")
    hook_cmd.bump_last_verified(f_q, today=today)
    assert 'last_verified: "2026-05-28"' in f_q.read_text()

    f_u = tmp_path / "unquoted.md"
    f_u.write_text("""---
last_verified: 2026-01-15
---
""")
    hook_cmd.bump_last_verified(f_u, today=today)
    text = f_u.read_text()
    assert "last_verified: 2026-05-28" in text
    assert 'last_verified: "2026-05-28"' not in text  # not quoted


def test_bump_last_verified_no_field_returns_false(tmp_path):
    """File has frontmatter but no last_verified field — no-op, returns False."""
    f = tmp_path / "sub.md"
    f.write_text("""---
spec: game-design.md
file_type: subfile
status: draft
---

body
""")
    result = hook_cmd.bump_last_verified(f)
    assert result is False


def test_bump_last_verified_no_frontmatter_raises(tmp_path):
    f = tmp_path / "broken.md"
    f.write_text("no frontmatter here\n")
    with pytest.raises(ValueError):
        hook_cmd.bump_last_verified(f)


def test_bump_last_verified_unclosed_frontmatter_raises(tmp_path):
    f = tmp_path / "broken.md"
    f.write_text("---\nspec: game-design.md\nstatus: draft\n")  # no closing ---
    with pytest.raises(ValueError):
        hook_cmd.bump_last_verified(f)


# ---- install_hook ------------------------------------------------------------

def test_install_hook_creates_config(tmp_path):
    """First invocation creates `.pre-commit-config.yaml` with the gdmd hook."""
    repo = tmp_path / "repo"
    tree = repo / "spec-tree"
    tree.mkdir(parents=True)
    path, status = hook_cmd.install_hook(tree, repo_root=repo)
    assert status == "created"
    assert path == repo / ".pre-commit-config.yaml"
    config = yaml.safe_load(path.read_text())
    # gdmd hook present under repos[?] -> hooks[?]
    assert any(
        any(h.get("id") == "gdmd-anti-drift" for h in r.get("hooks", []))
        for r in config.get("repos", [])
    )


def test_install_hook_idempotent_when_already_present(tmp_path):
    repo = tmp_path / "repo"
    tree = repo / "spec-tree"
    tree.mkdir(parents=True)
    path, status1 = hook_cmd.install_hook(tree, repo_root=repo)
    assert status1 == "created"
    mtime_before = path.stat().st_mtime

    # Second call: status "unchanged", file untouched.
    path2, status2 = hook_cmd.install_hook(tree, repo_root=repo)
    assert path2 == path
    assert status2 == "unchanged"
    mtime_after = path.stat().st_mtime
    assert mtime_before == mtime_after


def test_install_hook_updates_existing_config(tmp_path):
    """If a config exists without our hook, we add ours without clobbering."""
    repo = tmp_path / "repo"
    tree = repo / "spec-tree"
    tree.mkdir(parents=True)
    config_path = repo / ".pre-commit-config.yaml"
    config_path.write_text(yaml.safe_dump({
        "repos": [
            {"repo": "https://github.com/example/other",
             "rev": "v1.0.0",
             "hooks": [{"id": "other-hook"}]},
        ]
    }))

    path, status = hook_cmd.install_hook(tree, repo_root=repo)
    assert status == "updated"
    config = yaml.safe_load(path.read_text())
    repos = config["repos"]
    # The pre-existing third-party hook entry is preserved.
    assert any(r.get("repo") == "https://github.com/example/other" for r in repos)
    # Our local hook entry is appended.
    local_repos = [r for r in repos if r.get("repo") == "local"]
    assert local_repos, "expected local repo entry for gdmd hook"
    assert any(h.get("id") == "gdmd-anti-drift" for h in local_repos[0]["hooks"])


def test_install_hook_entry_uses_tree_relative_path(tmp_path):
    """The hook entry command embeds the tree path so pre-commit invokes
    `gdmd hook check <tree>` with the right tree."""
    repo = tmp_path / "repo"
    tree = repo / "examples" / "sample-tree"
    tree.mkdir(parents=True)
    path, _ = hook_cmd.install_hook(tree, repo_root=repo)
    config = yaml.safe_load(path.read_text())
    local_hooks = next(r for r in config["repos"] if r.get("repo") == "local")["hooks"]
    gdmd_entry = next(h for h in local_hooks if h["id"] == "gdmd-anti-drift")
    assert gdmd_entry["entry"] == "gdmd hook check examples/sample-tree"
    assert gdmd_entry["language"] == "system"
    assert gdmd_entry["pass_filenames"] is True
