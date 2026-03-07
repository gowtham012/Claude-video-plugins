"""
Unit tests for src/action_builder.py

action_builder.py is a standalone helper for building multimodal Anthropic messages
from a video manifest. It is NOT used by the MCP tools (which return context for
Claude Code to reason about directly). It exists for developers who want to call
Claude's API directly outside of Claude Code.

Tests here mock the Anthropic client — no API key required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.action_builder import _build_messages, describe_video, generate_frontend


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_MANIFEST = {
    "metadata": {
        "duration_seconds": 30.0,
        "resolution": "1920x1080",
        "fps": 30.0,
        "has_audio": True,
        "video_type": "website_recording",
    },
    "transcript": [
        {"start": 0.0, "end": 10.0, "text": "Welcome to our site", "confidence": 0.95},
        {"start": 10.0, "end": 25.0, "text": "Click to get started", "confidence": 0.92},
    ],
    "scenes": [
        {
            "id": "scene_0",
            "start": 0.0,
            "end": 12.5,
            "keyframe_path": "/tmp/frames/scene_0.png",
            "keyframe_b64": "aGVsbG8=",  # fake base64
            "detected_text": ["Home", "Products", "Get Started"],
            "motion_detected": False,
            "motion_level": 1.2,
            "transcript_overlap": "Welcome to our site",
        },
        {
            "id": "scene_1",
            "start": 12.5,
            "end": 30.0,
            "keyframe_path": "/tmp/frames/scene_1.png",
            "keyframe_b64": "d29ybGQ=",  # fake base64
            "detected_text": ["$29/mo", "Add to Cart"],
            "motion_detected": True,
            "motion_level": 18.7,
            "transcript_overlap": "Click to get started",
        },
    ],
    "summary": {
        "total_scenes": 2,
        "has_audio": True,
        "high_motion_scenes": ["scene_1"],
        "all_detected_text": ["Home", "Products", "Get Started", "$29/mo", "Add to Cart"],
    },
}


# ---------------------------------------------------------------------------
# _build_messages
# ---------------------------------------------------------------------------

def test_build_messages_returns_user_role():
    messages = _build_messages(SAMPLE_MANIFEST, "Generate code.")
    assert len(messages) == 1
    assert messages[0]["role"] == "user"


def test_build_messages_includes_images():
    messages = _build_messages(SAMPLE_MANIFEST, "Test prompt")
    content = messages[0]["content"]
    image_blocks = [c for c in content if c.get("type") == "image"]
    # Both scenes have non-empty keyframe_b64
    assert len(image_blocks) == 2


def test_build_messages_includes_ocr_text():
    messages = _build_messages(SAMPLE_MANIFEST, "Test prompt")
    content = messages[0]["content"]
    text_blocks = [c for c in content if c.get("type") == "text"]
    combined_text = "\n".join(b["text"] for b in text_blocks)
    assert "Home" in combined_text
    assert "$29/mo" in combined_text


def test_build_messages_includes_motion_flag():
    messages = _build_messages(SAMPLE_MANIFEST, "Test prompt")
    content = messages[0]["content"]
    text_blocks = [c for c in content if c.get("type") == "text"]
    combined_text = "\n".join(b["text"] for b in text_blocks)
    assert "HIGH" in combined_text
    assert "minimal" in combined_text


def test_build_messages_includes_transcript():
    messages = _build_messages(SAMPLE_MANIFEST, "Test prompt")
    content = messages[0]["content"]
    text_blocks = [c for c in content if c.get("type") == "text"]
    combined_text = "\n".join(b["text"] for b in text_blocks)
    assert "Welcome to our site" in combined_text


def test_build_messages_includes_system_prompt():
    messages = _build_messages(SAMPLE_MANIFEST, "MY CUSTOM PROMPT")
    content = messages[0]["content"]
    text_blocks = [c for c in content if c.get("type") == "text"]
    last_text = text_blocks[-1]["text"]
    assert "MY CUSTOM PROMPT" in last_text


def test_build_messages_no_b64_skips_image():
    manifest_no_b64 = {
        **SAMPLE_MANIFEST,
        "scenes": [
            {
                **SAMPLE_MANIFEST["scenes"][0],
                "keyframe_b64": "",
            }
        ],
    }
    messages = _build_messages(manifest_no_b64, "Test")
    content = messages[0]["content"]
    image_blocks = [c for c in content if c.get("type") == "image"]
    assert len(image_blocks) == 0


def test_build_messages_empty_scenes():
    manifest_empty = {**SAMPLE_MANIFEST, "scenes": []}
    messages = _build_messages(manifest_empty, "Test")
    assert messages[0]["role"] == "user"
    content = messages[0]["content"]
    # Should still have the summary text block + task block
    assert len(content) >= 2


# ---------------------------------------------------------------------------
# generate_frontend
# ---------------------------------------------------------------------------

def _mock_anthropic_response(text: str) -> MagicMock:
    response = MagicMock()
    response.content = [MagicMock(text=text)]
    return response


def test_generate_frontend_react(monkeypatch):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response(
        "// --- App.jsx ---\nconst App = () => <div>Hello</div>;\n"
        "// --- App.css ---\nbody { margin: 0; }"
    )

    with patch("src.action_builder.anthropic.Anthropic", return_value=mock_client):
        result = generate_frontend(SAMPLE_MANIFEST, "react")

    assert "App" in result
    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-opus-4-6"
    assert call_kwargs["max_tokens"] == 8096


def test_generate_frontend_html(monkeypatch):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response(
        "<!DOCTYPE html><html><body>Test</body></html>"
    )

    with patch("src.action_builder.anthropic.Anthropic", return_value=mock_client):
        result = generate_frontend(SAMPLE_MANIFEST, "html")

    assert "html" in result.lower()


def test_generate_frontend_uses_opus_model():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response("<div/>")

    with patch("src.action_builder.anthropic.Anthropic", return_value=mock_client):
        generate_frontend(SAMPLE_MANIFEST, "react")

    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["model"] == "claude-opus-4-6"


# ---------------------------------------------------------------------------
# describe_video
# ---------------------------------------------------------------------------

def test_describe_video_returns_string():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response(
        "## Video Analysis\nThis video shows a website demo."
    )

    with patch("src.action_builder.anthropic.Anthropic", return_value=mock_client):
        result = describe_video(SAMPLE_MANIFEST)

    assert isinstance(result, str)
    assert "Video Analysis" in result


def test_describe_video_uses_multimodal_messages():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response("Description")

    with patch("src.action_builder.anthropic.Anthropic", return_value=mock_client):
        describe_video(SAMPLE_MANIFEST)

    _, kwargs = mock_client.messages.create.call_args
    messages = kwargs["messages"]
    content = messages[0]["content"]
    image_blocks = [c for c in content if c.get("type") == "image"]
    assert len(image_blocks) == 2  # both scenes have b64
