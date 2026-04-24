# Irreversibility reference

Written for agents. Read before executing any action that touches external state.

## Definition

An action is **irreversible** if, after it executes, the agent cannot restore
the pre-action state *within the current session*, *without external
intervention*, and *without cost*. "Undoable in theory" does not count.
Undoable in practice by the agent, right now, is the only test that matters.

A reversible action leaves no durable trace outside the local sandbox.
An irreversible action crosses a system boundary and leaves a mark that
another process, service, or human can observe.

## Obvious irreversible actions

- **External API mutations.** POST/PUT/PATCH/DELETE to any service you do not
  own end-to-end. The other side has already received and processed the call
  by the time your function returns.
- **Financial transactions.** Charges, refunds, transfers, payouts. Even
  successful reversals are a second irreversible action, not an undo.
- **Database writes.** INSERT/UPDATE/DELETE/TRUNCATE/DROP. Transactions help
  only until commit. After commit, the write is public to every other reader.
- **File deletion and overwrite.** `rm`, `rmdir`, `unlink`, `shutil.rmtree`,
  `open(path, 'w')`. Overwrites destroy the prior bytes with no recovery
  unless a versioned backup exists outside the agent's control.
- **Message delivery.** Email, SMS, push, chat. The recipient's inbox
  remembers. Retraction features are social, not technical.
- **Webhook delivery.** The receiver has already processed and may have
  fanned out to its own downstream systems.
- **Infrastructure changes.** `terraform apply`, `kubectl apply`, cloud
  provider create/delete. Rollback is possible but costs time, money, and
  risks data divergence.
- **Credential operations.** Key creation, rotation, revocation; permission
  grants and revocations. Rotations invalidate holders; revocations cannot
  be un-revoked without re-issuing.

## Subtle cases agents miss

These are the expensive ones. Each section:

**What it looks like** — the pattern the agent sees.
**Why agents classify it as safe** — the trap.
**Why it is actually irreversible** — the real consequence.
**Pattern example** — code the agent should treat as a gate candidate.

### 1. Idempotent-looking POSTs that are not idempotent

**What it looks like:** `requests.post(url, json=payload)` to an endpoint
whose docs say "idempotent" or imply the operation is naturally safe to
retry.

**Why agents classify it as safe:** "Idempotent" is in the docs. The method
name in the SDK is something like `upsert`. The agent assumes calling it
twice is safe.

**Why it is actually irreversible:** Idempotency requires an idempotency
key. Without one, every call is a distinct operation on the server.
Many services advertise "idempotent" semantics that only apply when the
client supplies the key. Retrying without the key creates duplicates,
double-charges, duplicate emails, duplicate webhook deliveries.

**Pattern example:**
```python
# This is not idempotent:
requests.post("https://api.example.com/payments", json={"amount": 100})

# This is idempotent — key required:
requests.post(
    "https://api.example.com/payments",
    json={"amount": 100},
    headers={"Idempotency-Key": stable_request_uuid},
)
```

### 2. Read operations with server-side side effects

**What it looks like:** `GET /api/resource`, a read call.

**Why agents classify it as safe:** GET is meant to be safe by the HTTP
spec. The agent's classifier sees GET and flags reversible.

**Why it is actually irreversible:** Some "read" endpoints trigger
server-side work: a view counter, a read-receipt webhook, a rate-limit
decrement that counts against a quota even on 4xx. LLM vendor APIs that
"read" a model's response still consume tokens. Authentication-adjacent
reads (`/auth/verify`) may log attempts and contribute to lockout counters.

**Pattern example:**
```python
# Looks safe. Increments a read counter and may trigger a webhook.
requests.get("https://api.example.com/orders/42")

# Consumes tokens. Not free.
openai.chat.completions.create(...)
```

### 3. Cached writes that flush asynchronously

**What it looks like:** `cache.set(key, value)`, `redis.set(...)`.

**Why agents classify it as safe:** Cache writes are local to the agent's
process or to a local redis. Easy to clean up.

**Why it is actually irreversible:** Caches in production often replicate.
Multi-region redis, CDN edge caches, application caches with write-through
to a database. By the time the agent's function returns, the value has
propagated to replicas the agent cannot enumerate, let alone delete.

**Pattern example:**
```python
cdn.purge(url)         # flushes every edge globally — not local
cache.invalidate(key)  # triggers downstream invalidation hooks
```

### 4. Operations that appear local but replicate

**What it looks like:** File write to `/var/log/app.log`.

**Why agents classify it as safe:** It's a local file.

