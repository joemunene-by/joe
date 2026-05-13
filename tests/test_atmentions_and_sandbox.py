"""v0.10.4: @-mentions (Cursor/Continue.dev style) + sandbox modes
(Codex-inspired)."""
from __future__ import annotations

from pathlib import Path

import pytest


# --- @-mentions ---

def test_expand_at_mentions_noop_when_no_at(joe_module):
    out = joe_module._expand_at_mentions("just a normal message")
    assert out == "just a normal message"


def test_expand_at_mentions_injects_file(joe_module, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "auth.py").write_text("def login(user):\n    pass\n")
    out = joe_module._expand_at_mentions("@auth.py what's wrong here?")
    assert "<file path=\"auth.py\">" in out
    assert "def login" in out
    # The original prose is still in the message.
    assert "what's wrong here?" in out


def test_expand_at_mentions_unresolved_passthrough(joe_module, tmp_path, monkeypatch):
    """@something-that-doesnt-exist should NOT crash and should be left
    in the prose untouched (so the model can ask the user about it)."""
    monkeypatch.chdir(tmp_path)
    out = joe_module._expand_at_mentions("@nope/missing.py review please")
    assert out == "@nope/missing.py review please"


def test_expand_at_mentions_multiple_distinct(joe_module, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.py").write_text("AAA")
    (tmp_path / "b.py").write_text("BBB")
    out = joe_module._expand_at_mentions("compare @a.py to @b.py")
    assert "AAA" in out and "BBB" in out


def test_expand_at_mentions_dedups(joe_module, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "x.py").write_text("ONLY ONCE")
    out = joe_module._expand_at_mentions("@x.py and @x.py")
    # Content should appear ONCE, not twice.
    assert out.count("ONLY ONCE") == 1


def test_expand_at_mentions_strips_trailing_punctuation(joe_module, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "foo.py").write_text("PAYLOAD")
    out = joe_module._expand_at_mentions("look at @foo.py.")
    assert "PAYLOAD" in out


def test_expand_at_mentions_truncates_huge_files(joe_module, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "huge.txt").write_text("a" * 50_000)
    out = joe_module._expand_at_mentions("@huge.txt")
    assert "[... truncated ...]" in out
    assert len(out) < 35_000


# --- sandbox modes ---

def test_sandbox_full_allows_all(joe_module, monkeypatch):
    monkeypatch.setattr(joe_module, "_SANDBOX_MODE", "full")
    for tool in ("write", "bash", "browser", "click", "read"):
        assert joe_module._sandbox_allows(tool)


def test_sandbox_read_only_blocks_writes(joe_module, monkeypatch):
    monkeypatch.setattr(joe_module, "_SANDBOX_MODE", "read-only")
    assert not joe_module._sandbox_allows("write")
    assert not joe_module._sandbox_allows("edit")
    assert not joe_module._sandbox_allows("bash")
    assert not joe_module._sandbox_allows("browser")
    # but reads + glob + grep stay
    assert joe_module._sandbox_allows("read")
    assert joe_module._sandbox_allows("grep")


def test_sandbox_workspace_write_allows_writes(joe_module, monkeypatch):
    monkeypatch.setattr(joe_module, "_SANDBOX_MODE", "workspace-write")
    assert joe_module._sandbox_allows("write")
    assert joe_module._sandbox_allows("edit")
    assert joe_module._sandbox_allows("multi_edit")
    # but click/bash/browser still blocked
    assert not joe_module._sandbox_allows("click")
    assert not joe_module._sandbox_allows("bash")
    assert not joe_module._sandbox_allows("browser")


def test_sandbox_path_check_refuses_outside_cwd(joe_module, tmp_path, monkeypatch):
    monkeypatch.setattr(joe_module, "_SANDBOX_MODE", "workspace-write")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(joe_module.ToolError) as exc:
        joe_module._sandbox_check_path("write", "/etc/passwd")
    assert "refuses" in str(exc.value) and "outside" in str(exc.value)


def test_sandbox_path_check_allows_inside_cwd(joe_module, tmp_path, monkeypatch):
    monkeypatch.setattr(joe_module, "_SANDBOX_MODE", "workspace-write")
    monkeypatch.chdir(tmp_path)
    # Should not raise.
    joe_module._sandbox_check_path("write", str(tmp_path / "ok.py"))


def test_sandbox_path_check_noop_for_read(joe_module, tmp_path, monkeypatch):
    """The path check is for writes only; read should pass even outside cwd."""
    monkeypatch.setattr(joe_module, "_SANDBOX_MODE", "workspace-write")
    monkeypatch.chdir(tmp_path)
    joe_module._sandbox_check_path("read", "/etc/passwd")  # should not raise


def test_sandbox_in_slash_command_names(joe_module):
    assert "sandbox" in joe_module.SLASH_COMMAND_NAMES
