"""Judge abstraction: the auxiliary LLM that scores subjective rubrics.

Per pre-reg §"Judge", the auxiliary judge MUST come from a family
**different from the spec-author AND every test subject**. At v0.2 this
excludes Qwen (Alibaba — headline subject) and Claude (Anthropic —
spec-author AND transfer-probe subject). The rule exists to eliminate
two specific contamination vectors: spec-author interpretive bias
(Claude is the spec-author) and subject overlap (Claude is the
transfer-probe; a Claude judge would partly score outputs from its own
family). Most acute at the blinding-leak calibration, where the
judge's role is adversarial.

**At v7 the pinned auxiliary judge is Gemma 4 26B A4B (Google),
local-inference via llama.cpp** — non-Qwen, non-Claude, Apache-2.0, no
API key, runs sequentially alongside the Qwen instrument in the same
llama.cpp infrastructure.

Three judge responsibilities (each with a frozen prompt template
committed in `benchmark/tools/`):

  1. Score subject outputs on the "matches intent" 0-5 rubric (Layer 2
     of the judge stack). Template: `matches_intent_prompt.md`.
  2. Audit flattened B briefs for fairness on a 1-5 rubric (Layer 3
     of B-construction). Template: `fairness_audit_prompt.md`.
  3. Predict A/B/C conditions for the blinding-leak calibration
     (pre-reg §"Judge" Layer 3, two-phase per v7).
     Template: `blinding_leak_prompt.md`.

Concrete implementations:
  - `GemmaJudge`      — v7 PIN; local-inference via llama.cpp; non-Qwen,
                         non-Claude family per the pre-reg rule. Wiring
                         pending llama.cpp subprocess + GGUF download.
  - `GeminiJudge`     — alternative family (Google API); requires API key.
  - `OpenAIJudge`     — alternative family (OpenAI); requires API key.
  - `MockJudge`       — returns canned scores; lets the harness exercise
                         end-to-end without external infra. NOT used in
                         real trials.

**Explicitly NOT included** (and forbidden by the family rule):
  - QwenJudge (Qwen is the headline subject).
  - ClaudeJudge (Claude is the spec-author AND the transfer-probe
    subject). A `ClaudeJudge` class does not exist by design; if you
    are tempted to add one for convenience, see memory
    `judge-family-independence` and the pre-reg's v6 → v7 audit-trail
    row (#12) for why this is hard-disqualified.
"""
from __future__ import annotations

import os
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class JudgeBundle:
    """The aux-judge model + version pinned at the harness-build commit."""

    family: str          # "gemini" | "openai" | "local-llama"
    model_name: str      # e.g. "gemini-2.5-pro" or "gpt-4o-2024-08-06"
    version: str         # API version or local-build identifier
    temperature: float = 0.0  # Judge runs at temp 0 for reproducibility
    notes: str = ""

    def bundle_id(self) -> str:
        return f"{self.family}/{self.model_name}/{self.version}/temp={self.temperature}"


@dataclass(frozen=True)
class IntentScore:
    """The judge's score on the 'matches intent' 0-5 rubric (pre-reg §"Judge")."""
    score: int           # 0-5 per the rubric
    rationale: str
    bundle_id: str


@dataclass(frozen=True)
class FairnessScore:
    """The judge's score on the B-construction fairness audit 1-5 rubric."""
    score: int           # 1-5 per the rubric
    rationale: str
    specific_issues: tuple[str, ...]
    bundle_id: str


@dataclass(frozen=True)
class ConditionPrediction:
    """The judge's prediction for one output during blinding-leak calibration."""
    output_id: int
    predicted_condition: str  # "A" | "B" | "C"
    confidence: float         # 0.0 - 1.0
    rationale: str


class Judge(ABC):
    def __init__(self, bundle: JudgeBundle):
        self.bundle = bundle

    @abstractmethod
    def score_matches_intent(
        self,
        task_brief: str,
        subject_output: str,
        game_brief: str,  # the neutral design-brief.md — the rubric ground truth per pre-reg
    ) -> IntentScore: ...

    @abstractmethod
    def audit_fairness(
        self,
        flattened_b_text: str,
        game_name: str,
        game_pitch: str,
    ) -> FairnessScore: ...

    @abstractmethod
    def predict_conditions(
        self,
        outputs: list[tuple[int, str]],  # [(output_id, blinded_text), ...]
    ) -> list[ConditionPrediction]: ...


# ---------------------------------------------------------------------------
# Mock judge — for harness exercise WITHOUT external infra
# ---------------------------------------------------------------------------

