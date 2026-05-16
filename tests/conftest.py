"""Wspólne fixtury dla testów J.A.R.V.I.S."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture
def tmp_memory(tmp_path, monkeypatch):
    """Izolowany katalog pamięci na czas testu."""
    mem = tmp_path / "memory"
    mem.mkdir()
    (mem / "sessions").mkdir()
    (mem / "profile.json").write_text(json.dumps({
        "user": {"name": "Marcel", "alias": "TireQ"},
        "preferences": {"frameworks": []},
        "patterns": {"common_tasks": [], "avoided_approaches": [],
                     "preferred_solutions": []},
        "notes": []
    }), encoding="utf-8")
    (mem / "decisions.json").write_text(
        json.dumps({"decisions": []}), encoding="utf-8")
    return mem


@pytest.fixture
def sample_transcript(tmp_path):
    """Przykładowy transkrypt sesji."""
    t = tmp_path / "transcript.json"
    t.write_text(json.dumps([
        {"role": "user", "content": "preferuję FastAPI nad Flask"},
        {"role": "assistant", "content": "Zrozumiałem, Panie TireQ. "
         "FastAPI to doskonały wybór — walidacja typów i async w cenie."},
        {"role": "user", "content": "używamy PostgreSQL jako baza danych"},
        {"role": "assistant", "content": "Notuję, Panie TireQ."},
    ]), encoding="utf-8")
    return str(t)
