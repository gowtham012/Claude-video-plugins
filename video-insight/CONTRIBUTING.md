# Contributing

Thank you for your interest in contributing to video-insight!

## Development setup

```bash
git clone https://github.com/gowtham012/Claude-plugins
cd Claude-plugins/video-insight
pip install -e ".[dev]"
brew install ffmpeg   # macOS; or: sudo apt-get install ffmpeg
```

## Running tests

```bash
make test
```

Tests are fully mocked — no video files, GPU, or API keys required.

## Project structure

```
src/
  video_analyzer.py   # Core extraction pipeline (13 functions)
  server.py           # FastMCP server — 17 MCP tools
  action_builder.py   # Optional: multimodal message builder for direct Claude API use
tests/
  test_video_analyzer.py   # Unit tests for extraction functions
  test_action_builder.py   # Unit tests for message building
skills/
  analyze-video/SKILL.md      /analyze-video
  build-from-video/SKILL.md   /build-from-video
  extract-colors/SKILL.md     /extract-colors
  design-spec/SKILL.md        /design-spec
  write-copy/SKILL.md         /write-copy
  describe-3d/SKILL.md        /describe-3d
  generate-tests/SKILL.md     /generate-tests
  export-tokens/SKILL.md      /export-tokens
  user-flow/SKILL.md          /user-flow
  generate-animations/SKILL.md  /generate-animations
  watch/SKILL.md              /watch
  generate-prd/SKILL.md       /generate-prd
  compare-videos/SKILL.md     /compare-videos
  storybook/SKILL.md          /storybook
  playwright-tests/SKILL.md   /playwright-tests
  figma-tokens/SKILL.md       /figma-tokens
  changelog/SKILL.md          /changelog
examples/
  sample_output/
    manifest.json    # Full example manifest
.claude-plugin/
  plugin.json        # Claude Code plugin manifest
```

## Architecture

The plugin follows a strict separation of concerns:

1. **Extraction** (`video_analyzer.py`) — Pure CPU/IO work. No AI calls. Takes a video file, returns a structured dict.
2. **MCP tools** (`server.py`) — Thin wrappers that call extraction functions and return structured context. Claude Code reads the context and does all reasoning/generation.
3. **Skills** (`skills/*/SKILL.md`) — Prompts that tell Claude how to interpret the tool output and what to generate.

**No nested Anthropic API calls.** Claude Code itself is the AI. Tools only extract and return data.

## Adding a new MCP tool

1. Add extraction logic to `video_analyzer.py` if it needs new signals.
2. Add a `@mcp.tool()` function to `server.py`:
   - Return structured context (paths, dicts, task descriptions)
   - Include an `instructions` key explaining what Claude should do with the data
3. Add a skill in `skills/<tool-name>/SKILL.md` with the slash command, steps, and examples.
4. Add tests for any new extraction functions in `tests/test_video_analyzer.py`.
5. Update the tool count in the `server.py` docstring and README.

## Adding a new extraction signal

1. Write the function in `video_analyzer.py`:
   - Accept `frame_path: str` (for per-frame signals) or `(video_path, start, end)` (for temporal signals)
   - Return a dict with typed values
   - Wrap the body in `try/except Exception: return <safe_default>`
2. Call it in `_enrich_scene()` — it runs in parallel with other per-scene enrichment.
3. Add the result key to the scene dict returned by `_enrich_scene`.
4. Update `build_manifest` summary if relevant (e.g. `loading_scenes`, `cursor_active_scenes`).

## Code style

- Type hints on all public functions
- Docstrings on all public functions
- Graceful fallbacks when optional deps are missing (EasyOCR, faster-whisper, PySceneDetect all have `try/except ImportError`)
- No global state except `_MANIFEST_CACHE` (in-process cache)
- All extraction functions must be safe to call with a nonexistent path (return empty default, not raise)

## Submitting a PR

1. Fork and create a branch: `git checkout -b feature/my-feature`
2. Make changes and add tests
3. `make lint && make test` — both must pass cleanly
4. Open a PR with:
   - What signal/tool/skill was added or changed
   - Why it's useful
   - How it was tested

## Reporting issues

Open an issue at https://github.com/gowtham012/Claude-plugins/issues

Please include:
- OS and Python version
- ffmpeg version (`ffmpeg -version`)
- The error message or unexpected output
- Video type (screen recording, 3D, marketing — duration, resolution if known)
