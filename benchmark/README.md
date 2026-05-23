# `benchmark/` — Phase 5 help-benchmark scaffolding

> The harness for the Phase 5 help-benchmark whose pre-registration is locked at commit `27a4381` (chain: `f76f4c2 → a9425e8 → 77ae3a5 → 78f150c → 766e07b → 27a4381`). See [`docs/v0.2-phase5-pre-registration.md`](../docs/v0.2-phase5-pre-registration.md) for the locked gate, [`docs/v0.2-phase5-help-benchmark-scope.md`](../docs/v0.2-phase5-help-benchmark-scope.md) for the framing.

## Layout

```
benchmark/
  games/
    platformer/           # Embergrave — fresh game #1 (commit dc12419 / 27a4381)
      design-brief.md     # Act 1 (designer voice)
      game-design.md      # Act 2 (encoded A tree)
      gdd/                # Act 2
      content/            # Act 2
      gdd/architecture-invariants.md   # Act 3 (trace-disciplined)
    survival/             # Driftwood — fresh game #2 (commit 6f3ecdd)
      [same shape as platformer]
  c-prompts/              # Condition-C "minimal prompt" briefs (good-faith)
    platformer.md
    survival.md
  tasks/                  # Task definitions per (task type × game) cell
    easy_platformer.yaml      # N=5, non-headline (sanity check)
    easy_survival.yaml
    medium_platformer.yaml    # N=20, HEADLINE
    medium_survival.yaml
    hard_platformer.yaml      # N=20, HEADLINE
    hard_survival.yaml
    ambiguity_platformer.yaml # N=20, HEADLINE
    ambiguity_survival.yaml
  tools/
    flattener.py          # Layer 1 of B-construction: deterministic A → B
    verifier.py           # Layer 2 of B-construction: information-completeness
    fairness_audit_prompt.md  # Layer 3 of B-construction: judge prompt template
  harness/
    __init__.py           # Package readme
    tasks.py              # Load + freeze task definitions
    conditions.py         # Build A/B/C payloads
    instrument.py         # Instrument abstraction + MockInstrument + stubs
    judge.py              # Judge abstraction + MockJudge + stubs
    checklist.py          # Objective intent checklist evaluator
    calibration.py        # Instrument-calibration + blinding-leak calibration
    run_trial.py          # Main trial entry point (atomic per invocation)
    audits/               # Layer-3 fairness audit artifacts (populated at trial-build)
    trials/               # Per-trial JSON records (populated during trials)
```

## Status

**Pre-trial-zero scaffolding** at the time of this commit:

