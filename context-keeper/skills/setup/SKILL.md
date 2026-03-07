---
name: setup
description: One-time setup for carry-forward in the current project. Run this once per project before using save/load/clear.
disable-model-invocation: true
allowed-tools: mcp__carry-forward__setup_project
argument-hint: (no arguments needed)
---

## Current project state (auto-injected)

**Existing CLAUDE.md content (if any):**
```
!`cat CLAUDE.md 2>/dev/null || echo "(no CLAUDE.md yet — will be created)"`
```

**Existing carry-forward directory (if any):**
```
!`ls carry-forward/ 2>/dev/null || echo "(not yet set up)"`
```

---

## Instructions

Call `mcp__carry-forward__setup_project` with `cwd` = current working directory.

Report the result verbatim.

If CLAUDE.md already existed (shown above), confirm that the `@carry-forward/context.md` line was added without disturbing existing content.

Then tell the user:

> **Setup complete.** Restart Claude Code for the `@carry-forward/context.md` import to take effect — after that, your saved context loads automatically at the start of every session.
>
> **Next:** Use `/carry-forward:save` at the end of this session to write your first context snapshot.
