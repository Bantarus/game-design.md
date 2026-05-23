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

### 1. Pin the auxiliary LLM judge (pre-reg §"Judge")

The auxiliary judge must be a non-Qwen, non-Claude-family model. The pre-reg suggests Gemini, GPT-4o, or a local Llama variant. To wire it up:

1. Choose the specific model + version + sampling params.
2. Set the API key (`GEMINI_API_KEY` or `OPENAI_API_KEY`) in the environment.
3. Implement the corresponding judge class in `harness/judge.py` (the `GeminiJudge` / `OpenAIJudge` stubs are placeholders — replace `raise NotImplementedError` with actual SDK calls).
4. Commit the bundle declaration: this freezes the judge identity.

The judge is used for THREE purposes (each requires a separate prompt template):
- **Matches-intent scoring** (the 0-5 rubric in `judge.py::IntentScore`). Prompt template: builds at trial time from `task.brief` + `subject_output` + `game_brief` (the design-brief.md).
- **Fairness audit** (Layer 3 of B-construction). Prompt template at `tools/fairness_audit_prompt.md` (frozen).
- **Blinding-leak calibration** (predict A/B/C from blinded output). Prompt template: needs to be authored as part of judge wiring; the prompt should not leak the rubric or scoring criteria.

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

### 6. Run blinding-leak calibration on the pinned judge (pre-reg §"Judge" Layer 3)

```
python -m benchmark.harness.run_blinding_leak_calibration \
    --instrument qwen --task easy --game platformer
```

(Stub entrypoint.)

N=30 outputs (10 per A/B/C) on the easy_platformer task; the judge predicts each output's condition; pass criterion is no-better-than-chance accuracy (95% CI on accuracy includes 33%).

If calibration FAILS — the judge predicts above chance — the blinding leaks. Strip spec-vocabulary from A outputs / prose-style markers from B outputs as needed; re-run calibration; trials don't count until calibration passes.

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
