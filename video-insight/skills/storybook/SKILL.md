---
name: storybook
description: Generate Storybook .stories.jsx files for every UI component detected in a screen recording. Uses keyframes and burst frames as visual evidence for Default, Loading, and Interactive story variants.
disable-model-invocation: true
allowed-tools: mcp__video-understanding__generate_storybook
argument-hint: <video_path>
---

Generate Storybook stories from video: $ARGUMENTS

## Steps

1. Call MCP tool `mcp__video-understanding__generate_storybook` with `video_path` = `$0`.
2. For each component in `component_evidence`:
   - Read all `keyframe_path` and `burst_frame_paths` images
   - Identify visual appearance, color, size, and behavior
3. Write a `ComponentName.stories.jsx` file with:
   - `Default` — resting state, exact colors from `color_palette`
   - `Loading` — if `loading.has_spinner` or `loading.has_skeleton`
   - `Interactive` — hover/focus/active state using burst frames for animation reference
4. Use `color_tokens` for all colors (never hardcoded hex). Use `ocr_text` verbatim for labels and CTAs.

```jsx
import ComponentName from './ComponentName';

export default {
  title: 'Components/ComponentName',
  component: ComponentName,
};

export const Default = { args: { /* from OCR text + color_tokens */ } };
export const Loading = { args: { isLoading: true } };
export const Interactive = { args: { onClick: () => {} } };
```
