# `benchmark/` — Phase 5 help-benchmark scaffolding

> The harness for the Phase 5 help-benchmark whose pre-registration is locked at the v9 commit (chain: `f76f4c2 → a9425e8 → 77ae3a5 → 78f150c → 766e07b → 27a4381 → 4d322bf → f996187 → 94938ed → <v9 commit>`). See [`docs/v0.2-phase5-pre-registration.md`](../docs/v0.2-phase5-pre-registration.md) for the locked gate, [`docs/v0.2-phase5-help-benchmark-scope.md`](../docs/v0.2-phase5-help-benchmark-scope.md) for the framing.

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
    content_preservation.py  # v8: sanitizer's positive control + anchor library
    sanitization.py       # v7+: SHA-locked sanitizer (applied at trial scoring + calibration)
    run_trial.py          # Main trial entry point (sanitizes before scoring at v8)
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
| Blinding-leak calibration | **Mock-only** | Two-phase code path works with MockJudge (correctly fails Phase 1 as designed; v8 bumped N to 90). Real calibration is blocked on judge wiring. |
| Content-preservation calibration (v8) | **Mock-only** | Sanitizer's positive control. Anchor library at `harness/content_preservation.py` (3 correct + 3 incorrect per game on the easy task). MockJudge correctly fails Phase A (length heuristic can't read correctness). Real calibration is blocked on judge wiring. |
| Sanitizer (v9) | **Done** (content-general) | Every rule labeled (S) structural or (E) closed-enumeration drawn from the spec's declared vocabulary — NOT from observed calibration samples. Closes the train/test distribution-shift hole: a closed enumeration of the spec's namespaces, headers, and reference-phrases generalizes to any A-tell the spec offers, not just those observed in calibration. See [`harness/sanitization.py`](harness/sanitization.py) docstring. |
| Sanitizer-generalization check (v9) | **Mock-ready** | `check_blinding_generalization()` in `harness/calibration.py` runs the Phase-2 at-chance check on REAL trial outputs (not calibration anchors). Two timepoints: pre-sweep small-batch (N=12–30, before full sweep — catches generalization failure after ~20 trials instead of ~660) and post-hoc full-sweep sample (N=60–120, recorded alongside F-009). Real run blocked on instrument + judge wiring. |
| ClaudeInstrument wiring | **Done** (Claude Code CLI, Opus 4.7 xhigh) | `ClaudeInstrument.complete()` invokes `claude --print --max-turns 5 --no-session-persistence --output-format json --model claude-opus-4-7 --effort xhigh --system-prompt <sys+anti-flailing> --tools ""` in a fresh tempdir per call, prompt on stdin. Canonical-name pin (not alias) locks the model generation; xhigh effort matches the pre-reg's frontier-capability framing. No API key — uses the user's existing Claude Code login. Bundle declaration + CLI version pin are the harness-build commits. |
| Trial runs | **Mock-only** | One mock trial smoke-tested end-to-end. At v8, every trial sanitizes the subject output before any judge call (matches-intent + checklist grader both score the sanitized form); the trial record carries raw + sanitized + sanitization SHA. Real trials are blocked on Qwen + Gemma judge wiring (Claude instrument is wired). |

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

**Pinned to `claude-opus-4-7` at `--effort xhigh`** (the frontier capability tier in the Claude lineup at the time of trial zero) and wired via the **Claude Code CLI in headless mode** (NOT the Anthropic API). Uses the user's existing Claude Code subscription — no API key needed, no SDK dependency.

**Why frontier capability (and not the `opus` alias).** The pre-reg's framing of the Claude probe (§"Test subjects", line 133) is *"Tests how spec-helpfulness varies with model capability tier"* — the three named outcomes (Claude lift > / ≈ / < Qwen lift) all interpret meaningfully ONLY when the Claude side runs on a frontier model. Pinning a smaller-tier Claude (Sonnet, Haiku) would collapse "Claude lift < Qwen lift" into "this small Claude also needed the scaffold," which is uninterpretable as the capability-inference claim the probe is for. Opus 4.7 at `xhigh` is the strongest signal available through Claude Code; escalation to `--effort max` is a redirect-window decision if calibration shows xhigh leaves signal on the table. We request the **canonical name `claude-opus-4-7`** (not the `opus` alias) so the request itself locks the model generation — the alias would silently resolve to Opus 4.8 once Anthropic releases it, mid-sweep. The actually-served model version is still captured per-call in `instrument_extra.claude_code_served_models` (from Claude Code's `modelUsage` response field), and the requested effort tier in `instrument_extra.claude_code_effort_requested`, as audit backstops for any future point-release rotation behind the canonical name.

