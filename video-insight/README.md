# video-understanding-plugin

**A Claude Code plugin that gives AI deep understanding of any video.**

Feed it a screen recording, 3D walkthrough, or marketing demo — it extracts 10 structured signals and gives Claude everything it needs to build frontend code, write specs, generate tests, compare versions, and more.

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![MCP](https://img.shields.io/badge/protocol-MCP-purple)](https://modelcontextprotocol.io)

---

## The problem

Video is sequential, multi-modal, and time-based. AI can't reason about it natively. This plugin bridges that gap by converting any video into a rich structured **manifest** that Claude can read, reason about, and act on — without needing a separate AI API call.

**Claude Code IS the AI.** The plugin only does extraction.

---

## What it extracts

| Signal | Method | Output |
|--------|--------|--------|
| Smart keyframes | PySceneDetect AdaptiveDetector | One PNG per scene change (not uniform intervals) |
| Burst frames | OpenCV frame sampling | Extra frames inside high-motion scenes for animation states |
| Audio transcript | faster-whisper | Timestamped speech segments |
| OCR text | EasyOCR (threshold 0.25) | Text visible on screen per scene |
| Color palette | OpenCV k-means | Dominant colors with hex + proportion per scene |
| Motion events | Frame differencing | Type: animation / scroll / cut / none |
| Scene diffs | Pixel-level diff | What changed between consecutive scenes, with bounding boxes |
| UI components | Contour heuristics | navbar, button, input, card, modal, list_item, icon, divider |
| Font/typography | EasyOCR bbox analysis | Size class, weight hint, text sample per scene |
| Cursor tracking | Dense optical flow | Mouse path + hover region per scene |
| Scroll indicators | Edge strip analysis | Scrollbar position percentage |
| Loading states | Hough + contour analysis | spinner / skeleton / progress_bar |
| Confidence scores | Sharpness + OCR + boundary | Per-scene reliability 0–1 |

---

## 17 MCP tools

| Tool | What Claude can do with it |
|------|---------------------------|
| `analyze_video` | Full extraction pipeline — generates manifest.json + report.html |
| `build_frontend_from_video` | Build pixel-perfect React or HTML from a screen recording |
| `extract_colors` | Extract a complete design token palette |
| `design_spec` | Generate a full design specification |
| `write_copy` | Extract all visible text + narration verbatim |
| `describe_3d` | Describe geometry, materials, camera path from 3D walkthrough |
| `generate_tests` | Generate Playwright or Cypress test file from screen recording |
| `export_tokens` | Export colors as Tailwind config / CSS variables / Figma tokens |
| `user_flow` | Reconstruct step-by-step user journey |
| `generate_animations` | Generate CSS @keyframes or Framer Motion from animated scenes |
| `watch_directory` | Auto-analyze a folder of videos (hash-cached, safe to re-run) |
| `generate_report` | Self-contained HTML visual report with all keyframes |
| `generate_prd` | Product Requirements Document from a demo video |
| `compare_videos` | Structural A/B diff between two recordings |
| `generate_storybook` | Storybook stories for every detected UI component |
| `generate_changelog` | User-facing changelog from before/after recordings |
| `annotate_video` | Debug frames with OCR boxes, cursor path, motion regions |

## 17 slash skills

Skills are namespaced under `video-understanding:` when installed as a plugin:

```
/video-understanding:analyze-video         /video-understanding:build-from-video
/video-understanding:extract-colors        /video-understanding:design-spec
/video-understanding:write-copy            /video-understanding:describe-3d
/video-understanding:generate-tests        /video-understanding:export-tokens
/video-understanding:user-flow             /video-understanding:generate-animations
/video-understanding:watch                 /video-understanding:generate-report
/video-understanding:generate-prd         /video-understanding:compare-videos
/video-understanding:storybook             /video-understanding:playwright-tests
/video-understanding:changelog
```

---

## How it works

```
Video file
    │
    ├─ ffprobe ─────────────────────→ metadata (duration, resolution, fps, video_type)
    ├─ PySceneDetect ───────────────→ scene boundaries + keyframe PNGs
    ├─ faster-whisper ──────────────→ timestamped transcript
    │
    └─ Per scene (parallel threads):
         ├─ EasyOCR ────────────────→ text visible on screen
         ├─ k-means clustering ─────→ dominant color palette
         ├─ frame differencing ─────→ motion type + level
         ├─ Hough + contours ───────→ UI component detection
         ├─ optical flow ───────────→ cursor path + velocity
         ├─ edge analysis ──────────→ scroll position
         ├─ HoughCircles + gray ────→ loading state type
         ├─ Laplacian variance ─────→ frame sharpness / confidence
         └─ burst frame extraction ─→ animation keyframe states
                     │
               manifest.json + report.html
                     │
              Claude Code reads:
              - All keyframe PNGs
              - Manifest JSON
              - Annotated debug frames
                     │
         ┌───────────────────────────────────┐
         │  React / HTML / Tests / PRD / etc │
         └───────────────────────────────────┘
```

---

## Video Manifest format

Every video produces a structured JSON manifest:

```json
{
  "metadata": {
    "duration_seconds": 13.6,
    "resolution": "1932x1080",
    "fps": 58.0,
    "has_audio": false,
    "video_type": "component_demo"
  },
  "video_hash": "1217c8b0ff429508",
  "scenes": [
    {
      "id": "scene_0",
      "start": 0.0,
      "end": 3.2,
      "keyframe_path": "frames/scene_0.png",
      "detected_text": ["Dashboard", "Analytics"],
      "color_palette": [{"hex": "#131313", "rgb": [19,19,19], "proportion": 0.48}],
      "ui_components": ["navbar", "button", "card"],
      "fonts": [{"size_class": "heading", "height_px": 32, "weight_hint": "bold"}],
      "motion_detected": true,
      "motion_type": "animation",
      "motion_level": 18.7,
      "cursor": {"cursor_detected": true, "cursor_path": [{"x": 0.5, "y": 0.3, "timestamp": 1.2}]},
      "scroll": {"has_scrollbar": false, "scroll_direction": "none"},
      "loading": {"has_loading": false, "loading_type": "none"},
      "confidence": {"frame_sharpness": 0.72, "ocr_confidence": 0.6, "overall": 0.64},
      "annotated_frame_path": "annotated/scene_0_annotated.png",
      "transcript_overlap": "",
      "diff_from_previous": {"diff_score": 45.2, "change_type": "partial"}
    }
  ],
  "color_palette": [{"hex": "#131313", "rgb": [19,19,19], "proportion": 0.48}],
  "typography": [{"size_class": "heading", "height_px": 32, "weight_hint": "bold"}],
  "summary": {
    "total_scenes": 5,
    "ui_components_detected": ["button", "card", "icon"],
    "dominant_colors": ["#131313", "#f8f8f8"],
    "avg_confidence": 0.25,
    "loading_scenes": [],
    "cursor_active_scenes": ["scene_0", "scene_1"]
  }
}
```

---

## Installation

> **Note:** This plugin runs a Python MCP server. Python dependencies must be installed separately — the Claude Code plugin system does not run `pip install` automatically.

### Step 1 — Prerequisites

```bash
brew install ffmpeg          # macOS
sudo apt-get install ffmpeg  # Linux
python3 --version            # must be 3.10+
```

No Anthropic API key required. Claude Code itself handles all AI reasoning.

### Step 2 — Install Python dependencies

```bash
git clone https://github.com/gowtham/video-understanding-plugin
cd video-understanding-plugin
pip install -e .
```

### Step 3 — Install the plugin

**Option A — Official marketplace (recommended once listed):**

```
/plugin install video-understanding@claude-plugins-official
```

**Option B — Direct from GitHub:**

Inside Claude Code:

```
/plugin marketplace add gowtham/video-understanding-plugin
/plugin install video-understanding@video-understanding-plugin
```

**Option C — Local development:**

```bash
claude --plugin-dir /path/to/video-understanding-plugin
```

---

## Usage

```
# Deeply understand a video
/video-understanding:analyze-video /path/to/recording.mov

# Build a React component from a screen recording
/video-understanding:build-from-video /path/to/ui-demo.mp4 react ./src

# Build a self-contained HTML page
/video-understanding:build-from-video /path/to/landing-page.mp4 html

# Extract design tokens (Tailwind + CSS + Figma formats)
/video-understanding:figma-tokens /path/to/design-demo.mp4

# Generate Playwright tests from a user flow recording
/video-understanding:playwright-tests /path/to/checkout-flow.mp4

# Compare two versions of a product
/video-understanding:changelog /path/to/v1.mp4 /path/to/v2.mp4

# Generate Storybook stories for every component
/video-understanding:storybook /path/to/component-library.mp4

# Generate a PRD from a product demo
/video-understanding:generate-prd /path/to/product-demo.mp4

# Auto-analyze a folder of recordings
/video-understanding:watch ~/Desktop/recordings

# Visual debug report with OCR boxes + cursor path
/video-understanding:annotate-video /path/to/recording.mp4
```

---

## macOS screen recordings

macOS sets an access control attribute on screen recordings that blocks ffprobe. Copy the file first:

```bash
cp ~/Desktop/recording.mov /tmp/recording.mov
# then use /tmp/recording.mov with the plugin
```

---

## Performance

The plugin caches manifests in-process and on disk:

- **In-process cache**: Repeated tool calls on the same video within a Claude session return instantly (0ms)
- **Disk cache**: `watch_directory` uses SHA-256 file hashing — skips videos that haven't changed
- **Parallel enrichment**: Per-scene OCR, color, motion, cursor, fonts run simultaneously via `ThreadPoolExecutor`

Analysis time for a 13s 1080p screen recording: ~100s on CPU (mostly EasyOCR initialization).

---

## Running tests

```bash
make install   # pip install -e ".[dev]"
make test      # pytest — no video files or GPU required
```

Tests are fully mocked (ffprobe, cv2, EasyOCR, faster-whisper, PySceneDetect).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs welcome for:

- Better video type auto-detection
- GPU acceleration paths for EasyOCR / faster-whisper
- Multi-language OCR and transcription
- New output skills (Figma export, accessibility audit, etc.)
- Windows/Linux compatibility fixes

---

## License

MIT — see [LICENSE](LICENSE).
