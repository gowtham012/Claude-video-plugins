# deep-engineer

A Claude Code plugin that forces a disciplined engineering loop: **generalize → scenario-test → TDD → implement → verify**.

## The Problem

Claude Code often:
- Hardcodes solutions for the user's specific example instead of solving generally
- Skips edge cases and scenarios the user didn't mention
- Writes implementation before tests
- Doesn't think through approaches before coding

## The Solution

The `/deep-engineer:solve` skill forces Claude through 5 phases with **mechanical enforcement** — not just instructions, but tools and hooks that physically prevent shortcuts.

### Phase 1: Generalize
Restate the problem as a **general** problem. List 5+ scenarios including edge cases the user didn't mention. The `save_task` tool **rejects fewer than 5 scenarios**.

### Phase 2: Hypothetical Testing
Walk through the proposed approach mentally against ALL scenarios. Document pass/fail in a table. No code written yet. The **PreToolUse hook blocks Write/Edit** during this phase.

### Phase 3: TDD — Write Tests First
Write tests covering ALL scenarios. Tests must fail initially (red). The **PreToolUse hook blocks non-test files** — only files matching test patterns are allowed.

### Phase 4: Implement
Write code to pass ALL tests. No hardcoding — the solution must be general.

### Phase 5: Verify Loop
Run tests. If any fail → fix and re-run. Loop until ALL pass. The `complete_task` tool **rejects completion unless in verify phase**.

## Enforcement Mechanisms

| Mechanism | What it does |
|-----------|-------------|
| **PreToolUse hook** | Blocks Write/Edit tools during wrong phases. Claude literally cannot create implementation files before tests. |
| **Stop hook** | Outputs `additionalContext` JSON after every response — Claude sees phase reminders and warnings in its next turn. |
| **`save_task` validation** | Rejects fewer than 5 numbered scenarios. |
| **`update_phase` ordering** | Rejects phase skipping and backward movement. |
| **`complete_task` gating** | Rejects completion unless task is in verify phase. |
| **`check_warnings` feedback** | Surfaces violations from log.jsonl back to Claude before each phase transition. |

## Installation

```bash
claude plugin add gowtham012/Claude-plugins/deep-engineer
```

## Usage

### One-time setup
```
/deep-engineer:setup
```

### Start the engineering loop
```
/deep-engineer:solve Fix the date parser to handle ISO 8601 dates
```

### Check status mid-task
```
/deep-engineer:status
```

### Resume after session restart
Just run `/deep-engineer:solve` again — it detects the active task phase and resumes from where you left off.

## Skills

| Skill | Description |
|-------|-------------|
| `/deep-engineer:setup` | One-time project setup |
| `/deep-engineer:solve` | Main engineering loop (5 phases) |
| `/deep-engineer:status` | Check current loop status, warnings, test runner |

## MCP Tools

| Tool | Description |
|------|-------------|
| `setup_project` | Creates `deep-engineer/` dir, adds CLAUDE.md import |
| `save_task` | Saves problem, scenarios (min 5), approach |
| `read_task` | Returns current task state + warnings |
| `update_phase` | Moves to next phase (enforces order) |
| `complete_task` | Archives task (requires verify phase) |
| `check_warnings` | Returns discipline violations from log |
| `detect_test_runner` | Auto-detects test framework and command |

## Test Runner Support

Auto-detects 20+ test frameworks:

| Language | Frameworks |
|----------|-----------|
| Python | pytest, unittest |
| JavaScript/TypeScript | vitest, jest, mocha |
| Go | go test (built-in) |
| Rust | cargo test (built-in) |
| Ruby | rspec, rake test |
| Java | maven, gradle |
| PHP | phpunit |
| Elixir | mix test |

## Requirements

- Python 3.10+
- `uv` (for MCP server)

## License

MIT
