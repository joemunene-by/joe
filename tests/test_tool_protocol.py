"""Tool-call parser: the heart of how joe-gemma communicates with the shell."""
from __future__ import annotations


def test_self_closing_tool_tag(joe_module):
    call = joe_module.extract_first_tool_call('<read path="src/foo.py" />')
    assert call is not None
    assert call.name == "read"
    assert call.attrs == {"path": "src/foo.py"}
    assert call.body == ""


def test_block_tool_tag_with_body(joe_module):
    call = joe_module.extract_first_tool_call(
        '<write path="src/bar.py">print("hi")\n</write>'
    )
    assert call is not None
    assert call.name == "write"
    assert call.attrs == {"path": "src/bar.py"}
    assert "print" in call.body


def test_edit_with_old_new_body(joe_module):
    call = joe_module.extract_first_tool_call(
        '<edit path="src/baz.py"><old>x = 1</old><new>x = 2</new></edit>'
    )
    assert call is not None
    assert call.name == "edit"
    assert "<old>x = 1</old>" in call.body
    assert "<new>x = 2</new>" in call.body


def test_legacy_RUN_protocol_still_parsed(joe_module):
    """The personalised joe-gemma Modelfile teaches the older RUN: protocol."""
    call = joe_module.extract_first_tool_call("RUN: ls -la")
    assert call is not None
    assert call.name == "bash"
    assert call.body == "ls -la"


def test_path_with_slashes_does_not_break_attr_parsing(joe_module):
    call = joe_module.extract_first_tool_call(
        '<read path="/tmp/some/deep/path.txt" />'
    )
    assert call is not None
    assert call.attrs["path"] == "/tmp/some/deep/path.txt"


def test_no_tool_call_returns_none(joe_module):
    assert joe_module.extract_first_tool_call("just plain prose, no tags here") is None


def test_opener_fallback_for_missing_close(joe_module):
    """A bare opener like `<web_search query="...">` with no close
    should still parse as a self-closing call when it carries attrs."""
    call = joe_module.extract_first_tool_call(
        '<web_search query="rope reverse algorithm">'
    )
    assert call is not None
    assert call.name == "web_search"
    assert call.attrs["query"] == "rope reverse algorithm"


def test_first_tool_call_wins_over_later(joe_module):
    """Multiple tool calls in one response: only the first should be parsed
    (the shell loops between calls)."""
    call = joe_module.extract_first_tool_call(
        '<bash>echo hi</bash> later <write path="x">y</write>'
    )
    assert call is not None
    assert call.name == "bash"
    assert call.body == "echo hi"
