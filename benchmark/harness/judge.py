"""Judge abstraction: the auxiliary LLM that scores subjective rubrics.

Per pre-reg §"Judge", the auxiliary judge is pinned to a non-Qwen,
non-Claude-family model (Gemini, GPT-4o, or a local Llama variant; the
specific model is pinned at the harness-build commit). Its responsibilities:

  1. Score subject outputs on the "matches intent" rubric (Layer 2 of
     the judge stack) — the irreducible subjective remainder after the
     objective intent checklist is machine-scored.
  2. Audit flattened B briefs for fairness (Layer 3 of B-construction,
     using `benchmark/tools/fairness_audit_prompt.md`).
  3. Run the blinding-leak calibration (predict which condition each
     of 30 outputs came from; pre-reg §"Judge" Layer 3).

Concrete implementations are stubbed pending external infra:
  - `GeminiJudge`     — requires Google Gemini API access.
  - `OpenAIJudge`     — requires OpenAI API access.
  - `LocalLlamaJudge` — requires local Llama inference setup.
  - `MockJudge`       — returns canned scores; lets the harness exercise
                         end-to-end without external infra.
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

class GeminiJudge(Judge):
    """Google Gemini-family aux judge. Requires GEMINI_API_KEY."""

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
