"""Testy scripts/rag_query.py — fallback keyword search i formatowanie."""
import json

import pytest

import rag_query as rq


@pytest.fixture
def memory_with_data(tmp_path, monkeypatch):
    """Izolowany ROOT z plikami pamięci dla _keyword_search."""
    root = tmp_path
    mem = root / "memory"
    mem.mkdir()
    (mem / "decisions.json").write_text(json.dumps({
        "decisions": [
            {"decision": "backend w Pythonie z FastAPI", "date": "2026-01-10T12:00:00"},
            {"decision": "frontend w React z TypeScript", "date": "2026-02-01T09:00:00"},
        ]
    }), encoding="utf-8")
    (mem / "profile.json").write_text(json.dumps({
        "patterns": {"preferred_solutions": ["preferuje PostgreSQL nad MySQL"]},
        "notes": [{"note": "deadline projektu w czerwcu", "date": "2026-03-01T10:00:00"}],
    }), encoding="utf-8")
    monkeypatch.setattr(rq, "ROOT", root)
    return root


def test_keyword_search_finds_relevant_decision(memory_with_data):
    hits = rq._keyword_search("backend FastAPI", top_k=5, filter_type=None)
    assert any("FastAPI" in h["text"] for h in hits)
    assert hits[0]["type"] == "decision"
    assert hits[0]["relevance"] > 0


def test_keyword_search_filters_by_type(memory_with_data):
    hits = rq._keyword_search("PostgreSQL", top_k=5, filter_type="preference")
    assert len(hits) == 1
    assert hits[0]["type"] == "preference"


def test_keyword_search_type_filter_excludes_others(memory_with_data):
    hits = rq._keyword_search("backend FastAPI", top_k=5, filter_type="note")
    assert hits == []


def test_keyword_search_finds_note(memory_with_data):
    hits = rq._keyword_search("deadline czerwiec", top_k=5, filter_type=None)
    assert any(h["type"] == "note" for h in hits)


def test_keyword_search_respects_top_k(memory_with_data):
    hits = rq._keyword_search("Pythonie React PostgreSQL deadline",
                              top_k=2, filter_type=None)
    assert len(hits) <= 2


def test_keyword_search_no_match_returns_empty(memory_with_data):
    assert rq._keyword_search("kosmiczna teledetekcja kwantowa",
                              top_k=5, filter_type=None) == []


def test_keyword_search_ignores_short_tokens(memory_with_data):
    # same krótkie słowa (<=2 znaki) → brak słów kluczowych → brak trafień
    assert rq._keyword_search("a w z to", top_k=5, filter_type=None) == []


def test_keyword_search_missing_files_no_crash(tmp_path, monkeypatch):
    (tmp_path / "memory").mkdir()
    monkeypatch.setattr(rq, "ROOT", tmp_path)
    assert rq._keyword_search("cokolwiek", top_k=3, filter_type=None) == []


def test_format_results_empty():
    assert "Brak relevantnych" in rq.format_results([])


def test_format_results_renders_label_date_percent():
    out = rq.format_results([
        {"text": "decyzja X", "type": "decision",
         "date": "2026-01-01", "relevance": 0.85},
    ])
    assert "Decyzja" in out
    assert "2026-01-01" in out
    assert "85%" in out
    assert "decyzja X" in out


def test_format_results_unknown_type_falls_back():
    out = rq.format_results([
        {"text": "x", "type": "mystic", "date": "", "relevance": 0.5},
    ])
    assert "mystic" in out
