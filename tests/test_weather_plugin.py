"""Testy jarvis/plugins/weather_plugin.py — z mockowaniem HTTP."""
import json

import pytest

from jarvis.plugins import weather_plugin as wp


class FakeResp:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode()

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def mock_urlopen(monkeypatch, payloads):
    """payloads: lista odpowiedzi zwracanych kolejno przez urlopen."""
    it = iter(payloads)
    monkeypatch.setattr(wp.urllib.request, "urlopen",
                        lambda *a, **k: FakeResp(next(it)))


GEO = {"results": [{"latitude": 52.23, "longitude": 21.01}]}


# ── _weather_desc — czysta logika, wszystkie gałęzie ─────────────────────────

@pytest.mark.parametrize("code,expected", [
    (0, "Bezchmurnie"),
    (2, "Częściowe zachmurzenie"),
    (45, "Mgła"),
    (53, "Mżawka"),
    (63, "Deszcz"),
    (73, "Śnieg"),
    (81, "Przelotne opady"),
    (96, "Burza"),
])
def test_weather_desc_known_codes(code, expected):
    assert wp._weather_desc(code) == expected


def test_weather_desc_unknown_code():
    assert "Kod pogodowy: 123" == wp._weather_desc(123)


# ── _get_coords ──────────────────────────────────────────────────────────────

def test_get_coords_success(monkeypatch):
    mock_urlopen(monkeypatch, [GEO])
    assert wp._get_coords("Warszawa") == (52.23, 21.01)


def test_get_coords_no_results(monkeypatch):
    mock_urlopen(monkeypatch, [{"results": []}])
    assert wp._get_coords("Atlantyda") is None


def test_get_coords_network_error(monkeypatch):
    def boom(*a, **k):
        raise OSError("network down")
    monkeypatch.setattr(wp.urllib.request, "urlopen", boom)
    assert wp._get_coords("Warszawa") is None


# ── weather_current ──────────────────────────────────────────────────────────

def test_weather_current_success(monkeypatch):
    mock_urlopen(monkeypatch, [GEO, {"current": {
        "temperature_2m": 12.5, "relative_humidity_2m": 80,
        "wind_speed_10m": 15, "weather_code": 0}}])
    out = wp.weather_current("Warszawa")
    assert out["city"] == "Warszawa"
    assert out["temperature"] == "12.5°C"
    assert out["humidity"] == "80%"
    assert out["wind"] == "15 km/h"
    assert out["condition"] == "Bezchmurnie"


def test_weather_current_city_not_found(monkeypatch):
    mock_urlopen(monkeypatch, [{"results": []}])
    out = wp.weather_current("Nibylandia")
    assert "Nie znaleziono" in out["error"]


def test_weather_current_api_error(monkeypatch):
    it = iter([GEO])

    def fake(*a, **k):
        try:
            return FakeResp(next(it))
        except StopIteration:
            raise OSError("api 500")
    monkeypatch.setattr(wp.urllib.request, "urlopen", fake)
    out = wp.weather_current("Warszawa")
    assert "error" in out


# ── weather_forecast ─────────────────────────────────────────────────────────

def test_weather_forecast_success(monkeypatch):
    daily = {"daily": {
        "time": ["2026-05-16", "2026-05-17"],
        "temperature_2m_max": [18.0, 20.0],
        "temperature_2m_min": [9.0, 10.0],
        "precipitation_sum": [0.0, 2.5],
        "weather_code": [0, 61],
    }}
    mock_urlopen(monkeypatch, [GEO, daily])
    out = wp.weather_forecast("Warszawa", days=2)
    assert out["city"] == "Warszawa"
    assert len(out["forecast"]) == 2
    assert out["forecast"][0]["max"] == "18.0°C"
    assert out["forecast"][1]["condition"] == "Deszcz"
    assert out["forecast"][1]["rain"] == "2.5mm"


def test_weather_forecast_city_not_found(monkeypatch):
    mock_urlopen(monkeypatch, [{"results": []}])
    out = wp.weather_forecast("Nigdzie")
    assert "Nie znaleziono" in out["error"]


# ── Plugin metadata ──────────────────────────────────────────────────────────

def test_plugin_exposes_two_tools():
    tools = wp.plugin.get_tools()
    names = {t[0] for t in tools}
    assert names == {"weather_current", "weather_forecast"}


def test_plugin_attributes():
    assert wp.plugin.name == "weather"
    assert wp.plugin.enabled is True
