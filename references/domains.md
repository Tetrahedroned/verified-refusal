# Domain-specific VR guidance

For each domain: what counts as irreversible, what the gate's pre-checks
should verify, and what the report should record.

## Financial

**Irreversible actions:** payments, captures, refunds, transfers, payouts,
ledger postings, subscription state changes, invoice finalization.

**Pre-checks:**
- Amount is positive and under policy budget.
- Currency matches source account.
- Recipient identity resolved and non-null.
- Idempotency key present and stable (same key for retries).
- No duplicate charge with same key in the last N minutes.
- Customer is not flagged for fraud review.
- Total of this + recent charges is under daily/monthly cap.

**Report must include:** amount, currency, recipient identifier (not PAN),
idempotency key, the policy that was evaluated, the source account.

**Never:** log full card numbers, CVVs, or raw account credentials.

## Infrastructure

**Irreversible actions:** cloud resource create/delete, DNS record
changes, certificate issuance/revocation, IAM role or policy changes,
cluster scaling up or down, database cluster create/delete, backup
deletion, terraform apply, kubernetes apply/delete, snapshot deletion.

**Pre-checks:**
- Target environment is not production (or an explicit prod flag is set).
- Resource name matches expected pattern.
- Change plan has been computed and its diff is bounded (no unexpected
  deletions).
- No concurrent change is in flight on the same resource.
- Backup/snapshot exists for any stateful resource being modified.

**Report must include:** resource identifier, environment, change plan
summary (what will create, modify, delete), the actor, the upstream
ticket or change request.

## Communication

**Irreversible actions:** email send, SMS send, push notification,
webhook delivery, chat message post, voice call, fax.

**Pre-checks:**
- Recipient is not on a suppression or DNC list.
- Recipient has not been contacted within the cooldown window.
- Message content passes policy (profanity, PII, compliance disclaimers).
- Sender identity matches the configured from-address.
- Delivery volume this session is under daily cap.
- Template variables are all resolved (no literal `{{name}}` leaking).

**Report must include:** recipient type and hashed identifier (not raw
phone/email), template id, sender, content hash.

**Never:** log full message bodies containing PII. Hash or truncate.

## Data

**Irreversible actions:** database writes (INSERT/UPDATE/DELETE/
TRUNCATE/DROP), backup deletion, file deletion or overwrite, object
storage deletion, snapshot deletion, restore-from-backup.

**Pre-checks:**
- Statement is one of the expected mutation types.
- WHERE clause is not missing or tautological (`WHERE 1=1`).
- Estimated rows affected is bounded (row count from EXPLAIN or a
  preceding SELECT COUNT).
- Target schema/table is not on an allowlist of "never touch".
- For file ops: real path is inside the workspace; no symlink escapes.
- For S3 ops: bucket has versioning enabled, or a snapshot predates the
  operation.

**Report must include:** statement kind, table, estimated row count,
WHERE summary (hash of predicate tree, not raw values), backup reference.

## AI agents

**Irreversible actions:** tool calls that mutate external state, agent
memory writes that persist to a shared store, API calls to upstream LLM
vendors (consume tokens/quota), vector store upserts, skill install or
update.

**Pre-checks:**
- Tool call is allowed by the agent's policy.
- Token budget for the session has not been exceeded.
- Memory write is scoped to this agent's namespace.
- If the tool is newly loaded: its signature has been reviewed.
- No prompt injection markers detected in inputs from user content.

**Report must include:** tool name, tool version, input hash, token
spend so far this session, memory scope.

## Medical / healthcare

**Irreversible actions:** dosing calculations that feed a dispensing
system, EHR writes, HL7/FHIR mutations, imaging order placement,
patient-facing notifications (appointment reminders, result releases),
access to another patient's record.

**Pre-checks:**
- Patient identity double-verified (name + DOB + MRN, or equivalent).
- Action is within the ordering clinician's scope.
- Dose is within the drug's range and the patient's weight band.
- No contraindication with active medications.
- Consent present for release of results to the patient.
- Audit context includes the clinician of record.

**Report must include:** deidentified patient reference, clinician,
order code, dose band check outcome, consent reference.

**Never:** log PHI in plaintext. Use deidentified references only.

## Legal / regulatory

**Irreversible actions:** regulatory filings, court submissions, patent
filings, trademark filings, tax submissions, signatures on documents,
notarization requests.

**Pre-checks:**
- Document hash matches the approved draft.
- Signatory authority verified.
- Jurisdiction matches the filing system.
- Deadline not missed and not impossibly close.
- Supporting exhibits attached and their hashes verified.

**Report must include:** document hash, signatory, filing system, docket
or reference id (if pre-allocated), deadline, approval chain.

## Authentication

**Irreversible actions:** user creation, password set/rotate, API key
create/rotate/revoke, session termination, OAuth grant, SSO config change,
MFA enrollment or removal, role assignment, access revocation.

**Pre-checks:**
- Requester has authority to perform this operation on the target user.
- Target user identifier resolves to a real account.
- For key rotations: prior key has a documented retirement window.
- For revocations: active sessions are enumerated so affected clients
  can be notified.
- Action does not leave a user without any auth factor.

**Report must include:** target user reference (hashed), action kind,
requester, ticket or request reference. Never log secrets, key material,
or password hashes.
