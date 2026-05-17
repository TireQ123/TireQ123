"""Testy jarvis/core/agent.py — run_agent, ollama_chat."""
import urllib.request

import pytest

from jarvis.core import agent as ag
from jarvis.core.agent import run_agent, ollama_chat


# ── ollama_chat ───────────────────────────────────────────────────────────────

def test_ollama_chat_error_returns_blad(monkeypatch):
    def boom(*a, **k):
        raise OSError("brak sieci")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    result = ollama_chat([{"role": "user", "content": "test"}], "system")
    assert "[BŁĄD OLLAMA]" in result


# ── run_agent ─────────────────────────────────────────────────────────────────

def test_run_agent_no_tool_call_returns_response(monkeypatch):
    monkeypatch.setattr(ag, "ollama_chat", lambda msgs, sys: "Gotowe, Panie TireQ.")
    result = run_agent("proste zadanie", verbose=False)
    assert "Gotowe" in result


def test_run_agent_verbose_prints(monkeypatch, capsys):
    monkeypatch.setattr(ag, "ollama_chat", lambda msgs, sys: "Odpowiedź.")
    run_agent("zadanie testowe", verbose=True)
    out = capsys.readouterr().out
    assert "zadanie testowe" in out


def test_run_agent_executes_tool_then_finishes(monkeypatch):
    responses = iter([
        '<tool>\n{"name": "file_list", "params": {"directory": "."}}\n</tool>',
        "Lista plików pobrana, Panie TireQ."
    ])
    monkeypatch.setattr(ag, "ollama_chat", lambda msgs, sys: next(responses))
    result = run_agent("pokaż pliki", verbose=False)
    assert "Lista plików" in result


def test_run_agent_reaches_max_steps(monkeypatch, monkeypatch_session=None):
    monkeypatch.setattr(ag, "MAX_STEPS", 3)
    monkeypatch.setattr(ag, "ollama_chat",
        lambda msgs, sys: '<tool>\n{"name": "file_list", "params": {}}\n</tool>')
    result = run_agent("zapętlone zadanie", verbose=False)
    assert "limit" in result.lower()


def test_run_agent_tool_override(monkeypatch):
    called = []

    def custom_tool():
        called.append(True)
        return {"status": "ok", "result": "custom_ok"}

    responses = iter([
        '<tool>\n{"name": "custom_xyz", "params": {}}\n</tool>',
        "Gotowe."
    ])
    monkeypatch.setattr(ag, "ollama_chat", lambda msgs, sys: next(responses))
    run_agent("użyj custom", verbose=False, tool_override={"custom_xyz": custom_tool})
    assert called


def test_run_agent_verbose_shows_tool_step(monkeypatch, capsys):
    responses = iter([
        '<tool>\n{"name": "file_list", "params": {}}\n</tool>',
        "Zakończono."
    ])
    monkeypatch.setattr(ag, "ollama_chat", lambda msgs, sys: next(responses))
    run_agent("task", verbose=True)
    out = capsys.readouterr().out
    assert "file_list" in out or "Krok" in out


def test_run_agent_unknown_tool_still_continues(monkeypatch):
    responses = iter([
        '<tool>\n{"name": "nieznane_narzedzie_xyz", "params": {}}\n</tool>',
        "Skończyłem."
    ])
    monkeypatch.setattr(ag, "ollama_chat", lambda msgs, sys: next(responses))
    result = run_agent("zadanie", verbose=False)
    assert isinstance(result, str)


def test_run_agent_extra_tools_in_system(monkeypatch):
    captured_system = []
    monkeypatch.setattr(ag, "ollama_chat",
        lambda msgs, sys: captured_system.append(sys) or "Gotowe.")
    extra = [{"name": "special_tool", "description": "test", "params": {}}]
    run_agent("zadanie", verbose=False, extra_tools=extra)
    assert any("special_tool" in s for s in captured_system)
