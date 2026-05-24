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

import json
import os
import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


# Prompt-template directory. The three judge templates are committed
# verbatim and load on demand; their SHAs are part of the harness-build
# audit trail (recorded per pre-reg §"Judge" Layer 3a/3b/3c).
TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
_PROMPT_TEMPLATES: dict[str, str] = {}


def _load_template(name: str) -> str:
    """Read and cache a prompt template by filename stem (without .md)."""
    if name not in _PROMPT_TEMPLATES:
        path = TOOLS_DIR / f"{name}.md"
        _PROMPT_TEMPLATES[name] = path.read_text()
    return _PROMPT_TEMPLATES[name]


def _extract_json_object(text: str) -> dict:
    """Pull the first complete JSON object out of `text`.

    Local LLMs sometimes wrap JSON in markdown fences (```json ... ```)
    or prepend an explanation despite "respond with exactly this JSON"
    instructions. This helper is tolerant of both; it scans for the
    first '{', tracks brace depth (respecting string literals), and
    parses what it finds.
    """
    # Try a clean parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip a leading ```json fence + trailing ```
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))

    # Brace-balanced scan
    start = text.find("{")
    if start < 0:
        raise ValueError(f"no JSON object found in judge response: {text[:300]!r}")
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:i+1])
    raise ValueError(
        f"unbalanced braces in judge response (depth={depth}): {text[start:start+300]!r}"
    )


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
# this harness-build commit (filled when the GGUF was downloaded and the
# llama.cpp binary was verified). Any change to ANY field is a new pre-reg
# cycle per §"Test subjects" bundle discipline applied to the judge.
#
# Distribution: unsloth/gemma-4-26B-A4B-it-GGUF on HuggingFace
# (Apache-2.0). Quant: UD-Q4_K_M (16.9 GB; UD = Unsloth Dynamic, imatrix-
# improved). The reference download is via benchmark/tools/download_ggufs.sh;
# the GGUF SHA-256 below was computed by sha256sum after the download.
GEMMA_JUDGE_BUNDLE = JudgeBundle(
    family="gemma",
    model_name="gemma-4-26B-A4B-it",  # Google Gemma 4 26B-A4B Instruct
    version=(
        "unsloth-gguf/UD-Q4_K_M/"
        "sha256:34c746b1d50ab813e29cd46c4796e3f43c741901a582f93a67b55b9fc9687b35/"
        "llama.cpp-b9306-5d246a7"
    ),
    temperature=0.0,  # Judge runs at temp 0 for reproducibility
    notes=(
        "v7 PIN. Non-Qwen, non-Claude family per pre-reg §Judge family rule. "
        "Local-inference via llama-server (harness/llama_server.py); no API "
        "key required. Runs sequentially alongside the Qwen instrument "
        "(NOT concurrent — judge has full GPU during scoring pass). Three "
        "responsibilities: matches_intent_prompt.md (Layer 2 of judge stack), "
        "fairness_audit_prompt.md (Layer 3 of B-construction), "
        "blinding_leak_prompt.md (Layer 3 of judge calibration). Source: "
        "unsloth/gemma-4-26B-A4B-it-GGUF (HuggingFace), UD-Q4_K_M GGUF, "
        "SHA-256 pinned in `version`. llama.cpp build SHA 5d246a7 "
        "(version 9306), CUDA-enabled, RTX 4090. (Build advanced from "
        "b8628/fbd441c at this harness-build commit because the older "
        "build lacked `gemma4` architecture support.) Reasoning mode "
        "DISABLED (`--reasoning off`) so the judge emits the locked "
        "JSON envelope directly, instead of routing through an internal "
        "think→answer split that would multiply per-call wall by 10-30× "
        "with marginal scoring-quality improvement. The choice is a "
        "sampling/server parameter; pre-reg v7 family pin is unaffected."
    ),
)


