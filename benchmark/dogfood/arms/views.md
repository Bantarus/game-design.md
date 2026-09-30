## How to work in this session

You are working autonomously in a copy of the `game-design.md` repository. No human will answer questions during this session: make reasonable decisions, finish the task, then stop.

Follow the repository's own workflow (`AGENTS.md`, `CLAUDE.md`). To consult a design tree, read its root `game-design.md` first, then use its `files:` map to open only the subfiles your task needs; open individual content files on demand. Use the `gdmd` CLI as the workflow describes: `gdmd lint <tree>` to check your work, `gdmd hook check <tree> <paths...>` to see which spec sections reference code paths, and `gdmd touch <subfile...>` to bump `last_verified:`.

## Projected views: `gdmd view` and `gdmd graph`

This copy's `gdmd` also provides projected views over a tree (spec §9.9). They are computed from the tree on every call and store nothing. Every block they print is a verbatim slice of a tree file, with a `<path>:<start>-<end>` pointer; the path is relative to the tree root. Omitted lines are marked with the pointer of what was omitted.

- `gdmd view <tree>`: overview. Each file (type, status, `last_verified`), each namespace's tokens (id, status, pointer), and content entities counted per kind.
- `gdmd view <tree> --full`: every block and gap line of the tree, in canonical order, each with its pointer.
- `gdmd view <tree> --grep <regex> [--ignore-case]`: the blocks that contain a match, reduced to the matching lines and their ancestor keys.
- `gdmd view <tree> --ref <{ns.id}> [--hops N]`: one token in full, its forward references, and the blocks that reference it, out to N hops.
- `--flat`: any selection, as one line per block (role, id, pointer, status).
- `--role <role>`: restricts any view to the given roles: `token`, `invariant`, `content-entity`, `rationale`, `impl`, `meta`.
- `--json`: any view as JSON, including the tree's `tree_sha`.
- `gdmd graph <tree> --impact <{ns.id}>`: every block that references the token, directly or transitively, with its hop distance.
- `gdmd graph <tree> --from <{ns.id}> --to <{ns.id}> [--max-paths N]`: the shortest reference paths between two tokens.
- `gdmd graph <tree> --cycles`: reference cycles.
- `--format text|json|dot`: the graph output format.

Pointers are valid for the tree state (`tree_sha`) they were printed for. Re-run a view after editing.
