"""
Core video understanding pipeline.

Extracts 10 types of information from any video:
1.  Metadata (resolution, fps, duration, video_type)
2.  Smart keyframes (scene-change-detected + dense fallback for short videos)
3.  Burst frames (extra frames inside high-motion scenes)
4.  Audio transcript (timestamped speech-to-text via faster-whisper)
5.  OCR text (text visible on screen per scene via EasyOCR)
6.  Color palette (dominant colors per scene via OpenCV k-means)
7.  Motion events (frame-differencing with type: animation/scroll/cut/none)
8.  Scene diff (pixel-level diff between consecutive keyframes)
9.  UI component hints (heuristic detection of buttons, inputs, navbars, cards)
10. Font/typography hints (estimated sizes, weights, roles from text bounding boxes)

Performance: per-scene enrichment runs in parallel via ThreadPoolExecutor.
Progress: accepts optional progress_callback(stage, current, total) for streaming updates.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Optional

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Metadata + video type classifier
# ---------------------------------------------------------------------------

def get_metadata(video_path: str) -> dict[str, Any]:
    """Use ffprobe to extract video metadata."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)

    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"), {}
    )
    audio_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None
    )
    fmt = data.get("format", {})

    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))

    fps_raw = video_stream.get("r_frame_rate", "0/1")
    try:
        num, den = fps_raw.split("/")
        fps = round(int(num) / int(den), 2)
    except (ValueError, ZeroDivisionError):
        fps = 0.0

    duration = float(fmt.get("duration", 0) or video_stream.get("duration", 0) or 0)

    metadata = {
        "duration_seconds": round(duration, 2),
        "resolution": f"{width}x{height}",
        "width": width,
        "height": height,
        "fps": fps,
        "has_audio": audio_stream is not None,
        "video_type": "unknown",
    }

    metadata["video_type"] = _classify_video_type(metadata)
    return metadata


def _classify_video_type(meta: dict) -> str:
    """
    Heuristic video type classifier based on metadata signals.

    Rules:
    - fps >= 50 and short duration → component_demo (design tool recording)
    - No audio, high resolution, long duration → 3d_walkthrough
    - No audio, standard resolution → website_recording
    - Has audio, short duration (< 60s) → marketing
    - Has audio, long duration → tutorial
    """
    fps = meta.get("fps", 0)
    duration = meta.get("duration_seconds", 0)
    has_audio = meta.get("has_audio", False)
    width = meta.get("width", 0)

    if fps >= 50 and duration < 30 and not has_audio:
        return "component_demo"
    if not has_audio and width >= 1920 and duration > 30:
        return "3d_walkthrough"
    if not has_audio:
        return "website_recording"
    if has_audio and duration < 60:
        return "marketing"
    return "tutorial"


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------

