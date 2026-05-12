"""`_active_repos` discovery: pinned file > auto-scan."""
from __future__ import annotations


def test_pinned_repos_file_wins(joe_module, tmp_path):
    # Build two git-looking dirs that the auto-scan WOULD find.
    (tmp_path / "alpha" / ".git").mkdir(parents=True)
    (tmp_path / "beta" / ".git").mkdir(parents=True)
    pinned = joe_module.STATE_DIR / "repos.txt"
    pinned.parent.mkdir(parents=True, exist_ok=True)
    pinned.write_text(f"{tmp_path / 'alpha'}\n# comment line\n")
    repos = joe_module._active_repos()
    names = [p.name for p in repos]
    assert names == ["alpha"]


def test_auto_scan_picks_up_git_dirs(joe_module, tmp_path):
    (tmp_path / "alpha" / ".git").mkdir(parents=True)
    (tmp_path / "beta" / ".git").mkdir(parents=True)
    (tmp_path / "no-repo").mkdir()
    repos = joe_module._active_repos()
    names = sorted(p.name for p in repos)
    # alpha + beta but NOT no-repo
    assert "alpha" in names
    assert "beta" in names
    assert "no-repo" not in names
