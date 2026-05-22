# `game-design.md`

> **Status: draft / alpha (v0.1.1).** Expect the format to change. Modeled on Google Labs' [`DESIGN.md`](https://github.com/google-labs-code/design.md).

An LLM-first, engine-neutral, genre-agnostic standard for video-game design documents. The primary consumer of a `game-design.md` tree is an AI coding agent; a human is the second reader.

## What's in this repo

| Path | Purpose |
| --- | --- |
| [`docs/spec.md`](docs/spec.md) | The formal specification. |
| [`schema/game-design.schema.json`](schema/game-design.schema.json) | JSON Schema for frontmatter (editor / CI validation). |
| [`DECISIONS.md`](DECISIONS.md) | Locked engineering decisions + ratchet plans (D-001 through D-006). |
| [`examples/deckbuilder/`](examples/deckbuilder/) | Reference example — "Ember Ascent." Read this to learn the shape. |
| [`examples/tick-combat/`](examples/tick-combat/) | "Lockstep" — exercises the `deterministic` distribution naturally. |
| [`examples/party-rpg/`](examples/party-rpg/) | "Hollow Hold" — exercises the `pity_floor` distribution naturally. |
| [`examples/tcg/`](examples/tcg/) | "Lattice" — asymmetric two-player; covers the rest of the surface. |
| `src/game_design_md/` | The `game-design.md` CLI (Python ≥3.10). Installs as both `game-design.md` and `gdmd`. |
| `tests/`, `tests/fixtures/` | pytest suite + on-disk fixtures for each linter rule. |
| [`AGENTS.md`](AGENTS.md) | Workflow guide for any coding agent working in this repo. |
| [`CLAUDE.md`](CLAUDE.md) | Claude Code-specific notes; imports `AGENTS.md`. |

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"           # or: uv pip install -e ".[dev]"

gdmd lint examples/deckbuilder    # exit 0, JSON to stdout
gdmd spec                         # the spec, frontmatter stripped — ready for agent prompt injection
gdmd export examples/deckbuilder --format tokens
pytest                            # the test suite
```

## The idea in one paragraph

A `game-design.md` tree pairs **normative YAML tokens** (the truth an agent compiles against) with **prose rationale** (why, and fallback when no token covers a case). Every game — any genre — reduces to seven core namespaces (`entities`, `verbs`, `resources`, `states`, `rules`, `loops`, `distributions`), plus two cross-cutting (`feel`, `balance_targets`), plus a tenth architecture-level namespace (`invariants` — engine-neutral contracts on the codebase). Tokens cross-reference each other as `{namespace.id}`. Content-heavy data (cards, enemies, items, levels) lives in sibling `content/*/*.yaml` files referenced by `data_source`, so the agent's context stays lean at 200+ entities. A CLI (`lint | diff | export | spec | verify`) enforces structure, detects drift, and supports dynamic verification through project-supplied adapters.

## The four examples

| Tree | Genre | Distribution coverage | Files |
| --- | --- | --- | --- |
| `examples/deckbuilder/` | Deckbuilder roguelike | `shuffle_bag`, `gaussian`, `uniform`, `weighted` | 20 |
| `examples/tick-combat/` | Auto-battler | `deterministic` + `gaussian` + `uniform` + `weighted` | 13 |
| `examples/party-rpg/` | Dungeon-crawler RPG | `gaussian` + `uniform` + `pity_floor` | 13 |
| `examples/tcg/` | Asymmetric 2-player TCG | `shuffle_bag` + `uniform` + `weighted` | 13 |

All six v0.1 distribution types are exercised across realistic example designs.

## License

Apache-2.0. See [LICENSE](LICENSE).
