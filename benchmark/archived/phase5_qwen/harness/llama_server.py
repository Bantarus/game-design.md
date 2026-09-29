"""llama-server wrapper — context-managed local LLM inference for Phase 5.

Used by:
  - QwenInstrument (headline subject; pre-reg §"Test subjects").
  - GemmaJudge (auxiliary judge; pre-reg §"Judge" v7 pin).

Both run sequentially (not concurrent) — Qwen loaded for the generation
pass, then Qwen unloaded and Gemma loaded for the scoring pass. The
context-manager pattern below makes the "load once, run a batch, unload"
shape explicit at the call site so VRAM is never contended:

    with LlamaServer(gguf_path, ..., bundle_id="qwen3-coder-30b-a3b-q4km") as srv:
        for cell in plan:
            response = srv.chat(messages=[...], temperature=0, seed=cell.seed, ...)
            # ...
    # srv is now killed, VRAM is free, ready for the next bundle

Why llama-server (HTTP) and not llama-cli (subprocess-per-call):
  - With a 30B-class model, fresh load + warmup is ~10-30 seconds.
    660 trials × 10s = ~2 hours of pure model-load overhead under the
    subprocess-per-call pattern. The server pattern pays this cost ONCE
    per bundle (twice total: once for Qwen, once for Gemma).
  - The /v1/chat/completions endpoint is OpenAI-compatible, so the
    same client code works against llama.cpp, vLLM, or any other
    OpenAI-shaped server if we ever swap implementations.
  - llama-server's `--jinja` flag (default ON) applies the model's
    own chat template from GGUF metadata — no per-model template
    wiring on our side.

Sampling — two layers, two requirements (pre-reg §"Protocol" step 11):

  - The QWEN INSTRUMENT needs *cross-seed variance*: K ≥ 5 distinct
    seeds must produce K distinct outputs (the seed-sensitivity gate).
    N=20 per cell protects effect detection only by averaging over
    varied draws; greedy sampling collapses N=20 to N=1 silently.
    QWEN_HEADLINE_BUNDLE therefore uses Qwen's documented stochastic
    sampling (temperature=0.7, top_p=0.8, top_k=20, repeat_penalty=1.05).
  - The GEMMA JUDGE wants *intra-prompt determinism*: the same scored
    prompt should yield the same score on a re-run, so audit-replay
    reproduces the rubric judgment. GEMMA_JUDGE_BUNDLE therefore uses
    greedy sampling (temperature=0). At greedy, llama.cpp's seed is
    a no-op for the output (same-seed and different-seed both produce
    the same greedy trajectory at a fixed model/build/ctx).

  This is the layer distinction pre-reg §"Protocol" step 11 names:
  the benchmark instrument needs sampled variance; the judge does not.
  Importing byte-identity here was the layer confusion the pre-reg
  corrected at v4 — restoring it on the instrument side would be a
  regression.

  (Claude does not expose a seed; same-seed re-runs diverge naturally;
  see archived/instrument_claude.py::ClaudeInstrument for the
  pre-reg-named exception, archived at v12-D.)
"""
from __future__ import annotations

import os
import socket
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import httpx


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_HEALTH_TIMEOUT_S = 180     # 30B model on a 4090 loads in ~30-60s; allow headroom
DEFAULT_REQUEST_TIMEOUT_S = 600    # per-call generation can run long on hard tasks
DEFAULT_NGL = 999                  # offload everything to GPU; llama.cpp clamps to model layers
DEFAULT_CTX_SIZE = 32768           # 32k ctx; both Qwen3-Coder-30B and Gemma 4 26B support this comfortably
DEFAULT_FLASH_ATTN = "auto"


@dataclass(frozen=True)
class ChatResponse:
    """One response from the /v1/chat/completions endpoint."""
    text: str
    tokens_input: int            # prompt_tokens
    tokens_output: int           # completion_tokens
    finish_reason: str           # "stop" | "length" | etc.
    raw: dict                    # full JSON envelope, for audit


