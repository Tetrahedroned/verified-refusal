"""Tests for scripts/report.py — append-only audit log."""
import json
import os
from pathlib import Path

import report as R


def _redirect_log(tmp_path, monkeypatch):
    new_path = tmp_path / "vr_log.jsonl"
    monkeypatch.setattr(R, "LOG_PATH", new_path)
    return new_path


def test_write_appends(tmp_path, monkeypatch):
    log = _redirect_log(tmp_path, monkeypatch)
    assert not log.exists()
    r = R.write({"function": "foo", "would_have_executed": True})
    assert r["success"]
    assert log.exists()
    assert log.read_text().count("\n") == 1
    r2 = R.write({"function": "bar", "would_have_executed": False})
    assert log.read_text().count("\n") == 2
    assert r2["entry_count"] == 2


def test_write_creates_missing(tmp_path, monkeypatch):
    log = _redirect_log(tmp_path, monkeypatch)
    assert not log.exists()
    R.write({"function": "x"})
    assert log.exists()


def test_read_last_n(tmp_path, monkeypatch):
    _redirect_log(tmp_path, monkeypatch)
    for i in range(5):
        R.write({"function": f"fn_{i}", "i": i})
    entries = R.read(n=2)
    assert len(entries) == 2
    assert entries[-1]["i"] == 4


def test_read_missing_log(tmp_path, monkeypatch):
    _redirect_log(tmp_path, monkeypatch)
    assert R.read() == []


def test_filter_overrides(tmp_path, monkeypatch):
    _redirect_log(tmp_path, monkeypatch)
    R.write({"function": "a", "override_used": False})
    R.write({"function": "b", "override_used": True})
    R.write({"function": "c", "override_used": True})
    entries = R.read(filter_override=True)
    assert len(entries) == 2
    assert all(e["override_used"] for e in entries)


def test_summary_counts(tmp_path, monkeypatch):
    _redirect_log(tmp_path, monkeypatch)
    R.write({"function": "a", "confirmed": True, "category": "financial_transaction"})
    R.write({"function": "b", "confirmed": False, "category": "database_write"})
    R.write({"function": "c", "override_used": True, "category": "financial_transaction"})
    s = R.summary("all")
    assert s["total_checks"] == 3
    assert s["confirmed"] == 1
    assert s["overrides"] == 1
    assert s["by_category"]["financial_transaction"] == 2


def test_log_never_overwritten(tmp_path, monkeypatch):
    log = _redirect_log(tmp_path, monkeypatch)
    R.write({"function": "first"})
    first_bytes = log.read_bytes()
    R.write({"function": "second"})
    now = log.read_text()
    # append semantics: original content still present at the start
    assert now.startswith(first_bytes.decode())
    assert "second" in now


def test_corrupt_line_recovery(tmp_path, monkeypatch):
    log = _redirect_log(tmp_path, monkeypatch)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text('{"function": "ok"}\nGARBAGE LINE\n{"function": "ok2"}\n')
    entries = R.read()
    assert len(entries) == 2
    recovery = list(log.parent.glob("vr_log_recovery_*.jsonl"))
    assert recovery, "a recovery file should exist"
