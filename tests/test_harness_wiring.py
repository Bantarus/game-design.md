"""Unit tests for the harness wiring (instrument + judge + llama-server).

The end-to-end smoke tests at the harness-build commit verify the real
inference works (see commit message); these tests cover the wiring
seams — JSON parsing, lifecycle, request construction, response shape
— with mocked llama-server so they run fast on every pytest invocation
without VRAM / GGUF dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _extract_json_object — tolerant JSON parser
# ---------------------------------------------------------------------------

from benchmark.harness.judge import _extract_json_object


def test_extract_clean_json():
    text = '{"score": 5, "rationale": "fine"}'
    assert _extract_json_object(text) == {"score": 5, "rationale": "fine"}


def test_extract_json_with_markdown_fence():
    text = 'Here is the result:\n```json\n{"score": 4}\n```\nLet me know if you have questions.'
    assert _extract_json_object(text) == {"score": 4}


def test_extract_json_with_explanation_prefix():
    text = 'The score is 3 because of issues.\n\n{"score": 3, "rationale": "issues"}\n\nThank you.'
    assert _extract_json_object(text) == {"score": 3, "rationale": "issues"}


def test_extract_nested_json():
    text = '{"predictions": [{"output_id": 1, "predicted_condition": "A"}, {"output_id": 2, "predicted_condition": "B"}]}'
    out = _extract_json_object(text)
    assert len(out["predictions"]) == 2
    assert out["predictions"][1]["predicted_condition"] == "B"


def test_extract_json_with_string_containing_braces():
    """Strings inside JSON must not confuse the brace-balance scanner."""
    text = '{"rationale": "uses { and } in the code", "score": 4}'
    out = _extract_json_object(text)
    assert out["score"] == 4
    assert "{ and }" in out["rationale"]


def test_extract_json_with_escaped_quotes():
    text = '{"rationale": "the brief says \\"hp = 100\\" exactly", "score": 5}'
    out = _extract_json_object(text)
    assert out["score"] == 5


def test_extract_raises_when_no_json():
    with pytest.raises(ValueError, match="no JSON object"):
        _extract_json_object("This is just prose with no JSON anywhere.")


# ---------------------------------------------------------------------------
# LlamaServer lifecycle (mocked subprocess + httpx)
# ---------------------------------------------------------------------------

from benchmark.harness import llama_server as ls_mod
from benchmark.harness.llama_server import LlamaServer, ChatResponse


@dataclass
class _FakeProc:
    """Stand-in for subprocess.Popen — never actually spawns anything."""
    returncode: int | None = None
    terminated: bool = False
    killed: bool = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


@dataclass
class _FakeResponse:
    status_code: int = 200
    _json: dict = field(default_factory=dict)
    text: str = ""

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


@pytest.fixture
def fake_gguf(tmp_path):
    """A zero-byte file that exists at a known path — passes the
    file-exists check in LlamaServer.__init__ without needing a real GGUF.
    """
    p = tmp_path / "fake-model.gguf"
    p.write_bytes(b"")
    return str(p)


@pytest.fixture
def fake_binary(tmp_path):
    p = tmp_path / "llama-server"
    p.write_bytes(b"")
    p.chmod(0o755)
    return str(p)


def test_llama_server_requires_existing_gguf(tmp_path, fake_binary):
    with pytest.raises(FileNotFoundError, match="GGUF not found"):
        LlamaServer(gguf_path=str(tmp_path / "does-not-exist.gguf"),
                    llama_server_bin=fake_binary)


def test_llama_server_requires_existing_binary(fake_gguf, tmp_path):
    with pytest.raises(FileNotFoundError, match="llama-server binary"):
        LlamaServer(gguf_path=fake_gguf,
                    llama_server_bin=str(tmp_path / "no-such-bin"))


def test_llama_server_lifecycle_mocked(fake_gguf, fake_binary):
    """start() spawns subprocess + polls /health; stop() terminates."""
    proc = _FakeProc()

    with patch.object(ls_mod.subprocess, "Popen", return_value=proc) as mock_popen, \
         patch.object(ls_mod, "_is_port_listening", return_value=False), \
         patch.object(ls_mod.httpx, "get", return_value=_FakeResponse(status_code=200)) as mock_get, \
         patch.object(ls_mod.httpx, "Client", return_value=MagicMock()):

        srv = LlamaServer(gguf_path=fake_gguf, llama_server_bin=fake_binary, port=8090)
        srv.start()
        # Popen called with our binary + gguf
        cmd = mock_popen.call_args[0][0]
        assert fake_binary in cmd
        assert fake_gguf in cmd
        assert "--port" in cmd and "8090" in cmd
        assert "--jinja" in cmd
        # /health polled
        mock_get.assert_called_once()
        # cleanup
        srv.stop()
        assert proc.terminated


def test_llama_server_stop_escalates_to_kill_on_timeout(fake_gguf, fake_binary):
    """If terminate() doesn't take, stop() escalates to SIGKILL."""
    proc = _FakeProc()
    # Make wait() time out the first call (terminate), succeed the second (kill)
    call_count = [0]
    def wait_side_effect(timeout=None):
        call_count[0] += 1
        if call_count[0] == 1:
            import subprocess as sp
            raise sp.TimeoutExpired(cmd="fake", timeout=timeout or 0)
        return 0
    proc.wait = wait_side_effect

    with patch.object(ls_mod.subprocess, "Popen", return_value=proc), \
         patch.object(ls_mod, "_is_port_listening", return_value=False), \
         patch.object(ls_mod.httpx, "get", return_value=_FakeResponse(status_code=200)), \
         patch.object(ls_mod.httpx, "Client", return_value=MagicMock()):

        srv = LlamaServer(gguf_path=fake_gguf, llama_server_bin=fake_binary)
        srv.start()
        srv.stop()
        assert proc.terminated
        assert proc.killed


