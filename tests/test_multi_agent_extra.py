"""Testy dodatkowe jarvis/core/multi_agent.py — verbose paths, tool exception, interactive_mode."""
import pytest

from jarvis.core import multi_agent as ma


# ── run_sub_agent verbose=True ────────────────────────────────────────────────

def test_run_sub_agent_verbose_no_tool(monkeypatch, capsys):
    monkeypatch.setattr(ma, "_ollama",
                        lambda msgs, system, temperature=0.3: "Gotowe, Panie TireQ.")
    result = ma.run_sub_agent("code_agent", "zadanie testowe", verbose=True)
    out = capsys.readouterr().out
    assert "code_agent" in out
    assert "Gotowe" in result


def test_run_sub_agent_verbose_with_tool(monkeypatch, capsys):
    responses = iter([
        '<tool>\n{"name": "file_list", "params": {"directory": "."}}\n</tool>',
        "Lista gotowa."
    ])
    monkeypatch.setattr(ma, "_ollama",
                        lambda msgs, system, temperature=0.3: next(responses))
    result = ma.run_sub_agent("code_agent", "pokaż pliki", verbose=True)
    out = capsys.readouterr().out
    assert "file_list" in out
    assert "Lista gotowa" in result


def test_run_sub_agent_tool_exception(monkeypatch):
    monkeypatch.setattr(ma, "_ollama",
                        lambda msgs, system, temperature=0.3:
                        '<tool>\n{"name": "file_list", "params": {}}\n</tool>')
    # execute_tool is imported directly into multi_agent's namespace
    monkeypatch.setattr(ma, "execute_tool",
                        lambda name, params: (_ for _ in ()).throw(RuntimeError("kaboom")))
    result = ma.run_sub_agent("code_agent", "zadanie", verbose=False)
    assert "Błąd agenta" in result


# ── orchestrate verbose=True ──────────────────────────────────────────────────

def test_orchestrate_verbose_no_subtasks(monkeypatch, capsys):
    monkeypatch.setattr(ma, "_ollama",
                        lambda msgs, system, temperature=0.3: "zwykła odpowiedź bez JSON")
    result = ma.orchestrate("proste zadanie", verbose=True)
    out = capsys.readouterr().out
    assert "ORCHESTRATOR" in out
    assert isinstance(result, str)


def test_orchestrate_verbose_with_subtasks(monkeypatch, capsys):
    call_count = {"n": 0}

    def fake_ollama(msgs, system, temperature=0.3):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return '{"plan": "plan testowy", "subtasks": [{"agent": "code_agent", "task": "pisz kod"}]}'
        return "Wynik sub-agenta."

    monkeypatch.setattr(ma, "_ollama", fake_ollama)
    result = ma.orchestrate("złożone zadanie", verbose=True)
    out = capsys.readouterr().out
    assert "Plan" in out or "plan testowy" in out
    assert isinstance(result, str)


# ── interactive_mode ──────────────────────────────────────────────────────────

def test_interactive_mode_exit(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "exit")
    ma.interactive_mode()
    out = capsys.readouterr().out
    # "exit" breaks without farewell print; banner should still appear
    assert "Multi-Agent" in out


def test_interactive_mode_empty_then_quit(monkeypatch, capsys):
    inputs = iter(["", "quit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    ma.interactive_mode()


def test_interactive_mode_eof(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input",
                        lambda _: (_ for _ in ()).throw(EOFError()))
    ma.interactive_mode()
    out = capsys.readouterr().out
    assert "zobaczenia" in out.lower()
