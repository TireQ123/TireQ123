#!/usr/bin/env python3
"""
J.A.R.V.I.S. Plugin — Pogoda (Open-Meteo — darmowe API, bez klucza).
"""
import json
import urllib.request
import urllib.parse
from jarvis.plugins import JarvisPlugin


def _get_coords(city: str) -> tuple[float, float] | None:
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city)}&count=1&language=pl"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            results = data.get("results", [])
            if results:
                return results[0]["latitude"], results[0]["longitude"]
    except Exception:
        pass
    return None


def weather_current(city: str = "Warsaw") -> dict:
    coords = _get_coords(city)
    if not coords:
        return {"error": f"Nie znaleziono miasta: {city}"}
    lat, lon = coords
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
        f"&wind_speed_unit=kmh&timezone=auto"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            c = data["current"]
            code = c.get("weather_code", 0)
            desc = _weather_desc(code)
            return {
                "city": city,
                "temperature": f"{c['temperature_2m']}°C",
                "humidity": f"{c['relative_humidity_2m']}%",
                "wind": f"{c['wind_speed_10m']} km/h",
                "condition": desc
            }
    except Exception as e:
        return {"error": str(e)}


def weather_forecast(city: str = "Warsaw", days: int = 3) -> dict:
    coords = _get_coords(city)
    if not coords:
        return {"error": f"Nie znaleziono miasta: {city}"}
    lat, lon = coords
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum"
        f"&timezone=auto&forecast_days={min(days, 7)}"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            d = data["daily"]
            forecast = []
            for i in range(len(d["time"])):
                forecast.append({
                    "date": d["time"][i],
                    "max": f"{d['temperature_2m_max'][i]}°C",
                    "min": f"{d['temperature_2m_min'][i]}°C",
                    "rain": f"{d['precipitation_sum'][i]}mm",
                    "condition": _weather_desc(d["weather_code"][i])
                })
            return {"city": city, "forecast": forecast}
    except Exception as e:
        return {"error": str(e)}


def _weather_desc(code: int) -> str:
    if code == 0:
        return "Bezchmurnie"
    elif code in (1, 2, 3):
        return "Częściowe zachmurzenie"
    elif code in (45, 48):
        return "Mgła"
    elif code in (51, 53, 55):
        return "Mżawka"
    elif code in (61, 63, 65):
        return "Deszcz"
    elif code in (71, 73, 75):
        return "Śnieg"
    elif code in (80, 81, 82):
        return "Przelotne opady"
    elif code in (95, 96, 99):
        return "Burza"
    return f"Kod pogodowy: {code}"


class WeatherPlugin(JarvisPlugin):
    name = "weather"
    description = "Pogoda przez Open-Meteo (bez klucza API)"
    enabled = True

    def get_tools(self):
        return [
            ("weather_current", weather_current,
             {"description": "Aktualna pogoda w mieście",
              "params": {"city": "str — nazwa miasta, domyślnie Warsaw"}}),
            ("weather_forecast", weather_forecast,
             {"description": "Prognoza pogody na kilka dni",
              "params": {"city": "str", "days": "int 1-7"}}),
        ]


plugin = WeatherPlugin()
