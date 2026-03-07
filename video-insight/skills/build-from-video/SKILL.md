---
name: build-from-video
description: Generate pixel-perfect frontend code (React or HTML) from a screen recording. Analyzes keyframes, OCR text, colors, and motion to reconstruct the UI as working code.
disable-model-invocation: true
allowed-tools: mcp__video-insight__build_frontend_from_video
argument-hint: <video_path> [react|html] [output_dir]
---

Build frontend from video: $ARGUMENTS

Arguments:
- `$0` = video_path (required)
- `$1` = framework: `react` or `html` (default: `react`)
- `$2` = output_dir (default: `./output`)

## Steps

1. Call MCP tool `mcp__video-insight__build_frontend_from_video` with:
   - `video_path` = `$0`
   - `framework` = `$1` if provided, else `react`
   - `output_dir` = `$2` if provided, else `./output`

2. The tool returns `files_created`, `scene_count`, `framework`. Read the generated files and display them.

3. Provide a brief summary:
   - UI components generated
   - Scenes that contributed most content
   - Sections where OCR text or transcript filled in exact copy
   - Suggested next steps (routing, API connections, etc.)

## Output files

**React:** `App.jsx` + `App.css`
**HTML:** `index.html` (self-contained, inline CSS + JS)
