---
name: user-flow
description: Infer a step-by-step user journey from a screen recording — scene transitions, motion types, and OCR text changes reconstructed as a numbered flow with screenshots. Use for user story docs, QA test plans, or onboarding walkthroughs.
disable-model-invocation: true
allowed-tools: mcp__video-insight__user_flow
argument-hint: <video_path>
---

Generate user flow from video: $ARGUMENTS

## Steps

1. Call MCP tool `mcp__video-insight__user_flow` with `video_path` = `$0`.
2. Read keyframe image for each step.
3. Use `step.label` as the step title, `text_appeared` for new visible elements, `narration` for spoken context.
4. Generate a numbered markdown flow:

```markdown
## User Flow: <filename>

**Step 1 — Start / Landing** (0s)
[keyframe]
User sees: Dashboard, Analytics, Layers, Wallet

**Step 2 — Navigate → Products** (3.2s)
[keyframe]
User navigates. New elements: Product Catalog, $29/mo

**Step 3 — Interact: Add to Cart** (8.5s)
[keyframe]
User clicks. New element: Cart (1)
```
