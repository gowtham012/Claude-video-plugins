---
name: clear
description: Reset the project context back to a blank template. Always confirms with the user before proceeding. Archives the existing log as a .bak file.
disable-model-invocation: true
allowed-tools: mcp__carry-forward__clear_context
argument-hint: (no arguments needed)
---

First, ask the user to confirm:

> "This will clear all saved context for this project (the log will be archived as a timestamped `.bak` file). Are you sure? (yes/no)"

If the user confirms (yes / y / yep / sure):
- Call the `mcp__carry-forward__clear_context` tool with `cwd` = current working directory
- Report the result verbatim, including the archive filename if a backup was created
- Tell the user: "Context cleared. Use `/carry-forward:save` after your next session to start fresh."

If the user declines: acknowledge and do nothing.
