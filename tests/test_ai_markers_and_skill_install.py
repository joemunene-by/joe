"""v0.10.7: AI! markers (Aider style) + skill install from git URL."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest


def test_ai_marker_regex_matches_hash(joe_module):
    matches = joe_module._AI_MARKER_RE.findall("# AI! refactor this to async\n")
    assert "refactor this to async" in matches[0]


def test_ai_marker_regex_matches_slashslash(joe_module):
    matches = joe_module._AI_MARKER_RE.findall("// AI! make this lazy\n")
    assert "make this lazy" in matches[0]


def test_ai_marker_regex_matches_html_comment(joe_module):
    matches = joe_module._AI_MARKER_RE.findall("<!-- AI! add aria-label -->")
    assert "add aria-label" in matches[0]


def test_find_ai_markers_finds_in_py_file(joe_module, tmp_path):
    (tmp_path / "src.py").write_text(
        "def foo():\n"
        "    # AI! refactor this to use pathlib\n"
        "    return open(p).read()\n"
    )
    markers = joe_module.find_ai_markers(tmp_path)
    assert len(markers) >= 1
    path, lineno, text = markers[0]
    assert path.name == "src.py"
    assert lineno == 2
    assert "pathlib" in text


def test_find_ai_markers_skips_node_modules(joe_module, tmp_path):
    nm = tmp_path / "node_modules" / "evil"
    nm.mkdir(parents=True)
    (nm / "x.js").write_text("// AI! should not be picked up\n")
    (tmp_path / "real.js").write_text("// AI! pick me up\n")
    markers = joe_module.find_ai_markers(tmp_path)
    assert any("real.js" in str(m[0]) for m in markers)
    assert not any("evil" in str(m[0]) for m in markers)


def test_find_ai_markers_returns_empty_when_none(joe_module, tmp_path):
    (tmp_path / "clean.py").write_text("def foo(): pass\n")
    markers = joe_module.find_ai_markers(tmp_path)
    assert markers == []


def test_install_skill_from_git_requires_git(joe_module, monkeypatch):
    monkeypatch.setattr(joe_module.shutil, "which",
                        lambda name: None if name == "git" else "/bin/" + name)
    ok, msg = joe_module.install_skill_from_git("https://example.com/x.git")
    assert not ok
    assert "git not on PATH" in msg


def test_install_skill_from_git_rejects_unsafe_name(joe_module):
    """A URL whose tail isn't a clean alphanumeric identifier should be
    refused before any git clone attempt."""
    # URL parses to "weird name" which contains a space.
    ok, msg = joe_module.install_skill_from_git("https://example.com/weird name")
    assert not ok
    assert "not a clean identifier" in msg or "git" in msg.lower()


def test_install_skill_refuses_existing_target(joe_module):
    """Trying to reinstall an existing skill should fail with a clear message."""
    existing = joe_module.SKILLS_DIR / "already-here"
    existing.mkdir(parents=True, exist_ok=True)
    (existing / "marker").touch()
    ok, msg = joe_module.install_skill_from_git("https://example.com/already-here.git")
    assert not ok
    assert "already installed" in msg


def test_ai_markers_in_slash_command_names(joe_module):
    assert "ai-markers" in joe_module.SLASH_COMMAND_NAMES
