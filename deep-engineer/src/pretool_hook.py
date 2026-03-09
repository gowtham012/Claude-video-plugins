#!/usr/bin/env python3
"""
PreToolUse hook — runs before Write and Edit tool calls.
BLOCKS implementation code during pre-TDD phases.
Allows test code during TDD phase.
This is the real enforcement mechanism — Claude literally cannot
write implementation files when it shouldn't.
Uses stdlib only.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional


def _get_current_phase(task_file: Path) -> Optional[str]:
    """Extract the current phase from current-task.md frontmatter."""
    if not task_file.exists():
        return None
    for line in task_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("phase:"):
            return line.split(":", 1)[1].strip()
    return None


def _is_test_file(file_path: str) -> bool:
    """Check if a file path looks like a test file."""
    path_lower = file_path.lower()
    test_indicators = [
        "test_", "_test.", ".test.", ".spec.",
        "/tests/", "/test/", "/__tests__/", "/spec/",
        "conftest", "test_helper", "spec_helper",
        "_test.go", "_test.rs",
    ]
    return any(ind in path_lower for ind in test_indicators)


def _is_config_or_meta_file(file_path: str) -> bool:
    """Check if a file is configuration/metadata (always allowed)."""
    path_lower = file_path.lower()
    config_indicators = [
        "deep-engineer/", "current-task.md", "log.jsonl",
        ".json", ".toml", ".yaml", ".yml", ".cfg", ".ini",
        ".env", ".gitignore", "makefile", "dockerfile",
        "readme", "license", "changelog",
    ]
    return any(ind in path_lower for ind in config_indicators)


def _log_violation(cwd: str, phase: str, file_path: str, tool: str) -> None:
    """Log a violation to log.jsonl."""
    try:
        from datetime import datetime, timezone
        log_file = Path(cwd) / "deep-engineer" / "log.jsonl"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        entry = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "pretool_block",
            "phase": phase,
            "tool": tool,
            "file": file_path,
            "warning": f"Blocked {tool} on '{file_path}' during '{phase}' phase",
        })
        with log_file.open("a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except Exception:
        return

    cwd = data.get("cwd") or os.getcwd()
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    task_file = Path(cwd) / "deep-engineer" / "current-task.md"
    phase = _get_current_phase(task_file)

    if phase is None:
        # No active task — allow everything
        return

    # Extract file path from tool input
    file_path = ""
    if tool_name == "Write":
        file_path = tool_input.get("file_path", "")
    elif tool_name == "Edit":
        file_path = tool_input.get("file_path", "")

    if not file_path:
        return  # No file path to check, allow

    # Config/meta files are always allowed
    if _is_config_or_meta_file(file_path):
        return

    # Phase-based enforcement
    if phase in ("generalize", "hypothetical-testing"):
        # BLOCK all code writing (test or implementation)
        _log_violation(cwd, phase, file_path, tool_name)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"BLOCKED: Cannot write code during '{phase}' phase. "
                    f"You are trying to write to '{file_path}' but you have not "
                    "completed hypothetical testing yet. "
                    "Finish Phases 1-2 (generalize + hypothetical testing) first, "
                    "then move to Phase 3 (TDD) to write tests."
                ),
            }
        }
        print(json.dumps(output), flush=True)
        return

    if phase == "tdd-write-tests":
        # Allow test files, BLOCK implementation files
        if _is_test_file(file_path):
            return  # Allowed

        _log_violation(cwd, phase, file_path, tool_name)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"BLOCKED: Cannot write implementation code during 'tdd-write-tests' phase. "
                    f"'{file_path}' does not look like a test file. "
                    "Only test files are allowed in this phase. "
                    "Test files should contain: test_, _test, .test., .spec., "
                    "or be in a tests/test/__tests__/spec directory. "
                    "Write all tests first, then move to Phase 4 (implement)."
                ),
            }
        }
        print(json.dumps(output), flush=True)
        return

    # implement and verify phases — allow everything
    return


if __name__ == "__main__":
    main()
