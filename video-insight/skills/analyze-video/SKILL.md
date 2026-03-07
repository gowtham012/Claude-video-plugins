---
name: analyze-video
description: Deep analysis of any video file — extracts keyframes, OCR text, motion events, transcript, and color palette. Use when asked to analyze, understand, or describe a video.
disable-model-invocation: true
allowed-tools: mcp__video-insight__analyze_video
argument-hint: <video_path>
---

Analyze the video at path: $ARGUMENTS

## Steps

1. Call MCP tool `mcp__video-insight__analyze_video` with:
   - `video_path` = `$0`
   - `output_dir` = `./video_analysis` (default)

2. Read the returned manifest carefully:
   - `metadata` — resolution, fps, duration, video type
   - `scenes[]` — each scene's keyframe image, OCR text, motion level, transcript segment
   - `transcript` — full timestamped speech-to-text
   - `summary` — high-level stats and detected UI elements

3. For each scene, examine:
   - Keyframe image (`keyframe_path`)
   - `detected_text` — exact strings visible on screen
   - `transcript_overlap` — narration during this scene
   - `motion_detected` / `motion_level` — animations or changes

4. Produce a structured markdown report:

```
## Video Analysis: <filename>

**Duration:** Xs | **Scenes:** N | **Resolution:** WxH | **Has Audio:** yes/no

### Overview
<2-3 sentence summary>

### Scene Breakdown
| Scene | Time | Summary | Key Text | Motion |
|-------|------|---------|----------|--------|
| 0 | 0s-12s | ... | ... | Low |

### Narration Summary
<condensed transcript>

### Key Content Extracted
- Headlines: ...
- CTAs: ...
- Prices: ...
- Features: ...

### UI/UX Notes
- Layout / Navigation / Color scheme / Interactions
```
