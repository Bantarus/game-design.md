# Design note: decision drift from agent sessions (WS5)

> **Status:** design note only (D-043). **Not implemented**, and not scheduled: a v0.4+ candidate, as the v0.4 kickoff scoped it ("cover using VCC-compiled Claude Code sessions to flag conversations that discuss `{ns.id}` tokens with no commit touching them; include scope, harness dependency and privacy concerns; do not implement"). No incidence of the problem has been measured, so measuring it comes before any build.

## The gap

The anti-drift mechanisms watch two directions:

- **Code drifting ahead of the doc:** `stale-section` (spec §8.2) warns when referenced code is newer than a section's `last_verified:`.
- **A commit touching referenced code:** `gdmd hook check` (spec §9.7) lists the sections whose `implemented_in:` matches the staged files.

Neither watches **decisions made in conversation.** A design choice about a token is often reached in an agent session ("raise `{resources.energy}` to a max of 4"). If no commit then changes the tree, the team and the agent believe one thing and the tree says another. The next cold-context agent compiles against the tree, not the conversation.

## The idea

For each Claude Code session run in a repository, list the `{ns.id}` tokens the user and the agent discussed, and mark those that no commit in a window after the session touched. The output is a **review queue**: "these tokens were discussed in this session and not changed afterwards; was a decision left unrecorded?" It is not a finding, has no severity, and never fails anything.

## Scope

**In:**

- Claude Code session transcripts (JSONL) whose records' `cwd` is inside the repository.
- Literal `{ns.id}` references, the tree's own reference syntax, in **user and assistant message text** only. A tool result is not a discussion: a file the agent read mentions tokens because the agent read it. A tool input (`gdmd view --ref {…}`) is consultation, not a decision.
- Mentions that resolve in the tree as it was at the session's start (the existing `Tree` resolution, so "discussed" uses the same definition as lint and views).
- Commits on the session's branch in a window after it ends.

**Out:**

- Any natural-language inference: no embeddings, vector stores, LLM summarization or classification, and no GraphRAG-style dependency (the kickoff's constraints). In particular, the tool does not decide whether a discussion **was** a decision. A human does.
- Tokens named without braces ("the energy cap"). They are missed by design; the reference syntax is the only signal that is exact.
- Other agents' logs. Each has its own format; see "Harness dependency".
- Any automatic edit to the tree.

## How it would work (sketch)

1. **Select sessions.** Read the records' `cwd`, `gitBranch` and `timestamp` fields to keep sessions that ran in this repository, and note their branch and time span. Subagent records (`isSidechain`) are included but marked, since they are the agent talking to itself.
2. **Compile each session with VCC** (the View-oriented Conversation Compiler, `lllyasviel/VCC`), as `benchmark/dogfood/extract.py` already does. VCC's lexer separates user text, assistant text, tool calls and tool results, and its full view gives each message a line range. That range is the pointer the report uses, the same "every item carries a pointer" discipline as the views (spec §9.9.2).
3. **Extract mentions.** Apply the reference pattern (`refs.TOKEN_REF_RE`) to user and assistant text only. Keep mentions that resolve in the tree at the session's start commit (the last commit before the session's first timestamp).
4. **Decide "touched".** Compare the tree at the start commit with the tree at the last commit within the window after the session ends. Two definitions are possible, and the choice is open:
   - **Token values, reusing `gdmd diff`** (spec §9.2): a token is touched if it is added, removed or changed. It has one existing definition, but it misses a decision recorded only in rationale prose.
   - **Block overlap, reusing the views' compiled model** (spec §9.9.1): a token is touched if any changed line falls in its block or in a rationale block that references it. It catches prose-only edits, but costs a compile per commit.
5. **Report**, per session: each discussed token, its mention pointers into the VCC view, and touched or untouched. By default the report carries only token ids, pointers and counts, never transcript text.

## Harness dependency

- **VCC is an external script,** not a package dependency. It is used offline from the conversation-compiler skill (`~/.claude/skills/conversation-compiler/scripts/VCC.py`, or `--vcc` / `$DOGFOOD_VCC`), as the dogfood harness does (D-023).
- **The session format is Claude Code's internal JSONL, not a stable public contract.** Records carry the Claude Code `version`, and the format can change between versions. The dogfood harness has already had to reassemble assistant messages split across records (VCC's `merge_chunks`). A drift tool would need the same care, and a fixture per supported format version.
- **It is agent-specific, so it cannot be a `gdmd` verb.** The standard is LLM-first and engine-neutral, and its CLI reads only trees. A tool tied to one agent's log format belongs outside the normative CLI: a script beside the dogfood harness, or a plugin. A second agent would need its own adapter to the same report.
- **git** provides the commit windows and the trees at each commit.

## Privacy

A session transcript holds everything said and read in it: pasted secrets and keys, personal data (names, emails), content from other repositories, third-party text the user pasted, and the user's own reasoning. So the tool must be:

- **Local and read-only.** No network access, and no writes to the transcripts.
- **Opt-in per run.** It reads the sessions or the session directory it is given, never a default location it discovers on its own.
- **Minimal in its output.** Token ids, pointers and counts by default. Excerpts only behind an explicit flag, and only to standard output.
- **Out of the repository.** Compiled views, excerpts and reports are never written into the repository. The dogfood harness keeps its session copies in a gitignored directory; the same rule applies here.
- **Per person.** In a team, each person runs it on their own sessions. Another person's sessions are not inputs unless that person chooses to share them, and a report is not committed or circulated without its owner reviewing it.
- **Without retention,** or with any cache kept under the user's own temporary directory.

## Expected failure modes

- **Discussion is not decision.** Explorations, rejected alternatives and questions all mention tokens. Precision is likely low, which is why the output is a review queue and not a finding.
- **The agent echoes what it read.** Assistant text often restates ids it just read, even with tool results excluded.
- **Decisions applied later than the window** are flagged. Too long a window hides unrecorded ones.
- **History rewrites** (rebase, squash) move commit dates away from the session that motivated them.
- **Renamed tokens** show as removed plus added; the old id counts as touched.
- **Several trees in one repository:** the session's mentions must be matched to the tree they resolve in.

## Before any build: measure

By the project's measurement discipline, the first step is evidence, not code.

1. **A labeled set.** For a set of past sessions, a human labels each (session, token) pair: was a decision reached, and did it land in the tree? The owner of the sessions decides which ones may be used; this repository's own sessions are the obvious corpus, and they are the user's.
2. **A pre-registered rule, committed before the labels are compared,** for what counts as useful: for example, a minimum precision of the untouched list against the labels, and the incidence of unrecorded decisions per session.
3. **A positive control:** a planted session in which a token change is agreed and not committed must be flagged.
4. **A negative control:** a session that only reads the tree must produce no untouched decisions beyond echoes, which measures the echo rate.

Only if unrecorded decisions are common enough, and the flag finds them with usable precision, is a build worth its privacy surface.

## Related

- **D-027's deferred `decision` role** would let views show decision records kept in files. It is separate: it concerns written records, while this note concerns decisions that were never written. No game tree has a DECISIONS file; this repository's `DECISIONS.md` records format decisions.
- **`gdmd hook check`** (code → spec at commit time) and **`stale-section`** (verify-side) are the existing anti-drift directions. This would be a third, conversation → spec, and advisory only.

## Open questions for the user

- Should tool inputs that change the tree (an `Edit` to a subfile) count as a touch before commit, or only commits?
- One window for everyone, or a flag?
- Token-value `diff`, or block overlap, as the definition of touched?
- Is this repository's own session history an acceptable labeled corpus?
