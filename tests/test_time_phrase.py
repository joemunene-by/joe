"""Time-aware /recall: natural-language window extraction."""
from __future__ import annotations


def test_no_time_phrase_returns_none_for_both_bounds(joe_module):
    since, until, cleaned = joe_module._parse_time_phrase("ghostloop launch state")
    assert since is None
    assert until is None
    assert cleaned == "ghostloop launch state"


def test_yesterday_morning_yields_a_12h_window(joe_module):
    since, until, cleaned = joe_module._parse_time_phrase(
        "what did we decide yesterday morning about token budget?"
    )
    assert since is not None
    assert until is not None
    # 12h window
    import datetime as dt
    s = dt.datetime.fromisoformat(since)
    u = dt.datetime.fromisoformat(until)
    assert (u - s) == dt.timedelta(hours=12)
    assert "yesterday morning" not in cleaned.lower()


def test_n_hours_ago(joe_module):
    since, until, cleaned = joe_module._parse_time_phrase("two hours ago")
    # "two" isn't matched by \d+ — should fall through
    assert since is None
    since, until, cleaned = joe_module._parse_time_phrase("3 hours ago")
    assert since is not None
    assert until is None


def test_explicit_iso_date(joe_module):
    since, until, cleaned = joe_module._parse_time_phrase(
        "what was running on 2026-05-10 anyway?"
    )
    assert since is not None
    assert until is not None
    assert "2026-05-10" not in cleaned


def test_last_week(joe_module):
    since, until, cleaned = joe_module._parse_time_phrase(
        "what shipped last week?"
    )
    import datetime as dt
    s = dt.datetime.fromisoformat(since)
    u = dt.datetime.fromisoformat(until)
    assert (u - s) == dt.timedelta(days=7)
