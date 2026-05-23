#!/usr/bin/env python3
"""
J.A.R.V.I.S. Desktop GUI — graficzny interfejs do rozmów z Jarvisem.

Wymagania:
  pip install customtkinter

Opcjonalnie (tryb głosowy):
  pip install sounddevice faster-whisper numpy

Użycie:
  python training/jarvis_gui.py
  python training/jarvis_gui.py --host http://192.168.1.10:11434
"""

import argparse
import json
import queue
import sys
import threading
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
MEMORY_DIR = ROOT / "memory"
MODEL = "jarvis"
DEFAULT_HOST = "http://localhost:11434"

try:
    import customtkinter as ctk
except ImportError:
    print("[BŁĄD] Zainstaluj: pip install customtkinter")
    sys.exit(1)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

JARVIS_SYSTEM = (
    "Jesteś J.A.R.V.I.S. (Just A Rather Very Intelligent System) — "
    "osobisty asystent AI Marcela (TireQ). Działasz lokalnie na jego laptopie. "
    "Odpowiadasz po polsku, elegancko i precyzyjnie. Zwracasz się 'Panie TireQ'. "
    "Nigdy nie mówisz 'nie mogę' bez alternatywy. "
    "Doza suchego brytyjskiego humoru gdy stosowne."
)


# ── Funkcje pomocnicze ────────────────────────────────────────────────────────

def _load_memory_context() -> str:
    """Kontekst do system promptu."""
    lines = []
    decisions_file = MEMORY_DIR / "decisions.json"
    if decisions_file.exists():
        try:
            decisions = json.loads(decisions_file.read_text(encoding="utf-8"))["decisions"]
            if decisions:
                lines.append("Twoje ostatnie decyzje techniczne:")
                for d in decisions[-5:]:
                    lines.append(f"  - {d['decision']}")
        except Exception:
            pass
    profile_file = MEMORY_DIR / "profile.json"
    if profile_file.exists():
        try:
            profile = json.loads(profile_file.read_text(encoding="utf-8"))
            prefs = profile.get("patterns", {}).get("preferred_solutions", [])
            if prefs:
                lines.append(f"Twoje preferencje: {', '.join(prefs[:5])}")
        except Exception:
            pass
    return "\n".join(lines) if lines else ""


def _load_memory_display() -> dict:
    """Dane pamięci do wyświetlenia w sidebarze."""
    result = {"decisions": [], "preferences": [], "notes": []}
    decisions_file = MEMORY_DIR / "decisions.json"
    if decisions_file.exists():
        try:
            decisions = json.loads(decisions_file.read_text(encoding="utf-8"))["decisions"]
            result["decisions"] = [d["decision"] for d in decisions[-6:]]
        except Exception:
            pass
    profile_file = MEMORY_DIR / "profile.json"
    if profile_file.exists():
        try:
            profile = json.loads(profile_file.read_text(encoding="utf-8"))
            result["preferences"] = profile.get("patterns", {}).get("preferred_solutions", [])[:6]
            notes = profile.get("notes", [])
            result["notes"] = [
                (n.get("note", "") if isinstance(n, dict) else str(n))
                for n in notes[-4:]
            ]
        except Exception:
            pass
    return result


def _load_sessions() -> list[dict]:
    """Lista sesji z memory/sessions/."""
    sessions_dir = MEMORY_DIR / "sessions"
    if not sessions_dir.exists():
        return []
    sessions = []
    for f in sorted(sessions_dir.glob("*.json"), reverse=True)[:12]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            sessions.append({
                "date": data.get("date", "")[:10],
                "summary": data.get("summary", "Sesja")[:55],
            })
        except Exception:
            pass
    return sessions


def _check_ollama(host: str) -> bool:
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


# ── Główna aplikacja ──────────────────────────────────────────────────────────

