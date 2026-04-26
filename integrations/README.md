# Integrations

Verified-refusal is platform-neutral. Each agent harness — OpenClaw,
Claude Code, a generic Python loop — wires the protocol in slightly
differently. This directory is where those wirings live.

## How to add an integration

Create a new file at `integrations/<your-platform>.md` that follows the
contract below. If your platform needs a platform-shaped manifest (a
`SKILL.md` with platform-specific frontmatter, a config TOML, etc.),
add it under `integrations/<your-platform>/`.

## Contract

Every integration file MUST contain these six section headers, in this
order, at H2 depth (`##`):

1. **`## Install`** — clone command, symlink steps, anything needed to
   put the skill where the platform can find it. Must reference
   `~/.vr/skills/verified-refusal` as the canonical clone target.
2. **`## Reload`** — how to make the platform pick up the new skill.
   "Not applicable" is acceptable for harnesses that re-read on every
   process start.
3. **`## Verify`** — a one-liner the user can run that proves the gate
   is loaded. Should be testable without invoking the gate itself.
4. **`## Standing order`** — the platform-specific command that appends
   `standing-order.md` to whatever the platform treats as persistent
   system context (`SOUL.md`, `CLAUDE.md`, system prompt file, etc.).
5. **`## Audit log path`** — the platform's default path, plus the
   override env vars in priority order: `VR_LOG_PATH` (canonical) →
   `VR_DATA_DIR` → `OPENCLAW_VR_LOG` (deprecated alias).
6. **`## Slash commands`** — how the platform exposes `/vr-scan`,
   `/vr-wrap`, `/vr-report`, `/vr-status`, `/vr-log`. If the platform
   doesn't have slash commands, document direct script invocations.

`tests/test_integrations.py` enforces this contract — your PR will fail
CI if any header is missing or out of order.

## Stub status

A file is a "stub" if any required section reads "Stub. Contributions
welcome." or similar. Stubs are allowed to land but should be flagged
in their opening paragraph so users know they're following an unproven
path.

## Currently shipped

| Platform              | Status   | File                                  |
|-----------------------|----------|---------------------------------------|
| OpenClaw              | shipped  | [`openclaw.md`](./openclaw.md)        |
| Claude Code           | shipped  | [`claude-code.md`](./claude-code.md)  |
| Generic Python agent  | shipped  | [`generic-python-agent.md`](./generic-python-agent.md) |

Don't see your platform? Open a PR. The contract above plus a peer
file (`openclaw.md` is the most complete reference) should be enough
to get going.
