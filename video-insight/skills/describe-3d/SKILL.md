---
name: describe-3d
description: Analyze 3D walkthroughs, CAD recordings, or game engine captures. Classifies camera movement (orbit, pan, dolly, cut) per scene and produces a structured 3D scene description with materials and color palette.
disable-model-invocation: true
allowed-tools: mcp__video-insight__describe_3d
argument-hint: <video_path>
---

Describe 3D video: $ARGUMENTS

## Steps

1. Call MCP tool `mcp__video-insight__describe_3d` with `video_path` = `$0`.
2. Read every keyframe from `keyframes_dir` and burst frames from `burst_frames_dir`.
3. For each scene, note the `camera_movement` type:
   - `orbit_or_pan` — camera rotating around or panning across subject
   - `dolly_or_zoom` — camera moving toward/away from subject
   - `camera_cut` — instant cut to new angle
   - `static` — no camera movement
4. Output:

```markdown
## 3D Scene Analysis: <filename>

### Overview
<What is the 3D subject? Product, architecture, character, environment?>

### Camera Path
1. scene_0 (0s–5s): Static — [what's visible]
2. scene_1 (5s–12s): Orbit left — [new details revealed]

### Materials & Lighting
- Primary material / Lighting / Background

### Geometry Notes
- Notable shapes, symmetry, distinctive details

### Color Palette
[Material colors from extracted palette]
```
