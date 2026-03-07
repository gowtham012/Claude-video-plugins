---
name: generate-prd
description: Generate a Product Requirements Document (PRD) from a screen recording or product demo — extracts UI structure, user flows, text content, and interaction patterns.
disable-model-invocation: true
allowed-tools: mcp__video-insight__generate_prd
argument-hint: <video_path>
---

Generate PRD from video: $ARGUMENTS

## Steps

1. Call MCP tool `mcp__video-insight__generate_prd` with `video_path` = `$0`.
2. Read all keyframe images in order.
3. Write a full PRD:

```markdown
# PRD: <product name inferred from video>

## Overview
One paragraph describing what the product does.

## Goals
- User problems solved / Key success metrics visible in UI

## User Stories
- As a [user], I want to [action] so that [outcome]

## Functional Requirements
Numbered list of features with acceptance criteria.

## UI Specifications
Per-screen: Screen name / Components / Key interactions

## Non-Functional Requirements
- Performance indicators (load states, animations)
- Accessibility signals (labels, contrast)

## Open Questions
Things that couldn't be determined from the video alone.
```
