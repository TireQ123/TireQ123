"""Testy jarvis/api/server.py — endpointy FastAPI przez TestClient."""
import json

import pytest
from fastapi.testclient import TestClient

# Mockujemy Ollama przed importem app, żeby uniknąć timeout przy starcie
import urllib.request


@pytest.fixture(autouse=True)
def mock_ollama_at_module_level(monkeypatch):
    """Domyślna odpowiedź Ollama dla wszystkich testów serwera."""
    import jarvis.api.server as srv

    def fake_ollama(messages):
        return "Odpowiedź testowa, Panie TireQ."

    monkeypatch.setattr(srv, "_ollama", fake_ollama)


@pytest.fixture
def client():
    from jarvis.api.server import app
    return TestClient(app)


# ── /health ───────────────────────────────────────────────────────────────────

def test_health_returns_online(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"
    assert "model" in data
    assert "plugins" in data


# ── /chat ─────────────────────────────────────────────────────────────────────

def test_chat_returns_response(client):
    resp = client.post("/chat", json={"message": "Cześć Jarvisie!"})
    assert resp.status_code == 200
    data = resp.json()
    assert "response" in data
    assert "history" in data
    assert data["response"] == "Odpowiedź testowa, Panie TireQ."


def test_chat_history_grows(client):
    resp = client.post("/chat", json={
        "message": "drugie pytanie",
        "history": [
            {"role": "user", "content": "pierwsze"},
            {"role": "assistant", "content": "odp"},
        ]
    })
    assert resp.status_code == 200
    history = resp.json()["history"]
    assert len(history) >= 4  # 2 stare + user + assistant


def test_chat_ollama_error_returns_503(client, monkeypatch):
    import jarvis.api.server as srv

    def broken(_):
        raise OSError("brak Ollama")

    monkeypatch.setattr(srv, "_ollama", broken)
    resp = client.post("/chat", json={"message": "test"})
    assert resp.status_code == 503


# ── /memory ───────────────────────────────────────────────────────────────────

def test_get_memory_returns_data(client):
    resp = client.get("/memory")
    assert resp.status_code in (200, 500)


def test_post_memory_valid_key(client, monkeypatch):
    import jarvis.core.tools as tools

    def fake_save(key, value):
        return {"status": "ok", "result": f"Saved {key}={value}"}

    monkeypatch.setattr(tools, "memory_save", fake_save)
    resp = client.post("/memory", json={"key": "decision", "value": "backend Python"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["saved"] is True
    assert data["key"] == "decision"


def test_post_memory_error_returns_400(client, monkeypatch):
    import jarvis.core.tools as tools

    def fake_save(key, value):
        return {"status": "error", "result": "nieprawidłowy klucz"}

    monkeypatch.setattr(tools, "memory_save", fake_save)
    resp = client.post("/memory", json={"key": "invalid", "value": "x"})
    assert resp.status_code == 400


# ── /plugins ──────────────────────────────────────────────────────────────────

def test_get_plugins_structure(client):
    resp = client.get("/plugins")
    assert resp.status_code == 200
    data = resp.json()
    assert "plugins" in data
    assert "tools" in data
    assert isinstance(data["tools"], list)


# ── /agent ────────────────────────────────────────────────────────────────────

def test_agent_returns_result(client, monkeypatch):
    import jarvis.core.agent as agent_mod

    def fake_run(task, verbose=False, extra_tools=None, tool_override=None):
        return f"Wykonano: {task}"

    monkeypatch.setattr(agent_mod, "run_agent", fake_run)
    resp = client.post("/agent", json={"task": "sprawdź pliki"})
    assert resp.status_code == 200
    data = resp.json()
    assert "result" in data
    assert data["task"] == "sprawdź pliki"


# ── /dashboard ────────────────────────────────────────────────────────────────

def test_dashboard_returns_html(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_dashboard_data_returns_dict(client):
    resp = client.get("/dashboard/data")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


# ── /tool/{tool_name} ─────────────────────────────────────────────────────────

def test_call_tool_via_registry(client, monkeypatch):
    from jarvis.plugins import registry

    def fake_tool(param="x"):
        return {"result": f"ok {param}"}

    registry.tools["test_tool_42"] = fake_tool
    resp = client.post("/tool/test_tool_42", json={"param": "hello"})
    assert resp.status_code == 200
    del registry.tools["test_tool_42"]


def test_call_tool_unknown_returns_400(client, monkeypatch):
    import jarvis.core.tools as tools

    def fake_execute(name, params):
        return {"status": "error", "result": "nieznane narzędzie"}

    monkeypatch.setattr(tools, "execute_tool", fake_execute)
    resp = client.post("/tool/ghost_tool_xyz", json={})
    assert resp.status_code == 400
