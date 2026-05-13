"""v0.9.6: reproducibility passport.

Every model call writes a passport row keyed by sha256 of the input
space (model + prompt + cwd + active lessons + LoRA endpoint). The
passport can be retrieved by prefix, listed, and replayed.
"""
from __future__ import annotations

import pytest


def test_passport_hash_is_stable(joe_module):
    """Identical inputs produce identical hashes."""
    h1 = joe_module._passport_hash(
        "joe-gemma", "hello", "/tmp/x", ["no em-dash"], "",
    )
    h2 = joe_module._passport_hash(
        "joe-gemma", "hello", "/tmp/x", ["no em-dash"], "",
    )
    assert h1 == h2
    assert len(h1) == 16  # 64-bit prefix


def test_passport_hash_changes_with_any_input(joe_module):
    """Each input axis flips the hash."""
    base = joe_module._passport_hash("joe-gemma", "hi", "/x", ["a"], "")
    assert base != joe_module._passport_hash("OTHER", "hi", "/x", ["a"], "")
    assert base != joe_module._passport_hash("joe-gemma", "OTHER", "/x", ["a"], "")
    assert base != joe_module._passport_hash("joe-gemma", "hi", "/OTHER", ["a"], "")
    assert base != joe_module._passport_hash("joe-gemma", "hi", "/x", ["b"], "")
    assert base != joe_module._passport_hash("joe-gemma", "hi", "/x", ["a"], "http://mlx:8081/v1")


def test_passport_hash_lesson_order_irrelevant(joe_module):
    """Lessons are sorted before hashing, so order doesn't matter."""
    a = joe_module._passport_hash("m", "p", "/c", ["rule-a", "rule-b"], "")
    b = joe_module._passport_hash("m", "p", "/c", ["rule-b", "rule-a"], "")
    assert a == b


def test_passport_record_and_retrieve(joe_module):
    """record -> get round-trip."""
    h = joe_module.passport_record(
        "joe-gemma", "what is 2+2?", "4.",
        mode="once",
    )
    assert h
    rec = joe_module.passport_get(h)
    assert rec is not None
    assert rec["model"] == "joe-gemma"
    assert rec["prompt"] == "what is 2+2?"
    assert rec["response"] == "4."
    assert rec["mode"] == "once"


def test_passport_get_by_prefix(joe_module):
    """Short hash prefix (≥4 chars) should resolve."""
    h = joe_module.passport_record("m", "prefix-test", "ok", mode="once")
    short = h[:8]
    rec = joe_module.passport_get(short)
    assert rec is not None
    assert rec["hash"] == h


def test_passport_get_rejects_too_short(joe_module):
    assert joe_module.passport_get("a") is None
    assert joe_module.passport_get("") is None


def test_passport_list_returns_newest_first(joe_module):
    joe_module.passport_record("m1", "first", "r1", mode="once")
    joe_module.passport_record("m2", "second", "r2", mode="once")
    rows = joe_module.passport_list(10)
    assert len(rows) >= 2
    # ts strings are ISO-8601 so lexical sort matches chronological
    assert rows[0]["ts"] >= rows[1]["ts"]


def test_passport_in_slash_command_names(joe_module):
    assert "passport" in joe_module.SLASH_COMMAND_NAMES