class JarvisGUI(ctk.CTk):
    def __init__(self, host: str = DEFAULT_HOST):
        super().__init__()
        self.host = host
        self.title("J.A.R.V.I.S. — Osobisty Asystent AI")
        self.geometry("1200x760")
        self.minsize(900, 600)

        self._history: list[dict] = []
        self._token_queue: queue.Queue = queue.Queue()
        self._streaming = False
        self._recording = False
        self._response_buf: list[str] = []
        self._saved_len = 0  # liczba wiadomości w ostatnio zapisanej sesji

        mem_ctx = _load_memory_context()
        self._system_msg = {
            "role": "system",
            "content": JARVIS_SYSTEM + (f"\n\n{mem_ctx}" if mem_ctx else ""),
        }

        self._build_ui()
        self._refresh_memory()
        self._refresh_sessions()
        self.after(400, self._check_connection)
        self._poll_queue()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self._sidebar = ctk.CTkFrame(self, width=255, corner_radius=0)
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_propagate(False)
        self._sidebar.grid_rowconfigure(3, weight=1)
        self._build_sidebar()

        # Panel czatu
        self._chat_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self._chat_frame.grid(row=0, column=1, sticky="nsew", padx=(2, 0))
        self._chat_frame.grid_rowconfigure(0, weight=1)
        self._chat_frame.grid_columnconfigure(0, weight=1)
        self._build_chat_panel()

    def _build_sidebar(self):
        ctk.CTkLabel(
            self._sidebar, text="⚙  J.A.R.V.I.S.",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, pady=(16, 4), padx=14, sticky="w")

        self._status_lbl = ctk.CTkLabel(
            self._sidebar, text="● Łączę z Ollama...",
            font=ctk.CTkFont(size=11), text_color="gray",
        )
        self._status_lbl.grid(row=1, column=0, padx=14, pady=(0, 10), sticky="w")

        ctk.CTkLabel(
            self._sidebar, text="PAMIĘĆ",
            font=ctk.CTkFont(size=10, weight="bold"), text_color="gray",
        ).grid(row=2, column=0, padx=14, pady=(4, 2), sticky="w")

        self._memory_box = ctk.CTkTextbox(
            self._sidebar, width=235, height=260,
            font=ctk.CTkFont(size=11), wrap="word", state="disabled",
        )
        self._memory_box.grid(row=3, column=0, padx=10, pady=(0, 4), sticky="nsew")

        ctk.CTkButton(
            self._sidebar, text="⟳  Odśwież pamięć",
            width=235, height=26, font=ctk.CTkFont(size=11),
            command=self._refresh_memory,
            fg_color="transparent", border_width=1,
        ).grid(row=4, column=0, padx=10, pady=(0, 10))

        ctk.CTkLabel(
            self._sidebar, text="HISTORIA SESJI",
            font=ctk.CTkFont(size=10, weight="bold"), text_color="gray",
        ).grid(row=5, column=0, padx=14, pady=(4, 2), sticky="w")

        self._sessions_box = ctk.CTkScrollableFrame(
            self._sidebar, width=235, height=160, fg_color="transparent",
        )
        self._sessions_box.grid(row=6, column=0, padx=10, pady=(0, 10), sticky="ew")

    def _build_chat_panel(self):
        # Obszar wiadomości
        self._chat_box = ctk.CTkTextbox(
            self._chat_frame,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            wrap="word", state="disabled", corner_radius=8,
        )
        self._chat_box.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 5))

        # Tagi kolorów (przez wewnętrzny widget)
        tb = self._chat_box._textbox
        tb.tag_config("user",   foreground="#5ba3f5")
        tb.tag_config("jarvis", foreground="#6abf6a")
        tb.tag_config("system", foreground="#777777")
        tb.tag_config("time",   foreground="#555555")

        # Wiersz input
        inp = ctk.CTkFrame(self._chat_frame, fg_color="transparent")
        inp.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 4))
        inp.grid_columnconfigure(1, weight=1)

        self._voice_btn = ctk.CTkButton(
            inp, text="🎤", width=44, height=44,
            font=ctk.CTkFont(size=18),
            command=self._toggle_voice,
            fg_color="#1f5a8a", hover_color="#cc3333",
        )
        self._voice_btn.grid(row=0, column=0, padx=(0, 6))

        self._input_box = ctk.CTkTextbox(
            inp, height=44, font=ctk.CTkFont(size=13), corner_radius=8,
        )
        self._input_box.grid(row=0, column=1, sticky="ew")
        self._input_box.bind("<Return>", self._on_enter)

        self._send_btn = ctk.CTkButton(
            inp, text="▶  Wyślij", width=100, height=44,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._send_message,
        )
        self._send_btn.grid(row=0, column=2, padx=(6, 0))

        # Dolny pasek
        bot = ctk.CTkFrame(self._chat_frame, fg_color="transparent")
        bot.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

        ctk.CTkButton(
            bot, text="🗑  Wyczyść", width=130, height=28,
            font=ctk.CTkFont(size=11),
            command=self._clear_chat,
            fg_color="transparent", border_width=1,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            bot, text="💾  Zapisz sesję", width=140, height=28,
            font=ctk.CTkFont(size=11),
            command=self._save_session,
            fg_color="transparent", border_width=1,
        ).pack(side="left")

        self._voice_lbl = ctk.CTkLabel(
            bot, text="", font=ctk.CTkFont(size=11), text_color="#ff9944",
        )
        self._voice_lbl.pack(side="right")

        self._append_system(
            "Dzień dobry, Panie TireQ. J.A.R.V.I.S. gotowy do pracy."
        )

    # ── Wyświetlanie wiadomości ───────────────────────────────────────────────

    def _write(self, text: str, tag: str):
        tb = self._chat_box._textbox
        self._chat_box.configure(state="normal")
        tb.insert("end", text, (tag,))
        self._chat_box.configure(state="disabled")
        self._chat_box.see("end")

    def _append_msg(self, role: str, text: str):
        now = datetime.now().strftime("%H:%M")
        if role == "user":
            self._write(f"\n[{now}] Ty:\n", "time")
            self._write(f"{text}\n", "user")
        elif role == "jarvis":
            self._write(f"\n[{now}] JARVIS:\n", "time")
            self._write(f"{text}\n", "jarvis")

    def _append_system(self, text: str):
        self._write(f"\n  ⚙ {text}\n", "system")

    def _start_jarvis_msg(self):
        now = datetime.now().strftime("%H:%M")
        self._write(f"\n[{now}] JARVIS:\n", "time")
        self._response_buf = []

    def _append_token(self, token: str):
        self._write(token, "jarvis")
        self._response_buf.append(token)

    def _finalize_jarvis_msg(self):
        self._write("\n", "jarvis")
        full = "".join(self._response_buf)
        if full.strip():
            self._history.append({"role": "assistant", "content": full})
        self._response_buf = []

    # ── Wysyłanie ─────────────────────────────────────────────────────────────

    def _on_enter(self, event):
        if event.state & 0x1:  # Shift+Enter → nowa linia
            return
        self._send_message()
        return "break"

    def _send_message(self):
        if self._streaming:
            return
        text = self._input_box.get("1.0", "end").strip()
        if not text:
            return
        self._input_box.delete("1.0", "end")
        self._history.append({"role": "user", "content": text})
        self._append_msg("user", text)
        self._send_btn.configure(state="disabled", text="⟳  Myślę...")
        self._streaming = True
        self._start_jarvis_msg()
        threading.Thread(target=self._stream_response, daemon=True).start()

    def _stream_response(self):
        messages = [self._system_msg] + self._history
        payload = json.dumps({
            "model": MODEL,
            "messages": messages,
            "stream": True,
            "options": {"temperature": 0.4, "top_p": 0.85},
        }).encode()
        req = urllib.request.Request(
            f"{self.host}/api/chat", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                for line in resp:
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        self._token_queue.put(("token", token))
                    if chunk.get("done"):
                        break
        except urllib.error.URLError as e:
            self._token_queue.put(("error", str(e.reason)))
        except Exception as e:
            self._token_queue.put(("error", str(e)))
        self._token_queue.put(("done", None))

    def _poll_queue(self):
        try:
            while True:
                kind, data = self._token_queue.get_nowait()
                if kind == "token":
                    self._append_token(data)
                elif kind == "error":
                    self._append_system(f"Błąd: {data}")
                    self._finalize_jarvis_msg()
                    self._streaming = False
                    self._send_btn.configure(state="normal", text="▶  Wyślij")
                elif kind == "done":
                    self._finalize_jarvis_msg()
                    self._streaming = False
                    self._send_btn.configure(state="normal", text="▶  Wyślij")
        except queue.Empty:
            pass
        self.after(40, self._poll_queue)

    # ── Tryb głosowy ──────────────────────────────────────────────────────────

    def _toggle_voice(self):
        if self._recording or self._streaming:
            return
        self._recording = True
        self._voice_btn.configure(fg_color="#cc3333", text="⏹")
        self._voice_lbl.configure(text="🎤 Nagrywam 5s...")
        threading.Thread(target=self._record_and_transcribe, daemon=True).start()

    def _record_and_transcribe(self):
        try:
            import sounddevice as sd
            import numpy as np
            import wave
            import tempfile
            import os

            sample_rate = 16000
            audio = sd.rec(5 * sample_rate, samplerate=sample_rate,
                           channels=1, dtype="int16")
            sd.wait()

            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            with wave.open(tmp.name, "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio.tobytes())

            self.after(0, lambda: self._voice_lbl.configure(text="⟳ Transkrybuję..."))

            from faster_whisper import WhisperModel
            wm = WhisperModel("base", device="cuda", compute_type="float16")
            segments, _ = wm.transcribe(tmp.name, language="pl")
            text = " ".join(s.text for s in segments).strip()
            os.unlink(tmp.name)

            if text:
                self.after(0, lambda t=text: self._insert_voice(t))
            else:
                self.after(0, lambda: self._voice_lbl.configure(text="Nie wykryto mowy"))

        except ImportError as e:
            pkg = "sounddevice" if "sounddevice" in str(e) else "faster-whisper"
            self.after(0, lambda p=pkg: self._voice_lbl.configure(
                text=f"Brak: pip install {p}"))
        except Exception as e:
            self.after(0, lambda err=str(e): self._voice_lbl.configure(
                text=f"Błąd głosu: {err[:40]}"))
        finally:
            self._recording = False
            self.after(0, lambda: self._voice_btn.configure(
                fg_color="#1f5a8a", text="🎤"))
            self.after(3000, lambda: self._voice_lbl.configure(text=""))

    def _insert_voice(self, text: str):
        self._input_box.delete("1.0", "end")
        self._input_box.insert("1.0", text)
        self._input_box.focus()

    # ── Pamięć i sesje ────────────────────────────────────────────────────────

    def _refresh_memory(self):
        data = _load_memory_display()
        self._memory_box.configure(state="normal")
        self._memory_box.delete("1.0", "end")

        if data["decisions"]:
            self._memory_box.insert("end", "📋 Decyzje techniczne:\n")
            for d in data["decisions"]:
                self._memory_box.insert("end", f"  • {d[:46]}\n")
            self._memory_box.insert("end", "\n")

        if data["preferences"]:
            self._memory_box.insert("end", "⭐ Preferencje:\n")
            for p in data["preferences"]:
                self._memory_box.insert("end", f"  • {p[:46]}\n")
            self._memory_box.insert("end", "\n")

        if data["notes"]:
            self._memory_box.insert("end", "📝 Notatki:\n")
            for n in data["notes"]:
                self._memory_box.insert("end", f"  • {n[:46]}\n")

        if not any(data.values()):
            self._memory_box.insert("end", "  (pusta pamięć)\n")

        self._memory_box.configure(state="disabled")

    def _refresh_sessions(self):
        for w in self._sessions_box.winfo_children():
            w.destroy()
        sessions = _load_sessions()
        if not sessions:
            ctk.CTkLabel(
                self._sessions_box, text="Brak zapisanych sesji",
                font=ctk.CTkFont(size=10), text_color="gray",
            ).pack(anchor="w", padx=4, pady=2)
            return
        for s in sessions:
            ctk.CTkLabel(
                self._sessions_box,
                text=f"[{s['date']}] {s['summary']}",
                font=ctk.CTkFont(size=10), anchor="w", wraplength=215,
            ).pack(fill="x", padx=4, pady=1)

    def _write_session_file(self) -> str | None:
        """Zapisuje bieżącą rozmowę do memory/sessions/. Zwraca nazwę pliku lub None."""
        if len(self._history) < 2:
            return None
        sessions_dir = MEMORY_DIR / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        turns = sum(1 for m in self._history if m["role"] == "user")
        topics = ", ".join(
            m["content"][:40] for m in self._history if m["role"] == "user"
        )[:200]
        data = {
            "date": datetime.now().isoformat(timespec="seconds"),
            "summary": f"Sesja GUI ({turns} pytań). Tematy: {topics}",
            "source": "jarvis_gui",
            "turns": turns,
        }
        f = sessions_dir / f"{date_str}.json"
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._saved_len = len(self._history)
        return f.name

    def _save_session(self):
        name = self._write_session_file()
        if name is None:
            self._append_system("Za krótka rozmowa — nic do zapisania.")
            return
        self._append_system(f"Sesja zapisana → {name}")
        self._refresh_sessions()

    def _on_close(self):
        """Auto-zapis sesji przy zamknięciu okna (jeśli są nowe wiadomości)."""
        if len(self._history) >= 2 and len(self._history) > self._saved_len:
            self._write_session_file()
        self.destroy()

    def _clear_chat(self):
        self._history = []
        self._saved_len = 0
        self._chat_box.configure(state="normal")
        self._chat_box._textbox.delete("1.0", "end")
        self._chat_box.configure(state="disabled")
        self._append_system("Rozmowa wyczyszczona. Pamięć modelu zresetowana.")

    # ── Połączenie ────────────────────────────────────────────────────────────

    def _check_connection(self):
        if _check_ollama(self.host):
            self._status_lbl.configure(
                text=f"● Połączono  ({MODEL})", text_color="#6abf6a")
        else:
            self._status_lbl.configure(
                text="✗ Ollama niedostępna", text_color="#cc4444")
            self._append_system(
                f"Brak Ollama na {self.host}. Uruchom: ollama serve")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Desktop GUI")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="Adres serwera Ollama (domyślnie: localhost:11434)")
    args = parser.parse_args()
    app = JarvisGUI(host=args.host)
    app.mainloop()


if __name__ == "__main__":
    main()
