# J.A.R.V.I.S. — Testy

## Uruchomienie

```bash
pip install pytest pytest-cov
python -m pytest                          # wszystkie testy
python -m pytest tests/test_memory.py     # jeden moduł
python -m pytest --cov=jarvis --cov=scripts --cov-report=term-missing
```

## Pokrycie modułów

| Plik testowy | Moduł | Co testuje |
|---|---|---|
| `test_memory.py` | memory_sync, memory_update | normalizacja, deduplikacja, ekstrakcja wiedzy |
| `test_tools.py` | jarvis.core.tools | operacje plików, bezpieczeństwo shell |
| `test_agent.py` | jarvis.core.agent | parsowanie wywołań narzędzi |
| `test_plugins.py` | jarvis.plugins | rejestr, kalendarz, notatki |
| `test_scheduler.py` | jarvis.scheduler | harmonogram, logika should_run |
| `test_training.py` | training_collect, training_format | scoring, ekstrakcja, eksport |
| `test_memory_cleanup.py` | memory_cleanup | dedup, archiwizacja, konsolidacja sesji |
| `test_rag_query.py` | rag_query | fallback keyword search, formatowanie |
| `test_dashboard.py` | jarvis.api.dashboard | agregacja danych ze wszystkich modułów |
| `test_cli.py` | jarvis.cli | dispatch komend, budowanie wywołań |
| `test_weather_plugin.py` | jarvis.plugins.weather | API pogodowe (mock HTTP) |
| `test_github_plugin.py` | jarvis.plugins.github | repos/issues/PR (mock HTTP) |
| `test_scheduler_engine.py` | jarvis.scheduler.engine | execute_task, run_pending, weekly |

## Stan

148 testów, wszystkie przechodzą. CI: `.github/workflows/tests.yml`
(Python 3.11 + 3.12, coverage + lint).

Pokrycie modułów priorytetowych:
- `weather_plugin` — 97%
- `dashboard.get_dashboard_data` — 94%
- `github_plugin` — 94%
- `memory_cleanup` — 88%
- `scheduler.engine` — 71%
- `jarvis.cli` — 66%
- `rag_query._keyword_search` — pełne (gałąź `query()` wymaga ChromaDB)

## Priorytety dalszego pokrycia

Najważniejsze nieprzetestowane obszary:
- `memory_suggest` — heurystyki sugestii
- `jarvis.monitor.watcher` — detekcja zmian w repo
- `jarvis.core.multi_agent` — orkiestracja (wymaga mock Ollama)
- `memory_load` — wstrzykiwanie do CLAUDE.md
