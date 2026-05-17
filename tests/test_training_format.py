"""Testy scripts/training_format.py — load_raw, format_openai, format_alpaca, format_huggingface, export."""
import json

import pytest

import training_format as tf


SAMPLE_PAIR = {
    "id": "abc123",
    "score": 0.75,
    "messages": [
        {"role": "system", "content": "Jesteś J.A.R.V.I.S."},
        {"role": "user", "content": "jak zrobić API?"},
        {"role": "assistant", "content": "Panie TireQ, użyj FastAPI."},
    ]
}


@pytest.fixture
def isolated_format(tmp_path, monkeypatch):
    training = tmp_path / "training"
    training.mkdir()
    raw = training / "raw_pairs.jsonl"
    monkeypatch.setattr(tf, "TRAINING_DIR", training)
    monkeypatch.setattr(tf, "RAW_FILE", raw)
    return {"training": training, "raw": raw}


def _write_pairs(path, pairs):
    with open(path, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")


# ── load_raw ──────────────────────────────────────────────────────────────────

def test_load_raw_missing_file(isolated_format):
    assert tf.load_raw() == []


def test_load_raw_reads_all(isolated_format):
    _write_pairs(isolated_format["raw"], [SAMPLE_PAIR])
    pairs = tf.load_raw(min_score=0.0)
    assert len(pairs) == 1


def test_load_raw_filters_by_score(isolated_format):
    low = {**SAMPLE_PAIR, "id": "low", "score": 0.3}
    high = {**SAMPLE_PAIR, "id": "high", "score": 0.8}
    _write_pairs(isolated_format["raw"], [low, high])
    pairs = tf.load_raw(min_score=0.5)
    assert len(pairs) == 1
    assert pairs[0]["id"] == "high"


def test_load_raw_skips_corrupt_lines(isolated_format):
    isolated_format["raw"].write_text(
        "nie json\n" + json.dumps(SAMPLE_PAIR) + "\n", encoding="utf-8"
    )
    pairs = tf.load_raw(min_score=0.0)
    assert len(pairs) == 1


def test_load_raw_default_min_score_is_half(isolated_format):
    below = {**SAMPLE_PAIR, "id": "b", "score": 0.4}
    above = {**SAMPLE_PAIR, "id": "a", "score": 0.6}
    _write_pairs(isolated_format["raw"], [below, above])
    pairs = tf.load_raw()  # default 0.5
    assert len(pairs) == 1
    assert pairs[0]["id"] == "a"


# ── format_openai ─────────────────────────────────────────────────────────────

def test_format_openai_output_structure(isolated_format):
    out = isolated_format["training"] / "openai.jsonl"
    count = tf.format_openai([SAMPLE_PAIR], out)
    assert count == 1
    data = json.loads(out.read_text())
    assert "messages" in data
    assert len(data["messages"]) == 3


def test_format_openai_multiple(isolated_format):
    pairs = [SAMPLE_PAIR, {**SAMPLE_PAIR, "id": "second"}]
    out = isolated_format["training"] / "openai.jsonl"
    count = tf.format_openai(pairs, out)
    assert count == 2
    lines = out.read_text().strip().splitlines()
    assert len(lines) == 2


def test_format_openai_preserves_roles(isolated_format):
    out = isolated_format["training"] / "openai.jsonl"
    tf.format_openai([SAMPLE_PAIR], out)
    data = json.loads(out.read_text())
    roles = [m["role"] for m in data["messages"]]
    assert roles == ["system", "user", "assistant"]


# ── format_alpaca ─────────────────────────────────────────────────────────────

def test_format_alpaca_output_structure(isolated_format):
    out = isolated_format["training"] / "alpaca.json"
    count = tf.format_alpaca([SAMPLE_PAIR], out)
    assert count == 1
    data = json.loads(out.read_text())
    assert isinstance(data, list)
    assert "instruction" in data[0]
    assert "input" in data[0]
    assert "output" in data[0]


def test_format_alpaca_maps_roles(isolated_format):
    out = isolated_format["training"] / "alpaca.json"
    tf.format_alpaca([SAMPLE_PAIR], out)
    entry = json.loads(out.read_text())[0]
    assert entry["instruction"] == "Jesteś J.A.R.V.I.S."
    assert entry["input"] == "jak zrobić API?"
    assert entry["output"] == "Panie TireQ, użyj FastAPI."


def test_format_alpaca_multiple(isolated_format):
    out = isolated_format["training"] / "alpaca.json"
    pairs = [SAMPLE_PAIR, {**SAMPLE_PAIR, "id": "s2"}]
    count = tf.format_alpaca(pairs, out)
    assert count == 2
    assert len(json.loads(out.read_text())) == 2


# ── format_huggingface ────────────────────────────────────────────────────────

def test_format_huggingface_output_structure(isolated_format):
    out = isolated_format["training"] / "hf.jsonl"
    count = tf.format_huggingface([SAMPLE_PAIR], out)
    assert count == 1
    data = json.loads(out.read_text())
    assert "text" in data


def test_format_huggingface_contains_tags(isolated_format):
    out = isolated_format["training"] / "hf.jsonl"
    tf.format_huggingface([SAMPLE_PAIR], out)
    text = json.loads(out.read_text())["text"]
    assert "<|system|>" in text
    assert "<|user|>" in text
    assert "<|assistant|>" in text


def test_format_huggingface_contains_content(isolated_format):
    out = isolated_format["training"] / "hf.jsonl"
    tf.format_huggingface([SAMPLE_PAIR], out)
    text = json.loads(out.read_text())["text"]
    assert "jak zrobić API?" in text
    assert "Panie TireQ, użyj FastAPI." in text


# ── export ────────────────────────────────────────────────────────────────────

def test_export_openai(isolated_format, capsys):
    _write_pairs(isolated_format["raw"], [SAMPLE_PAIR])
    tf.export("openai", 0.5)
    out = isolated_format["training"] / "openai_finetune.jsonl"
    assert out.exists()
    assert "openai" in capsys.readouterr().out


def test_export_alpaca(isolated_format):
    _write_pairs(isolated_format["raw"], [SAMPLE_PAIR])
    tf.export("alpaca", 0.5)
    out = isolated_format["training"] / "alpaca_train.json"
    assert out.exists()


def test_export_huggingface(isolated_format):
    _write_pairs(isolated_format["raw"], [SAMPLE_PAIR])
    tf.export("huggingface", 0.5)
    out = isolated_format["training"] / "hf_train.jsonl"
    assert out.exists()


def test_export_all_creates_three_files(isolated_format):
    _write_pairs(isolated_format["raw"], [SAMPLE_PAIR])
    tf.export("all", 0.5)
    assert (isolated_format["training"] / "openai_finetune.jsonl").exists()
    assert (isolated_format["training"] / "alpaca_train.json").exists()
    assert (isolated_format["training"] / "hf_train.jsonl").exists()


def test_export_no_data_prints_message(isolated_format, capsys):
    tf.export("openai", 0.9)  # score 0.9 — żadna para nie przejdzie
    out = capsys.readouterr().out
    assert "Brak" in out
