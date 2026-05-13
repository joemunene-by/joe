"""v0.9.7: custom slash commands from ~/.joe-agent/commands/*.toml
plus lifecycle hooks at ~/.joe-agent/hooks/<event>.sh.

Mirrors the surfaces Claude Code / Codex / OpenCode standardise on
so power users can drop into joe with their existing muscle memory.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest


def _commands_dir(joe_module) -> Path:
    return joe_module.COMMANDS_DIR


def _hooks_dir(joe_module) -> Path:
    return joe_module.HOOKS_DIR


def _write_command(joe_module, name: str, body: str) -> Path:
    d = _commands_dir(joe_module)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.toml"
    p.write_text(body)
    return p


def _write_hook(joe_module, event: str, body: str) -> Path:
    d = _hooks_dir(joe_module)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{event}.sh"
    p.write_text("#!/usr/bin/env bash\n" + body)
    p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return p


def test_load_custom_commands_empty_dir(joe_module):
    """No commands dir => returns empty map cleanly."""
    cmds = joe_module.load_custom_commands()
    assert isinstance(cmds, dict)


def test_load_custom_commands_picks_up_toml(joe_module):
    _write_command(joe_module, "foo", '''
description = "say foo about something"
template = "Say something about {{args}} in the cwd {{cwd}}."
''')
    cmds = joe_module.load_custom_commands()
    assert "foo" in cmds
    assert cmds["foo"]["description"] == "say foo about something"
    assert "{{args}}" in cmds["foo"]["template"]


def test_render_custom_command_substitutes_args(joe_module):
    _write_command(joe_module, "review", '''
template = "Review {{args}} please."
''')
    joe_module.load_custom_commands()
    out = joe_module.render_custom_command("review", "the README")
    assert out == "Review the README please."


def test_render_custom_command_substitutes_cwd(joe_module):
    _write_command(joe_module, "where", '''template = "Cwd is {{cwd}}"
''')
    joe_module.load_custom_commands()
    out = joe_module.render_custom_command("where", "")
    assert "Cwd is " in out
    assert "/" in out  # some path was substituted


def test_render_custom_command_unknown_returns_none(joe_module):
    joe_module.load_custom_commands()
    assert joe_module.render_custom_command("nope-not-here", "") is None


def test_load_custom_commands_skips_invalid_toml(joe_module):
    """A malformed TOML file should not crash startup."""
    d = _commands_dir(joe_module)
    d.mkdir(parents=True, exist_ok=True)
    (d / "broken.toml").write_text("this is not = valid TOML [[\n")
    _write_command(joe_module, "good", 'template = "ok"\n')
    cmds = joe_module.load_custom_commands()
    assert "good" in cmds
    assert "broken" not in cmds


def test_load_custom_commands_requires_template(joe_module):
    """A TOML file without a `template` key should be ignored."""
    _write_command(joe_module, "no-template", 'description = "missing template"\n')
    cmds = joe_module.load_custom_commands()
    assert "no-template" not in cmds


def test_fire_hook_no_script_returns_zero(joe_module):
    rc, err = joe_module._fire_hook("pre_tool")
    assert rc == 0
    assert err == ""


def test_fire_hook_executes_script(joe_module, tmp_path):
    _write_hook(joe_module, "user_prompt", "exit 0\n")
    rc, _ = joe_module._fire_hook("user_prompt")
    assert rc == 0


def test_fire_hook_propagates_nonzero(joe_module):
    _write_hook(joe_module, "pre_tool", "echo 'blocked' >&2; exit 42\n")
    rc, err = joe_module._fire_hook("pre_tool")
    assert rc == 42
    assert "blocked" in err


def test_fire_hook_passes_env_vars(joe_module, tmp_path):
    """Hooks receive JOE_HOOK_TOOL via env."""
    out_file = tmp_path / "hook-captured.txt"
    _write_hook(
        joe_module, "pre_tool",
        f'echo "tool=${{JOE_HOOK_TOOL}}" > "{out_file}"\nexit 0\n',
    )
    joe_module._fire_hook("pre_tool", {"JOE_HOOK_TOOL": "write"})
    assert out_file.exists()
    assert "tool=write" in out_file.read_text()


def test_fire_hook_handles_non_executable(joe_module):
    """A script without +x bit should be a no-op, not a crash."""
    d = _hooks_dir(joe_module)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "stop.sh"
    p.write_text("#!/bin/sh\nexit 1\n")  # but no chmod +x
    rc, _ = joe_module._fire_hook("stop")
    assert rc == 0  # treated as missing


def test_commands_in_slash_command_names(joe_module):
    assert "commands" in joe_module.SLASH_COMMAND_NAMES