class MockJudge(Judge):
    """Returns deterministic-but-shape-realistic scores. Lets the harness be
    exercised end-to-end without external infra. NOT a real judge."""

    def __init__(self, bundle: JudgeBundle | None = None):
        super().__init__(bundle or JudgeBundle(
            family="mock",
            model_name="mock-judge",
            version="v0",
            notes="Returns canned scores; NOT a real judge.",
        ))

    def score_matches_intent(self, task_brief, subject_output, game_brief) -> IntentScore:
        # Score-by-length heuristic so the mock is deterministic and varies
        # plausibly across mock outputs. Real-judge scores will vary by
        # rubric-aware reasoning.
        s = 3
        if len(subject_output) > 500:
            s = 4
        if len(subject_output) > 2000 and "rationale" in subject_output.lower():
            s = 5
        return IntentScore(score=s, rationale="[MOCK] heuristic score by length.", bundle_id=self.bundle.bundle_id())

    def audit_fairness(self, flattened_b_text, game_name, game_pitch) -> FairnessScore:
        # Mock fairness audit: PASS if the flat brief is at least 500 lines long
        # and contains the game's name and pitch. Real audits will read the prose.
        score = 5 if (game_name in flattened_b_text and game_pitch in flattened_b_text and len(flattened_b_text) > 5000) else 2
        return FairnessScore(
            score=score,
            rationale=f"[MOCK] passes-on-length-and-name heuristic ({len(flattened_b_text)} chars).",
            specific_issues=(),
            bundle_id=self.bundle.bundle_id(),
        )

    def predict_conditions(self, outputs) -> list[ConditionPrediction]:
        # Mock: predict each output uniformly at random with seed=output_id
        preds: list[ConditionPrediction] = []
        for oid, text in outputs:
            rng = random.Random(oid)
            choice = rng.choice(["A", "B", "C"])
            preds.append(ConditionPrediction(
                output_id=oid,
                predicted_condition=choice,
                confidence=1.0 / 3.0,
                rationale="[MOCK] uniform-random prediction.",
            ))
        return preds


# ---------------------------------------------------------------------------
# Real judges — stubbed
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Gemma judge — V7 PIN; local-inference via llama.cpp; no API key
# ---------------------------------------------------------------------------

# The pre-registered Gemma judge bundle. The model_name + variant + family
# are pinned at the pre-reg level (v7 commit). The quant + gguf_sha256 +
# inference_engine version + sampling_params + chat_template are pinned at
# the harness-build commit (filled in when the GGUF is downloaded and the
# llama.cpp binary is built). Any change to ANY field is a new pre-reg cycle
# per §"Test subjects" bundle discipline applied to the judge.
GEMMA_JUDGE_BUNDLE = JudgeBundle(
    family="gemma",
    model_name="gemma-4-26b-a4b",  # Google Gemma 4, 26B-A4B MoE variant
    version="TBD-at-harness-build",  # quant + GGUF SHA + llama.cpp version
    temperature=0.0,  # Judge runs at temp 0 for reproducibility
    notes=(
        "v7 PIN. Non-Qwen, non-Claude family per pre-reg §Judge family rule. "
        "Local-inference via llama.cpp; no API key required. Runs sequentially "
        "alongside the Qwen instrument (not concurrent — judge has full GPU "
        "during scoring pass). The full bundle (quant, GGUF SHA, llama.cpp "
        "version, sampling params, chat template) is finalized at the "
        "harness-build commit, and that commit's SHA is recorded as the "
        "judge bundle's lock."
    ),
)


