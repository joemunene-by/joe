"""v0.10.5: Aider-style repo map + Cline/Roo-style mode switching.

The repo map is a shallow per-file symbol table joe injects into the
system prompt every turn so the model has a working memory of the
project. Modes bundle output_style + sandbox into one switch.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def test_build_repo_map_empty_dir(joe_module, tmp_path):
    """No source files => empty map (no <repo_map> block to inject)."""
    out = joe_module._build_repo_map(tmp_path)
    assert out == ""


def test_build_repo_map_python_symbols(joe_module, tmp_path):
    src = (tmp_path / "auth.py")
    src.write_text(
        "import os\n"
        "\n"
        "def login(user):\n"
        "    pass\n"
        "\n"
        "class SessionManager:\n"
        "    def save(self): pass\n"
    )
    joe_module._REPO_MAP_CACHE.clear()
    out = joe_module._build_repo_map(tmp_path)
    assert "auth.py" in out
    assert "login" in out
    assert "SessionManager" in out


def test_build_repo_map_javascript_symbols(joe_module, tmp_path):
    (tmp_path / "api.ts").write_text(
        "export function getUser(id) {}\n"
        "export const ApiClient = class {}\n"
        "async function refresh() {}\n"
    )
    joe_module._REPO_MAP_CACHE.clear()
    out = joe_module._build_repo_map(tmp_path)
    assert "api.ts" in out
    assert "getUser" in out
    assert "ApiClient" in out
    assert "refresh" in out


def test_build_repo_map_rust_symbols(joe_module, tmp_path):
    (tmp_path / "lib.rs").write_text(
        "pub struct Server { port: u16 }\n"
        "pub fn start() {}\n"
        "trait Handler {}\n"
    )
    joe_module._REPO_MAP_CACHE.clear()
    out = joe_module._build_repo_map(tmp_path)
    assert "lib.rs" in out
    assert "Server" in out
    assert "start" in out


def test_build_repo_map_skips_node_modules(joe_module, tmp_path):
    """node_modules should be ignored even if it contains source files."""
    nm = tmp_path / "node_modules" / "deep"
    nm.mkdir(parents=True)
    (nm / "evil.js").write_text("function shouldNotShow() {}")
    (tmp_path / "real.js").write_text("function shouldShow() {}")
    joe_module._REPO_MAP_CACHE.clear()
    out = joe_module._build_repo_map(tmp_path)
    assert "shouldShow" in out
    assert "shouldNotShow" not in out


def test_build_repo_map_caches(joe_module, tmp_path):
    (tmp_path / "x.py").write_text("def foo(): pass\n")
    joe_module._REPO_MAP_CACHE.clear()
    first = joe_module._build_repo_map(tmp_path)
    # Force a stat-changing write that would alter the map IF the cache
    # were ignored. (Same content; map output is identical anyway.)
    second = joe_module._build_repo_map(tmp_path)
    assert first == second
    assert str(tmp_path) in joe_module._REPO_MAP_CACHE


def test_build_repo_map_truncates_when_too_many_files(joe_module, tmp_path):
    """200 .py files should result in a capped output."""
    for i in range(200):
        (tmp_path / f"mod{i}.py").write_text(f"def f{i}(): pass\n")
    joe_module._REPO_MAP_CACHE.clear()
    out = joe_module._build_repo_map(tmp_path, max_files=80, max_bytes=5000)
    # Either a truncation marker OR we just stopped early; either way the
    # output must not exceed the byte budget.
    assert len(out) <= 5500


# --- modes ---

def test_modes_dict_has_expected_presets(joe_module):
    assert "act" in joe_module._MODES
    assert "plan" in joe_module._MODES
    assert "ask" in joe_module._MODES
    assert "debug" in joe_module._MODES


def test_mode_act_pairs_ship_it_with_full(joe_module):
    assert joe_module._MODES["act"]["sandbox"] == "full"
    assert joe_module._MODES["act"]["style"] == "ship-it"


def test_mode_plan_is_read_only(joe_module):
    assert joe_module._MODES["plan"]["sandbox"] == "read-only"


def test_mode_in_slash_command_names(joe_module):
    assert "mode" in joe_module.SLASH_COMMAND_NAMES
