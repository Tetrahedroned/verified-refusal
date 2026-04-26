# OpenClaw

Verified-refusal loaded as an OpenClaw skill. The OpenClaw-shaped
manifest lives at `/integrations/openclaw/SKILL.md`; OpenClaw reads it
directly when you point its skills directory at that overlay folder
(see Install below). The overlay carries the OpenClaw frontmatter and
the `{baseDir}` slash command bindings; the root `SKILL.md` is the
platform-neutral protocol contract.

## Install

Clone the repo to the platform-neutral default, then symlink the
OpenClaw overlay directory into OpenClaw's skills folder:

```bash
git clone https://github.com/Tetrahedroned/verified-refusal \
  ~/.vr/skills/verified-refusal

ln -s ~/.vr/skills/verified-refusal/integrations/openclaw \
  ~/.openclaw/workspace/skills/verified-refusal
```

The symlink target is the `integrations/openclaw/` directory — that's
what OpenClaw treats as the skill root. Its `SKILL.md` references the
shared `scripts/` and `templates/` at repo root via `{baseDir}/../../`.

## Reload

```bash
# from chat
/new

# or restart the gateway
openclaw gateway restart
```

## Verify

```bash
openclaw skills list | grep verified-refusal
```

## Standing order

In OpenClaw, `SOUL.md` holds the instructions the agent carries into
every session. Append the standing order to make the protocol permanent
— every session, every agent, without you thinking about it.

```bash
cat ~/.vr/skills/verified-refusal/standing-order.md \
  >> ~/clawd/SOUL.md
```

## Audit log path

OpenClaw default: `~/.openclaw/vr_log.jsonl` (matches OpenClaw's existing
data dir convention).

Override, in priority order:

```bash
VR_LOG_PATH=/custom/path/vr_log.jsonl your-command   # canonical
VR_DATA_DIR=/custom/dir your-command                 # log → <dir>/vr_log.jsonl
OPENCLAW_VR_LOG=/custom/path/vr_log.jsonl your-command   # deprecated alias
```

The OpenClaw-default path comes from the OpenClaw integration, not from
the gate templates — the templates default to `~/.vr/vr_log.jsonl`. To
match OpenClaw's convention, set `VR_DATA_DIR=$HOME/.openclaw` in your
OpenClaw shell profile, or use `VR_LOG_PATH` directly.

## Slash commands

OpenClaw reads `integrations/openclaw/SKILL.md` and registers these
automatically. `{baseDir}` resolves to the overlay directory; the
`../../` segments reach the shared `scripts/` at repo root:

| Command      | Implementation                                                              |
|--------------|-----------------------------------------------------------------------------|
| `/vr-scan`   | `python3 {baseDir}/../../scripts/scan.py --root .`                          |
| `/vr-wrap`   | `python3 {baseDir}/../../scripts/wrap.py --file <path> --function <name>`   |
| `/vr-report` | `python3 {baseDir}/../../scripts/report.py --read --n 1`                    |
| `/vr-status` | `python3 {baseDir}/../../scripts/scan.py --root . --json`                   |
| `/vr-log`    | `python3 {baseDir}/../../scripts/report.py --read --n 50`                   |
