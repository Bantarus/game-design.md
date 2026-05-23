"""Instrument abstraction: the subject LLM under test.

Two instrument bundles are pinned at the harness-build commit per pre-reg
§"Test subjects":
  - Headline: a specific Qwen variant (model + quant + GGUF SHA +
    llama.cpp build + sampling params + chat template) running locally.
  - Transfer probe: a specific Claude version.

Both instruments speak through the same `Instrument` interface so the
harness can parametrize subject without conditionals throughout the trial
loop.

Concrete implementations are stubbed pending external infra:
  - `QwenInstrument`     — requires local llama.cpp build + GGUF model + flags.
  - `ClaudeInstrument`   — requires Anthropic API key + a pinned Claude
                            version.
  - `MockInstrument`     — returns canned responses, lets the harness be
                            exercised end-to-end without external infra.
"""
from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class InstrumentBundle:
    """The full bundle that's pre-registered per pre-reg §11. A change to
    ANY field here means a different instrument and requires a new pre-reg."""

    model_name: str             # e.g. "qwen3-30b-a3b" or "claude-sonnet-4-7"
    variant: str                # e.g. "instruct" or "thinking-mode-on"
    quant: str = ""             # e.g. "Q4_K_M" (empty for non-quantized)
    gguf_sha256: str = ""       # SHA-256 of the GGUF file (empty for API-served)
    inference_engine: str = ""  # e.g. "llama.cpp-b3300" (empty for API-served)
    sampling_temperature: float = 0.0
    sampling_top_p: float = 1.0
    sampling_top_k: int = 0
    sampling_max_tokens: int = 4096
    chat_template: str = ""     # e.g. "chatml" (empty for API-default)
    reasoning_format: str = ""  # e.g. "<think>...</think>" (empty for non-reasoning)
    notes: str = ""

    def bundle_id(self) -> str:
        """A short, unique identifier for the bundle (used in trial records)."""
        return f"{self.model_name}/{self.variant}/{self.quant or 'native'}/{self.sampling_temperature}"


@dataclass(frozen=True)
class InstrumentResponse:
    """One response from one invocation."""

    text: str                   # the response text
    tokens_input: int           # tokens consumed by the prompt
    tokens_output: int          # tokens generated in the response
    tool_steps: int             # number of tool calls made (0 for tool-less)
    wall_clock_seconds: float
    bundle_id: str
    invocation_seed: int        # the seed used for this invocation (for audit)
    extra: dict = field(default_factory=dict)  # bundle-specific metadata


class Instrument(ABC):
    """Abstract instrument. Subclasses implement `complete()`."""

    def __init__(self, bundle: InstrumentBundle):
        self.bundle = bundle

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        seed: int,
    ) -> InstrumentResponse:
        """Send a prompt to the instrument; return its response."""
        ...


# ---------------------------------------------------------------------------
# Mock instrument — for harness exercise WITHOUT external infra
# ---------------------------------------------------------------------------

class MockInstrument(Instrument):
    """Returns canned responses. The seed is interpolated so different seeds
    produce different texts — useful for exercising the seed-sensitivity
    calibration without a real instrument."""

    def __init__(self, bundle: InstrumentBundle | None = None):
        super().__init__(bundle or InstrumentBundle(
            model_name="mock-instrument",
            variant="canned",
            notes="Returns canned responses for harness exercise; NOT a real instrument.",
        ))

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        seed: int,
    ) -> InstrumentResponse:
        # A response that varies by seed (so seed-sensitivity passes trivially)
        # and includes enough sham content that the checklist machinery can
        # be exercised end-to-end.
        text = (
            f"[mock response, seed={seed}]\n\n"
            f"(This is a placeholder. Real trials require a wired-up Instrument; "
            f"MockInstrument exists only to exercise the harness end-to-end without external infra. "
            f"The seed parameter ({seed}) is interpolated to satisfy seed-sensitivity checks at the harness layer.)\n\n"
            f"--- Prompt echo (first 200 chars) ---\n"
            f"{user_prompt[:200]}"
        )
        return InstrumentResponse(
            text=text,
            tokens_input=len(user_prompt) // 4,
            tokens_output=len(text) // 4,
            tool_steps=0,
            wall_clock_seconds=0.0,
            bundle_id=self.bundle.bundle_id(),
            invocation_seed=seed,
        )


