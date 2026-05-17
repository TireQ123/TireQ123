"""Testy scripts/rag_index.py — stable_id, load_json, collect_documents (mock chromadb)."""
import json

import pytest

import rag_index as ri


@pytest.fixture
def isolated_index(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    sessions = mem / "sessions"
    sessions.mkdir(parents=True)
    monkeypatch.setattr(ri, "MEMORY_DIR", mem)
    monkeypatch.setattr(ri, "CHROMA_DIR", mem / "chroma_db")
    return {"mem": mem, "sessions": sessions}


# ── stable_id ─────────────────────────────────────────────────────────────────

def test_stable_id_deterministic():
    id1 = ri.stable_id("backend Python", "dec")
    id2 = ri.stable_id("backend Python", "dec")
    assert id1 == id2


def test_stable_id_prefix_included():
    assert ri.stable_id("text", "pref").startswith("pref_")
    assert ri.stable_id("text", "dec").startswith("dec_")
    assert ri.stable_id("text", "note").startswith("note_")


def test_stable_id_length():
    sid = ri.stable_id("jakiś tekst", "sess")
    assert len(sid) == len("sess_") + 12


def test_stable_id_differs_for_different_text():
    assert ri.stable_id("A", "x") != ri.stable_id("B", "x")


# ── load_json ─────────────────────────────────────────────────────────────────

def test_load_json_reads_file(tmp_path):
    f = tmp_path / "d.json"
    f.write_text(json.dumps({"key": "value"}), encoding="utf-8")
    assert ri.load_json(f) == {"key": "value"}


def test_load_json_missing_returns_empty(tmp_path):
    assert ri.load_json(tmp_path / "ghost.json") == {}


# ── collect_documents ─────────────────────────────────────────────────────────

def test_collect_documents_empty_memory(isolated_index):
    docs = ri.collect_documents()
    assert docs == []


def test_collect_documents_from_decisions(isolated_index):
    decisions = {
        "decisions": [
            {"date": "2026-01-01T09:00", "decision": "backend Python"},
            {"date": "2026-01-02T09:00", "decision": "frontend React"},
        ]
    }
    (isolated_index["mem"] / "decisions.json").write_text(
        json.dumps(decisions), encoding="utf-8"
    )
    docs = ri.collect_documents()
    texts = [d[1] for d in docs]
    assert "backend Python" in texts
    assert "frontend React" in texts


def test_collect_documents_decision_metadata(isolated_index):
    decisions = {
        "decisions": [{"date": "2026-05-01T10:00", "decision": "PostgreSQL", "source": "manual"}]
    }
    (isolated_index["mem"] / "decisions.json").write_text(
        json.dumps(decisions), encoding="utf-8"
    )
    docs = ri.collect_documents()
    _, text, meta = docs[0]
    assert meta["type"] == "decision"
    assert meta["source"] == "manual"


def test_collect_documents_from_profile_prefs(isolated_index):
    profile = {
        "patterns": {"preferred_solutions": ["FastAPI", "pytest"], "avoided_approaches": []},
        "notes": []
    }
    (isolated_index["mem"] / "profile.json").write_text(
        json.dumps(profile), encoding="utf-8"
    )
    docs = ri.collect_documents()
    texts = [d[1] for d in docs]
    assert "FastAPI" in texts
    assert "pytest" in texts


def test_collect_documents_from_profile_notes(isolated_index):
    profile = {
        "patterns": {"preferred_solutions": [], "avoided_approaches": []},
        "notes": [{"date": "2026-01-01T10:00", "note": "deadline w czerwcu"}]
    }
    (isolated_index["mem"] / "profile.json").write_text(
        json.dumps(profile), encoding="utf-8"
    )
    docs = ri.collect_documents()
    texts = [d[1] for d in docs]
    assert "deadline w czerwcu" in texts


def test_collect_documents_from_sessions(isolated_index):
    (isolated_index["sessions"] / "2026-05-01.json").write_text(json.dumps({
        "date": "2026-05-01",
        "summary": "praca nad RAG"
    }), encoding="utf-8")
    docs = ri.collect_documents()
    texts = [d[1] for d in docs]
    assert "praca nad RAG" in texts


def test_collect_documents_session_metadata(isolated_index):
    (isolated_index["sessions"] / "2026-05-10.json").write_text(json.dumps({
        "date": "2026-05-10",
        "summary": "testy jednostkowe"
    }), encoding="utf-8")
    docs = ri.collect_documents()
    _, text, meta = docs[0]
    assert meta["type"] == "session"
    assert meta["file"] == "2026-05-10.json"


def test_collect_documents_skips_empty_text(isolated_index):
    decisions = {"decisions": [{"date": "2026-01-01T09:00", "decision": ""}]}
    (isolated_index["mem"] / "decisions.json").write_text(
        json.dumps(decisions), encoding="utf-8"
    )
    assert ri.collect_documents() == []


def test_collect_documents_stable_ids_are_unique(isolated_index):
    decisions = {
        "decisions": [
            {"date": "2026-01-01T09:00", "decision": "backend Python"},
            {"date": "2026-01-02T09:00", "decision": "frontend React"},
        ]
    }
    (isolated_index["mem"] / "decisions.json").write_text(
        json.dumps(decisions), encoding="utf-8"
    )
    docs = ri.collect_documents()
    ids = [d[0] for d in docs]
    assert len(ids) == len(set(ids))


# ── index_all (mock chromadb) ─────────────────────────────────────────────────

class FakeCollection:
    def __init__(self):
        self._data = {}

    def get(self):
        return {"ids": list(self._data.keys())}

    def upsert(self, ids, documents, metadatas):
        for id_, doc, meta in zip(ids, documents, metadatas):
            self._data[id_] = {"doc": doc, "meta": meta}


@pytest.fixture
def fake_collection(monkeypatch):
    col = FakeCollection()
    monkeypatch.setattr(ri, "get_collection", lambda: col)
    return col


def test_index_all_returns_zero_on_empty(isolated_index, fake_collection):
    assert ri.index_all() == 0


def test_index_all_indexes_decisions(isolated_index, fake_collection):
    decisions = {
        "decisions": [
            {"date": "2026-01-01T09:00", "decision": "backend Python"},
        ]
    }
    (isolated_index["mem"] / "decisions.json").write_text(
        json.dumps(decisions), encoding="utf-8"
    )
    count = ri.index_all()
    assert count == 1


def test_index_all_delta_skips_existing(isolated_index, fake_collection):
    decisions = {
        "decisions": [
            {"date": "2026-01-01T09:00", "decision": "backend Python"},
        ]
    }
    (isolated_index["mem"] / "decisions.json").write_text(
        json.dumps(decisions), encoding="utf-8"
    )
    ri.index_all()  # pełny indeks
    count = ri.index_all(delta=True)  # delta — nic nowego
    assert count == 0


def test_index_all_delta_adds_new(isolated_index, fake_collection):
    (isolated_index["mem"] / "decisions.json").write_text(
        json.dumps({"decisions": [{"date": "2026-01-01T09:00", "decision": "Python"}]}),
        encoding="utf-8"
    )
    ri.index_all()

    # Dodajemy nową sesję
    (isolated_index["sessions"] / "new.json").write_text(
        json.dumps({"date": "2026-05-01", "summary": "nowa sesja"}), encoding="utf-8"
    )
    count = ri.index_all(delta=True)
    assert count == 1
