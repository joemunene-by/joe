"""v0.7.4: <cd> tool tag + Desktop project alias resolution."""
from __future__ import annotations

import pytest


def test_pending_cwd_starts_none(joe_module):
    assert joe_module._PENDING_CWD is None


def test_tool_cd_absolute_path_sets_pending(joe_module, tmp_path):
    target = tmp_path / "somedir"
    target.mkdir()
    joe_module._PENDING_CWD = None
    out = joe_module.tool_cd({"path": str(target)}, "")
    assert "cwd -> " in out
    assert joe_module._PENDING_CWD == target


def test_tool_cd_body_fallback_when_no_attr(joe_module, tmp_path):
    """A bare `<cd>~/foo</cd>` body should also work, not just path attr."""
    target = tmp_path / "via-body"
    target.mkdir()
    joe_module._PENDING_CWD = None
    out = joe_module.tool_cd({}, str(target))
    assert str(target) in out
    assert joe_module._PENDING_CWD == target


def test_tool_cd_empty_path_errors(joe_module):
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_cd({}, "")


def test_tool_cd_nonexistent_errors(joe_module):
    with pytest.raises(joe_module.ToolError) as exc:
        joe_module.tool_cd({"path": "/no/such/path/anywhere-12345"}, "")
    assert "no such directory" in str(exc.value).lower()


def test_tool_bash_cd_redirects_to_cd_tag(joe_module):
    """`<bash>cd X</bash>` should fail loud, telling the model to use <cd>."""
    with pytest.raises(joe_module.ToolError) as exc:
        joe_module.tool_bash({}, "cd /tmp", allow_all=False, confirm=False)
    msg = str(exc.value)
    assert "<cd" in msg
    assert "subshell" in msg.lower()


def test_tool_bash_cd_redirects_even_in_unsafe_mode(joe_module):
    """--unsafe-bash widens the allow-list, but `cd` is still pointless because
    the subshell discards the change. Should still raise the same hint."""
    with pytest.raises(joe_module.ToolError):
        joe_module.tool_bash({}, "cd /tmp", allow_all=True, confirm=False)


def test_project_aliases_indexes_marker_dir(joe_module, tmp_path):
    """A directory under ~/Desktop with a project marker should be aliased."""
    desk = tmp_path / "Desktop"
    desk.mkdir()
    proj = desk / "FakeCRM"
    proj.mkdir()
    (proj / "package.json").write_text("{}")
    joe_module._PROJECT_ALIASES_CACHE = None
    idx = joe_module._project_aliases()
    assert "FakeCRM" in idx
    assert idx["FakeCRM"] == proj


def test_project_alias_resolution_is_case_insensitive(joe_module, tmp_path):
    desk = tmp_path / "Desktop"
    desk.mkdir()
    proj = desk / "GhostLoop"
    proj.mkdir()
    (proj / ".git").mkdir()
    joe_module._PROJECT_ALIASES_CACHE = None
    # Different cases of the same name should still resolve.
    assert joe_module._resolve_project_alias("GhostLoop") == proj
    assert joe_module._resolve_project_alias("ghostloop") == proj
    assert joe_module._resolve_project_alias("GHOSTLOOP") == proj


def test_project_alias_substring_match(joe_module, tmp_path):
    """'crm' should match a project named 'AwesomeCRM' on substring fallback."""
    desk = tmp_path / "Desktop"
    desk.mkdir()
    proj = desk / "AwesomeCRM"
    proj.mkdir()
    (proj / "pyproject.toml").write_text("[tool.x]")
    joe_module._PROJECT_ALIASES_CACHE = None
    assert joe_module._resolve_project_alias("crm") == proj


def test_project_alias_skips_non_project_dirs(joe_module, tmp_path):
    """Random dirs with no project marker should NOT show up in the index."""
    desk = tmp_path / "Desktop"
    desk.mkdir()
    (desk / "JustNotes").mkdir()  # no marker
    joe_module._PROJECT_ALIASES_CACHE = None
    idx = joe_module._project_aliases()
    assert "JustNotes" not in idx


def test_tool_cd_resolves_project_alias(joe_module, tmp_path):
    desk = tmp_path / "Desktop"
    desk.mkdir()
    proj = desk / "CRM"
    proj.mkdir()
    (proj / ".git").mkdir()
    joe_module._PROJECT_ALIASES_CACHE = None
    joe_module._PENDING_CWD = None
    out = joe_module.tool_cd({"path": "CRM"}, "")
    assert "CRM" in out
    assert joe_module._PENDING_CWD == proj


def test_projects_block_contains_known_repo(joe_module, tmp_path):
    desk = tmp_path / "Desktop"
    desk.mkdir()
    proj = desk / "linkdrop"
    proj.mkdir()
    (proj / ".git").mkdir()
    joe_module._PROJECT_ALIASES_CACHE = None
    block = joe_module._projects_block()
    assert "<available_projects>" in block
    assert "linkdrop" in block


def test_projects_block_empty_when_no_projects(joe_module, tmp_path):
    """If nothing under HOME looks like a project, the block is omitted
    (the empty string short-circuits the system-prompt injection)."""
    joe_module._PROJECT_ALIASES_CACHE = None
    block = joe_module._projects_block()
    assert block == ""


def test_cd_in_tool_dispatcher_table(joe_module):
    """Confirm the dispatcher branch for <cd> exists by source inspection."""
    src = (joe_module.__file__,)
    import pathlib
    text = pathlib.Path(joe_module.__file__).read_text()
    assert 'call.name == "cd"' in text
    assert "tool_cd(call.attrs, call.body)" in text


def test_cd_tag_is_parseable_by_extract(joe_module):
    """Regression: the TAG_PAT regex must include 'cd' in its tag whitelist.
    First field test on the Mac showed the model emitting <cd path="CRM" />
    correctly but the parser returning None because 'cd' was missing from
    the disjunction -- so the tag was silently treated as prose."""
    call = joe_module.extract_first_tool_call('<cd path="CRM" />')
    assert call is not None, "the parser must recognise <cd>"
    assert call.name == "cd"
    assert call.attrs == {"path": "CRM"}


def test_cd_tag_block_form_parses(joe_module):
    """Block form: `<cd>path</cd>` should also parse, body becomes the path."""
    call = joe_module.extract_first_tool_call("<cd>~/Desktop/CRM</cd>")
    assert call is not None
    assert call.name == "cd"
    assert call.body == "~/Desktop/CRM"


def test_cd_tag_with_absolute_path_parses(joe_module):
    """Path attrs that contain `/` must not break the regex (regression)."""
    call = joe_module.extract_first_tool_call('<cd path="/Users/ghost/Desktop/CRM" />')
    assert call is not None
    assert call.name == "cd"
    assert call.attrs["path"] == "/Users/ghost/Desktop/CRM"
