---
name: compare-videos
description: Compare two screen recordings side by side — visual diff, text changes, flow changes, motion differences, and similarity score. Use for A/B testing, before/after reviews, or regression checks.
disable-model-invocation: true
allowed-tools: mcp__video-insight__compare_videos
argument-hint: <video_a> <video_b>
---

Compare videos: $ARGUMENTS

Arguments:
- `$0` = video_a (required)
- `$1` = video_b (required)

## Steps

1. Call MCP tool `mcp__video-insight__compare_videos` with `video_a` = `$0`, `video_b` = `$1`.
2. Read keyframes from both videos.
3. Generate a structured comparison report covering:
   - Visual changes (colors added/removed, UI components)
   - Text changes (new, removed, modified)
   - Flow changes (steps added/removed/reordered)
   - Motion/animation changes
   - Similarity score (overall, visual, text, flow)
   - Recommendation: which version appears more complete/polished and why
