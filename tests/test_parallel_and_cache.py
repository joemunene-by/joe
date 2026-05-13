"""v0.9.9: parallel tool execution + deterministic tool result cache.

Side-effect-free tools (read, grep, glob, web_fetch) get memoised by
(name, attrs, body, cwd). The <parallel> tag fans out N children
concurrently via a ThreadPoolExecutor.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest


def test_parallel_tag_in_known_tools(joe_module):
    assert "parallel" in joe_module._KNOWN_TOOL_NAMES


def test_parallel_tag_parseable(joe_module):
    call = joe_module.extract_first_tool_call(
        "<parallel>\n  <read path=\"a.py\" />\n  <read path=\"b.py\" />\n</parallel>"
    )
    assert call is not None
    assert call.name == "parallel"
    assert "<read" in call.body


def test_parse_parallel_children_extracts_each(joe_module):
    children = joe_module._parse_parallel_children(
        '  <read path="a.py" />\n'
        '  <grep pattern="TODO" path="." />\n'
        '  <glob pattern="*.py" />\n'
    )
    assert len(children) == 3
    names = [c[0] for c in children]
    assert names == ["read", "grep", "glob"]
    assert children[0][1]["path"] == "a.py"


def test_parse_parallel_skips_disallowed_children(joe_module):
    """write/bash/edit should not be picked up by the parallel parser
    (they're not side-effect-free)."""
    children = joe_module._parse_parallel_children(
        '<read path="a.py" /><write path="x">y</write>'
    )
    names = [c[0] for c in children]
    assert "read" in names
    assert "write" not in names


def test_parallel_empty_body_errors(joe_module):
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_parallel({}, "")


def test_parallel_with_unparseable_children_errors(joe_module):
    """Prose with no children should refuse."""
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_parallel({}, "no tags here just words")


def test_parallel_single_child_unwraps_to_dispatch(joe_module, tmp_path, monkeypatch):
    """Single-child parallel should just run the child directly (no thread overhead)."""
    p = tmp_path / "single.txt"
    p.write_text("hello world")
    out = joe_module.tool_parallel(
        {}, f'<read path="{p}" />',
    )
    assert "hello world" in out


def test_parallel_runs_two_reads_concurrently(joe_module, tmp_path):
    a = tmp_path / "a.txt"; a.write_text("aaa-content")
    b = tmp_path / "b.txt"; b.write_text("bbb-content")
    out = joe_module.tool_parallel(
        {}, f'<read path="{a}" />\n<read path="{b}" />',
    )
    assert "aaa-content" in out
    assert "bbb-content" in out
    # Output labels each child by its tag name + 1-indexed position.
    assert "child 1" in out and "child 2" in out


def test_cache_key_distinguishes_inputs(joe_module):
    k1 = joe_module._cache_key("read", {"path": "a.py"}, "")
    k2 = joe_module._cache_key("read", {"path": "b.py"}, "")
    assert k1 != k2


def test_cached_or_run_skips_runner_on_cache_hit(joe_module):
    joe_module._TOOL_RESULT_CACHE.clear()
    calls = {"n": 0}
    def runner() -> str:
        calls["n"] += 1
        return "side-effect-free result"
    out1 = joe_module._cached_or_run("read", {"path": "x"}, "", runner)
    out2 = joe_module._cached_or_run("read", {"path": "x"}, "", runner)
    assert calls["n"] == 1  # runner called only once
    assert "side-effect-free result" in out1
    assert "side-effect-free result" in out2
    assert "[cache hit]" in out2 and "[cache hit]" not in out1


def test_cached_or_run_bypasses_when_not_cacheable(joe_module):
    """A non-cacheable tool name should ALWAYS call the runner."""
    joe_module._TOOL_RESULT_CACHE.clear()
    calls = {"n": 0}
    def runner() -> str:
        calls["n"] += 1
        return "fresh"
    joe_module._cached_or_run("bash", {}, "ls", runner)
    joe_module._cached_or_run("bash", {}, "ls", runner)
    assert calls["n"] == 2  # called both times; not cached


def test_cached_or_run_different_cwd_misses_cache(joe_module, tmp_path, monkeypatch):
    """The cache key includes cwd; same args under different cwd should
    not collide."""
    joe_module._TOOL_RESULT_CACHE.clear()
    calls = {"n": 0}
    def runner() -> str:
        calls["n"] += 1
        return f"call-{calls['n']}"
    a = tmp_path / "a"; a.mkdir()
    b = tmp_path / "b"; b.mkdir()
    monkeypatch.chdir(a)
    joe_module._cached_or_run("read", {"path": "x"}, "", runner)
    monkeypatch.chdir(b)
    joe_module._cached_or_run("read", {"path": "x"}, "", runner)
    assert calls["n"] == 2  # cwd changed -> cache miss
