"""Example: gated external API call with budget enforcement.

Shows the full protocol:
  1. classify the action
  2. run pre-condition checks against real state
  3. gate on mode; return structured report without executing
  4. wait for human confirmation (CONFIRM=1 in this example)
  5. execute only after confirmation; log the outcome

Run it:
  python3 examples/api_budget.py              # prod-like — refuses
  VERIFIED_REFUSAL_MODE=1 python3 examples/api_budget.py
  VERIFIED_REFUSAL_MODE=1 CONFIRM=1 python3 examples/api_budget.py
  VERIFIED_REFUSAL_OVERRIDE=1 python3 examples/api_budget.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make templates/ importable without install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "templates"))
from gate import vr_gate  # noqa: E402

DAILY_BUDGET_CENTS = 50_000
_session_spend = {"cents": 0}


def _mock_charge(amount_cents: int, recipient: str) -> dict:
    """Stand-in for a real payment provider call. No network I/O."""
    _session_spend["cents"] += amount_cents
    return {"ok": True, "amount_cents": amount_cents, "recipient": recipient,
            "provider_ref": "mock_ch_001"}


def charge_customer(amount_cents: int, recipient: str, idempotency_key: str) -> dict:
    report = vr_gate(
        function="charge_customer",
        file=__file__,
        category="financial_transaction",
        confidence=0.98,
        consequence=f"charge {amount_cents} cents to {recipient}",
        checks=[
            lambda: (amount_cents > 0, "amount_positive"),
            lambda: (amount_cents < 10_000_000, "amount_under_absolute_cap"),
            lambda: (
                _session_spend["cents"] + amount_cents <= DAILY_BUDGET_CENTS,
                "amount_under_daily_budget",
            ),
            lambda: (bool(idempotency_key), "idempotency_key_present"),
        ],
    )
    if report is not None:
        # VR mode active — do not execute. Return the report.
        return report

    # Post-gate: requires explicit confirmation in this example.
    if os.environ.get("CONFIRM") != "1":
        return {
            "mode": "verified_refusal",
            "function": "charge_customer",
            "would_have_executed": True,
            "confirmed": False,
            "deferred": True,
            "note": "set CONFIRM=1 to execute",
        }

    outcome = _mock_charge(amount_cents, recipient)
    return {
        "mode": "verified_refusal",
        "function": "charge_customer",
        "would_have_executed": True,
        "confirmed": True,
        "outcome": outcome,
    }


if __name__ == "__main__":
    import json
    result = charge_customer(
        amount_cents=12_345,
        recipient="cust_abc",
        idempotency_key="req-2026-04-24-0001",
    )
    print(json.dumps(result, indent=2, default=str))
