"""v0.12.1: skill effectiveness ledger. Closes the loop on skill synthesis by
scoring each injected skill as a win or a loss against /undo events, and
pruning synthesized skills that never trigger or go net-negative.

Offline: no ollama. We seed the usage DB and the lessons (undo) DB directly.
"""
from __future__ import annotations

import datetime as _dt


GOOD_SKILL = """---
name: Rotate API Keys
description: Safely rotate a service API key without downtime.
when_to_use: rotate key, api key, credential rotation
---
1. Generate the new key. 2. Dual-run. 3. Cut over. 4. Revoke the old key.
"""


def _insert_undo(joe_module, session: str, ts: str) -> None:
    """Write an /undo event into the lessons DB so it counts as a loss."""
    c = joe_module._lessdb()
    c.execute(
        "INSERT INTO events (ts, source, session, model, agent, user_msg,"
        " rejected, note) VALUES (?, 'undo', ?, '', '', '', '', '')",
        (ts, session),
    )
    c.commit()
    c.close()


def test_record_and_effectiveness_counts_wins(joe_module):
    joe_module.record_skill_usage(["S1", "S2"], "sess1")
    eff = joe_module.skill_effectiveness()
    assert eff["S1"]["uses"] == 1
    assert eff["S1"]["wins"] == 1
    assert eff["S1"]["losses"] == 0
    assert eff["S2"]["wins"] == 1


def test_effectiveness_counts_loss_on_same_hour_undo(joe_module):
    joe_module.record_skill_usage(["S1"], "sess1")
    # Read back the usage ts and plant an undo in the same session+hour.
    c = joe_module._skill_usage_db()
    ts = c.execute("SELECT ts FROM skill_usage WHERE skill='S1'").fetchone()[0]
    c.close()
    _insert_undo(joe_module, "sess1", ts)
    eff = joe_module.skill_effectiveness()
    assert eff["S1"]["losses"] == 1
    assert eff["S1"]["wins"] == 0


def test_effectiveness_undo_in_other_session_is_not_a_loss(joe_module):
    joe_module.record_skill_usage(["S1"], "sess1")
    c = joe_module._skill_usage_db()
    ts = c.execute("SELECT ts FROM skill_usage WHERE skill='S1'").fetchone()[0]
    c.close()
    _insert_undo(joe_module, "different-session", ts)
    eff = joe_module.skill_effectiveness()
    assert eff["S1"]["wins"] == 1
    assert eff["S1"]["losses"] == 0


def test_record_skill_usage_empty_is_noop(joe_module):
    joe_module.record_skill_usage([], "sess1")
    assert joe_module.skill_effectiveness() == {}


def test_synth_marker_written(joe_module):
    ok, path = joe_module.write_synthesized_skill(GOOD_SKILL)
    assert ok
    dirs = joe_module._skill_dirs()
    assert "Rotate API Keys" in dirs
    assert joe_module._is_synthesized(dirs["Rotate API Keys"])


def test_prune_flags_never_triggered_synth_skill(joe_module):
    joe_module.write_synthesized_skill(GOOD_SKILL)
    results = joe_module.skill_prune(dry_run=True)
    names = [r[0] for r in results]
    assert "Rotate API Keys" in names
    assert any("never triggered" in r[1] for r in results)
    # dry run must not move anything: still loadable.
    assert "Rotate API Keys" in joe_module.load_skills()


def test_prune_apply_archives_and_disables(joe_module):
    joe_module.write_synthesized_skill(GOOD_SKILL)
    joe_module.skill_prune(dry_run=False)
    # After archiving, the loader must no longer see it.
    assert "Rotate API Keys" not in joe_module.load_skills()
    assert (joe_module.SKILLS_DIR / "_archived").is_dir()


def test_prune_keeps_net_positive_synth_skill(joe_module):
    joe_module.write_synthesized_skill(GOOD_SKILL)
    # Two wins, no losses -> earns its place.
    joe_module.record_skill_usage(["Rotate API Keys"], "s1")
    joe_module.record_skill_usage(["Rotate API Keys"], "s2")
    results = joe_module.skill_prune(dry_run=True)
    assert results == []


def test_prune_never_touches_installed_skill(joe_module, tmp_path):
    # An installed (non-synth) skill: SKILL.md but no .synth marker.
    d = joe_module.SKILLS_DIR / "manual-skill"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(GOOD_SKILL, encoding="utf-8")
    assert not joe_module._is_synthesized(d)
    results = joe_module.skill_prune(dry_run=False)
    assert results == []
    # Still present.
    assert (d / "SKILL.md").is_file()
