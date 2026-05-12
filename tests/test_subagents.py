"""Subagent loader + seeder."""
from __future__ import annotations

import pytest


def test_seed_creates_four_default_agents(joe_module):
    joe_module._seed_default_agents()
    agents = list(joe_module._list_agents())
    names = sorted(a.name for a in agents)
    # Defaults: reviewer, doc-writer, security, explainer, oncall,
    # release-manager, refactor-specialist.
    for required in (
        "reviewer", "doc-writer", "security", "explainer",
        "oncall", "release-manager", "refactor-specialist",
    ):
        assert required in names


def test_load_agent_returns_persona_with_system_prompt(joe_module):
    joe_module._seed_default_agents()
    a = joe_module._load_agent("reviewer")
    assert a is not None
    assert a.name == "reviewer"
    assert a.model
    assert len(a.system_prompt) > 50


def test_load_agent_unknown_returns_none(joe_module):
    joe_module._seed_default_agents()
    assert joe_module._load_agent("does-not-exist") is None


def test_seed_is_idempotent(joe_module):
    joe_module._seed_default_agents()
    before = len(list(joe_module.AGENTS_DIR.iterdir()))
    joe_module._seed_default_agents()
    after = len(list(joe_module.AGENTS_DIR.iterdir()))
    assert before == after
