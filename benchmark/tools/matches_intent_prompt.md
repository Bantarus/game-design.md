# Matches-Intent Prompt — for Layer 2 of the Judge stack

> **What this is.** The exact prompt sent to the auxiliary LLM judge to score one subject output on the "matches intent" 0-5 rubric (pre-reg §"Judge" Layer 2, locked at commit v7). The template is committed here so trial-zero readers can audit both the trial outputs AND the question we asked the judge to score them on. A loose or leading prompt would let a high score reflect rapport rather than fit; pinning the prompt is the same discipline as pinning the rubric.

---

## Prompt to the auxiliary LLM judge

You are scoring whether a coding agent's response **matches the intent** of a game-design implementation task. You will be given:

1. The **neutral design brief** of the game — written in a designer's voice, no implementation vocabulary. This is the *ground truth* against which intent is measured.
2. The **task brief** — the specific implementation task the agent was asked to do.
3. The **subject output** — the agent's response.

Your job is to **score the output on a 0-5 scale** answering:

> **"Does the output match the intent of the task brief, judged against the design brief?"**

### Scoring rubric (fixed in pre-reg)

| Score | Definition |
| --- | --- |
| **5** | Fully meets the brief. Every design choice is defensible against the brief's prose rationale. No unsupported additions. |
| **4** | Mostly meets. One small design choice defensible but non-optimal; no unsupported additions. |
| **3** | Partially meets. Either one significant gap OR one unsupported addition. |
| **2** | Mostly off. Multiple gaps or multiple unsupported additions. |
| **1** | Off. Doesn't address the brief, or contradicts the game's pillars / non-goals. |
| **0** | No usable output (refusal, empty, syntactically broken to the point of unscorable). |

A trial **passes the subjective criterion** at score ≥ 4. (The trial also has to pass the objective intent checklist, scored separately; passing this rubric alone is necessary but not sufficient for an overall trial pass.)

### Critical scoring discipline (cannot be relaxed)

**Score on whether the GAME CAME OUT CORRECT, not on whether the implementation MIRRORS THE SPEC.**

- An A-condition output using structured spec namespacing (`{verbs.X}`, `{loops.Y}`), a B-condition output using prose paraphrase, and a C-condition output using inline implementation code can all score the same as long as they exhibit the same game behavior described in the brief.
- Do NOT reward an output for "looking structurally right" if its content does not meet the brief.
- Do NOT punish an output for "not using the spec's namespacing" if its content does meet the brief.
- The scoring axis is behavioral / design intent, not structural / spec-conformance.

**Score against the design brief, not against the encoded A tree.** The brief is the ground truth. If the brief implies a design choice the A tree happens not to encode, an output reflecting that brief-implied choice should still score well. If the A tree encodes something the brief doesn't motivate, "mirroring the A tree" should NOT pull the score upward.

**Do NOT pull additional information about the game from anywhere outside the brief + task + output.** No web search, no inferred fan-wiki knowledge. The brief is the entire context.

### Output format

Respond with exactly this JSON, no other text:

```json
{
  "score": <integer 0-5>,
  "rationale": "<3-5 sentences citing specific text in the output AND specific claims in the design brief>",
  "design_choices_defended": ["<claim 1>", "<claim 2>", ...],
  "unsupported_additions": ["<claim 1>", "<claim 2>", ...]
}
```

`design_choices_defended` lists the specific design choices in the output that you judged as defensible against the brief (e.g., "the wall_kick's 1-ember cost matches the existing dash-rejection-without-ember pattern in the brief").

`unsupported_additions` lists any choices made WITHOUT brief support. An empty list at score ≥ 4 indicates a clean implementation. A non-empty list at score 4 or 5 must be explained in `rationale` (why the additions didn't pull the score lower — usually: they're small and brief-consistent).

---

## Context to provide alongside this prompt

When invoking the judge, attach:

1. **This prompt** (verbatim, including the rubric).
2. **The neutral design brief** — `benchmark/games/<game>/design-brief.md` for the game the task is on.
3. **The task brief** — `benchmark/tasks/<task_type>_<game>.yaml::brief`.
4. **The subject output** (verbatim, after the harness has captured it).

Do NOT attach:
- The A-tree game-design.md files (the brief is the ground truth, not the encoding).
- The B flattened prose (irrelevant to scoring this output).
- The C-prompt (irrelevant to scoring this output).
- Other subject outputs for comparison (each is scored independently).
- The objective intent checklist (that's scored separately, by a tightly scoped per-criterion judge call — see `benchmark/harness/checklist.py::write_checklist_template_for_judge`).
