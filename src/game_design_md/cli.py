"""game-design.md CLI: lint | diff | export | spec | verify.

Exit-code contract (spec §9):
  lint    : 0 if no errors, 1 otherwise.
  diff    : 0 if no balance_regressions or status_regressions, 1 otherwise.
  verify  : 0 if every non-presentation_usability target passed, 1 otherwise.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from game_design_md import __spec_version__, __version__
from game_design_md import diff_cmd, export_cmd, linter, spec_cmd, verify_cmd
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
              help="EXPERIMENTAL (v0.1.1). Invoke a project-supplied adapter "
                   "and validate its VerifyResult JSON.")
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True,
                                        path_type=Path))
@click.option("--adapter", "adapter_name", default="default",
              help="Adapter key under `adapters:` (defaults to 'default').")
def verify_cmd_entry(path: Path, adapter_name: str) -> None:
    tree = Tree.load(path)
    targets, adapters = verify_cmd.collect_config(tree)
    adapter = adapters.get(adapter_name)
    if not adapter:
        raise click.ClickException(
            f"no adapter '{adapter_name}' declared. verify is experimental in v0.1.1; "
            f"declare an adapter in gdd/verification.md and supply the executable."
        )
    try:
        result = verify_cmd.run_adapter(adapter, tree.root)
    except verify_cmd.VerifyError as e:
        raise click.ClickException(str(e)) from e
    click.echo(json.dumps(result, indent=2))
    sys.exit(verify_cmd.evaluate(result))


if __name__ == "__main__":
    main()
