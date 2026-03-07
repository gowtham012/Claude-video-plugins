---
name: export-tokens
description: Extract a video's color palette and export as Tailwind config, CSS custom properties, Figma tokens, or all three formats at once.
disable-model-invocation: true
allowed-tools: mcp__video-insight__export_tokens
argument-hint: <video_path> [tailwind|css|figma|all]
---

Export design tokens from video: $ARGUMENTS

Arguments:
- `$0` = video_path (required)
- `$1` = format: `tailwind`, `css`, `figma`, or `all` (default: `all`)

## Steps

1. Call MCP tool `mcp__video-insight__export_tokens` with `video_path` = `$0`, `format` = `$1` (default `all`).
2. Report what was generated:

| Format | File | Contents |
|--------|------|----------|
| `tailwind` | `tailwind.config.js` | `theme.extend.colors` block |
| `css` | `tokens.css` | `:root { --color-* }` variables |
| `figma` | `figma-tokens.json` | Figma Tokens plugin JSON |

3. Show a color swatch summary (hex + semantic role) and tell the user where each file was saved.
