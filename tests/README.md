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

## Stan

46 testów, wszystkie przechodzą. CI: `.github/workflows/tests.yml`
(Python 3.11 + 3.12, coverage + lint).

## Priorytety dalszego pokrycia

Najważniejsze nieprzetestowane obszary (logika nie wymagająca Ollama):
- `rag_query._keyword_search` — fallback wyszukiwania
- `memory_cleanup` — konsolidacja i archiwizacja
- `jarvis.cli` — dispatch komend
- `dashboard.get_dashboard_data` — agregacja danych
- pluginy `weather`, `github` — wymagają mockowania HTTP