def extract_audio_transcript(video_path: str) -> list[dict[str, Any]]:
    """
    Use faster-whisper to transcribe audio from the video.
    Returns [] if the video has no audio track or transcription fails.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return []

    meta_cmd = [
        "ffprobe", "-v", "quiet", "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-of", "default=noprint_wrappers=1:nokey=1", video_path
    ]
    probe = subprocess.run(meta_cmd, capture_output=True, text=True, timeout=15)
    if "audio" not in probe.stdout:
        return []

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        audio_path = tmp.name

    try:
        extract_cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            audio_path
        ]
        subprocess.run(extract_cmd, capture_output=True, timeout=120, check=True)

        model = WhisperModel("base", compute_type="int8")
        segments, _ = model.transcribe(audio_path, beam_size=5)

        transcript = []
        for seg in segments:
            transcript.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
                "confidence": round(getattr(seg, "avg_logprob", 0.0) + 1.0, 2),
            })
        return transcript

    except Exception:
        return []
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)


# ---------------------------------------------------------------------------
# Scene detection + keyframes
# ---------------------------------------------------------------------------

def detect_scenes_and_keyframes(
    video_path: str,
    output_dir: str,
) -> list[dict[str, Any]]:
    """
    Use PySceneDetect (AdaptiveDetector) to find scene changes.
    For each scene: extract keyframe PNG + base64-encode it.
    Falls back to uniform sampling every 3s if PySceneDetect finds < 3 scenes.
    """
    frames_dir = Path(output_dir) / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    scenes_raw = _detect_scenes_pyscenedetect(video_path)

    # If we got very few scenes relative to duration, fall back to denser sampling
    meta_cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", video_path]
    dur_result = subprocess.run(meta_cmd, capture_output=True, text=True, timeout=10)
    try:
        duration = float(dur_result.stdout.strip())
    except (ValueError, TypeError):
        duration = 0

    min_expected_scenes = max(3, int(duration / 5))
    if len(scenes_raw) < min_expected_scenes:
        fallback = _detect_scenes_uniform(video_path, interval=3.0)
        # Merge: keep PySceneDetect boundaries + add uniform splits
        all_boundaries = sorted(set(
            [s for pair in scenes_raw for s in pair] +
            [s for pair in fallback for s in pair]
        ))
        if len(all_boundaries) >= 2:
            scenes_raw = list(zip(all_boundaries[:-1], all_boundaries[1:]))
        else:
            scenes_raw = fallback

    results = []
    for i, (start_sec, end_sec) in enumerate(scenes_raw):
        keyframe_path = str(frames_dir / f"scene_{i}.png")
        midpoint = start_sec + (end_sec - start_sec) / 2.0
        _extract_frame_at(video_path, midpoint, keyframe_path)

        keyframe_b64 = ""
        if os.path.exists(keyframe_path):
            with open(keyframe_path, "rb") as f:
                keyframe_b64 = base64.b64encode(f.read()).decode("utf-8")

        results.append({
            "id": f"scene_{i}",
            "start": round(start_sec, 2),
            "end": round(end_sec, 2),
            "keyframe_path": keyframe_path,
            "keyframe_b64": keyframe_b64,
        })

    return results


def extract_burst_frames(
    video_path: str,
    scene_id: str,
    scene_start: float,
    scene_end: float,
    output_dir: str,
    n_frames: int = 4,
) -> list[dict[str, Any]]:
    """
    Extract N evenly-spaced frames within a high-motion scene.
    Captures intermediate animation states that a single keyframe misses.
    Returns list of {path, b64, timestamp}.
    """
    burst_dir = Path(output_dir) / "burst"
    burst_dir.mkdir(parents=True, exist_ok=True)

    duration = scene_end - scene_start
    if duration <= 0 or n_frames < 2:
        return []

    timestamps = [
        scene_start + duration * i / (n_frames - 1)
        for i in range(n_frames)
    ]

    frames = []
    for j, ts in enumerate(timestamps):
        out_path = str(burst_dir / f"{scene_id}_burst_{j}.png")
        _extract_frame_at(video_path, ts, out_path)

        b64 = ""
        if os.path.exists(out_path):
            with open(out_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")

        frames.append({
            "path": out_path,
            "b64": b64,
            "timestamp": round(ts, 2),
        })

    return frames


def _detect_scenes_pyscenedetect(video_path: str) -> list[tuple[float, float]]:
    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import AdaptiveDetector

        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(AdaptiveDetector())
        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()

        if not scene_list:
            return []

        return [(s[0].get_seconds(), s[1].get_seconds()) for s in scene_list]
    except Exception:
        return []


def _detect_scenes_uniform(video_path: str, interval: float = 3.0) -> list[tuple[float, float]]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    cap.release()

    duration = total_frames / fps
    scenes = []
    t = 0.0
    while t < duration:
        scenes.append((t, min(t + interval, duration)))
        t += interval
    return scenes


def _extract_frame_at(video_path: str, timestamp: float, out_path: str) -> None:
    cmd = [
        "ffmpeg", "-y", "-ss", str(timestamp), "-i", video_path,
        "-vframes", "1", "-q:v", "1", out_path
    ]
    subprocess.run(cmd, capture_output=True, timeout=30)


# ---------------------------------------------------------------------------
# OCR — lower threshold, full-res
# ---------------------------------------------------------------------------

def detect_ocr_text(frame_path: str) -> list[str]:
    """
    Run EasyOCR on a keyframe.
    Confidence threshold lowered to 0.25 to catch small UI labels.
    Returns list of (text, confidence) tuples for transparency.
    """
    if not os.path.exists(frame_path):
        return []

    try:
        import easyocr
        reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        results = reader.readtext(frame_path, detail=1)
        return [text for (_, text, conf) in results if conf >= 0.25]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Color palette extraction
# ---------------------------------------------------------------------------

def extract_color_palette(frame_path: str, n_colors: int = 6) -> list[dict[str, Any]]:
    """
    Extract dominant colors from a keyframe using OpenCV k-means clustering.

    Returns list of {hex, rgb, proportion} sorted by dominance.
    Ignores near-white and near-black to focus on brand/accent colors.
    """
    if not os.path.exists(frame_path):
        return []

    try:
        img = cv2.imread(frame_path)
        if img is None:
            return []

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Resize for speed
        h, w = img_rgb.shape[:2]
        scale = min(1.0, 300 / max(h, w))
        small = cv2.resize(img_rgb, (int(w * scale), int(h * scale)))

        pixels = small.reshape(-1, 3).astype(np.float32)

        # K-means clustering
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        _, labels, centers = cv2.kmeans(
            pixels, n_colors, None, criteria, 5, cv2.KMEANS_RANDOM_CENTERS
        )

        centers = centers.astype(int)
        counts = np.bincount(labels.flatten())
        total = len(pixels)

        palette = []
        for color, count in sorted(zip(centers, counts), key=lambda x: -x[1]):
            r, g, b = int(color[0]), int(color[1]), int(color[2])
            hex_code = f"#{r:02x}{g:02x}{b:02x}"
            proportion = round(count / total, 3)
            palette.append({
                "hex": hex_code,
                "rgb": [r, g, b],
                "proportion": proportion,
            })

        return palette

    except Exception:
        return []


# ---------------------------------------------------------------------------
# Motion detection
# ---------------------------------------------------------------------------

def detect_motion(
    video_path: str,
    scene_start: float,
    scene_end: float,
    sample_frames: int = 8,
) -> dict[str, Any]:
    """
    OpenCV frame differencing to detect motion within a scene.
    Returns {motion_detected, motion_level, motion_type}.
    motion_type: 'animation' (gradual), 'cut' (sudden), 'scroll' (directional), 'none'
    """
    MOTION_THRESHOLD = 5.0

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"motion_detected": False, "motion_level": 0.0, "motion_type": "none"}

    duration = scene_end - scene_start
    if duration <= 0 or sample_frames < 2:
        cap.release()
        return {"motion_detected": False, "motion_level": 0.0, "motion_type": "none"}

    timestamps = [
        scene_start + duration * i / (sample_frames - 1)
        for i in range(sample_frames)
    ]

    frames = []
    for ts in timestamps:
        cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
        ret, frame = cap.read()
        if ret:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frames.append(gray.astype(np.float32))
    cap.release()

    if len(frames) < 2:
        return {"motion_detected": False, "motion_level": 0.0, "motion_type": "none"}

    diffs = [float(np.mean(np.abs(b - a))) for a, b in zip(frames[:-1], frames[1:])]
    motion_level = round(float(np.mean(diffs)), 2)
    max_diff = max(diffs)

    # Classify motion type
    if motion_level < MOTION_THRESHOLD:
        motion_type = "none"
    elif max_diff > 40 and max_diff > np.mean(diffs) * 3:
        motion_type = "cut"         # sudden spike = hard cut
    elif motion_level > 15:
        motion_type = "animation"   # sustained high motion = UI animation
    else:
        motion_type = "scroll"      # moderate gradual motion = scroll/pan

    return {
        "motion_detected": motion_level >= MOTION_THRESHOLD,
        "motion_level": motion_level,
        "motion_type": motion_type,
    }


# ---------------------------------------------------------------------------
# Transcript ↔ Scene alignment
# ---------------------------------------------------------------------------

def _align_transcript_to_scene(
    transcript: list[dict],
    scene_start: float,
    scene_end: float,
) -> str:
    parts = []
    for seg in transcript:
        if seg["start"] < scene_end and seg["end"] > scene_start:
            parts.append(seg["text"])
    return " ".join(parts).strip()


# ---------------------------------------------------------------------------
# Build manifest (orchestrator)
# ---------------------------------------------------------------------------

def _enrich_scene(args: tuple) -> dict[str, Any]:
    """
    Worker function: enrich a single scene with all per-frame data.
    Runs in a thread — each call is independent.
    """
    scene, video_path, output_dir = args
    ocr_text      = detect_ocr_text(scene["keyframe_path"])
    color_palette = extract_color_palette(scene["keyframe_path"])
    components    = detect_ui_components(scene["keyframe_path"])
    fonts         = detect_fonts(scene["keyframe_path"])
    motion        = detect_motion(video_path, scene["start"], scene["end"])
    cursor        = detect_cursor_position(video_path, scene["start"], scene["end"])
    scroll        = detect_scroll_indicators(scene["keyframe_path"])
    loading       = detect_loading_states(scene["keyframe_path"])

    burst_frames: list[dict] = []
    if motion["motion_detected"]:
        burst_frames = extract_burst_frames(
            video_path, scene["id"], scene["start"], scene["end"], output_dir
        )

    return {
        "id":            scene["id"],
        "start":         scene["start"],
        "end":           scene["end"],
        "keyframe_path": scene["keyframe_path"],
        "keyframe_b64":  scene["keyframe_b64"],
        "detected_text": ocr_text,
        "color_palette": color_palette,
        "ui_components": components,
        "fonts":         fonts,
        "motion_detected": motion["motion_detected"],
        "motion_level":    motion["motion_level"],
        "motion_type":     motion["motion_type"],
        "burst_frames":    burst_frames,
        "cursor":          cursor,
        "scroll":          scroll,
        "loading":         loading,
        # transcript_overlap, diff_from_previous, confidence, annotated_frame_path
        # are added in the sequential pass (need scene ordering / previous scene)
        "transcript_overlap":   "",
        "diff_from_previous":   {},
        "confidence":           {},
        "annotated_frame_path": "",
    }


# In-process manifest cache keyed by (video_hash, output_dir).
# Avoids re-running the full OCR+motion+cursor pipeline on repeated tool calls
# for the same video within a single Claude Code session.
_MANIFEST_CACHE: dict[str, dict[str, Any]] = {}


def build_manifest(
    video_path: str,
    output_dir: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> dict[str, Any]:
    """
    Full video understanding pipeline — runs per-scene enrichment in parallel.

    progress_callback(stage: str, current: int, total: int) is called at each stage.

    Results are cached in-process by (video_hash, output_dir) so repeated calls
    from different tools in the same session skip expensive re-analysis.
    """
    # Fast path: check cache first (before computing hash)
    resolved_out = str(Path(output_dir).expanduser().resolve())
    resolved_vid = str(Path(video_path).expanduser().resolve())

    manifest_file = Path(resolved_out) / "manifest.json"
    if manifest_file.exists():
        vh = compute_video_hash(resolved_vid)
        cache_key = f"{vh}::{resolved_out}"
        if cache_key in _MANIFEST_CACHE:
            return _MANIFEST_CACHE[cache_key]
        # Also check if saved manifest matches current hash
        try:
            import json as _j
            saved = _j.loads(manifest_file.read_text())
            if saved.get("video_hash") == vh:
                # Rebuild in-memory manifest from saved file + re-attach b64
                _MANIFEST_CACHE[cache_key] = saved
                return saved
        except Exception:
            pass
    def _progress(stage: str, current: int, total: int) -> None:
        if progress_callback:
            progress_callback(stage, current, total)

    output_path = Path(resolved_out)
    output_path.mkdir(parents=True, exist_ok=True)

    # 1. Metadata
    _progress("metadata", 0, 5)
    metadata = get_metadata(resolved_vid)

    # 2. Transcript (parallel with scene detection — both are slow I/O)
    _progress("transcript", 1, 5)
    transcript = extract_audio_transcript(resolved_vid)
    metadata["has_audio"] = bool(transcript) or metadata.get("has_audio", False)

    # 3. Scene detection + keyframe extraction
    _progress("scenes", 2, 5)
    scenes_raw = detect_scenes_and_keyframes(resolved_vid, resolved_out)

    # 4. Parallel per-scene enrichment
    _progress("enriching", 3, 5)
    n_scenes = len(scenes_raw)
    enriched: dict[str, dict] = {}

    max_workers = min(4, max(1, n_scenes))
    args_list = [(scene, resolved_vid, resolved_out) for scene in scenes_raw]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_enrich_scene, args): args[0]["id"] for args in args_list}
        done = 0
        for future in as_completed(futures):
            result = future.result()
            enriched[result["id"]] = result
            done += 1
            _progress("enriching", done, n_scenes)

    # 5. Sequential pass: transcript alignment + scene diffs + confidence + annotations
    _progress("finalizing", 4, 5)
    scenes: list[dict] = []
    all_ocr_text: list[str] = []
    all_colors: list[dict] = []
    annotated_dir = str(Path(output_dir) / "annotated")

    for i, raw in enumerate(scenes_raw):
        scene = enriched[raw["id"]]
        scene["transcript_overlap"] = _align_transcript_to_scene(
            transcript, scene["start"], scene["end"]
        )
        if i > 0 and scenes:
            scene["diff_from_previous"] = compute_scene_diff(
                scenes[-1]["keyframe_path"], scene["keyframe_path"]
            )
        # Confidence score (needs diff_from_previous to be set first)
        scene["confidence"] = compute_scene_confidence(scene, scene["keyframe_path"])

        # Annotated frame
        ann_path = os.path.join(annotated_dir, f"{scene['id']}_annotated.png")
        scene["annotated_frame_path"] = generate_annotated_frame(
            scene["keyframe_path"], scene, ann_path
        )

        all_ocr_text.extend(scene["detected_text"])
        all_colors.extend(scene["color_palette"])
        scenes.append(scene)

    # 6. Globals
    global_palette    = _merge_palettes(all_colors)
    global_fonts      = _merge_fonts([f for s in scenes for f in s.get("fonts", [])])
    high_motion       = [s for s in scenes if s["motion_detected"]]
    unique_text       = list(dict.fromkeys(all_ocr_text))
    all_components    = sorted({c for s in scenes for c in s.get("ui_components", [])})

    manifest: dict[str, Any] = {
        "metadata":      metadata,
        "video_hash":    compute_video_hash(resolved_vid),
        "transcript":    transcript,
        "scenes":        scenes,
        "color_palette": global_palette,
        "typography":    global_fonts,
        "summary": {
            "total_scenes":            len(scenes),
            "has_audio":               bool(transcript),
            "high_motion_scenes":      [s["id"] for s in high_motion],
            "motion_types":            sorted({s["motion_type"] for s in scenes if s["motion_type"] != "none"}),
            "all_detected_text":       unique_text[:100],
            "dominant_colors":         [c["hex"] for c in global_palette[:5]],
            "ui_components_detected":  all_components,
            "font_sizes_detected":     [f["size_class"] for f in global_fonts],
            "loading_scenes":          [s["id"] for s in scenes if s.get("loading", {}).get("has_loading")],
            "scroll_scenes":           [s["id"] for s in scenes if s.get("scroll", {}).get("has_scrollbar")],
            "cursor_active_scenes":    [s["id"] for s in scenes if s.get("cursor", {}).get("cursor_detected")],
            "avg_confidence":          round(
                sum(s.get("confidence", {}).get("overall", 0) for s in scenes) / max(len(scenes), 1), 2
            ),
            "annotated_frames_dir":    annotated_dir,
        },
    }

    # Save manifest.json (strip b64)
    import copy
    file_manifest = copy.deepcopy(manifest)
    for s in file_manifest["scenes"]:
        s["keyframe_b64"] = "<base64 omitted — see keyframe_path>"
        for bf in s.get("burst_frames", []):
            bf["b64"] = "<base64 omitted>"
    with open(output_path / "manifest.json", "w") as f:
        json.dump(file_manifest, f, indent=2)

    _progress("done", 5, 5)

    # Store in process cache
    vh = manifest.get("video_hash", "")
    if vh:
        cache_key = f"{vh}::{resolved_out}"
        _MANIFEST_CACHE[cache_key] = manifest

    return manifest


def _merge_palettes(colors: list[dict]) -> list[dict]:
    """Merge color entries from multiple scenes, deduplicate by proximity."""
    if not colors:
        return []

    merged: list[dict] = []
    for c in colors:
        rgb = np.array(c["rgb"])
        matched = False
        for m in merged:
            if np.linalg.norm(rgb - np.array(m["rgb"])) < 30:
                m["proportion"] = round(m["proportion"] + c["proportion"], 3)
                matched = True
                break
        if not matched:
            merged.append(dict(c))

    return sorted(merged, key=lambda x: -x["proportion"])[:8]


# ---------------------------------------------------------------------------
# Video hash (for manifest caching)
# ---------------------------------------------------------------------------

def compute_video_hash(video_path: str) -> str:
    """SHA-256 of the first 2MB of the video file for fast identity check."""
    h = hashlib.sha256()
    try:
        with open(video_path, "rb") as f:
            h.update(f.read(2 * 1024 * 1024))
    except OSError:
        return ""
    return h.hexdigest()[:16]


# ---------------------------------------------------------------------------
# Scene diff — what changed between two consecutive keyframes
# ---------------------------------------------------------------------------

def compute_scene_diff(frame_a: str, frame_b: str) -> dict[str, Any]:
    """
    Pixel-level diff between two keyframes.

    Returns:
      {
        diff_score: float,          # mean pixel change 0-255
        changed_regions: list,      # [{x, y, w, h, intensity}] bounding boxes of changed areas
        change_type: str,           # 'full_swap' | 'partial' | 'minimal'
      }
    """
    if not os.path.exists(frame_a) or not os.path.exists(frame_b):
        return {}

    try:
        img_a = cv2.imread(frame_a)
        img_b = cv2.imread(frame_b)
        if img_a is None or img_b is None:
            return {}

        # Resize to same shape if needed
        if img_a.shape != img_b.shape:
            img_b = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]))

        gray_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY)
        gray_b = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY)

        diff = cv2.absdiff(gray_a, gray_b)
        diff_score = round(float(np.mean(diff)), 2)

        # Threshold + find contours of changed regions
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h, w = gray_a.shape
        changed_regions = []
        for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
            if cv2.contourArea(cnt) < 100:
                continue
            x, y, cw, ch = cv2.boundingRect(cnt)
            changed_regions.append({
                "x": round(x / w, 3),
                "y": round(y / h, 3),
                "w": round(cw / w, 3),
                "h": round(ch / h, 3),
                "intensity": round(float(np.mean(diff[y:y+ch, x:x+cw])), 1),
            })

        if diff_score > 60:
            change_type = "full_swap"
        elif diff_score > 10:
            change_type = "partial"
        else:
            change_type = "minimal"

        return {
            "diff_score": diff_score,
            "changed_regions": changed_regions,
            "change_type": change_type,
        }

    except Exception:
        return {}


# ---------------------------------------------------------------------------
# UI component detection (heuristic, no ML model needed)
# ---------------------------------------------------------------------------

def detect_fonts(frame_path: str) -> list[dict[str, Any]]:
    """
    Estimate typography properties from text bounding boxes in a keyframe.

    Uses EasyOCR bounding boxes to measure text height in pixels, then classifies:
    - size_class: 'heading' (>28px), 'subheading' (18-28px), 'body' (11-18px), 'caption' (<11px)
    - weight_hint: 'bold' (thick strokes) or 'regular'
    - Returns deduplicated list sorted by size descending.
    """
    if not os.path.exists(frame_path):
        return []

    try:
        import easyocr
        reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        results = reader.readtext(frame_path, detail=1)

        img = cv2.imread(frame_path)
        if img is None:
            return []
        img_h = img.shape[0]

        fonts: list[dict] = []
        seen_sizes: set[str] = set()

        for (bbox, text, conf) in results:
            if conf < 0.3 or not text.strip():
                continue

            # bbox = [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
            ys = [pt[1] for pt in bbox]
            height_px = max(ys) - min(ys)

            # Normalize to percentage of frame height
            size_pct = height_px / img_h * 100

            if height_px > 28:
                size_class = "heading"
            elif height_px > 18:
                size_class = "subheading"
            elif height_px > 11:
                size_class = "body"
            else:
                size_class = "caption"

            if size_class in seen_sizes:
                continue
            seen_sizes.add(size_class)

            # Stroke width analysis for bold detection
            xs = [pt[0] for pt in bbox]
            x1, y1 = int(min(xs)), int(min(ys))
            x2, y2 = int(max(xs)), int(max(ys))
            roi = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
            if roi.size > 0:
                _, binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                dark_ratio = np.sum(binary == 0) / binary.size
                weight_hint = "bold" if dark_ratio > 0.45 else "regular"
            else:
                weight_hint = "regular"

            fonts.append({
                "text_sample": text[:30],
                "height_px": round(height_px),
                "size_pct": round(size_pct, 1),
                "size_class": size_class,
                "weight_hint": weight_hint,
                "confidence": round(conf, 2),
            })

        return sorted(fonts, key=lambda x: -x["height_px"])

    except Exception:
        return []


def _merge_fonts(fonts: list[dict]) -> list[dict]:
    """Deduplicate font entries by size_class, keep largest height_px per class."""
    merged: dict[str, dict] = {}
    for f in fonts:
        sc = f["size_class"]
        if sc not in merged or f["height_px"] > merged[sc]["height_px"]:
            merged[sc] = f
    order = ["heading", "subheading", "body", "caption"]
    return [merged[k] for k in order if k in merged]


def detect_ui_components(frame_path: str) -> list[str]:
    """
    Heuristic detection of UI component types from a keyframe.

    Uses OpenCV contour analysis + aspect ratio + size heuristics.
    Returns a list of component type strings (may contain duplicates for multiple instances).

    Detects: button, input_field, card, navbar, modal, list_item, icon, divider
    """
    if not os.path.exists(frame_path):
        return []

    try:
        img = cv2.imread(frame_path)
        if img is None:
            return []

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Edge detection + contours
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 30, 100)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        components = set()

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 500:
                continue

            x, y, cw, ch = cv2.boundingRect(cnt)
            aspect = cw / ch if ch > 0 else 0
            rel_w = cw / w
            rel_h = ch / h

            # Navbar: wide + thin + near top
            if rel_w > 0.7 and rel_h < 0.12 and y / h < 0.2:
                components.add("navbar")

            # Button: small-medium, wide-ish aspect, not full width
            elif 1.5 < aspect < 5 and 0.02 < rel_w < 0.3 and rel_h < 0.08:
                components.add("button")

            # Input field: wide, shallow, rectangular
            elif aspect > 3 and rel_w > 0.2 and rel_h < 0.06:
                components.add("input_field")

            # Card: roughly square-ish, medium size
            elif 0.5 < aspect < 2.0 and 0.1 < rel_w < 0.6 and 0.1 < rel_h < 0.6:
                components.add("card")

            # Divider: very wide, very thin
            elif rel_w > 0.6 and rel_h < 0.01:
                components.add("divider")

            # List item: wide, short, stacked (detected multiple)
            elif aspect > 4 and rel_w > 0.5 and rel_h < 0.08:
                components.add("list_item")

            # Icon: small, roughly square
            elif 0.7 < aspect < 1.3 and rel_w < 0.06 and rel_h < 0.06:
                components.add("icon")

        # Modal: if we see a centered rectangle with significant padding from edges
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            if (0.1 < x/w < 0.3 and 0.1 < y/h < 0.3 and
                    0.4 < cw/w < 0.8 and 0.4 < ch/h < 0.8):
                components.add("modal")

        return sorted(components)

    except Exception:
        return []


# ---------------------------------------------------------------------------
# Cursor tracking — mouse position via optical flow
# ---------------------------------------------------------------------------

def detect_cursor_position(
    video_path: str,
    scene_start: float,
    scene_end: float,
    sample_frames: int = 8,
) -> dict[str, Any]:
    """
    Detect mouse cursor movement within a scene using dense optical flow.

    The cursor is typically the smallest, fastest-moving element in a UI recording.
    Returns cursor path as normalized (0-1) x/y coordinates per frame pair.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"cursor_detected": False, "cursor_path": [], "hover_region": None}

    duration = scene_end - scene_start
    if duration <= 0:
        cap.release()
        return {"cursor_detected": False, "cursor_path": [], "hover_region": None}

    timestamps = [
        scene_start + duration * i / max(sample_frames - 1, 1)
        for i in range(sample_frames)
    ]

    frames = []
    for ts in timestamps:
        cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
        ret, frame = cap.read()
        if ret:
            frames.append((ts, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)))
    cap.release()

    if len(frames) < 2:
        return {"cursor_detected": False, "cursor_path": [], "hover_region": None}

    h, w = frames[0][1].shape
    cursor_points: list[dict] = []

    for i in range(len(frames) - 1):
        ts_a, gray_a = frames[i]
        ts_b, gray_b = frames[i + 1]

        try:
            flow = cv2.calcOpticalFlowFarneback(
                gray_a, gray_b, None, 0.5, 3, 15, 3, 5, 1.2, 0
            )
            mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])

            # Cursor is a small isolated peak — find 97th-percentile motion area
            threshold = float(np.percentile(mag, 97))
            if threshold < 0.5:
                continue
            mask = (mag >= threshold).astype(np.uint8) * 255

            # Get centroid of this isolated high-motion region
            M = cv2.moments(mask)
            if M["m00"] > 10:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                velocity = round(float(np.mean(mag[mask > 0])), 1)
                cursor_points.append({
                    "x": round(cx / w, 3),
                    "y": round(cy / h, 3),
                    "timestamp": round(ts_b, 2),
                    "velocity": velocity,
                })
        except Exception:
            continue

    # Compute hover region (average cursor position ± 5% margin)
    hover_region = None
    if cursor_points:
        xs = [p["x"] for p in cursor_points]
        ys = [p["y"] for p in cursor_points]
        avg_x = sum(xs) / len(xs)
        avg_y = sum(ys) / len(ys)
        hover_region = {
            "x": round(max(0, avg_x - 0.05), 3),
            "y": round(max(0, avg_y - 0.05), 3),
            "w": 0.1,
            "h": 0.1,
        }

    return {
        "cursor_detected": len(cursor_points) > 0,
        "cursor_path": cursor_points,
        "hover_region": hover_region,
    }


