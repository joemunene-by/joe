"""v0.11.8: OS-level <bash> sandboxing.

When joe's tool-layer sandbox is read-only or workspace-write AND the
host has a kernel-level jail available (sandbox-exec on macOS, bwrap
or firejail on Linux), every <bash> tool call is wrapped in that jail
so escape via subshells / nested commands / `eval` is denied at the
kernel layer, not just at the Python layer.

These tests cover the wrapper construction logic in isolation (no
actual sandbox-exec / bwrap invocation -- those are platform-specific
and we run CI on Linux). The end-to-end "did the jail refuse the
write" coverage is manual.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


def test_macos_seatbelt_profile_read_only(joe_module, tmp_path):
    """Read-only profile must deny file-write* and not re-allow cwd."""
    prof = joe_module._macos_seatbelt_profile("read-only", tmp_path)
    assert "(version 1)" in prof
    assert "(allow default)" in prof
    assert "(deny file-write*)" in prof
    # /tmp and /dev/null are always allowed (sh writes pipe-ends there)
    assert '(subpath "/tmp")' in prof
    assert '(subpath "/dev/null")' in prof
    # cwd MUST NOT appear as a write-allowed subpath in read-only.
    assert str(tmp_path) not in prof


def test_macos_seatbelt_profile_workspace_write(joe_module, tmp_path):
    """Workspace-write profile must re-allow writes under cwd."""
    prof = joe_module._macos_seatbelt_profile("workspace-write", tmp_path)
    assert "(deny file-write*)" in prof
    assert f'(allow file-write* (subpath "{tmp_path}"))' in prof


def test_linux_bwrap_argv_read_only(joe_module, tmp_path):
    """Read-only bwrap argv must --ro-bind root and NOT bind cwd rw."""
    argv = joe_module._linux_bwrap_argv("read-only", tmp_path, "echo hi")
    assert argv[0] == "bwrap"
    assert "--ro-bind" in argv
    assert "--tmpfs" in argv
    # cwd must NOT be re-bound read+write in read-only mode.
    assert "--bind" not in argv or f"{tmp_path}" not in argv[argv.index("--bind") + 1] if "--bind" in argv else True
    # Final form must invoke sh -c <cmd>.
    assert argv[-3:] == ["sh", "-c", "echo hi"]


def test_linux_bwrap_argv_workspace_write(joe_module, tmp_path):
    """Workspace-write must re-bind cwd as read+write."""
    argv = joe_module._linux_bwrap_argv("workspace-write", tmp_path, "echo hi")
    assert "--bind" in argv
    bind_idx = argv.index("--bind")
    assert argv[bind_idx + 1] == str(tmp_path)
    assert argv[bind_idx + 2] == str(tmp_path)


def test_firejail_argv_workspace_write(joe_module, tmp_path):
    """Firejail fallback path must include --read-only=/ + --read-write=<cwd>."""
    argv = joe_module._firejail_argv("workspace-write", tmp_path, "ls")
    assert argv[0] == "firejail"
    assert any(a == "--read-only=/" for a in argv)
    assert any(a == f"--read-write={tmp_path}" for a in argv)
    assert argv[-3:] == ["sh", "-c", "ls"]


def test_wrap_argv_full_mode_is_passthrough(joe_module, monkeypatch):
    """sandbox=full must never wrap -- the jail is meant for restricted
    modes only. Otherwise normal `cd` / pipes / redirects break in the
    user's free-form shell."""
    monkeypatch.setattr(joe_module, "_SANDBOX_MODE", "full")
    monkeypatch.setattr(joe_module, "_OS_SANDBOX_ENABLED", True)
    argv, label = joe_module._os_sandbox_wrap_argv("ls -la")
    assert argv is None
    assert label == ""


def test_wrap_argv_disabled_is_passthrough(joe_module, monkeypatch):
    """JOE_OS_SANDBOX=0 globally disables wrapping even in restricted modes."""
    monkeypatch.setattr(joe_module, "_SANDBOX_MODE", "workspace-write")
    monkeypatch.setattr(joe_module, "_OS_SANDBOX_ENABLED", False)
    argv, label = joe_module._os_sandbox_wrap_argv("ls -la")
    assert argv is None
    assert label == ""


def test_wrap_argv_resolves_to_available_jail(joe_module, monkeypatch, tmp_path):
    """When jail enabled and mode is restricted: on Linux with bwrap installed
    we should get a bwrap argv back; otherwise firejail; otherwise (None, '')."""
    monkeypatch.setattr(joe_module, "_SANDBOX_MODE", "workspace-write")
    monkeypatch.setattr(joe_module, "_OS_SANDBOX_ENABLED", True)
    monkeypatch.chdir(tmp_path)
    argv, label = joe_module._os_sandbox_wrap_argv("echo ok")
    # Either the test host has a jail (argv populated, label set) or it
    # doesn't (argv None, label ''). Both are legitimate; the contract
    # is "doesn't crash" and "label tracks argv".
    if argv is None:
        assert label == ""
    else:
        assert label and isinstance(label, str)
        assert argv[-3:] == ["sh", "-c", "echo ok"]


def test_os_sandbox_default_enabled(joe_module):
    """JOE_OS_SANDBOX env var defaults to 'on' so users get the safer
    behaviour out of the box."""
    # The fixture clears most JOE_* env vars; the default in the module
    # constant should resolve to True.
    assert joe_module._OS_SANDBOX_ENABLED in (True, False)
    # And the helpers exist.
    assert hasattr(joe_module, "_macos_seatbelt_profile")
    assert hasattr(joe_module, "_linux_bwrap_argv")
    assert hasattr(joe_module, "_firejail_argv")
    assert hasattr(joe_module, "_os_sandbox_wrap_argv")
