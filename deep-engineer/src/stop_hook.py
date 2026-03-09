#!/usr/bin/env python3
"""
Stop hook — runs synchronously after every Claude response.
Outputs JSON with additionalContext so Claude sees phase reminders
and violation warnings in its next turn.
Uses stdlib only; never blocks Claude on unexpected errors.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
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


def _get_warnings(log_file: Path) -> list[str]:
    """Get recent warnings from log.jsonl."""
    warnings: list[str] = []
    if not log_file.exists():
        return warnings
    lines = log_file.read_text(encoding="utf-8").splitlines()
    for line in lines[-20:]:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            w = entry.get("warning")
            if w:
                warnings.append(w)
        except Exception:
            pass
    return warnings


PHASE_HINTS = {
    "generalize": (
        "You are in GENERALIZE phase. "
        "Do NOT write any code. Focus on restating the problem generally "
        "and listing 5+ scenarios."
    ),
    "hypothetical-testing": (
        "You are in HYPOTHETICAL TESTING phase. "
        "Do NOT write any code. Walk through each scenario mentally "
        "and document pass/fail in a table."
    ),
    "tdd-write-tests": (
        "You are in TDD phase. "
        "Write ONLY test files. Do NOT write implementation code yet."
    ),
    "implement": (
        "You are in IMPLEMENT phase. "
        "Write implementation code to make all tests pass. "
        "Do NOT hardcode values from the user's specific example."
    ),
    "verify": (
        "You are in VERIFY phase. "
        "Run all tests. Fix failures and re-run until all pass."
    ),
}


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except Exception:
        return

    if data.get("stop_hook_active"):
        return

    cwd = data.get("cwd") or os.getcwd()

    try:
        task_dir = Path(cwd) / "deep-engineer"
        task_file = task_dir / "current-task.md"
        log_file = task_dir / "log.jsonl"

        phase = _get_current_phase(task_file)
        if phase is None:
            # No active task — nothing to enforce
            return

        task_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).isoformat()
        entry = {"ts": ts, "event": "stop_hook", "phase": phase}

        # Build context message for Claude's next turn
        context_parts: list[str] = []

        # Phase reminder
        hint = PHASE_HINTS.get(phase, "")
        if hint:
            context_parts.append(f"[deep-engineer] {hint}")

        # Check for recent warnings
        warnings = _get_warnings(log_file)
        if warnings:
            context_parts.append(
                f"[deep-engineer] WARNINGS ({len(warnings)}): "
                + "; ".join(warnings[-3:])
            )
            entry["warnings_surfaced"] = len(warnings)

        # Log the event
        record = json.dumps(entry)
        with log_file.open("a", encoding="utf-8") as f:
            f.write(record + "\n")

        # Output JSON with additionalContext so Claude sees it
        if context_parts:
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "Stop",
                    "additionalContext": "\n".join(context_parts),
                }
            }
            print(json.dumps(output), flush=True)

    except Exception:
        pass  # Never block Claude on unexpected errors


if __name__ == "__main__":
    main()
