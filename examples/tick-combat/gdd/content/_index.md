---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-22"
---

## Tokens

Index for the `content/` subtree. One content type ships in v0.1: [`units.md`](units.md). All ~24 designed units live in `content/units/*.yaml`.

## Rationale

`count_target: 24` puts units above the spec's mandatory-split threshold (`{count_target >= 20}`) — entries must be in sibling `*.yaml` files, not inlined here. See `docs/spec.md` §6.
