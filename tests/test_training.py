"""Testy pipeline'u treningowego — scoring, ekstrakcja par, eksport."""
import importlib
import json


def test_score_pair_rewards_polish_and_length():
    tc = importlib.import_module("training_collect")
    short = tc.score_pair("pytanie", "ok")
    rich = tc.score_pair(
        "jak zrobić API?",
        "Panie TireQ, proponuję FastAPI. To się sprawdza jak nie wiem co. "
        "```python\napp = FastAPI()\n```"
    )
    assert rich > short


def test_is_quality_pair_rejects_short_answer():
    tc = importlib.import_module("training_collect")
    assert tc.is_quality_pair("pytanie", "krótko") is False


def test_is_quality_pair_accepts_good_answer():
    tc = importlib.import_module("training_collect")
    ans = "Panie TireQ, oto rozwiązanie. " * 5
    assert tc.is_quality_pair("jak to zrobić?", ans) is True


def test_extract_pairs_from_messages():
    tc = importlib.import_module("training_collect")
    messages = [
        {"role": "user", "content": "jak zrobić REST API?"},
        {"role": "assistant",
         "content": "Panie TireQ, " + "FastAPI to najlepszy wybór. " * 5},
    ]
    pairs = tc.extract_pairs(messages)
    assert len(pairs) == 1
    assert pairs[0]["messages"][1]["content"] == "jak zrobić REST API?"
    assert "score" in pairs[0]


def test_training_format_openai(tmp_path, monkeypatch):
    tf = importlib.import_module("training_format")
    raw = tmp_path / "raw_pairs.jsonl"
    raw.write_text(json.dumps({
        "id": "abc", "score": 0.8,
        "messages": [
            {"role": "system", "content": "S"},
            {"role": "user", "content": "U"},
            {"role": "assistant", "content": "A"}
        ]
    }) + "\n", encoding="utf-8")
    monkeypatch.setattr(tf, "RAW_FILE", raw)

    pairs = tf.load_raw(min_score=0.5)
    assert len(pairs) == 1

    out = tmp_path / "out.jsonl"
    n = tf.format_openai(pairs, out)
    assert n == 1
    entry = json.loads(out.read_text())
    assert entry["messages"][1]["content"] == "U"


def test_training_format_filters_low_score(tmp_path, monkeypatch):
    tf = importlib.import_module("training_format")
    raw = tmp_path / "raw_pairs.jsonl"
    raw.write_text(json.dumps({"id": "x", "score": 0.2, "messages": []}) + "\n",
                   encoding="utf-8")
    monkeypatch.setattr(tf, "RAW_FILE", raw)
    assert tf.load_raw(min_score=0.5) == []
