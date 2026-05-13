"""v0.10.3: Claude-Code parity pack -- output styles, statusline,
multi_edit tool, notebook_edit tool."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_output_styles_known_presets(joe_module):
    presets = joe_module._OUTPUT_STYLES
    for name in ("default", "concise", "explanatory", "learning",
                 "security", "review", "ship-it"):
        assert name in presets


def test_load_output_style_default_is_empty(joe_module):
    assert joe_module._load_output_style("default") == ""
    assert joe_module._load_output_style("") == ""


def test_load_output_style_preset_has_content(joe_module):
    style = joe_module._load_output_style("concise")
    assert len(style) > 20
    assert "terse" in style.lower() or "concise" in style.lower() or "fewest" in style.lower()


def test_load_output_style_custom_md_file(joe_module, tmp_path):
    d = joe_module.OUTPUT_STYLES_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / "my-style.md").write_text("Always respond in haiku.")
    assert joe_module._load_output_style("my-style") == "Always respond in haiku."


def test_load_output_style_unknown_returns_empty(joe_module):
    assert joe_module._load_output_style("does-not-exist-xyz") == ""


def test_list_output_styles_includes_builtins(joe_module):
    names = joe_module.list_output_styles()
    assert "concise" in names
    assert "security" in names


def test_statusline_in_slash_command_names(joe_module):
    assert "statusline" in joe_module.SLASH_COMMAND_NAMES


def test_output_style_in_slash_command_names(joe_module):
    assert "output-style" in joe_module.SLASH_COMMAND_NAMES


# --- multi_edit tests ---

def test_multi_edit_tag_parses(joe_module):
    body = "<e><old>x = 1</old><new>x = 2</new></e>"
    call = joe_module.extract_first_tool_call(
        f'<multi_edit path="src/foo.py">{body}</multi_edit>'
    )
    assert call is not None
    assert call.name == "multi_edit"
    assert "x = 1" in call.body


def test_multi_edit_missing_path_errors(joe_module):
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_multi_edit({}, "<e><old>x</old><new>y</new></e>", confirm=False)


def test_multi_edit_empty_body_errors(joe_module, tmp_path):
    p = tmp_path / "f.txt"; p.write_text("hi")
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_multi_edit({"path": str(p)}, "no entries here", confirm=False)


def test_multi_edit_applies_sequential_edits(joe_module, tmp_path, monkeypatch):
    monkeypatch.setenv("JOE_AUTO_YES", "1")
    p = tmp_path / "f.py"
    p.write_text("x = 1\ny = 2\n")
    out = joe_module.tool_multi_edit(
        {"path": str(p)},
        "<e><old>x = 1</old><new>x = 10</new></e>"
        "<e><old>y = 2</old><new>y = 20</new></e>",
        confirm=False,
    )
    assert "applied 2 edits" in out
    assert p.read_text() == "x = 10\ny = 20\n"


def test_multi_edit_atomic_on_missing_old(joe_module, tmp_path, monkeypatch):
    """If any edit's old-string is absent, NO edits land."""
    monkeypatch.setenv("JOE_AUTO_YES", "1")
    p = tmp_path / "f.txt"
    p.write_text("a\nb\n")
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_multi_edit(
            {"path": str(p)},
            "<e><old>a</old><new>A</new></e>"
            "<e><old>NOPE</old><new>X</new></e>",
            confirm=False,
        )
    # File must be untouched.
    assert p.read_text() == "a\nb\n"


# --- notebook_edit tests ---

def _ipynb(cells: list) -> str:
    return json.dumps({
        "cells": cells,
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    })


def test_notebook_edit_tag_parses(joe_module):
    call = joe_module.extract_first_tool_call(
        '<notebook_edit path="x.ipynb" cell="0" op="replace">new src</notebook_edit>'
    )
    assert call is not None
    assert call.name == "notebook_edit"


def test_notebook_edit_replace(joe_module, tmp_path, monkeypatch):
    monkeypatch.setenv("JOE_AUTO_YES", "1")
    p = tmp_path / "nb.ipynb"
    p.write_text(_ipynb([
        {"cell_type": "code", "source": ["x = 1\n"], "outputs": [],
         "execution_count": 1, "metadata": {}},
    ]))
    joe_module.tool_notebook_edit(
        {"path": str(p), "cell": "0", "op": "replace"},
        "x = 99\n", confirm=False,
    )
    nb = json.loads(p.read_text())
    assert "x = 99" in "".join(nb["cells"][0]["source"])
    # outputs cleared
    assert nb["cells"][0]["outputs"] == []


def test_notebook_edit_delete(joe_module, tmp_path, monkeypatch):
    monkeypatch.setenv("JOE_AUTO_YES", "1")
    p = tmp_path / "nb.ipynb"
    p.write_text(_ipynb([
        {"cell_type": "code", "source": ["a"], "outputs": [], "execution_count": 1, "metadata": {}},
        {"cell_type": "code", "source": ["b"], "outputs": [], "execution_count": 2, "metadata": {}},
    ]))
    joe_module.tool_notebook_edit(
        {"path": str(p), "cell": "0", "op": "delete"},
        "", confirm=False,
    )
    nb = json.loads(p.read_text())
    assert len(nb["cells"]) == 1
    assert "b" in "".join(nb["cells"][0]["source"])


def test_notebook_edit_insert(joe_module, tmp_path, monkeypatch):
    monkeypatch.setenv("JOE_AUTO_YES", "1")
    p = tmp_path / "nb.ipynb"
    p.write_text(_ipynb([
        {"cell_type": "code", "source": ["a"], "outputs": [], "execution_count": 1, "metadata": {}},
    ]))
    joe_module.tool_notebook_edit(
        {"path": str(p), "op": "insert", "cell_type": "markdown", "after": "0"},
        "# Heading\n", confirm=False,
    )
    nb = json.loads(p.read_text())
    assert len(nb["cells"]) == 2
    assert nb["cells"][1]["cell_type"] == "markdown"


def test_notebook_edit_rejects_non_ipynb(joe_module, tmp_path, monkeypatch):
    monkeypatch.setenv("JOE_AUTO_YES", "1")
    p = tmp_path / "f.py"; p.write_text("x = 1")
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_notebook_edit(
            {"path": str(p), "cell": "0", "op": "replace"},
            "x = 2", confirm=False,
        )


def test_multi_edit_in_known_tools(joe_module):
    assert "multi_edit" in joe_module._KNOWN_TOOL_NAMES


def test_notebook_edit_in_known_tools(joe_module):
    assert "notebook_edit" in joe_module._KNOWN_TOOL_NAMES
