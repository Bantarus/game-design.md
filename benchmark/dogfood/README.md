# Dogfood harness

The routine evidence surface for claims about how agents work with a `game-design.md` tree (spec §11.3, `DECISIONS.md` D-023). A subject agent (`claude-sonnet-5-5`, headless Claude Code) runs small fixed tasks on this repository's own trees. Deterministic checkers grade the outcome, and a locked rule (D-025), written before the first real run, turns the results into a verdict.

**It never runs in CI.** The pytest suite (`tests/test_dogfood.py`) tests the harness itself (checkers, fixtures, extraction, flag validation) and makes no model calls.

## Layout

```
tasks/tasks.yaml              task registry: mode, tree, optional fixture patch
tasks/<task_id>.md            prompt given to the subject verbatim (on stdin)
tasks/<task_id>.check.py      deterministic checker: exit 0 = success, JSON report on stdout
tasks/*.fixture.patch         teammate commit applied before the session (git format-patch)
tasks/lookup_refs.expected.json   frozen, hand-verified answers (never recomputed at check time)
arms/baseline.md              appended to the system prompt: the current workflow
arms/views.md                 baseline.md + a "projected views" section (draft until WS2 lands)
fixture.py                    isolated per-run copies
checklib.py                   shared checker helpers
extract.py                    trace metrics via VCC
run.py                        orchestrator
results/<run_id>.jsonl        one line per run (committed)
results/sessions/             session JSONLs, VCC views, per-run metrics (gitignored; SHA-256 in each line)
```

## Tasks

| Task | Mode | Tree | Success (checker) |
| --- | --- | --- | --- |
| `authoring_new_card` | authoring (§11.1 shape) | deckbuilder | Exactly one new card matching the brief and the content-schema (validated by the checker itself, since lint doesn't: OI-005); `draft`; nothing else changed; lint 0/0. |
| `lookup_refs` | lookup | deckbuilder | `answers/lookup.txt` equals the frozen answers: Q1 is backlinks of a resource, Q2 is a 2-hop forward walk. |
| `operating_energy_budget` | operating | deckbuilder | The token diff equals the expected propagation set, including a coupling lint can't see; nothing else; lint 0/0. |
| `maintenance_drift` | maintenance | tick-combat | A teammate's behavior-preserving refactor under `implemented_in`: `last_verified` bumped on exactly the affected section, no token churn, impl untouched, lint 0/0. |
| `negative_control_no_drift` | negative control | tick-combat | Same prompt as maintenance; the teammate change is in a file no section references. The copy must be left unchanged. |

"Ritual metadata" (a root `version` increase with `last_updated`, and `last_verified` bumps) is allowed but never required, except where it is the thing being tested (maintenance) or where no change at all is correct (the control). See `checklib.check_ritual_metadata`.

## Isolation (per run)

- **Copy:** a `git archive HEAD` export, extracted **outside** the repo. That way Claude Code's parent-directory `CLAUDE.md` discovery sees only the copy's own `CLAUDE.md`, and so both arms pay the same `@`-imports.
- **Excluded from the copy:** `benchmark/dogfood/` and `tests/test_dogfood.py` (tasks, checkers, answers).
- **mtimes:** normalized to a fixed date, so `stale-section` reads the copy like the working tree. The fixture patch is the only fresh mtime, and so the only drift signal.
- **Git:** a fresh `git init`, with its own `.git`; not a worktree, so a subject's commit can't reach the real repo. Checkers diff against the `dogfood-base` tag.
- **CLI under test:** `gdmd` on PATH is a shim that runs the copy's own `src/`.
- **Claude Code flags:**
  - `--restricted`: file tools confined to the copy; user, project and local settings ignored, so the maintainer's plugins, skills, hooks and effort don't leak in.
  - `--strict-mcp-config`: no MCP servers.
  - `--disable-slash-commands`.
  - `--tools Read,Grep,Glob,Edit,Write,Bash`, with Bash allowlisted to read-only inspection plus `gdmd`.
  - `--permission-mode acceptEdits`.
  - pinned `--model` and `--effort`.
- **Caps:** `--max-budget-usd` per run and a wall-clock timeout. The turn cap is enforced by `run.py` on the stream: this CLI has no documented `--max-turns`.
- **Flag check:** `run.py` validates every flag it passes against `claude --help` before running (including `--dry-run`).

Residual leakage risk: Bash `cat`/`grep` can read absolute paths outside the copy. It isn't prevented, but it is **detected**: `extract.py` reports any tool input path outside the copy as `out_of_copy_access`, and a run with a non-zero count is flagged.

## Metrics

`extract.py` compiles each session with VCC (`~/.claude/skills/conversation-compiler/scripts/VCC.py`, or `--vcc`, or `$DOGFOOD_VCC`) and writes the full and brief views next to the stored JSONL. Every tool call in `<cell>.metrics.json` carries its VCC full-view line range, so any number can be audited.

- **Per-turn context occupancy** = `input + cache_creation + cache_read` tokens of one API call. A turn is one assistant message id; split records are deduplicated.
- **Consultation bytes** = the UTF-8 bytes of all raw tool-result content returned to the model.

These are the two pre-registered primaries: consultation bytes for views vs baseline, per-turn occupancy for the D-024 card ablation. The exact definitions live in D-025; keep this file in sync with it.

## Commands

```bash
python run.py --dry-run                    # validate flags + build every fixture; no model calls
python run.py --probe                      # 1 call: is the pinned model id served?
python run.py --import-probe               # 2 calls: spec.md @-import size (D-024 precondition)
python run.py --pilot                      # baseline x every task x 1 (not evidence)
python run.py --task lookup_refs --arm views --repeats 3
```

Order of operations (D-023 / D-025): dry run → probe → pilot (validates checkers, isolation and extraction; estimates cost) → **stop for approval** → full matrix.

## Limits (state them in every report)

- Small n: the default is 3 repeats per cell.
- A single subject model.
- The tasks were designed by the format's own author, on the format's own trees; the subject may also notice from `DECISIONS.md` that it is being benchmarked, which affects both arms equally.
- Not a longitudinal test (spec §11.2).
- Not comparable to F-009 (D-023).
