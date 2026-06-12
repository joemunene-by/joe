"""v0.12.2: bake proven skills into training data. `train collect` now also
emits chat-format records for skills that earned their place (used and
net-positive), so the on-device LoRA learns the procedures that worked.

Offline: no ollama. Seeds usage + undo DBs directly.
"""
from __future__ import annotations


GOOD_SKILL = """---
name: Rotate API Keys
description: Safely rotate a service API key without downtime.
when_to_use: rotate key, api key, credential rotation
---
1. Generate the new key. 2. Dual-run. 3. Cut over. 4. Revoke the old key.
"""


def _win(joe_module, skill: str, session: str) -> None:
    joe_module.record_skill_usage([skill], session)


def _loss(joe_module, skill: str, session: str) -> None:
    """A usage plus an /undo in the same session+hour = a loss."""
    joe_module.record_skill_usage([skill], session)
    c = joe_module._skill_usage_db()
    ts = c.execute(
        "SELECT ts FROM skill_usage WHERE skill=? ORDER BY id DESC LIMIT 1", (skill,)
    ).fetchone()[0]
    c.close()
    le = joe_module._lessdb()
    le.execute(
        "INSERT INTO events (ts, source, session, model, agent, user_msg,"
        " rejected, note) VALUES (?, 'undo', ?, '', '', '', '', '')",
        (ts, session),
    )
    le.commit()
    le.close()


def test_proven_skills_excludes_unused(joe_module):
    joe_module.write_synthesized_skill(GOOD_SKILL)
    # Never used -> not proven.
    assert joe_module.proven_skills() == []


def test_proven_skills_includes_net_positive(joe_module):
    joe_module.write_synthesized_skill(GOOD_SKILL)
    _win(joe_module, "Rotate API Keys", "s1")
    _win(joe_module, "Rotate API Keys", "s2")
    proven = joe_module.proven_skills()
    assert [s["name"] for s in proven] == ["Rotate API Keys"]


def test_proven_skills_excludes_net_negative(joe_module):
    joe_module.write_synthesized_skill(GOOD_SKILL)
    _win(joe_module, "Rotate API Keys", "s1")
    _loss(joe_module, "Rotate API Keys", "s2")
    _loss(joe_module, "Rotate API Keys", "s3")
    assert joe_module.proven_skills() == []


def test_skill_training_records_shape(joe_module):
    joe_module.write_synthesized_skill(GOOD_SKILL)
    _win(joe_module, "Rotate API Keys", "s1")
    recs = joe_module.skill_training_records()
    assert len(recs) == 1
    rec = recs[0]
    # Must match the existing {"messages": [user, assistant]} shape exactly.
    assert set(rec.keys()) == {"messages"}
    roles = [m["role"] for m in rec["messages"]]
    assert roles == ["user", "assistant"]
    assert "Revoke the old key" in rec["messages"][1]["content"]
    assert "Rotate API Keys".lower() in rec["messages"][0]["content"].lower() \
        or "rotate" in rec["messages"][0]["content"].lower()


def test_skill_training_records_empty_when_nothing_proven(joe_module):
    joe_module.write_synthesized_skill(GOOD_SKILL)  # written but never used
    assert joe_module.skill_training_records() == []
