"""Testy jarvis/core/multi_agent.py — _parse_json, run_sub_agent, orchestrate."""
import pytest

from jarvis.core import multi_agent as ma


# ── _parse_json ───────────────────────────────────────────────────────────────

def test_parse_json_clean():
    result = ma._parse_json('{"plan": "x", "subtasks": []}')
    assert result["plan"] == "x"


def test_parse_json_with_surrounding_text():
    result = ma._parse_json('Oto plan:\n{"plan": "coś"}\nKoniec.')
    assert result["plan"] == "coś"


def test_parse_json_malformed_returns_empty():
    assert ma._parse_json("{nie: poprawny}") == {}


def test_parse_json_no_json_returns_empty():
    assert ma._parse_json("brak json w ogóle") == {}


def test_parse_json_empty_object():
    assert ma._parse_json("{}") == {}


# ── AGENTS registry ───────────────────────────────────────────────────────────

def test_all_agents_have_required_keys():
    for name, cfg in ma.AGENTS.items():
        assert "description" in cfg, f"{name} brak description"
        assert "tools" in cfg, f"{name} brak tools"
        assert "system" in cfg, f"{name} brak system"


def test_agent_tools_are_valid_strings():
    for name, cfg in ma.AGENTS.items():
        for tool in cfg["tools"]:
            assert isinstance(tool, str) and tool, f"{name} ma pusty tool"


def test_known_agents_present():
    for expected in ("code_agent", "git_agent", "research_agent", "memory_agent", "file_agent"):
        assert expected in ma.AGENTS


# ── run_sub_agent ─────────────────────────────────────────────────────────────

def test_run_sub_agent_unknown_agent():
    result = ma.run_sub_agent("ghost_agent", "zadanie", verbose=False)
    assert "Nieznany agent" in result


def test_run_sub_agent_no_tool_call(monkeypatch):
    monkeypatch.setattr(ma, "_ollama", lambda msgs, system, temperature=0.3: "Gotowe, Panie TireQ.")
    result = ma.run_sub_agent("code_agent", "proste zadanie", verbose=False)
    assert "Gotowe" in result


def test_run_sub_agent_executes_tool(monkeypatch):
    responses = iter([
        '<tool>\n{"name": "file_list", "params": {"path": "."}}\n</tool>',
        "Lista plików gotowa."
    ])
    monkeypatch.setattr(ma, "_ollama", lambda msgs, system, temperature=0.3: next(responses))
    result = ma.run_sub_agent("code_agent", "pokaż pliki", verbose=False)
    assert result == "Lista plików gotowa."


def test_run_sub_agent_handles_ollama_error(monkeypatch):
    monkeypatch.setattr(ma, "_ollama", lambda msgs, system, temperature=0.3: "[BŁĄD] brak połączenia")
    result = ma.run_sub_agent("git_agent", "git status", verbose=False)
    assert "[BŁĄD]" in result


# ── orchestrate ───────────────────────────────────────────────────────────────

def test_orchestrate_simple_task_no_subtasks(monkeypatch):
    call_log = []
    def fake_ollama(msgs, system, temperature=0.3):
        call_log.append(temperature)
        return "prosta odpowiedź"  # brak JSON → brak subtasks

    monkeypatch.setattr(ma, "_ollama", fake_ollama)
    result = ma.orchestrate("proste pytanie", verbose=False)
    assert isinstance(result, str)


def test_orchestrate_with_subtasks(monkeypatch):
    call_count = {"n": 0}

    def fake_ollama(msgs, system, temperature=0.3):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return '{"plan": "plan", "subtasks": [{"agent": "code_agent", "task": "pisz kod"}]}'
        return "Wynik podzadania lub podsumowanie."

    monkeypatch.setattr(ma, "_ollama", fake_ollama)
    result = ma.orchestrate("złożone zadanie", verbose=False)
    assert isinstance(result, str)
    assert call_count["n"] >= 2


def test_orchestrate_skips_empty_subtask_task(monkeypatch):
    call_count = {"n": 0}

    def fake_ollama(msgs, system, temperature=0.3):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return '{"plan": "p", "subtasks": [{"agent": "code_agent", "task": ""}]}'
        return "podsumowanie"

    monkeypatch.setattr(ma, "_ollama", fake_ollama)
    result = ma.orchestrate("zadanie", verbose=False)
    assert isinstance(result, str)


# ── _ollama error path ────────────────────────────────────────────────────────

def test_ollama_returns_error_on_exception(monkeypatch):
    def boom(*a, **k):
        raise OSError("brak Ollama")

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    result = ma._ollama([{"role": "user", "content": "test"}], "system")
    assert "[BŁĄD]" in result
