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
    the Anthropic API. Benefits: no API key needed (uses the user's Claude
    Code subscription/login); no SDK dependency. Pinned at the
    harness-build commit to Haiku 4.5 specifically (the latest small
    capability-tier Claude model — see §"Test subjects" + pre-reg).

    Contamination isolation (the load-bearing fix at this commit).
      Running `claude` inside the project repo loads .claude/projects/
      <cwd-hash>/memory/MEMORY.md, which is the entire design history of
      this benchmark — that would hand the subject the spec via memory
      and break A-vs-B-vs-C comparability across conditions. Fix: spawn
      every subprocess with `cwd` set to a fresh empty temp directory
      OUTSIDE the repo, plus the following hardening flags so the
      subject runs as a bare LLM:

        - `cwd=<fresh /tmp/xyz>`        : no CLAUDE.md, no project memory
                                          loads, no .claude/ in scope.
        - `--system-prompt <text>`      : REPLACE Claude Code's default
                                          agentic system prompt (verified
                                          empirically: a haiku-only
                                          system-prompt produces haiku
                                          responses, confirming replace
                                          semantics — see commit message
                                          for the probe). NOT
                                          --append-system-prompt.
        - `--tools ""`                  : disable all built-in tools
                                          (cleaner than enumerated
                                          --disallowed-tools).
        - `--no-session-persistence`    : no JSONL session log written
                                          to ~/.claude/projects/...
                                          (would accumulate per-call
                                          state otherwise).
        - `--max-turns 1`               : single-turn; one-shot text
                                          generation matching Qwen's
                                          shape so A/B/C is comparable
                                          across subjects.
        - `--output-format json`        : structured response.

      Bare mode (`--bare`) is NOT used — it would force ANTHROPIC_API_KEY
      and lose the subscription login (per `claude --help`: "Anthropic
      auth is strictly ANTHROPIC_API_KEY or apiKeyHelper via --settings
      (OAuth and keychain are never read)"). The isolated-cwd path
      keeps the subscription while neutralizing the contamination.

    Verification — the isolation smoke test (REQUIRED before this
    instrument counts as wired). See
    `benchmark/harness/verify_claude_isolation.py`. It runs the
    instrument against probes that only the project memory could answer
    (specific finding IDs, decision IDs, fresh-game names, spec
    section structure). A correctly-isolated subject MUST NOT produce
    correct answers; a leak means the contamination check failed and
    the wiring is wrong — fix before any trial counts.

    Residual confound (named, not hidden — recorded in F-009 transfer-
    probe limitations). Even isolated, Claude runs through the Claude
    Code harness — which adds ~1874 tokens of intrinsic Claude system
    context (constitution / safety guidance), processed identically
    across A/B/C. Qwen runs bare llama.cpp with its own chat-template
    overhead. So cross-subject lift differences conflate model
    capability with harness-overhead delta. The HEADLINE (per-subject
    A-vs-B paired McNemar) is unaffected because the harness overhead
    is constant across conditions WITHIN a subject. The transfer
    probe's cross-subject comparisons (Qwen lift vs Claude lift) carry
    this residual; F-009 reports it alongside the other transfer-probe
    caveats.

    Seed handling: Claude Code does not accept a seed parameter. The
    `seed` arg is recorded on every InstrumentResponse for audit-trail
    purposes (per pre-reg §11 "auditability is recorded, not gated") but
    does NOT deterministically reproduce. Same-seed re-runs will diverge
    — expected and accepted per the v4 layer-confusion correction (the
    benchmark needs sampled variance, not byte-identical reproducibility).
    """

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
        import tempfile
        # --max-turns is set to 5 (not 1) because Claude is heavily agentic-
        # trained and will occasionally attempt a tool call on the first turn
        # even with --tools "". When the tool attempt fails, Claude needs an
        # additional turn to synthesize a text-only response. Empirically
        # verified: --max-turns 1 fails with `subtype: error_max_turns` /
        # `stop_reason: tool_use` on probes that prompt tool-attempt behavior;
        # --max-turns 5 lets Claude recover cleanly (typical num_turns is 1
        # for tasks where the context is in-prompt; 2-3 if Claude tries a
        # tool first). Cross-subject comparability is at the METRIC level
        # (input tokens + output tokens + wall clock + cost), not at the
        # turn-count level — Qwen has no notion of turns, and the metric is
        # what the headline measures.
        cmd = [
            self._claude_bin,
            "--print",
            "--max-turns", "5",
            "--no-session-persistence",
            "--output-format", "json",
            "--model", self.bundle.model_name,
            "--system-prompt", system_prompt,  # REPLACE default; verified
            "--tools", "",                     # disable all built-in tools
        ]
        # Fresh isolated cwd per call: no CLAUDE.md/project-memory leaks.
        # Per-call dir (not a fixed scratch) so accidental writes by
        # subprocesses can't accumulate across the ~660-trial sweep.
        with tempfile.TemporaryDirectory(prefix="claude-isolated-") as scratch:
            t0 = time.monotonic()
            try:
                proc = subprocess.run(
                    cmd,
                    input=user_prompt,
                    capture_output=True,
                    text=True,
                    cwd=scratch,
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
            # --max-turns 1 + --tools "" this should always be 0.
            tool_steps=max(0, num_turns - 1),
            wall_clock_seconds=wall_clock,
            bundle_id=self.bundle.bundle_id(),
            invocation_seed=seed,
            extra={
                "claude_code_duration_ms": data.get("duration_ms"),
                "claude_code_total_cost_usd": data.get("total_cost_usd"),
                "claude_code_num_turns": num_turns,
                # cache_creation_input_tokens captures Claude's intrinsic
                # constitution/safety overhead (~1874 tokens, constant
                # across conditions); recorded for audit and for the F-009
                # transfer-probe limitations.
                "claude_code_cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
                "claude_code_cache_read_input_tokens": usage.get("cache_read_input_tokens"),
                # Note: seed is recorded above but Claude Code does NOT use it.
                # Same-seed re-runs will diverge; recorded for audit, not gated.
            },
        )


# Pinned Claude transfer-probe bundle for trial zero (v9 + this commit).
# Model: claude-haiku-4-5-20251001 (Haiku 4.5, latest small capability-tier
# Claude model as of the harness-build commit). Pinned to the full
# model name (not the `haiku` alias) so the bundle stays reproducible if
# the alias re-points to a newer version later.
CLAUDE_TRANSFER_PROBE_BUNDLE = InstrumentBundle(
    model_name="claude-haiku-4-5-20251001",
    variant="claude-code-cli-headless",
    quant="",
    gguf_sha256="",  # not applicable for API-hosted model
    inference_engine="claude-code-cli-2.1.143",  # update at harness-build commit
    sampling_temperature=0.0,  # documentation only; Claude Code CLI does not expose --temperature
    sampling_top_p=1.0,
    sampling_top_k=0,
    sampling_max_tokens=4096,
    chat_template="",  # Claude Code default; not user-controllable
    reasoning_format="",
    notes=(
        "Invoked via Claude Code CLI in headless mode (--print --no-session-"
        "persistence --max-turns 1 --tools '' --system-prompt <sys> "
        "--output-format json) with cwd = fresh tempdir per call to "
        "neutralize project-memory contamination. Subscription login; no "
        "API key. Residual confound: Claude Code's intrinsic ~1874-token "
        "constitution/safety overhead is constant across A/B/C within "
        "the Claude arm but conflates with Qwen's bare-llama.cpp shape "
        "for cross-subject comparisons; recorded in F-009 transfer-probe "
        "limitations. Isolation verified via "
        "benchmark/harness/verify_claude_isolation.py."
    ),
)
