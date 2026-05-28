"""game-design.md CLI: lint | diff | export | spec | verify | status.

Exit-code contract (spec §9):
  lint    : 0 if no errors, 1 otherwise.
  diff    : 0 if no balance_regressions or status_regressions, 1 otherwise.
  verify  : 0 if every non-presentation_usability target passed, 1 otherwise.
  status  : always 0 (informational; not a gate). See spec §9.6.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from game_design_md import __spec_version__, __version__
from game_design_md import diff_cmd, export_cmd, linter, spec_cmd, status_cmd, verify_cmd
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
def lint_cmd(path: Path) -> None:
    tree = Tree.load(path)
    result = linter.run_all(tree)
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


if __name__ == "__main__":
    main()
