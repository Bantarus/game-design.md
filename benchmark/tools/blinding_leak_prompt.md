# Blinding-Leak Prompt — for the two-phase blinding-leak calibration

> **What this is.** The exact prompt sent to the auxiliary LLM judge during the two-phase blinding-leak calibration (pre-reg v7 §"Judge" Layer 3). The judge sees a batch of subject outputs with all condition labels stripped and must predict which condition (A / B / C) produced each one. The same prompt is used in both phases — Phase 1 (positive control on raw outputs, must score *above* chance) and Phase 2 (blinding-leak gate on sanitized outputs, must score *at* chance). Using the same prompt across phases is essential: a different prompt would confound "the judge can't see tells in sanitized outputs" with "the judge is being asked a different question."
>
> The template is committed here so trial-zero readers can audit both the calibration outputs AND the question we asked the judge to detect from. A leading prompt ("look for spec-vocabulary in A outputs") would teach the judge what to find and inflate the Phase-1 result; pinning the prompt prevents that.

---

## Prompt to the auxiliary LLM judge

You are evaluating a batch of coding-agent outputs produced under three different background-information conditions. Your job is to **predict which condition produced each output**.

The three conditions:

- **Condition A — Full structured design tree.** The agent had access to a complete, conformant `game-design.md` tree (YAML frontmatter with `entities`, `verbs`, `loops`, `rules`, `distributions`, etc., plus prose rationale) and project-level agent guidance files.
- **Condition B — Flattened prose.** The agent had access to the *same information* as A but mechanically flattened into a single unstructured prose document (no YAML frontmatter, no `{ref}` syntax, no canonical section structure).
- **Condition C — Minimal prompt.** The agent had access only to a one-paragraph description of the game (no numbers, no rules, no detailed mechanics).

All three conditions were given the **same implementation task**. Your job is NOT to score the outputs' quality; it is only to predict, for each output, which condition it came from.

You will be given the batch as a numbered list of outputs. For each output, predict A, B, or C.

### Critical scoring discipline

**Predict from whatever distinguishing features you can see** — vocabulary, structure, citation patterns, density, formality, references to the design document, presence of structured tokens or YAML-like syntax, anything that varies between the three conditions. Use your full judgment.

**You may be wrong.** That is expected and informative — if you genuinely cannot distinguish the conditions, that is what the calibration is measuring. Do NOT default to guessing one condition more than the others if the outputs look genuinely indistinguishable; report your honest best guess per output.

**Do NOT communicate with the user.** This is an automated calibration; respond only with the JSON below.

### Output format

Respond with exactly this JSON, no other text:

```json
{
  "predictions": [
    {
      "output_id": <integer>,
      "predicted_condition": "A" | "B" | "C",
      "confidence": <float 0.0-1.0>,
      "rationale": "<1-2 sentences citing the specific feature that drove your prediction>"
    },
    ...
  ]
}
```

The `output_id` MUST match the integer ID provided alongside each output in the batch. Order is the order you encountered them; you may reorder freely if the schema is preserved.

The `rationale` must cite the *specific feature* of the output that drove your prediction (e.g., "output uses `{verbs.X}` curly-brace syntax — A-tell", or "output uses 'as per the spec' phrasing — A-tell"). At Phase 1 these rationales explain how you saw the tells; at Phase 2 they explain what tells survived sanitization. The rationales are recorded as calibration artifacts.

`confidence` is your subjective certainty per output. A confidence of 0.33 means "I literally cannot distinguish."

---

## Context to provide alongside this prompt

When invoking the judge, attach:

1. **This prompt** (verbatim).
2. **The batch of outputs** with stripped labels — each output is preceded by `<<< OUTPUT_ID: N >>>` for identification.

Do NOT attach:
- Condition labels (the whole point of the calibration is that the judge guesses).
- The design brief or task brief (the judge is detecting condition style, not scoring task fit).
- The C-prompt or B-flattened brief (would teach the judge what each condition's payload looks like — circular).
- Other batches for comparison (each batch is processed in isolation).

---

## How the two phases use this template

Both Phase 1 (positive control on raw outputs) and Phase 2 (blinding-leak gate on sanitized outputs) use this template verbatim. The only difference is the input batch: Phase 1's batch is the raw subject outputs, Phase 2's batch is those same outputs after passing through `benchmark/harness/sanitization.py::sanitize_output`. Identical prompt → any divergence in judge accuracy between the two phases is attributable to the sanitization, not to a prompt-shift confound.

Phase 1 expected outcome (when the judge bundle is competent): accuracy clearly above 33%, with rationales citing visible A-tells like `{namespace.id}` syntax, canonical section headers, "per the spec" phrasing. If Phase 1's accuracy is at chance, the judge is too weak — the bundle needs to be re-pinned.

Phase 2 expected outcome (when sanitization is sufficient): accuracy at chance (95% Wilson CI on accuracy includes 33%), with rationales citing genuinely indistinguishable content. If Phase 2's accuracy is above chance even after sanitization, the sanitizer needs to be strengthened (add more patterns to `harness/sanitization.py`) and Phase 2 re-run.

---

## Audit-log convention

When the calibration runs, the harness records:

- The judge bundle (model + variant + quant + GGUF SHA + sampling params + chat template).
- This prompt template's SHA at calibration time.
- The sanitizer's SHA at calibration time (`benchmark/harness/sanitization.py`).
- The calibration task ID + game.
- The raw subject outputs (per-output ID, condition, full text).
- The sanitized subject outputs (per-output ID, sanitized text).
- The judge's full JSON response in both phases (per-output prediction, confidence, rationale).
- The computed accuracy + Wilson 95% CI for each phase.
- The overall pass/fail decision and which phase(s) failed if applicable.

Artifacts live at `benchmark/harness/audits/blinding_leak_<timestamp>.json` and are committed to the repo. Calibration must pass before trial zero counts.
