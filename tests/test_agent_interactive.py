"""Testy jarvis/core/agent.py — ollama_chat success path, interactive_mode."""
import json
import urllib.request

import pytest

from jarvis.core import agent as ag
from jarvis.core.agent import ollama_chat, interactive_mode


# ── ollama_chat — success path (linia 64) ────────────────────────────────────

class _FakeResp:
    def __init__(self, content: str):
        self._data = json.dumps({"message": {"content": content}}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self):
        return self._data


def test_ollama_chat_success_returns_content(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp("odpowiedź ok"))
    result = ollama_chat([{"role": "user", "content": "test"}], "system")
    assert result == "odpowiedź ok"


# ── interactive_mode ──────────────────────────────────────────────────────────

def test_interactive_mode_exit(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "exit")
    interactive_mode()
    out = capsys.readouterr().out
    assert "zobaczenia" in out.lower()


def test_interactive_mode_empty_then_exit(monkeypatch):
    inputs = iter(["", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    interactive_mode()


def test_interactive_mode_task_then_quit(monkeypatch, capsys):
    inputs = iter(["sprawdź status", "quit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    monkeypatch.setattr(ag, "run_agent", lambda task, **kw: "wynik")
    interactive_mode()
    out = capsys.readouterr().out
    assert "zobaczenia" in out.lower()


def test_interactive_mode_eof_breaks(monkeypatch, capsys):
    def raise_eof(_prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    interactive_mode()
    out = capsys.readouterr().out
    assert "zobaczenia" in out.lower()
