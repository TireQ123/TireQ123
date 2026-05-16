"""Testy schedulera — parsowanie harmonogramu, logika should_run."""
from datetime import datetime, timedelta

from jarvis.scheduler.engine import parse_interval, should_run


def test_parse_interval_hours():
    assert parse_interval("every 6h") == timedelta(hours=6)


def test_parse_interval_minutes():
    assert parse_interval("every 30m") == timedelta(minutes=30)


def test_parse_interval_days():
    assert parse_interval("every 2d") == timedelta(days=2)


def test_parse_interval_invalid():
    assert parse_interval("08:00") is None


def test_should_run_interval_first_time():
    task = {"id": "t1", "schedule": "every 1h", "repeat": "interval", "enabled": True}
    assert should_run(task, {}, datetime.now()) is True


def test_should_run_interval_not_yet():
    now = datetime.now()
    task = {"id": "t1", "schedule": "every 1h", "repeat": "interval", "enabled": True}
    state = {"t1": {"last_run": (now - timedelta(minutes=10)).isoformat()}}
    assert should_run(task, state, now) is False


def test_should_run_interval_elapsed():
    now = datetime.now()
    task = {"id": "t1", "schedule": "every 1h", "repeat": "interval", "enabled": True}
    state = {"t1": {"last_run": (now - timedelta(hours=2)).isoformat()}}
    assert should_run(task, state, now) is True


def test_should_run_disabled_task():
    task = {"id": "t1", "schedule": "every 1h", "repeat": "interval", "enabled": False}
    assert should_run(task, {}, datetime.now()) is False


def test_should_run_daily_before_time():
    now = datetime.now().replace(hour=6, minute=0)
    task = {"id": "d1", "schedule": "08:00", "repeat": "daily", "enabled": True}
    assert should_run(task, {}, now) is False


def test_should_run_daily_after_time_first():
    now = datetime.now().replace(hour=9, minute=0)
    task = {"id": "d1", "schedule": "08:00", "repeat": "daily", "enabled": True}
    assert should_run(task, {}, now) is True
