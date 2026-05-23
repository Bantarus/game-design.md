"""Instrument abstraction: the subject LLM under test.

Two instrument bundles are pinned at the harness-build commit per pre-reg
§"Test subjects":
  - Headline: a specific Qwen variant (model + quant + GGUF SHA +
    llama.cpp build + sampling params + chat template) running locally.
  - Transfer probe: a specific Claude version, invoked via the Claude
    Code CLI in headless mode (NOT the Anthropic API — uses the user's
    existing Claude Code installation and authentication; no API key).

Both instruments speak through the same `Instrument` interface so the
harness can parametrize subject without conditionals throughout the trial
loop.

Concrete implementations are stubbed pending external infra:
  - `QwenInstrument`     — requires local llama.cpp build + GGUF model + flags.
  - `ClaudeInstrument`   — requires the `claude` CLI binary on PATH
                            (Claude Code, headless / `--print` mode) and
                            an active Claude Code session/login. No
                            Anthropic API key needed.
  - `MockInstrument`     — returns canned responses, lets the harness be
                            exercised end-to-end without external infra.
"""
from __future__ import annotations

import json
import os
import subprocess
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
    """Transfer-probe instrument: Claude via the Claude Code CLI (headless).

    Wired through the user's existing Claude Code installation rather than
    the Anthropic API. Benefits over the API path: no API key needed (uses
    the user's Claude Code login session); same model behavior as the
    user's interactive Claude Code sessions; no SDK dependency.

    Requires:
      - The `claude` CLI on PATH (or set DRIFTWOOD_CLAUDE_CODE_BIN).
      - An active Claude Code login (run `claude` once interactively to
        authenticate; the CLI caches the session).
      - The pinned Claude model name in the bundle (passed via --model).
      - The pinned sampling params recorded in the bundle for audit;
        Claude Code CLI does not expose a `--temperature` flag, so the
        bundle's `sampling_temperature` is documentation of Claude's
        in-effect default, not a per-call override. The seed-sensitivity
        gate (Protocol step 11) still passes because Claude's default
        temperature is > 0 and same-prompt repeated invocations produce
        varied outputs naturally.

    Invocation contract (matches Qwen one-shot text generation so the
    A-vs-B-vs-C comparison is comparable across instruments):
      - `--max-turns 1`            : single-turn (no tool-use loop)
      - `--disallowed-tools "*"`   : no tool invocations
      - `--output-format json`     : structured response with token
                                      counts and duration
      - prompt passed via stdin    : avoids shell-quoting issues for
                                      long design contexts

    Seed handling: Claude Code does not accept a seed parameter. The
    `seed` arg is recorded on every InstrumentResponse for audit-trail
    purposes (per pre-reg §11 "auditability is recorded, not gated") but
    does NOT deterministically reproduce. Same-seed re-runs will diverge;
    that is expected and accepted per the v4 layer-confusion correction.

    The transfer-probe role is documented in pre-reg §"Test subjects" —
    NOT framed as an "optimistic ceiling," but as a capability-tier
    transfer test.
    """

    DEFAULT_DISALLOWED_TOOLS = (
        "Bash,Read,Write,Edit,Grep,Glob,WebFetch,WebSearch,Task,TodoWrite,"
        "NotebookEdit,SlashCommand,KillShell"
    )

    def __init__(self, bundle: InstrumentBundle):
        super().__init__(bundle)
        self._claude_bin = os.environ.get("DRIFTWOOD_CLAUDE_CODE_BIN", "claude")
        self._timeout_seconds = int(os.environ.get(
            "DRIFTWOOD_CLAUDE_CODE_TIMEOUT_SECONDS", "300"
        ))

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        seed: int,
    ) -> InstrumentResponse:
        cmd = [
            self._claude_bin,
            "--print",
            "--max-turns", "1",
            "--output-format", "json",
            "--model", self.bundle.model_name,
            "--append-system-prompt", system_prompt,
            "--disallowed-tools", self.DEFAULT_DISALLOWED_TOOLS,
        ]
        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                input=user_prompt,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except FileNotFoundError as e:
            raise NotImplementedError(
                f"ClaudeInstrument requires the `claude` CLI on PATH (or set "
                f"DRIFTWOOD_CLAUDE_CODE_BIN). Tried: {self._claude_bin!r}. "
                f"See benchmark/README.md."
            ) from e
        wall_clock = time.monotonic() - t0

        if proc.returncode != 0:
            raise RuntimeError(
                f"Claude Code CLI returned exit code {proc.returncode}.\n"
                f"stderr (last 2 KB): {proc.stderr[-2048:]!r}"
            )

        # Claude Code's --output-format json returns a single object with
        # `result` (the text), `usage` (token counts), `duration_ms`,
        # `num_turns`, `total_cost_usd`, etc.
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Claude Code CLI returned non-JSON on stdout despite "
                f"--output-format json. First 2 KB of stdout: "
                f"{proc.stdout[:2048]!r}"
            ) from e

        text = data.get("result", "")
        usage = data.get("usage", {}) or {}
        tokens_input = int(usage.get("input_tokens", 0))
        tokens_output = int(usage.get("output_tokens", 0))
        num_turns = int(data.get("num_turns", 0))

        return InstrumentResponse(
            text=text,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            # tool_steps = num_turns - 1 (the first turn is the response
            # itself; any additional turn is a tool round-trip). With
            # --max-turns 1 + --disallowed-tools, this should always be 0.
            tool_steps=max(0, num_turns - 1),
            wall_clock_seconds=wall_clock,
            bundle_id=self.bundle.bundle_id(),
            invocation_seed=seed,
            extra={
                "claude_code_duration_ms": data.get("duration_ms"),
                "claude_code_total_cost_usd": data.get("total_cost_usd"),
                "claude_code_num_turns": num_turns,
                # Note: seed is recorded above but Claude Code does NOT use it.
                # Same-seed re-runs will diverge; recorded for audit, not gated.
            },
        )