class GemmaJudge(Judge):
    """V7 PIN: Gemma 4 26B A4B Instruct via local llama-server. No API key.

    Wired through [`benchmark/harness/llama_server.py`](llama_server.py).
    The server is loaded once on first method-call, reused across all
    judge invocations for the lifetime of this instance, and released
    on close() / context-manager exit. The Qwen and Gemma servers MUST
    NOT run concurrently — they each want the full RTX 4090 VRAM — so
    the driver is responsible for closing Qwen before opening Gemma:

        with QwenInstrument(QWEN_HEADLINE_BUNDLE) as inst:
            # all 330 Qwen trials run here, instrument outputs written to
            # benchmark/harness/trials/...
            ...
        # Qwen unloaded → VRAM free
        with GemmaJudge(GEMMA_JUDGE_BUNDLE) as judge:
            # judge reads back stored outputs and scores them
            ...

    Three responsibilities (each from a frozen prompt template):
      - score_matches_intent  — `matches_intent_prompt.md`
      - audit_fairness        — `fairness_audit_prompt.md`
      - predict_conditions    — `blinding_leak_prompt.md`

    Env vars at runtime:
      - DRIFTWOOD_GEMMA_GGUF_PATH — path to the Gemma GGUF.
      - DRIFTWOOD_LLAMA_CPP_BIN  — path to llama-server (default
                                    ~/llama.cpp/build/bin/llama-server).

    The server runs on a different port from Qwen's by default (8081 vs
    8080), so a misconfigured driver that left Qwen running would fail
    fast at start() rather than VRAM-OOM at first chat. Override via
    the `port=` kwarg.
    """

    def __init__(
        self,
        bundle: JudgeBundle = GEMMA_JUDGE_BUNDLE,
        *,
        server: "LlamaServer | None" = None,
        gguf_path: str | None = None,
        port: int = 8081,
        max_tokens: int = 2048,
    ):
        super().__init__(bundle)
        self._gguf_path = (
            gguf_path
            or os.environ.get("DRIFTWOOD_GEMMA_GGUF_PATH")
        )
        if not self._gguf_path:
            raise RuntimeError(
                "GemmaJudge needs DRIFTWOOD_GEMMA_GGUF_PATH set (or pass "
                "gguf_path=... explicitly). The pinned GGUF lives at the path "
                "computed by benchmark/tools/download_ggufs.sh."
            )
        self._server = server
        self._owns_server = server is None
        self._port = port
        self._max_tokens = max_tokens

    def _ensure_server(self) -> "LlamaServer":
        if self._server is None:
            from .llama_server import LlamaServer
            # Gemma 4 26B A4B is a reasoning-enabled model by default; the
            # default `--reasoning auto` mode routes generation through an
            # internal think→answer split that, with a finite max_tokens
            # budget, consumes the budget on the think trace before
            # emitting the answer. For our judge use the answer (a
            # structured JSON object per the locked prompt templates) is
            # what we need; the think trace would help only marginally
            # AND would multiply per-call wall by 10-30×. Explicitly
            # disable reasoning at server level (`--reasoning off`); the
            # judge then emits the answer directly. Decision recorded in
            # the bundle notes; pre-reg pin is unaffected (the reasoning
            # mode is a sampling/server parameter under §"Test subjects"
            # bundle discipline, not a methodological lock).
            self._server = LlamaServer(
                gguf_path=self._gguf_path,
                bundle_id=self.bundle.bundle_id(),
                port=self._port,
                extra_args=["--reasoning", "off"],
            )
            self._server.start()
        return self._server

    def _chat_for_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> tuple[dict, str]:
        """Send a chat call to the Gemma server, parse the JSON reply.

        Returns (parsed_json_dict, raw_text_for_audit).
        """
        srv = self._ensure_server()
        response = srv.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.bundle.temperature,
            top_p=1.0,
            max_tokens=max_tokens or self._max_tokens,
            seed=0,  # deterministic judge runs; seed 0 across all calls
        )
        parsed = _extract_json_object(response.text)
        return parsed, response.text

    def close(self) -> None:
        if self._owns_server and self._server is not None:
            self._server.stop()
            self._server = None

    def __enter__(self) -> "GemmaJudge":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # -----------------------------------------------------------------
    # The three pre-reg-pinned judge calls
    # -----------------------------------------------------------------

    def score_matches_intent(
        self,
        task_brief: str,
        subject_output: str,
        game_brief: str,
    ) -> IntentScore:
        system_prompt = _load_template("matches_intent_prompt")
        user_prompt = (
            "--- DESIGN BRIEF (ground truth) ---\n"
            f"{game_brief}\n\n"
            "--- TASK BRIEF (what the subject was asked to do) ---\n"
            f"{task_brief}\n\n"
            "--- SUBJECT OUTPUT (scored verbatim) ---\n"
            f"{subject_output}\n\n"
            "Respond with exactly the JSON object specified in the prompt."
        )
        parsed, _raw = self._chat_for_json(system_prompt, user_prompt)
        return IntentScore(
            score=int(parsed["score"]),
            rationale=str(parsed.get("rationale", "")),
            bundle_id=self.bundle.bundle_id(),
        )

    def audit_fairness(
        self,
        flattened_b_text: str,
        game_name: str,
        game_pitch: str,
    ) -> FairnessScore:
        system_prompt = _load_template("fairness_audit_prompt")
        user_prompt = (
            f"--- GAME NAME ---\n{game_name}\n\n"
            f"--- GAME PITCH ---\n{game_pitch}\n\n"
            "--- FLATTENED B PROSE (audited for fairness) ---\n"
            f"{flattened_b_text}\n\n"
            "Respond with exactly the JSON object specified in the prompt."
        )
        # Fairness audits read long flattened briefs; allow a wider budget.
        parsed, _raw = self._chat_for_json(system_prompt, user_prompt, max_tokens=4096)
        return FairnessScore(
            score=int(parsed["score"]),
            rationale=str(parsed.get("rationale", "")),
            specific_issues=tuple(parsed.get("specific_issues", []) or []),
            bundle_id=self.bundle.bundle_id(),
        )

    def predict_conditions(
        self,
        outputs: list[tuple[int, str]],
    ) -> list[ConditionPrediction]:
        system_prompt = _load_template("blinding_leak_prompt")
        # Batched prediction: format all outputs into one user message,
        # let the judge emit a single JSON envelope with the full
        # predictions array. This matches what the template expects
        # ("predictions": [...]) and is also faster than per-output
        # calls (one prompt-cache warm-up, one server call).
        rendered_outputs = "\n\n".join(
            f"--- OUTPUT {oid} ---\n{text}" for oid, text in outputs
        )
        user_prompt = (
            f"You will see {len(outputs)} outputs below, each tagged with "
            "an integer OUTPUT id. For each, predict the condition (A | B "
            "| C) per the calibration rubric, output a single JSON object "
            "with a `predictions` array as specified in the prompt.\n\n"
            f"{rendered_outputs}\n\n"
            "Respond with exactly the JSON object specified in the prompt."
        )
        # Bigger budget for batched predictions: ~80 tokens per output (
        # short rationale per the template) × N outputs + envelope.
        max_tokens = max(2048, 200 * len(outputs))
        parsed, _raw = self._chat_for_json(system_prompt, user_prompt, max_tokens=max_tokens)

        preds: list[ConditionPrediction] = []
        for p in parsed.get("predictions", []):
            preds.append(ConditionPrediction(
                output_id=int(p["output_id"]),
                predicted_condition=str(p["predicted_condition"]).strip().upper()[:1],
                confidence=float(p.get("confidence", 1.0 / 3.0)),
                rationale=str(p.get("rationale", "")),
            ))
        return preds


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