| Component | Status | What's in / out |
| --- | --- | --- |
| Fresh games (A trees) | **Done** | Embergrave (commit `dc12419` / Act-3 retro `27a4381`) and Driftwood (`6f3ecdd`); all under three-act protocol; lint 0e/0w. |
| Design briefs (Act 1) | **Done** | One per game; designer voice; ~90 lines each. |
| C-prompts | **Done** | One per game; good-faith minimal briefs (held to the same fairness standard as B per the user's harness-caution). |
| Task definitions | **Done** | 8 tasks total: easy / medium / hard / ambiguity × 2 games; intent checklists score game behavior, NOT spec-structure-conformance. |
| Flattener (B Layer 1) | **Done** | Deterministic; smoke-tested on both games (byte-identical re-runs). Verifier passes 0e on both. |
| Verifier (B Layer 2) | **Done** | Six completeness checks per the pre-reg; passes on both games. |
| Fairness audit prompt (B Layer 3) | **Done** (template) | Authored. Needs an auxiliary LLM judge wired up to actually run. |
| Trial harness skeleton | **Done** (scaffold) | `tasks.py`, `conditions.py`, `instrument.py`, `judge.py`, `checklist.py`, `calibration.py`, `run_trial.py`. End-to-end smoke-tested with MockInstrument + MockJudge. |
| Calibration smoke runs | **Mock-only** | Calibration code path works; the seed-sensitivity gate correctly *fails* MockInstrument (as designed — mock outputs only vary by seed integer). Real-instrument calibration is blocked on instrument wiring. |
| Blinding-leak calibration | **Mock-only** | Code path works with MockJudge; real calibration is blocked on judge wiring. |
| Trial runs | **Mock-only** | One mock trial smoke-tested end-to-end. Real trials are blocked on instrument + judge wiring. |

## What's needed before trial zero can fire

The harness is complete *to the extent code-only work can complete it*. The remaining work requires either an external API key or a local model deployment — each is listed below with what specifically the pre-reg requires.

### 1. Wire up the auxiliary LLM judge (pinned at v7: Gemma 4 26B A4B)

**The auxiliary judge bundle is pinned at pre-reg v7 (commit landing alongside this README) to Gemma 4 26B A4B (Google), local-inference via llama.cpp.** Non-Qwen, non-Claude family — satisfies the pre-reg's hard family rule (the rule exists to eliminate spec-author interpretive bias and subject overlap; Claude as judge is hard-disqualified by both vectors). Apache-2.0 licensed. No API key required. Runs sequentially alongside the Qwen instrument in the same llama.cpp infrastructure (judge has the full GPU during scoring; generation and judging never compete for VRAM).

The model family + base identity (`gemma-4-26b-a4b`) is normative at v7 pre-reg. The quant + GGUF SHA + llama.cpp version + sampling parameters + chat template are pinned at the harness-build commit per the same bundle-pinning discipline as the instruments. To finalize:

1. Build llama.cpp at a chosen release tag (record git SHA in the bundle).
2. Download the chosen Gemma 4 26B A4B GGUF (record SHA-256 in the bundle).
3. Set env vars `DRIFTWOOD_GEMMA_GGUF_PATH` and `DRIFTWOOD_LLAMA_CPP_BIN` (same llama.cpp binary as the Qwen instrument).
4. Implement `GemmaJudge.{score_matches_intent, audit_fairness, predict_conditions}` in `harness/judge.py` — the class + bundle declaration are pinned; the three methods need their subprocess-call bodies wired up.
5. Commit the finalized bundle declaration (the harness-build commit's SHA becomes the bundle lock).

The judge is used for THREE purposes (each with a frozen prompt template committed in `benchmark/tools/`):

- **Matches-intent scoring** (the 0-5 rubric, pre-reg §"Judge" Layer 2). Template: [`tools/matches_intent_prompt.md`](tools/matches_intent_prompt.md). Frozen.
- **Fairness audit** (Layer 3 of B-construction). Template: [`tools/fairness_audit_prompt.md`](tools/fairness_audit_prompt.md). Frozen.
- **Blinding-leak prediction** (Phase 1 + Phase 2 of the two-phase blinding-leak calibration, pre-reg §"Judge" Layer 3 v7). Template: [`tools/blinding_leak_prompt.md`](tools/blinding_leak_prompt.md). Frozen; identical prompt across both phases.

All three templates are loaded as text and substituted at runtime — no template-generation logic in the judge wire-up.

**Alternative judges (`GeminiJudge`, `OpenAIJudge`) remain in `harness/judge.py` as future-options** if a v8+ extension changes the pin away from Gemma; both require API keys and both satisfy the family rule. Neither is the v7 pin and neither should be used as a substitute for the Gemma pin without a pre-reg supersession.

**Forbidden judge candidates:** Qwen (headline subject), Claude (spec-author + transfer-probe subject). The latter is most acute at the blinding-leak step where the judge's job is adversarial — the family that wrote the spec is the family most likely to recognize spec-vocabulary leaking through A-condition outputs. See pre-reg v6 → v7 audit-trail row #12 for the full rationale and project memory `judge-family-independence` for the standing rule.

### 2. Pin the Qwen headline instrument bundle (pre-reg §"Test subjects")

Required:
- Local llama.cpp build at a known version (record the git SHA or release tag).
- The Qwen GGUF file at a known path (record SHA-256 of the file).
- Sampling parameters chosen and pinned.
- Chat template + reasoning-format handling chosen and pinned (the `<think>...</think>` block handling specifically).

To wire up:
1. Set env vars `DRIFTWOOD_QWEN_GGUF_PATH` and `DRIFTWOOD_LLAMA_CPP_BIN`.
2. Implement `QwenInstrument.complete()` in `harness/instrument.py` (replace the stub with the subprocess call).
3. Commit the bundle declaration: `bundle = InstrumentBundle(model_name=..., quant=..., gguf_sha256=..., ...)` — this freezes the instrument identity.

### 3. Pin the Claude transfer-probe instrument bundle (pre-reg §"Test subjects")

Required:
- Anthropic API access (`ANTHROPIC_API_KEY`).
- The specific Claude version pinned.

To wire up:
1. Set env var `ANTHROPIC_API_KEY`.
2. Implement `ClaudeInstrument.complete()` in `harness/instrument.py` (replace the stub with `anthropic.Anthropic(...).messages.create(...)`).
3. Commit the bundle declaration.

### 4. Run the fairness audit on both games' flattened B (Layer 3 of B-construction)

```
python -m benchmark.harness.audit_fairness --game platformer
python -m benchmark.harness.audit_fairness --game survival
```

(This entrypoint is a stub; needs to be authored once the judge is wired up. The judge prompt template is already locked at `tools/fairness_audit_prompt.md`.)

Both audits must pass at score ≥ 4 before the flattener SHA can be frozen for trial use. Failure → revise flattener → re-audit.

### 5. Run instrument calibration on both instrument bundles (pre-reg §"Protocol" step 11)

```
python -m benchmark.harness.run_calibration --instrument qwen
python -m benchmark.harness.run_calibration --instrument claude
```

(This entrypoint is a stub; needs to be authored once instruments are wired up.)

Both bundles must pass all three gates (structural / seed-sensitivity / rubric-reachability). The same-seed audit is recorded but not gated.

### 6. Run blinding-leak calibration on the pinned judge — TWO PHASES (pre-reg v7 §"Judge" Layer 3)

```
python -m benchmark.harness.run_blinding_leak_calibration \
    --instrument qwen --task easy --game platformer
```

(Stub entrypoint.)

N=30 outputs (10 per A/B/C) on the easy_platformer task. **Two-phase gate per pre-reg v7:**

- **Phase 1 — Positive control / judge fitness.** Judge predicts each output's condition on the RAW outputs (no sanitization applied; spec-vocabulary in A intact, prose-style markers in B intact). **PASS iff** judge's accuracy is *above chance* with statistical significance — lower bound of 95% Wilson CI > 1/3. Proves the judge is a fair adversary that CAN detect tells.
- **Sanitize.** Apply [`harness/sanitization.py::sanitize_output`](harness/sanitization.py) to every output. (Pre-reg-locked; sanitizer changes require pre-reg supersession.)
- **Phase 2 — Blinding-leak gate.** Judge predicts each output's condition on the SANITIZED outputs. **PASS iff** judge's accuracy is at chance — 95% Wilson CI on accuracy includes 1/3. Proves the sanitization REMOVED the tells.

**Overall pass requires BOTH phases.** Fail modes:
- **Phase 1 fails** → the judge is too weak to detect even un-sanitized tells. Re-pin the judge (family rule must still hold). Phase-1 failure invalidates the judge, not the blinding.
- **Phase 2 fails** → the blinding leaks even after sanitization. Strengthen `sanitization.py` (add more patterns), re-run from Phase 2 only — Phase 1 holds because the judge already passed fitness.

Why two phases (v7 hardening): a one-phase "at-chance" gate is ambiguous between "blinding works" and "judge too weak to detect anything." A weak judge gets ~chance regardless, which is a false pass. The positive control closes the hole — see pre-reg v6 → v7 audit-trail row #13 and project memory `calibration-positive-control` for the general rule.

The harness's MockJudge demonstrates the gate working as designed: it predicts uniformly at random, so its accuracy lands at ~chance in both phases, and the positive control correctly FAILS (a uniform-random judge isn't a fair adversary). Real Gemma should pass Phase 1 with accuracy clearly above chance (cites visible `{namespace.id}` syntax / canonical headers / "per the spec" phrasing as A-tells) and then Phase 2 should fall to chance after sanitization strips those tells.

### 7. (Then) Trial zero

After steps 1-6 land, trial zero is the first run of `python -m benchmark.harness.run_trial` with a real subject. Once that fires, **the pre-registration is frozen and any redirect of gates / B-construction / task set / judge / etc. is no longer possible**.

The trial sweep itself: 660 outputs per the pre-reg's design (3 headline task types × 2 games × 20 N × 2 conditions = 240 paired per subject; plus C unpaired 60 × 2 subjects; plus 5 × 2 × 3 easy = 30 per subject; × 2 subjects = 660). At real instrument speeds (~30s per Qwen invocation, ~10s per Claude invocation, average), a serial sweep takes ~9 hours; parallelization across cells trivially possible.

## Discipline reminders

Two specific cautions from the user's review of v6 + Game #2 authoring:

**Intent checklists are about game behavior, not spec-structure.** A criterion like "implements the recipe tree from the brief" is neutral; a criterion like "uses a state machine for the world clock" silently rewards the A-condition output for being spec-shaped and tilts the headline. The 8 task definitions in `benchmark/tasks/` have been authored under this discipline; any future criterion addition should pass the same test. See the `notes:` field on each task for the specific phrasing choices made.

**C-prompts get the same good-faith standard as B.** The B-fairness audit (Layer 3) enforces "fair brief, not strawman" on the flattened B with a score-≥-4 gate; the C-prompts in `benchmark/c-prompts/` have been written to the same standard (a genuine minimal description of the game, not an impoverished one-liner). C only feeds the secondary A-vs-C and B-vs-C comparisons, but a strawman C inflates those contexts and muddies the headline's surroundings.

## Where the next checkpoint lives

Per the user's standing direction, the next checkpoint is *"calibration has passed for both instruments and trial zero is genuinely ready to fire, with the pre-registration commit standing behind it untouched."* That means:

- Steps 1-3 above (judge + Qwen + Claude wired up) committed.
- Step 4 (fairness audit) run and passed for both games; flattener SHA frozen.
- Step 5 (instrument calibration) run and passed for both bundles.
- Step 6 (blinding-leak calibration) run and passed.
- No edits to the pre-reg (`27a4381`) — the gate stands.

At that point the harness is loaded, calibrated, and waiting; the only thing left is the `run_trial` invocation that fires trial zero.
