"""v0.8.3: block catch-all grep patterns + system-prompt rule.

Field bug: after `<cd path="CRM" />` joe-gemma emitted
`<grep pattern=".*" path="." />` which matched every line of every file
under CRM and drowned both the model context and the live transcript
viewer. v0.8.3 rejects the catch-all at the tool layer with a useful
hint, AND adds the rule to the system prompt so the model doesn't try
in the first place.
"""
from __future__ import annotations

import pathlib

import pytest


def test_grep_catchall_rejected_dotstar(joe_module):
    with pytest.raises(joe_module.ToolError) as exc:
        joe_module.tool_grep({"pattern": ".*", "path": "."}, "")
    msg = str(exc.value)
    assert "catch-all" in msg.lower() or "every line" in msg.lower()


def test_grep_catchall_rejected_dotplus(joe_module):
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_grep({"pattern": ".+", "path": "."}, "")


def test_grep_catchall_rejected_single_dot(joe_module):
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_grep({"pattern": ".", "path": "."}, "")


def test_grep_catchall_rejected_anchor_only(joe_module):
    """`^` matches the start of every line. `$` matches every empty line.
    Both produce one row per line and should be refused."""
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_grep({"pattern": "^", "path": "."}, "")
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_grep({"pattern": "$", "path": "."}, "")


def test_grep_catchall_rejected_with_whitespace(joe_module):
    """The check should strip whitespace -- ` .*  ` still gets blocked."""
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_grep({"pattern": "  .*  "}, "")


def test_grep_specific_pattern_still_works(joe_module, tmp_path):
    """A tight pattern should pass through to the underlying grep."""
    (tmp_path / "src.py").write_text(
        "def foo():\n    pass\nclass Bar:\n    pass\n"
    )
    # 'class' is a specific literal; should not be blocked here even if
    # the subsequent subprocess call fails for environment reasons. We
    # only assert that the catch-all guard does NOT fire.
    try:
        joe_module.tool_grep({"pattern": "class", "path": str(tmp_path)}, "")
    except joe_module.ToolError as e:
        assert "catch-all" not in str(e).lower()
        assert "every line" not in str(e).lower()


def test_system_prompt_warns_about_catchall_grep(joe_module, tmp_path):
    prompt = joe_module._initial_prompt("find something", tmp_path, session=None)
    assert "Tool discipline" in prompt
    assert ".*" in prompt
    assert "catch-all" in prompt.lower()


def test_system_prompt_offers_alternatives(joe_module, tmp_path):
    prompt = joe_module._initial_prompt("find something", tmp_path, session=None)
    # Should point the model toward ls / glob / literal-token greps.
    assert "<bash>ls</bash>" in prompt or "ls</bash>" in prompt
    assert "<glob" in prompt
