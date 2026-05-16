#!/usr/bin/env python3
"""
J.A.R.V.I.S. Dashboard — panel webowy.
Montowany do serwera API. Cały system w jednym oknie przeglądarki.

Dostęp: http://localhost:8000/dashboard
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def get_dashboard_data() -> dict:
    """Zbiera dane ze wszystkich modułów Jarvisa."""
    profile = _read_json(ROOT / "memory/profile.json", {})
    decisions = _read_json(ROOT / "memory/decisions.json", {"decisions": []})

    # Pamięć
    prefs = profile.get("patterns", {}).get("preferred_solutions", [])
    notes = profile.get("notes", [])
    decs = decisions.get("decisions", [])

    # Dane treningowe
    raw = ROOT / "training/raw_pairs.jsonl"
    train_count = sum(1 for _ in raw.open()) if raw.exists() else 0

    # Scheduler
    tasks = _read_json(ROOT / "jarvis/scheduler/tasks.json", {"tasks": []})["tasks"]
    sched_state = _read_json(ROOT / "memory/.scheduler_state.json", {})

    # Monitor alerts
    alerts = _read_json(ROOT / "memory/monitor_alerts.json", [])

    # Sesje
    sessions_dir = ROOT / "memory/sessions"
    sessions = []
    if sessions_dir.exists():
        for f in sorted(sessions_dir.glob("*.json"), reverse=True)[:10]:
            d = _read_json(f, {})
            sessions.append({"date": d.get("date", "")[:16], "summary": d.get("summary", "")})

    # Git
    try:
        git_log = subprocess.run(
            ["git", "log", "--oneline", "-5"], cwd=ROOT,
            capture_output=True, text=True, timeout=5
        ).stdout.strip().splitlines()
    except Exception:
        git_log = []

    # Kalendarz
    calendar = _read_json(ROOT / "memory/calendar.json", [])

    return {
        "memory": {
            "preferences": prefs,
            "decisions": [{"date": d.get("date", "")[:10], "text": d.get("decision", "")}
                          for d in decs[-10:]],
            "notes": [{"date": (n.get("date", "")[:10] if isinstance(n, dict) else ""),
                       "text": (n.get("note", "") if isinstance(n, dict) else n)}
                      for n in notes[-10:]],
        },
        "training": {
            "count": train_count,
            "target": 100,
            "percent": min(100, int(train_count / 100 * 100))
        },
        "scheduler": [
            {
                "name": t["name"],
                "schedule": t["schedule"],
                "enabled": t.get("enabled", True),
                "last_run": sched_state.get(t["id"], {}).get("last_run", "nigdy")
            }
            for t in tasks
        ],
        "alerts": alerts[-10:][::-1],
        "sessions": sessions,
        "git": git_log,
        "calendar": sorted(calendar, key=lambda e: e.get("datetime", ""))[:5],
    }


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>J.A.R.V.I.S. Dashboard</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:'Segoe UI',system-ui,sans-serif; background:#0a0e14;
         color:#c9d1d9; padding:20px; }
  h1 { font-size:22px; color:#58a6ff; margin-bottom:4px;
       display:flex; align-items:center; gap:10px; }
  .sub { color:#6e7681; font-size:12px; margin-bottom:20px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(340px,1fr));
          gap:16px; }
  .card { background:#0d1117; border:1px solid #21262d; border-radius:10px;
          padding:16px; }
  .card h2 { font-size:14px; color:#58a6ff; margin-bottom:12px;
             text-transform:uppercase; letter-spacing:0.5px;
             border-bottom:1px solid #21262d; padding-bottom:8px; }
  .item { padding:6px 0; font-size:13px; border-bottom:1px solid #161b22; }
  .item:last-child { border:none; }
  .date { color:#6e7681; font-size:11px; margin-right:6px; }
  .bar { background:#161b22; border-radius:6px; height:22px; overflow:hidden;
         margin:8px 0; }
  .fill { background:linear-gradient(90deg,#1f6feb,#58a6ff); height:100%;
          display:flex; align-items:center; padding-left:8px;
          font-size:11px; color:#fff; transition:width .5s; }
  .ok { color:#3fb950; } .warn { color:#d29922; } .err { color:#f85149; }
  .pill { display:inline-block; padding:2px 8px; border-radius:10px;
          font-size:10px; background:#161b22; }
  .pill.on { color:#3fb950; } .pill.off { color:#6e7681; }
  #chat { display:flex; flex-direction:column; height:300px; }
  #log { flex:1; overflow-y:auto; display:flex; flex-direction:column;
         gap:6px; margin-bottom:8px; }
  .msg { padding:6px 10px; border-radius:6px; font-size:13px; max-width:85%; }
  .u { background:#1f6feb; color:#fff; align-self:flex-end; }
  .j { background:#161b22; align-self:flex-start; white-space:pre-wrap; }
  #row { display:flex; gap:6px; }
  #inp { flex:1; background:#0d1117; border:1px solid #21262d; color:#c9d1d9;
         padding:8px; border-radius:6px; }
  button { background:#238636; color:#fff; border:none; padding:8px 14px;
           border-radius:6px; cursor:pointer; font-size:13px; }
  button:hover { background:#2ea043; }
  .refresh { float:right; font-size:11px; color:#6e7681; }
  .empty { color:#6e7681; font-style:italic; font-size:12px; }
</style>
</head>
<body>
  <h1>&#129302; J.A.R.V.I.S. Dashboard</h1>
  <div class="sub">Osobisty asystent AI &mdash; TireQ
     <span class="refresh" id="ts"></span></div>

  <div class="grid">
    <div class="card" style="grid-column:1/-1;">
      <h2>Rozmowa</h2>
      <div id="chat">
        <div id="log"></div>
        <div id="row">
          <input id="inp" placeholder="Napisz do Jarvisa..." autocomplete="off">
          <button onclick="send()">Wy&#347;lij</button>
        </div>
      </div>
    </div>

    <div class="card">
      <h2>Dane treningowe</h2>
      <div class="bar"><div class="fill" id="trainfill"></div></div>
      <div id="traintxt" class="sub"></div>
    </div>

    <div class="card"><h2>Preferencje</h2><div id="prefs"></div></div>
    <div class="card"><h2>Decyzje techniczne</h2><div id="decs"></div></div>
    <div class="card"><h2>Notatki</h2><div id="notes"></div></div>
    <div class="card"><h2>Zadania w tle</h2><div id="sched"></div></div>
    <div class="card"><h2>Alerty monitora</h2><div id="alerts"></div></div>
    <div class="card"><h2>Kalendarz</h2><div id="cal"></div></div>
    <div class="card"><h2>Ostatnie sesje</h2><div id="sess"></div></div>
    <div class="card"><h2>Git</h2><div id="git"></div></div>
  </div>

<script>
let history = [];

function row(items, fmt) {
  if (!items || !items.length) return '<div class="empty">brak danych</div>';
  return items.map(fmt).join('');
}

async function load() {
  const r = await fetch('/dashboard/data');
  const d = await r.json();

  document.getElementById('ts').textContent =
    'odświeżono ' + new Date().toLocaleTimeString('pl-PL');

  const t = d.training;
  document.getElementById('trainfill').style.width = t.percent + '%';
  document.getElementById('trainfill').textContent = t.percent + '%';
  document.getElementById('traintxt').textContent =
    t.count + ' / ' + t.target + ' par' +
    (t.count >= t.target ? ' — gotowe do fine-tuningu!' : '');

  document.getElementById('prefs').innerHTML =
    row(d.memory.preferences, p => `<div class="item">&bull; ${p}</div>`);
  document.getElementById('decs').innerHTML =
    row(d.memory.decisions, x =>
      `<div class="item"><span class="date">${x.date}</span>${x.text}</div>`);
  document.getElementById('notes').innerHTML =
    row(d.memory.notes, x =>
      `<div class="item"><span class="date">${x.date}</span>${x.text}</div>`);

  document.getElementById('sched').innerHTML =
    row(d.scheduler, s =>
      `<div class="item">
        <span class="pill ${s.enabled?'on':'off'}">${s.enabled?'ON':'OFF'}</span>
        ${s.name} <span class="date">(${s.schedule})</span></div>`);

  document.getElementById('alerts').innerHTML =
    row(d.alerts, a =>
      `<div class="item warn"><span class="date">${(a.time||'').slice(11,16)}</span>${a.message}</div>`);

  document.getElementById('cal').innerHTML =
    row(d.calendar, e =>
      `<div class="item"><span class="date">${(e.datetime||'').slice(0,16)}</span>${e.title}</div>`);

  document.getElementById('sess').innerHTML =
    row(d.sessions, s =>
      `<div class="item"><span class="date">${s.date}</span>${s.summary.slice(0,90)}</div>`);

  document.getElementById('git').innerHTML =
    row(d.git, g => `<div class="item">${g}</div>`);
}

function add(role, text) {
  const log = document.getElementById('log');
  const div = document.createElement('div');
  div.className = 'msg ' + (role === 'user' ? 'u' : 'j');
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

async function send() {
  const inp = document.getElementById('inp');
  const txt = inp.value.trim();
  if (!txt) return;
  inp.value = '';
  add('user', txt);
  add('jarvis', '...');
  const log = document.getElementById('log');
  const last = log.lastChild;
  try {
    const r = await fetch('/chat', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({message: txt, history})
    });
    const d = await r.json();
    last.textContent = d.response;
    history = d.history;
  } catch (e) {
    last.textContent = 'Błąd: Ollama niedostępna (' + e.message + ')';
  }
}

document.getElementById('inp').addEventListener('keydown',
  e => { if (e.key === 'Enter') send(); });

load();
setInterval(load, 15000);
</script>
</body>
</html>"""
