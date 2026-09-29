## How to work in this session

You are working autonomously in a copy of the `game-design.md` repository. No human will answer questions during this session: make reasonable decisions, finish the task, then stop.

Follow the repository's own workflow (`AGENTS.md`, `CLAUDE.md`). To consult a design tree, read its root `game-design.md` first, then use its `files:` map to open only the subfiles your task needs; open individual content files on demand. Use the `gdmd` CLI as the workflow describes: `gdmd lint <tree>` to check your work, `gdmd hook check <tree> <paths...>` to see which spec sections reference code paths, and `gdmd touch <subfile...>` to bump `last_verified:`.

## Consulting a tree with projected views

<!-- DRAFT: command syntax follows the WS2 plan and is finalized after v0.4 Checkpoint 3.
     run.py refuses the views arm until `gdmd view --help` succeeds in the copy. -->

Instead of opening whole files, consult the tree through `gdmd view` and `gdmd graph`. They are computed on the fly from the tree and never paraphrase it: every token value is shown verbatim, and every block carries a `file:start-end` pointer you can open if you need the surrounding text.

- `gdmd view <tree>`: overview. Every token per namespace, with its status and a pointer.
- `gdmd view <tree> --ref {ns.id} [--hops N]`: one token, with the tokens it references and the tokens that reference it (backlinks).
- `gdmd view <tree> --grep <pattern>`: only the matching blocks, keeping their namespace → token → field structure.
- `gdmd view <tree> --flat`: the same, as a flat list tagged by role.
- `gdmd graph <tree> --impact {ns.id}`: everything that transitively depends on a token.
- `gdmd graph <tree> --from {ns.id} --to {ns.id}`: the reference paths between two tokens.

Prefer a view to reading a whole file. When a view truncates something it says so and gives the pointer; open only that range.