**Contamination isolation is the load-bearing fix.** Running `claude` inside the project repo would auto-load `~/.claude/projects/-home-bantarus-DEV-game-design/memory/MEMORY.md`, which contains the entire design history of this benchmark (spec rationale, findings, pre-reg discipline). That would hand the subject the spec via memory in every condition — fatal for A-vs-B-vs-C comparability. The fix: every subprocess invocation runs in a **fresh temporary directory outside the repo** (`tempfile.TemporaryDirectory()` per call), so:

- No `CLAUDE.md` in scope (cwd is empty; tempdir ancestors `/tmp`, `/` have none).
- No `.claude/` in scope.
- No `~/.claude/projects/<cwd-hash>/memory/MEMORY.md` to load (the tempdir's path-hash has no memory dir).

**Why not `--bare`?** Bare mode would force `ANTHROPIC_API_KEY` per `claude --help` ("Anthropic auth is strictly ANTHROPIC_API_KEY or apiKeyHelper via --settings (OAuth and keychain are never read)") — losing the subscription path entirely. Isolated-cwd keeps the subscription while neutralizing contamination.

**Invocation contract** (verified empirically; see [verify_claude_isolation.py](harness/verify_claude_isolation.py)):
- `cwd = <fresh tempdir per call>` (the contamination fix)
- `--print` (non-interactive)
- `--system-prompt <text>` (**replaces** Claude Code's default agentic system prompt — verified by a haiku-only-bot probe that produced haiku responses, not normal answers; NOT `--append-system-prompt`)
- `--tools ""` (disable all built-in tools)
- `--no-session-persistence` (no JSONL session log written)
- `--max-turns 5` (NOT 1 — Claude is heavily agentic-trained and may attempt a tool call even with `--tools ""`; one additional turn lets it recover with a text-only response; cross-subject comparability is at the metric level, not turn-count level)
- `--output-format json` (structured response with token counts + duration + cost)
- `--model claude-opus-4-7` (the canonical pinned name, not the `opus` alias — locks the model generation; served version is captured per-call via Claude Code's `modelUsage` for audit)
- `--effort xhigh` (the named effort tier just below `max`; required for the frontier-capability framing; captured per-call as `instrument_extra.claude_code_effort_requested`)
- Prompt passed via stdin (avoids shell-quoting issues for long design contexts)

**Required isolation smoke test before this counts as wired.** Run [verify_claude_isolation.py](harness/verify_claude_isolation.py) — 4 probes that only the project memory or repo content could answer (fresh-game name, decision D-018, v8 pre-reg supersession content, the five invariant kinds). **Grader semantics**: each probe's `truth_signals` ARE tokens from the canonical correct answer (not heuristic leak proxies); `leak_detected` fires only when ≥ `min_signals` of those truth-tokens appear in the response. The grader asks *"did the subject reproduce the fact?"* (truth-anchor), not *"did the subject answer at all?"* (production-anchor) — robust to refusals, confident confabulations, and model swaps. A correctly-isolated subject MUST NOT produce correct project-specific answers. Latest run after the Opus-4.7 xhigh model swap: **4/4 PASS** (all probes returned clean "I don't know" / "I don't have access" deferrals — zero truth-token matches).

Treat a leak the same way you'd treat a failed calibration gate: stop, fix the wiring, re-run.

**Residual confound (split — recorded in F-009 transfer-probe limitations).** Even isolated, Claude runs through the Claude Code harness. Two separable overheads with different consequences:

- **STATIC overhead** (constitution / safety / tool descriptions / MCP enumeration: re-measured at the Opus-4.7 xhigh swap as **~200 input tokens** above the user-supplied prompt per call, with `cache_creation_input_tokens` and `cache_read_input_tokens` both 0 in Claude Code's per-call accounting — the earlier 2k–4.5k Haiku-era figure was a cache-creation artifact of a prior Claude Code version and does NOT transfer). Prompt-independent → constant across A/B/C → **per-subject headline McNemar UNAFFECTED**. Pads cost-lift denominator by a small constant within Claude (an order of magnitude smaller than was assumed pre-swap, so the caveat is structurally weaker, not stronger). Cross-subject lift-magnitude comparisons carry this static delta; named in F-009 transfer-probe caveats. No mitigation needed.
- **DYNAMIC overhead** (agentic-flailing: Claude attempts denied tool calls). **Prompt-dependent** → potentially divergent across A/B/C → could regime-distort the within-Claude **cost-lift gate** (one of two headline gates). Mitigation: (1) `ClaudeInstrument.CLAUDE_ANTI_FLAILING_SUFFIX` ("tools are disabled... respond with the implementation directly as text") appended to every Claude system prompt — cuts flailing at the source. (2) `--max-turns 5` lets Claude recover from residual tool-attempts. (3) **Post-trial regime-constancy check** [`harness/regime_constancy.py`](harness/regime_constancy.py): per-(subject, condition) distributions of `num_turns`, tokens, cost, stop_reason, error rate; advisory flags at 2x cell-mean ratio or 10pp error-rate spread within a subject. Run on the pre-sweep batch AND post-hoc on the full sweep; turns the within-Claude regime-constancy assumption into a measured fact.

**`error_max_turns` handling rule (pre-registered).** Trials that hit `subtype: error_max_turns` even at 5 turns **count as failures** (no exclusion, no retry — both would be condition-dependent and bias the headline). Per-condition error rates are recorded in `instrument_extra` on every `TrialRecord` and reported with F-009 via the regime-constancy artifact.

**Global config audit:** no `~/.claude/CLAUDE.md` exists, skills/plugins/MCPs are unrelated to the spec — no spec-specific config leak.

**Seed handling.** Claude Code does NOT accept a seed parameter. The `seed` argument is recorded on every `InstrumentResponse` for audit-trail purposes (per pre-reg §11 "auditability is recorded, not gated") but does NOT deterministically reproduce. Same-seed re-runs will diverge; expected and accepted per the v4 layer-confusion correction (the benchmark needs sampled variance, not byte-identical reproducibility).

To wire up:
1. Verify `claude --version` works on your system (`DRIFTWOOD_CLAUDE_CODE_BIN` defaults to `claude` from PATH).
2. Run `claude` once interactively if not already authenticated.
3. The `ClaudeInstrument.complete()` implementation in [`harness/instrument.py`](harness/instrument.py) and the pinned `CLAUDE_TRANSFER_PROBE_BUNDLE` are already wired.
4. Run the isolation smoke test: `python -m benchmark.harness.verify_claude_isolation`. Must report **4/4 ok** before trial-zero readiness.
5. Update the bundle's `inference_engine` field if the Claude Code CLI version changes from `2.1.143`. The `model_name` is pinned to the canonical `claude-opus-4-7` (no alias); served versions are captured per-call as the audit backstop. The `--effort xhigh` request is also captured per-call as `instrument_extra.claude_code_effort_requested`.

Optional env vars:
- `DRIFTWOOD_CLAUDE_CODE_BIN` — path to the `claude` binary (default: PATH lookup).
- `DRIFTWOOD_CLAUDE_CODE_TIMEOUT_SECONDS` — per-invocation timeout (default: 300).

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

### 6. Run blinding-leak calibration on the pinned judge — TWO PHASES (pre-reg v7 §"Judge" Layer 3, N bumped at v8)

```
python -m benchmark.harness.run_blinding_leak_calibration \
    --instrument qwen --task easy --game platformer
```

(Stub entrypoint.)

**N=90 outputs (30 per A/B/C)** on the easy_platformer task. (v7's N=30 had a wide enough Wilson CI that "includes 1/3" only ruled out a *large* leak; v8 bumped to 90 to catch ~10pp-or-larger residual leaks — half-width ~0.10 near p=0.5. The 90 outputs are generated once via the instrument; both phases re-score the same 90, so the marginal cost over v7 is one extra scoring pass on stored text.)

**Two-phase gate per pre-reg v7:**

- **Phase 1 — Positive control / judge fitness.** Judge predicts each output's condition on the RAW outputs (no sanitization applied; spec-vocabulary in A intact, prose-style markers in B intact). **PASS iff** judge's accuracy is *above chance* with statistical significance — lower bound of 95% Wilson CI > 1/3. Proves the judge is a fair adversary that CAN detect tells.
- **Sanitize.** Apply [`harness/sanitization.py::sanitize_output`](harness/sanitization.py) to every output. (Pre-reg-locked; sanitizer changes require pre-reg supersession.)
- **Phase 2 — Blinding-leak gate.** Judge predicts each output's condition on the SANITIZED outputs. **PASS iff** judge's accuracy is at chance — 95% Wilson CI on accuracy includes 1/3. Proves the sanitization REMOVED the tells.

**Overall pass requires BOTH phases.** Fail modes:
- **Phase 1 fails** → the judge is too weak to detect even un-sanitized tells. Re-pin the judge (family rule must still hold). Phase-1 failure invalidates the judge, not the blinding.
- **Phase 2 fails** → the blinding leaks even after sanitization. Strengthen `sanitization.py` (add more patterns), re-run from Phase 2 only — Phase 1 holds because the judge already passed fitness. **Counterweighted by step 6b below: tuning sanitization toward more stripping must not destroy content the matches-intent judge needs at trial time.**

Why two phases (v7 hardening): a one-phase "at-chance" gate is ambiguous between "blinding works" and "judge too weak to detect anything." A weak judge gets ~chance regardless, which is a false pass. The positive control closes the hole — see pre-reg v6 → v7 audit-trail row #13 and project memory `calibration-positive-control` for the general rule.

The harness's MockJudge demonstrates the gate working as designed: it predicts uniformly at random, so its accuracy lands at ~chance in both phases, and the positive control correctly FAILS (a uniform-random judge isn't a fair adversary). Real Gemma should pass Phase 1 with accuracy clearly above chance (cites visible `{namespace.id}` syntax / canonical headers / "per the spec" phrasing as A-tells) and then Phase 2 should fall to chance after sanitization strips those tells.

### 6b. Run content-preservation calibration — TWO PHASES (pre-reg v8 §"Judge" Layer 3b)

```
python -m benchmark.harness.run_content_preservation_calibration
```

(Stub entrypoint.)

The sanitizer's positive control. Step 6 above pressures sanitization toward more aggressive stripping (judge at chance is easier when there's less to read); step 6b is the counterweight that prevents over-stripping from passing the gate vacuously by destroying content. **Both calibrations must pass before trial zero** — a sanitization function passes the v8 apparatus iff it lands in the joint pass region of step 6 (tells removed) AND step 6b (content preserved).

The matches-intent judge (same `score_matches_intent` rubric used at trial scoring time) scores K=3 known-correct + K=3 known-incorrect pre-authored anchors per (game, calibration task) set. Anchors are committed in [`harness/content_preservation.py`](harness/content_preservation.py) — correct anchors span A/B/C styles (so the gate measures content recognition, not style recognition); incorrect anchors span failure modes (off-topic / hand-waving / wrong-on-specifics).

**Phase A — Anchor sanity check** (on RAW anchors). Pass iff `median(correct, raw) ≥ 4` AND `median(incorrect, raw) ≤ 2` AND `raw_gap ≥ 3`, per set. Validates that the anchors are discriminably authored. A Phase-A fail per set means the anchors must be re-authored (re-pin in a pre-reg cycle); Phase-A fail invalidates the *anchors*, not the sanitization.

**Phase B — Content preservation** (on SANITIZED anchors). Pass iff `median(correct, sanitized) ≥ 3` AND `sanitized_gap ≥ 2`, per set. Validates that sanitization preserved enough discriminative signal for the matches-intent judge to still distinguish correct from incorrect anchors. A Phase-B fail per set means the sanitizer is destroying content for that set; tune the sanitizer down in a pre-reg cycle, re-run Phase B only (Phase A holds because the anchors are unchanged); Phase-B fail invalidates the *sanitization*, not the anchors.

**Overall pass requires every per-set result to have both phases passing.**

The harness's MockJudge demonstrates the gate working as designed: it scores by length (not content), so its raw median(correct) and median(incorrect) collapse to similar values and Phase A correctly fails (anchor sanity can't hold against a content-blind judge). A real Gemma judge should pass Phase A with a clear raw gap and then maintain a smaller-but-still-present sanitized gap in Phase B.

See pre-reg v7 → v8 audit-trail row #15 for the rationale and project memory `sanitizer-content-preservation` for the general "every sanitization-style gate needs a content-preservation counterweight" rule.

### 6c. Run sanitizer-generalization check on a pre-sweep small batch (pre-reg v9 §"Judge" Layer 3c)

```
python -m benchmark.harness.run_generalization_check --label pre_sweep
```

(Stub entrypoint.)

**Steps 6 and 6b validate the sanitizer on the calibration sample (90 outputs) + the anchor library (12 anchors). They do NOT validate that the sanitizer generalizes to the ~660-trial production population, which neither calibration ever saw.** v9 closes that gap two ways: (a) the sanitizer is content-general by construction (every rule structural or closed-enumeration drawn from spec vocabulary — see [`harness/sanitization.py`](harness/sanitization.py) docstring); (b) a positive verification on real trial outputs runs at two timepoints. This step is the first timepoint.

After step 11 (instrument calibration) has passed but BEFORE the full trial sweep (step 7 below), generate a **small batch of real trials** — a handful per condition per game, total **N=12–30**. Apply the SHA-locked sanitization. Run the condition-prediction judge (same Layer 3 judge) on the sanitized outputs. **Pass criterion identical to step 6 Phase 2:** 95% Wilson CI on judge accuracy includes 1/3 (predictions at chance).

Wilson CI is wide at small N — this is an early-warning flag, not a statistical guarantee. An above-chance accuracy here is a strong signal of generalization failure. **Pre-sweep fail → do NOT proceed to the full sweep.** Strengthen the sanitizer in a pre-reg supersession (re-runs step 6 Phase 2 + step 6b Phase B + this check); re-evaluate.

The whole apparatus is "judge predictions on stored text" — nearly free relative to the full ~9-hour trial sweep. Catches sanitizer leaks on the trial population after ~20 trials instead of after ~660.

See pre-reg v8 → v9 audit-trail row #17 and project memory `train-test-distribution-shift-sanitizer` for the standing rule.

### 7. (Then) Trial zero, with post-hoc generalization check (pre-reg v9)

After steps 1-6c land, trial zero is the first run of `python -m benchmark.harness.run_trial` with a real subject. Once that fires, **the pre-registration is frozen and any redirect of gates / B-construction / task set / judge / etc. is no longer possible**.

The trial sweep itself: 660 outputs per the pre-reg's design (3 headline task types × 2 games × 20 N × 2 conditions = 240 paired per subject; plus C unpaired 60 × 2 subjects [C runs at N=10 for m/h/a, the explicit reconciliation of the pre-reg's stated "60" figure — see [`harness/sweep_plan.py::C_N_PER_CELL_OVERRIDES`](harness/sweep_plan.py)]; plus 5 × 2 × 3 easy = 30 per subject; × 2 subjects = 660). At real instrument speeds (~30s per Qwen invocation, ~10s per Claude invocation, average), a serial sweep takes ~9 hours; parallelization across cells trivially possible.

