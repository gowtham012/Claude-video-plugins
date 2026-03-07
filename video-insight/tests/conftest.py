"""
conftest.py — mock heavy ML deps at import time so tests collect without
needing GPU, video files, or the full ML stack installed.

numpy is real (installed). cv2, easyocr, faster_whisper, scenedetect,
and anthropic are mocked. Tests that need REAL cv2 image I/O are marked
with @pytest.mark.skipif(not HAS_CV2, ...) in the test files.
"""
import sys
from unittest.mock import MagicMock

# ── Check what is genuinely available ────────────────────────────────────────

try:
    import cv2 as _cv2  # noqa: F401
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

# ── Mock every heavy dep that is NOT available ────────────────────────────────

_ALWAYS_MOCK = [
    "easyocr",
    "faster_whisper",
    "scenedetect",
    "scenedetect.detectors",
    "scenedetect.scene_manager",
    "scenedetect.video_stream",
    "anthropic",
]

for _mod in _ALWAYS_MOCK:
    sys.modules.setdefault(_mod, MagicMock())

if not HAS_CV2:
    # Provide a minimal cv2 stub so src/video_analyzer.py imports cleanly.
    # Tests that call real cv2 functions (imwrite/imread/cvtColor) will be
    # skipped via the HAS_CV2 guard in the test files.
    _cv2_mock = MagicMock()
    _cv2_mock.COLOR_BGR2GRAY = 6        # numeric constant expected by code
    _cv2_mock.COLOR_BGR2RGB = 4
    _cv2_mock.TERM_CRITERIA_EPS = 1
    _cv2_mock.TERM_CRITERIA_MAX_ITER = 2
    sys.modules["cv2"] = _cv2_mock

# Export availability flag so test files can import it
import builtins
builtins._TEST_HAS_CV2 = HAS_CV2