**Why it is actually irreversible:** `/var/log/` is often scraped by a
log-shipping agent (fluentd, vector, filebeat) that sends the bytes to a
remote log aggregator. Deleting the local file does not delete the
remote record. The same pattern holds for files in watched directories,
NFS mounts that replicate, and anything in a git worktree that later gets
committed.

### 5. File operations on symlinked paths

**What it looks like:** `shutil.rmtree("./build")`.

**Why agents classify it as safe:** The agent assumes `./build` is a
regular directory inside the workspace.

**Why it is actually irreversible:** If `./build` is a symlink to
`/var/shared/builds`, `rmtree` follows the link and deletes the shared
directory. Python 3.12 makes rmtree symlink-aware for the top-level path,
but files inside a directory that contain symlinks to external paths can
still be affected. Always resolve the real path before destructive ops.

**Pattern example:**
```python
# Safer:
real = os.path.realpath(target)
if not real.startswith(WORKSPACE_ROOT):
    raise RuntimeError("refusing to delete outside workspace")
```

### 6. Database reads inside transactions that escalate lock level

**What it looks like:** `SELECT * FROM users WHERE id = 42 FOR UPDATE`.

**Why agents classify it as safe:** It's a SELECT. Reads are reversible.

**Why it is actually irreversible:** `FOR UPDATE` takes a row-level
exclusive lock. Depending on isolation level and table access patterns,
this can escalate to a page-level or table-level lock, blocking every
other writer and some readers until the transaction commits. Holding the
lock has observable effects on other services: their writes queue up,
their timeouts fire, their circuit breakers trip.

### 7. Webhook registrations

**What it looks like:** `stripe.WebhookEndpoint.create(url=..., events=[...])`.

**Why agents classify it as safe:** It's a configuration call.

**Why it is actually irreversible:** Once registered, the webhook begins
receiving events. Those events may be processed by downstream systems that
assume their consumer exists. Deregistering a webhook after events have
fired does not un-process them. If the receiver was misconfigured, each
delivery triggered real work.

### 8. Rate limit consumption on failure

**What it looks like:** `requests.post(url, ...)` that fails with a 4xx.

**Why agents classify it as safe:** The call failed. No state changed
on the server.

**Why it is actually irreversible:** Most rate limiters count the attempt,
not the outcome. Failed auth attempts burn through the quota. A script that
retries on failure can exhaust the hour's quota and lock the agent out of
every other call, some of which may have been critical. The quota
consumption is itself a persistent state change.

### 9. Soft-delete cascades

**What it looks like:** `DELETE /api/projects/42` on an API that docs say
implements soft-delete with a 30-day recovery window.

**Why agents classify it as safe:** Recovery is documented.

**Why it is actually irreversible:** Soft-deletes often trigger synchronous
side effects: webhooks fire to notify integrators, cached indexes update,
search systems remove the record. After the TTL, hard-delete runs and
cascades to child records that may not have the same recovery window. Some
systems cascade immediately and only soft-delete the root.

### 10. Audit log writes

**What it looks like:** `audit_log.record(action="...")`.

**Why agents classify it as safe:** Audit logs are write-only. They can't
harm anything.

**Why it is actually irreversible:** The audit log entry *is* the
irreversible action in regulated domains. Once written, a compliance
system may auto-report to an external regulator, a SIEM may page an
on-call engineer, a tamper-evident store may refuse any subsequent change.
In healthcare and finance, an audit log entry is often the legal record
of the event.

## Partially reversible actions and their windows

- **Uncommitted database transactions:** reversible until `COMMIT`. Window:
  transaction duration. Rollback is free.
- **Message queues with delayed consumers:** reversible if you can delete
  the message before any consumer reads it. Window: seconds, usually.
- **Outbound email with provider cancel window:** some providers expose a
  short "cancel send" API. Window: seconds to minutes.
- **Object storage with versioning:** overwrites and deletes are restorable.
  Window: until the version is explicitly expired or the versioning policy
  garbage-collects it.
- **Git operations against a local repo:** `reflog` usually saves you.
  Window: `gc.reflogExpire` (default 90 days).
- **Kubernetes rollout:** `kubectl rollout undo` can revert within revision
  history. Window: size of revision history (default 10).

None of these windows justify skipping the gate. They justify a *less*
severe response after execution, not skipping the pre-execution check.

## What "reversible" actually means

An action is reversible only if **all** of the following hold:

1. The agent can restore the prior state with tools it already has.
2. No third party has observed or acted on the changed state.
3. No quota, rate limit, or budget has been consumed that cannot be
   restored.
4. Restoration does not require notifying a human or waiting beyond the
   session.

If any of these fail: treat it as irreversible. Run the gate.
