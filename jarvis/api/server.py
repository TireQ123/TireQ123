#!/usr/bin/env python3
"""
J.A.R.V.I.S. API — serwer FastAPI.
Udostępnia Jarvisa jako HTTP endpoints.

Uruchomienie:
  pip install fastapi uvicorn
  python jarvis/api/server.py
  # lub:
  uvicorn jarvis.api.server:app --host 0.0.0.0 --port 8000 --reload

Endpoints:
  POST /chat          — rozmowa z Jarvisem
  POST /agent         — zadanie dla Agent Mode
  GET  /memory        — odczyt pamięci
  POST /memory        — zapis do pamięci
  GET  /plugins       — lista załadowanych pluginów
  GET  /health        — status serwera
  WS   /ws/chat       — streaming przez WebSocket
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("[BŁĄD] pip install fastapi uvicorn")
    sys.exit(1)

from jarvis.core.tools import memory_read, memory_save, execute_tool
from jarvis.core.agent import run_agent
from jarvis.plugins import registry

# ── Startup ───────────────────────────────────────────────────────────────────

registry.load_all()

app = FastAPI(
    title="J.A.R.V.I.S. API",
    description="Osobisty asystent AI Marcela (TireQ)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Modele danych ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []

class AgentRequest(BaseModel):
    task: str
    verbose: bool = False

class MemoryWrite(BaseModel):
    key: str   # decision | preference | note
    value: str

# ── Ollama helper ─────────────────────────────────────────────────────────────

import urllib.request

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "jarvis"

SYSTEM = (
    "Jesteś J.A.R.V.I.S. — osobisty asystent AI Marcela (TireQ). "
    "Odpowiadasz po polsku, elegancko. Zwracasz się 'Panie TireQ'."
)


def _ollama(messages: list[dict]) -> str:
    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYSTEM}] + messages,
        "stream": False
    }).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())["message"]["content"]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "online",
        "model": MODEL,
        "plugins": registry.list_plugins()
    }


@app.post("/chat")
def chat(req: ChatRequest):
    history = req.history + [{"role": "user", "content": req.message}]
    try:
        response = _ollama(history)
        return {
            "response": response,
            "history": history + [{"role": "assistant", "content": response}]
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ollama niedostępna: {e}")


@app.post("/agent")
def agent(req: AgentRequest):
    result = run_agent(
        req.task,
        verbose=req.verbose,
        extra_tools=registry.schemas,
        tool_override=registry.tools
    )
    return {"result": result, "task": req.task}


@app.get("/memory")
def get_memory():
    result = memory_read()
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["result"])
    return result["result"]


@app.post("/memory")
def post_memory(req: MemoryWrite):
    result = memory_save(req.key, req.value)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["result"])
    return {"saved": True, "key": req.key, "value": req.value}


@app.get("/plugins")
def get_plugins():
    return {
        "plugins": registry.list_plugins(),
        "tools": [s["name"] for s in registry.schemas]
    }


@app.post("/tool/{tool_name}")
def call_tool(tool_name: str, params: dict = {}):
    fn = registry.tools.get(tool_name)
    if fn:
        return fn(**params)
    result = execute_tool(tool_name, params)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["result"])
    return result


# ── WebSocket streaming ───────────────────────────────────────────────────────

@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    history = []
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            history.append({"role": "user", "content": msg.get("message", "")})

            import asyncio
            response = await asyncio.to_thread(_ollama, history)
            history.append({"role": "assistant", "content": response})
            await websocket.send_text(json.dumps({"response": response}))
    except WebSocketDisconnect:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n  J.A.R.V.I.S. API — uruchomiony")
    print("  Docs: http://localhost:8000/docs")
    print("  Health: http://localhost:8000/health\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
