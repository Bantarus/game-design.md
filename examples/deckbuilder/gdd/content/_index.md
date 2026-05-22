---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-21"
---

## Tokens

Index file for the `content/` subtree. No tokens; this file exists because `docs/spec.md` §2.2 makes `content/_index.md` required whenever any content-schema file is present.

## Rationale

Two content-schema files in this tree:

- [`cards.md`](cards.md) — schema for the 220 designed cards under `content/cards/*.yaml`.
- [`enemies.md`](enemies.md) — schema for the ~30 designed enemies under `content/enemies/*.yaml`.

Add a new content type (relics, events, etc.) by:

1. Writing a new content-schema file `gdd/content/<kind>.md` (`file_type: content-schema`).
2. Creating the sibling `content/<kind>/` directory.
3. Adding the new key to the root `files:` map.
4. Linking it from this `_index.md`.

The `inline-content-over-threshold` rule (§9.1) makes the split mandatory once `count_target >= 20`.