**Execution-order discipline — interleaved, not blocked.** The driver MUST consume the sweep plan from [`harness/sweep_plan.py`](harness/sweep_plan.py) (CLI emits JSONL, one cell per line, in execution order):

```
python -m benchmark.harness.sweep_plan --subject claude --shuffle-seed 12345 \
  | while read cell; do
      python -m benchmark.harness.run_trial \
          --subject claude --condition $(jq -r .condition <<<"$cell") \
          --task $(jq -r .task <<<"$cell") \
          --game $(jq -r .game <<<"$cell") \
          --seed $(jq -r .seed <<<"$cell")
    done
```

The planner emits per-pair-interleaved cells with a seeded inter-unit shuffle: A_i and B_i of every paired instance run back-to-back, and the order of pairs across the sweep is randomized. This defeats the time-correlated nuisance both subjects carry — Claude rate-limit posture climbing toward the wall over a multi-hour run, and Qwen llama.cpp drift over the same. **`count-as-failure` for `error_max_turns` is unbiased ONLY under interleaved ordering**; under blocked ordering, rate-limit failures correlate with whichever condition runs late, manufacturing a spurious A-vs-B difference. The `shuffle_seed` is part of the harness-build SHA discipline; F-009 records it.

**Pre-sweep usage-watch on the Claude arm.** Opus 4.7 `--effort xhigh` is materially heavier than the Haiku-era assumption (~$0.007/call floor; bigger A trees push it higher). Watch the Claude subscription usage during the pre-sweep batch (N≈20 trials): a usage wall at N=20 is recoverable; a wall at N=300 is not. If pre-sweep batch shows the wall is plausible within the full sweep, the API key earns its keep — switching from subscription to `ANTHROPIC_API_KEY` (requires changing `--bare` to be set and re-running the isolation smoke) is the right operational redirect, not a methodology change.