class LlamaServer:
    """Context-managed llama-server subprocess + HTTP client.

    Example:
      with LlamaServer(gguf_path="/path/to/model.gguf") as srv:
          r = srv.chat(
              messages=[
                  {"role": "system", "content": "You are a helpful assistant."},
                  {"role": "user", "content": "Hello"},
              ],
              temperature=0.0,
              seed=42,
              max_tokens=4096,
          )
          print(r.text)
      # subprocess killed here; VRAM released
    """

    def __init__(
        self,
        gguf_path: str | Path,
        *,
        llama_server_bin: str | None = None,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        ngl: int = DEFAULT_NGL,
        ctx_size: int = DEFAULT_CTX_SIZE,
        flash_attn: str = DEFAULT_FLASH_ATTN,
        bundle_id: str = "",
        health_timeout_s: float = DEFAULT_HEALTH_TIMEOUT_S,
        request_timeout_s: float = DEFAULT_REQUEST_TIMEOUT_S,
        extra_args: list[str] | None = None,
        log_path: str | Path | None = None,
    ):
        self.gguf_path = str(Path(gguf_path).expanduser())
        if not Path(self.gguf_path).is_file():
            raise FileNotFoundError(f"GGUF not found: {self.gguf_path}")

        self.llama_server_bin = (
            llama_server_bin
            or os.environ.get("DRIFTWOOD_LLAMA_CPP_BIN")
            or str(Path.home() / "llama.cpp/build/bin/llama-server")
        )
        if not Path(self.llama_server_bin).is_file():
            raise FileNotFoundError(
                f"llama-server binary not found: {self.llama_server_bin!r}. "
                f"Set DRIFTWOOD_LLAMA_CPP_BIN env var or pass llama_server_bin=..."
            )

        self.host = host
        self.port = port
        self.ngl = ngl
        self.ctx_size = ctx_size
        self.flash_attn = flash_attn
        self.bundle_id = bundle_id
        self.health_timeout_s = health_timeout_s
        self.request_timeout_s = request_timeout_s
        self.extra_args = list(extra_args or [])
        self.log_path = log_path

        self._proc: subprocess.Popen | None = None
        self._log_fp = None
        self._client: httpx.Client | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    # ---------------------------------------------------------------
    # Context-manager lifecycle
    # ---------------------------------------------------------------

    def __enter__(self) -> "LlamaServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False  # propagate exceptions

    def start(self) -> None:
        if self._proc is not None:
            raise RuntimeError("LlamaServer already started")

        if _is_port_listening(self.host, self.port):
            raise RuntimeError(
                f"Port {self.port} already in use on {self.host}. "
                f"Another llama-server instance may be running; stop it first."
            )

        cmd = [
            self.llama_server_bin,
            "-m", self.gguf_path,
            "--host", self.host,
            "--port", str(self.port),
            "-ngl", str(self.ngl),
            "-c", str(self.ctx_size),
            "-fa", self.flash_attn,
            "--jinja",  # use model's own chat template from GGUF metadata (D-014-style discipline)
            "--no-warmup",  # warmup is unnecessary for our batch shape; saves 5-10s startup
        ]
        if self.bundle_id:
            cmd.extend(["-a", self.bundle_id])
        cmd.extend(self.extra_args)

        # Pipe stderr to a log file so the subprocess never blocks on
        # full pipe buffers (llama-server is quite chatty at startup).
        if self.log_path:
            self._log_fp = open(self.log_path, "w")
            log_stream = self._log_fp
        else:
            log_stream = subprocess.DEVNULL

        self._proc = subprocess.Popen(
            cmd,
            stdout=log_stream,
            stderr=log_stream if log_stream is not subprocess.DEVNULL else subprocess.DEVNULL,
            # Detach stdin so the subprocess never blocks waiting for input
            stdin=subprocess.DEVNULL,
        )

        # Poll /health until ready (or until timeout). The /health
        # endpoint returns 200 once the model is fully loaded; before
        # that it may return 503 or connection-refused.
        try:
            self._wait_for_ready()
        except Exception:
            # Clean up the subprocess if the health-check failed
            self.stop()
            raise

        # Create the httpx client once; reuse for all calls during the
        # session (TCP keep-alive).
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.request_timeout_s,
        )

    def stop(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

        if self._proc is not None:
            try:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # If terminate didn't take, escalate to SIGKILL.
                    self._proc.kill()
                    self._proc.wait(timeout=10)
            finally:
                self._proc = None

        if self._log_fp is not None:
            self._log_fp.close()
            self._log_fp = None

    def _wait_for_ready(self) -> None:
        """Poll /health until 200, or raise after `health_timeout_s`."""
        deadline = time.monotonic() + self.health_timeout_s
        last_err: Exception | None = None
        while time.monotonic() < deadline:
            # Subprocess crash detection
            if self._proc is None or self._proc.poll() is not None:
                rc = self._proc.returncode if self._proc else None
                raise RuntimeError(
                    f"llama-server subprocess exited prematurely "
                    f"(returncode={rc}). Check the log at {self.log_path!r}."
                )
            try:
                r = httpx.get(f"{self.base_url}/health", timeout=5)
                if r.status_code == 200:
                    return
                last_err = RuntimeError(f"/health returned {r.status_code}: {r.text!r}")
            except httpx.RequestError as e:
                last_err = e
            time.sleep(1)
        raise TimeoutError(
            f"llama-server did not become ready within {self.health_timeout_s}s; "
            f"last error: {last_err!r}"
        )

    # ---------------------------------------------------------------
    # Inference API
    # ---------------------------------------------------------------

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        top_p: float = 1.0,
        top_k: int = 0,
        repeat_penalty: float = 1.0,
        max_tokens: int = 4096,
        seed: int | None = None,
        stop: list[str] | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> ChatResponse:
        """POST /v1/chat/completions with the given messages.

        Returns the assistant's reply text + token counts + finish_reason.
        Uses the OpenAI-compatible envelope; works against any
        OpenAI-shaped server (llama.cpp, vLLM, etc.).

        `repeat_penalty` uses llama.cpp's REST parameter name (the
        OpenAI envelope ignores it; llama-server consumes it). Default
        1.0 = disabled, matching llama-server's CLI default.
        """
        if self._client is None:
            raise RuntimeError("LlamaServer.start() not called (use as context manager)")

        body: dict[str, Any] = {
            "model": self.bundle_id or "llama-server",
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if top_k > 0:
            body["top_k"] = top_k
        if repeat_penalty != 1.0:
            body["repeat_penalty"] = repeat_penalty
        if seed is not None:
            body["seed"] = seed
        if stop:
            body["stop"] = stop
        if extra_body:
            body.update(extra_body)

        r = self._client.post("/v1/chat/completions", json=body)
        r.raise_for_status()
        data = r.json()

        choice = data["choices"][0]
        text = choice["message"]["content"]
        finish_reason = choice.get("finish_reason", "")
        usage = data.get("usage", {}) or {}
        tokens_input = int(usage.get("prompt_tokens", 0))
        tokens_output = int(usage.get("completion_tokens", 0))

        return ChatResponse(
            text=text,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            finish_reason=finish_reason,
            raw=data,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_port_listening(host: str, port: int) -> bool:
    """True if something is already listening on (host, port)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.25)
        try:
            s.connect((host, port))
            return True
        except (ConnectionRefusedError, OSError, socket.timeout):
            return False


@contextmanager
def server_for_bundle(
    gguf_path: str | Path,
    bundle_id: str,
    **kwargs,
) -> Iterator[LlamaServer]:
    """Convenience context manager mirroring `with LlamaServer(...) as srv:`.

    Exists for symmetry with future alternative backends (e.g. a vLLM
    or TGI implementation) — call-site code can switch backends by
    swapping the import without changing the `with` shape.
    """
    with LlamaServer(gguf_path=gguf_path, bundle_id=bundle_id, **kwargs) as srv:
        yield srv
