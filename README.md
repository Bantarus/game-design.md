# `game-design.md`

> **A living game design document that stays current with the code, maintained by an AI coding agent over the lifetime of a project.** Pre-stable (v0.3.0); v1.0 is the planned stable lock. Modeled on Google Labs' [`DESIGN.md`](https://github.com/google-labs-code/design.md).

`game-design.md` is what `CLAUDE.md` or `AGENTS.md` is for a software project, applied to a video game: a structured plain-text artifact the AI agent reads first, writes back to, and keeps coherent over weeks and months of development. The format is **LLM-first, engine-neutral, genre-agnostic**: the primary consumer is a coding agent; a human is the second reader; no engine, framework, or genre is privileged at the schema level.

The closer analog isn't a one-shot specification handed off to a contractor. It is a *living project artifact the agent maintains* — a source of truth that the agent updates when the design changes, references when implementing new features, and treats as authoritative when the code and the document disagree. The structural inheritance from `DESIGN.md` is real (the two-layer YAML+prose file pattern, the canonical section order, the linter discipline); the temporal axis — *the document outlives the session, the agent keeps it current* — is the differentiator.

## What's in this repo

| Path | Purpose |
| --- | --- |
| [`docs/spec.md`](docs/spec.md) | The formal specification (v0.3.0). |
| [`schema/game-design.schema.json`](schema/game-design.schema.json) | JSON Schema for frontmatter (editor / CI validation). |
| [`DECISIONS.md`](DECISIONS.md) | Locked engineering decisions + ratchet plans (D-001 through D-021). |
| [`CHANGELOG.md`](CHANGELOG.md) | What landed when, Keep-a-Changelog format. |
| [`AGENTS.md`](AGENTS.md) | Workflow guide for any coding agent working in this repo — the three-mode operating lens (authoring / operating / maintenance). |
| [`CLAUDE.md`](CLAUDE.md) | Claude Code-specific notes; imports `AGENTS.md`. |
| [`examples/`](examples/) | Four canonical example trees: deckbuilder, tick-combat, party-rpg, tcg. The reference shape; copy these to learn the format. |
| [`benchmark/games/`](benchmark/games/) | Two fresh game trees (platformer, survival) authored under the Phase-5 protocol; sources for the per-genre starter templates. |
| [`templates/starters/`](templates/starters/) | Six per-genre starter templates (deckbuilder, party-rpg, tcg, tick-combat, platformer, survival). Scaffolded by `gdmd init`. |
| [`docs/release-notes/`](docs/release-notes/) | Per-release narrative notes. |
| [`docs/case-studies/`](docs/case-studies/) | Worked examples — what a result looks like when reported by the locked rule. |
| [`docs/methodology/`](docs/methodology/) | Framing layer for the methodology framework v0.1.1 → v0.3 surfaced. |
| `src/game_design_md/` | The `game-design.md` CLI (Python ≥3.10). Installs as both `game-design.md` and `gdmd`. |
| `tests/`, `tests/fixtures/` | pytest suite + on-disk fixtures for each linter rule. |

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"           # or: uv pip install -e ".[dev]"

gdmd init --genre deckbuilder my-game        # scaffold a new tree from a starter
gdmd lint my-game                            # validate (exit 0, structured JSON to stdout)
gdmd status my-game                          # project dashboard view
gdmd spec                                    # the spec itself, frontmatter stripped — ready for agent prompt injection

