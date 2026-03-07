#!/usr/bin/env python3
"""
context-keeper MCP server (FastMCP).
5 tools: setup_project, read_context, write_context, append_log, clear_context.
"""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("carry-forward")

CONTEXT_TEMPLATE = """\
---
last_saved: {ts}
project: {project}
---

## Current Task
<!-- Describe what you are working on right now -->

## Files Being Worked On
<!-- List key files -->

## Key Decisions
<!-- Important architectural or design decisions made -->

## Next Steps
<!-- What needs to happen next -->

## Blockers
<!-- Anything blocking progress -->
"""

CLAUDE_MD_IMPORT = "@carry-forward/context.md"


def _context_dir(cwd: str) -> Path:
    return Path(cwd) / "carry-forward"


def _context_file(cwd: str) -> Path:
    return _context_dir(cwd) / "context.md"


def _log_file(cwd: str) -> Path:
    return _context_dir(cwd) / "log.jsonl"


def _decisions_file(cwd: str) -> Path:
    return _context_dir(cwd) / "decisions.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@mcp.tool()
def setup_project(cwd: str) -> str:
    """
    One-time setup for a project.
    Creates context-keeper/ directory, writes initial context.md,
    and appends @import line to CLAUDE.md so context auto-loads every session.
    """
    ctx_dir = _context_dir(cwd)
    ctx_dir.mkdir(parents=True, exist_ok=True)

    ctx_file = _context_file(cwd)
    project_name = Path(cwd).name
    if not ctx_file.exists():
        ctx_file.write_text(
            CONTEXT_TEMPLATE.format(ts=_now_iso(), project=project_name),
            encoding="utf-8",
        )

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
        f"context-keeper set up in {ctx_dir}.\n"
        f"{claude_md_status}\n"
        "Restart Claude Code for auto-loading to take effect."
    )


@mcp.tool()
def read_context(cwd: str) -> str:
    """
    Returns the full context.md content plus the last 10 log.jsonl entries.
    """
    ctx_file = _context_file(cwd)
    if not ctx_file.exists():
        return "No context found. Run setup_project first."

    context = ctx_file.read_text(encoding="utf-8")

    log = _log_file(cwd)
    recent_entries: list[str] = []
    if log.exists():
        lines = [l.strip() for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
        for line in lines[-10:]:
            try:
                entry = json.loads(line)
                recent_entries.append(f"[{entry.get('ts', '')}] {entry.get('summary', '')}")
            except Exception:
                pass

    log_section = "\n".join(recent_entries) if recent_entries else "(no entries yet)"
    return f"{context}\n\n---\n## Recent Activity Log\n{log_section}"


@mcp.tool()
def write_context(cwd: str, content: str) -> str:
    """
    Overwrites context.md with the provided content.
    Updates the last_saved frontmatter timestamp.
    """
    ctx_dir = _context_dir(cwd)
    ctx_dir.mkdir(parents=True, exist_ok=True)

    # Update last_saved timestamp in frontmatter if present
    ts = _now_iso()
    lines = content.splitlines()
    updated_lines: list[str] = []
    in_frontmatter = False
    frontmatter_done = False
    ts_updated = False

    for i, line in enumerate(lines):
        if i == 0 and line.strip() == "---":
            in_frontmatter = True
            updated_lines.append(line)
            continue
        if in_frontmatter and not frontmatter_done:
            if line.strip() == "---":
                if not ts_updated:
                    updated_lines.append(f"last_saved: {ts}")
                updated_lines.append(line)
                frontmatter_done = True
                in_frontmatter = False
            elif line.startswith("last_saved:"):
                updated_lines.append(f"last_saved: {ts}")
                ts_updated = True
            else:
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    final_content = "\n".join(updated_lines)
    if not final_content.endswith("\n"):
        final_content += "\n"

    _context_file(cwd).write_text(final_content, encoding="utf-8")
    return f"context.md updated at {ts}."


@mcp.tool()
def append_log(cwd: str, entry: str) -> str:
    """
    Appends a timestamped entry to log.jsonl.
    """
    ctx_dir = _context_dir(cwd)
    ctx_dir.mkdir(parents=True, exist_ok=True)

    record = json.dumps({"ts": _now_iso(), "summary": entry.strip()[:300]})
    with _log_file(cwd).open("a", encoding="utf-8") as f:
        f.write(record + "\n")
    return "Log entry appended."


@mcp.tool()
def clear_context(cwd: str) -> str:
    """
    Resets context.md to the blank template.
    Archives log.jsonl to log.{timestamp}.jsonl.bak before clearing.
    """
    log = _log_file(cwd)
    archive_msg = ""
    if log.exists() and log.stat().st_size > 0:
        ts_safe = _now_iso().replace(":", "-").replace(".", "-")
        archive = log.parent / f"log.{ts_safe}.jsonl.bak"
        shutil.copy2(log, archive)
        log.write_text("", encoding="utf-8")
        archive_msg = f" Log archived to {archive.name}."

    project_name = Path(cwd).name
    _context_dir(cwd).mkdir(parents=True, exist_ok=True)
    _context_file(cwd).write_text(
        CONTEXT_TEMPLATE.format(ts=_now_iso(), project=project_name),
        encoding="utf-8",
    )
    return f"Context cleared and reset to template.{archive_msg}"


if __name__ == "__main__":
    mcp.run()
