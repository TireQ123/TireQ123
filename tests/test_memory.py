"""Testy systemu pamięci — deduplikacja, normalizacja, zapis."""
import importlib

import pytest


def test_normalize_collapses_whitespace_and_case():
    ms = importlib.import_module("memory_sync")
    assert ms.normalize("  FastAPI   Jest  Super ") == "fastapi jest super"


def test_similarity_identical_is_one():
    ms = importlib.import_module("memory_sync")
    assert ms.similarity("FastAPI backend", "fastapi backend") == pytest.approx(1.0)


def test_similarity_different_is_low():
    ms = importlib.import_module("memory_sync")
    assert ms.similarity("React frontend", "PostgreSQL baza") < 0.5


def test_is_duplicate_detects_paraphrase():
    ms = importlib.import_module("memory_sync")
    existing = ["używamy FastAPI jako backend"]
    assert ms.is_duplicate("uzywamy FastAPI jako backend", existing) is True


def test_is_duplicate_allows_distinct_entry():
    ms = importlib.import_module("memory_sync")
    existing = ["używamy FastAPI jako backend"]
    assert ms.is_duplicate("frontend w React z TypeScript", existing) is False


def test_extract_from_transcript_finds_decision(sample_transcript):
    ms = importlib.import_module("memory_sync")
    extracted = ms.extract_from_transcript(sample_transcript)
    joined = " ".join(extracted["decisions"] + extracted["preferences"]).lower()
    assert "postgresql" in joined or "fastapi" in joined


def test_memory_update_add_decision(tmp_memory, monkeypatch):
    import memory_update as mu
    monkeypatch.setattr(mu, "DECISIONS_FILE", tmp_memory / "decisions.json")
    mu.add_decision("backend w Pythonie")
    import json
    data = json.loads((tmp_memory / "decisions.json").read_text())
    assert any("Pythonie" in d["decision"] for d in data["decisions"])


def test_memory_update_dedupes_preferences(tmp_memory, monkeypatch):
    import memory_update as mu
    monkeypatch.setattr(mu, "PROFILE_FILE", tmp_memory / "profile.json")
    mu.add_preference("preferuje FastAPI")
    mu.add_preference("preferuje FastAPI")
    import json
    data = json.loads((tmp_memory / "profile.json").read_text())
    prefs = data["patterns"]["preferred_solutions"]
    assert prefs.count("preferuje FastAPI") == 1
