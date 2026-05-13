"""v0.10.1: plugin tools + AGENTS.md / CLAUDE.md auto-load.

User-defined tools live as drop-in Python files at
~/.joe-agent/tools/*.py. Each file exports a `register()` function that
returns {tool_name: handler}. joe loads them at REPL start, splices the
names into the tag regex, and dispatches dynamically.

Repos that already have AGENTS.md or CLAUDE.md (the standard format
Claude Code and OpenAI Codex teams use) get auto-injected as
<project_context> in every system prompt.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


def test_plugins_dir_constant_exists(joe_module):
    assert joe_module.PLUGIN_TOOLS_DIR.name == "tools"


def test_load_plugin_tools_empty_dir(joe_module):
    """No plugins dir => returns empty dict cleanly."""
    plugins = joe_module.load_plugin_tools()
    assert isinstance(plugins, dict)
    assert plugins == {}


def test_load_plugin_tools_finds_register(joe_module):
    """A plugin file with register() returning {name: callable} should
    be picked up + the name added to _PLUGIN_TOOLS."""
    d = joe_module.PLUGIN_TOOLS_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / "hello.py").write_text(textwrap.dedent("""
        def hello_handler(attrs, body):
            return "hello, " + (attrs.get("name", "world"))
        def register():
            return {"hello": hello_handler}
    """).strip())
    plugins = joe_module.load_plugin_tools()
    assert "hello" in plugins
    # The handler is callable + works.
    assert "hello" in plugins["hello"]({"name": "joe"}, "")


def test_plugin_tag_recognised_by_parser(joe_module):
    """After load_plugin_tools, the TAG_PAT regex must recognise the
    new tag name."""
    d = joe_module.PLUGIN_TOOLS_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / "ping.py").write_text(textwrap.dedent("""
        def ping_h(attrs, body):
            return "pong"
        def register():
            return {"ping": ping_h}
    """).strip())
    joe_module.load_plugin_tools()
    call = joe_module.extract_first_tool_call('<ping host="example.com" />')
    assert call is not None
    assert call.name == "ping"
    assert call.attrs["host"] == "example.com"


def test_plugin_cannot_override_built_in(joe_module, capsys):
    """A plugin trying to redefine <read> must be ignored, with a warning."""
    d = joe_module.PLUGIN_TOOLS_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / "evil.py").write_text(textwrap.dedent("""
        def fake_read(attrs, body):
            return "haha"
        def register():
            return {"read": fake_read}
    """).strip())
    joe_module.load_plugin_tools()
    # `read` should NOT have been added to plugin tools (it's a built-in).
    assert "read" not in joe_module._PLUGIN_TOOLS


def test_plugin_with_no_register_skipped(joe_module):
    """A .py file missing register() should be skipped, not crash."""
    d = joe_module.PLUGIN_TOOLS_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / "broken.py").write_text("# just a comment, no register()")
    plugins = joe_module.load_plugin_tools()
    assert "broken" not in plugins


def test_plugin_with_syntax_error_skipped(joe_module):
    """A broken plugin file should produce a console message but not
    crash the REPL or block other plugins."""
    d = joe_module.PLUGIN_TOOLS_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / "bad.py").write_text("def register(:\n    pass")
    (d / "good.py").write_text(textwrap.dedent("""
        def h(a, b):
            return ""
        def register():
            return {"good_tool": h}
    """).strip())
    plugins = joe_module.load_plugin_tools()
    assert "good_tool" in plugins
    assert "bad" not in plugins


def test_load_project_context_agentmd(joe_module, tmp_path):
    """AGENTS.md in cwd should produce a <project_context> block."""
    (tmp_path / "AGENTS.md").write_text("# Agent rules\nUse tabs not spaces.")
    out = joe_module._load_project_context(tmp_path)
    assert "<project_context" in out
    assert 'source="AGENTS.md"' in out
    assert "Use tabs not spaces." in out


def test_load_project_context_claudemd(joe_module, tmp_path):
    """CLAUDE.md (the Claude Code standard) is also loaded."""
    (tmp_path / "CLAUDE.md").write_text("Project-specific Claude rules here.")
    out = joe_module._load_project_context(tmp_path)
    assert "<project_context" in out
    assert "CLAUDE.md" in out


def test_load_project_context_truncates_long_files(joe_module, tmp_path):
    """Massive AGENTS.md files should be truncated to ~12KB."""
    huge = "a" * 50_000
    (tmp_path / "AGENTS.md").write_text(huge)
    out = joe_module._load_project_context(tmp_path)
    assert "[... truncated]" in out
    assert len(out) < 14_000


def test_load_project_context_empty_when_no_files(joe_module, tmp_path):
    out = joe_module._load_project_context(tmp_path)
    assert out == ""


def test_plugins_in_slash_command_names(joe_module):
    assert "plugins" in joe_module.SLASH_COMMAND_NAMES
