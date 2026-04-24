# VR gate patterns by language

Copy-paste ready. Each block is the smallest working gate for that language.

## Python

### Minimal inline gate
```python
import os, json, datetime

def charge_customer(amount):
    if os.environ.get("VERIFIED_REFUSAL_MODE") == "1" and os.environ.get("VERIFIED_REFUSAL_OVERRIDE") != "1":
        print(json.dumps({
            "mode": "verified_refusal",
            "function": "charge_customer",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "would_have_executed": True,
            "override_used": False,
            "confirmed": False,
        }))
        return None
    # real call
    return stripe.Charge.create(amount=amount)
```

### With structured report output
```python
from templates.gate import vr_gate

def charge_customer(amount):
    report = vr_gate(
        category="financial_transaction",
        confidence=0.98,
        consequence=f"charge ${amount} to customer",
        checks=[
            (lambda: (amount > 0, "amount_positive")),
            (lambda: (amount < 10_000_00, "amount_under_budget")),
        ],
    )
    if report is not None:
        return report
    return stripe.Charge.create(amount=amount)
```

### With override support
```python
# The override path is built into vr_gate. Set VERIFIED_REFUSAL_OVERRIDE=1
# to bypass the block. The override is always logged.
#
# Shell:   VERIFIED_REFUSAL_OVERRIDE=1 python3 app.py
# Python:  os.environ["VERIFIED_REFUSAL_OVERRIDE"] = "1"
```

### As a decorator
```python
from templates.gate import vr_protect

@vr_protect(category="financial_transaction", confidence=0.98,
            consequence="charge customer")
def charge_customer(amount):
    return stripe.Charge.create(amount=amount)
```

### Async functions
```python
from templates.gate import vr_protect

@vr_protect(category="external_api_side_effect", confidence=0.9)
async def deliver_webhook(url, payload):
    async with aiohttp.ClientSession() as s:
        return await s.post(url, json=payload)
```

---

## JavaScript / TypeScript

### Minimal inline gate (Node)
```javascript
function chargeCustomer(amount) {
  if (process.env.VERIFIED_REFUSAL_MODE === '1' && process.env.VERIFIED_REFUSAL_OVERRIDE !== '1') {
    const report = {
      mode: 'verified_refusal',
      function: 'chargeCustomer',
      timestamp: new Date().toISOString(),
      would_have_executed: true,
      override_used: false,
      confirmed: false,
    };
    console.log(JSON.stringify(report));
    return null;
  }
  return stripe.charges.create({ amount });
}
```

### Structured report with checks (async)
```javascript
const { vrGate } = require('./templates/gate.js');

async function chargeCustomer(amount) {
  const report = await vrGate({
    function: 'chargeCustomer',
    category: 'financial_transaction',
    confidence: 0.98,
    consequence: `charge $${amount} to customer`,
    checks: [
      () => [amount > 0, 'amount_positive'],
      () => [amount < 1_000_000, 'amount_under_budget'],
    ],
  });
  if (report !== null) return report;
  return stripe.charges.create({ amount });
}
```

### Decorator-style wrap
```javascript
const { vrProtect } = require('./templates/gate.js');

const chargeCustomer = vrProtect({
  category: 'financial_transaction',
  confidence: 0.98,
  consequence: 'charge customer',
})(async function chargeCustomer(amount) {
  return stripe.charges.create({ amount });
});
```

### Override
```bash
VERIFIED_REFUSAL_OVERRIDE=1 node app.js
```

---

## Bash

### Minimal gate
```bash
#!/usr/bin/env bash
source templates/gate.sh

delete_production_bucket() {
  vr_gate "delete_production_bucket" "infrastructure_change" "delete s3 bucket prod-data"
  # vr_gate exits with 10 when blocked; callers must propagate.
  if [ $? -eq 10 ]; then
    return 10
  fi

  aws s3 rb s3://prod-data --force
}
```

### Inline (no sourcing)
```bash
delete_production_bucket() {
  if [ "$VERIFIED_REFUSAL_MODE" = "1" ] && [ "$VERIFIED_REFUSAL_OVERRIDE" != "1" ]; then
    printf '{"mode":"verified_refusal","function":"delete_production_bucket","would_have_executed":true,"override_used":false,"confirmed":false}\n'
    return 10
  fi
  aws s3 rb s3://prod-data --force
}
```

---

## Go

### Minimal gate
```go
package main

import (
    "encoding/json"
    "fmt"
    "os"
    "time"
)

func ChargeCustomer(amount int) (map[string]any, error) {
    if os.Getenv("VERIFIED_REFUSAL_MODE") == "1" && os.Getenv("VERIFIED_REFUSAL_OVERRIDE") != "1" {
        report := map[string]any{
            "mode":                 "verified_refusal",
            "function":             "ChargeCustomer",
            "timestamp":            time.Now().UTC().Format(time.RFC3339),
            "classification":       "irreversible",
            "category":             "financial_transaction",
            "confidence":           0.98,
            "would_have_executed":  true,
            "override_used":        false,
            "confirmed":            false,
        }
        b, _ := json.Marshal(report)
        fmt.Println(string(b))
        return report, nil
    }
    // real call
    return stripe.Charge(amount)
}
```

---

## Rust

### Minimal gate
```rust
use std::env;
use std::time::SystemTime;
use serde_json::json;

fn charge_customer(amount: u64) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
    let mode_on = env::var("VERIFIED_REFUSAL_MODE").ok().as_deref() == Some("1");
    let overridden = env::var("VERIFIED_REFUSAL_OVERRIDE").ok().as_deref() == Some("1");
    if mode_on && !overridden {
        let now: chrono::DateTime<chrono::Utc> = SystemTime::now().into();
        let report = json!({
            "mode": "verified_refusal",
            "function": "charge_customer",
            "timestamp": now.to_rfc3339(),
            "classification": "irreversible",
            "category": "financial_transaction",
            "confidence": 0.98,
            "would_have_executed": true,
            "override_used": false,
            "confirmed": false,
        });
        println!("{}", report);
        return Ok(report);
    }
    stripe::charge(amount)
}
```

---

## Gate output schema (every language must emit this)

```json
{
  "mode": "verified_refusal",
  "timestamp": "2026-04-24T12:34:56Z",
  "function": "charge_customer",
  "file": "path/to/file.py",
  "classification": "irreversible",
  "confidence": 0.98,
  "category": "financial_transaction",
  "gates_passed": ["amount_positive"],
  "gates_failed": [],
  "would_have_executed": true,
  "consequence": "charge $100 to customer",
  "override_used": false,
  "confirmed": false,
  "report_path": "~/.openclaw/vr_log.jsonl"
}
```
