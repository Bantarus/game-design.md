---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-22"
---

## Tokens

Index for the `content/` subtree. One content type ships in v0.1: [`items.md`](items.md). All ~50 designed items live in `content/items/*.yaml`.

## Rationale

`count_target: 50` puts items above the spec's mandatory-split threshold (`{count_target >= 20}`) — entries live in sibling `*.yaml` files. See `docs/spec.md` §6.

Each item carries a `rarity:` that maps to one of the five buckets sampled from `{distributions.loot_rarity}`.
