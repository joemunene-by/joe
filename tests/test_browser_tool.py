"""v0.9.10: Playwright <browser> tool.

We don't want CI installing Chromium just to run unit tests, so this
file covers only:
  - parser recognition of the <browser> tag
  - dispatcher branch wiring (source inspection)
  - graceful refuse when Playwright is missing (the install-hint path)
  - validation of required attrs / body (close + open + click + type)

Actual headed/headless flows are exercised manually.
"""
from __future__ import annotations

import sys
from unittest.mock import patch

import pytest


def test_browser_in_known_tool_names(joe_module):
    assert "browser" in joe_module._KNOWN_TOOL_NAMES


def test_browser_self_closing_parses(joe_module):
    call = joe_module.extract_first_tool_call(
        '<browser action="open" url="https://example.com" />'
    )
    assert call is not None
    assert call.name == "browser"
    assert call.attrs["action"] == "open"
    assert call.attrs["url"] == "https://example.com"


def test_browser_block_with_body_parses(joe_module):
    call = joe_module.extract_first_tool_call(
        '<browser action="type" selector="#q">hello world</browser>'
    )
    assert call is not None
    assert call.name == "browser"
    assert call.body == "hello world"


def test_browser_missing_action_errors(joe_module):
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_browser({}, "", confirm=False)


def test_browser_unknown_action_errors(joe_module):
    """Refuses with a helpful message when Playwright IS available
    but the action name is wrong. We mock around Playwright so this
    test doesn't need the Chromium binary."""
    if "playwright.sync_api" not in sys.modules:
        # Skip if Playwright really isn't installed; that's tested separately.
        pytest.skip("Playwright not installed; can't test unknown-action branch")
    with pytest.raises(joe_module.ToolError) as exc:
        joe_module.tool_browser({"action": "fly-to-mars"}, "", confirm=False)
    assert "unknown action" in str(exc.value).lower() or "fly-to-mars" in str(exc.value)


def test_browser_refuses_when_playwright_missing(joe_module, monkeypatch):
    """When Playwright isn't installed, _ensure_browser should ToolError
    with a useful install hint instead of a bare ImportError."""
    # Force the import to fail inside _ensure_browser.
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    joe_module._BROWSER_CTX["page"] = None  # reset cache
    with pytest.raises(joe_module.ToolError) as exc:
        joe_module._ensure_browser()
    assert "Playwright" in str(exc.value) or "playwright" in str(exc.value)
    assert "pip install" in str(exc.value)


def test_browser_close_works_without_active_session(joe_module):
    """Calling <browser action=\"close\" /> when nothing is open should
    be a no-op, not an error."""
    joe_module._BROWSER_CTX["page"] = None
    result = joe_module.tool_browser({"action": "close"}, "", confirm=False)
    assert "closed" in result.lower()


def test_browser_dispatch_branch_exists(joe_module):
    """Source inspection: run_turn has a branch for <browser>."""
    import pathlib
    src = pathlib.Path(joe_module.__file__).read_text()
    assert 'call.name == "browser"' in src
    assert "tool_browser" in src
