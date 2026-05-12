"""Lessons capture + provenance record + blame: the AI-blame log path."""
from __future__ import annotations

from pathlib import Path


def test_lesson_capture_appends_event(joe_module):
    joe_module.lesson_capture(
        source="manual", rejected="some thing", note="user said no",
    )
    c = joe_module._lessdb()
    rows = c.execute("SELECT source, rejected, note FROM events").fetchall()
    c.close()
    assert len(rows) == 1
    assert rows[0][0] == "manual"
    assert "no" in rows[0][2]


def test_lessons_active_rules_empty_when_no_rules(joe_module):
    assert joe_module.lessons_active_rules() == []


def test_lessons_block_empty_when_no_state(joe_module):
    assert joe_module.lessons_block() == ""


def test_provenance_record_roundtrips_via_blame(joe_module, tmp_path):
    target = tmp_path / "src" / "foo.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("def hello(): pass\n")
    # Stamp the turn context the way run_turn would.
    joe_module._TURN_CTX.update(
        session="test-sess", model="joe-gemma", agent="reviewer",
        user_msg="add a hello function",
    )
    joe_module.provenance_record(
        target, op="write", before=None, after="def hello(): pass\n",
        line_start=1, line_end=1, adds=1, dels=0,
    )
    hits = joe_module.provenance_blame(str(target), line=1)
    assert len(hits) == 1
    h = hits[0]
    assert h["op"] == "write"
    assert h["agent"] == "reviewer"
    assert h["model"] == "joe-gemma"
    assert "hello function" in h["user_msg"]


def test_provenance_blame_with_no_line_returns_all(joe_module, tmp_path):
    target = tmp_path / "a.py"
    target.write_text("x")
    joe_module._TURN_CTX.update(
        session="s", model="m", agent="", user_msg="u",
    )
    for ls, le in [(1, 5), (6, 10), (11, 15)]:
        joe_module.provenance_record(
            target, op="edit", before="x", after="x",
            line_start=ls, line_end=le, adds=1, dels=1,
        )
    all_hits = joe_module.provenance_blame(str(target), line=None)
    assert len(all_hits) == 3
