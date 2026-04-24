"""Example: gated database write with transaction awareness.

Uses an in-memory SQLite DB so the example is fully self-contained and
safe to run anywhere. The gate:
  - refuses statements whose kind is not on the allowlist
  - refuses when the WHERE clause looks tautological
  - refuses when the estimated row count exceeds a cap
  - emits a structured report under VR mode
  - commits only after confirmation

Run:
  python3 examples/db_write.py
  VERIFIED_REFUSAL_MODE=1 python3 examples/db_write.py
  VERIFIED_REFUSAL_MODE=1 CONFIRM=1 python3 examples/db_write.py
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "templates"))
from gate import vr_gate  # noqa: E402

ALLOWED_KINDS = {"INSERT", "UPDATE", "DELETE"}
MAX_ROWS_AFFECTED = 100
TAUTOLOGY_RX = re.compile(r"\bWHERE\s+(?:1\s*=\s*1|TRUE)\b", re.IGNORECASE)


def _statement_kind(sql: str) -> str:
    head = sql.strip().split(None, 1)[0].upper()
    return head


def _estimate_rows(conn: sqlite3.Connection, sql: str) -> int:
    """Count matching rows *before* the mutation. Uses a read-only probe."""
    kind = _statement_kind(sql)
    if kind == "DELETE":
        m = re.search(r"delete\s+from\s+(\w+)(.*)", sql, re.IGNORECASE | re.DOTALL)
        if not m:
            return -1
        table, tail = m.group(1), m.group(2)
        probe = f"SELECT COUNT(*) FROM {table} {tail}"
        return conn.execute(probe).fetchone()[0]
    if kind == "UPDATE":
        m = re.search(r"update\s+(\w+)\s+set\s+.+?(\s+where\s+.+)?$", sql, re.IGNORECASE | re.DOTALL)
        if not m:
            return -1
        table, where = m.group(1), m.group(2) or ""
        probe = f"SELECT COUNT(*) FROM {table} {where}"
        return conn.execute(probe).fetchone()[0]
    if kind == "INSERT":
        return 1  # single-row INSERT VALUES; multi-row isn't demoed here
    return -1


def run_mutation(conn: sqlite3.Connection, sql: str) -> dict:
    kind = _statement_kind(sql)
    estimated = _estimate_rows(conn, sql)

    report = vr_gate(
        function="run_mutation",
        file=__file__,
        category="database_write",
        confidence=0.95,
        consequence=f"{kind} affecting ~{estimated} row(s)",
        checks=[
            lambda: (kind in ALLOWED_KINDS, "kind_allowed"),
            lambda: (not TAUTOLOGY_RX.search(sql), "no_tautological_where"),
            lambda: (0 <= estimated <= MAX_ROWS_AFFECTED, "row_count_bounded"),
        ],
    )
    if report is not None:
        return report

    if os.environ.get("CONFIRM") != "1":
        return {
            "mode": "verified_refusal",
            "function": "run_mutation",
            "kind": kind,
            "estimated_rows": estimated,
            "would_have_executed": True,
            "confirmed": False,
            "deferred": True,
            "rollback_window": "until COMMIT",
            "note": "set CONFIRM=1 to execute",
        }

    cur = conn.execute(sql)
    conn.commit()
    return {
        "mode": "verified_refusal",
        "function": "run_mutation",
        "kind": kind,
        "rows_affected": cur.rowcount,
        "would_have_executed": True,
        "confirmed": True,
    }


if __name__ == "__main__":
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER)")
    for i in range(5):
        conn.execute("INSERT INTO accounts (name, balance) VALUES (?, ?)", (f"acct_{i}", 100))
    conn.commit()

    result = run_mutation(conn, "UPDATE accounts SET balance = balance + 1 WHERE id = 3")
    print(json.dumps(result, indent=2, default=str))