**After the sweep, run the post-hoc sanitizer-generalization check (pre-reg v9 step 14).** Draw a uniform sample from the full ~660 trial records (N=60–120, distributed across conditions × games × tasks), apply the SHA-locked sanitization, run the condition-prediction judge, report the 95% Wilson CI on accuracy alongside F-009. A CI that includes 1/3 confirms generalization; a CI strictly above 1/3 is recorded as a stated F-009 limitation with the observed leak magnitude — F-009 reports the residual leak as a measured fact and does NOT retroactively re-run.

```
python -m benchmark.harness.run_generalization_check --label post_hoc --sample-n 100
```

## Discipline reminders

Three specific cautions, in chronological order of when the user surfaced them:

**Intent checklists are about game behavior, not spec-structure.** (v6 + Game #2 review.) A criterion like "implements the recipe tree from the brief" is neutral; a criterion like "uses a state machine for the world clock" silently rewards the A-condition output for being spec-shaped and tilts the headline. The 8 task definitions in `benchmark/tasks/` have been authored under this discipline; any future criterion addition should pass the same test. See the `notes:` field on each task for the specific phrasing choices made.

**C-prompts get the same good-faith standard as B.** (v6 + Game #2 review.) The B-fairness audit (Layer 3) enforces "fair brief, not strawman" on the flattened B with a score-≥-4 gate; the C-prompts in `benchmark/c-prompts/` have been written to the same standard (a genuine minimal description of the game, not an impoverished one-liner). C only feeds the secondary A-vs-C and B-vs-C comparisons, but a strawman C inflates those contexts and muddies the headline's surroundings.

**Trial-time scoring is on SANITIZED outputs only.** (v8.) Every trial sanitizes its subject output via `harness/sanitization.py::sanitize_output` once at scoring time, and BOTH judge calls — matches-intent (Layer 2) and the per-criterion checklist grader (Layer 1 when LLM-graded) — score the sanitized form. Raw subject outputs MUST NEVER reach the scoring judge. The constraint exists because the v7 two-phase blinding-leak calibration validated the judge's behavior on sanitized outputs (Phase 2: judge at chance); Phase 1 was the proof that the judge *can* read condition off raw outputs. If trials scored raw, the judge would be operating in its un-blinded mode against exactly the channel the calibration was designed to close. See pre-reg v7 → v8 audit-trail row #14 and project memory `sanitized-scoring-consistency` for the standing rule.

**Every sanitizer rule is structural or closed-enumeration from spec vocabulary — NOT from calibration samples.** (v9.) The sanitizer at [`harness/sanitization.py`](harness/sanitization.py) labels each of its nine rules as either (S) a structural pattern (regex on shape, content-agnostic) or (E) a closed enumeration drawn from `docs/spec.md` (§3 namespace ownership table; §5.2 + §7.1 canonical section headers; spec-terminology synonyms). The discipline exists because the calibration sample is N=90 but the trial population is N=660; a denylist drawn from calibration would be train-set-shaped and would leak tells appearing in trials but not in calibration. Adding rules: either generalize (structural) or enumerate from spec vocabulary, not from observed sample outputs. See pre-reg v8 → v9 audit-trail row #17 and project memory `train-test-distribution-shift-sanitizer` for the standing rule.

## Where the next checkpoint lives

Per the user's standing direction, the next checkpoint is *"calibration has passed for both instruments and trial zero is genuinely ready to fire, with the pre-registration commit standing behind it untouched."* That means:

- Steps 1-3 above (judge + Qwen + Claude wired up) committed.
- Step 4 (fairness audit) run and passed for both games; flattener SHA frozen.
- Step 5 (instrument calibration) run and passed for both bundles.
- Step 6 (blinding-leak calibration, two-phase at N=90) run and passed.
- Step 6b (content-preservation calibration, two-phase across both games' anchor sets) run and passed.
- Step 6c (sanitizer-generalization check on a pre-sweep small batch of real trial outputs) run and passed.
- No edits to the v9 pre-reg — the gate stands.

At that point the harness is loaded, all three calibration apparatuses have landed in their respective pass regions (sanitization strips enough to blind the condition-prediction judge AND preserves enough for the matches-intent judge to discriminate good from bad content AND generalizes to a small batch of real trial outputs), and the only thing left is the `run_trial` invocation that fires trial zero — followed by the post-hoc generalization check on the full sweep, recorded alongside F-009.
