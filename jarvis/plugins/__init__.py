#!/usr/bin/env python3
"""
J.A.R.V.I.S. Plugin Registry — ładuje i rejestruje wtyczki.
Każdy plugin to plik Python w jarvis/plugins/ z klasą dziedziczącą JarvisPlugin.
"""
import importlib
from pathlib import Path
from typing import Callable

PLUGINS_DIR = Path(__file__).parent


class JarvisPlugin:
    """Bazowa klasa dla każdej wtyczki Jarvisa."""
    name: str = "unnamed"
    description: str = ""
    enabled: bool = True

    def get_tools(self) -> list[tuple[str, Callable, dict]]:
        """Zwraca listę (nazwa, funkcja, schemat_params)."""
        return []

    def on_load(self) -> None:
        """Wywoływane przy ładowaniu pluginu."""
        pass


class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, JarvisPlugin] = {}
        self._tools: dict[str, Callable] = {}
        self._schemas: list[dict] = []

    def register(self, plugin: JarvisPlugin) -> None:
        if not plugin.enabled:
            return
        self._plugins[plugin.name] = plugin
        plugin.on_load()
        for tool_name, fn, schema in plugin.get_tools():
            self._tools[tool_name] = fn
            self._schemas.append({
                "name": tool_name,
                "description": schema.get("description", ""),
                "params": schema.get("params", {})
            })
        print(f"[JARVIS] Plugin załadowany: {plugin.name} "
              f"({len(plugin.get_tools())} narzędzi)")

    def load_all(self) -> "PluginRegistry":
        for f in PLUGINS_DIR.glob("*_plugin.py"):
            module_name = f"jarvis.plugins.{f.stem}"
            try:
                mod = importlib.import_module(module_name)
                if hasattr(mod, "plugin"):
                    self.register(mod.plugin)
            except Exception as e:
                print(f"[JARVIS] Błąd ładowania pluginu {f.stem}: {e}")
        return self

    @property
    def tools(self) -> dict[str, Callable]:
        return self._tools

    @property
    def schemas(self) -> list[dict]:
        return self._schemas

    def list_plugins(self) -> list[str]:
        return list(self._plugins.keys())


registry = PluginRegistry()
