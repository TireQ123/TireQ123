"""Testy scripts/rag_inject.py — get_last_user_message, build_rag_block, inject_to_claude."""
import json

import pytest

import rag_inject as ri


@pytest.fixture
def isolated_inject(tmp_path, monkeypatch):
    claude = tmp_path / "CLAUDE.md"
    claude.write_text("# Projekt\n\nOpis projektu.\n", encoding="utf-8")
    monkeypatch.setattr(ri, "CLAUDE_FILE", claude)
    return claude


# ── get_last_user_message ────────────────────────────────────────────────────

def test_get_last_user_string(tmp_path):
    t = tmp_path / "t.json"
    t.write_text(json.dumps([
        {"role": "user", "content": "pierwsze"},
        {"role": "assistant", "content": "odpowiedź"},
        {"role": "user", "content": "drugie pytanie"},
    ]), encoding="utf-8")
    assert ri.get_last_user_message(str(t)) == "drugie pytanie"


def test_get_last_user_from_messages_key(tmp_path):
    t = tmp_path / "t.json"
    t.write_text(json.dumps({"messages": [
        {"role": "user", "content": "z klucza messages"},
    ]}), encoding="utf-8")
    assert ri.get_last_user_message(str(t)) == "z klucza messages"


def test_get_last_user_content_blocks(tmp_path):
    t = tmp_path / "t.json"
    t.write_text(json.dumps([
        {"role": "user", "content": [
            {"type": "text", "text": "blok tekstowy"},
            {"type": "image", "url": "x"},
        ]},
    ]), encoding="utf-8")
    assert ri.get_last_user_message(str(t)) == "blok tekstowy"


def test_get_last_user_missing_file():
    assert ri.get_last_user_message("/nope/ghost.json") is None


def test_get_last_user_caps_at_500_chars(tmp_path):
    t = tmp_path / "t.json"
    long_msg = "x" * 1000
    t.write_text(json.dumps([{"role": "user", "content": long_msg}]), encoding="utf-8")
    result = ri.get_last_user_message(str(t))
    assert len(result) == 500


def test_get_last_user_skips_non_user(tmp_path):
    t = tmp_path / "t.json"
    t.write_text(json.dumps([
        {"role": "assistant", "content": "odpowiedź bez pytania"},
    ]), encoding="utf-8")
    assert ri.get_last_user_message(str(t)) is None


# ── build_rag_block ──────────────────────────────────────────────────────────

def test_build_rag_block_empty_returns_empty():
    assert ri.build_rag_block([]) == ""


def test_build_rag_block_contains_markers():
    items = [{"type": "decision", "text": "backend Python", "date": "2026-01-01"}]
    block = ri.build_rag_block(items)
    assert ri.MARKER_START in block
    assert ri.MARKER_END in block


def test_build_rag_block_contains_text():
    items = [{"type": "decision", "text": "backend Python", "date": "2026-01-01"}]
    block = ri.build_rag_block(items)
    assert "backend Python" in block


def test_build_rag_block_multiple_items():
    items = [
        {"type": "decision", "text": "backend Python", "date": "2026-01-01"},
        {"type": "preference", "text": "FastAPI", "date": ""},
    ]
    block = ri.build_rag_block(items)
    assert "backend Python" in block
    assert "FastAPI" in block


def test_build_rag_block_no_date_omits_brackets():
    items = [{"type": "preference", "text": "Vim", "date": ""}]
    block = ri.build_rag_block(items)
    assert "[]" not in block


def test_build_rag_block_with_date_shows_date():
    items = [{"type": "decision", "text": "test", "date": "2026-05-01"}]
    block = ri.build_rag_block(items)
    assert "2026-05-01" in block


# ── inject_to_claude ─────────────────────────────────────────────────────────

def test_inject_appends_when_no_marker(isolated_inject):
    block = f"{ri.MARKER_START}\nNOWY BLOK\n{ri.MARKER_END}"
    ri.inject_to_claude(block)
    content = isolated_inject.read_text()
    assert "# Projekt" in content
    assert "NOWY BLOK" in content


def test_inject_replaces_existing_marker(isolated_inject):
    old = f"# Projekt\n{ri.MARKER_START}\nSTARE\n{ri.MARKER_END}\n"
    isolated_inject.write_text(old, encoding="utf-8")
    new_block = f"{ri.MARKER_START}\nNOWE\n{ri.MARKER_END}"
    ri.inject_to_claude(new_block)
    content = isolated_inject.read_text()
    assert "STARE" not in content
    assert "NOWE" in content
    assert content.count(ri.MARKER_START) == 1


def test_inject_preserves_surrounding_content(isolated_inject):
    old = f"# Projekt\n{ri.MARKER_START}\nOLD\n{ri.MARKER_END}\n\n## Reszta\n"
    isolated_inject.write_text(old, encoding="utf-8")
    new_block = f"{ri.MARKER_START}\nNEW\n{ri.MARKER_END}"
    ri.inject_to_claude(new_block)
    content = isolated_inject.read_text()
    assert "# Projekt" in content
    assert "## Reszta" in content
