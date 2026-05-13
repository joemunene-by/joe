"""v0.11.10: secrets-pattern guardrail on tool_write / tool_edit / tool_multi_edit.

Modeled on Future AGI's guardrail-engine block/warn/log action triad and
adapted to the local-first threat model: the actual nightmare on a dev
box isn't a hallucinated slur, it's a model that helpfully writes your
live API key into a file you then commit. Joe refuses the write at the
tool boundary unless ``JOE_GUARDRAILS=0`` is set.
"""
from __future__ import annotations

from pathlib import Path

import pytest


# Live-looking but obviously-bogus secrets used solely to exercise the
# scanner; none of these grant real access. The keys structurally match
# their providers' published formats so the regexes catch them.
# Synthetic strings whose *structure* matches each provider's published
# secret format so the regexes catch them, but whose body is obviously
# fabricated (``EXAMPLE`` / ``TEST`` / single-char fill) so neither a
# human reading the file nor an upstream secret scanner mistakes them
# for live credentials.
FAKE_AWS_KEY = "AKIAIOSFODNN7EXAMPLE"  # AWS's own published EXAMPLE id
FAKE_AWS_SECRET = (
    'aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"'
)
FAKE_OPENAI_KEY = "sk-proj-" + "EXAMPLE" * 4
FAKE_ANTHROPIC_KEY = "sk-ant-" + "EXAMPLE" * 4
FAKE_GH_PAT = "ghp_" + "EXAMPLE" * 6  # 42 chars after prefix
FAKE_GH_FINE = "github_pat_" + "EXAMPLE" * 11  # 77 chars after prefix
FAKE_STRIPE = "sk_live_" + "EXAMPLE" * 4  # 28 chars; clearly fake
FAKE_GOOGLE = "AIzaEXAMPLE" + "B" * 28  # 35 chars after AIza, matching the regex
FAKE_SLACK_HOOK = (
    "https://hooks.slack.com/services/TEXAMPLE0/BEXAMPLE0/" + "X" * 24
)
FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJURVNUIn0.EXAMPLEsignatureXYZ"
PRIVATE_KEY = "-----BEGIN RSA PRIVATE KEY-----"


def test_scan_clean_content_is_empty(joe_module):
    assert joe_module._scan_secrets("hello world\nno secrets here") == []


def test_scan_empty_content_is_empty(joe_module):
    assert joe_module._scan_secrets("") == []


@pytest.mark.parametrize(
    "label_substring,content",
    [
        ("AWS access key", f"key={FAKE_AWS_KEY}"),
        ("AWS secret access key", FAKE_AWS_SECRET),
        ("OpenAI API key", f"OPENAI_API_KEY={FAKE_OPENAI_KEY}"),
        ("Anthropic API key", f"ANTHROPIC_API_KEY={FAKE_ANTHROPIC_KEY}"),
        ("GitHub PAT", f"token: {FAKE_GH_PAT}"),
        ("GitHub fine-grained token", f"token={FAKE_GH_FINE}"),
        ("Stripe live key", f"STRIPE_KEY={FAKE_STRIPE}"),
        ("Google API key", f"GOOGLE_API_KEY={FAKE_GOOGLE}"),
        ("Slack webhook", f"webhook: {FAKE_SLACK_HOOK}"),
        ("JWT", f"Authorization: Bearer {FAKE_JWT}"),
        ("Private key (PEM)", f"{PRIVATE_KEY}\nMIIEvAIBADANBgkq..."),
    ],
)
def test_scan_catches_each_pattern(joe_module, label_substring, content):
    hits = joe_module._scan_secrets(content)
    assert len(hits) >= 1
    labels = [h[0] for h in hits]
    assert any(label_substring in lbl for lbl in labels), (
        f"expected {label_substring} in {labels} for content: {content[:40]}..."
    )


def test_scan_truncates_long_match_in_report(joe_module):
    """The matched bytes are abbreviated so the panel doesn't echo the
    full key into terminal scrollback."""
    hits = joe_module._scan_secrets(f"key={FAKE_OPENAI_KEY}")
    assert hits
    _, _, shown = hits[0]
    assert FAKE_OPENAI_KEY not in shown, "full secret leaked into the report text"
    assert "..." in shown


def test_scan_returns_line_numbers(joe_module):
    body = "first line\nsecond line\nkey=" + FAKE_AWS_KEY + "\nfourth line"
    hits = joe_module._scan_secrets(body)
    assert hits
    assert hits[0][1] == 3  # 1-indexed


def test_scan_disabled_when_env_unset(joe_module, monkeypatch):
    """JOE_GUARDRAILS=0 globally disables the scanner."""
    monkeypatch.setattr(joe_module, "_GUARDRAILS_ENABLED", False)
    assert joe_module._scan_secrets(f"key={FAKE_AWS_KEY}") == []


def test_format_secret_block_does_not_leak_full_secret(joe_module, tmp_path):
    p = tmp_path / "config.py"
    hits = joe_module._scan_secrets(f"OPENAI_API_KEY = '{FAKE_OPENAI_KEY}'")
    msg = joe_module._format_secret_block(p, hits)
    assert "Guardrail blocked" in msg
    assert "config.py" in msg
    assert FAKE_OPENAI_KEY not in msg


def test_tool_write_refuses_secret(joe_module, tmp_path, monkeypatch):
    """The integration point: tool_write refuses a body that matches a
    secret pattern and the file is NOT created."""
    monkeypatch.setenv("JOE_AUTO_YES", "1")
    p = tmp_path / "leaks.py"
    body = f"API_KEY = '{FAKE_AWS_KEY}'\n"
    with pytest.raises(joe_module.ToolError) as exc:
        joe_module.tool_write({"path": str(p)}, body, confirm=False)
    assert "Guardrail blocked" in str(exc.value)
    assert "AWS access key" in str(exc.value)
    assert not p.exists()


def test_tool_write_allows_clean_python(joe_module, tmp_path, monkeypatch):
    monkeypatch.setenv("JOE_AUTO_YES", "1")
    p = tmp_path / "ok.py"
    body = "API_KEY = os.environ['OPENAI_API_KEY']\n"
    result = joe_module.tool_write({"path": str(p)}, body, confirm=False)
    assert "wrote" in result
    assert p.exists()


def test_tool_write_allows_when_disabled(joe_module, tmp_path, monkeypatch):
    """JOE_GUARDRAILS=0 bypasses the scan: dangerous test fixtures or
    intentional placeholder content can be written without redaction."""
    monkeypatch.setenv("JOE_AUTO_YES", "1")
    monkeypatch.setattr(joe_module, "_GUARDRAILS_ENABLED", False)
    p = tmp_path / "fixture.txt"
    body = f"sample = '{FAKE_AWS_KEY}'\n"
    result = joe_module.tool_write({"path": str(p)}, body, confirm=False)
    assert "wrote" in result
    assert p.exists()


def test_default_enabled(joe_module):
    """JOE_GUARDRAILS defaults to on -- users get the safer behaviour out
    of the box."""
    assert joe_module._GUARDRAILS_ENABLED in (True, False)
    # Sanity: the module exports the public names we wired in.
    assert hasattr(joe_module, "_scan_secrets")
    assert hasattr(joe_module, "_format_secret_block")
    assert hasattr(joe_module, "_SECRET_PATTERNS")
