# Claude Code

Verified-refusal loaded as a Claude Code project rule plus user-scope
slash commands. Claude Code's persistent system context lives in
`CLAUDE.md`; custom slash commands live as Markdown files in
`~/.claude/commands/` (user) or `.claude/commands/` (project).

## Install

Clone to the platform-neutral default. Claude Code does not need a
symlink into a separate skills directory — the integration is the
`CLAUDE.md` append plus the slash command files installed below.

```bash
git clone https://github.com/Tetrahedroned/verified-refusal \
  ~/.vr/skills/verified-refusal
```

Then install the user-scope slash commands (one Markdown file per
command in `~/.claude/commands/`):

```bash
mkdir -p ~/.claude/commands

cat > ~/.claude/commands/vr-scan.md <<'EOF'
---
description: Scan the current workspace for ungated irreversible actions
allowed-tools: ["Bash(python3 ~/.vr/skills/verified-refusal/scripts/scan.py:*)"]
---

Run `python3 ~/.vr/skills/verified-refusal/scripts/scan.py --root .`
in the project root. Summarize ungated irreversibles by priority and
suggest `/vr-wrap` calls for the top items.
EOF

cat > ~/.claude/commands/vr-wrap.md <<'EOF'
---
description: Wrap a target function with a verified-refusal gate
argument-hint: <file_path> <function_name>
allowed-tools: ["Bash(python3 ~/.vr/skills/verified-refusal/scripts/wrap.py:*)"]
---

Run `python3 ~/.vr/skills/verified-refusal/scripts/wrap.py --file $1 --function $2`
and report the diff applied.
EOF

cat > ~/.claude/commands/vr-report.md <<'EOF'
---
description: Show the structured report from the last verified-refusal run
allowed-tools: ["Bash(python3 ~/.vr/skills/verified-refusal/scripts/report.py:*)"]
---

Run `python3 ~/.vr/skills/verified-refusal/scripts/report.py --read --n 1`
and show the JSON.
EOF

cat > ~/.claude/commands/vr-status.md <<'EOF'
---
description: Show gated vs ungated coverage in the current workspace
allowed-tools: ["Bash(python3 ~/.vr/skills/verified-refusal/scripts/scan.py:*)"]
---

Run `python3 ~/.vr/skills/verified-refusal/scripts/scan.py --root . --json`
and surface the coverage percent plus the top five ungated functions.
EOF

cat > ~/.claude/commands/vr-log.md <<'EOF'
---
description: Show recent verified-refusal audit log entries
allowed-tools: ["Bash(python3 ~/.vr/skills/verified-refusal/scripts/report.py:*)"]
---

Run `python3 ~/.vr/skills/verified-refusal/scripts/report.py --read --n 50`
and present the entries in reverse chronological order.
EOF
```

## Reload

Start a new Claude Code session, or run `/new` from chat. Slash command
files are picked up on session start.

## Verify

```bash
ls ~/.claude/commands/ | grep '^vr-'
```

Expect five files: `vr-scan.md`, `vr-wrap.md`, `vr-report.md`,
`vr-status.md`, `vr-log.md`. From a Claude Code session, type `/vr-`
and the autocomplete should list all five.

## Standing order

Append the standing order to `CLAUDE.md` so it loads into every session:

```bash
# project scope (this repo only)
cat ~/.vr/skills/verified-refusal/standing-order.md >> ./CLAUDE.md

# user-global scope (every Claude Code session, every project)
cat ~/.vr/skills/verified-refusal/standing-order.md >> ~/.claude/CLAUDE.md
```

## Audit log path

Default: `~/.vr/vr_log.jsonl`

Override, in priority order:

```bash
VR_LOG_PATH=/custom/path/vr_log.jsonl your-command   # canonical
VR_DATA_DIR=/custom/dir your-command                 # log → <dir>/vr_log.jsonl
OPENCLAW_VR_LOG=/custom/path/vr_log.jsonl your-command   # deprecated alias
```

## Slash commands

Installed by the Install step above. The commands are user-scope
(`~/.claude/commands/`), so they're available in every Claude Code
project. To make them project-scope only, write the same Markdown files
to `<project>/.claude/commands/` instead.

| Command      | Backing script                                  |
|--------------|-------------------------------------------------|
| `/vr-scan`   | `scripts/scan.py --root .`                      |
| `/vr-wrap`   | `scripts/wrap.py --file <path> --function <fn>` |
| `/vr-report` | `scripts/report.py --read --n 1`                |
| `/vr-status` | `scripts/scan.py --root . --json`               |
| `/vr-log`    | `scripts/report.py --read --n 50`               |
