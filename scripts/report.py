#!/usr/bin/env python3
"""verified-refusal report: append-only audit log for VR protocol runs.

The log lives at ~/.openclaw/vr_log.jsonl. One JSON object per line.
Never truncated. Never edited. Corruption triggers a recovery file.

CLI:
  python3 report.py --read --n 20
  python3 report.py --summary --period day
  python3 report.py --overrides
  python3 report.py --write '{"mode": "verified_refusal", ...}'
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

LOG_PATH = Path(os.path.expanduser("~/.openclaw/vr_log.jsonl"))


def _log_dir() -> Path:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    return LOG_PATH.parent


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def write(report: dict[str, Any]) -> dict[str, Any]:
    """Append one entry. Never modifies prior lines."""
    if not isinstance(report, dict):
        raise TypeError("report must be a dict")
    _log_dir()
    entry = dict(report)
    entry.setdefault("timestamp", _now())
    entry.setdefault("mode", "verified_refusal")
    line = json.dumps(entry, default=str, ensure_ascii=False)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    count = sum(1 for _ in LOG_PATH.open("r", encoding="utf-8", errors="replace"))
    return {"success": True, "log_path": str(LOG_PATH), "entry_count": count}


def _recovery_path() -> Path:
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return LOG_PATH.parent / f"vr_log_recovery_{ts}.jsonl"


def _iter_entries() -> list[dict[str, Any]]:
    if not LOG_PATH.exists():
        return []
    good: list[dict[str, Any]] = []
    corrupt_lines: list[str] = []
    with LOG_PATH.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                good.append(json.loads(raw))
            except json.JSONDecodeError:
                corrupt_lines.append(raw)
    if corrupt_lines:
        rec = _recovery_path()
        rec.write_text("\n".join(corrupt_lines) + "\n", encoding="utf-8")
        sys.stderr.write(f"warning: {len(corrupt_lines)} corrupt entries copied to {rec}\n")
    return good


def read(n: int = 50, filter_override: bool = False, filter_confirmed: bool = False) -> list[dict[str, Any]]:
    entries = _iter_entries()
    if filter_override:
        entries = [e for e in entries if e.get("override_used")]
    if filter_confirmed:
        entries = [e for e in entries if e.get("confirmed")]
    return entries[-n:]


def _period_start(period: str) -> _dt.datetime | None:
    now = _dt.datetime.now(_dt.timezone.utc)
    if period == "session":
        # best-effort: session = last 2h. sessions don't write PIDs here.
        return now - _dt.timedelta(hours=2)
    if period == "day":
        return now - _dt.timedelta(days=1)
    if period == "week":
        return now - _dt.timedelta(days=7)
    if period == "all":
        return None
    raise ValueError(f"unknown period: {period}")


def _parse_ts(value: Any) -> _dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def summary(period: str = "session") -> dict[str, Any]:
    start = _period_start(period)
    entries = _iter_entries()
    in_window: list[dict[str, Any]] = []
    for e in entries:
        ts = _parse_ts(e.get("timestamp"))
        if start is None or (ts and ts >= start):
            in_window.append(e)
    confirmed = sum(1 for e in in_window if e.get("confirmed"))
    overrides = sum(1 for e in in_window if e.get("override_used"))
    deferred = sum(
        1 for e in in_window
        if not e.get("confirmed") and not e.get("override_used") and not e.get("would_have_executed") is False
    )
    by_category = dict(Counter(e.get("category") or "unknown" for e in in_window))

    # coverage trend: gated vs ungated ratio across entries with classification
    classified = [e for e in in_window if e.get("classification")]
    irreversible_seen = sum(1 for e in classified if e.get("classification") == "irreversible")
    gated_seen = sum(1 for e in classified if e.get("classification") == "irreversible" and e.get("gates_passed"))
    trend = (gated_seen / irreversible_seen) if irreversible_seen else 1.0

    return {
        "period": period,
        "total_checks": len(in_window),
        "confirmed": confirmed,
        "deferred": deferred,
        "overrides": overrides,
        "by_category": by_category,
        "coverage_trend": round(trend, 3),
    }


def _cli() -> int:
    ap = argparse.ArgumentParser(description="verified-refusal audit log")
    ap.add_argument("--read", action="store_true")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--overrides", action="store_true", help="only override entries")
    ap.add_argument("--confirmed", action="store_true", help="only confirmed entries")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--period", choices=["session", "day", "week", "all"], default="session")
    ap.add_argument("--write", help="JSON string to append")
    args = ap.parse_args()

    if args.write:
        try:
            payload = json.loads(args.write)
        except json.JSONDecodeError as exc:
            print(f"error: invalid JSON: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(write(payload), indent=2))
        return 0

    if args.summary:
        print(json.dumps(summary(args.period), indent=2))
        return 0

    if args.read or args.overrides or args.confirmed:
        entries = read(args.n, filter_override=args.overrides, filter_confirmed=args.confirmed)
        for e in entries:
            print(json.dumps(e))
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(_cli())
