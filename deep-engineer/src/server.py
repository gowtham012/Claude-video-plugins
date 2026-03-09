#!/usr/bin/env python3
"""
deep-engineer MCP server (FastMCP).
7 tools: setup_project, save_task, read_task, update_phase,
         complete_task, check_warnings, detect_test_runner.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("deep-engineer")

PHASES = ["generalize", "hypothetical-testing", "tdd-write-tests", "implement", "verify"]

PHASE_ORDER = {phase: i for i, phase in enumerate(PHASES)}

TASK_TEMPLATE = """\
---
created: {ts}
phase: generalize
status: active
---

## Problem (as stated by user)
{problem}

## Generalized Problem
{general_problem}

## Scenarios
{scenarios}

## Approach
{approach}

## Phase Log
- [{ts}] Task created — phase: generalize
"""

CLAUDE_MD_IMPORT = "@deep-engineer/current-task.md"

# Test runner detection: (manifest file, indicator, test command)
TEST_RUNNERS = [
    # JS/TS — vitest
    ("vitest.config.ts", None, "npx vitest run"),
    ("vitest.config.js", None, "npx vitest run"),
    ("vitest.config.mts", None, "npx vitest run"),
    # JS/TS — jest
    ("jest.config.ts", None, "npx jest"),
    ("jest.config.js", None, "npx jest"),
    ("jest.config.mjs", None, "npx jest"),
    # JS/TS — package.json with test script
    ("package.json", "test", "npm test"),
    # Python — pytest
    ("pyproject.toml", "pytest", "pytest"),
    ("pytest.ini", None, "pytest"),
    ("setup.cfg", "pytest", "pytest"),
    ("conftest.py", None, "pytest"),
    # Python — unittest (fallback)
    ("pyproject.toml", None, "python -m pytest"),
    # Rust
    ("Cargo.toml", None, "cargo test"),
    # Go
    ("go.mod", None, "go test ./..."),
    # Ruby
    ("Gemfile", "rspec", "bundle exec rspec"),
    ("Rakefile", None, "bundle exec rake test"),
    # Java — Maven
    ("pom.xml", None, "mvn test"),
    # Java — Gradle
    ("build.gradle", None, "gradle test"),
    ("build.gradle.kts", None, "gradle test"),
    # Elixir
    ("mix.exs", None, "mix test"),
    # PHP
    ("phpunit.xml", None, "vendor/bin/phpunit"),
    ("phpunit.xml.dist", None, "vendor/bin/phpunit"),
]


def _task_dir(cwd: str) -> Path:
    return Path(cwd) / "deep-engineer"


def _task_file(cwd: str) -> Path:
    return _task_dir(cwd) / "current-task.md"


def _log_file(cwd: str) -> Path:
    return _task_dir(cwd) / "log.jsonl"


def _history_dir(cwd: str) -> Path:
    return _task_dir(cwd) / "history"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_current_phase(cwd: str) -> str | None:
    """Extract the current phase from current-task.md frontmatter."""
    task_file = _task_file(cwd)
    if not task_file.exists():
        return None
    for line in task_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("phase:"):
            return line.split(":", 1)[1].strip()
    return None


def _count_scenarios(scenarios: str) -> int:
    """Count numbered items in a scenario list."""
    return len(re.findall(r"^\s*\d+[\.\)]\s+", scenarios, re.MULTILINE))


@mcp.tool()
def setup_project(cwd: str) -> str:
    """
    One-time setup for a project.
    Creates deep-engineer/ directory and appends @import line to CLAUDE.md
    so the current task auto-loads every session.
    """
    task_dir = _task_dir(cwd)
    task_dir.mkdir(parents=True, exist_ok=True)
    _history_dir(cwd).mkdir(parents=True, exist_ok=True)

    # Ensure log.jsonl exists
    log = _log_file(cwd)
    if not log.exists():
        log.touch()

    # Append @import to CLAUDE.md if not already present
    claude_md = Path(cwd) / "CLAUDE.md"
    already_imported = False
    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")
        already_imported = CLAUDE_MD_IMPORT in content

    if not already_imported:
        with claude_md.open("a", encoding="utf-8") as f:
            f.write(f"\n{CLAUDE_MD_IMPORT}\n")
        claude_md_status = "Added @import to CLAUDE.md."
    else:
        claude_md_status = "CLAUDE.md already has the @import line."

    return (
        f"deep-engineer set up in {task_dir}.\n"
        f"{claude_md_status}\n"
        "Restart Claude Code for auto-loading to take effect."
    )


@mcp.tool()
def save_task(
    cwd: str,
    problem: str,
    general_problem: str,
    scenarios: str,
    approach: str,
) -> str:
    """
    Saves Phase 1+2 output: the user's problem, the generalized version,
    scenarios list, and the proposed approach. Creates current-task.md.

    ENFORCED: scenarios must contain at least 5 numbered items.
    """
    # Validate scenario count
    count = _count_scenarios(scenarios)
    if count < 5:
        return (
            f"REJECTED: Only {count} scenarios provided. "
            "You MUST list at least 5 scenarios before proceeding. "
            "Include: (1) the user's exact case, (2) a different valid case, "
            "(3) an edge case, (4) a failure/error case, (5) a scale or boundary case. "
            "Call save_task again with at least 5 numbered scenarios."
        )

    task_dir = _task_dir(cwd)
    task_dir.mkdir(parents=True, exist_ok=True)

    ts = _now_iso()
    content = TASK_TEMPLATE.format(
        ts=ts,
        problem=problem.strip(),
        general_problem=general_problem.strip(),
        scenarios=scenarios.strip(),
        approach=approach.strip(),
    )

    _task_file(cwd).write_text(content, encoding="utf-8")

    # Log the event
    record = json.dumps({
        "ts": ts,
        "event": "task_created",
        "phase": "generalize",
        "scenario_count": count,
    })
    with _log_file(cwd).open("a", encoding="utf-8") as f:
        f.write(record + "\n")

    return (
        f"Task saved to {_task_file(cwd)}. Phase: generalize. "
        f"Scenarios: {count} registered."
    )


@mcp.tool()
def read_task(cwd: str) -> str:
    """
    Returns the current task state (current-task.md content)
    plus the last 10 log entries and any active warnings.
    """
    task_file = _task_file(cwd)
    if not task_file.exists():
        return "No active task. Use save_task to start one."

    content = task_file.read_text(encoding="utf-8")

    log = _log_file(cwd)
    recent_entries: list[str] = []
    warnings: list[str] = []
    if log.exists():
        lines = [
            l.strip()
            for l in log.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        for line in lines[-20:]:
            try:
                entry = json.loads(line)
                event = entry.get("event", "")
                phase = entry.get("phase", "")
                result = entry.get("result", "")
                warning = entry.get("warning", "")
                recent_entries.append(
                    f"[{entry.get('ts', '')}] {event} — {phase} {result}"
                )
                if warning:
                    warnings.append(f"WARNING: {warning}")
            except Exception:
                pass

    log_section = "\n".join(recent_entries[-10:]) if recent_entries else "(no entries yet)"
    warning_section = ""
    if warnings:
        warning_section = (
            "\n\n---\n## ACTIVE WARNINGS\n"
            + "\n".join(warnings[-5:])
            + "\n\nYou MUST address these warnings before proceeding."
        )

    return f"{content}\n\n---\n## Recent Log\n{log_section}{warning_section}"


@mcp.tool()
def update_phase(cwd: str, phase: str, result: str) -> str:
    """
    Moves the task to the next phase and logs the result.
    Valid phases: generalize, hypothetical-testing, tdd-write-tests, implement, verify.

    ENFORCED: Phases must progress in order. You cannot skip phases or go backwards.
    """
    if phase not in PHASES:
        return f"REJECTED: Invalid phase '{phase}'. Valid phases: {', '.join(PHASES)}"

    task_file = _task_file(cwd)
    if not task_file.exists():
        return "REJECTED: No active task. Use save_task first."

    # Enforce phase ordering
    current_phase = _get_current_phase(cwd)
    if current_phase and current_phase in PHASE_ORDER:
        current_idx = PHASE_ORDER[current_phase]
        target_idx = PHASE_ORDER[phase]

        if target_idx < current_idx:
            return (
                f"REJECTED: Cannot go backwards from '{current_phase}' to '{phase}'. "
                "Phases must progress forward: "
                + " → ".join(PHASES)
            )

        if target_idx > current_idx + 1:
            next_phase = PHASES[current_idx + 1]
            return (
                f"REJECTED: Cannot skip from '{current_phase}' to '{phase}'. "
                f"You must complete '{next_phase}' first. "
                "Phase order: " + " → ".join(PHASES)
            )

    content = task_file.read_text(encoding="utf-8")

    # Update phase in frontmatter
    lines = content.splitlines()
    updated_lines: list[str] = []
    for line in lines:
        if line.startswith("phase:"):
            updated_lines.append(f"phase: {phase}")
        else:
            updated_lines.append(line)

    ts = _now_iso()
    updated_lines.append(f"- [{ts}] Phase: {phase} — {result.strip()[:300]}")

    task_file.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")

    # Log the event
    record = json.dumps({
        "ts": ts,
        "event": "phase_update",
        "phase": phase,
        "result": result.strip()[:300],
    })
    with _log_file(cwd).open("a", encoding="utf-8") as f:
        f.write(record + "\n")

    # Return next-phase guidance
    current_idx = PHASE_ORDER[phase]
    if current_idx < len(PHASES) - 1:
        next_phase = PHASES[current_idx + 1]
        guidance = f" Next phase: '{next_phase}'."
    else:
        guidance = " All phases complete. Call complete_task."

    return f"Phase updated to '{phase}'. Result logged.{guidance}"


@mcp.tool()
def complete_task(cwd: str) -> str:
    """
    Marks the current task as done. Archives current-task.md to history/.

    ENFORCED: Task must be in 'verify' phase to complete.
    """
    task_file = _task_file(cwd)
    if not task_file.exists():
        return "REJECTED: No active task to complete."

    # Enforce: must be in verify phase
    current_phase = _get_current_phase(cwd)
    if current_phase != "verify":
        return (
            f"REJECTED: Cannot complete task in '{current_phase}' phase. "
            "You must reach 'verify' phase with all tests passing first. "
            "Phase order: " + " → ".join(PHASES)
        )

    content = task_file.read_text(encoding="utf-8")
    content = content.replace("status: active", "status: completed")

    ts = _now_iso()
    content += f"\n- [{ts}] Task completed\n"

    # Archive
    history = _history_dir(cwd)
    history.mkdir(parents=True, exist_ok=True)
    ts_safe = ts.replace(":", "-").replace(".", "-")
    archive_file = history / f"task-{ts_safe}.md"
    archive_file.write_text(content, encoding="utf-8")

    # Clear current task
    task_file.unlink()

    # Log the event
    record = json.dumps({"ts": ts, "event": "task_completed"})
    with _log_file(cwd).open("a", encoding="utf-8") as f:
        f.write(record + "\n")

    return f"Task completed and archived to {archive_file.name}."


@mcp.tool()
def check_warnings(cwd: str) -> str:
    """
    Returns any discipline warnings from the stop hook log.
    Call this before starting each phase to check for violations.
    Returns 'CLEAN' if no warnings, or lists violations that must be addressed.
    """
    log = _log_file(cwd)
    if not log.exists():
        return "CLEAN: No log file found."

    warnings: list[str] = []
    lines = [
        l.strip()
        for l in log.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]

    for line in lines[-30:]:
        try:
            entry = json.loads(line)
            warning = entry.get("warning")
            if warning:
                warnings.append(f"[{entry.get('ts', '')}] {warning}")
        except Exception:
            pass

    if not warnings:
        return "CLEAN: No discipline violations detected."

    return (
        f"VIOLATIONS DETECTED ({len(warnings)}):\n"
        + "\n".join(warnings)
        + "\n\nYou MUST address these before proceeding. "
        "If you wrote implementation code before tests, delete it and write tests first."
    )


@mcp.tool()
def detect_test_runner(cwd: str) -> str:
    """
    Auto-detects the project's test runner by scanning for config files.
    Returns the test command to use, the test directory convention,
    and framework-specific guidance.
    """
    root = Path(cwd)
    detected: list[dict[str, str]] = []

    for manifest, indicator, command in TEST_RUNNERS:
        manifest_path = root / manifest
        if not manifest_path.exists():
            continue

        if indicator is not None:
            try:
                content = manifest_path.read_text(encoding="utf-8")
                if indicator not in content:
                    continue
            except Exception:
                continue

        detected.append({
            "manifest": manifest,
            "command": command,
        })

    if not detected:
        return (
            "NO TEST RUNNER DETECTED.\n"
            "No recognized test framework configuration found.\n"
            "You must set up a test framework before Phase 3 (TDD).\n\n"
            "Common options:\n"
            "- Python: pip install pytest → pytest\n"
            "- JavaScript: npm install -D vitest → npx vitest run\n"
            "- Go: go test ./... (built-in)\n"
            "- Rust: cargo test (built-in)"
        )

    # Find test directories
    test_dirs: list[str] = []
    for d in ["tests", "test", "__tests__", "spec", "src/test", "src/__tests__"]:
        if (root / d).is_dir():
            test_dirs.append(d)

    # Use the first (highest priority) match
    primary = detected[0]
    test_dir_info = ", ".join(test_dirs) if test_dirs else "(no test directory yet — create one)"

    result = (
        f"TEST RUNNER: {primary['command']}\n"
        f"Detected via: {primary['manifest']}\n"
        f"Test directories: {test_dir_info}\n"
    )

    if len(detected) > 1:
        alts = [d["command"] for d in detected[1:3]]
        result += f"Alternatives: {', '.join(alts)}\n"

    # Framework-specific test file naming conventions
    cmd = primary["command"]
    if "pytest" in cmd:
        result += "\nConventions: test_*.py files, def test_*() functions, tests/ directory"
    elif "vitest" in cmd or "jest" in cmd:
        result += "\nConventions: *.test.ts / *.spec.ts files, describe/it/expect, __tests__/ directory"
    elif "cargo test" in cmd:
        result += "\nConventions: #[cfg(test)] mod tests, #[test] fn, or tests/ directory for integration"
    elif "go test" in cmd:
        result += "\nConventions: *_test.go files, func Test*(t *testing.T)"
    elif "rspec" in cmd:
        result += "\nConventions: *_spec.rb files, describe/it/expect, spec/ directory"
    elif "phpunit" in cmd:
        result += "\nConventions: *Test.php files, public function test*(), tests/ directory"

    return result


if __name__ == "__main__":
    mcp.run()
