"""Testy scripts/memory_load.py — budowanie kontekstu i wstrzykiwanie do CLAUDE.md."""
import json

import pytest

import memory_load as ml


@pytest.fixture
def isolated_load(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    sessions = mem / "sessions"
    sessions.mkdir(parents=True)
    claude = tmp_path / "CLAUDE.md"
    monkeypatch.setattr(ml, "PROFILE_FILE", mem / "profile.json")
    monkeypatch.setattr(ml, "DECISIONS_FILE", mem / "decisions.json")
    monkeypatch.setattr(ml, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(ml, "CLAUDE_FILE", claude)
    return {"mem": mem, "sessions": sessions, "claude": claude}


def _write_profile(path, prefs=None, avoided=None, notes=None):
    path.write_text(json.dumps({
        "patterns": {
            "preferred_solutions": prefs or [],
            "avoided_approaches": avoided or [],
        },
        "notes": notes or [],
    }), encoding="utf-8")


def test_load_json_reads(tmp_path):
    f = tmp_path / "d.json"
    f.write_text(json.dumps({"k": 1}), encoding="utf-8")
    assert ml.load_json(f) == {"k": 1}


def test_get_last_sessions_no_dir(isolated_load, monkeypatch):
    monkeypatch.setattr(ml, "SESSIONS_DIR", isolated_load["mem"] / "ghost")
    assert ml.get_last_sessions() == []


def test_get_last_sessions_returns_newest_first(isolated_load):
    s = isolated_load["sessions"]
    (s / "2026-05-01.json").write_text(json.dumps(
        {"date": "2026-05-01", "summary": "stara"}), encoding="utf-8")
    (s / "2026-05-15.json").write_text(json.dumps(
        {"date": "2026-05-15", "summary": "nowa"}), encoding="utf-8")
    out = ml.get_last_sessions(3)
    assert out[0]["summary"] == "nowa"


def test_build_context_full(isolated_load):
    _write_profile(
        isolated_load["mem"] / "profile.json",
        prefs=["FastAPI nad Flask"],
        avoided=["globalne zmienne"],
        notes=[{"date": "2026-05-10T10:00", "note": "deadline w czerwcu"}],
    )
    (isolated_load["mem"] / "decisions.json").write_text(json.dumps({
        "decisions": [{"date": "2026-04-01T09:00", "decision": "backend Python"}]
    }), encoding="utf-8")
    (isolated_load["sessions"] / "s.json").write_text(json.dumps(
        {"date": "2026-05-12", "summary": "praca nad RAG"}), encoding="utf-8")

    ctx = ml.build_context()

    assert ml.CONTEXT_MARKER_START in ctx
    assert ml.CONTEXT_MARKER_END in ctx
    assert "FastAPI nad Flask" in ctx
    assert "globalne zmienne" in ctx
    assert "backend Python" in ctx
    assert "deadline w czerwcu" in ctx
    assert "praca nad RAG" in ctx


def test_build_context_empty_sections_omitted(isolated_load):
    _write_profile(isolated_load["mem"] / "profile.json")
    (isolated_load["mem"] / "decisions.json").write_text(
        json.dumps({"decisions": []}), encoding="utf-8")
    ctx = ml.build_context()
    assert "### Preferencje techniczne" not in ctx
    assert "### Ostatnie decyzje" not in ctx
    assert ctx.strip().endswith(ml.CONTEXT_MARKER_END)


def test_update_claude_md_appends_when_no_marker(isolated_load):
    isolated_load["claude"].write_text("# Projekt\n\nOpis.", encoding="utf-8")
    ml.update_claude_md("BLOK PAMIĘCI")
    content = isolated_load["claude"].read_text()
    assert "# Projekt" in content
    assert "BLOK PAMIĘCI" in content


def test_update_claude_md_replaces_existing_block(isolated_load):
    original = (
        f"# Projekt\n\n{ml.CONTEXT_MARKER_START}\nSTARE\n"
        f"{ml.CONTEXT_MARKER_END}\n\n## Reszta"
    )
    isolated_load["claude"].write_text(original, encoding="utf-8")
    new_block = f"{ml.CONTEXT_MARKER_START}\nNOWE\n{ml.CONTEXT_MARKER_END}"
    ml.update_claude_md(new_block)
    content = isolated_load["claude"].read_text()
    assert "STARE" not in content
    assert "NOWE" in content
    assert "## Reszta" in content
    assert content.count(ml.CONTEXT_MARKER_START) == 1
