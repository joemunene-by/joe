"""v0.11.11: three batched features mined from a 2026 OSS-agent landscape sweep.

1. **Codebase RAG** — auto-injects vector-index chunks under cwd into the
   system prompt every turn. Mirrors Cursor's ``@codebase``, Cody's
   agentic context, Continue's ``@codebase`` context.
2. **Linter-feedback ACI on edit** — runs the project's per-file linter
   after a successful ``write`` / ``edit`` / ``multi_edit`` and appends
   diagnostics to the tool return so the model self-corrects on the
   same turn. The SWE-agent ACI insight: tool ergonomics dwarf retrieval
   gains.
3. **OpenHands microagent trigger compat** — ``triggers: [a, b]`` in
   SKILL.md frontmatter folds into ``when_to_use`` so OpenHands
   microagents drop into joe's skills dir without translation.
"""
from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Codebase RAG
# ---------------------------------------------------------------------------


def _seed_vector_index(joe_module, db_path: Path, cwd: Path, n_chunks: int = 3) -> None:
    """Insert n_chunks fake chunks into a vector-index.sqlite at db_path,
    all under cwd, with a uniform embedding so cosine is deterministic."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS chunks ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " repo TEXT NOT NULL,"
        " path TEXT NOT NULL,"
        " line_start INTEGER NOT NULL,"
        " line_end INTEGER NOT NULL,"
        " text TEXT NOT NULL,"
        " embedding BLOB NOT NULL,"
        " mtime REAL NOT NULL,"
        " indexed_at REAL NOT NULL)"
    )
    # 768-dim embedding (nomic-embed-text), all zeros except first dim.
    vec = [1.0] + [0.0] * 767
    blob = struct.pack(f"{len(vec)}f", *vec)
    for i in range(n_chunks):
        conn.execute(
            "INSERT INTO chunks "
            "(repo, path, line_start, line_end, text, embedding, mtime, indexed_at)"
            " VALUES (?, ?, ?, ?, ?, ?, 0, 0)",
            (
                str(cwd),
                f"{cwd}/file_{i}.py",
                10 + i * 5,
                14 + i * 5,
                f"def chunk_{i}_function():\n    return 'snippet {i}'",
                blob,
            ),
        )
    conn.commit()
    conn.close()


def test_repo_rag_no_db_returns_empty(joe_module, tmp_path, monkeypatch):
    """Without a vector-index.sqlite, RAG must silently no-op."""
    monkeypatch.setattr(joe_module, "VECTOR_INDEX_DB", tmp_path / "no-such.sqlite")
    hits = joe_module.repo_rag_query("how does authentication work here?", tmp_path)
    assert hits == []


def test_repo_rag_short_query_returns_empty(joe_module, tmp_path):
    """User msgs under 12 chars (e.g. "hi", "ok") get no retrieval."""
    assert joe_module.repo_rag_query("hi", tmp_path) == []
    assert joe_module.repo_rag_query("ok", tmp_path) == []


def test_repo_rag_disabled_returns_empty(joe_module, tmp_path, monkeypatch):
    """JOE_AUTO_RAG=0 globally disables the auto-inject path."""
    monkeypatch.setattr(joe_module, "_AUTO_REPO_RAG", False)
    monkeypatch.setattr(joe_module, "VECTOR_INDEX_DB", tmp_path / "vector-index.sqlite")
    _seed_vector_index(joe_module, joe_module.VECTOR_INDEX_DB, tmp_path)
    # Even with an index present, disabled means empty.
    hits = joe_module.repo_rag_query("a question about the code", tmp_path)
    assert hits == []


def test_repo_rag_filters_by_cwd(joe_module, tmp_path, monkeypatch):
    """Chunks indexed under OTHER repos must not leak into cwd-scoped results."""
    other = tmp_path / "other-repo"
    cwd = tmp_path / "active-repo"
    other.mkdir(); cwd.mkdir()
    db = tmp_path / "vector-index.sqlite"
    monkeypatch.setattr(joe_module, "VECTOR_INDEX_DB", db)
    # Stub the embed call so we don't hit ollama.
    monkeypatch.setattr(joe_module, "_embed", lambda text: [1.0] + [0.0] * 767)
    _seed_vector_index(joe_module, db, other, n_chunks=2)
    # Query against cwd (which has no chunks) -> empty.
    hits = joe_module.repo_rag_query("a question about the code", cwd)
    assert hits == []


def test_repo_rag_returns_hits_under_cwd(joe_module, tmp_path, monkeypatch):
    """Happy path: index + cwd + stubbed embed -> top-k hits."""
    cwd = tmp_path / "repo"
    cwd.mkdir()
    db = tmp_path / "vector-index.sqlite"
    monkeypatch.setattr(joe_module, "VECTOR_INDEX_DB", db)
    monkeypatch.setattr(joe_module, "_embed", lambda text: [1.0] + [0.0] * 767)
    _seed_vector_index(joe_module, db, cwd, n_chunks=5)
    hits = joe_module.repo_rag_query("how does this code work?", cwd, k=3)
    assert len(hits) == 3
    for h in hits:
        assert h["path"].startswith(str(cwd))
        assert "line_start" in h and "line_end" in h
        assert 0.0 <= h["score"] <= 1.0


def test_repo_rag_block_renders_well_formed(joe_module):
    """The block must look like our other context blocks: a wrapper
    element with `note=` plus one `<file>` per hit."""
    hits = [
        {
            "score": 0.85,
            "path": "/r/x.py",
            "line_start": 1,
            "line_end": 10,
            "text": "def f():\n    pass",
        },
        {
            "score": 0.61,
            "path": "/r/y.py",
            "line_start": 20,
            "line_end": 25,
            "text": "class Y: ...",
        },
    ]
    block = joe_module.repo_rag_block(hits)
    assert block.startswith("<repo_rag")
    assert block.endswith("</repo_rag>")
    assert "<file " in block and 'path="/r/x.py"' in block
    assert 'lines="1-10"' in block
    assert 'score="0.85"' in block


def test_repo_rag_block_empty_hits_returns_empty_string(joe_module):
    """No hits = no block. Matches history_block convention."""
    assert joe_module.repo_rag_block([]) == ""


# ---------------------------------------------------------------------------
# Linter-feedback ACI on edit
# ---------------------------------------------------------------------------


def test_post_edit_lint_unsupported_ext_skips(joe_module, tmp_path):
    """Files with no linter mapping return None (no-op, not error)."""
    p = tmp_path / "notes.txt"
    p.write_text("just some prose")
    assert joe_module._post_edit_lint(p) is None


def test_post_edit_lint_disabled(joe_module, tmp_path, monkeypatch):
    """JOE_AUTO_LINT=0 turns off the post-write lint pass entirely."""
    monkeypatch.setattr(joe_module, "_AUTO_LINT_AFTER_EDIT", False)
    p = tmp_path / "x.py"
    p.write_text("x = 1\n")
    assert joe_module._post_edit_lint(p) is None


def test_post_edit_lint_missing_file_returns_none(joe_module, tmp_path):
    """Defensive: caller might pass a deleted path."""
    assert joe_module._post_edit_lint(tmp_path / "doesnotexist.py") is None


def test_annotate_with_lint_appends_block_on_diagnostics(joe_module, tmp_path, monkeypatch):
    """When the linter has output, the base message gets a
    `<lint_after_write>` suffix the model can read on the same turn."""
    p = tmp_path / "x.py"
    p.write_text("x = 1\n")
    # Stub _post_edit_lint to return fake diagnostics.
    monkeypatch.setattr(
        joe_module, "_post_edit_lint",
        lambda path: "x.py:1:1: F401 unused import 'os'" if path == p else None,
    )
    annotated = joe_module._annotate_with_lint("wrote 6 bytes to x.py", p)
    assert "wrote 6 bytes to x.py" in annotated
    assert "<lint_after_write" in annotated
    assert "F401" in annotated
    assert "</lint_after_write>" in annotated


def test_annotate_with_lint_no_diagnostics_returns_base(joe_module, tmp_path, monkeypatch):
    """Clean lint = unchanged message. No extra noise."""
    monkeypatch.setattr(joe_module, "_post_edit_lint", lambda path: None)
    p = tmp_path / "x.py"
    base = "wrote 6 bytes to x.py"
    assert joe_module._annotate_with_lint(base, p) == base


# ---------------------------------------------------------------------------
# OpenHands microagent trigger compatibility
# ---------------------------------------------------------------------------


def test_skill_inline_triggers_fold_into_when_to_use(joe_module, tmp_path):
    """``triggers: [a, b, c]`` (OpenHands inline-list form) merges into the
    same when_to_use keyword-match flow joe already used."""
    skill_dir = tmp_path / "skills" / "review"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: code-review\n"
        "description: Senior review with security focus\n"
        "triggers: [audit, vulnerability, security review]\n"
        "---\n"
        "Review like a senior. Focus on injection, race conditions, secrets.\n"
    )
    parsed = joe_module._parse_skill_md(skill_dir / "SKILL.md")
    assert parsed is not None
    assert parsed["name"] == "code-review"
    assert "audit" in parsed["when_to_use"]
    assert "vulnerability" in parsed["when_to_use"]
    assert "security review" in parsed["when_to_use"]


def test_skill_triggers_merge_with_existing_when_to_use(joe_module, tmp_path):
    """If a SKILL.md has both ``when_to_use`` and ``triggers``, both
    contribute. Backward-compatible with existing skills."""
    skill_dir = tmp_path / "skills" / "review"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: code-review\n"
        "description: x\n"
        "when_to_use: review, check\n"
        "triggers: [audit, vulnerability]\n"
        "---\n"
        "body\n"
    )
    parsed = joe_module._parse_skill_md(skill_dir / "SKILL.md")
    assert parsed is not None
    flat = parsed["when_to_use"].lower()
    for kw in ("review", "check", "audit", "vulnerability"):
        assert kw in flat


def test_skill_without_triggers_unchanged(joe_module, tmp_path):
    """Backward compat: a skill with only when_to_use parses identically
    to before."""
    skill_dir = tmp_path / "skills" / "review"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: x\n"
        "description: y\n"
        "when_to_use: foo, bar\n"
        "---\n"
        "body\n"
    )
    parsed = joe_module._parse_skill_md(skill_dir / "SKILL.md")
    assert parsed is not None
    assert parsed["when_to_use"] == "foo, bar"
