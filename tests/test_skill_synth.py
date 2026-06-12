"""v0.12: skill synthesis. Turn a successful session into a reusable SKILL.md.

These tests inject a stub model_fn so they never touch ollama. They cover the
pure extraction/slug helpers, the writer (which must produce a SKILL.md that
the canonical loader can read back), and the end-to-end session -> skill path.
"""
from __future__ import annotations


GOOD_SKILL = """---
name: Rotate API Keys
description: Safely rotate a service API key without downtime.
when_to_use: rotate key, api key, credential rotation, secret rotation
---
1. Generate the new key in the provider dashboard.
2. Add it as a second active credential, do not remove the old one yet.
3. Deploy the app reading the new key, watch error rates.
4. Once traffic is clean, revoke the old key.
Gotcha: never delete the old key before the new one is serving traffic.
"""


def test_extract_skill_md_plain(joe_module):
    out = joe_module._extract_skill_md(GOOD_SKILL)
    assert out is not None
    assert out.startswith("---")
    assert "name: Rotate API Keys" in out


def test_extract_skill_md_strips_code_fence(joe_module):
    fenced = "```markdown\n" + GOOD_SKILL + "```"
    out = joe_module._extract_skill_md(fenced)
    assert out is not None
    assert out.lstrip().startswith("---")
    assert "```" not in out


def test_extract_skill_md_strips_leading_prose(joe_module):
    noisy = "Sure! Here is a skill for that:\n\n" + GOOD_SKILL
    out = joe_module._extract_skill_md(noisy)
    assert out is not None
    assert out.startswith("---")


def test_extract_skill_md_declines_on_none(joe_module):
    assert joe_module._extract_skill_md("NONE") is None
    assert joe_module._extract_skill_md("  none  ") is None


def test_extract_skill_md_rejects_no_frontmatter(joe_module):
    assert joe_module._extract_skill_md("just some text, no skill here") is None


def test_extract_skill_md_rejects_unclosed_frontmatter(joe_module):
    assert joe_module._extract_skill_md("---\nname: x\nno closing fence") is None


def test_slugify_skill_name(joe_module):
    assert joe_module._slugify_skill_name("Rotate API Keys") == "rotate-api-keys"
    assert joe_module._slugify_skill_name("  Weird__Name!! ") == "weird-name"
    assert joe_module._slugify_skill_name("???") == "skill"


def test_write_synthesized_skill_is_loadable(joe_module):
    ok, path = joe_module.write_synthesized_skill(GOOD_SKILL)
    assert ok, path
    # The canonical loader must read it back as a real skill.
    skills = joe_module.load_skills()
    assert "Rotate API Keys" in skills
    assert "credential rotation" in skills["Rotate API Keys"]["when_to_use"]


def test_write_synthesized_skill_never_clobbers(joe_module):
    ok1, p1 = joe_module.write_synthesized_skill(GOOD_SKILL)
    ok2, p2 = joe_module.write_synthesized_skill(GOOD_SKILL)
    assert ok1 and ok2
    assert p1 != p2  # second write goes to <slug>-2, original preserved


def test_write_synthesized_skill_rejects_garbage(joe_module):
    ok, msg = joe_module.write_synthesized_skill("not a skill at all")
    assert not ok
    assert "valid SKILL.md" in msg


def test_synth_from_session_happy_path(joe_module):
    sess = "build-feature"
    joe_module.session_append(sess, "user", "add a retry wrapper to the http client")
    joe_module.session_append(sess, "assistant", "Read client.py, added backoff retry.")
    joe_module.session_append(sess, "user", "now add jitter")
    joe_module.session_append(sess, "assistant", "Added full jitter, tests pass.")

    captured = {}

    def stub_model(prompt: str) -> str:
        captured["prompt"] = prompt
        return GOOD_SKILL

    ok, path = joe_module.skill_synth_from_session(sess, "stub", model_fn=stub_model)
    assert ok, path
    # The transcript actually reached the model.
    assert "retry wrapper" in captured["prompt"]
    assert "Rotate API Keys" in joe_module.load_skills()


def test_synth_from_session_too_short(joe_module):
    sess = "tiny"
    joe_module.session_append(sess, "user", "hi")
    joe_module.session_append(sess, "assistant", "hello")
    ok, msg = joe_module.skill_synth_from_session(sess, "stub", model_fn=lambda p: GOOD_SKILL)
    assert not ok
    assert "at least" in msg


def test_synth_from_session_model_declines(joe_module):
    sess = "chatter"
    for i in range(4):
        joe_module.session_append(sess, "user", f"msg {i}")
        joe_module.session_append(sess, "assistant", f"reply {i}")
    ok, msg = joe_module.skill_synth_from_session(sess, "stub", model_fn=lambda p: "NONE")
    assert not ok
    assert "no reusable skill" in msg


def test_latest_session(joe_module):
    assert joe_module._latest_session() is None
    joe_module.session_append("first", "user", "a")
    joe_module.session_append("second", "user", "b")
    assert joe_module._latest_session() == "second"
