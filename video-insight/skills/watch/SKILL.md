---
name: watch
description: Scan a directory for video files and analyze any that haven't been processed yet. Uses hash caching — skips unchanged files. Safe to run repeatedly on the same folder.
disable-model-invocation: true
allowed-tools: mcp__video-insight__watch_directory
argument-hint: <directory> [output_base_dir]
---

Scan and analyze videos in directory: $ARGUMENTS

Arguments:
- `$0` = directory to scan (required)
- `$1` = output_base_dir (default: `./video_analysis`)

## Steps

1. Call MCP tool `mcp__video-insight__watch_directory` with `directory` = `$0`, `output_base_dir` = `$1` (default `./video_analysis`).
2. Review `results` — each entry has `status: analyzed | cached | error`.
3. For analyzed videos, summarize findings: video type, scene count, dominant colors, UI components detected.
4. List any errors separately.
