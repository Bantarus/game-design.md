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
arms/views.md                 baseline.md + a neutral §9.9 command reference (hash recorded in D-025 before the Rule V matrix)
fixture.py                    isolated per-run copies
checklib.py                   shared checker helpers
extract.py                    trace metrics via VCC
run.py                        orchestrator
results/<run_id>.jsonl        one line per run (committed)
results/<run_id>/metrics/     per-cell extraction output (committed)
results/<run_id>/archive.json where the session logs were archived, with per-file SHA-256 (committed)
results/import-probe-*.json   import-size probe results (committed)
results/card-probe-*.json     card import-size probe results (committed)
results/sessions/             session JSONLs, stderr, VCC views (gitignored; compressed into
                              ~/.local/share/gdmd-dogfood/archive/<run_id>.tar.xz after each run)
```

## Arms and worlds (D-025)

| Arm | World: tooling-and-instructions layer | `gdmd` | Appended text |
| --- | --- | --- | --- |
| `baseline` | `v0.3`: `CLAUDE.md`, `AGENTS.md`, `docs/spec.md`, `schema/`, `src/`, `pyproject.toml` from tag `v0.3.0` | the v0.3 venv | `arms/baseline.md` |
| `views` | `matrix`: the matrix commit as-is | the copy's own `src/` | `arms/views.md` (pinned by SHA-256) |
| `import-full` (Rule C) | `matrix` | the copy's own `src/` | `arms/baseline.md` |
| `import-card` (Rule C) | `matrix`, with `CLAUDE.md`'s `@docs/spec.md` line swapped for `@docs/spec-card.md` | the copy's own `src/` | `arms/baseline.md` |

Everything else in a copy, including every task tree, comes from the matrix commit in both arms, so task content is identical by construction. The D-024 card ablation (Rule C) runs in the `matrix` world with `arms/baseline.md` (D-024 puts it on the baseline tool arm; the card needs v0.4 tooling). In each `import-card` copy, `fixture.swap_in_card` generates `docs/spec-card.md` with the copy's own `gdmd spec --card` and swaps only that one import line, before the copy's baseline commit, so no checker sees the swap as an edit. Every other copy (`baseline`, `views`, `import-full`, and the spec-import probe's copies) carries no `docs/spec-card.md`, even though the repository commits it since the card adoption (D-026 amendment 4, `fixture.remove_unimported_card`).

**The judge.** Checkers never use the arm's own `gdmd`. `run.py` exports the matrix commit's `src/` once per run as the fixed judge and passes it as `$DOGFOOD_GDMD`. The preflight refuses a copy if the arm's `gdmd` and the judge lint the untouched fixture differently, before or after the fixture patch.

## One-time setup (outside the repo)

```bash
# the v0.3 world's gdmd, installed from the tag; run.py hash-checks it against the tag
python3 -m venv ~/.local/share/gdmd-dogfood/venvs/gdmd-v0.3.0
~/.local/share/gdmd-dogfood/venvs/gdmd-v0.3.0/bin/pip install "git+file://$PWD@v0.3.0"   # from the repo root

