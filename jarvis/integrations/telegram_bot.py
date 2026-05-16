#!/usr/bin/env python3
"""
J.A.R.V.I.S. Telegram Bot — zdalny dostęp z telefonu.
Piszesz do Jarvisa na Telegramie → odpowiada z Legiona.

Zero zewnętrznych zależności — czysty urllib + long polling.

KONFIGURACJA (jednorazowa):
  1. Napisz do @BotFather na Telegramie → /newbot → otrzymasz token
  2. Ustaw zmienne środowiskowe:
       set TELEGRAM_BOT_TOKEN=123456:ABC...        (Windows)
       export TELEGRAM_BOT_TOKEN=123456:ABC...     (Linux)
  3. (Opcjonalnie) ogranicz dostęp do swojego konta:
       set TELEGRAM_ALLOWED_USER=<twoje_chat_id>
       (chat_id pokaże się przy pierwszej wiadomości w logu)

URUCHOMIENIE:
  jarvis telegram
  python -m jarvis.integrations.telegram_bot

KOMENDY W BOCIE:
  /start          — powitanie
  /briefing       — poranny briefing
  /status         — status systemu
  /agent <opis>   — Agent Mode
  /memory         — pokaż pamięć
  /pamiec <tekst> — zapisz notatkę
  (zwykły tekst)  — rozmowa z Jarvisem
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USER = os.environ.get("TELEGRAM_ALLOWED_USER", "")
API = f"https://api.telegram.org/bot{TOKEN}"
OLLAMA_URL = "http://localhost:11434/api/chat"

SYSTEM = (
    "Jesteś J.A.R.V.I.S. — osobisty asystent AI Marcela (TireQ). "
    "Odpowiadasz po polsku, elegancko, zwięźle. Zwracasz się 'Panie TireQ'. "
    "Odpowiedzi na Telegramie krótkie — max 4-5 zdań, bez długich bloków kodu."
)

# Historia rozmowy per chat_id (pamięć krótkoterminowa)
_histories: dict[int, list] = {}


def _api(method: str, **params) -> dict:
    url = f"{API}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=70) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_message(chat_id: int, text: str) -> None:
    # Telegram limit 4096 znaków — dziel długie odpowiedzi
    for i in range(0, len(text), 4000):
        _api("sendMessage", chat_id=chat_id, text=text[i:i + 4000])


def send_typing(chat_id: int) -> None:
    _api("sendChatAction", chat_id=chat_id, action="typing")


def ollama_chat(chat_id: int, message: str) -> str:
    history = _histories.setdefault(chat_id, [])
    history.append({"role": "user", "content": message})
    history[:] = history[-12:]  # ostatnie 6 wymian

    payload = json.dumps({
        "model": "jarvis",
        "messages": [{"role": "system", "content": SYSTEM}] + history,
        "stream": False,
        "options": {"temperature": 0.7}
    }).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            answer = json.loads(resp.read())["message"]["content"]
        history.append({"role": "assistant", "content": answer})
        return answer
    except Exception as e:
        return f"Przepraszam, Panie TireQ — Ollama niedostępna na Legionie. ({e})"


# ── Handlery komend ───────────────────────────────────────────────────────────

def handle_command(chat_id: int, text: str) -> bool:
    """Zwraca True jeśli to była komenda (obsłużona)."""
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "/start":
        send_message(chat_id,
            "Systemy aktywne, Panie TireQ.\n\n"
            "Dostępne komendy:\n"
            "/briefing — poranny briefing\n"
            "/status — status systemu\n"
            "/agent <opis> — Agent Mode\n"
            "/memory — pokaż pamięć\n"
            "/pamiec <tekst> — zapisz notatkę\n\n"
            "Lub po prostu napisz — odpowiem."
        )
        return True

    if cmd == "/briefing":
        send_typing(chat_id)
        try:
            from jarvis.plugins.tireq_plugin import tireq_briefing
            send_message(chat_id, tireq_briefing()["result"])
        except Exception as e:
            send_message(chat_id, f"Błąd briefingu: {e}")
        return True

    if cmd == "/status":
        send_typing(chat_id)
        try:
            import subprocess
            out = subprocess.run(
                [sys.executable, "-m", "jarvis.cli", "status"],
                cwd=ROOT, capture_output=True, text=True, timeout=30
            ).stdout
            send_message(chat_id, out or "Status niedostępny.")
        except Exception as e:
            send_message(chat_id, f"Błąd: {e}")
        return True

    if cmd == "/agent":
        if not arg:
            send_message(chat_id, "Podaj zadanie: /agent napraw bug w X")
            return True
        send_typing(chat_id)
        try:
            from jarvis.core.agent import run_agent
            result = run_agent(arg, verbose=False)
            send_message(chat_id, f"Agent zakończył:\n{result}")
        except Exception as e:
            send_message(chat_id, f"Błąd agenta: {e}")
        return True

    if cmd == "/memory":
        send_typing(chat_id)
        try:
            from jarvis.core.tools import memory_read
            m = memory_read()["result"]
            prefs = "\n".join(f"• {p}" for p in m.get("preferences", []))
            decs = "\n".join(f"• {d}" for d in m.get("recent_decisions", []))
            send_message(chat_id,
                f"PAMIĘĆ JARVISA\n\nPreferencje:\n{prefs or 'brak'}\n\n"
                f"Ostatnie decyzje:\n{decs or 'brak'}")
        except Exception as e:
            send_message(chat_id, f"Błąd: {e}")
        return True

    if cmd in ("/pamiec", "/pamięć"):
        if not arg:
            send_message(chat_id, "Podaj treść: /pamiec deadline projektu X to 1 czerwca")
            return True
        try:
            sys.path.insert(0, str(ROOT / "scripts"))
            import memory_update as mu
            mu.add_note(arg)
            send_message(chat_id, f"Zapisano w pamięci, Panie TireQ:\n„{arg}\"")
        except Exception as e:
            send_message(chat_id, f"Błąd zapisu: {e}")
        return True

    return False


# ── Pętla główna ──────────────────────────────────────────────────────────────

def process_update(update: dict) -> None:
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()
    if not text:
        return

    # Autoryzacja — tylko właściciel
    if ALLOWED_USER and str(chat_id) != str(ALLOWED_USER):
        send_message(chat_id, "Dostęp ograniczony. To prywatny asystent.")
        print(f"[Telegram] Odrzucono nieautoryzowany chat_id: {chat_id}")
        return

    print(f"[Telegram] chat_id={chat_id}: {text[:60]}")

    if handle_command(chat_id, text):
        return

    send_typing(chat_id)
    answer = ollama_chat(chat_id, text)
    send_message(chat_id, answer)


def run() -> None:
    if not TOKEN:
        print("[BŁĄD] Brak TELEGRAM_BOT_TOKEN.")
        print("  1. Napisz do @BotFather → /newbot → skopiuj token")
        print("  2. set TELEGRAM_BOT_TOKEN=<token>  (Windows)")
        print("     export TELEGRAM_BOT_TOKEN=<token>  (Linux)")
        sys.exit(1)

    me = _api("getMe")
    if not me.get("ok"):
        print(f"[BŁĄD] Token nieprawidłowy lub brak sieci: {me}")
        sys.exit(1)

    bot_name = me["result"]["username"]
    print(f"\n  J.A.R.V.I.S. Telegram Bot — @{bot_name}")
    print(f"  Autoryzacja: {'tylko user ' + ALLOWED_USER if ALLOWED_USER else 'OTWARTA (ustaw TELEGRAM_ALLOWED_USER)'}")
    print(f"  Napisz do bota na telefonie. Ctrl+C aby zatrzymać.\n")

    offset = 0
    while True:
        try:
            resp = _api("getUpdates", offset=offset, timeout=60)
            if not resp.get("ok"):
                time.sleep(5)
                continue
            for update in resp.get("result", []):
                offset = update["update_id"] + 1
                try:
                    process_update(update)
                except Exception as e:
                    print(f"[Telegram] Błąd przetwarzania: {e}")
        except KeyboardInterrupt:
            print("\n[JARVIS] Telegram Bot zatrzymany.")
            break
        except Exception as e:
            print(f"[Telegram] Błąd pętli: {e}")
            time.sleep(5)


if __name__ == "__main__":
    run()
