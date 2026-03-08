# video-insight

> Give Claude eyes. Drop any video — get keyframes, OCR text, colors, motion, transcript, and production-ready code.

video-insight is a Claude Code plugin that deeply understands video recordings. Point it at any screen recording, product demo, or video file and it extracts 13 structured signals — then use 12 skills to turn that data into frontend code, design specs, tests, PRDs, user flows, and more.

## Installation

```
/plugin marketplace add gowtham012/Claude-plugins
/plugin install video-insight@Claude-plugins
```

Requires `uv` for dependency management:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Skills

### Analysis

**`/video-insight:analyze-video <path>`**
Full pipeline — extracts all 13 signals and produces a structured markdown report with scene breakdown, key content, and UI/UX notes.

**`/video-insight:extract-colors <path>`**
K-means color clustering across all keyframes. Returns hex codes by dominance, semantic token assignments (background/surface/accent/text), dark/light mode detection, and per-scene palettes.

**`/video-insight:write-copy <path>`**
All visible text via OCR + full narration transcript, organized by scene and order of appearance. Ready to paste verbatim.

**`/video-insight:user-flow <path>`**
Reconstructs the step-by-step user journey from scene transitions, motion types, and text changes. Outputs a numbered markdown flow with timestamps.

**`/video-insight:describe-3d <path>`**
Tuned for 3D walkthroughs and CAD recordings. Classifies camera movement (orbit, pan, dolly, cut) per scene.

### Code generation

**`/video-insight:build-from-video <path> [react|html]`**
Generates pixel-perfect frontend code from a screen recording. Uses keyframes, OCR text, colors, and motion to reconstruct the UI.
- `react` → `App.jsx` + `App.css`
- `html` → `index.html` (self-contained, inline CSS + JS)

**`/video-insight:generate-tests <path> [playwright|cypress]`**
Infers user actions from motion and OCR text changes, then generates a complete test file with real selectors and assertions.

**`/video-insight:generate-animations <path> [css|framer-motion]`**
Uses burst frames as keyframe states to write exact CSS `@keyframes` or Framer Motion code replicating animations from the video.

### Design & documentation

**`/video-insight:design-spec <path>`**
Figma-style design specification — color tokens, component inventory, exact copy, motion catalogue, and spacing hints in one document.

**`/video-insight:export-tokens <path> [tailwind|css|figma|all]`**
Exports the color palette as:
- `tailwind.config.js` — `theme.extend.colors` block
- `tokens.css` — `:root { --color-* }` custom properties
- `figma-tokens.json` — Figma Tokens plugin format

**`/video-insight:generate-prd <path>`**
Full Product Requirements Document from a product demo — overview, user stories, functional requirements, UI specs per screen, and open questions.

**`/video-insight:compare-videos <path_a> <path_b>`**
Structural A/B diff — visual changes, text changes, flow changes, motion differences, similarity score, and a recommendation on which version is more complete.

## What gets extracted

| Signal | Description |
|--------|-------------|
| Keyframes | One representative frame per scene |
| OCR text | Every string visible on screen, timestamped |
| Color palette | Hex codes by dominance + semantic assignments |
| Motion events | Animated scenes with motion type classification |
| Transcript | Full speech-to-text with timestamps |
| Cursor path | Click and movement tracking |
| Scroll indicators | Scroll events detected per scene |
| Loading states | Spinners, skeletons, progress bars |
| Burst frames | High-FPS capture of fast animations |
| Scene diffs | Frame-level visual change detection |
| Fonts | Font detection across keyframes |
| Confidence scores | Reliability rating per extracted signal |
| Video hash | Deduplication across repeated analyses |

## Requirements

- Python 3.10+
- `uv` — manages all ML dependencies automatically on first run
- `ffmpeg` (includes `ffprobe`) — required for video metadata extraction

Install ffmpeg:
```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows (with chocolatey)
choco install ffmpeg
```

Optional (for faster transcription):
- GPU with CUDA support

## License

MIT
