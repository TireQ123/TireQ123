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
| `test_memory_load.py` | memory_load | build_context, wstrzykiwanie do CLAUDE.md |
| `test_memory_suggest.py` | memory_suggest | ekstrakcja, parsowanie, zapis sugestii |
| `test_monitor_watcher.py` | jarvis.monitor.watcher | commity, duże pliki, sekrety, gałąź |
| `test_training_seed.py` | training_seed | build_pair, main, deduplication, jakość danych |
| `test_training_generate.py` | training_generate | load_profile_summary, save_pairs, fallbacki API |
| `test_rag_inject.py` | rag_inject | get_last_user_message, build_rag_block, inject_to_claude |
| `test_rag_index.py` | rag_index | stable_id, collect_documents, index_all (mock chromadb) |
| `test_multi_agent.py` | jarvis.core.multi_agent | _parse_json, run_sub_agent, orchestrate (mock Ollama) |
| `test_server.py` | jarvis.api.server | wszystkie endpointy FastAPI (TestClient) |

## Stan

276 testów, wszystkie przechodzą. CI: `.github/workflows/tests.yml`
(Python 3.11 + 3.12, coverage + lint). Pokrycie globalne: 62%.

Pokrycie modułów priorytetowych:
- `weather_plugin` — 97%
- `training_seed` — 92%
- `rag_index` — 90%
- `memory_load` — 90%
- `github_plugin` — 94%
- `plugins.__init__` — 93%
- `dashboard.get_dashboard_data` — 94%
- `memory_cleanup` — 88%
- `rag_inject` — 78%
- `memory_suggest` — 78%
- `scheduler.engine` — 71%
- `monitor.watcher` — 68%
- `jarvis.api.server` — 65%+ (endpointy HTTP, WebSocket pominięty)
- `multi_agent` — 70%+
- `rag_query._keyword_search` — pełne (gałąź `query()` wymaga ChromaDB)

## Priorytety dalszego pokrycia

Pozostałe nieprzetestowane obszary (niski priorytet):
- `jarvis.plugins.tireq_plugin` — 19% (wymaga pliku credentials / Telegram)
- `scripts.memory_update` — 36% (CLI argparse, interaktywne)
- `scripts.training_collect` / `training_format` — 39-43% (parse_transcript wymaga transkryptów)
- `scripts.memory_sync` — 47% (orchestracja skryptów)
