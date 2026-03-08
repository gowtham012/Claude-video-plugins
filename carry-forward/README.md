# carry-forward

A Claude Code plugin that persists session context across conversations — zero friction.

## Problem

Every new Claude Code session loses all context: what you were building, decisions made, files touched, next steps. You re-explain the same things every day.

## Solution

carry-forward bridges sessions automatically:
- **Auto-saves** after every Claude response (Stop hook → `log.jsonl`)
- **Auto-loads** at every session start (CLAUDE.md `@import` → `context.md`)
- **Rich manual save** with `/carry-forward:save`

---

## Prerequisites

- Claude Code **1.0.33 or later** (`claude --version`)
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) — used to run the MCP server with zero global installs

Install `uv`:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Install

### From GitHub (recommended)

Inside Claude Code:

```
/plugin marketplace add gowtham012/Claude-plugins
/plugin install carry-forward@Claude-plugins
```

### Dev / local testing

```bash
claude --plugin-dir /path/to/carry-forward
```

This loads the plugin for the current session only — use this while developing, not for day-to-day use.

---

## One-time project setup

After installing, open Claude Code in any project and run:

```
/carry-forward:setup
```

Then **restart Claude Code**. From that point on, `context.md` loads automatically at every session start via the `@import` in `CLAUDE.md` — no command needed.

---

## Skills

| Skill | When to use |
|-------|-------------|
| `/carry-forward:setup` | Once per project — wires up CLAUDE.md auto-load |
| `/carry-forward:save` | End of session — writes structured summary to `context.md` |
| `/carry-forward:load` | Mid-session — review saved context on demand |
| `/carry-forward:clear` | Start fresh — resets context, archives log |

---

## How it works

```
Session 1                    Disk                     Session 2
─────────────────────        ─────────────────────    ─────────────────────
/carry-forward:setup    →    CLAUDE.md gets           Open Claude Code
                             @carry-forward/          Claude reads context.md
... work ...                 context.md               automatically at startup

Stop hook fires         →    log.jsonl grows          Claude already knows:
after every response         (auto, silent)           - Current task
                                                      - Files in play
/carry-forward:save     →    context.md updated       - Decisions made
                             (rich summary)           - Next steps

Close Claude Code                                     Just say "continue"
```

---

## Storage

Files are created inside your project:

```
your-project/
├── CLAUDE.md                           ← @carry-forward/context.md added here
└── carry-forward/
    ├── context.md                      ← auto-loaded every session start
    ├── log.jsonl                       ← auto-appended after every response
    └── log.2026-03-07T10-30.jsonl.bak  ← created by /clear
```

---

## Update

```
/plugin marketplace update carry-forward
```

---

## Uninstall

```
/plugin uninstall carry-forward@Claude-plugins
```

---

## License

MIT
