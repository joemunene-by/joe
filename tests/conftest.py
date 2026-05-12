"""Shared fixtures: import bin/joe as a module under a tmp HOME so its
state-directory side-effects land in pytest tmp_path instead of ~/.joe-agent.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
JOE_PATH = REPO_ROOT / "bin" / "joe"


@pytest.fixture
def joe_module(tmp_path, monkeypatch):
    """Import bin/joe with HOME redirected to a clean tmp dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("JOE_DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("JOE_DEFAULT_CODER", raising=False)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    # Force a fresh import every test so module-level Path.home() reads tmp.
    if "joe_module_under_test" in sys.modules:
        del sys.modules["joe_module_under_test"]
    # bin/joe has no .py extension so we provide an explicit SourceFileLoader.
    loader = SourceFileLoader("joe_module_under_test", str(JOE_PATH))
    spec = importlib.util.spec_from_loader("joe_module_under_test", loader)
    mod = importlib.util.module_from_spec(spec)
    # @dataclass decorators at module load look up cls.__module__ in
    # sys.modules; register the module before exec so the lookup succeeds.
    sys.modules["joe_module_under_test"] = mod
    try:
        loader.exec_module(mod)
    except Exception:
        sys.modules.pop("joe_module_under_test", None)
        raise
    return mod
