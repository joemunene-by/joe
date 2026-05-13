"""v0.9.6: tool-emission repair hints.

When extract_first_tool_call returns None but the model clearly TRIED
to emit a tool tag, diagnose_tool_emission produces a specific repair
hint that's fed back to the model so the next turn produces valid
output.
"""
from __future__ import annotations


def test_diagnose_returns_none_for_pure_prose(joe_module):
    """A plain answer with no tag-shaped content should not trigger a hint."""
    assert joe_module.diagnose_tool_emission(
        "Switched to the CRM directory. Let me know what you want to do."
    ) is None


def test_diagnose_catches_unclosed_write(joe_module):
    """Classic failure mode: opener with no close, no self-close."""
    hint = joe_module.diagnose_tool_emission(
        '<write path="foo.py">\nx = 1\n'
    )
    assert hint is not None
    assert "write" in hint
    assert "never closed" in hint or "close" in hint.lower()


def test_diagnose_catches_typo_tag_name(joe_module):
    """`<writes>` is close to `<write>`; surface 'Did you mean'."""
    hint = joe_module.diagnose_tool_emission(
        '<writes path="foo.py">x</writes>'
    )
    assert hint is not None
    assert "writes" in hint
    assert "write" in hint  # the suggestion


def test_diagnose_catches_markdown_fence_wrap(joe_module):
    """When the model wraps the tag in ```...``` it confuses some hosts."""
    hint = joe_module.diagnose_tool_emission(
        "```xml\n<write path=\"a.py\">x</write>\n```"
    )
    assert hint is not None
    assert "markdown" in hint.lower() or "fence" in hint.lower()


def test_diagnose_ignores_unknown_unhelpful_word(joe_module):
    """A `<hr>` or `<br>` shouldn't trigger noisy hints."""
    # `<hr>` isn't even close to a known tool name so we shouldn't suggest.
    hint = joe_module.diagnose_tool_emission("here's a horizontal rule: <hr>")
    # Either None or doesn't claim a fix; both acceptable.
    if hint is not None:
        assert "did you mean" not in hint.lower() or "Known tools" in hint
