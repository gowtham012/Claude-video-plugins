#!/usr/bin/env python3
"""PostToolUse hook — narrates every Edit/Write and appends to changelog."""
from __future__ import annotations
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path


def _dir(cwd: str) -> Path:
    return Path(cwd) / "diff-narrator"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _regenerate_changelog(cwd: str, limit: int = 30) -> None:
    """Regenerate changelog.md from the last `limit` entries."""
    ef = _dir(cwd) / "entries.jsonl"
    if not ef.exists():
        return
    entries = []
    for line in ef.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            pass

    recent = entries[-limit:]
    lines = [
        "# Diff Narrator — Changelog",
        "",
        f"_Last updated: {_now_iso()}_",
        "",
    ]
    if not recent:
        lines.append("_No changes recorded yet._")
    else:
        for e in reversed(recent):
            ts = e.get("ts", "")
            short_ts = ts[11:19] if len(ts) >= 19 else ts
            fp = e.get("file_path", "unknown")
            ct = e.get("change_type", "modify")
            desc = e.get("description", "")
            lines.append(f"- **[{short_ts}]** `{fp}` ({ct}) — {desc}")

    lines.append("")
    (_dir(cwd) / "changelog.md").write_text("\n".join(lines), encoding="utf-8")


def _truncate(s: str, max_len: int = 50) -> str:
    """Truncate string to max_len chars, adding ellipsis if needed."""
    s = s.replace("\n", " ").strip()
    if len(s) <= max_len:
        return s
    return s[:max_len] + "..."


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except Exception:
        return

    cwd = data.get("cwd") or os.getcwd()
    try:
        d = _dir(cwd)
        if not d.exists():
            return

        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {})

        file_path = tool_input.get("file_path", "unknown")
        # Make path relative to cwd for readability
        try:
            rel_path = str(Path(file_path).relative_to(cwd))
        except ValueError:
            rel_path = file_path

        filename = Path(file_path).name

        if tool_name == "Edit":
            old_string = tool_input.get("old_string", "")
            new_string = tool_input.get("new_string", "")

            if not old_string and new_string:
                change_type = "create"
                description = f"Created content in {filename}"
            else:
                change_type = "modify"
                old_preview = _truncate(old_string)
                new_preview = _truncate(new_string)
                description = f"Replaced `{old_preview}` with `{new_preview}`"

        elif tool_name == "Write":
            content = tool_input.get("content", "")
            line_count = content.count("\n") + 1 if content else 0

            # Detect create vs overwrite
            if Path(file_path).exists():
                change_type = "modify"
                description = f"Overwrote {filename} ({line_count} lines)"
            else:
                change_type = "create"
                description = f"Created {filename} ({line_count} lines)"

        else:
            return

        # Build entry
        ef = d / "entries.jsonl"
        existing_count = 0
        if ef.exists():
            existing_count = sum(1 for line in ef.read_text(encoding="utf-8").splitlines() if line.strip())

        entry = {
            "id": existing_count + 1,
            "ts": _now_iso(),
            "file_path": rel_path,
            "tool": tool_name,
            "change_type": change_type,
            "description": description[:200],
        }

        with ef.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        _regenerate_changelog(cwd)

        # Output hook response
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": f"[diff-narrator] Logged: {description}"
            }
        }
        print(json.dumps(output))

    except Exception:
        pass


if __name__ == "__main__":
    main()
