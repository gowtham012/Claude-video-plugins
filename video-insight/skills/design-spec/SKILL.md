---
name: design-spec
description: Generate a Figma-style design specification from a video — color tokens, component inventory, exact copy, motion catalogue, and spacing hints in one document.
disable-model-invocation: true
allowed-tools: mcp__video-insight__design_spec
argument-hint: <video_path>
---

Generate design spec from video: $ARGUMENTS

## Steps

1. Call MCP tool `mcp__video-insight__design_spec` with `video_path` = `$0`.
2. Read keyframe images from `keyframes_dir` and burst frames from `burst_frames_dir`.
3. Use `color_tokens` for semantic assignments (background/surface/accent/text).
4. Use `text_inventory` for exact copy per scene.
5. Use `motion_inventory` to document transitions.
6. Infer components from keyframe images.
7. Output a structured spec:

```markdown
## Design Spec: <filename>

### Metadata
- Type / Duration / Scenes / Resolution

### Color Tokens
| Token | Hex | Usage |
|-------|-----|-------|
| background | #141414 | Page background |
| surface | #2a2a2a | Cards |
| accent | #c8921c | CTAs |
| text | #f0f0f0 | Primary text |

### Full Palette
[swatches with hex + proportion]

### Components Detected
- [Component name, layout, state variants]

### Copy Inventory
scene_0: ["Headline", "CTA", ...]

### Motion Catalogue
| Scene | Type | CSS |
|-------|------|-----|
| scene_0 | animation | transition: all 0.4s ease |
```
