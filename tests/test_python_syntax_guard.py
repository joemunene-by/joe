"""v0.9.6: AST validation on Python writes / edits.

When the model is about to write a .py file with broken syntax, joe
catches it BEFORE the file lands on disk and reflects the error back
to the model with line:col, so the next turn fixes it instead of
shipping a syntactically broken file.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def test_valid_python_passes(joe_module, tmp_path):
    p = tmp_path / "ok.py"
    assert joe_module._validate_python_syntax(
        p, "def f(x):\n    return x + 1\n"
    ) is None


def test_invalid_python_is_caught(joe_module, tmp_path):
    p = tmp_path / "bad.py"
    err = joe_module._validate_python_syntax(
        p, "def f(\n    return 1\n",  # unclosed paren
    )
    assert err is not None
    assert "syntax error" in err.lower()
    assert "line" in err.lower()


def test_non_python_paths_skip_validation(joe_module, tmp_path):
    """Markdown / yaml / text shouldn't run through Python's parser."""
    for name in ("README.md", "config.yaml", "notes.txt"):
        p = tmp_path / name
        # Content that would be invalid as Python should still be allowed.
        assert joe_module._validate_python_syntax(p, "# heading\n- item") is None


def test_tool_write_blocks_invalid_python(joe_module, tmp_path, monkeypatch):
    """tool_write must raise ToolError when body is invalid Python."""
    monkeypatch.setenv("JOE_AUTO_YES", "1")  # skip confirm
    p = tmp_path / "broken.py"
    with pytest.raises(joe_module.ToolError) as exc:
        joe_module.tool_write(
            {"path": str(p)}, "def broken(\n    return 1\n", confirm=False,
        )
    assert "syntax" in str(exc.value).lower()
    assert not p.exists()  # file must NOT have been written


def test_tool_write_allows_valid_python(joe_module, tmp_path, monkeypatch):
    monkeypatch.setenv("JOE_AUTO_YES", "1")
    p = tmp_path / "good.py"
    result = joe_module.tool_write(
        {"path": str(p)}, "x = 1\n", confirm=False,
    )
    assert "wrote" in result
    assert p.exists()
    assert p.read_text() == "x = 1\n"
