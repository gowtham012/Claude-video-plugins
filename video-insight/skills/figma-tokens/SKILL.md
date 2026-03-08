---
name: figma-tokens
description: Export a video's color palette as Figma Variables-compatible tokens, CSS custom properties, and Tailwind config — all three formats from one screen recording.
disable-model-invocation: true
allowed-tools: mcp__video-insight__export_tokens
argument-hint: <video_path>
---

Export Figma tokens from video: $ARGUMENTS

## Steps

1. Call MCP tool `mcp__video-insight__export_tokens` with `video_path` = `$0` and `format` = `"all"`.
2. Report what was generated: `figma_tokens` (JSON), `css_variables`, `tailwind_config`.
3. Show a color swatch summary (hex + role: background / surface / accent / text).
4. Tell the user where each file was saved.

## Token roles (auto-inferred)

| Token | How inferred |
|-------|-------------|
| `background` | Darkest dominant color |
| `surface` | Second darkest |
| `accent` | Most saturated |
| `text` | Lightest dominant |
| `brand-1..8` | Remaining colors by screen proportion |
