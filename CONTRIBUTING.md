# Contributing to verified-refusal

Verified-refusal is a behavioral contract for irreversible agent
actions. Contributions land in three buckets: protocol changes,
classifier improvements, and new platform integrations. Each has a
slightly different bar.

## Protocol changes

`SKILL.md`, `standing-order.md`, and `references/irreversible.md` are
the protocol surface. Changes here affect every platform and every
agent. Open an issue first to discuss; we want a stable contract more
than we want a complete one.

If you change `SKILL.md` (the platform-neutral contract), also update
the OpenClaw overlay at `integrations/openclaw/SKILL.md` so they don't
drift. The contract test enforces structure but not content equality.

## Classifier improvements

`references/irreversible.md` is the source of truth for what counts as
irreversible. If the classifier in `scripts/classify.py` misses a
category you care about — POSTs without idempotency keys, lock-
escalating reads, soft-deletes that hard-delete after a TTL — open a
PR with:

1. The category added to `references/irreversible.md` with the subtle
   case explained.
2. The pattern detection added to `scripts/classify.py`.
3. A test in `tests/test_classify.py` covering both the positive and
   negative cases.

## Adding a new platform integration

This is the most welcome contribution. The protocol is universal; new
integrations make it actually usable.

1. Read [`integrations/README.md`](./integrations/README.md) — the
   contract for what every integration file must contain.
2. Pick a peer file as your reference. `integrations/openclaw.md` is
   the most complete; `integrations/claude-code.md` shows how to wire a
   platform that uses `.claude/commands/` rather than a manifest.
3. Create `integrations/<your-platform>.md` with the six canonical H2
   headers in order: Install, Reload, Verify, Standing order, Audit log
   path, Slash commands.
4. If your platform needs a platform-shaped manifest (a `SKILL.md` with
   platform-specific frontmatter), add it under
   `integrations/<your-platform>/`. See
   `integrations/openclaw/SKILL.md` for the pattern.
5. Verify the contract test passes: `pytest tests/test_integrations.py`.
6. Add an entry to the "Currently shipped" table in
   `integrations/README.md` and the integration links list in `README.md`.

## Tests

```bash
pytest tests/                         # all tests
pytest tests/test_integrations.py     # integration contract only
pytest --cov=scripts --cov=templates  # with coverage
```

Existing tests should pass. New code paths need tests at the same level
of scrutiny as the existing suite (unit + integration where the script
touches the filesystem).

## Pre-commit on this repo

If you want the hook running on your own commits to verified-refusal
itself, add a `.pre-commit-config.yaml` at repo root:

```yaml
repos:
  - repo: .
    rev: HEAD
    hooks:
      - id: vr-scan
```

Then `pre-commit install`. The hook invokes `scripts/scan.py` against
staged files only.

## Commit style

Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`,
`chore:`. The repo's own commits are the reference style.