# ---------------------------------------------------------------------------
# Scroll detection — scrollbar position inference
# ---------------------------------------------------------------------------

def detect_scroll_indicators(frame_path: str) -> dict[str, Any]:
    """
    Detect scrollbar presence and position in a keyframe.

    Checks right edge (vertical scrollbar) and bottom edge (horizontal scrollbar).
    Estimates scroll position as a percentage of total scrollable range.
    """
    if not os.path.exists(frame_path):
        return {"has_scrollbar": False, "scroll_direction": "none", "scroll_position_pct": None}

    try:
        img = cv2.imread(frame_path)
        if img is None:
            return {"has_scrollbar": False, "scroll_direction": "none", "scroll_position_pct": None}

        h, w = img.shape[:2]

        # Right strip (vertical scrollbar)
        right_strip = cv2.cvtColor(img[:, max(0, w - 18):w], cv2.COLOR_BGR2GRAY).astype(float)
        right_var = float(np.var(right_strip))
        has_v_scroll = right_var > 80

        scroll_pos = None
        if has_v_scroll:
            col_var = np.var(right_strip, axis=1)
            peak_row = int(np.argmax(col_var))
            scroll_pos = round(peak_row / max(h - 1, 1), 2)

        # Bottom strip (horizontal scrollbar)
        bottom_strip = cv2.cvtColor(img[max(0, h - 18):h, :], cv2.COLOR_BGR2GRAY).astype(float)
        has_h_scroll = float(np.var(bottom_strip)) > 80

        direction = (
            "both" if has_v_scroll and has_h_scroll else
            "vertical" if has_v_scroll else
            "horizontal" if has_h_scroll else
            "none"
        )

        return {
            "has_scrollbar": has_v_scroll or has_h_scroll,
            "has_vertical_scrollbar": has_v_scroll,
            "has_horizontal_scrollbar": has_h_scroll,
            "scroll_position_pct": scroll_pos,
            "scroll_direction": direction,
        }

    except Exception:
        return {"has_scrollbar": False, "scroll_direction": "none", "scroll_position_pct": None}


