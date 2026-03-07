"""
Unit tests for src/server.py — all 5 MCP tools.

Uses only stdlib (pathlib, json, tempfile) — no external deps required.
fastmcp is mocked by conftest.py so the @mcp.tool() decorator is a passthrough.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.server import (
    append_log,
    clear_context,
    read_context,
    setup_project,
    write_context,
    CLAUDE_MD_IMPORT,
    CONTEXT_TEMPLATE,
)


# ── setup_project ─────────────────────────────────────────────────────────────

class TestSetupProject:
    def test_creates_context_keeper_directory(self, tmp_path):
        setup_project(str(tmp_path))
        assert (tmp_path / "carry-forward").is_dir()

    def test_creates_context_md(self, tmp_path):
        setup_project(str(tmp_path))
        ctx = tmp_path / "carry-forward" / "context.md"
        assert ctx.exists()
        assert "## Current Task" in ctx.read_text()

    def test_creates_log_jsonl(self, tmp_path):
        setup_project(str(tmp_path))
        assert (tmp_path / "carry-forward" / "log.jsonl").exists()

    def test_creates_claude_md_if_missing(self, tmp_path):
        setup_project(str(tmp_path))
        claude_md = tmp_path / "CLAUDE.md"
        assert claude_md.exists()
        assert CLAUDE_MD_IMPORT in claude_md.read_text()

    def test_appends_to_existing_claude_md(self, tmp_path):
        existing = "# My Project\n\nExisting content here.\n"
        (tmp_path / "CLAUDE.md").write_text(existing)
        setup_project(str(tmp_path))
        content = (tmp_path / "CLAUDE.md").read_text()
        assert "Existing content here." in content
        assert CLAUDE_MD_IMPORT in content

    def test_does_not_duplicate_import_on_second_run(self, tmp_path):
        setup_project(str(tmp_path))
        setup_project(str(tmp_path))  # run twice
        content = (tmp_path / "CLAUDE.md").read_text()
        assert content.count(CLAUDE_MD_IMPORT) == 1

    def test_does_not_overwrite_existing_context_md(self, tmp_path):
        ctx_dir = tmp_path / "carry-forward"
        ctx_dir.mkdir()
        existing_ctx = ctx_dir / "context.md"
        existing_ctx.write_text("# Custom content\n")
        setup_project(str(tmp_path))
        assert existing_ctx.read_text() == "# Custom content\n"

    def test_context_md_contains_project_name(self, tmp_path):
        setup_project(str(tmp_path))
        content = (tmp_path / "carry-forward" / "context.md").read_text()
        assert tmp_path.name in content

    def test_return_message_mentions_restart(self, tmp_path):
        result = setup_project(str(tmp_path))
        assert "Restart" in result or "restart" in result

    def test_idempotent_already_imported(self, tmp_path):
        """Second call on a project with import already present returns different message."""
        setup_project(str(tmp_path))
        result = setup_project(str(tmp_path))
        assert "already" in result


# ── read_context ──────────────────────────────────────────────────────────────

class TestReadContext:
    def test_no_context_returns_helpful_message(self, tmp_path):
        result = read_context(str(tmp_path))
        assert "No context" in result or "setup_project" in result

    def test_returns_context_md_content(self, tmp_path):
        setup_project(str(tmp_path))
        ctx = tmp_path / "carry-forward" / "context.md"
        ctx.write_text("## Current Task\nBuilding auth flow\n")
        result = read_context(str(tmp_path))
        assert "Building auth flow" in result

    def test_includes_log_entries(self, tmp_path):
        setup_project(str(tmp_path))
        log = tmp_path / "carry-forward" / "log.jsonl"
        log.write_text(
            json.dumps({"ts": "2026-03-07T10:00:00Z", "summary": "Fixed login bug"}) + "\n"
        )
        result = read_context(str(tmp_path))
        assert "Fixed login bug" in result

    def test_returns_only_last_10_log_entries(self, tmp_path):
        setup_project(str(tmp_path))
        log = tmp_path / "carry-forward" / "log.jsonl"
        lines = [
            json.dumps({"ts": f"2026-03-07T10:{i:02d}:00Z", "summary": f"entry-{i}"}) + "\n"
            for i in range(15)
        ]
        log.write_text("".join(lines))
        result = read_context(str(tmp_path))
        # entry-0 through entry-4 should NOT appear (only last 10)
        assert "entry-0" not in result
        assert "entry-14" in result

    def test_handles_malformed_log_lines_gracefully(self, tmp_path):
        setup_project(str(tmp_path))
        log = tmp_path / "carry-forward" / "log.jsonl"
        log.write_text("not-json\n" + json.dumps({"ts": "2026-03-07T10:00:00Z", "summary": "valid"}) + "\n")
        result = read_context(str(tmp_path))
        assert "valid" in result   # valid entry must still appear

    def test_empty_log_shows_placeholder(self, tmp_path):
        setup_project(str(tmp_path))
        result = read_context(str(tmp_path))
        assert "no entries" in result.lower() or "recent" in result.lower()


# ── write_context ─────────────────────────────────────────────────────────────

class TestWriteContext:
    def test_writes_content_to_file(self, tmp_path):
        content = "---\nlast_saved: old\nproject: test\n---\n\n## Current Task\nTest task\n"
        write_context(str(tmp_path), content)
        written = (tmp_path / "carry-forward" / "context.md").read_text()
        assert "Test task" in written

    def test_updates_last_saved_timestamp(self, tmp_path):
        content = "---\nlast_saved: 2020-01-01T00:00:00Z\nproject: test\n---\n\n## Task\nWork\n"
        write_context(str(tmp_path), content)
        written = (tmp_path / "carry-forward" / "context.md").read_text()
        # Timestamp must have been updated (no longer 2020)
        assert "2020-01-01" not in written
        assert "last_saved:" in written

    def test_creates_directory_if_missing(self, tmp_path):
        write_context(str(tmp_path), "# content\n")
        assert (tmp_path / "carry-forward").is_dir()

    def test_content_without_frontmatter_is_written_as_is(self, tmp_path):
        write_context(str(tmp_path), "## No frontmatter here\nJust content.\n")
        written = (tmp_path / "carry-forward" / "context.md").read_text()
        assert "Just content." in written

    def test_return_message_mentions_updated(self, tmp_path):
        result = write_context(str(tmp_path), "content")
        assert "updated" in result.lower() or "context.md" in result

    def test_file_always_ends_with_newline(self, tmp_path):
        write_context(str(tmp_path), "## Content without newline")
        written = (tmp_path / "carry-forward" / "context.md").read_text()
        assert written.endswith("\n")

    def test_injects_last_saved_if_missing_from_frontmatter(self, tmp_path):
        """Frontmatter with no last_saved line gets one injected before closing ---."""
        content = "---\nproject: myapp\n---\n\n## Task\nWork\n"
        write_context(str(tmp_path), content)
        written = (tmp_path / "carry-forward" / "context.md").read_text()
        assert "last_saved:" in written


# ── append_log ────────────────────────────────────────────────────────────────

class TestAppendLog:
    def test_appends_entry_to_log(self, tmp_path):
        append_log(str(tmp_path), "Implemented login endpoint")
        log = tmp_path / "carry-forward" / "log.jsonl"
        assert log.exists()
        data = json.loads(log.read_text().strip())
        assert data["summary"] == "Implemented login endpoint"

    def test_entry_has_timestamp(self, tmp_path):
        append_log(str(tmp_path), "Some work done")
        data = json.loads((tmp_path / "carry-forward" / "log.jsonl").read_text().strip())
        assert "ts" in data
        assert "Z" in data["ts"] or "+00:00" in data["ts"]  # UTC ISO format

    def test_multiple_entries_accumulate(self, tmp_path):
        append_log(str(tmp_path), "First entry")
        append_log(str(tmp_path), "Second entry")
        append_log(str(tmp_path), "Third entry")
        lines = (tmp_path / "carry-forward" / "log.jsonl").read_text().strip().splitlines()
        assert len(lines) == 3

    def test_truncates_long_entries_to_300_chars(self, tmp_path):
        long_entry = "x" * 500
        append_log(str(tmp_path), long_entry)
        data = json.loads((tmp_path / "carry-forward" / "log.jsonl").read_text().strip())
        assert len(data["summary"]) <= 300

    def test_strips_whitespace_from_entry(self, tmp_path):
        append_log(str(tmp_path), "   padded entry   ")
        data = json.loads((tmp_path / "carry-forward" / "log.jsonl").read_text().strip())
        assert data["summary"] == "padded entry"

    def test_creates_directory_if_missing(self, tmp_path):
        append_log(str(tmp_path), "entry")
        assert (tmp_path / "carry-forward").is_dir()

    def test_return_message(self, tmp_path):
        result = append_log(str(tmp_path), "entry")
        assert "appended" in result.lower() or "log" in result.lower()


# ── clear_context ─────────────────────────────────────────────────────────────

class TestClearContext:
    def test_resets_context_md_to_template(self, tmp_path):
        setup_project(str(tmp_path))
        ctx = tmp_path / "carry-forward" / "context.md"
        ctx.write_text("## Custom content that should be cleared\n")

        clear_context(str(tmp_path))

        written = ctx.read_text()
        assert "## Current Task" in written         # template marker
        assert "Custom content" not in written

    def test_archives_log_before_clearing(self, tmp_path):
        setup_project(str(tmp_path))
        log = tmp_path / "carry-forward" / "log.jsonl"
        log.write_text(json.dumps({"ts": "2026-03-07T10:00:00Z", "summary": "old entry"}) + "\n")

        clear_context(str(tmp_path))

        bak_files = list((tmp_path / "carry-forward").glob("*.bak"))
        assert len(bak_files) == 1
        assert "old entry" in bak_files[0].read_text()

    def test_log_is_empty_after_clear(self, tmp_path):
        setup_project(str(tmp_path))
        log = tmp_path / "carry-forward" / "log.jsonl"
        log.write_text("some entries\n")

        clear_context(str(tmp_path))

        assert log.read_text() == ""

    def test_no_archive_if_log_empty(self, tmp_path):
        setup_project(str(tmp_path))
        # log.jsonl exists but is empty — no archive should be created
        clear_context(str(tmp_path))
        bak_files = list((tmp_path / "carry-forward").glob("*.bak"))
        assert len(bak_files) == 0

    def test_return_message_mentions_cleared(self, tmp_path):
        setup_project(str(tmp_path))
        result = clear_context(str(tmp_path))
        assert "cleared" in result.lower() or "reset" in result.lower()

    def test_return_message_mentions_archive_name(self, tmp_path):
        setup_project(str(tmp_path))
        log = tmp_path / "carry-forward" / "log.jsonl"
        log.write_text(json.dumps({"ts": "2026-03-07T10:00:00Z", "summary": "x"}) + "\n")

        result = clear_context(str(tmp_path))
        assert ".bak" in result

    def test_context_md_contains_project_name_after_clear(self, tmp_path):
        setup_project(str(tmp_path))
        clear_context(str(tmp_path))
        content = (tmp_path / "carry-forward" / "context.md").read_text()
        assert tmp_path.name in content

    def test_creates_directory_if_missing(self, tmp_path):
        """clear_context should not crash on a fresh project with no context-keeper dir."""
        clear_context(str(tmp_path))
        assert (tmp_path / "carry-forward" / "context.md").exists()
