# Fairness Audit Prompt — for Layer 3 of B-construction

> **What this is.** The exact prompt sent to the auxiliary LLM judge during the B-construction fairness audit (pre-reg §B-construction Layer 3, `27a4381`). The audit happens **before** the flattener's SHA is frozen for trial use. The judge rates the flattened B brief on the question: "is this a fair prose brief, or a strawman?" The flattener SHA is frozen only at score ≥ 4. Score < 4 → revise the flattener and re-audit.
>
> The prompt is committed here so trial-zero readers can audit not only the flattener's output but also the question we asked the judge to score it on. A loose or leading audit question would let an unfair flattener pass; pinning the question in the spec is the same discipline as pinning the threshold.

---

## Prompt to the auxiliary LLM judge

You are evaluating whether a prose brief about a video game is a **fair** summary of the game's design — or whether it's a **strawman** that an unfriendly party could have written to make the game look incoherent.

You will be given:

1. A short context about what the brief is *supposed to be*: a coherent, topic-grouped prose summary of every design fact in a structured design document, written as a competent human prose-author would write it for an implementing team — facts grouped by topic, sentences flowing naturally, no token dumps in arbitrary order, no structural-syntax remnants.

2. The actual brief.

Your job is to **score the brief on a 1–5 scale** answering:

> **"Is this a fair prose brief — facts grouped by topic, readable as a coherent summary — or a strawman: incoherent, token-dump-style, or pathologically disorganized?"**

### Scoring rubric (fixed at pre-registration)

- **5 — clearly fair.** Reads as a coherent design summary. A reader could implement the game (or a substantial part of it) from this brief. Facts are grouped sensibly (loops together, recipes together, balance numbers in context). The prose flows.
- **4 — fair with minor friction.** Mostly coherent; some sentences are awkward or some grouping is suboptimal, but a reader could still implement the game with reasonable effort. The brief is informative.
- **3 — borderline.** Coherent in places, awkward in others. A reader would have to work harder than necessary to extract the game's shape. Some topics are well-grouped, others are scattered.
- **2 — substantially incoherent.** Reads as a token dump in arbitrary order. Topics are not grouped. A reader would have difficulty extracting the game's shape without doing the grouping themselves.
- **1 — strawman.** Reads as if produced by an unfriendly party. No coherent narrative. Structural-syntax remnants are visible. A reader would conclude the source design is incoherent (which it is not — this is the flattener's failure).

### Pass threshold

The flattener's SHA is frozen for trial use **only at score ≥ 4**. A score of 1, 2, or 3 means the flattener must be revised and re-audited.

### What to NOT score on

- **Do not score on agreement with the design.** You may dislike the game's premise, find a recipe imbalanced, or think a pillar is poorly chosen. None of that is the audit. The audit is about whether the brief *fairly represents* the design, not whether the design is good.
- **Do not score on whether the brief is "elegant" or "concise."** Coherence and topic-grouping are the bar; brevity is not.
- **Do not score on whether the brief contains every fact.** A separate machine verifier (`verifier.py`) checks information-completeness against the source design. Your job is fairness, not completeness — assume completeness holds.

### Output format

Respond with exactly this JSON, no other text:

```json
{
  "score": <integer 1-5>,
  "rationale": "<2-4 sentences explaining the score; cite specific passages>",
  "specific_issues": ["<issue 1>", "<issue 2>", ...]
}
```

If `specific_issues` is non-empty AND `score` is 4 or 5, you must explain in `rationale` why the issues did not pull the score lower. If `score` is 3 or below, `specific_issues` must list the concrete things to fix.

---

## Context to provide alongside this prompt

When invoking the judge, attach:

1. **This prompt** (verbatim, including the rubric).
2. **The brief being audited** (the full flattened B prose document).
3. **The source design's name and one-sentence pitch** (for grounding context only — NOT for the judge to score against; the judge should not pull additional information about the game from anywhere).

Do NOT attach:
- The source design's structured tree (the judge should not be comparing prose-to-tree; that's the machine verifier's job).
- The C-prompt (irrelevant to fairness).
- Other flattened briefs for comparison (each brief is audited on its own merits).

---

## Audit log convention

When the audit runs (once per fresh game, so twice total — Embergrave + Driftwood), the harness records:

- The judge model + version pinned for the audit.
- The prompt SHA at audit time (this file's SHA).
- The flattener SHA at audit time.
- The brief's SHA at audit time.
- The judge's full JSON output.
- A pass/fail flag.

These artifacts live at `benchmark/harness/audits/<game>_fairness_audit_<timestamp>.json` and are committed to the repo. The flattener SHA is frozen for trial use only after both games' audits pass.