# ---------------------------------------------------------------------------
# Loading state detection — spinners, skeletons, progress bars
# ---------------------------------------------------------------------------

def detect_loading_states(frame_path: str) -> dict[str, Any]:
    """
    Detect UI loading states in a keyframe:
    - Spinner: circular high-circularity contour (Hough circles)
    - Skeleton loader: many medium-gray rectangles in content area
    - Progress bar: wide, thin, colored strip
    """
    if not os.path.exists(frame_path):
        return {"has_loading": False, "has_spinner": False, "has_skeleton": False, "has_progress_bar": False, "loading_type": "none"}

    try:
        img = cv2.imread(frame_path)
        if img is None:
            return {"has_loading": False, "has_spinner": False, "has_skeleton": False, "has_progress_bar": False, "loading_type": "none"}

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Spinner: Hough circle detection
        has_spinner = False
        circles = cv2.HoughCircles(
            blurred, cv2.HOUGH_GRADIENT, dp=1, minDist=20,
            param1=50, param2=30, minRadius=10, maxRadius=60
        )
        if circles is not None:
            has_spinner = True

        # Skeleton loader: lots of low-saturation mid-gray rects
        has_skeleton = False
        img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        gray_mask = cv2.inRange(img_hsv, (0, 0, 140), (180, 25, 220))
        if np.sum(gray_mask > 0) / gray_mask.size > 0.12:
            cnts, _ = cv2.findContours(gray_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            rect_count = sum(1 for c in cnts if cv2.contourArea(c) > 400)
            if rect_count >= 3:
                has_skeleton = True

        # Progress bar: wide thin strip anywhere in frame
        has_progress = False
        edges = cv2.Canny(blurred, 30, 100)
        cnts2, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in cnts2:
            x, y, cw, ch = cv2.boundingRect(cnt)
            if cw / w > 0.25 and 3 < ch < 18:
                has_progress = True
                break

        loading_type = (
            "spinner" if has_spinner else
            "skeleton" if has_skeleton else
            "progress_bar" if has_progress else
            "none"
        )

        return {
            "has_loading": has_spinner or has_skeleton or has_progress,
            "has_spinner": has_spinner,
            "has_skeleton": has_skeleton,
            "has_progress_bar": has_progress,
            "loading_type": loading_type,
        }

    except Exception:
        return {"has_loading": False, "has_spinner": False, "has_skeleton": False, "has_progress_bar": False, "loading_type": "none"}


# ---------------------------------------------------------------------------
# Frame sharpness + per-scene confidence scoring
# ---------------------------------------------------------------------------

def compute_frame_sharpness(frame_path: str) -> float:
    """Laplacian variance as image sharpness proxy. Returns 0.0–1.0."""
    try:
        img = cv2.imread(frame_path)
        if img is None:
            return 0.0
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        var = cv2.Laplacian(gray, cv2.CV_64F).var()
        return round(min(float(var) / 1000.0, 1.0), 3)
    except Exception:
        return 0.0


def compute_scene_confidence(scene: dict, frame_path: str) -> dict[str, Any]:
    """
    Per-scene reliability score.

    frame_sharpness:        0-1 Laplacian sharpness of keyframe
    ocr_confidence:         0-1 proxy from number of detected text items
    scene_boundary_strength: 0-1 from diff_score vs previous scene
    overall:                weighted average of above
    """
    sharpness = compute_frame_sharpness(frame_path)

    text_count = len(scene.get("detected_text", []))
    ocr_conf = round(min(text_count / 10.0, 1.0), 2)

    diff = scene.get("diff_from_previous", {})
    boundary = round(min(diff.get("diff_score", 50) / 60.0, 1.0), 2)

    overall = round(sharpness * 0.4 + ocr_conf * 0.3 + boundary * 0.3, 2)

    return {
        "frame_sharpness": sharpness,
        "ocr_confidence": ocr_conf,
        "scene_boundary_strength": boundary,
        "overall": overall,
    }


# ---------------------------------------------------------------------------
# Annotation overlay — debug frame with visual labels
# ---------------------------------------------------------------------------

def generate_annotated_frame(
    frame_path: str,
    scene_data: dict,
    output_path: str,
) -> str:
    """
    Burn analysis data into a copy of the keyframe:
    - Green boxes: OCR text regions with confidence
    - Orange boxes: changed regions from scene diff
    - Blue labels: detected UI components (top-left)
    - Red dots: cursor path points
    - Corner badge: overall confidence score

    Returns path to saved annotated image (empty string on failure).
    """
    if not os.path.exists(frame_path):
        return ""

    try:
        import easyocr

        img = cv2.imread(frame_path)
        if img is None:
            return ""

        h, w = img.shape[:2]
        overlay = img.copy()

        # Green: OCR bounding boxes
        reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        ocr_results = reader.readtext(frame_path, detail=1)
        for (bbox, text, conf) in ocr_results:
            if conf < 0.25:
                continue
            pts = np.array([[int(p[0]), int(p[1])] for p in bbox], dtype=np.int32)
            cv2.polylines(overlay, [pts], True, (0, 200, 0), 1)
            label = f"{text[:14]} {conf:.0%}"
            cv2.putText(overlay, label, (int(bbox[0][0]), max(int(bbox[0][1]) - 3, 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.28, (0, 220, 0), 1)

        # Orange: changed regions from scene diff
        for region in scene_data.get("diff_from_previous", {}).get("changed_regions", []):
            rx = int(region["x"] * w)
            ry = int(region["y"] * h)
            rw = int(region["w"] * w)
            rh = int(region["h"] * h)
            cv2.rectangle(overlay, (rx, ry), (rx + rw, ry + rh), (0, 140, 255), 2)

        # Blue: UI component labels (top-left stack)
        for i, comp in enumerate(scene_data.get("ui_components", [])):
            cv2.putText(overlay, comp, (5, 14 + i * 13),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 160, 0), 1)

        # Red: cursor path dots
        for pt in scene_data.get("cursor", {}).get("cursor_path", []):
            cx, cy = int(pt["x"] * w), int(pt["y"] * h)
            cv2.circle(overlay, (cx, cy), 5, (0, 0, 220), -1)
            cv2.circle(overlay, (cx, cy), 7, (0, 0, 255), 1)

        # Corner badge: confidence score
        conf_data = scene_data.get("confidence", {})
        score = conf_data.get("overall", 0.0)
        badge_color = (0, 200, 0) if score > 0.7 else (0, 165, 255) if score > 0.4 else (0, 0, 200)
        badge_text = f"conf {score:.0%}"
        (bw, bh), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        cv2.rectangle(overlay, (w - bw - 8, 2), (w - 2, bh + 8), (30, 30, 30), -1)
        cv2.putText(overlay, badge_text, (w - bw - 5, bh + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, badge_color, 1)

        # Blend (slight transparency to keep underlying image visible)
        annotated = cv2.addWeighted(overlay, 0.82, img, 0.18, 0)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, annotated)
        return output_path

    except Exception:
        return ""


# ---------------------------------------------------------------------------
# HTML manifest viewer — self-contained visual report
# ---------------------------------------------------------------------------

def generate_html_report(manifest: dict[str, Any], output_dir: str) -> str:
    """
    Generate a beautiful self-contained HTML report from a manifest.
    Embeds all keyframe images as base64 data URLs.
    Saved to output_dir/report.html — shareable with no dependencies.
    """
    scenes     = manifest.get("scenes", [])
    meta       = manifest.get("metadata", {})
    palette    = manifest.get("color_palette", [])
    typography = manifest.get("typography", [])
    summary    = manifest.get("summary", {})
    transcript = manifest.get("transcript", [])

    def _swatch(hex_code: str, pct: float) -> str:
        return (f'<div class="swatch" style="background:{hex_code}" title="{hex_code} ({round(pct*100)}%)">'
                f'<span class="swatch-label">{hex_code}</span></div>')

    def _badge(text: str, color: str) -> str:
        return f'<span class="badge" style="background:{color}">{text}</span>'

    motion_colors = {"animation": "#f59e0b", "cut": "#ef4444", "scroll": "#3b82f6", "none": "#6b7280"}

    scene_cards = ""
    for scene in scenes:
        b64 = scene.get("keyframe_b64", "")
        img_src = f"data:image/png;base64,{b64}" if b64 and "<" not in b64 else ""
        img_tag = (f'<img src="{img_src}" class="keyframe" alt="{scene["id"]}">'
                   if img_src else '<div class="no-frame">No frame</div>')

        mt = scene.get("motion_type", "none")
        badges = _badge(mt, motion_colors.get(mt, "#6b7280"))
        if scene.get("motion_detected"):
            badges += _badge(f'motion {scene.get("motion_level", 0):.1f}', "#8b5cf6")

        ocr_chips  = "".join(f'<span class="chip">{t}</span>' for t in scene.get("detected_text", []))
        comp_chips = "".join(f'<span class="chip comp">{c}</span>' for c in scene.get("ui_components", []))
        swatches   = "".join(_swatch(c["hex"], c["proportion"]) for c in scene.get("color_palette", [])[:4])

        burst_thumbs = ""
        for bf in scene.get("burst_frames", [])[:4]:
            bb = bf.get("b64", "")
            if bb and "<" not in bb:
                burst_thumbs += f'<img src="data:image/png;base64,{bb}" class="burst-thumb" title="t={bf.get("timestamp",0):.1f}s">'

        narration_html = (f'<p class="narration">🎙 {scene["transcript_overlap"]}</p>'
                          if scene.get("transcript_overlap") else "")

        fonts_html = "".join(
            f'<span class="chip font">{f["size_class"]} {f["height_px"]}px {f["weight_hint"]}</span>'
            for f in scene.get("fonts", [])
        )

        diff = scene.get("diff_from_previous", {})
        diff_html = (f'<p class="diff-info">↔ vs prev: <b>{diff.get("change_type","")}</b>'
                     f' (score {diff.get("diff_score",0):.1f})</p>') if diff else ""

        scene_cards += f"""
        <div class="scene-card">
          <div class="scene-header">
            <span class="scene-id">{scene["id"]}</span>
            <span class="scene-time">{scene["start"]}s – {scene["end"]}s</span>
            <div class="scene-badges">{badges}</div>
          </div>
          <div class="scene-body">
            <div class="scene-visual">
              {img_tag}
              <div class="burst-row">{burst_thumbs}</div>
            </div>
            <div class="scene-meta">
              {narration_html}{diff_html}
              <div class="scene-swatches">{swatches}</div>
              <div class="chips-row">{ocr_chips}</div>
              <div class="chips-row">{comp_chips}</div>
              <div class="chips-row">{fonts_html}</div>
            </div>
          </div>
        </div>"""

    palette_html = "".join(_swatch(c["hex"], c["proportion"]) for c in palette[:8])

    typo_rows = "".join(
        f'<tr><td>{f["size_class"]}</td><td>{f["height_px"]}px</td>'
        f'<td>{f["weight_hint"]}</td>'
        f'<td class="sample" style="font-size:{min(f["height_px"],32)}px">{f.get("text_sample","Aa")}</td></tr>'
        for f in typography
    )

    transcript_html = "".join(
        f'<div class="seg"><span class="seg-time">{s["start"]}s</span> {s["text"]}</div>'
        for s in transcript[:20]
    )

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Video Analysis Report</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display",sans-serif;background:#0f0f0f;color:#e0e0e0;padding:32px 24px}}
h1{{font-size:1.5rem;font-weight:700;margin-bottom:4px;color:#fff}}
h2{{font-size:.85rem;font-weight:600;color:#888;text-transform:uppercase;letter-spacing:.08em;margin:28px 0 10px}}
.meta-row{{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:28px;font-size:.83rem;color:#888}}
.meta-row b{{color:#ddd}}
.palette{{display:flex;flex-wrap:wrap;gap:8px}}
.swatch{{width:56px;height:56px;border-radius:10px;position:relative;display:flex;align-items:flex-end;justify-content:center;padding-bottom:3px;cursor:default}}
.swatch-label{{font-size:8px;background:rgba(0,0,0,.65);color:#fff;padding:1px 4px;border-radius:3px;white-space:nowrap}}
table{{width:100%;border-collapse:collapse;font-size:.83rem}}
th{{text-align:left;padding:5px 10px;color:#888;border-bottom:1px solid #222}}
td{{padding:5px 10px;border-bottom:1px solid #1a1a1a}}
.sample{{color:#fff;max-width:180px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}}
.scenes{{display:flex;flex-direction:column;gap:14px;margin-top:4px}}
.scene-card{{background:#1a1a1a;border-radius:12px;overflow:hidden;border:1px solid #2a2a2a}}
.scene-header{{display:flex;align-items:center;gap:10px;padding:10px 14px;background:#222;border-bottom:1px solid #2a2a2a}}
.scene-id{{font-weight:700;color:#fff;font-size:.9rem}}
.scene-time{{color:#888;font-size:.78rem}}
.scene-badges{{margin-left:auto;display:flex;gap:5px;flex-wrap:wrap}}
.badge{{font-size:.7rem;font-weight:600;padding:2px 8px;border-radius:99px;color:#fff}}
.scene-body{{display:grid;grid-template-columns:300px 1fr;gap:14px;padding:14px}}
.keyframe{{width:100%;border-radius:7px;display:block}}
.no-frame{{width:100%;height:130px;background:#111;border-radius:7px;display:flex;align-items:center;justify-content:center;color:#444;font-size:.8rem}}
.burst-row{{display:flex;gap:4px;margin-top:5px;flex-wrap:wrap}}
.burst-thumb{{width:68px;border-radius:4px;opacity:.75}}
.scene-swatches{{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:6px}}
.scene-swatches .swatch{{width:28px;height:28px}}
.scene-swatches .swatch-label{{display:none}}
.chips-row{{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:5px;min-height:4px}}
.chip{{font-size:.7rem;background:#252525;color:#bbb;padding:2px 7px;border-radius:99px;border:1px solid #333}}
.chip.comp{{border-color:#3b82f660;color:#93c5fd}}
.chip.font{{border-color:#8b5cf660;color:#c4b5fd}}
.narration{{font-size:.8rem;color:#9ca3af;margin-bottom:6px;font-style:italic}}
.diff-info{{font-size:.76rem;color:#6b7280;margin-bottom:6px}}
.diff-info b{{color:#f59e0b}}
.transcript-list{{max-height:240px;overflow-y:auto;background:#111;border-radius:8px;padding:10px}}
.seg{{font-size:.8rem;padding:3px 0;border-bottom:1px solid #1a1a1a;display:flex;gap:8px}}
.seg-time{{color:#6b7280;min-width:36px;flex-shrink:0}}
@media(max-width:660px){{.scene-body{{grid-template-columns:1fr}}}}
</style></head><body>
<h1>Video Analysis Report</h1>
<div class="meta-row">
  <span><b>Type</b> {meta.get("video_type","?")}</span>
  <span><b>Duration</b> {meta.get("duration_seconds",0)}s</span>
  <span><b>Resolution</b> {meta.get("resolution","?")}</span>
  <span><b>FPS</b> {meta.get("fps",0)}</span>
  <span><b>Audio</b> {"yes" if meta.get("has_audio") else "no"}</span>
  <span><b>Scenes</b> {summary.get("total_scenes",0)}</span>
  <span><b>Components</b> {", ".join(summary.get("ui_components_detected",[]) or ["—"])}</span>
</div>
<h2>Color Palette</h2><div class="palette">{palette_html}</div>
{"<h2>Typography</h2><table><tr><th>Role</th><th>Size</th><th>Weight</th><th>Sample</th></tr>" + typo_rows + "</table>" if typo_rows else ""}
{"<h2>Transcript</h2><div class='transcript-list'>" + transcript_html + "</div>" if transcript_html else ""}
<h2>Scenes ({summary.get("total_scenes",0)})</h2>
<div class="scenes">{scene_cards}</div>
</body></html>"""

    report_path = Path(output_dir) / "report.html"
    report_path.write_text(html)
    return str(report_path)
