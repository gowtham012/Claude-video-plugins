---
name: playwright-tests
description: Generate a complete TypeScript Playwright test file from a screen recording. Converts scene transitions, OCR text changes, and motion events into typed test steps with assertions.
disable-model-invocation: true
allowed-tools: mcp__video-insight__generate_tests
argument-hint: <video_path>
---

Generate Playwright tests from video: $ARGUMENTS

## Steps

1. Call MCP tool `mcp__video-insight__generate_tests` with `video_path` = `$0` and `framework` = `"playwright"`.
2. Read keyframe images for each step to identify exact selectors (button text, roles, test-ids).
3. Map each `inferred_action`:
   - `navigate` → `await page.goto()` or `expect(page).toHaveURL()`
   - `click_or_submit` → `await page.locator('text=...').click()`
   - `scroll` → `await page.evaluate(() => window.scrollBy(0, 500))`
   - `observe` → `await expect(page.locator('text=...')).toBeVisible()`
4. Use `text_appeared` for `toBeVisible()`, `text_disappeared` for `toBeHidden()`.
5. Wrap in `describe` / `test` blocks. Output a single `.spec.ts` file.
