---
name: generate-tests
description: Turn a screen recording into a Playwright or Cypress test file. Infers user actions from motion, OCR text changes, and scene diffs, then generates real test code.
disable-model-invocation: true
allowed-tools: mcp__video-insight__generate_tests
argument-hint: <video_path> [playwright|cypress]
---

Generate tests from video: $ARGUMENTS

Arguments:
- `$0` = video_path (required)
- `$1` = framework: `playwright` or `cypress` (default: `playwright`)

## Steps

1. Call MCP tool `mcp__video-insight__generate_tests` with `video_path` = `$0`, `framework` = `$1` (default `playwright`).
2. Read keyframe images for each step to identify selectors.
3. Map `inferred_action` to test commands:
   - `navigate` → `page.goto()` / `cy.visit()`
   - `click_or_submit` → `page.locator('text=...').click()` / `cy.click()`
   - `scroll` → `page.evaluate(scrollBy)` / `cy.scrollTo()`
   - `observe` → `expect().toBeVisible()` / `cy.should('be.visible')`
4. Use `text_appeared` for visibility assertions, `text_disappeared` for hidden assertions.
5. Wrap in `describe` / `test` blocks. Output a single complete test file.
