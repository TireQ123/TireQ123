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
| `test_memory_update.py` | memory_update | add_decision, add_preference, add_note, add_task, save_session |
| `test_memory_sync.py` | memory_sync | normalize, similarity, extract, merge, throttle |
| `test_training_collect.py` | training_collect | extract_text, is_quality_pair, score_pair, extract_pairs |
| `test_training_format.py` | training_format | load_raw, format_openai/alpaca/huggingface, export |
| `test_agent_run.py` | jarvis.core.agent | run_agent, ollama_chat, tool_override, verbose |
| `test_tools_extra.py` | jarvis.core.tools | memory_read/save, web_search, shell timeout, file_list |
| `test_tireq_plugin.py` | jarvis.plugins.tireq | briefing, project_init, daily_log, quick_commit, health_check |
| `test_calendar_notes_extra.py` | calendar_plugin, notes_plugin | calendar_today/remind, note_read/search |
| `test_cli_extra.py` | jarvis.cli | do_status, do_plugin, do_multi, do_briefing, do_schedule |
| `test_agent_interactive.py` | jarvis.core.agent | ollama_chat success, interactive_mode |
| `test_multi_agent_extra.py` | jarvis.core.multi_agent | verbose paths, tool exception, interactive_mode |
| `test_monitor_extra.py` | jarvis.monitor.watcher | _run, run_once branches, watch_loop |
| `test_scheduler_extra.py` | jarvis.scheduler.engine | _log, plugin/agent tasks, daemon_loop |

## Stan

490 testów, wszystkie przechodzą. CI: `.github/workflows/tests.yml`
(Python 3.11 + 3.12, coverage + lint). Pokrycie globalne: 82%.

Pokrycie modułów priorytetowych:
- `weather_plugin` — 97%
- `github_plugin` — 94%
- `dashboard` — 94%
- `training_format` — 92%
- `training_seed` — 92%
- `rag_index` — 90%
- `memory_load` — 90%
- `memory_cleanup` — 88%
- `calendar_plugin` — 100%
- `notes_plugin` — 100%
- `tireq_plugin` — 96%
- `core/agent` — 91%
- `core/tools` — 91%
- `core/multi_agent` — 89%
- `memory_sync` — 99%
- `training_collect` — 81%
- `cli` — 98%
- `monitor.watcher` — 94%
- `scheduler.engine` — 88%
- `api/server` — 75%

## Priorytety dalszego pokrycia

Pozostałe obszary z niskim pokryciem (wymagają zewnętrznych zależności):
- `jarvis.integrations.telegram_bot` — 0% (wymaga Telegram API — pominięte)
- `scripts.rag_query` (gałąź `query()`) — wymaga ChromaDB z danymi
- `scripts.training_generate` — 59% (wymaga ANTHROPIC_API_KEY)