class GemmaJudge(Judge):
    """V7 PIN: Gemma 4 26B A4B via local llama.cpp. No API key.

    Requires:
      - Local llama.cpp build (record the git SHA / release tag in the bundle).
      - The Gemma GGUF file at a known path (SHA-256 recorded in bundle).
      - The three judge prompt templates (committed in benchmark/tools/):
          - matches_intent_prompt.md
          - fairness_audit_prompt.md
          - blinding_leak_prompt.md

    The harness invokes the same llama.cpp binary it uses for Qwen, but
    SEQUENTIALLY — generation pass first (Qwen + Claude write all trial
    outputs to per-trial JSON), then a separate scoring pass loads the
    Gemma GGUF and reads back the outputs to score. Generation and
    scoring never compete for VRAM.

    Env vars at runtime:
      - DRIFTWOOD_GEMMA_GGUF_PATH — path to the Gemma GGUF.
      - DRIFTWOOD_LLAMA_CPP_BIN  — path to the llama.cpp binary
                                    (same binary as the Qwen instrument).

    Stub status: bundle is pinned (the family + base model are normative
    per pre-reg v7); the subprocess invocation is the remaining wire-up.
    """

    def __init__(self, bundle: JudgeBundle = GEMMA_JUDGE_BUNDLE):
        super().__init__(bundle)
        self._gguf_path = os.environ.get("DRIFTWOOD_GEMMA_GGUF_PATH")
        self._llama_cpp_bin = os.environ.get("DRIFTWOOD_LLAMA_CPP_BIN")

    def score_matches_intent(self, task_brief, subject_output, game_brief) -> IntentScore:
        if not (self._gguf_path and self._llama_cpp_bin):
            raise NotImplementedError(
                "GemmaJudge requires DRIFTWOOD_GEMMA_GGUF_PATH and "
                "DRIFTWOOD_LLAMA_CPP_BIN env vars + a wired-up subprocess call. "
                "Load the prompt template from "
                "`benchmark/tools/matches_intent_prompt.md`, fill in "
                "task_brief / subject_output / game_brief, invoke llama.cpp, "
                "parse the JSON response per the template's output spec. "
                "Stub pending external infra; see benchmark/README.md."
            )
        # TODO: load matches_intent_prompt.md template; substitute; invoke
        # llama.cpp via subprocess; parse JSON; return IntentScore.
        raise NotImplementedError("GemmaJudge.score_matches_intent stub; wire up llama.cpp.")

    def audit_fairness(self, flattened_b_text, game_name, game_pitch) -> FairnessScore:
        if not (self._gguf_path and self._llama_cpp_bin):
            raise NotImplementedError(
                "GemmaJudge requires DRIFTWOOD_GEMMA_GGUF_PATH and "
                "DRIFTWOOD_LLAMA_CPP_BIN env vars. Load prompt from "
                "`benchmark/tools/fairness_audit_prompt.md`."
            )
        raise NotImplementedError("GemmaJudge.audit_fairness stub; wire up llama.cpp.")

    def predict_conditions(self, outputs) -> list[ConditionPrediction]:
        if not (self._gguf_path and self._llama_cpp_bin):
            raise NotImplementedError(
                "GemmaJudge requires DRIFTWOOD_GEMMA_GGUF_PATH and "
                "DRIFTWOOD_LLAMA_CPP_BIN env vars. Load prompt from "
                "`benchmark/tools/blinding_leak_prompt.md`."
            )
        raise NotImplementedError("GemmaJudge.predict_conditions stub; wire up llama.cpp.")


# ---------------------------------------------------------------------------
# Alternative-family judges (API-based, not the v7 pin)
# ---------------------------------------------------------------------------

class GeminiJudge(Judge):
    """Google Gemini-family aux judge (API). Requires GEMINI_API_KEY.

    NOT the v7 pin — Gemma (local, same family but different model + no
    API key) is the v7 pin. GeminiJudge remains as an alternative if a
    future Phase-5+ revision changes the pin AND you need API-grade
    Google models specifically.
    """

    def __init__(self, bundle: JudgeBundle):
        super().__init__(bundle)
        self._api_key = os.environ.get("GEMINI_API_KEY")

    def score_matches_intent(self, task_brief, subject_output, game_brief) -> IntentScore:
        if not self._api_key:
            raise NotImplementedError("GeminiJudge requires GEMINI_API_KEY env var. Stub.")
        # TODO: build prompt from rubric in pre-reg §"Judge" (the 0-5 scale);
        # send game_brief as ground-truth context, subject_output as scored,
        # task_brief as task framing. Parse JSON response.
        raise NotImplementedError("GeminiJudge.score_matches_intent stub.")

    def audit_fairness(self, flattened_b_text, game_name, game_pitch) -> FairnessScore:
        if not self._api_key:
            raise NotImplementedError("GeminiJudge requires GEMINI_API_KEY env var. Stub.")
        # TODO: load benchmark/tools/fairness_audit_prompt.md, fill in
        # game_name/game_pitch/flat_text, send to Gemini, parse JSON response.
        raise NotImplementedError("GeminiJudge.audit_fairness stub.")

    def predict_conditions(self, outputs) -> list[ConditionPrediction]:
        if not self._api_key:
            raise NotImplementedError("GeminiJudge requires GEMINI_API_KEY env var. Stub.")
        raise NotImplementedError("GeminiJudge.predict_conditions stub.")


class OpenAIJudge(Judge):
    """OpenAI GPT-family aux judge. Requires OPENAI_API_KEY."""

    def __init__(self, bundle: JudgeBundle):
        super().__init__(bundle)
        self._api_key = os.environ.get("OPENAI_API_KEY")

    def score_matches_intent(self, task_brief, subject_output, game_brief) -> IntentScore:
        if not self._api_key:
            raise NotImplementedError("OpenAIJudge requires OPENAI_API_KEY env var. Stub.")
        raise NotImplementedError("OpenAIJudge.score_matches_intent stub.")

    def audit_fairness(self, flattened_b_text, game_name, game_pitch) -> FairnessScore:
        if not self._api_key:
            raise NotImplementedError("OpenAIJudge requires OPENAI_API_KEY env var. Stub.")
        raise NotImplementedError("OpenAIJudge.audit_fairness stub.")

    def predict_conditions(self, outputs) -> list[ConditionPrediction]:
        if not self._api_key:
            raise NotImplementedError("OpenAIJudge requires OPENAI_API_KEY env var. Stub.")
        raise NotImplementedError("OpenAIJudge.predict_conditions stub.")
