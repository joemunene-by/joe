"""v0.7.6: scope-discipline rules in system prompt + passive-tool nudge.

Field bug that motivated this: after `<cd path="CRM" />` succeeded, joe-gemma
unsolicited-ly read README.md and then started writing a "polished" version
with hallucinated content (wrong git URL substituted from another project).

The fix has two layers we test here:
  - prompt: a 'Scope discipline' section telling the model to STOP after
    navigation / inspection tags.
  - runtime: when the tool just dispatched was passive (cd/read/grep/glob),
    the post-tool nudge explicitly tells the model the request is fulfilled.
"""
from __future__ import annotations

import pathlib


def test_system_prompt_has_scope_discipline_section(joe_module, tmp_path):
    prompt = joe_module._initial_prompt(
        "change to the CRM directory",
        tmp_path,
        session=None,
    )
    assert "Scope discipline" in prompt
    assert "NAVIGATION ONLY" in prompt
    assert "INSPECTION ONLY" in prompt


def test_system_prompt_explicitly_forbids_pre_emptive_write(joe_module, tmp_path):
    """The Scope discipline section should call out the exact failure mode:
    cd then 'while I'm here' write."""
    prompt = joe_module._initial_prompt("go to X", tmp_path, session=None)
    assert "silence, not <write>" in prompt or "silence" in prompt.lower()
    assert "[followup]" in prompt


def test_inline_write_exception_requires_explicit_request(joe_module, tmp_path):
    """The old prompt said 'pure prose changes (README, comments) inline'
    which let the model rationalise any README rewrite. New rule requires
    EXPLICIT user request."""
    prompt = joe_module._initial_prompt("touch nothing", tmp_path, session=None)
    assert "EXPLICITLY asked" in prompt
    # Old loophole phrasing should be gone.
    assert "pure prose changes (README" not in prompt


def test_passive_tool_nudge_present_in_source(joe_module):
    text = pathlib.Path(joe_module.__file__).read_text()
    assert 'PASSIVE_TOOLS = {"cd", "read", "grep", "glob"}' in text
    assert "request is now FULFILLED" in text


def test_passive_nudge_mentions_no_chain_in_write(joe_module):
    """Specifically guard against 'while you're here' chain-writes."""
    text = pathlib.Path(joe_module.__file__).read_text()
    assert "while" in text and "you're here" in text
    assert "STOP emitting tags" in text


def test_prompt_warns_against_substituted_facts(joe_module, tmp_path):
    """The CRM bug substituted Complex-Developers-Web's URL into CRM's
    README. The prompt should explicitly forbid substituting facts."""
    prompt = joe_module._initial_prompt("nav", tmp_path, session=None)
    assert "substitute facts" in prompt or "substitute" in prompt.lower()
