---
name: solve
description: "The main engineering loop. Forces Claude through 5 phases: generalize → scenario-test → TDD → implement → verify. Prevents hardcoded solutions."
disable-model-invocation: true
allowed-tools: mcp__deep-engineer__save_task, mcp__deep-engineer__read_task, mcp__deep-engineer__update_phase, mcp__deep-engineer__complete_task, mcp__deep-engineer__check_warnings, mcp__deep-engineer__detect_test_runner, Read, Edit, Write, Glob, Grep, Bash(*)
argument-hint: <problem description>
---

## Problem from user

$ARGUMENTS

---

## Current project context (auto-injected)

**Language/framework detection:**
```
!`ls package.json pyproject.toml Cargo.toml go.mod pom.xml Gemfile composer.json mix.exs 2>/dev/null || echo "(no package manifest found)"`
```

**Existing test directory:**
```
!`ls -d tests/ test/ __tests__/ spec/ src/test/ src/__tests__/ 2>/dev/null | head -10 || echo "(no test directory found)"`
```

**Active task (if resuming):**
```
!`cat deep-engineer/current-task.md 2>/dev/null || echo "(no active task)"`
```

**Discipline warnings (if any):**
```
!`grep -c '"warning"' deep-engineer/log.jsonl 2>/dev/null || echo "0"` warnings in log
```

---

## RESUME LOGIC — Check this FIRST

Read the "Active task" section above.

**If there IS an active task**, determine the current phase from the frontmatter (`phase: <value>`) and **skip directly to that phase's section below**. Do NOT repeat completed phases. Announce:

> **Resuming task at Phase N: <phase name>**
>
> Previously completed: <list of completed phases from the Phase Log>

**If there is NO active task**, start from Phase 1.

---

## CRITICAL RULES — Read before doing ANYTHING

1. **The user's description is ONE example. Identify the GENERAL pattern.**
2. **You MUST list at least 5 scenarios before writing any code.** The `save_task` tool will REJECT fewer than 5.
3. **You MUST NOT write implementation code before tests.** The stop hook will BLOCK you and print a violation.
4. **Your tests MUST include cases the user did NOT mention.**
5. **If your code uses any value from the user's specific example as a literal/hardcode, you're doing it wrong.**
6. **You MUST run tests and loop until ALL pass.**
7. **You CANNOT skip phases.** The `update_phase` tool enforces sequential order.
8. **Check for warnings** by calling `check_warnings` before each phase transition.

---

## Phase 1: Generalize

Restate the user's problem as a GENERAL problem. Strip away their specific example and find the underlying pattern.

**Think about:**
- What is the general category of this problem?
- What inputs/outputs vary?
- What assumptions should NOT be baked in?

Then list **at least 5 scenarios** the solution must handle:
1. The user's exact case (baseline)
2. A different but valid case
3. An edge case (empty input, boundary value, null, etc.)
4. A failure/error case (invalid input, missing data, permission denied)
5. A scale/performance case OR another boundary case
6. (Optional but encouraged) A concurrency or timing case
7. (Optional but encouraged) A cross-platform or encoding case

**Anti-hardcoding check before saving:**
- Do your scenarios only use the user's example values? Add different ones.
- Would someone reading just the scenarios understand the GENERAL problem? If not, rewrite.

Call `mcp__deep-engineer__save_task` with:
- `cwd` = current working directory
- `problem` = the user's original problem statement (verbatim from $ARGUMENTS)
- `general_problem` = your generalized restatement
- `scenarios` = numbered list of all scenarios (minimum 5 — tool enforces this)
- `approach` = your initial approach idea (1-3 sentences)

If the tool returns "REJECTED", fix the issues and call again.

---

## Phase 2: Hypothetical Testing

Before writing ANY code, mentally walk through your proposed approach against EVERY scenario from Phase 1.

For each scenario, produce a table:

| # | Scenario | Input | Expected Output | Pass/Fail | Notes |
|---|----------|-------|-----------------|-----------|-------|
| 1 | ...      | ...   | ...             | ...       | ...   |

**If ANY scenario fails:**
- Revise your approach
- Re-test mentally against ALL scenarios (not just the failing one)
- Repeat until all scenarios pass in your mental model
- Document what changed and why

