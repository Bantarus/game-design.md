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
    sampling_repetition_penalty: float = 1.0  # 1.0 = disabled (llama.cpp default)
    sampling_max_tokens: int = 4096
    chat_template: str = ""     # e.g. "chatml" (empty for API-default)
    reasoning_format: str = ""  # e.g. "<think>...</think>" (empty for non-reasoning)
    notes: str = ""

    def bundle_id(self) -> str:
        """A short, unique identifier for the bundle (used in trial records).

        Embeds the full sampling tuple so two bundles that differ only in
        sampling get distinct ids — a change to sampling is a change to
        the instrument per pre-reg §"Test subjects"."""
        return (
            f"{self.model_name}/{self.variant}/{self.quant or 'native'}"
            f"/T={self.sampling_temperature}"
            f"/Tp={self.sampling_top_p}"
            f"/Tk={self.sampling_top_k}"
            f"/Rp={self.sampling_repetition_penalty}"
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
    sampling_max_tokens=4096,
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


class ClaudeInstrument(Instrument):
    """Transfer-probe instrument: Claude via the Claude Code CLI (headless).

    Wired through the user's existing Claude Code installation rather than
    the Anthropic API. Benefits: no API key needed (uses the user's Claude
    Code subscription/login); no SDK dependency. Pinned at the
    harness-build commit to **Opus 4.7 at `--effort xhigh`** — the frontier
    capability tier in the Claude lineup at the time of trial zero. See
    §"Test subjects" + pre-reg line 133: *"Tests how spec-helpfulness
    varies with model capability tier"*; the three named outcomes (Claude
    lift > / ≈ / < Qwen lift) all interpret meaningfully ONLY when the
    Claude side is on a frontier model. A smaller-tier Claude (Sonnet,
    Haiku) would collapse the "frontier models infer the structure
    unaided" outcome (Claude lift < Qwen lift) into "this small model
    needed the scaffold too," which is uninterpretable as a capability-
    tier claim. Opus 4.7 at xhigh is the strongest signal available
    through Claude Code; max is one tier higher and reserved for a
    redirect if xhigh proves insufficient.

    Model pin discipline. We request `claude-opus-4-7` (the canonical
    name) not `opus` (the alias). The alias is resolution-deferred and
    could swap to Opus 4.8 mid-sweep once Anthropic releases it; the
    canonical name locks the request to this generation. (Unlike Haiku
    4.5, which exposes a dated full name `claude-haiku-4-5-20251001`,
    Opus 4.7 does not yet have a dated variant — empirically verified:
    `claude-opus-4-7-YYYYMMDD` returns 404. `claude-opus-4-7` IS the
    canonical pin available for this generation.) The actually-served
    version is still captured per-call in
    `instrument_extra.claude_code_served_models` from Claude Code's
    `modelUsage` field — that's the audit backstop if Anthropic adds a
    dated suffix or rotates a point release behind the canonical name.

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
    Code harness — which adds intrinsic system-context overhead
    (constitution / safety guidance / available-tool descriptions),
    processed identically across A/B/C. Re-measured at the Opus-4.7
    xhigh commit on this instrument: input_tokens ≈ 200 above the
    user-supplied prompt on minimal probes; cache_creation and
    cache_read both 0 in the per-call accounting that Claude Code
    surfaces (the Haiku-era observation of 2k-4.5k overhead was likely
    a cache-creation artifact of an earlier Claude Code version and
    does NOT transfer to this instrument). Qwen runs bare llama.cpp
    with its own chat-template overhead. So cross-subject lift
    differences conflate model capability with harness-overhead delta.
    The HEADLINE (per-subject A-vs-B paired McNemar) is unaffected
    because the harness overhead is constant across conditions WITHIN a
    subject. The transfer probe's cross-subject comparisons (Qwen lift
    vs Claude lift) carry this residual; F-009 reports it alongside the
    other transfer-probe caveats.

    Seed handling: Claude Code does not accept a seed parameter. The
    `seed` arg is recorded on every InstrumentResponse for audit-trail
    purposes (per pre-reg §11 "auditability is recorded, not gated") but
    does NOT deterministically reproduce. Same-seed re-runs will diverge
    — expected and accepted per the v4 layer-confusion correction (the
    benchmark needs sampled variance, not byte-identical reproducibility).
    """

    # Claude-specific system-prompt steer (appended to the harness's
    # system_prompt). The two added sentences cut the agentic-flailing
    # rate at the source — without them, Claude under --tools "" sometimes
    # attempts a denied tool call and burns a turn before delivering text,
    # which inflates `num_turns` and (more importantly) inflates input
    # tokens / cost in a way that may be *prompt-dependent*: a context-
    # poor C prompt could make Claude think "I'm missing information, let
    # me look" more often than a full A tree, which would systematically
    # distort the within-Claude cost-lift gate (one of two headline gates).
    # The steer is a Claude-specific addition (no analogue for Qwen, which
    # has no tools to attempt anyway) — named in pre-reg as an instrument-
    # level confound for the transfer probe. Constant within Claude across
    # A/B/C; safe for the per-subject headline. The regime-constancy check
    # (harness/regime_constancy.py) verifies, post-trial, that num_turns
    # and tokens distributions are comparable across conditions within the
    # Claude arm — turning the assumption into a measured fact.
    CLAUDE_ANTI_FLAILING_SUFFIX = (
        "\n\n"
        "(Session note: tools are disabled in this environment. Respond "
        "with the implementation directly as text; do not attempt tool "
        "calls.)"
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
        import tempfile
        # Append the Claude-specific anti-flailing steer to the harness's
        # system prompt. This is a Claude-only addition (Qwen has no tools);
        # constant within Claude across A/B/C; documented in §"Test subjects"
        # as a named instrument-level confound for the transfer probe.
        effective_system_prompt = system_prompt + self.CLAUDE_ANTI_FLAILING_SUFFIX
        # --max-turns is set to 5 (not 1) because Claude is heavily agentic-
        # trained and may attempt a tool call even with --tools "" + the
        # anti-flailing steer. One additional turn lets it recover with a
        # text-only response. Empirically verified: --max-turns 1 fails with
        # `subtype: error_max_turns` / `stop_reason: tool_use` on probes that
        # prompt tool-attempt behavior; --max-turns 5 works cleanly in normal
        # operation. error_max_turns at 5+ is rare but possible — handled
        # below as a degraded-output trial (counts as a trial; recorded with
        # the error so per-condition error rates are visible; NOT excluded
        # and NOT retried — exclusion/retry could be condition-dependent and
        # would bias the headline; see pre-reg §"Test subjects").
        # --effort xhigh enables Claude's "extra-high" thinking budget for
        # this session. The frontier-capability framing of the transfer
        # probe (pre-reg line 133) requires the strongest signal Claude
        # can produce; xhigh is the named tier just below `max`. The
        # effort level is constant within Claude across A/B/C, so the
        # per-subject paired-McNemar headline is unaffected; cross-subject
        # cost-lift comparisons carry the (constant) overhead delta per
        # the static-overhead caveat (pre-reg §"What this benchmark will
        # NOT establish"). The effort level is captured per-call in
        # instrument_extra.claude_code_effort_requested for audit.
        cmd = [
            self._claude_bin,
            "--print",
            "--max-turns", "5",
            "--no-session-persistence",
            "--output-format", "json",
            "--model", self.bundle.model_name,
            "--effort", "xhigh",
            "--system-prompt", effective_system_prompt,  # REPLACE default; verified
            "--tools", "",                                # disable all built-in tools
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

        # Parse the JSON envelope FIRST. The Claude Code CLI returns a
        # well-formed JSON document even when is_error=true (e.g.
        # error_max_turns), with exit code 1. We treat error_max_turns and
        # similar degraded-output cases as completed trials with whatever
        # `result` text exists — typically empty for error_max_turns. The
        # scoring layer will fail them naturally on both the checklist (no
        # implementation present) and matches-intent (low score). This
        # preserves the trial sample without exclusion or retry, both of
        # which could be condition-dependent and bias the headline.
        try:
            data = json.loads(proc.stdout) if proc.stdout.strip() else {}
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Claude Code CLI returned non-JSON on stdout despite "
                f"--output-format json. exit_code={proc.returncode}. "
                f"First 2 KB of stdout: {proc.stdout[:2048]!r}\n"
                f"stderr (last 2 KB): {proc.stderr[-2048:]!r}"
            ) from e

        # Raise only on hard failures (no parseable JSON envelope — that's
        # a wiring problem, not a degraded-trial). is_error inside a valid
        # envelope is captured below and surfaced via extra fields.
        if not data and proc.returncode != 0:
            raise RuntimeError(
                f"Claude Code CLI returned exit code {proc.returncode} "
                f"with no parseable JSON envelope. "
                f"stderr (last 2 KB): {proc.stderr[-2048:]!r}"
            )

        text = data.get("result", "") or ""
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
            # --tools "" + the anti-flailing steer, this should usually be 0.
            tool_steps=max(0, num_turns - 1),
            wall_clock_seconds=wall_clock,
            bundle_id=self.bundle.bundle_id(),
            invocation_seed=seed,
            extra={
                # Per-call audit fields — load-bearing for the regime-
                # constancy check (harness/regime_constancy.py). These let
                # us verify post-trial that num_turns / tokens / cost /
                # stop_reason distributions are comparable across A/B/C
                # within the Claude arm. If they diverge, the within-Claude
                # cost-lift gate is regime-distorted rather than measuring
                # the spec format's actual cost.
                "claude_code_duration_ms": data.get("duration_ms"),
                "claude_code_total_cost_usd": data.get("total_cost_usd"),
                "claude_code_num_turns": num_turns,
                "claude_code_stop_reason": data.get("stop_reason"),
                "claude_code_subtype": data.get("subtype"),
                "claude_code_is_error": data.get("is_error"),
                "claude_code_errors": data.get("errors"),
                "claude_code_exit_code": proc.returncode,
                # cache_creation_input_tokens captures Claude's intrinsic
                # constitution/safety overhead (~2k-4.5k tokens, constant
                # across conditions); recorded for audit and for the F-009
                # transfer-probe limitations.
                "claude_code_cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
                "claude_code_cache_read_input_tokens": usage.get("cache_read_input_tokens"),
                # Actually-served model version(s) — we pin to the
                # canonical `claude-opus-4-7` (not the `opus` alias), but
                # Anthropic may still rotate point releases behind that
                # name or add a dated variant during the sweep. Capture
                # the served keys per call so any rotation is visible
                # post-hoc. The list keys of modelUsage are the served
                # version IDs (typically one).
                "claude_code_served_models": list((data.get("modelUsage") or {}).keys()),
                # Requested effort tier (pre-reg-relevant: the frontier-
                # capability framing of the transfer probe requires the
                # strongest signal Claude can produce). Captured for
                # audit and so any mid-sweep change is detectable.
                "claude_code_effort_requested": "xhigh",
                # Note: seed is recorded above but Claude Code does NOT use it.
                # Same-seed re-runs will diverge; recorded for audit, not gated.
            },
        )


# Pinned Claude transfer-probe bundle for trial zero (v9 + this commit).
#
# Model: `claude-opus-4-7` requested via --model + `xhigh` requested via
# --effort. This is the FRONTIER-CAPABILITY tier in the Claude lineup at
# the time of trial zero, per the pre-reg's framing (line 133: "Tests how
# spec-helpfulness varies with model capability tier" — the probe is only
# interpretable as a capability-tier claim when the Claude side runs on a
# frontier model; on Haiku/Sonnet the "Claude lift < Qwen lift" outcome
# would collapse to "this small Claude needed the scaffold too," which is
# uninterpretable). xhigh is the named tier just below `max`; if Phase 5
# calibrations show xhigh is leaving signal on the table, escalation to
# `max` is the natural redirect.
#
# Why the canonical name not the alias. We request `claude-opus-4-7` (not
# the `opus` alias) so the request itself locks the model generation;
# the alias would resolve to Opus 4.8 mid-sweep once Anthropic releases
# it, silently confounding any within-Claude A-vs-B that straddles the
# rotation. (Unlike Haiku 4.5's dated form `claude-haiku-4-5-20251001`,
# Opus 4.7 does not yet have a dated variant — empirically verified at
# this commit: every `claude-opus-4-7-YYYYMMDD` guess returned 404.
# `claude-opus-4-7` IS the canonical pin available for this generation.)
# The audit backstop — capturing the actually-served version per call
# from Claude Code's `modelUsage` — is preserved: any future point-
# release rotation behind the canonical name is detectable post-hoc, and
# would land in F-009's "served versions observed" report.
CLAUDE_TRANSFER_PROBE_BUNDLE = InstrumentBundle(
    model_name="claude-opus-4-7",
    variant="claude-code-cli-headless-effort-xhigh",
    quant="",
    gguf_sha256="",  # not applicable for API-hosted model
    inference_engine="claude-code-cli-2.1.143",  # update at harness-build commit
    sampling_temperature=0.0,  # documentation only; Claude Code CLI does not expose --temperature
    sampling_top_p=1.0,
    sampling_top_k=0,
    sampling_max_tokens=4096,
    chat_template="",  # Claude Code default; not user-controllable
    reasoning_format="",  # extended thinking enabled via --effort xhigh; output text only — thinking traces not returned in --print JSON
    notes=(
        "Invoked via Claude Code CLI in headless mode (--print --no-session-"
        "persistence --max-turns 5 --tools '' --model claude-opus-4-7 "
        "--effort xhigh --system-prompt <sys+steer> --output-format json) "
        "with cwd = fresh tempdir per call to neutralize project-memory "
        "contamination. Subscription login; no API key. Frontier-capability "
        "tier per pre-reg line 133 — Opus 4.7 at xhigh effort. Two named "
        "instrument-level confounds (recorded in F-009 transfer-probe "
        "limitations): (1) STATIC overhead — Claude Code's intrinsic "
        "constitution/safety/tool-description overhead, prompt-independent, "
        "constant across A/B/C within Claude (headline safe; mildly pads "
        "cost-lift denominator); exact token magnitude re-measured at this "
        "commit's isolation smoke with Opus xhigh (Haiku-era numbers do not "
        "transfer). (2) DYNAMIC overhead — Claude is heavily agentic-trained "
        "and may attempt denied tool calls when prompts feel context-poor; "
        "mitigated by the CLAUDE_ANTI_FLAILING_SUFFIX system-prompt steer "
        "('tools are disabled... respond with the implementation directly "
        "as text'), verified post-trial by harness/regime_constancy.py "
        "which checks that num_turns / tokens / cost / stop_reason "
        "distributions are comparable across A/B/C within the Claude arm "
        "(turning the constancy assumption into a measured fact). "
        "error_max_turns trials count as failures (no exclusion, no retry "
        "— would be condition-dependent and bias the headline); per-"
        "condition error rates reported with F-009. Isolation verified "
        "via benchmark/harness/verify_claude_isolation.py."
    ),
)
