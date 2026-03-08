---
name: changelog
description: Compare two screen recordings (before and after) and write a polished user-facing changelog entry. Use for version diffs, redesign comparisons, or release notes.
disable-model-invocation: true
allowed-tools: mcp__video-insight__generate_changelog
argument-hint: <video_before> <video_after> [v1_label] [v2_label]
---

Generate changelog comparing videos: $ARGUMENTS

Arguments:
- `$0` = video_before (required)
- `$1` = video_after (required)
- `$2` = version label for before (default: `v1`)
- `$3` = version label for after (default: `v2`)

## Steps

1. Call MCP tool `mcp__video-insight__generate_changelog` with both video paths and version labels.
2. For each `scene_diff`, examine `keyframe_before` and `keyframe_after` side by side.
3. Write the changelog:

```markdown
## $3 — What's New

### Added
- New [component] with [copy from text_added]

### Changed
- [Screen name]: [what changed visually]

### Removed
- [copy from text_removed]

### Design Updates
- New color palette: [translate hex to description]
- New animations: [from motion_types_added]
```

Be specific — reference exact UI text from OCR. Keep tone user-facing, no technical jargon.
