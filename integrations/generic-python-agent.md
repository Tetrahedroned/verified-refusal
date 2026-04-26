# Generic Python agent

Use the gate directly from any Python agent. No skill loader, no slash
command runtime — just the templates and scripts shipped in this repo.

## Install

```bash
git clone https://github.com/Tetrahedroned/verified-refusal \
  ~/.vr/skills/verified-refusal

pip install -r ~/.vr/skills/verified-refusal/requirements.txt   # optional
```

Then either copy `templates/gate.py` into your project, or import it
from the install path:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.vr/skills/verified-refusal/templates"))
from gate import vr_protect, vr_gate   # decorator + inline check
```

### Working example

```python
import os, sys
sys.path.insert(0, os.path.expanduser("~/.vr/skills/verified-refusal/templates"))
from gate import vr_protect

@vr_protect(
    category="financial_transaction",
    confidence=0.97,
    consequence="charge customer credit card",
    checks=[lambda: (bool(os.environ.get("IDEMPOTENCY_KEY")), "idempotency_key_present")],
)
def charge_customer(customer_id: str, amount_cents: int) -> dict:
    return {"ok": True, "id": customer_id, "amount": amount_cents}

if __name__ == "__main__":
    # default mode: gate is dormant unless VERIFIED_REFUSAL_MODE=1
    print(charge_customer("cust_42", 9900))
```

Run it once normally, then with the gate engaged:

```bash
$ VERIFIED_REFUSAL_MODE=1 python3 example.py
{"mode": "verified_refusal", "function": "charge_customer",
 "category": "financial_transaction", "gates_passed": [],
 "gates_failed": ["idempotency_key_present"],
 "would_have_executed": false, "consequence": "charge customer credit card",
 "override_used": false, "report_path": "/home/you/.vr/vr_log.jsonl", ...}
```

The same JSON line is appended to `~/.vr/vr_log.jsonl`.

## Reload

Not applicable. The next time your agent process starts, the gate is
active.

## Verify

```bash
python3 -c "import sys, os; \
  sys.path.insert(0, os.path.expanduser('~/.vr/skills/verified-refusal/templates')); \
  import gate; print('verified-refusal gate at', gate.__file__)"
```

## Standing order

Whichever file your harness loads as a system prompt or persistent
memory, append the standing order to it:

```bash
cat ~/.vr/skills/verified-refusal/standing-order.md \
  >> <your-agent-system-prompt-file>
```

If your harness has no persistent system prompt, prepend the standing
order to the user/system message at the start of every run.

## Audit log path

Default: `~/.vr/vr_log.jsonl`

Override, in priority order:

```bash
VR_LOG_PATH=/custom/path/vr_log.jsonl python3 your-agent.py   # canonical
VR_DATA_DIR=/custom/dir python3 your-agent.py                 # log → <dir>/vr_log.jsonl
OPENCLAW_VR_LOG=/custom/path/vr_log.jsonl python3 your-agent.py   # deprecated alias
```

## Slash commands

Generic Python agents don't have slash commands. Invoke the scripts
directly when you need them:

```bash
python3 ~/.vr/skills/verified-refusal/scripts/scan.py   --root .
python3 ~/.vr/skills/verified-refusal/scripts/wrap.py   --file <path> --function <name>
python3 ~/.vr/skills/verified-refusal/scripts/report.py --read --n 1     # /vr-report
python3 ~/.vr/skills/verified-refusal/scripts/scan.py   --root . --json  # /vr-status
python3 ~/.vr/skills/verified-refusal/scripts/report.py --read --n 50    # /vr-log
```
