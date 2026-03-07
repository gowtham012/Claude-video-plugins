---
name: write-copy
description: Extract all text content from a video — visible text via OCR and spoken narration via transcript. Returns clean organized copy ready to use verbatim. Use for marketing videos, app demos, or tutorials.
disable-model-invocation: true
allowed-tools: mcp__video-insight__write_copy
argument-hint: <video_path>
---

Extract copy from video: $ARGUMENTS

## Steps

1. Call MCP tool `mcp__video-insight__write_copy` with `video_path` = `$0`.
2. Read `visible_text` (OCR, in order of first appearance), `full_transcript` (narration), `text_per_scene` (by timestamp).
3. Output organized copy:

```markdown
## Copy: <filename>

### All Visible Text (in order of appearance)
1. "Dashboard" — scene_0 (0s)
2. "Get Started" — scene_2 (12s)

### Narration
"Welcome to the dashboard. Click analytics to see your data..."

### By Scene
**scene_0 (0s–12s)**
Visible: Dashboard, Analytics, Layers, Wallet
Narration: "Welcome to the dashboard"
```
