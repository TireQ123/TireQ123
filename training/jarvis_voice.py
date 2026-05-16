#!/usr/bin/env python3
"""
J.A.R.V.I.S. Voice — interfejs głosowy lokalny
Mikrofon → Whisper (STT) → Ollama (LLM) → edge-tts (TTS) → głośnik

Wszystko lokalnie na RTX 5060 — Whisper używa GPU.
TTS: głos Microsoft Neural przez edge-tts (wymaga połączenia dla TTS,
     ale Whisper i LLM są w pełni offline).

Użycie:
  pip install -r training/requirements_voice.txt
  python training/jarvis_voice.py
  python training/jarvis_voice.py --text-only   # bez TTS, tylko tekst
  python training/jarvis_voice.py --offline-tts # pyttsx3 zamiast edge-tts
"""

import argparse
import asyncio
import json
import os
import tempfile
import threading
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
MEMORY_DIR = ROOT / "memory"
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "jarvis"

# Głos Jarvisa — angielski brzmi jak film, polskie Neural też dostępne
VOICE_EN = "en-GB-RyanNeural"      # brytyjski angielski — jak filmowy Jarvis
VOICE_PL = "pl-PL-MarekNeural"     # polski Neural

SYSTEM_PROMPT = (
    "Jesteś J.A.R.V.I.S. — osobisty asystent AI Marcela (TireQ). "
    "Odpowiadasz po polsku, elegancko. Zwracasz się 'Panie TireQ'. "
    "Odpowiedzi głosowe: krótsze niż tekstowe — max 3-4 zdania, "
    "bez list i kodu. Mów jak asystent, nie jak dokumentacja."
)

SEPARATOR = "=" * 52


def load_memory_context() -> str:
    lines = []
    decisions_file = MEMORY_DIR / "decisions.json"
    if decisions_file.exists():
        decisions = json.loads(decisions_file.read_text())["decisions"]
        if decisions:
            lines.append("Twoje ostatnie decyzje techniczne:")
            for d in decisions[-5:]:
                lines.append(f"  - {d['decision']}")
    profile_file = MEMORY_DIR / "profile.json"
    if profile_file.exists():
        profile = json.loads(profile_file.read_text())
        prefs = profile.get("patterns", {}).get("preferred_solutions", [])
        if prefs:
            lines.append(f"Twoje preferencje: {', '.join(prefs[:4])}")
    return "\n".join(lines)


def transcribe(audio_path: str, model_size: str = "base") -> str:
    """Transkrypcja audio przez Whisper na GPU."""
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cuda", compute_type="float16")
    segments, _ = model.transcribe(audio_path, language="pl")
    return " ".join(s.text for s in segments).strip()


def record_audio(duration: int = 5, sample_rate: int = 16000) -> str:
    """Nagrywa audio z mikrofonu, zwraca ścieżkę do pliku WAV."""
    import sounddevice as sd
    import numpy as np
    import wave

    print(f"  [🎤 Nagrywam {duration}s... mów teraz]")
    audio = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="int16"
    )
    sd.wait()

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    return tmp.name


async def speak_edge(text: str, voice: str = VOICE_PL) -> None:
    """TTS przez edge-tts (Microsoft Neural voices)."""
    import edge_tts
    import pygame

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(tmp.name)

    pygame.mixer.init()
    pygame.mixer.music.load(tmp.name)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        await asyncio.sleep(0.1)
    pygame.mixer.quit()
    os.unlink(tmp.name)


def speak_offline(text: str) -> None:
    """TTS przez pyttsx3 (offline, gorsza jakość)."""
    import pyttsx3
    engine = pyttsx3.init()
    engine.setProperty("rate", 175)
    voices = engine.getProperty("voices")
    for v in voices:
        if "polish" in v.name.lower() or "pl" in v.id.lower():
            engine.setProperty("voice", v.id)
            break
    engine.say(text)
    engine.runAndWait()


def ollama_chat(messages: list[dict]) -> str:
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 300}
    }).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())["message"]["content"]
    except Exception as e:
        return f"Przepraszam, Panie TireQ — błąd połączenia z modelem: {e}"


def run(text_only: bool = False, offline_tts: bool = False,
        voice_lang: str = "pl", record_seconds: int = 5) -> None:

    memory = load_memory_context()
    system = SYSTEM_PROMPT + (f"\n\n{memory}" if memory else "")
    history = [{"role": "system", "content": system}]
    voice = VOICE_PL if voice_lang == "pl" else VOICE_EN

    print(f"\n{SEPARATOR}")
    print("  J.A.R.V.I.S. — Interfejs głosowy")
    print(f"  STT: Whisper (GPU)  |  TTS: {'offline' if offline_tts else 'Neural'}")
    print(f"  Pamięć: {'załadowana' if memory else 'pusta'}")
    print(f"{SEPARATOR}")
    if text_only:
        print("  Tryb tekstowy — wpisz pytanie, naciśnij Enter")
    else:
        print("  Naciśnij Enter → nagrywanie → mów → odpowiedź")
    print(f"  Wpisz 'exit' aby zakończyć")
    print(f"{SEPARATOR}\n")

    while True:
        try:
            if text_only:
                user_text = input("Ty: ").strip()
            else:
                input("  [Enter = zacznij nagrywanie]")
                audio_path = record_audio(duration=record_seconds)
                print("  [Transkrybuję...]")
                user_text = transcribe(audio_path)
                os.unlink(audio_path)
                if not user_text:
                    print("  [Nie wykryto mowy — spróbuj ponownie]\n")
                    continue
                print(f"Ty: {user_text}")

        except (KeyboardInterrupt, EOFError):
            print(f"\n\n[JARVIS] Do zobaczenia, Panie TireQ.")
            break

        if user_text.lower() in ("exit", "quit", "/bye", "koniec"):
            print("[JARVIS] Do zobaczenia, Panie TireQ.")
            break

        history.append({"role": "user", "content": user_text})
        print("JARVIS: ", end="", flush=True)

        response = ollama_chat(history)
        print(response)
        print()

        history.append({"role": "assistant", "content": response})

        if not text_only:
            if offline_tts:
                speak_offline(response)
            else:
                asyncio.run(speak_edge(response, voice=voice))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Voice")
    parser.add_argument("--text-only", action="store_true", help="Bez mikrofonu i TTS")
    parser.add_argument("--offline-tts", action="store_true", help="TTS offline (pyttsx3)")
    parser.add_argument("--voice", choices=["pl", "en"], default="pl", help="Język głosu")
    parser.add_argument("--record", type=int, default=5, help="Sekundy nagrywania")
    args = parser.parse_args()
    run(
        text_only=args.text_only,
        offline_tts=args.offline_tts,
        voice_lang=args.voice,
        record_seconds=args.record
    )
