"""v0.10.2: reasoning trace capture for <think>...</think>-emitting models.

DeepSeek-R1 and similar models emit chain-of-thought in <think> blocks
that pollute downstream tool-call parsing. capture_reasoning_trace
strips them, persists each block to think.sqlite, returns the clean
response. /think show <hash> surfaces past traces.
"""
from __future__ import annotations

import pytest


def test_capture_returns_input_unchanged_when_no_think(joe_module):
    """A response without <think> blocks should pass through unchanged."""
    response = "Just a normal answer with no thinking blocks."
    out = joe_module.capture_reasoning_trace("any-model", response)
    assert out == response


def test_capture_strips_think_blocks(joe_module):
    """Block with reasoning + answer should return just the answer."""
    response = "<think>let me consider this... yes, 4 is right</think>The answer is 4."
    out = joe_module.capture_reasoning_trace("any-model", response)
    assert "let me consider" not in out
    assert "The answer is 4." in out


def test_capture_handles_multiple_think_blocks(joe_module):
    response = (
        "<think>first thought</think>"
        "intermediate prose "
        "<think>second thought</think>"
        "final answer"
    )
    out = joe_module.capture_reasoning_trace("any-model", response)
    assert "first thought" not in out
    assert "second thought" not in out
    assert "intermediate prose" in out
    assert "final answer" in out


def test_capture_handles_case_insensitive(joe_module):
    """<THINK> and <Think> should match too."""
    out = joe_module.capture_reasoning_trace(
        "m", "<THINK>upper</THINK>answer",
    )
    assert "upper" not in out
    assert "answer" in out


def test_show_reasoning_trace_returns_none_for_unknown_hash(joe_module):
    assert joe_module.show_reasoning_trace("zzzzzz-no-such") is None


def test_show_reasoning_trace_requires_min_4_chars(joe_module):
    assert joe_module.show_reasoning_trace("abc") is None
    assert joe_module.show_reasoning_trace("") is None


def test_capture_persists_to_thinkdb(joe_module):
    """After capture + persist, show_reasoning_trace should find the
    trace by its session id (or hash)."""
    joe_module._TURN_CTX["session"] = "test-session-12345"
    joe_module.capture_reasoning_trace(
        "deepseek-r1:14b",
        "<think>step 1: x. step 2: y.</think>therefore z",
    )
    traces = joe_module.show_reasoning_trace("test-session-12345")
    assert traces is not None
    assert any("step 1" in t for t in traces)


def test_think_in_slash_command_names(joe_module):
    assert "think" in joe_module.SLASH_COMMAND_NAMES


def test_diff_model_in_slash_command_names(joe_module):
    assert "diff-model" in joe_module.SLASH_COMMAND_NAMES or \
           "diffmodel" in joe_module.SLASH_COMMAND_NAMES
