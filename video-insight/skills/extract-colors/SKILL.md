---
name: extract-colors
description: Extract an exact color palette from any video using k-means clustering on keyframes. Returns hex codes by dominance, semantic token assignments, and dark/light mode detection.
disable-model-invocation: true
allowed-tools: mcp__video-insight__extract_colors
argument-hint: <video_path>
---

Extract colors from video: $ARGUMENTS

## Steps

1. Call MCP tool `mcp__video-insight__extract_colors` with `video_path` = `$0`.
2. Read `global_palette` (hex codes by dominance) and `scene_palettes` (per-scene breakdown).
3. Check `has_dark_mode` and `has_light_mode` flags.
4. Output:

```
## Color Palette: <filename>

### Global (sorted by dominance)
| Hex | RGB | Coverage |
|-----|-----|---------|
| #141414 | 20,20,20 | 38% |

### Semantic Tokens
- Background / Surface / Accent / Text

### Dark Mode: yes/no | Light Mode: yes/no

### Per Scene
scene_0: [#hex, #hex, ...]
```