pytest                                       # the test suite (161 tests at v0.3)
```

For an existing tree, the anti-drift ritual is the rhythm:

```bash
gdmd hook install my-game                    # one-time pre-commit registration
# on every commit, `gdmd hook check` surfaces affected spec sections
gdmd touch my-game/gdd/mechanics.md          # atomically bump last_verified: after re-verifying
gdmd lint my-game && gdmd status my-game     # close the loop
```

## The idea in one paragraph

A `game-design.md` tree pairs **normative YAML tokens** (the truth an agent compiles against) with **prose rationale** (why, and fallback when no token covers a case). Every game — any genre — reduces to seven core namespaces (`entities`, `verbs`, `resources`, `states`, `rules`, `loops`, `distributions`), plus two cross-cutting (`feel`, `balance_targets`), plus a tenth architecture-level namespace (`invariants` — engine-neutral contracts on the codebase), plus a v0.3 time-passage namespace (`clocks`, the first-class primitive distinct from player verbs). Tokens cross-reference each other as `{namespace.id}`. Content-heavy data (cards, enemies, items, levels) lives in sibling `content/*/*.yaml` files referenced by `data_source`, so the agent's context stays lean at 200+ entities. A CLI (`lint | diff | export | spec | verify | status | hook | touch | init`) enforces structure, detects drift, supports dynamic verification through project-supplied adapters, and automates the maintenance ritual.

## What's been demonstrated

The v0.2 cross-engine pass demonstrated that the spec drives byte-identical integer trajectories across two engines (xtreme/Bevy ECS in Rust + Godot 4 in GDScript) at the same seed; both pass `gdmd verify` exit 0 against the same canonical JSONL trajectory. v0.3 closed two expressiveness gaps (F-008 per-instance state, F-010 verb-centric friction in non-turn-based games) surfaced by fresh-game authoring during Phase 5.

The v0.2 help-benchmark (F-009) reported NULL on success-lift and FAIL on cost-lift under the locked rule on a single-subject Qwen-Coder configuration. The result was reported by the rule that had been locked before the trial fired. The reading of what that meant — and the reframe into the longitudinal living-doc proposition v0.3 ships under — is the worked example at [`docs/case-studies/F-009.md`](docs/case-studies/F-009.md). The methodology that produced both the locked rule and the reframe lives at [`docs/methodology/README.md`](docs/methodology/README.md). The validation surface v0.3 ships under is scoped in [`docs/spec.md`](docs/spec.md) §11.2.

## Tree validation at a glance

All 12 in-repo trees (6 canonical/benchmark + 6 starters) lint clean at v0.3 — 0 errors, 0 warnings — under default thresholds.

| Tree | Genre | v0.3 vocab carried |
| --- | --- | --- |
| [`examples/deckbuilder/`](examples/deckbuilder/) | Roguelike deckbuilder | (no v0.3 vocab — deckbuilder was the F-008/F-010 no-op) |
| [`examples/tick-combat/`](examples/tick-combat/) | Auto-battler tick combat | `{clocks.tick}` + `instance_container` (cross-engine determinism canonical case) |
| [`examples/party-rpg/`](examples/party-rpg/) | Party-based RPG | `instance_container` (party members) |
| [`examples/tcg/`](examples/tcg/) | Two-player asymmetric TCG | `instance_container` (battlefield) |
| [`benchmark/games/platformer/`](benchmark/games/platformer/) | Real-time precision platformer (Embergrave) | `{clocks.physics}` (continuous, 60 Hz) |
| [`benchmark/games/survival/`](benchmark/games/survival/) | Action-economy survival sim (Driftwood) | `{clocks.world_time}` (per_verb_delta) + `instance_container` (inventory) |

The 6 starter templates carry forward v0.3 vocab where the canonical example demonstrated the closure — descriptive-not-prescriptive at the starter-content layer.

## v0.3 release at a glance

Twelve commits, kickoff order `1 → 2 → 3 → 6 → 4 → 5 → 7`. See [`CHANGELOG.md`](CHANGELOG.md) for the full list and [`docs/release-notes/v0.3.md`](docs/release-notes/v0.3.md) for the narrative.

The validation bar reframe (D-021, spec §11.2) — from the kickoff's "at least one live project" to v0.3's three-claim in-repo evidence surface plus one v0.4+-queued longitudinal claim — is recorded with full audit lineage. v0.4 vocabulary growth is gated on observed need from live adoption; v0.3 ships the apparatus the longitudinal property would test.

## License

Apache-2.0. See [LICENSE](LICENSE).
