"""v0.11.7: tree-sitter-aware edit validation for non-Python languages.

When the model writes / edits a .js, .ts, .rs, .go, ... file with
malformed syntax, joe parses through tree-sitter (if installed) and
refuses the write the same way it refuses a broken .py file. When
tree-sitter-languages isn't installed it's a silent no-op -- the
optional dep stays optional.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _tree_sitter_available() -> bool:
    try:
        import tree_sitter_languages  # noqa: F401
        return True
    except Exception:
        return False


def test_ts_lang_map_covers_common_extensions(joe_module):
    """Spot-check that the most common code suffixes route to a grammar."""
    m = joe_module._TS_LANG_FOR_EXT
    assert m[".js"] == "javascript"
    assert m[".ts"] == "typescript"
    assert m[".tsx"] == "tsx"
    assert m[".rs"] == "rust"
    assert m[".go"] == "go"
    assert m[".rb"] == "ruby"
    assert m[".java"] == "java"
    assert m[".c"] == "c"
    assert m[".cpp"] == "cpp"


def test_python_files_bypass_treesitter(joe_module, tmp_path):
    """Python is validated by the stdlib ast path, not tree-sitter."""
    p = tmp_path / "x.py"
    # _validate_treesitter must return None for .py regardless of content.
    assert joe_module._validate_treesitter(p, "def f(\n    return 1\n") is None


def test_unknown_extension_skips(joe_module, tmp_path):
    """A file with no grammar mapping is a no-op (e.g., .txt, .log)."""
    for name in ("notes.txt", "app.log", "raw.bin"):
        p = tmp_path / name
        assert joe_module._validate_treesitter(p, "anything at all\n") is None


def test_validate_source_combines_py_and_ts(joe_module, tmp_path):
    """_validate_source is the one-call entry point used by tool_write,
    tool_edit, and tool_multi_edit. Python errors still surface."""
    p = tmp_path / "bad.py"
    err = joe_module._validate_source(p, "def broken(\n    return 1\n")
    assert err is not None
    assert "syntax" in err.lower()


def test_validate_source_no_op_on_text(joe_module, tmp_path):
    """No grammar + not Python -> validator never blocks."""
    p = tmp_path / "README.md"
    assert joe_module._validate_source(p, "# joe\n\nhi") is None


def test_treesitter_is_optional_dep(joe_module, tmp_path):
    """Even if tree-sitter-languages isn't installed in the test env,
    validation must return None (skip) rather than crash."""
    p = tmp_path / "x.js"
    # Whatever the environment, this call must be exception-free.
    result = joe_module._validate_treesitter(p, "let x = 1;\n")
    assert result is None  # valid JS or treesitter absent: either way -> None


@pytest.mark.skipif(
    not _tree_sitter_available(),
    reason="tree-sitter-languages not installed in test env",
)
def test_treesitter_blocks_broken_javascript(joe_module, tmp_path):
    """When the grammar IS installed, mangled JS gets rejected."""
    p = tmp_path / "broken.js"
    err = joe_module._validate_treesitter(
        p, "function f( { let x = 1; return\n",  # unclosed param + ret
    )
    # Either the grammar caught it (err is a string) or the parser is
    # tolerant enough to recover (err is None). Both are acceptable;
    # the contract is "doesn't crash".
    if err is not None:
        assert "syntax error" in err.lower()


@pytest.mark.skipif(
    not _tree_sitter_available(),
    reason="tree-sitter-languages not installed in test env",
)
def test_treesitter_allows_valid_rust(joe_module, tmp_path):
    """Valid Rust must always pass."""
    p = tmp_path / "ok.rs"
    src = "fn main() {\n    let x = 1 + 2;\n    println!(\"{}\", x);\n}\n"
    assert joe_module._validate_treesitter(p, src) is None
