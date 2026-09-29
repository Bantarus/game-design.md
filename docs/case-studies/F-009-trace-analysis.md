# F-009 trace analysis: not analyzable for consultation cost

> **Status: recorded, not performed (v0.4 WS1, 2026-09-30).** Decision of record: [`DECISIONS.md`](../../DECISIONS.md) D-022. This note says why F-009's records cannot answer "where did the +37% go?" as a consultation question, and where that question moved. It contains no new numbers and does not reinterpret [F-009](F-009.md).

## The question WS1 asked

The v0.4 kickoff proposed a consultation-layer fix: projected views over the tree (`gdmd view`), so agents stop opening whole files. It cited F-009's 37.1% cost-lift as the motivating measurement, and asked where that cost went. The candidate causes were:
- full spec injection;
- whole-file reads;
- re-reads;
- reads of files irrelevant to the task.

The analysis was to compile F-009's traces into VCC views.

## Why the records can't answer it

| What the analysis needs | What F-009's apparatus produced (harness source at `37c004d`) |
| --- | --- |
| A session with tool calls, so reads can be counted | One system + one user chat-completion per trial. `tool_steps=0` by construction; the subject had no tools. |
| An agent choosing what to consult | A fixed payload built by the harness. Condition A was `AGENTS.md` + `CLAUDE.md` + every game-tree file, the same for every task. Condition B was the flattener's prose. |
| The prompt text, to attribute tokens to parts of it | Not stored. Records keep `payload_sha256` and `tokens_input` only. |
| Spec text in context, to test "spec injection" | Absent by construction. `docs/spec.md` was never in a payload; `CLAUDE.md`'s `@docs/spec.md` reached the model as literal text. |
| A format VCC compiles | Upstream VCC compiles Claude Code JSONL. A gather record is one JSON object with one response, so there is no block structure to project. |

Cost-lift in F-009 is `mean(tokens_in + tokens_out | A) / mean(… | B) − 1`. It is payload size plus response length under a harness-built payload. It measures what a model does with a whole tree *handed to it*, which is not what an agent does when it *looks things up*.

## What was declined, and what would still be possible

A deterministic token-accounting pass was considered and declined at Checkpoint 1:
1. Rebuild each A/B payload from git at `37c004d` and verify it against `payload_sha256`.
2. Validate a Qwen tokenizer against the recorded `tokens_input`.
3. Split the A−B delta into input segments (agent files, anti-drift metadata, syntax, task-irrelevant files) and output length.

It needs no model inference and stays available if a future question needs it. Even done, it would describe payload composition, not consultation.

## Where the question went

The consultation question moves to the **dogfood harness** (`benchmark/dogfood/`, D-023). Its runs are headless Claude Code sessions on this repo's own trees, so the traces are Claude Code JSONL, which VCC compiles natively. Any claim that views reduce session cost will come from a rule pre-registered there (D-025) before the first real run. It will not come from F-009.

F-009 itself stands as recorded: NULL on success-lift, FAIL on cost-lift, with every caveat in [the case study](F-009.md).
