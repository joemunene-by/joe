"""v0.10.6: skills system. ~/.joe-agent/skills/<name>/SKILL.md packages
with frontmatter (name, description, when_to_use), auto-injected into
the system prompt when the user message matches the when_to_use trigger
list. Mirrors Claude Code's skills surface."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


def _write_skill(joe_module, name: str, frontmatter: str, body: str = "body content") -> Path:
    d = joe_module.SKILLS_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n{body}\n")
    return d


def test_skills_dir_constant(joe_module):
    assert joe_module.SKILLS_DIR.name == "skills"


def test_load_skills_empty_dir(joe_module):
    out = joe_module.load_skills()
    assert out == {}


def test_load_skills_picks_up_skill_md(joe_module):
    _write_skill(joe_module, "pr-review",
                 "name: pr-review\n"
                 "description: senior code review\n"
                 "when_to_use: review, audit, check for bugs")
    out = joe_module.load_skills()
    assert "pr-review" in out
    assert out["pr-review"]["description"] == "senior code review"


def test_load_skills_uses_dir_name_when_frontmatter_missing(joe_module):
    """If SKILL.md has no `name:` field, fall back to the directory name."""
    _write_skill(joe_module, "fallback-name",
                 "description: something\n"
                 "when_to_use: foo")
    out = joe_module.load_skills()
    assert "fallback-name" in out


def test_load_skills_skips_dir_without_skill_md(joe_module):
    """A directory under skills/ that doesn't contain SKILL.md is ignored."""
    (joe_module.SKILLS_DIR / "empty-dir").mkdir(parents=True, exist_ok=True)
    out = joe_module.load_skills()
    assert "empty-dir" not in out


def test_relevant_skills_matches_trigger_word(joe_module):
    """User message containing 'review' triggers the pr-review skill."""
    _write_skill(joe_module, "pr-review",
                 "name: pr-review\n"
                 "description: code review\n"
                 "when_to_use: review, audit, security")
    joe_module._LOADED_SKILLS = joe_module.load_skills()
    matched = joe_module._relevant_skills("please review src/auth.py")
    assert any(s["name"] == "pr-review" for s in matched)


def test_relevant_skills_misses_when_no_trigger(joe_module):
    _write_skill(joe_module, "pr-review",
                 "name: pr-review\n"
                 "description: code review\n"
                 "when_to_use: review, audit")
    joe_module._LOADED_SKILLS = joe_module.load_skills()
    matched = joe_module._relevant_skills("compile this binary")
    assert not any(s["name"] == "pr-review" for s in matched)


def test_skills_block_returns_empty_when_no_match(joe_module):
    _write_skill(joe_module, "pr-review",
                 "name: pr-review\n"
                 "description: x\n"
                 "when_to_use: completely-unrelated-phrase")
    joe_module._LOADED_SKILLS = joe_module.load_skills()
    assert joe_module._skills_block("normal request") == ""


def test_skills_block_includes_body_on_match(joe_module):
    _write_skill(joe_module, "review",
                 "name: review\n"
                 "description: x\n"
                 "when_to_use: review",
                 body="When reviewing, check for SQL injection.")
    joe_module._LOADED_SKILLS = joe_module.load_skills()
    block = joe_module._skills_block("please review my code")
    assert "<skill_available" in block
    assert "SQL injection" in block


def test_skills_in_slash_command_names(joe_module):
    assert "skills" in joe_module.SLASH_COMMAND_NAMES


def test_loop_in_slash_command_names(joe_module):
    assert "loop" in joe_module.SLASH_COMMAND_NAMES
