---
name: setup
description: One-time setup for deep-engineer in the current project. Creates the deep-engineer/ directory and adds CLAUDE.md import.
disable-model-invocation: true
allowed-tools: mcp__deep-engineer__setup_project
argument-hint: (no arguments needed)
---

## Current project state (auto-injected)

**Existing CLAUDE.md content (if any):**
```
!`cat CLAUDE.md 2>/dev/null || echo "(no CLAUDE.md yet — will be created)"`
```

**Existing deep-engineer directory (if any):**
```
!`ls deep-engineer/ 2>/dev/null || echo "(not yet set up)"`
```

---

## Instructions

Call `mcp__deep-engineer__setup_project` with `cwd` = current working directory.

Report the result verbatim.

If CLAUDE.md already existed (shown above), confirm that the `@deep-engineer/current-task.md` line was added without disturbing existing content.

Then tell the user:

> **Setup complete.** Restart Claude Code for the `@deep-engineer/current-task.md` import to take effect — after that, your active task loads automatically at the start of every session.
>
> **Before you start, here's what to expect:**
>
> **WARNING: This plugin changes how Claude approaches tasks.**
>
> - Claude will follow a strict 5-phase loop: **generalize → scenario-test → TDD → implement → verify**
> - Claude will **NOT** write implementation code until tests exist — this is by design
> - You must describe at least **5 scenarios** (including edge cases) before any code is written
> - **Write and Edit tools are physically blocked** during wrong phases (PreToolUse hook denies them)
> - A Stop hook reminds Claude of the current phase after every response
> - Tasks are slower but produce more robust, general solutions — no hardcoding
>
> **Commands:**
> - `/deep-engineer:solve <problem>` — start the engineering loop
> - `/deep-engineer:status` — check which phase you're in
>
> **Requires:** Python 3.10+, `uv` installed
