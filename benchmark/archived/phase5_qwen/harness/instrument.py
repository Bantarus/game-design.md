"""Instrument abstraction: the subject LLM under test.

One instrument bundle is active for the current benchmark execution
(pre-reg v12-D scope reduction, see `docs/v0.2-phase5-pre-registration.md`):
  - Headline: a specific Qwen variant (model + quant + GGUF SHA +
    llama.cpp build + sampling params + chat template) running locally.

The pre-registered transfer-probe identity (Opus 4.7 at `--effort xhigh`
via Claude Code CLI) is **archived not deleted** under
`benchmark/harness/archived/instrument_claude.py`. It remains the named
transfer-probe-of-record for any future formal validation; v12-D defers
the probe under THIS benchmark execution only. Re-activation procedure:
see `benchmark/harness/archived/README.md`.

The `Instrument` interface is preserved unchanged so re-activation
re-imports `ClaudeInstrument` + `CLAUDE_TRANSFER_PROBE_BUNDLE` from the
archived module and the trial loop parametrizes subject without changes.

Concrete implementations:
  - `QwenInstrument`     — requires local llama.cpp build + GGUF model + flags.
  - `MockInstrument`     — returns canned responses, lets the harness be
                            exercised end-to-end without external infra.
  - `ClaudeInstrument`   — ARCHIVED at v12-D. Lives at
                            `benchmark/harness/archived/instrument_claude.py`.
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
    sampling_repetition_penalty: float = 1.0  # 1.0 = disabled (llama.cpp default)
    sampling_max_tokens: int = 4096
    chat_template: str = ""     # e.g. "chatml" (empty for API-default)
    reasoning_format: str = ""  # e.g. "<think>...</think>" (empty for non-reasoning)
    notes: str = ""

    def bundle_id(self) -> str:
        """A short, unique identifier for the bundle (used in trial records).

        Embeds the full sampling tuple so two bundles that differ only in
        sampling get distinct ids — a change to sampling is a change to
        the instrument per pre-reg §"Test subjects".

        v13-D: `Mt=<max_tokens>` added after the v12-D smoke surfaced a
        cap-bind on cell #1 of trial zero (medium task; 4096-token cap
        truncated implementation). The cap IS part of bundle identity
        (different caps produce different output distributions at the
        cap boundary); making it visible in bundle_id surfaces bundle
        changes in F-009 aggregation and audit filenames.
        """
        return (
            f"{self.model_name}/{self.variant}/{self.quant or 'native'}"
            f"/T={self.sampling_temperature}"
            f"/Tp={self.sampling_top_p}"
            f"/Tk={self.sampling_top_k}"
            f"/Rp={self.sampling_repetition_penalty}"
            f"/Mt={self.sampling_max_tokens}"
        )


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
    """Headline instrument: local Qwen via llama-server (long-running HTTP).

    Wired through [`benchmark/harness/llama_server.py`](llama_server.py).
    The server is loaded once per instance (lazy on first complete()), reused
    across all calls for the lifetime of the QwenInstrument, and released
    on close() / context-manager exit. For a 330-trial Qwen arm at 30B
    Q4_K_M, this pays the ~15s model-load cost ONCE instead of per-call —
    a meaningful saving on the multi-hour sweep.

    Usage (long-running, the sweep driver):
        with QwenInstrument(bundle) as inst:
            for cell in plan:
                r = inst.complete(sys_prompt, user_prompt, seed=cell.seed)

    Usage (one-off, the per-cell CLI shape):
        inst = QwenInstrument(bundle)
        r = inst.complete(...)
        inst.close()  # or rely on GC + LlamaServer's stop()

    Pinned env vars at runtime:
      - DRIFTWOOD_QWEN_GGUF_PATH — path to the Qwen GGUF.
      - DRIFTWOOD_LLAMA_CPP_BIN  — path to llama-server (default
                                    ~/llama.cpp/build/bin/llama-server).

    Seed: llama.cpp's seed parameter, set per-call, gives deterministic
    outputs at temperature=0 for a fixed (model, ngl, ctx_size, batch_size,
    build SHA) combination. The InstrumentBundle pins all five; the seed
    is the per-trial varying input. Same-seed re-runs against the same
    bundle produce byte-identical outputs (verified at the smoke-test
    commit landing this wiring).
    """

    def __init__(
        self,
        bundle: InstrumentBundle,
        *,
        server: "LlamaServer | None" = None,
        gguf_path: str | None = None,
        port: int = 8080,
    ):
        super().__init__(bundle)
        self._gguf_path = (
            gguf_path
            or os.environ.get("DRIFTWOOD_QWEN_GGUF_PATH")
        )
        if not self._gguf_path:
            raise RuntimeError(
                "QwenInstrument needs DRIFTWOOD_QWEN_GGUF_PATH set (or pass "
                "gguf_path=... explicitly). The pinned GGUF lives at the path "
                "computed by benchmark/tools/download_ggufs.sh."
            )
        # Lazy server-start: the LlamaServer is not booted until the first
        # complete() call, so constructing a QwenInstrument (e.g. for tests
        # that don't actually call it) is cheap.
        self._server = server
        self._owns_server = server is None
        self._port = port

    def _ensure_server(self) -> "LlamaServer":
        if self._server is None:
            # Lazy import to avoid pulling httpx into modules that only
            # touch MockInstrument.
            from .llama_server import LlamaServer
            self._server = LlamaServer(
                gguf_path=self._gguf_path,
                bundle_id=self.bundle.bundle_id(),
                port=self._port,
            )
            self._server.start()
        return self._server

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        seed: int,
    ) -> InstrumentResponse:
        srv = self._ensure_server()
        t0 = time.monotonic()
        response = srv.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.bundle.sampling_temperature,
            top_p=self.bundle.sampling_top_p,
            top_k=self.bundle.sampling_top_k,
            repeat_penalty=self.bundle.sampling_repetition_penalty,
            max_tokens=self.bundle.sampling_max_tokens,
            seed=seed,
        )
        wall_clock = time.monotonic() - t0

        return InstrumentResponse(
            text=response.text,
            tokens_input=response.tokens_input,
            tokens_output=response.tokens_output,
            tool_steps=0,  # llama.cpp serves chat-completions; no tool round-trips
            wall_clock_seconds=wall_clock,
            bundle_id=self.bundle.bundle_id(),
            invocation_seed=seed,
            extra={
                "qwen_finish_reason": response.finish_reason,
            },
        )

    def close(self) -> None:
        if self._owns_server and self._server is not None:
            self._server.stop()
            self._server = None

    def __enter__(self) -> "QwenInstrument":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# Pinned Qwen headline-subject bundle for trial zero.
#
# Model: Qwen3-Coder-30B-A3B-Instruct (MoE, A3B active params, code-
# specialized). Pinned at this harness-build commit per pre-reg §"Test
# subjects" — the headline subject. Three outcomes for the headline gate
# (success-lift ≥ 25pp, cost-lift ≤ 25%) are all interpretable against
# this specific pinned bundle; the per-subject McNemar headline is
# scoped to this exact (model, variant, quant, GGUF SHA, llama.cpp
# build, sampling params) tuple.
#
# Distribution: unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF on HuggingFace
# (Apache-2.0). Quant: Q4_K_M (18.6 GB on disk). The reference download
# is via benchmark/tools/download_ggufs.sh; the GGUF SHA-256 below was
# computed by `sha256sum` after the download and is the audit-trail pin.
QWEN_HEADLINE_BUNDLE = InstrumentBundle(
    model_name="Qwen3-Coder-30B-A3B-Instruct",
    variant="unsloth-gguf",
    quant="Q4_K_M",
    gguf_sha256="fadc3e5f8d42bf7e894a785b05082e47daee4df26680389817e2093056f088ad",
    inference_engine="llama.cpp-b9306-5d246a7",
    # Stochastic sampling per Qwen's documented Best Practices for
    # Qwen3-Coder (both upstream Qwen and unsloth's GGUF page recommend
    # the same values verbatim, fetched 2026-05-24). The pre-reg's
    # seed-sensitivity gate (Protocol step 11) requires K=5 distinct
    # seeds to produce K distinct outputs whose pairwise edit distance
    # exceeds 20% of the shorter output — greedy (temperature=0) would
    # collapse N=20 per cell to N=1 and silently destroy the design's
    # statistical power. min_p stays at llama-server's default 0.05
    # (Qwen does not override it). repeat_penalty maps to llama.cpp's
    # REST `repeat_penalty` parameter (passed via LlamaServer.chat()).
    sampling_temperature=0.7,
    sampling_top_p=0.8,
    sampling_top_k=20,
    sampling_repetition_penalty=1.05,
    # v13-D bump: 4096 → 8192. The v12-D trial-zero smoke (cell #1, A medium
    # survival seed=1000128) hit the 4096-token cap mid-rule, with the judge
    # explicitly citing "incomplete, cutting off mid-sentence." Easy task
    # outputs in step 6 calibration max at ~2k tokens (0/90 cap-hits); the
    # cap was off-axis for that calibration's workload but binds for medium/
    # hard/ambiguity tasks where YAML implementations require deeper coverage.
    # Bumped to 8192 (still comfortably within 32k ctx for input tokens ~22k
    # + output ~8k = ~30k; 32k ctx supports it without a ctx_size change).
    # The cap is now ~2× the heaviest expected medium implementation, leaving
    # margin for unusual cases. The bundle SHA changes; v13-D supersession
    # records the audit trail. (Cell #1 of trial zero was discarded as
    # produced under the obsolete bundle.) See pre-reg v12-D → v13-D audit
    # trail row #23.
    sampling_max_tokens=8192,
    chat_template="jinja-from-gguf",  # llama-server --jinja reads the chat template from GGUF metadata
    reasoning_format="",  # Qwen3-Coder is non-reasoning by default; no <think> envelope
    notes=(
        "Headline subject. MoE shape (~3B active params) — fast on the "
        "RTX 4090; runs at ~30-50 tokens/sec generation. Hand-rolled "
        "llama-server wrapper at harness/llama_server.py loads the model "
        "once per arm (~15s on warm cache, no model-load cost per call). "
        "Sampling pinned to Qwen's documented Best Practices for "
        "Qwen3-Coder (temperature=0.7, top_p=0.8, top_k=20, "
        "repetition_penalty=1.05; min_p left at llama-server's default "
        "0.05 because Qwen does not override it). This is the *opposite* "
        "of byte-identity — see llama_server.py module docstring for the "
        "layer distinction pre-reg §\"Protocol\" step 11 names. Cross-seed "
        "divergence is verified at the harness-build smoke commit (K=5 "
        "distinct seeds → 5 distinct SHA-256 hashes, pairwise edit "
        "distance ≥ 20% of shortest output). Same-seed re-runs at this "
        "stochastic sampling will NOT be byte-identical; the same-seed "
        "audit in calibrate_instrument records divergence as data for "
        "F-009 (not as a gate). License: Apache-2.0. Source: unsloth/"
        "Qwen3-Coder-30B-A3B-Instruct-GGUF (HuggingFace), Q4_K_M GGUF, "
        "SHA-256 above. llama.cpp build SHA 5d246a7 (version 9306), "
        "CUDA-enabled, RTX 4090."
    ),
)




# --- ARCHIVED AT v12-D ---
# ClaudeInstrument + CLAUDE_TRANSFER_PROBE_BUNDLE + CLAUDE_ANTI_FLAILING_SUFFIX
# moved to `benchmark/harness/archived/instrument_claude.py` at v12-D scope
# reduction (pre-reg supersession `1bb0803 → ...`). The pre-registered Opus
# 4.7 / xhigh transfer-probe identity remains the design-of-record; v12-D
# defers the probe under THIS benchmark execution only (step 6c read (c)
# FLIP_API_KEY rule fired at 100.4% of default subscription budget; user
# chose deferral over API-key fallback and v12-substitute paths). A future
# re-activation re-imports from `archived/instrument_claude.py` and re-adds
# `claude` to `harness/sweep_plan.py::INSTANCE_SEED_BASE_BY_SUBJECT` with
# the reserved `seed_base=2_000_000`. See `archived/README.md` for the full
# re-activation procedure.
# --- END ARCHIVED v12-D ---
