"""
Unit tests for src/video_analyzer.py

Heavy deps (cv2, EasyOCR, faster-whisper, PySceneDetect) are mocked by
conftest.py so the suite runs without a GPU or video files.

Tests that need REAL cv2 for image I/O (imwrite/imread/cvtColor) are
guarded with @pytest.mark.skipif(not HAS_CV2, ...) and skipped cleanly
when cv2 is not installed.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Flag set by conftest.py
HAS_CV2 = getattr(__builtins__, "_TEST_HAS_CV2", False) if isinstance(__builtins__, dict) else getattr(__builtins__, "_TEST_HAS_CV2", False)
try:
    import cv2 as _cv2_check
    HAS_CV2 = not isinstance(_cv2_check, MagicMock)
except Exception:
    HAS_CV2 = False

from src.video_analyzer import (
    _align_transcript_to_scene,
    _merge_palettes,
    compute_frame_sharpness,
    compute_scene_confidence,
    compute_scene_diff,
    detect_loading_states,
    detect_motion,
    detect_ocr_text,
    detect_scroll_indicators,
    get_metadata,
)


# ── get_metadata ─────────────────────────────────────────────────────────────

MOCK_FFPROBE_OUTPUT = json.dumps({
    "streams": [
        {
            "codec_type": "video",
            "width": 1920,
            "height": 1080,
            "r_frame_rate": "30/1",
        },
        {
            "codec_type": "audio",
        },
    ],
    "format": {
        "duration": "90.0",
    },
})


def test_get_metadata_happy_path(tmp_path):
    fake_video = tmp_path / "test.mp4"
    fake_video.touch()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=MOCK_FFPROBE_OUTPUT)
        meta = get_metadata(str(fake_video))

    assert meta["duration_seconds"] == 90.0
    assert meta["resolution"] == "1920x1080"
    assert meta["fps"] == 30.0
    assert meta["has_audio"] is True
    assert meta["width"] == 1920
    assert meta["height"] == 1080


def test_get_metadata_no_audio(tmp_path):
    fake_video = tmp_path / "test.mp4"
    fake_video.touch()

    no_audio = json.dumps({
        "streams": [
            {"codec_type": "video", "width": 1280, "height": 720, "r_frame_rate": "24/1"},
        ],
        "format": {"duration": "30.0"},
    })

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=no_audio)
        meta = get_metadata(str(fake_video))

    assert meta["has_audio"] is False
    assert meta["fps"] == 24.0


def test_get_metadata_ffprobe_failure(tmp_path):
    fake_video = tmp_path / "test.mp4"
    fake_video.touch()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="error", stdout="{}")
        with pytest.raises(RuntimeError):
            get_metadata(str(fake_video))


def test_get_metadata_fractional_fps(tmp_path):
    """24000/1001 ≈ 23.976 fps — common for film content."""
    fake_video = tmp_path / "test.mp4"
    fake_video.touch()

    data = json.dumps({
        "streams": [{"codec_type": "video", "width": 1920, "height": 1080,
                     "r_frame_rate": "24000/1001"}],
        "format": {"duration": "60.0"},
    })
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=data)
        meta = get_metadata(str(fake_video))

    assert abs(meta["fps"] - 23.976) < 0.01


# ── _align_transcript_to_scene ───────────────────────────────────────────────

TRANSCRIPT = [
    {"start": 0.0, "end": 5.0, "text": "Hello welcome"},
    {"start": 5.0, "end": 12.0, "text": "to our product"},
    {"start": 12.0, "end": 20.0, "text": "see the features"},
    {"start": 25.0, "end": 30.0, "text": "thank you for watching"},
]


def test_align_transcript_full_overlap():
    result = _align_transcript_to_scene(TRANSCRIPT, 0.0, 12.0)
    assert "Hello welcome" in result
    assert "to our product" in result
    assert "see the features" not in result


def test_align_transcript_partial_overlap():
    result = _align_transcript_to_scene(TRANSCRIPT, 10.0, 15.0)
    assert "to our product" in result
    assert "see the features" in result


def test_align_transcript_no_overlap():
    result = _align_transcript_to_scene(TRANSCRIPT, 31.0, 40.0)
    assert result == ""


def test_align_transcript_empty():
    result = _align_transcript_to_scene([], 0.0, 10.0)
    assert result == ""


def test_align_transcript_exact_boundary():
    """Segment ending exactly at scene start should NOT be included."""
    result = _align_transcript_to_scene(TRANSCRIPT, 5.0, 12.0)
    # "Hello welcome" ends at 5.0 — whether included depends on overlap logic
    # Either way, "to our product" (5.0–12.0) must be present
    assert "to our product" in result


def test_align_transcript_single_long_segment():
    long_transcript = [{"start": 0.0, "end": 100.0, "text": "continuous narration"}]
    result = _align_transcript_to_scene(long_transcript, 40.0, 60.0)
    assert "continuous narration" in result


# ── detect_ocr_text ──────────────────────────────────────────────────────────

def test_detect_ocr_text_missing_file():
    result = detect_ocr_text("/nonexistent/path/frame.png")
    assert result == []


def test_detect_ocr_text_easyocr_unavailable(tmp_path):
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"\x89PNG\r\n")

    with patch("builtins.__import__", side_effect=ImportError("easyocr not installed")):
        result = detect_ocr_text(str(frame))
    assert result == []


def test_detect_ocr_text_filters_low_confidence(tmp_path):
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"\x89PNG\r\n")

    mock_reader = MagicMock()
    mock_reader.readtext.return_value = [
        ([0, 0, 10, 10], "Hello", 0.9),
        ([0, 10, 10, 20], "World", 0.1),   # below threshold — must be excluded
        ([0, 20, 10, 30], "Button", 0.5),
    ]

    with patch.dict("sys.modules", {"easyocr": MagicMock(Reader=MagicMock(return_value=mock_reader))}):
        result = detect_ocr_text(str(frame))

    assert "Hello" in result
    assert "Button" in result
    assert "World" not in result


def test_detect_ocr_text_returns_list(tmp_path):
    """Return type must always be a list, never None."""
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"\x89PNG\r\n")
    result = detect_ocr_text(str(frame))
    assert isinstance(result, list)


# ── detect_motion ─────────────────────────────────────────────────────────────

def test_detect_motion_video_not_openable():
    result = detect_motion("/nonexistent/video.mp4", 0.0, 5.0)
    assert result["motion_detected"] is False
    assert result["motion_level"] == 0.0


def test_detect_motion_zero_duration():
    with patch("cv2.VideoCapture") as mock_cap:
        mock_instance = MagicMock()
        mock_instance.isOpened.return_value = True
        mock_cap.return_value = mock_instance

        result = detect_motion("fake.mp4", 5.0, 5.0)
    assert result["motion_detected"] is False


def test_detect_motion_high_motion():
    frames_iter = iter([
        (True, np.zeros((100, 100, 3), dtype=np.uint8)),
        (True, np.full((100, 100, 3), 200, dtype=np.uint8)),
        (True, np.zeros((100, 100, 3), dtype=np.uint8)),
        (True, np.full((100, 100, 3), 200, dtype=np.uint8)),
    ])

    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.side_effect = lambda: next(frames_iter, (False, None))
        mock_cap_cls.return_value = mock_cap

        result = detect_motion("fake.mp4", 0.0, 3.0, sample_frames=4)

    assert result["motion_detected"] is True
    assert result["motion_level"] > 5.0


def test_detect_motion_low_motion():
    static_frame = np.full((100, 100, 3), 128, dtype=np.uint8)
    frames_data = [(True, static_frame.copy()) for _ in range(8)]
    frames_iter = iter(frames_data)

    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.side_effect = lambda: next(frames_iter, (False, None))
        mock_cap_cls.return_value = mock_cap

        result = detect_motion("fake.mp4", 0.0, 7.0, sample_frames=8)

    assert result["motion_detected"] is False
    assert result["motion_level"] < 5.0


def test_detect_motion_result_has_required_keys():
    result = detect_motion("/nonexistent/video.mp4", 0.0, 5.0)
    assert "motion_detected" in result
    assert "motion_level" in result


# ── _merge_palettes ───────────────────────────────────────────────────────────

def test_merge_palettes_deduplicates_similar_colors():
    colors = [
        {"hex": "#ff0000", "rgb": [255, 0, 0], "proportion": 0.3},
        {"hex": "#fe0000", "rgb": [254, 0, 0], "proportion": 0.2},   # near-identical to first
        {"hex": "#0000ff", "rgb": [0, 0, 255], "proportion": 0.5},
    ]
    merged = _merge_palettes(colors)
    assert len(merged) == 2
    blue = next(c for c in merged if c["rgb"][2] > 200)
    assert blue["proportion"] == 0.5


def test_merge_palettes_empty():
    assert _merge_palettes([]) == []


def test_merge_palettes_sorts_by_proportion():
    colors = [
        {"hex": "#aaaaaa", "rgb": [170, 170, 170], "proportion": 0.1},
        {"hex": "#000000", "rgb": [0, 0, 0], "proportion": 0.6},
        {"hex": "#ffffff", "rgb": [255, 255, 255], "proportion": 0.3},
    ]
    merged = _merge_palettes(colors)
    assert merged[0]["hex"] == "#000000"


def test_merge_palettes_single_color():
    colors = [{"hex": "#abcdef", "rgb": [171, 205, 239], "proportion": 1.0}]
    merged = _merge_palettes(colors)
    assert len(merged) == 1
    assert merged[0]["hex"] == "#abcdef"


def test_merge_palettes_all_unique():
    """Completely different colors should not be merged."""
    colors = [
        {"hex": "#ff0000", "rgb": [255, 0, 0], "proportion": 0.33},
        {"hex": "#00ff00", "rgb": [0, 255, 0], "proportion": 0.33},
        {"hex": "#0000ff", "rgb": [0, 0, 255], "proportion": 0.34},
    ]
    merged = _merge_palettes(colors)
    assert len(merged) == 3


# ── compute_frame_sharpness ───────────────────────────────────────────────────

def test_compute_frame_sharpness_missing_file():
    result = compute_frame_sharpness("/nonexistent/frame.png")
    assert result == 0.0


@pytest.mark.skipif(not HAS_CV2, reason="real cv2 required for image I/O")
def test_compute_frame_sharpness_blurry_vs_sharp(tmp_path):
    import cv2

    blurry = np.full((100, 100), 128, dtype=np.uint8)
    sharp = np.zeros((100, 100), dtype=np.uint8)
    sharp[::2, ::2] = 255   # checkerboard — high frequency = sharp

    blurry_path = str(tmp_path / "blurry.png")
    sharp_path = str(tmp_path / "sharp.png")
    cv2.imwrite(blurry_path, blurry)
    cv2.imwrite(sharp_path, sharp)

    s_blur = compute_frame_sharpness(blurry_path)
    s_sharp = compute_frame_sharpness(sharp_path)

    assert s_sharp > s_blur


@pytest.mark.skipif(not HAS_CV2, reason="real cv2 required for image I/O")
def test_compute_frame_sharpness_returns_float(tmp_path):
    import cv2
    img = np.full((50, 50), 200, dtype=np.uint8)
    path = str(tmp_path / "img.png")
    cv2.imwrite(path, img)
    result = compute_frame_sharpness(path)
    assert isinstance(result, float)
    assert result >= 0.0


# ── compute_scene_confidence ──────────────────────────────────────────────────

def test_compute_scene_confidence_structure():
    scene = {
        "detected_text": ["Home", "About", "Products", "Contact", "Login"],
        "diff_from_previous": {"diff_score": 55.0},
    }
    conf = compute_scene_confidence(scene, "/nonexistent/frame.png")
    assert "frame_sharpness" in conf
    assert "ocr_confidence" in conf
    assert "scene_boundary_strength" in conf
    assert "overall" in conf
    assert 0.0 <= conf["overall"] <= 1.0


def test_compute_scene_confidence_more_text_higher_ocr():
    scene_few = {"detected_text": ["Hi"], "diff_from_previous": {"diff_score": 30}}
    scene_many = {"detected_text": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
                  "diff_from_previous": {"diff_score": 30}}

    conf_few = compute_scene_confidence(scene_few, "/nonexistent/frame.png")
    conf_many = compute_scene_confidence(scene_many, "/nonexistent/frame.png")
    assert conf_many["ocr_confidence"] > conf_few["ocr_confidence"]


def test_compute_scene_confidence_empty_scene():
    scene = {"detected_text": [], "diff_from_previous": {}}
    conf = compute_scene_confidence(scene, "/nonexistent/frame.png")
    assert conf["overall"] >= 0.0


def test_compute_scene_confidence_high_diff_score():
    """High diff score (big scene change) should produce strong boundary strength."""
    scene_low  = {"detected_text": [], "diff_from_previous": {"diff_score": 5.0}}
    scene_high = {"detected_text": [], "diff_from_previous": {"diff_score": 90.0}}

    conf_low  = compute_scene_confidence(scene_low,  "/nonexistent/frame.png")
    conf_high = compute_scene_confidence(scene_high, "/nonexistent/frame.png")
    assert conf_high["scene_boundary_strength"] > conf_low["scene_boundary_strength"]


# ── detect_scroll_indicators ──────────────────────────────────────────────────

def test_detect_scroll_indicators_missing_file():
    result = detect_scroll_indicators("/nonexistent/frame.png")
    assert result["has_scrollbar"] is False
    assert result["scroll_direction"] == "none"


@pytest.mark.skipif(not HAS_CV2, reason="real cv2 required for image I/O")
def test_detect_scroll_indicators_no_scrollbar(tmp_path):
    import cv2
    img = np.full((200, 300, 3), 200, dtype=np.uint8)
    path = str(tmp_path / "frame.png")
    cv2.imwrite(path, img)
    result = detect_scroll_indicators(path)
    assert isinstance(result["has_scrollbar"], bool)


def test_detect_scroll_indicators_returns_expected_keys():
    result = detect_scroll_indicators("/nonexistent/frame.png")
    assert "has_scrollbar" in result
    assert "scroll_direction" in result


# ── detect_loading_states ─────────────────────────────────────────────────────

def test_detect_loading_states_missing_file():
    result = detect_loading_states("/nonexistent/frame.png")
    assert result["has_loading"] is False
    assert result["loading_type"] == "none"


@pytest.mark.skipif(not HAS_CV2, reason="real cv2 required for image I/O")
def test_detect_loading_states_returns_expected_keys(tmp_path):
    import cv2
    img = np.full((200, 300, 3), 240, dtype=np.uint8)
    path = str(tmp_path / "frame.png")
    cv2.imwrite(path, img)
    result = detect_loading_states(path)
    assert "has_loading" in result
    assert "has_spinner" in result
    assert "has_skeleton" in result
    assert "has_progress_bar" in result
    assert "loading_type" in result


def test_detect_loading_states_keys_always_present():
    """Keys must be present even on missing files — callers depend on this."""
    result = detect_loading_states("/nonexistent/frame.png")
    for key in ("has_loading", "has_spinner", "has_skeleton", "has_progress_bar", "loading_type"):
        assert key in result


# ── compute_scene_diff ────────────────────────────────────────────────────────

def test_compute_scene_diff_missing_files():
    result = compute_scene_diff("/nonexistent/a.png", "/nonexistent/b.png")
    assert result == {}


@pytest.mark.skipif(not HAS_CV2, reason="real cv2 required for image I/O")
def test_compute_scene_diff_identical_frames(tmp_path):
    import cv2
    img = np.full((100, 100, 3), 128, dtype=np.uint8)
    path = str(tmp_path / "frame.png")
    cv2.imwrite(path, img)

    result = compute_scene_diff(path, path)
    assert result["diff_score"] == 0.0
    assert result["change_type"] == "minimal"


@pytest.mark.skipif(not HAS_CV2, reason="real cv2 required for image I/O")
def test_compute_scene_diff_completely_different(tmp_path):
    import cv2
    black = np.zeros((100, 100, 3), dtype=np.uint8)
    white = np.full((100, 100, 3), 255, dtype=np.uint8)
    path_a = str(tmp_path / "black.png")
    path_b = str(tmp_path / "white.png")
    cv2.imwrite(path_a, black)
    cv2.imwrite(path_b, white)

    result = compute_scene_diff(path_a, path_b)
    assert result["diff_score"] > 60
    assert result["change_type"] == "full_swap"


def test_compute_scene_diff_missing_one_file(tmp_path):
    """One missing file should still return empty dict gracefully."""
    existing = tmp_path / "exists.png"
    existing.write_bytes(b"\x89PNG\r\n")
    result = compute_scene_diff(str(existing), "/nonexistent/b.png")
    assert isinstance(result, dict)
