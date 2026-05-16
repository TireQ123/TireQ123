"""Testy parsowania wywołań narzędzi w Agent Mode."""
from jarvis.core.agent import parse_tool_call, build_system


def test_parse_valid_tool_call():
    text = '<tool>\n{"name": "file_read", "params": {"path": "x.py"}}\n</tool>'
    call = parse_tool_call(text)
    assert call == {"name": "file_read", "params": {"path": "x.py"}}


def test_parse_no_tool_returns_none():
    assert parse_tool_call("Zadanie wykonane, Panie TireQ.") is None


def test_parse_malformed_json_returns_none():
    text = "<tool>\n{name: file_read}\n</tool>"
    assert parse_tool_call(text) is None


def test_parse_tool_with_surrounding_text():
    text = ('Użyję narzędzia.\n<tool>\n'
            '{"name": "git_status", "params": {}}\n</tool>\nGotowe.')
    call = parse_tool_call(text)
    assert call["name"] == "git_status"


def test_build_system_includes_tools():
    system = build_system()
    assert "file_read" in system
    assert "shell_run" in system


def test_build_system_includes_extra_tools():
    extra = [{"name": "custom_tool", "description": "test", "params": {}}]
    system = build_system(extra)
    assert "custom_tool" in system
