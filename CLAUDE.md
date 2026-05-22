# CLAUDE.md

The full workflow for this repository lives in @AGENTS.md. Read it first — everything there applies to you.

This file adds only Claude Code-specific notes that don't belong in the shared agent guide.

## Quick orientation

- This is a spec + CLI project for `game-design.md`, an LLM-first, engine-neutral, genre-agnostic game design document standard modeled on Google Labs' `DESIGN.md`.
- Format definition: @docs/spec.md
- Frontmatter schema: @schema/game-design.schema.json
- Reference example to study: @examples/deckbuilder/game-design.md

## Progressive disclosure

Do not pull the whole `gdd/` tree into context. The root `game-design.md` has a `files:` map — use it to open only the subfile(s) the task needs. Content lives in external `content/*/*.yaml`; read individual entity files on demand, not the whole directory.

## Before you commit

Run, in order:

```
pytest
gdmd lint examples/deckbuilder
```

Both must pass. `lint` returns JSON; if there are findings, fix them before committing — do not commit with open findings.

If `gdmd` isn't on `$PATH` yet, install the package once with `pip install -e ".[dev]"` (or `uv pip install -e ".[dev]"`).

## When you change a design

Follow the anti-drift ritual in @AGENTS.md (update `status:`, `implemented_in:`, `last_verified:`, bump `version:`, re-lint). This is not optional — the entire point of the standard is that the document and the code stay in sync, and you are the mechanism that keeps them in sync.

## When in doubt

- Ambiguous design decision → present 2–3 options, ask, don't guess.
- Tempted to add a genre-specific token to the core spec → don't. Use a prose convention in the example's subfile instead.
- Unsure how the real `DESIGN.md` handles something → `web_fetch` `github.com/google-labs-code/design.md/blob/main/docs/spec.md` and check.