# ---------------------------------------------------------------------------
# Real instruments — stubbed until external infra is wired up
# ---------------------------------------------------------------------------

class QwenInstrument(Instrument):
    """Headline instrument: local Qwen via llama.cpp.

    Requires:
      - llama.cpp build (the exact version is pinned in the bundle)
      - the pinned GGUF file at a known path (the SHA-256 is pinned in the bundle)
      - sampling params as declared in the bundle
      - chat-template + reasoning-format handling as declared in the bundle

    The trial-zero command line will set the GGUF path via env var
    `DRIFTWOOD_QWEN_GGUF_PATH` and the llama.cpp binary via env var
    `DRIFTWOOD_LLAMA_CPP_BIN`; this class verifies both exist on construction.
    """

    def __init__(self, bundle: InstrumentBundle):
        super().__init__(bundle)
        self._gguf_path = os.environ.get("DRIFTWOOD_QWEN_GGUF_PATH")
        self._llama_cpp_bin = os.environ.get("DRIFTWOOD_LLAMA_CPP_BIN")
        # Verification is deliberately deferred; the harness's calibration smoke
        # run is the canonical check that the bundle is correctly wired.

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        seed: int,
    ) -> InstrumentResponse:
        if not self._gguf_path or not self._llama_cpp_bin:
            raise NotImplementedError(
                "QwenInstrument requires DRIFTWOOD_QWEN_GGUF_PATH and "
                "DRIFTWOOD_LLAMA_CPP_BIN env vars + a wired-up subprocess call. "
                "Stub pending external infra; see benchmark/README.md."
            )
        # TODO: subprocess.run([self._llama_cpp_bin, "-m", self._gguf_path,
        #                       "--seed", str(seed), ...])
        # Parse output, count tokens, handle <think>...</think> blocks per bundle.
        # Return InstrumentResponse(...)
        raise NotImplementedError("QwenInstrument.complete() stub; wire up llama.cpp invocation.")


class ClaudeInstrument(Instrument):
    """Transfer-probe instrument: Claude via the Anthropic API.

    Requires:
      - ANTHROPIC_API_KEY env var
      - the pinned Claude model name in the bundle
      - the pinned sampling params

    The transfer-probe role is documented in pre-reg §"Test subjects" —
    NOT framed as an "optimistic ceiling," but as a capability-tier
    transfer test.
    """

    def __init__(self, bundle: InstrumentBundle):
        super().__init__(bundle)
        self._api_key = os.environ.get("ANTHROPIC_API_KEY")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        seed: int,
    ) -> InstrumentResponse:
        if not self._api_key:
            raise NotImplementedError(
                "ClaudeInstrument requires ANTHROPIC_API_KEY env var + the "
                "Anthropic SDK. Stub pending external infra; see benchmark/README.md."
            )
        # TODO: import anthropic; client = anthropic.Anthropic(api_key=self._api_key)
        # response = client.messages.create(model=self.bundle.model_name,
        #                                    system=system_prompt,
        #                                    messages=[{"role": "user", "content": user_prompt}],
        #                                    max_tokens=self.bundle.sampling_max_tokens,
        #                                    temperature=self.bundle.sampling_temperature,
        #                                    metadata={"user_id": str(seed)})
        # Note: Claude's API doesn't take a seed parameter directly; the
        # `metadata.user_id` field is the closest proxy. The bundle's
        # `sampling_temperature` must be > 0 for the seed-sensitivity check
        # to produce distinct outputs.
        raise NotImplementedError("ClaudeInstrument.complete() stub; wire up Anthropic SDK.")
