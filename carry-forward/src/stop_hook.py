#!/usr/bin/env python3
"""
Stop hook — runs after every Claude response.
Appends a brief summary line to {cwd}/carry-forward/log.jsonl.
Uses stdlib only; never blocks Claude on any error.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except Exception:
        return

    # Prevent infinite loops if this hook triggers another Stop event
    if data.get("stop_hook_active"):
        return

    cwd = data.get("cwd") or os.getcwd()
    message = data.get("last_assistant_message") or ""
    if not message.strip():
        return

    try:
        log_dir = Path(cwd) / "carry-forward"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "log.jsonl"

        summary = message.strip().replace("\n", " ")[:300]
        entry = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
        })
        with log_file.open("a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass  # Never block Claude


if __name__ == "__main__":
    main()
