"""v0.8.6: LoRA endpoint routing through mlx_lm.server.

joe REPL should auto-detect when an mlx_lm.server is running on :8081
and route /chat through its OpenAI-compatible /v1/chat/completions
instead of ollama's /api/generate. The /lora slash command toggles
this explicitly.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


def test_detect_llm_returns_empty_when_nothing_listening(joe_module, monkeypatch):
    """With no server up and no env override, _detect_llm returns "" (fall
    back to ollama)."""
    monkeypatch.delenv("JOE_LLM_BASE_URL", raising=False)
    joe_module._LLM_DETECTED = None
    joe_module.LLM_BASE_URL = ""

    def fake_urlopen(*a, **kw):
        raise ConnectionRefusedError("nothing on 8081")

    monkeypatch.setattr(joe_module.urllib.request, "urlopen", fake_urlopen)
    assert joe_module._detect_llm() == ""


def test_detect_llm_uses_env_override(joe_module, monkeypatch):
    """JOE_LLM_BASE_URL bypasses the probe entirely."""
    joe_module._LLM_DETECTED = None
    joe_module.LLM_BASE_URL = "http://my-other-mac:8081/v1"
    # urlopen should NOT be called when the env override is set.
    sentinel = MagicMock(side_effect=RuntimeError("urlopen should not run"))
    monkeypatch.setattr(joe_module.urllib.request, "urlopen", sentinel)
    assert joe_module._detect_llm() == "http://my-other-mac:8081/v1"
    sentinel.assert_not_called()


def test_detect_llm_probes_8081_when_no_override(joe_module, monkeypatch):
    """No env override → joe should probe :8081 and adopt it on 200."""
    joe_module._LLM_DETECTED = None
    joe_module.LLM_BASE_URL = ""
    fake_resp = MagicMock(status=200)
    fake_resp.__enter__ = lambda self: self
    fake_resp.__exit__ = lambda self, *a: None
    monkeypatch.setattr(
        joe_module.urllib.request, "urlopen",
        lambda *a, **kw: fake_resp,
    )
    assert joe_module._detect_llm() == "http://127.0.0.1:8081/v1"


def test_detect_llm_caches_result(joe_module, monkeypatch):
    """Repeated calls should not re-probe; cached at _LLM_DETECTED."""
    joe_module._LLM_DETECTED = "http://cached:8081/v1"
    joe_module.LLM_BASE_URL = ""
    bomb = MagicMock(side_effect=AssertionError("cache miss"))
    monkeypatch.setattr(joe_module.urllib.request, "urlopen", bomb)
    assert joe_module._detect_llm() == "http://cached:8081/v1"


def test_mlx_resolve_model_picks_lora_fused(joe_module, monkeypatch):
    """_mlx_resolve_model should prefer a 'lora' or 'fused' model when
    the user passes a short name like 'joe-gemma'."""
    listing = {
        "data": [
            {"id": "mlx-community/gemma-3-4b-it-4bit"},
            {"id": "/Users/ghost/.joe-agent/joe-gemma-lora-v3-fused"},
        ]
    }
    fake_resp = MagicMock()
    fake_resp.read = lambda: json.dumps(listing).encode()
    fake_resp.__enter__ = lambda self: self
    fake_resp.__exit__ = lambda self, *a: None
    monkeypatch.setattr(
        joe_module.urllib.request, "urlopen",
        lambda *a, **kw: fake_resp,
    )
    chosen = joe_module._mlx_resolve_model("joe-gemma", "http://x:8081/v1")
    assert "lora" in chosen or "fused" in chosen


def test_mlx_resolve_model_absolute_path_passthrough(joe_module, monkeypatch):
    """If the user passes an absolute path, return it verbatim."""
    bomb = MagicMock(side_effect=AssertionError("should not probe"))
    monkeypatch.setattr(joe_module.urllib.request, "urlopen", bomb)
    assert joe_module._mlx_resolve_model(
        "/abs/path/to/my-model", "http://x:8081/v1",
    ) == "/abs/path/to/my-model"


def test_ollama_once_routes_to_mlx_when_detected(joe_module, monkeypatch):
    """When _detect_llm returns a URL, _ollama_once should call the mlx
    helper and never touch the ollama endpoint."""
    joe_module._LLM_DETECTED = "http://127.0.0.1:8081/v1"
    joe_module.LLM_BASE_URL = ""
    monkeypatch.setattr(
        joe_module, "_mlx_server_once",
        lambda model, prompt, base, timeout: f"MLX_SAW: {prompt[:20]}",
    )
    # urlopen should not be hit at all (ollama path bypassed).
    bomb = MagicMock(side_effect=AssertionError("ollama should not be called"))
    monkeypatch.setattr(joe_module.urllib.request, "urlopen", bomb)
    out = joe_module._ollama_once("joe-gemma", "hello world via mlx")
    assert out.startswith("MLX_SAW: hello world")


def test_ollama_once_falls_back_to_ollama_when_no_detect(joe_module, monkeypatch):
    """When _detect_llm returns "", _ollama_once should still talk to ollama."""
    joe_module._LLM_DETECTED = ""
    joe_module.LLM_BASE_URL = ""
    fake_resp = MagicMock()
    fake_resp.read = lambda: json.dumps({"response": "ollama answered"}).encode()
    fake_resp.__enter__ = lambda self: self
    fake_resp.__exit__ = lambda self, *a: None

    calls: list[str] = []
    def fake_urlopen(req, **kw):
        calls.append(req.full_url if hasattr(req, "full_url") else str(req))
        return fake_resp
    monkeypatch.setattr(joe_module.urllib.request, "urlopen", fake_urlopen)

    out = joe_module._ollama_once("joe-gemma", "hi")
    assert out == "ollama answered"
    assert any("11434" in u for u in calls)


def test_lora_slash_in_command_names(joe_module):
    assert "lora" in joe_module.SLASH_COMMAND_NAMES
