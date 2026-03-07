# context-keeper

A Claude Code plugin that persists session context across conversations — zero friction.

## Problem

Every new Claude Code session loses all context: what you were building, decisions made, files touched, next steps. You re-explain the same things every day.

## Solution

context-keeper bridges sessions automatically:
- **Auto-saves** after every Claude response (Stop hook → `log.jsonl`)
- **Auto-loads** at every session start (CLAUDE.md `@import` → `context.md`)
- **Rich manual save** with `/context-keeper:save`

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
/plugin marketplace add gowtham/context-keeper
/plugin install context-keeper@context-keeper
```

### Dev / local testing

```bash
claude --plugin-dir /path/to/context-keeper
```

This loads the plugin for the current session only — use this while developing, not for day-to-day use.

---

## One-time project setup

After installing, open Claude Code in any project and run:

```
/context-keeper:setup
```

Then **restart Claude Code**. From that point on, `context.md` loads automatically at every session start via the `@import` in `CLAUDE.md` — no command needed.

---

## Skills

| Skill | When to use |
|-------|-------------|
| `/context-keeper:setup` | Once per project — wires up CLAUDE.md auto-load |
| `/context-keeper:save` | End of session — writes structured summary to `context.md` |
| `/context-keeper:load` | Mid-session — review saved context on demand |
| `/context-keeper:clear` | Start fresh — resets context, archives log |

---

## How it works

```
Session 1                    Disk                     Session 2
─────────────────────        ─────────────────────    ─────────────────────
/context-keeper:setup   →    CLAUDE.md gets           Open Claude Code
                             @context-keeper/         Claude reads context.md
... work ...                 context.md               automatically at startup

Stop hook fires         →    log.jsonl grows          Claude already knows:
after every response         (auto, silent)           - Current task
                                                      - Files in play
/context-keeper:save    →    context.md updated       - Decisions made
                             (rich summary)           - Next steps

Close Claude Code                                     Just say "continue"
```

---

## Storage

Files are created inside your project:

```
your-project/
├── CLAUDE.md                           ← @context-keeper/context.md added here
└── context-keeper/
    ├── context.md                      ← auto-loaded every session start
    ├── log.jsonl                       ← auto-appended after every response
    └── log.2026-03-07T10-30.jsonl.bak  ← created by /clear
```

---

## Update

```
/plugin marketplace update context-keeper
```

---

## Uninstall

```
/plugin uninstall context-keeper@context-keeper
```

---

## License

MIT
