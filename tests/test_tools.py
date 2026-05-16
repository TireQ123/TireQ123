"""Testy narzędzi Agent Mode — operacje plików, bezpieczeństwo shell."""
from jarvis.core.tools import (
    execute_tool, file_write, file_read, file_list,
    shell_run, TOOLS, TOOLS_SCHEMA,
)


def test_all_tools_have_schema():
    schema_names = {t["name"] for t in TOOLS_SCHEMA}
    assert set(TOOLS.keys()) == schema_names


def test_file_write_then_read(tmp_path):
    target = tmp_path / "hello.txt"
    w = file_write(str(target), "Witaj, Panie TireQ")
    assert w["status"] == "ok"
    r = file_read(str(target))
    assert r["status"] == "ok"
    assert "TireQ" in r["result"]


def test_file_read_missing_returns_error():
    r = file_read("/nieistnieje/plik_xyz.txt")
    assert r["status"] == "error"


def test_shell_run_executes_echo():
    r = shell_run("echo JARVIS_TEST")
    assert r["status"] == "ok"
    assert "JARVIS_TEST" in r["result"]


def test_shell_run_blocks_dangerous_command():
    r = shell_run("rm -rf /")
    assert r["status"] == "error"
    assert "zablokowana" in r["result"].lower()


def test_shell_run_blocks_forkbomb():
    r = shell_run(":(){ :|:& };:")
    assert r["status"] == "error"


def test_execute_tool_unknown_returns_error():
    r = execute_tool("nieistniejace_narzedzie", {})
    assert r["status"] == "error"


def test_execute_tool_bad_params_returns_error():
    r = execute_tool("file_read", {"zly_param": "x"})
    assert r["status"] == "error"


def test_file_list_returns_list(tmp_path):
    (tmp_path / "a.py").write_text("x")
    r = file_list(str(tmp_path))
    assert r["status"] == "ok"
    assert isinstance(r["result"], list)