# the pinned Claude Code CLI (run.py checks its SHA-256 and version; see CLAUDE_PIN_* in run.py)
mkdir -p ~/.local/share/gdmd-dogfood/claude
cp -p ~/.local/share/claude/versions/2.1.285 ~/.local/share/gdmd-dogfood/claude/claude-2.1.285
```

The copy sits outside the native installer's `versions/` directory, so auto-update pruning can't remove it. Sessions also run with `DISABLE_AUTOUPDATER=1`, and each cell re-checks `--version` against the run's first value.

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

- **Copy:** a `git archive` export of the run's pinned commit (HEAD when the run starts; a real run refuses to start with uncommitted harness changes), extracted **outside** the repo. That way Claude Code's parent-directory `CLAUDE.md` discovery sees only the copy's own `CLAUDE.md`, and so both arms pay the same `@`-imports.
- **Excluded from the copy:** `benchmark/dogfood/` and `tests/test_dogfood.py` (tasks, checkers, answers).
- **mtimes:** normalized to a fixed date, so `stale-section` reads the copy like the working tree. The fixture patch is the only fresh mtime, and so the only drift signal.
- **Git:** a fresh `git init`, with its own `.git`; not a worktree, so a subject's commit can't reach the real repo. Checkers diff against the `dogfood-base` tag.
- **CLI under test:** `gdmd` on PATH is a per-cell shim: the copy's own `src/` (`matrix`) or the v0.3 venv (`v0.3`).
- **Claude Code flags:**
  - `--setting-sources project,local`: loads the copy's own `CLAUDE.md` with its `@`-imports, and no user settings, so the maintainer's plugins, hooks and effort don't leak in. (`--restricted` is **not** used: it also drops `CLAUDE.md`; D-025 amendment 1.)
  - Auto-memory off (`--settings '{"autoMemoryEnabled": false}'` and `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`): otherwise the subject is offered a memory directory outside the copy.
  - Every run is checked from its transcript: `CLAUDE.md` injected, no auto-memory section. A failure makes the run an apparatus `error`.
  - `--strict-mcp-config`: no MCP servers.
  - `--disable-slash-commands`.
  - `--tools Read,Grep,Glob,Edit,Write,Bash`, with Bash allowlisted to read-only inspection plus `gdmd`.
  - `--permission-mode acceptEdits`.
  - pinned `--model` and `--effort`.
- **Caps:** `--max-budget-usd` per run and a wall-clock timeout. The turn cap is enforced by `run.py` on the stream: this CLI has no documented `--max-turns`.
- **Flag check:** `run.py` validates every flag it passes against `claude --help` before running (including `--dry-run`).

Residual leakage risk: file tools and Bash `cat`/`grep` can read absolute paths outside the copy. It isn't prevented, but it is **detected**: `extract.py` reports any tool input path outside the copy as `out_of_copy_access`, and a run with a non-zero count is flagged.

## Outcomes (D-025)

Each run is exactly one of:
- `success`: the session completed and the checker passed.
- `fail`: the session completed and the checker failed.
- `capped`: the turn cap, the wall-clock timeout or the budget cap ended the session. It counts as not-success.
- `error`: an apparatus failure, meaning no result event, another CLI error, no session JSONL, or a checker that emitted no report. D-025 governs re-runs.

## Metrics

`extract.py` compiles each session with VCC (`~/.claude/skills/conversation-compiler/scripts/VCC.py`, or `--vcc`, or `$DOGFOOD_VCC`) and writes the full and brief views next to the stored JSONL. Every tool call in `<cell>.metrics.json` carries its VCC full-view line range, so any number can be audited.

- **Per-turn context occupancy** = `input + cache_creation + cache_read` tokens of one API call. A turn is one assistant message id; split records are deduplicated.
- **Consultation bytes** = the UTF-8 bytes of all raw tool-result content returned to the model.

- **Reads** (secondary, D-025 amendment 3): subjects mostly read through Bash (`cat`, `head`, `sed -n`, `grep`), not `Read`. `bash_read_calls`, `bash_read_bytes`, `bash_files_read`, `all_files_read` and `all_re_reads` count both. `cd` is tracked across calls, and errored or denied calls read nothing. The `Read`-only `files_read` / `bytes_read` / `re_reads` stay for continuity.

- **Consultation bytes by view mode** (secondary, D-025 amendment 5): `view_mode_bytes` / `view_mode_calls` attribute each Bash call's full result bytes (errors included, as in the primary) to the view mode its command runs: `overview`, `full`, `grep`, `ref` (`gdmd view`), `graph` (any `gdmd graph`), `other` (`--help`), or `mixed` (more than one mode in one call). Descriptive only; it shows whether a mode such as `--full` drove the views arm's cost.

- **`--section` calls** (Rule C secondary): `gdmd_spec_section_calls` counts Bash calls containing `gdmd spec --section`, a sign of what the card leaves out.

These are the two pre-registered primaries: consultation bytes for views vs baseline, per-turn occupancy for the D-024 card ablation. The exact definitions live in D-025; keep this file in sync with it.

## Commands

```bash
python run.py --dry-run                    # validate flags + build every fixture; no model calls
python run.py --probe                      # 1 call: is the pinned model id served?
python run.py --import-probe               # 4 calls: spec.md @-import size in both worlds (D-024)
python run.py --card-probe --ref <sha>     # 2 calls: the card @-import's own size, matrix world (Rule C addendum)
python run.py --pilot                      # baseline x every task x 1 (not evidence)
python run.py --task lookup_refs --arm views --repeats 3
python run.py --task maintenance_drift --arm baseline --arm views --repeats 2 --repeat-start 4   # D-025 extension
python analyze.py rule-v results/<run>.jsonl [results/<rerun-or-extension>.jsonl ...]   # Rule V verdict, as locked
python analyze.py rule-c results/<run>.jsonl [...] --probe results/import-probe-<id>.json   # Rule C verdict (delta from the probe)
```

Order of operations (D-023 / D-025): dry run → probe → import probe → pilot (validates checkers, isolation and extraction; estimates cost) → **stop for approval** → full matrix.

## Limits (state them in every report)

- Small n: the default is 3 repeats per cell.
- A single subject model.
- The tasks were designed by the format's own author, on the format's own trees; the subject may also notice from `DECISIONS.md` that it is being benchmarked, which affects both arms equally.
- Not a longitudinal test (spec §11.2).
- Not comparable to F-009 (D-023).
