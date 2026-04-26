---
name: verified_refusal
description: Mandatory deliberation protocol for irreversible agent actions
user-invocable: true
metadata: {"openclaw":{"emoji":"🔒","requires":{"bins":["python3"]},"os":["linux","darwin","win32"]}}
---

# verified_refusal — OpenClaw overlay

This is the **OpenClaw-shaped manifest** for verified-refusal. The full
platform-neutral protocol contract lives at the repo root in
[`SKILL.md`](../../SKILL.md); the body below is reproduced here so
OpenClaw's loader has everything it needs in one file. If you change
the contract, change the root file first and copy down.

The slash command bindings at the bottom use OpenClaw's `{baseDir}`
token, which resolves to this directory; the `../../` segments reach
the shared `scripts/` and `templates/` at repo root.

## Definition

An action is **irreversible** when any of the following is true:

- It calls an external API with a side effect (POST/PUT/PATCH/DELETE, or
  any request that mutates remote state, consumes quota, or triggers a
  downstream handler).
- It is a financial transaction — charge, refund, transfer, payout,
  ledger posting.
- It writes to a database (INSERT/UPDATE/DELETE/TRUNCATE/DROP/ALTER), or
  commits a transaction that previously only held writes.
- It deletes or overwrites a file, object, or blob.
- It sends a message — email, SMS, push, chat post, voice call.
- It delivers or registers a webhook.
- It changes infrastructure — cloud resources, DNS, certificates, IAM,
  container orchestration.
- It creates, rotates, or revokes a credential or permission.
- It crosses any system boundary and leaves a mark outside the agent's
  local sandbox.

"Reversible in theory" does not count. An action is reversible only if
the agent can restore the prior state within the current session, with
tools it already has, without external intervention, and without cost.
If any of those four conditions fails, the action is irreversible and
this protocol applies.

## The Protocol — mandatory

1. Identify irreversible action — do not execute.
2. Run `classify.py` — confirm irreversible classification.
3. Run all pre-conditions and policy checks against real state.
4. If all pass: report what would have executed. Return the structured
   report. Stop.
5. Wait for explicit human confirmation before live execution.
6. If confirmed: execute. Run `report.py` immediately after.
7. If not confirmed in session: do not execute. Record as deferred.

## Activation

This protocol activates automatically when the skill is loaded.
It does not require invocation.
It applies to every session, every task, every agent that loads this skill.

On first load in a new workspace, offer to run `/vr-scan` once. If the
user declines, do not ask again that session.

## Override

`VERIFIED_REFUSAL_OVERRIDE=1` bypasses the gate and permits live execution.

Every override writes an entry to the audit log with `override_used: true`.
No silent overrides. Ever. If an override path exists that does not log,
it is a bug and must be fixed before the skill is published.

## Slash commands

- `/vr-scan`   — scan current workspace for ungated irreversible actions.
- `/vr-wrap`   — wrap a target function with a VR gate.
- `/vr-report` — show the structured report from the last VR run.
- `/vr-status` — show which functions are gated vs ungated in the workspace.
- `/vr-log`    — show recent audit log entries.

OpenClaw bindings (resolved via `{baseDir}`, which points at this
directory; the `../../` reaches repo root where the shared scripts live):

- `/vr-scan`   → `python3 {baseDir}/../../scripts/scan.py --root .`
- `/vr-wrap`   → `python3 {baseDir}/../../scripts/wrap.py --file <path> --function <name>`
- `/vr-report` → `python3 {baseDir}/../../scripts/report.py --read --n 1`
- `/vr-status` → `python3 {baseDir}/../../scripts/scan.py --root . --json`
- `/vr-log`    → `python3 {baseDir}/../../scripts/report.py --read --n 50`

## Output format

Every VR protocol run must return exactly this structure:

```json
{
  "mode": "verified_refusal",
  "timestamp": "iso8601",
  "function": "function_name",
  "file": "filepath",
  "classification": "irreversible|reversible|uncertain",
  "confidence": 0.0,
  "category": "category_string",
  "gates_passed": ["gate1", "gate2"],
  "gates_failed": [],
  "would_have_executed": true,
  "consequence": "description of what would have happened",
  "override_used": false,
  "confirmed": false,
  "report_path": "~/.openclaw/vr_log.jsonl"
}
```

Canonical categories (use exactly one per report):
`external_api_side_effect`, `financial_transaction`, `database_write`,
`file_destructive`, `message_delivery`, `webhook_delivery`,
`infrastructure_change`, `credential_operation`, `rate_limit_consumption`,
`cache_flush_async`, `idempotent_violation`, `lock_escalation`,
`symlink_target`.

## Audit log

OpenClaw default location: `~/.openclaw/vr_log.jsonl` (append-only
JSONL). Override via:

- `VR_LOG_PATH` (canonical) — full file path.
- `VR_DATA_DIR` — base directory; log goes to `<dir>/vr_log.jsonl`.
- `OPENCLAW_VR_LOG` — deprecated alias for `VR_LOG_PATH`; still honored.

- Every gate execution writes one line.
- Every override writes one line with `override_used: true`.
- No script ever deletes, truncates, or edits prior entries.
- If the file does not exist, it is created on first write.
- If the file is corrupt, a recovery file is written alongside and the
  main log is not modified.

Access via `python3 {baseDir}/../../scripts/report.py --read --n 50` or
the `/vr-log` slash command.

## Subtle risks that must never be classified as reversible

- POST without an idempotency key.
- Reads that trigger server-side counters, webhooks, or token spend.
- Cache writes that replicate across edges or clusters.
- File operations on paths that resolve through symlinks.
- `SELECT ... FOR UPDATE` and other lock-escalating reads.
- Webhook registrations (the receiver starts acting on events immediately).
- Rate-limit consumption that counts against quota on failure.
- Soft-delete APIs that cascade to hard-delete after a TTL.
- Audit log writes that are themselves the irreversible action.

See `../../references/irreversible.md` for the full treatment of each.

## Standing rule

Before executing any action that modifies external state, crosses a
system boundary, or cannot be undone — pause. Run the protocol. Do not
proceed without a gate report. Do not proceed without confirmation.
All overrides are logged. No silent bypasses.
