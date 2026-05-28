"""game-design.md CLI: lint | diff | export | spec | verify | status | hook | touch | init.

Exit-code contract (spec §9):
  lint    : 0 if no errors, 1 otherwise.
  diff    : 0 if no balance_regressions or status_regressions, 1 otherwise.
  verify  : 0 if every non-presentation_usability target passed, 1 otherwise.
  status  : always 0 (informational; not a gate). See spec §9.6.
  hook    : always 0 (informational; not a gate). See spec §9.7 (Task 4 v0.3).
  touch   : always 0 (idempotent — no-op if last_verified already today).
  init    : 0 on success, 1 on usage/IO error. See spec §9.8 (Task 7 v0.3).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from game_design_md import __spec_version__, __version__
from game_design_md import (
    diff_cmd, export_cmd, hook_cmd, init_cmd, linter, spec_cmd, status_cmd,
    verify_cmd,
)
from game_design_md.tree import Tree


@click.group(
    help="game-design.md — lint, diff, export, print the spec, or verify.",
)
@click.version_option(__version__, prog_name="game-design.md")
def main() -> None:
    pass


@main.command("lint", help="Lint a game-design.md tree. Emits JSON to stdout.")
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True,
                                        path_type=Path))
@click.option("--stale-days", type=int, default=30, show_default=True,
              help="`stale-section`: max days impl source can be newer than "
                   "doc's `last_verified:` before warning.")
@click.option("--prototyped-stale-days", type=int, default=30, show_default=True,
              help="`prototyped-without-pointer`: tokens at status>=prototyped "
                   "without `implemented_in:` are flagged when file's "
                   "`last_verified:` exceeds this age.")
@click.option("--shipped-stale-days", type=int, default=180, show_default=True,
              help="`shipped-stale-doc`: files at status=shipped are flagged "
                   "when `last_verified:` exceeds this age.")
def lint_cmd(path: Path, stale_days: int, prototyped_stale_days: int,
             shipped_stale_days: int) -> None:
    tree = Tree.load(path)
    config = linter.LintConfig(
        stale_days=stale_days,
        prototyped_stale_days=prototyped_stale_days,
        shipped_stale_days=shipped_stale_days,
    )
    result = linter.run_all(tree, config=config)
    click.echo(json.dumps(result.to_dict(), indent=2))
    sys.exit(result.exit_code)


@main.command("diff", help="Diff two trees. Exit 1 on balance/status regression.")
@click.argument("old", type=click.Path(exists=True, file_okay=False, dir_okay=True,
                                       path_type=Path))
@click.argument("new", type=click.Path(exists=True, file_okay=False, dir_okay=True,
                                       path_type=Path))
def diff_cmd_entry(old: Path, new: Path) -> None:
    old_tree = Tree.load(old)
    new_tree = Tree.load(new)
    result = diff_cmd.diff_trees(old_tree, new_tree)
    click.echo(json.dumps(result, indent=2, default=str))
    regressed = bool(result["balance_regressions"]) or bool(result["status_regressions"])
    sys.exit(1 if regressed else 0)


@main.command("export", help="Export JSON Schema (--format schema) or flattened tokens (--format tokens).")
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True,
                                        path_type=Path), required=False)
@click.option("--format", "fmt",
              type=click.Choice(["schema", "tokens"]), default="tokens",
              help="schema = the JSON Schema; tokens = flat dotted-path JSON of the tree.")
def export_cmd_entry(path: Path | None, fmt: str) -> None:
    if fmt == "schema":
        click.echo(export_cmd.export_schema())
        return
    if path is None:
        raise click.UsageError("--format tokens requires a PATH to a tree")
    tree = Tree.load(path)
    click.echo(export_cmd.export_tokens(tree))


@main.command("spec", help="Print docs/spec.md to stdout (frontmatter stripped).")
def spec_cmd_entry() -> None:
    click.echo(spec_cmd.spec_text(), nl=False)


@main.command("verify",
              help="Invoke a project-supplied adapter once per verify_target "
                   "and compare trajectories against goldens. See spec §9.5.")
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True,
                                        path_type=Path))
@click.option("--adapter", "adapter_name", default="default",
              help="Adapter key under `adapters:` (defaults to 'default').")
def verify_cmd_entry(path: Path, adapter_name: str) -> None:
    tree = Tree.load(path)
    targets, adapters = verify_cmd.collect_config(tree)
    adapter_cmd = adapters.get(adapter_name)
    if not adapter_cmd:
        raise click.ClickException(
            f"no adapter '{adapter_name}' declared under `adapters:`. "
            f"Declare one in gdd/verification.md (or the core file) per spec §9.5.6."
        )
    if not targets:
        raise click.ClickException(
            "no verify_targets declared. Add at least one target under "
            "`verify_targets:` in gdd/verification.md."
        )
    try:
        adapter_path = verify_cmd.resolve_adapter(adapter_cmd, tree.root)
        result = verify_cmd.run_all(targets, adapter_path, tree.root)
    except verify_cmd.VerifyError as e:
        raise click.ClickException(str(e)) from e
    click.echo(json.dumps(result, indent=2))
    sys.exit(verify_cmd.evaluate(result))


@main.command("status",
              help="Project dashboard: status counts, staleness flags, "
                   "pointer health. Always exits 0 (informational). "
                   "See spec §9.6.")
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True,
                                        path_type=Path))
@click.option("--json", "as_json", is_flag=True, default=False,
              help="Emit machine-readable JSON instead of human-readable text.")
@click.option("--stale-days", type=int, default=90, show_default=True,
              help="Days threshold for `last_verified` staleness flag.")
@click.option("--shipped-stale-days", type=int, default=180, show_default=True,
              help="Days threshold for `status: shipped` staleness flag.")
def status_cmd_entry(path: Path, as_json: bool, stale_days: int,
                     shipped_stale_days: int) -> None:
    tree = Tree.load(path)
    report = status_cmd.status_report(
        tree, stale_days=stale_days, shipped_stale_days=shipped_stale_days,
    )
    if as_json:
        click.echo(json.dumps(report, indent=2, default=str))
    else:
        click.echo(status_cmd.render_human(report))


@main.group("hook",
            help="Anti-drift pre-commit hook commands (Task 4 v0.3). "
                 "Composes with the pre-commit framework via "
                 ".pre-commit-config.yaml. See spec §9.7.")
def hook_group() -> None:
    pass


@hook_group.command("check",
                    help="Pre-commit-invoked check: surface spec sections "
                         "that reference any staged code paths. Always "
                         "exits 0 (informational, not a gate).")
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True,
                                        path_type=Path))
@click.argument("staged_files", nargs=-1, required=False)
def hook_check_cmd(path: Path, staged_files: tuple[str, ...]) -> None:
    tree = Tree.load(path)
    matches = hook_cmd.check_staged(tree, list(staged_files))
    output = hook_cmd.render_hook_output(matches, tree_path=path)
    if output:
        click.echo(output)
    sys.exit(0)


@hook_group.command("install",
                    help="Install the gdmd anti-drift hook into "
                         ".pre-commit-config.yaml at the repo root. "
                         "Idempotent.")
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True,
                                        path_type=Path))
@click.option("--repo-root", type=click.Path(exists=True, file_okay=False,
                                              dir_okay=True, path_type=Path),
              default=None,
              help="Repo root where .pre-commit-config.yaml lives. Defaults "
                   "to the tree path (typical when the spec tree is the repo).")
def hook_install_cmd(path: Path, repo_root: Path | None) -> None:
    config_path, status = hook_cmd.install_hook(path, repo_root=repo_root)
    click.echo(f"{status} {config_path}")


@main.command("touch",
              help="Bump `last_verified:` of one or more subfiles to today's "
                   "date. Idempotent — no-op if already today. The bump "
                   "command paired with `gdmd hook check` forms the commit-"
                   "side of the bidirectional contract.")
@click.argument("paths", nargs=-1, required=True,
                type=click.Path(exists=True, file_okay=True, dir_okay=False,
                                path_type=Path))
def touch_cmd(paths: tuple[Path, ...]) -> None:
    for p in paths:
        try:
            bumped = hook_cmd.bump_last_verified(p)
        except ValueError as e:
            raise click.ClickException(str(e)) from e
        if bumped:
            click.echo(f"bumped {p}")
        else:
            click.echo(f"no change: {p}")
    sys.exit(0)


@main.command("init",
              help="Scaffold a new game-design.md tree from a per-genre "
                   "starter (Task 7 v0.3). Use --list to see available "
                   "genres. See spec §9.8.")
@click.argument("dest", type=click.Path(file_okay=False, dir_okay=True,
                                         path_type=Path), required=False)
@click.option("--genre", "genre",
              help="Genre name (deckbuilder | party-rpg | tcg | tick-combat "
                   "| platformer | survival). If omitted, prompts.")
@click.option("--list", "list_only", is_flag=True, default=False,
              help="List available genres and exit.")
def init_cmd_entry(dest: Path | None, genre: str | None,
                   list_only: bool) -> None:
    if list_only:
        click.echo(init_cmd.render_genre_list())
        sys.exit(0)
    if genre is None:
        available = init_cmd.list_genres()
        click.echo(init_cmd.render_genre_list())
        click.echo("")
        genre = click.prompt(
            "Genre", type=click.Choice(available, case_sensitive=False),
            show_choices=False,
        )
    if dest is None:
        dest = Path(".")
    try:
        out_path, n = init_cmd.copy_starter(genre, dest)
    except FileNotFoundError as e:
        raise click.UsageError(str(e)) from e
    except FileExistsError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"scaffolded {genre} starter ({n} files) at {out_path}")
    click.echo("")
    click.echo("Next steps:")
    click.echo(f"  cd {out_path}")
    click.echo("  gdmd lint .          # confirm the tree is green")
    click.echo("  # then make the tree your own — see the STARTER NOTE")
    click.echo("  # comment block in game-design.md for what to delete.")
    sys.exit(0)


if __name__ == "__main__":
    main()
