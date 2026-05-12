"""Macro recorder: TOML round-trip + step structure."""
from __future__ import annotations

import json


def test_macro_file_format_round_trip(joe_module):
    """The /macro stop handler writes TOML; verify a hand-built file
    can be parsed back into a steps list."""
    import tomllib
    path = joe_module.MACROS_DIR / "morning.toml"
    steps = ["/standup", "/journal", "/diff"]
    body = (
        'name = "morning"\n'
        'created = "2026-05-12T10:00:00"\n'
        f"steps = {json.dumps(steps)}\n"
    )
    path.write_text(body)
    cfg = tomllib.loads(path.read_text())
    assert cfg["name"] == "morning"
    assert cfg["steps"] == steps
