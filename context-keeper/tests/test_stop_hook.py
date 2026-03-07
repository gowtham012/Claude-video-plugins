"""
Unit tests for src/stop_hook.py.

Tests invoke main() by monkey-patching sys.stdin so no subprocess is needed.
All I/O uses tmp_path; stdlib only.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Import after conftest.py has already loaded (which is guaranteed by pytest)
from src.stop_hook import main


def _run(payload: dict | None = None, raw: str = "") -> None:
    """Run stop_hook.main() with the given stdin payload."""
    if payload is not None:
        raw = json.dumps(payload)
    with patch("sys.stdin", io.StringIO(raw)):
        main()


# ── Normal operation ───────────────────────────────────────────────────────────

class TestNormalOperation:
    def test_appends_entry_on_valid_input(self, tmp_path):
        _run({"cwd": str(tmp_path), "last_assistant_message": "Did some work."})
        log = tmp_path / "carry-forward" / "log.jsonl"
        assert log.exists()
        data = json.loads(log.read_text().strip())
        assert data["summary"] == "Did some work."

    def test_entry_has_utc_timestamp(self, tmp_path):
        _run({"cwd": str(tmp_path), "last_assistant_message": "Check timestamp"})
        data = json.loads((tmp_path / "carry-forward" / "log.jsonl").read_text().strip())
        assert "ts" in data
        assert "Z" in data["ts"] or "+00:00" in data["ts"]  # UTC marker

    def test_creates_directory_if_missing(self, tmp_path):
        assert not (tmp_path / "carry-forward").exists()
        _run({"cwd": str(tmp_path), "last_assistant_message": "Hello"})
        assert (tmp_path / "carry-forward").is_dir()

    def test_multiple_calls_accumulate_lines(self, tmp_path):
        _run({"cwd": str(tmp_path), "last_assistant_message": "First"})
        _run({"cwd": str(tmp_path), "last_assistant_message": "Second"})
        _run({"cwd": str(tmp_path), "last_assistant_message": "Third"})
        lines = (tmp_path / "carry-forward" / "log.jsonl").read_text().strip().splitlines()
        assert len(lines) == 3

    def test_newlines_in_message_collapsed_to_spaces(self, tmp_path):
        _run({"cwd": str(tmp_path), "last_assistant_message": "line1\nline2\nline3"})
        data = json.loads((tmp_path / "carry-forward" / "log.jsonl").read_text().strip())
        assert "\n" not in data["summary"]
        assert "line1" in data["summary"]

    def test_long_message_truncated_to_300_chars(self, tmp_path):
        _run({"cwd": str(tmp_path), "last_assistant_message": "x" * 500})
        data = json.loads((tmp_path / "carry-forward" / "log.jsonl").read_text().strip())
        assert len(data["summary"]) <= 300

    def test_message_is_stripped(self, tmp_path):
        _run({"cwd": str(tmp_path), "last_assistant_message": "   trimmed   "})
        data = json.loads((tmp_path / "carry-forward" / "log.jsonl").read_text().strip())
        assert data["summary"] == "trimmed"

    def test_falls_back_to_cwd_when_no_cwd_in_payload(self, tmp_path):
        """If 'cwd' key is absent, hook falls back to os.getcwd()."""
        with patch("os.getcwd", return_value=str(tmp_path)):
            _run({"last_assistant_message": "fallback cwd test"})
        log = tmp_path / "carry-forward" / "log.jsonl"
        assert log.exists()


# ── Guard conditions — hook must stay silent ───────────────────────────────────

class TestGuardConditions:
    def test_stop_hook_active_flag_prevents_write(self, tmp_path):
        """stop_hook_active=True must be a no-op to prevent infinite loops."""
        _run({"cwd": str(tmp_path), "last_assistant_message": "Should not log", "stop_hook_active": True})
        log = tmp_path / "carry-forward" / "log.jsonl"
        assert not log.exists()

    def test_empty_stdin_is_silently_ignored(self, tmp_path):
        _run(raw="")
        assert not (tmp_path / "carry-forward").exists()

    def test_whitespace_only_stdin_is_ignored(self, tmp_path):
        _run(raw="   \n  ")
        assert not (tmp_path / "carry-forward").exists()

    def test_malformed_json_is_silently_ignored(self, tmp_path):
        _run(raw="not-json{{{")
        # Should not raise; directory should not be created
        assert not (tmp_path / "carry-forward").exists()

    def test_empty_message_produces_no_entry(self, tmp_path):
        _run({"cwd": str(tmp_path), "last_assistant_message": ""})
        assert not (tmp_path / "carry-forward" / "log.jsonl").exists()

    def test_whitespace_only_message_produces_no_entry(self, tmp_path):
        _run({"cwd": str(tmp_path), "last_assistant_message": "   \n  "})
        assert not (tmp_path / "carry-forward" / "log.jsonl").exists()

    def test_missing_message_key_produces_no_entry(self, tmp_path):
        _run({"cwd": str(tmp_path)})
        assert not (tmp_path / "carry-forward" / "log.jsonl").exists()

    def test_null_message_produces_no_entry(self, tmp_path):
        _run({"cwd": str(tmp_path), "last_assistant_message": None})
        assert not (tmp_path / "carry-forward" / "log.jsonl").exists()


# ── Error resilience — hook must never raise ──────────────────────────────────

class TestErrorResilience:
    def test_unwritable_directory_does_not_raise(self, tmp_path):
        """Even if the filesystem write fails, main() must exit cleanly."""
        bad_path = str(tmp_path / "nonexistent" / "deep" / "path")
        ctx_dir = Path(bad_path) / "carry-forward"
        # Make a file where a directory would be — causes mkdir to fail
        ctx_dir.parent.mkdir(parents=True)
        ctx_dir.parent.joinpath("carry-forward").write_text("I am a file, not a dir")
        # Should not raise
        try:
            _run({"cwd": bad_path, "last_assistant_message": "write will fail"})
        except Exception as exc:
            pytest.fail(f"stop_hook.main() raised unexpectedly: {exc}")
