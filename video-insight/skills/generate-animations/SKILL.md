---
name: generate-animations
description: Generate CSS @keyframes or Framer Motion code from a video's animated scenes. Uses burst frames as keyframe states to replicate the exact motion shown.
disable-model-invocation: true
allowed-tools: mcp__video-insight__generate_animations
argument-hint: <video_path> [css|framer-motion]
---

Generate animation code from video: $ARGUMENTS

Arguments:
- `$0` = video_path (required)
- `$1` = framework: `css` or `framer-motion` (default: `css`)

## Steps

1. Call MCP tool `mcp__video-insight__generate_animations` with `video_path` = `$0`, `framework` = `$1` (default `css`).
2. For each high-motion scene, read all burst frame images in order:
   - `burst_frame_paths[0]` = animation start state
   - `burst_frame_paths[-1]` = animation end state
   - Intermediate frames = easing curve snapshots
   - `frame_interval_ms` = timing between stops
   - `duration_seconds` = total animation duration
3. Identify what property is animating (opacity, transform, color, size, position).
4. Write one animation block per scene using exact values from the frames.
5. Output complete, copy-paste-ready code.
