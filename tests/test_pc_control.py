"""v0.9.7: agentic PC control tool parsing + dispatch.

The actual click/type/key invocations depend on pyautogui and a real
display, so these tests cover only the parser + dispatcher + safe
side-effect-free paths (screen capture failure surface, clipboard
no-binary fallback, etc.).
"""
from __future__ import annotations

import pytest


def test_screen_tag_parseable(joe_module):
    call = joe_module.extract_first_tool_call("<screen />")
    assert call is not None
    assert call.name == "screen"


def test_click_tag_parseable_with_attrs(joe_module):
    call = joe_module.extract_first_tool_call(
        '<click x="100" y="200" button="left" clicks="2" />'
    )
    assert call is not None
    assert call.name == "click"
    assert call.attrs["x"] == "100"
    assert call.attrs["y"] == "200"


def test_type_tag_parseable_with_body(joe_module):
    call = joe_module.extract_first_tool_call(
        "<type>hello world</type>"
    )
    assert call is not None
    assert call.name == "type"
    assert call.body == "hello world"


def test_key_tag_parseable(joe_module):
    call = joe_module.extract_first_tool_call("<key>cmd+c</key>")
    assert call is not None
    assert call.name == "key"
    assert call.body == "cmd+c"


def test_open_tag_parseable(joe_module):
    call = joe_module.extract_first_tool_call(
        "<open>https://example.com</open>"
    )
    assert call is not None
    assert call.name == "open"
    assert "example.com" in call.body


def test_clipboard_get_tag_parseable(joe_module):
    call = joe_module.extract_first_tool_call('<clipboard op="get" />')
    assert call is not None
    assert call.name == "clipboard"
    assert call.attrs["op"] == "get"


def test_clipboard_set_tag_parseable(joe_module):
    call = joe_module.extract_first_tool_call(
        '<clipboard op="set">pasted</clipboard>'
    )
    assert call is not None
    assert call.name == "clipboard"
    assert call.body == "pasted"


def test_click_requires_int_coords(joe_module):
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_click({"x": "not-a-number", "y": "5"}, "", confirm=False)


def test_click_without_coords_errors(joe_module):
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_click({}, "", confirm=False)


def test_type_empty_body_errors(joe_module):
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_type({}, "", confirm=False)


def test_open_empty_target_errors(joe_module):
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_open({}, "", confirm=False)


def test_clipboard_set_empty_errors(joe_module):
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_clipboard({"op": "set"}, "", confirm=False)


def test_clipboard_unknown_op_errors(joe_module):
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_clipboard({"op": "swap"}, "", confirm=False)
