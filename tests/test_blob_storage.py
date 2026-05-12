"""Content-addressed blob storage that the edit-history + provenance use."""
from __future__ import annotations


def test_hash_is_stable_and_short(joe_module):
    h1 = joe_module._hash_text("hello world")
    h2 = joe_module._hash_text("hello world")
    assert h1 == h2
    assert len(h1) == 16  # truncated sha1


def test_store_and_load_blob_roundtrip(joe_module):
    content = "def foo():\n    return 42\n"
    h = joe_module._store_blob(content)
    assert joe_module._load_blob(h) == content


def test_store_same_content_returns_same_hash(joe_module):
    h1 = joe_module._store_blob("same content")
    h2 = joe_module._store_blob("same content")
    assert h1 == h2
