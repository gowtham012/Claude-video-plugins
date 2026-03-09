---
name: status
description: Check the current engineering loop status — active phase, scenarios covered, warnings, and test runner info.
disable-model-invocation: true
allowed-tools: mcp__deep-engineer__read_task, mcp__deep-engineer__check_warnings, mcp__deep-engineer__detect_test_runner
argument-hint: (no arguments needed)
---

## Current task state (auto-injected)

**Task file exists?**
```
!`test -f deep-engineer/current-task.md && echo "YES — active task" || echo "NO — no active task"`
```

**Warning count:**
```
!`grep -c '"warning"' deep-engineer/log.jsonl 2>/dev/null || echo "0"` warnings in log
```

---

## Instructions

**Step 1:** Call `mcp__deep-engineer__read_task` with `cwd` = current working directory.

If no active task exists, tell the user:

> **No active task.** Start one with `/deep-engineer:solve <problem description>`.

If a task exists, continue to Step 2.

**Step 2:** Call `mcp__deep-engineer__check_warnings` with `cwd` = current working directory.

**Step 3:** Call `mcp__deep-engineer__detect_test_runner` with `cwd` = current working directory.

**Step 4:** Format the response:

> **Active Task Status**
>
> **Phase:** <current phase> (`N` of 5)
> ```
> generalize → hypothetical-testing → tdd-write-tests → implement → verify
>      ✓              ✓                    ◀ YOU ARE HERE
> ```
>
> **Problem (generalized):** <generalized problem statement>
>
> **Scenarios:** <count> defined
> <numbered list of scenarios>
>
> **Test Runner:** <detected command or "not detected">
>
> **Warnings:** <count> — <CLEAN or list of violations>
>
> **Phase Log:**
> <recent phase transitions with timestamps>
>
> **Next action:** <what to do next based on current phase>

For the "Next action", be specific:
- generalize → "List 5+ scenarios and call save_task"
- hypothetical-testing → "Walk through each scenario mentally, document in a table"
- tdd-write-tests → "Write test files, run them, confirm all fail"
- implement → "Write implementation to pass all tests"
- verify → "Run all tests, fix failures, loop until green"
