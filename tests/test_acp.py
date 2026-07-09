"""v0.13.0: ACP bridge (bin/joe-acp). Speaks Agent Client Protocol v1 over
stdio so ACP editors (Zed agent panel, Neovim, Emacs, JetBrains) can run joe
as a first-class agent.

Offline: no ollama and no real `joe` invocation. The bridge is spawned as a
real subprocess with JOE_ACP_BIN pointed at a stub shell script, so these
tests exercise the actual wire: newline-delimited JSON-RPC, streaming
session/update notifications, and cancellation.
"""
from __future__ import annotations

import importlib.util
import json
import queue
import subprocess
import sys
import threading
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ACP_PATH = REPO_ROOT / "bin" / "joe-acp"

ECHO_STUB = """#!/bin/sh
# argv: -p <prompt> -s <session> ; echo both back so tests can assert.
echo "stub-reply: $2"
echo "session: $4"
"""

SLEEP_STUB = """#!/bin/sh
sleep 30
"""


class AcpClient:
    """Minimal ACP test client: spawn joe-acp, send requests, collect
    interleaved notifications until each response arrives."""

    def __init__(self, stub_body: str, tmp_path: Path):
        stub = tmp_path / "joe-stub"
        stub.write_text(stub_body)
        stub.chmod(0o755)
        self.proc = subprocess.Popen(
            [sys.executable, str(ACP_PATH)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
            env={"PATH": "/usr/bin:/bin", "JOE_ACP_BIN": str(stub),
                 "HOME": str(tmp_path)},
        )
        self.next_id = 0
        self.lines: queue.Queue = queue.Queue()
        t = threading.Thread(target=self._reader, daemon=True)
        t.start()

    def _reader(self):
        for line in self.proc.stdout:
            self.lines.put(json.loads(line))

    def notify(self, method: str, params: dict) -> None:
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: dict, timeout: float = 10.0):
        """Send a request; return (response, notifications-seen-before-it)."""
        self.next_id += 1
        rid = self.next_id
        msg = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params}
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        notes = []
        while True:
            got = self.lines.get(timeout=timeout)
            if got.get("id") == rid:
                return got, notes
            notes.append(got)

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=5)


@pytest.fixture
def client(tmp_path):
    c = AcpClient(ECHO_STUB, tmp_path)
    yield c
    c.close()


def _new_session(client, cwd: str):
    resp, _ = client.request("initialize", {"protocolVersion": 1,
                                            "clientCapabilities": {}})
    assert resp["result"]["protocolVersion"] == 1
    resp, _ = client.request("session/new", {"cwd": cwd, "mcpServers": []})
    return resp["result"]["sessionId"]


def test_initialize_capabilities(client):
    resp, _ = client.request("initialize", {"protocolVersion": 1,
                                            "clientCapabilities": {}})
    caps = resp["result"]["agentCapabilities"]
    assert caps["loadSession"] is False
    assert caps["promptCapabilities"]["embeddedContext"] is True
    assert resp["result"]["authMethods"] == []


def test_session_new_and_bad_cwd(client, tmp_path):
    sid = _new_session(client, str(tmp_path))
    assert sid.startswith("acp-")
    resp, _ = client.request("session/new",
                             {"cwd": str(tmp_path / "nope"), "mcpServers": []})
    assert resp["error"]["code"] == -32602


def test_prompt_streams_chunks_and_ends_turn(client, tmp_path):
    sid = _new_session(client, str(tmp_path))
    resp, notes = client.request("session/prompt", {
        "sessionId": sid,
        "prompt": [{"type": "text", "text": "hello joe"}],
    })
    assert resp["result"]["stopReason"] == "end_turn"
    chunks = [n for n in notes if n.get("method") == "session/update"
              and n["params"]["update"]["sessionUpdate"] == "agent_message_chunk"]
    assert chunks, "expected at least one agent_message_chunk"
    text = "".join(c["params"]["update"]["content"]["text"] for c in chunks)
    assert "stub-reply: hello joe" in text
    # the ACP session id doubles as the joe -s session name
    assert f"session: {sid}" in text


def test_prompt_flattens_context_blocks(client, tmp_path):
    sid = _new_session(client, str(tmp_path))
    resp, notes = client.request("session/prompt", {
        "sessionId": sid,
        "prompt": [
            {"type": "text", "text": "explain this"},
            {"type": "resource",
             "resource": {"uri": "file:///a.py", "text": "print(1)"}},
            {"type": "resource_link", "uri": "file:///b.py"},
        ],
    })
    assert resp["result"]["stopReason"] == "end_turn"
    text = "".join(
        n["params"]["update"]["content"]["text"]
        for n in notes if n.get("method") == "session/update")
    assert "[context: file:///a.py]" in text
    assert "print(1)" in text
    assert "[file: file:///b.py]" in text


def test_unknown_method_and_unknown_session(client, tmp_path):
    resp, _ = client.request("session/set_mode", {"mode": "x"})
    assert resp["error"]["code"] == -32601
    resp, _ = client.request("session/prompt", {
        "sessionId": "acp-bogus", "prompt": [{"type": "text", "text": "hi"}]})
    assert resp["error"]["code"] == -32602


def test_cancel_kills_prompt(tmp_path):
    c = AcpClient(SLEEP_STUB, tmp_path)
    try:
        sid = _new_session(c, str(tmp_path))
        c.next_id += 1
        rid = c.next_id
        c.proc.stdin.write(json.dumps({
            "jsonrpc": "2.0", "id": rid, "method": "session/prompt",
            "params": {"sessionId": sid,
                       "prompt": [{"type": "text", "text": "long task"}]},
        }) + "\n")
        c.proc.stdin.flush()
        c.notify("session/cancel", {"sessionId": sid})
        while True:
            got = c.lines.get(timeout=10)
            if got.get("id") == rid:
                assert got["result"]["stopReason"] == "cancelled"
                break
    finally:
        c.close()


def test_prompt_text_unit():
    loader = SourceFileLoader("joe_acp_under_test", str(ACP_PATH))
    spec = importlib.util.spec_from_loader("joe_acp_under_test", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    out = mod.prompt_text([
        {"type": "text", "text": "a"},
        {"type": "resource", "resource": {"uri": "u", "blob": "eA=="}},
        {"type": "funky"},
    ])
    assert "a" in out
    assert "[attachment (binary, skipped): u]" in out
    assert "[unsupported funky block skipped]" in out
