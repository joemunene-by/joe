"""v0.9.4: _orient banner + friendly missing-dep error.

When joe is launched, the banner now ALSO prints a short context line
acknowledging which project the cwd is in (name, framework, git branch
+ last commit, README first line, active LoRA endpoint). And a missing
runtime dep (rich) no longer raises a bare ModuleNotFoundError; it
prints an instruction telling the user the exact interpreter path and
the exact pip command.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def test_import_required_or_die_passes_when_module_present(joe_module):
    """Sanity: the dep check function returns silently when the module
    is importable (rich obviously IS, since joe-module loaded)."""
    # Just call it; should not raise / exit.
    joe_module._import_required_or_die("rich")
    joe_module._import_required_or_die("os")  # always importable


def test_import_required_or_die_exits_on_missing(joe_module, capsys):
    """Missing-module path: function prints the install hint and exits."""
    with pytest.raises(SystemExit) as exc:
        joe_module._import_required_or_die("definitely_not_a_real_module_xyz")
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "definitely_not_a_real_module_xyz" in err
    assert "pip install" in err
    assert "VS Code" in err  # mentions the common cause


def test_orient_skipped_at_home(joe_module, tmp_path, capsys):
    """At HOME, _orient should be a no-op (nothing to say about ~)."""
    fake_home = tmp_path
    joe_module.HOME = fake_home
    joe_module._orient(fake_home)
    out = capsys.readouterr().out
    assert "project:" not in out


def test_orient_shows_project_name(joe_module, tmp_path, capsys):
    proj = tmp_path / "my-cool-app"
    proj.mkdir()
    joe_module.HOME = tmp_path
    joe_module._orient(proj)
    out = capsys.readouterr().out
    assert "my-cool-app" in out
    assert "project:" in out


def test_orient_picks_up_git_branch(joe_module, tmp_path, capsys):
    proj = tmp_path / "git-project"
    proj.mkdir()
    # Real init so the orient code can shell out to git.
    subprocess.run(["git", "-C", str(proj), "init", "-q"], check=True)
    subprocess.run(
        ["git", "-C", str(proj), "config", "user.email", "t@t.t"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(proj), "config", "user.name", "t"], check=True,
    )
    subprocess.run(
        ["git", "-C", str(proj), "config", "commit.gpgsign", "false"],
        check=True,
    )
    (proj / "x.txt").write_text("hi")
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(proj), "commit", "-q", "-m", "initial squeeze"],
        check=True,
    )
    joe_module.HOME = tmp_path
    joe_module._orient(proj)
    out = capsys.readouterr().out
    assert "git:" in out
    assert "initial squeeze" in out


def test_orient_reads_readme_first_line(joe_module, tmp_path, capsys):
    proj = tmp_path / "documented"
    proj.mkdir()
    (proj / "README.md").write_text(
        "# Awesome Project\n\n"
        "A library that does the awesome thing efficiently.\n"
    )
    joe_module.HOME = tmp_path
    joe_module._orient(proj)
    out = capsys.readouterr().out
    # The first stripped non-empty non-image line should appear.
    assert "Awesome Project" in out or "library that does" in out
    assert "about:" in out


def test_orient_survives_unreadable_readme(joe_module, tmp_path):
    """A broken README (binary garbage, OS error) must not crash startup."""
    proj = tmp_path / "broken-readme"
    proj.mkdir()
    (proj / "README.md").write_bytes(b"\xff\xfe\x00\x00broken")
    joe_module.HOME = tmp_path
    # Should not raise.
    joe_module._orient(proj)


def test_orient_caps_long_readme_lines(joe_module, tmp_path, capsys):
    proj = tmp_path / "verbose"
    proj.mkdir()
    long_line = "A" * 300
    (proj / "README.md").write_text(long_line)
    joe_module.HOME = tmp_path
    joe_module._orient(proj)
    out = capsys.readouterr().out
    # Either truncated to ~110 chars + ellipsis, OR omitted entirely.
    # The 300-A run must NOT appear verbatim.
    assert "A" * 200 not in out