First, call `mcp__deep-engineer__check_warnings` with `cwd` = current working directory.
If any violations exist, address them first.

Then call `mcp__deep-engineer__update_phase` with:
- `cwd` = current working directory
- `phase` = "hypothetical-testing"
- `result` = summary including the table results (e.g. "All 6 scenarios pass. Revised approach once: changed X to handle edge case Y.")

---

## Phase 3: TDD — Write Tests First

**Step 3a: Detect the test runner.**

Call `mcp__deep-engineer__detect_test_runner` with `cwd` = current working directory.

Use the returned command and conventions. If no test runner is detected, set one up first (install the standard framework for the language).

**Step 3b: Write test files.**

Cover ALL scenarios from Phase 1. Follow the detected framework's conventions.

**Test quality rules:**
- Each scenario from Phase 1 gets at least one test function/case
- Add edge cases the user DIDN'T mention (at least 2 beyond the original 5)
- Tests must be runnable independently (no test-order dependencies)
- Test names must describe the scenario: `test_parses_iso8601_with_timezone` not `test_parse_1`
- NO implementation code yet — only test files and any necessary test fixtures

**Step 3c: Run the tests.**

Use the detected test command. ALL tests should FAIL (red phase).
If any tests pass before implementation exists, they're not testing real behavior — fix them.

First, call `mcp__deep-engineer__check_warnings` with `cwd` = current working directory.

Then call `mcp__deep-engineer__update_phase` with:
- `cwd` = current working directory
- `phase` = "tdd-write-tests"
- `result` = "Wrote N tests in <file path(s)>, all failing as expected. Test runner: <command>"

---

## Phase 4: Implement

Now write the implementation code to make ALL tests pass.

**Anti-hardcoding checklist (go through each one):**

| Check | Question | Action if YES |
|-------|----------|---------------|
| Literals | Does any value from the user's specific example appear as a literal? | Replace with parameter/variable |
| Scenario #3 | Would this code handle the edge case? | Add handling |
| Scenario #4 | Would this code handle the error case? | Add error handling |
| Scenario #5 | Would this work at scale / boundary? | Optimize or add bounds checking |
| Magic values | Any magic numbers/strings that should be configurable? | Extract to parameter/constant |
| Assumptions | Does the code assume specific input format/type/encoding? | Validate and handle alternatives |

First, call `mcp__deep-engineer__check_warnings` with `cwd` = current working directory.

Then call `mcp__deep-engineer__update_phase` with:
- `cwd` = current working directory
- `phase` = "implement"
- `result` = summary of implementation + which files were created/modified

---

## Phase 5: Verify Loop

**Step 5a: Run ALL tests.**

Use the same test command from Phase 3.

**Step 5b: Evaluate results.**

**If any tests fail:**
1. Read the failure output carefully — understand WHY it failed
2. Fix the **implementation** (NOT the tests, unless the test itself has a bug)
3. Re-run ALL tests (not just the failing one)
4. Repeat until ALL pass
5. Maximum 5 fix iterations — if still failing after 5, stop and report the issue

**If ALL tests pass:**

Call `mcp__deep-engineer__check_warnings` with `cwd` = current working directory.

Then call `mcp__deep-engineer__update_phase` with:
- `cwd` = current working directory
- `phase` = "verify"
- `result` = "All N tests passing. Test command: <command>"

Then call `mcp__deep-engineer__complete_task` with:
- `cwd` = current working directory

---

## Final Report

Tell the user:

> **Engineering loop complete.**
>
> **Problem (user's words):** <original problem>
>
> **Problem (generalized):** <your generalized version>
>
> **Scenarios covered:** <count> scenarios:
> 1. <brief scenario description>
> 2. ...
>
> **Tests:** <count> tests, all passing
> - Test command: `<command>`
> - Test file(s): `<path(s)>`
>
> **Implementation:** `<path(s)>`
>
> **Files created/modified:**
> - `path/to/test_file` — tests (<count> test cases)
> - `path/to/impl_file` — implementation
>
> **Beyond the user's example:** Here's how the solution handles cases you didn't mention:
> - Scenario #3 (<edge case>): <how it's handled>
> - Scenario #4 (<error case>): <how it's handled>
