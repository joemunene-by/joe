"""v0.9.5: per-tool session trust.

The bare _confirm() y/N prompt now also accepts 'a' for "always for this
tool this session". After one 'a' answer, future _confirm(..., tool=X)
calls for the same tool name auto-approve without prompting. The /trust
slash command exposes the state explicitly and supports reset.
"""
from __future__ import annotations

import io
import os
from unittest.mock import patch

import pytest


def _stub_tty(joe_module, answer: str):
    """Pipe `answer` into _confirm by faking a non-tty stdin so Rich's
    Prompt.ask falls back to the readline branch (which is testable)."""
    fake_stdin = io.StringIO(answer + "\n")
    fake_stdin.isatty = lambda: False  # type: ignore[attr-defined]
    return patch.object(joe_module.sys, "stdin", fake_stdin)


def test_confirm_y_once_does_not_set_trust(joe_module, monkeypatch):
    """Plain 'y' answers a single prompt; it does NOT add the tool to
    _SESSION_TRUST. Next call still prompts."""
    joe_module._SESSION_TRUST.clear()
    monkeypatch.delenv("JOE_AUTO_YES", raising=False)
    with _stub_tty(joe_module, "y"):
        ok = joe_module._confirm("write?", tool="write")
    assert ok is True
    assert joe_module._SESSION_TRUST.get("write") is None


def test_confirm_always_sets_session_trust(joe_module, monkeypatch):
    """Answering 'a' (always) flips the per-tool trust flag."""
    joe_module._SESSION_TRUST.clear()
    monkeypatch.delenv("JOE_AUTO_YES", raising=False)
    with _stub_tty(joe_module, "a"):
        ok = joe_module._confirm("write?", tool="write")
    assert ok is True
    assert joe_module._SESSION_TRUST.get("write") is True


def test_confirm_skips_prompt_when_trusted(joe_module, monkeypatch, capsys):
    """Once trusted, subsequent _confirm calls auto-approve and don't
    consume stdin."""
    joe_module._SESSION_TRUST.clear()
    joe_module._SESSION_TRUST["write"] = True
    monkeypatch.delenv("JOE_AUTO_YES", raising=False)
    # No stdin stub: if _confirm tried to read stdin, the test would hang.
    ok = joe_module._confirm("write again?", tool="write")
    assert ok is True
    captured = capsys.readouterr().out
    assert "auto-approved" in captured


def test_confirm_trust_is_per_tool(joe_module, monkeypatch):
    """Trusting 'write' must not trust 'bash'."""
    joe_module._SESSION_TRUST.clear()
    joe_module._SESSION_TRUST["write"] = True
    monkeypatch.delenv("JOE_AUTO_YES", raising=False)
    # The bash prompt should still need a real answer.
    with _stub_tty(joe_module, "N"):
        ok = joe_module._confirm("bash?", tool="bash")
    assert ok is False


def test_confirm_no_tool_kwarg_means_no_persist(joe_module, monkeypatch):
    """When _confirm is called without tool=, 'a' should not crash and
    should not pollute _SESSION_TRUST (nothing to key off)."""
    joe_module._SESSION_TRUST.clear()
    monkeypatch.delenv("JOE_AUTO_YES", raising=False)
    with _stub_tty(joe_module, "a"):
        ok = joe_module._confirm("something?")  # no tool=
    assert ok is True
    assert len(joe_module._SESSION_TRUST) == 0


def test_always_variants_all_trigger_persist(joe_module, monkeypatch):
    """Synonyms for 'always' all work."""
    monkeypatch.delenv("JOE_AUTO_YES", raising=False)
    for variant in ("a", "always", "trust", "all"):
        joe_module._SESSION_TRUST.clear()
        with _stub_tty(joe_module, variant):
            ok = joe_module._confirm("x?", tool="bash")
        assert ok is True
        assert joe_module._SESSION_TRUST.get("bash") is True, \
            f"variant {variant!r} should have persisted trust"


def test_yolo_short_circuits_trust(joe_module, monkeypatch):
    """JOE_AUTO_YES still wins everything; trust state irrelevant."""
    joe_module._SESSION_TRUST.clear()
    monkeypatch.setenv("JOE_AUTO_YES", "1")
    ok = joe_module._confirm("anything?", tool="write")
    assert ok is True


def test_trust_in_slash_command_names(joe_module):
    assert "trust" in joe_module.SLASH_COMMAND_NAMES