def test_llama_server_chat_constructs_request(fake_gguf, fake_binary):
    """chat() sends the right JSON body to /v1/chat/completions."""
    proc = _FakeProc()
    mock_client = MagicMock()
    mock_client.post.return_value = _FakeResponse(
        status_code=200,
        _json={
            "choices": [{
                "message": {"content": "hello", "role": "assistant"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1},
        },
    )

    with patch.object(ls_mod.subprocess, "Popen", return_value=proc), \
         patch.object(ls_mod, "_is_port_listening", return_value=False), \
         patch.object(ls_mod.httpx, "get", return_value=_FakeResponse(status_code=200)), \
         patch.object(ls_mod.httpx, "Client", return_value=mock_client):

        with LlamaServer(gguf_path=fake_gguf, llama_server_bin=fake_binary, bundle_id="test-bundle") as srv:
            r = srv.chat(
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.0,
                seed=42,
                max_tokens=128,
            )

        # post was called with /v1/chat/completions and the right body
        assert mock_client.post.call_count == 1
        url = mock_client.post.call_args[0][0]
        body = mock_client.post.call_args[1]["json"]
        assert url == "/v1/chat/completions"
        assert body["model"] == "test-bundle"
        assert body["messages"] == [{"role": "user", "content": "hi"}]
        assert body["temperature"] == 0.0
        assert body["seed"] == 42
        assert body["max_tokens"] == 128

        # parsed response
        assert isinstance(r, ChatResponse)
        assert r.text == "hello"
        assert r.tokens_input == 5
        assert r.tokens_output == 1
        assert r.finish_reason == "stop"


def test_llama_server_refuses_port_collision(fake_gguf, fake_binary):
    with patch.object(ls_mod, "_is_port_listening", return_value=True):
        srv = LlamaServer(gguf_path=fake_gguf, llama_server_bin=fake_binary, port=8080)
        with pytest.raises(RuntimeError, match="Port 8080 already in use"):
            srv.start()


def test_llama_server_health_timeout(fake_gguf, fake_binary):
    """If /health never returns 200, start() raises TimeoutError."""
    proc = _FakeProc()
    with patch.object(ls_mod.subprocess, "Popen", return_value=proc), \
         patch.object(ls_mod, "_is_port_listening", return_value=False), \
         patch.object(ls_mod.httpx, "get", return_value=_FakeResponse(status_code=503)), \
         patch.object(ls_mod.httpx, "Client", return_value=MagicMock()), \
         patch.object(ls_mod.time, "sleep"):

        srv = LlamaServer(gguf_path=fake_gguf, llama_server_bin=fake_binary, health_timeout_s=0.5)
        with pytest.raises(TimeoutError):
            srv.start()


# ---------------------------------------------------------------------------
# QwenInstrument wiring (uses an injected LlamaServer mock)
# ---------------------------------------------------------------------------

from benchmark.harness.instrument import QwenInstrument, QWEN_HEADLINE_BUNDLE


def test_qwen_instrument_uses_injected_server():
    """QwenInstrument.complete() forwards system+user prompts + seed
    + sampling params to the LlamaServer.chat() call."""
    fake_server = MagicMock()
    fake_server.chat.return_value = ChatResponse(
        text="def add(a, b): return a + b",
        tokens_input=42,
        tokens_output=10,
        finish_reason="stop",
        raw={},
    )

    inst = QwenInstrument(QWEN_HEADLINE_BUNDLE, server=fake_server, gguf_path="/dev/null")
    r = inst.complete(
        system_prompt="You are a coder.",
        user_prompt="Write add.",
        seed=42,
    )

    # Server was called with the right messages + Qwen's documented
    # stochastic sampling (temperature=0.7, top_p=0.8, top_k=20,
    # repeat_penalty=1.05). Greedy sampling on the headline subject
    # would collapse N=20 per cell to N=1 — see QWEN_HEADLINE_BUNDLE
    # docstring for the layer distinction.
    call = fake_server.chat.call_args
    assert call.kwargs["messages"][0]["role"] == "system"
    assert call.kwargs["messages"][0]["content"] == "You are a coder."
    assert call.kwargs["messages"][1]["role"] == "user"
    assert call.kwargs["messages"][1]["content"] == "Write add."
    assert call.kwargs["temperature"] == 0.7
    assert call.kwargs["top_p"] == 0.8
    assert call.kwargs["top_k"] == 20
    assert call.kwargs["repeat_penalty"] == 1.05
    assert call.kwargs["seed"] == 42
    assert call.kwargs["max_tokens"] == 4096

    # Response fields are forwarded
    assert r.text == "def add(a, b): return a + b"
    assert r.tokens_input == 42
    assert r.tokens_output == 10
    assert r.tool_steps == 0
    assert r.bundle_id == QWEN_HEADLINE_BUNDLE.bundle_id()
    assert r.invocation_seed == 42
    assert r.extra["qwen_finish_reason"] == "stop"


def test_qwen_instrument_does_not_close_injected_server():
    """Caller-supplied server stays open after the instrument's close()."""
    fake_server = MagicMock()
    inst = QwenInstrument(QWEN_HEADLINE_BUNDLE, server=fake_server, gguf_path="/dev/null")
    inst.close()
    fake_server.stop.assert_not_called()


def test_qwen_instrument_requires_gguf_path():
    """Without DRIFTWOOD_QWEN_GGUF_PATH or explicit gguf_path, error."""
    import os
    saved = os.environ.pop("DRIFTWOOD_QWEN_GGUF_PATH", None)
    try:
        with pytest.raises(RuntimeError, match="DRIFTWOOD_QWEN_GGUF_PATH"):
            QwenInstrument(QWEN_HEADLINE_BUNDLE)
    finally:
        if saved is not None:
            os.environ["DRIFTWOOD_QWEN_GGUF_PATH"] = saved


# ---------------------------------------------------------------------------
# GemmaJudge wiring (uses an injected LlamaServer mock)
# ---------------------------------------------------------------------------

from benchmark.harness.judge import GemmaJudge, GEMMA_JUDGE_BUNDLE


def _fake_chat_response(text: str) -> ChatResponse:
    return ChatResponse(text=text, tokens_input=100, tokens_output=50, finish_reason="stop", raw={})


def test_gemma_score_matches_intent_parses_json():
    fake_server = MagicMock()
    fake_server.chat.return_value = _fake_chat_response(
        '{"score": 4, "rationale": "good", "design_choices_defended": ["A"], "unsupported_additions": []}'
    )
    judge = GemmaJudge(GEMMA_JUDGE_BUNDLE, server=fake_server, gguf_path="/dev/null")
    score = judge.score_matches_intent("task brief", "subject output", "game brief")
    assert score.score == 4
    assert score.rationale == "good"
    assert score.bundle_id == GEMMA_JUDGE_BUNDLE.bundle_id()
    # User message included all three inputs
    user_msg = fake_server.chat.call_args.kwargs["messages"][1]["content"]
    assert "task brief" in user_msg
    assert "subject output" in user_msg
    assert "game brief" in user_msg


def test_gemma_audit_fairness_parses_json_with_issues():
    fake_server = MagicMock()
    fake_server.chat.return_value = _fake_chat_response(
        '{"score": 3, "rationale": "issues found", "specific_issues": ["weak pitch", "missing pillar"]}'
    )
    judge = GemmaJudge(GEMMA_JUDGE_BUNDLE, server=fake_server, gguf_path="/dev/null")
    audit = judge.audit_fairness("flattened text", "Embergrave", "precision platformer")
    assert audit.score == 3
    assert audit.specific_issues == ("weak pitch", "missing pillar")


def test_gemma_predict_conditions_batched():
    fake_server = MagicMock()
    fake_server.chat.return_value = _fake_chat_response(
        '{"predictions": ['
        '{"output_id": 0, "predicted_condition": "A", "confidence": 0.9, "rationale": "yaml tells"},'
        '{"output_id": 1, "predicted_condition": "b", "confidence": 0.7, "rationale": "prose tells"},'
        '{"output_id": 2, "predicted_condition": "C", "confidence": 0.5, "rationale": "minimal"}'
        ']}'
    )
    judge = GemmaJudge(GEMMA_JUDGE_BUNDLE, server=fake_server, gguf_path="/dev/null")
    preds = judge.predict_conditions([(0, "yaml..."), (1, "prose..."), (2, "min...")])
    assert len(preds) == 3
    assert preds[0].predicted_condition == "A"
    # Lowercase 'b' should be normalized to uppercase
    assert preds[1].predicted_condition == "B"
    assert preds[2].confidence == 0.5

    # Batched: ONE chat call for all three outputs (not one per output)
    assert fake_server.chat.call_count == 1


def test_gemma_judge_does_not_close_injected_server():
    fake_server = MagicMock()
    judge = GemmaJudge(GEMMA_JUDGE_BUNDLE, server=fake_server, gguf_path="/dev/null")
    judge.close()
    fake_server.stop.assert_not_called()
