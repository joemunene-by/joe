"""Catch-all: small helpers that would silently break expensive things."""
from __future__ import annotations


def test_token_estimate_is_at_least_one(joe_module):
    assert joe_module.estimate_tokens("") >= 1
    assert joe_module.estimate_tokens("hello") >= 1


def test_token_estimate_grows_with_length(joe_module):
    short = joe_module.estimate_tokens("hi")
    long_ = joe_module.estimate_tokens("hello world " * 100)
    assert long_ > short


def test_cosine_identity_is_one(joe_module):
    v = [1.0, 2.0, 3.0]
    assert abs(joe_module._cosine(v, v) - 1.0) < 1e-6


def test_cosine_orthogonal_is_zero(joe_module):
    assert abs(joe_module._cosine([1.0, 0.0], [0.0, 1.0])) < 1e-6


def test_pack_unpack_vec_round_trip(joe_module):
    v = [0.1, -0.2, 3.14, 0.0]
    packed = joe_module._pack_vec(v)
    out = joe_module._unpack_vec(packed)
    assert len(out) == len(v)
    for a, b in zip(v, out):
        assert abs(a - b) < 1e-5


def test_guess_lexer_known_extensions(joe_module):
    from pathlib import Path
    assert joe_module._guess_lexer(Path("foo.py")) == "python"
    assert joe_module._guess_lexer(Path("foo.tsx")) == "tsx"
    assert joe_module._guess_lexer(Path("foo.rs")) == "rust"
    assert joe_module._guess_lexer(Path("foo.unknown_ext")) == "text"
