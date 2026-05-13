"""v0.8.5: joe train lora data prep.

The earlier mlx_lm.lora run crashed with `ValueError: Dataset must have
at least batch_size=4 examples but only has 3` and `ModuleNotFoundError:
No module named 'datasets'` because joe was passing the parent of the
collected jsonl as --data, which mlx-lm fell back to interpreting as a
HuggingFace dataset name.

These tests cover the inline data-prep step that builds train/valid/test
splits with the literal filenames mlx-lm's local path expects.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _write_collected_jsonl(td: Path, n_lines: int) -> Path:
    """Write a jsonl file that looks like what `joe train collect` produces."""
    p = td / "jsonl-20260101-000000.jsonl"
    lines = []
    for i in range(n_lines):
        rec = {"messages": [
            {"role": "user", "content": f"msg{i}"},
            {"role": "assistant", "content": f"reply{i}"},
        ]}
        lines.append(json.dumps(rec))
    p.write_text("\n".join(lines) + "\n")
    return p


def test_lora_prep_creates_three_files(joe_module, tmp_path, monkeypatch):
    """Running `joe train lora` should leave train.jsonl, valid.jsonl,
    test.jsonl in TRAINING_DATA_DIR/lora-set."""
    monkeypatch.setattr(joe_module, "TRAINING_DATA_DIR", tmp_path)
    _write_collected_jsonl(tmp_path, n_lines=20)
    # Force `which mlx_lm.lora` to find a stub so we hit the data-prep
    # code path without trying to actually spawn mlx-lm.
    fake_mlx = tmp_path / "mlx_lm.lora"
    fake_mlx.write_text("#!/bin/sh\necho fake-mlx\n")
    fake_mlx.chmod(0o755)
    monkeypatch.setattr(
        joe_module.shutil, "which",
        lambda name: str(fake_mlx) if "mlx" in name else None,
    )
    # task_spawn talks to the joe task subsystem we don't want to touch;
    # stub it out so the test only exercises the data-prep code path.
    monkeypatch.setattr(
        joe_module, "task_spawn",
        lambda cmd, cwd, label: {"id": "test-0"},
    )
    joe_module.cmd_train(["lora"], default_model="joe-gemma")
    lora_set = tmp_path / "lora-set"
    assert (lora_set / "train.jsonl").is_file()
    assert (lora_set / "valid.jsonl").is_file()
    assert (lora_set / "test.jsonl").is_file()


def test_lora_prep_valid_has_at_least_four_examples(joe_module, tmp_path, monkeypatch):
    """mlx-lm's default batch_size=4 requires valid.jsonl >= 4 lines."""
    monkeypatch.setattr(joe_module, "TRAINING_DATA_DIR", tmp_path)
    _write_collected_jsonl(tmp_path, n_lines=20)
    fake_mlx = tmp_path / "mlx_lm.lora"
    fake_mlx.write_text("#!/bin/sh\n")
    fake_mlx.chmod(0o755)
    monkeypatch.setattr(
        joe_module.shutil, "which",
        lambda name: str(fake_mlx) if "mlx" in name else None,
    )
    monkeypatch.setattr(
        joe_module, "task_spawn",
        lambda cmd, cwd, label: {"id": "test-0"},
    )
    joe_module.cmd_train(["lora"], default_model="joe-gemma")
    valid = (tmp_path / "lora-set" / "valid.jsonl").read_text().splitlines()
    assert len(valid) >= 4, f"valid set too small for default batch_size=4: {len(valid)}"


def test_lora_prep_train_and_valid_disjoint(joe_module, tmp_path, monkeypatch):
    """The first N records go to valid, next N to test, the rest to train.
    Train must not overlap with valid (avoids over-reporting eval scores)."""
    monkeypatch.setattr(joe_module, "TRAINING_DATA_DIR", tmp_path)
    _write_collected_jsonl(tmp_path, n_lines=20)
    fake_mlx = tmp_path / "mlx_lm.lora"
    fake_mlx.write_text("#!/bin/sh\n")
    fake_mlx.chmod(0o755)
    monkeypatch.setattr(
        joe_module.shutil, "which",
        lambda name: str(fake_mlx) if "mlx" in name else None,
    )
    monkeypatch.setattr(
        joe_module, "task_spawn",
        lambda cmd, cwd, label: {"id": "test-0"},
    )
    joe_module.cmd_train(["lora"], default_model="joe-gemma")
    train = set((tmp_path / "lora-set" / "train.jsonl").read_text().splitlines())
    valid = set((tmp_path / "lora-set" / "valid.jsonl").read_text().splitlines())
    assert train.isdisjoint(valid), "train.jsonl overlaps with valid.jsonl"


def test_lora_prep_refuses_when_too_few_examples(joe_module, tmp_path, monkeypatch, capsys):
    """With <8 examples there's no useful split, so refuse early with a hint."""
    monkeypatch.setattr(joe_module, "TRAINING_DATA_DIR", tmp_path)
    _write_collected_jsonl(tmp_path, n_lines=5)
    fake_mlx = tmp_path / "mlx_lm.lora"
    fake_mlx.write_text("#!/bin/sh\n")
    fake_mlx.chmod(0o755)
    monkeypatch.setattr(
        joe_module.shutil, "which",
        lambda name: str(fake_mlx) if "mlx" in name else None,
    )
    rc = joe_module.cmd_train(["lora"], default_model="joe-gemma")
    assert rc == 1
    # Should NOT have spawned anything if rc=1.
    assert not (tmp_path / "lora-set" / "train.jsonl").exists()
