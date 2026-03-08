# Claude Plugins

Two Claude Code plugins by Gowtham — install once, use forever.

| Plugin | What it does |
|--------|-------------|
| [carry-forward](#carry-forward) | Remembers your work across Claude sessions |
| [video-insight](#video-insight) | Deeply understands any video file |

---

## Prerequisites

- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) — manages dependencies automatically

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

For video-insight, you also need `ffmpeg`:
```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

## Installation

```
/plugin marketplace add gowtham012/Claude-plugins
/plugin install carry-forward@Claude-plugins
/plugin install video-insight@Claude-plugins
```

---

## carry-forward

> Never lose context between Claude Code sessions again.

Every time you start a new Claude session, it forgets everything. carry-forward fixes that — it auto-saves what you were working on after every response and auto-loads it at the start of every session.

### How it works

1. Run `/carry-forward:setup` once in your project
2. Claude adds `@carry-forward/context.md` to your `CLAUDE.md`
3. From then on — context saves automatically after every response and loads automatically when you start a new session

### Skills

| Skill | What it does |
|-------|-------------|
| `/carry-forward:setup` | One-time setup for a project |
| `/carry-forward:save` | Save a rich structured summary of the current session |
| `/carry-forward:load` | Review what was saved from your last session |
| `/carry-forward:clear` | Reset context and archive the log |

### What gets saved

```markdown
## Current Task
Implementing JWT refresh flow in useAuth.ts

## Files Being Worked On
- src/hooks/useAuth.ts — adding silent token refresh
- src/middleware/auth.py — fixing exp field parsed as string

## Key Decisions
- JWT stored in httpOnly cookie (not localStorage) — security
- React Context over Redux — simpler scope for this feature

## Next Steps
1. Add refresh_token field to auth state
2. Wire up axios interceptor for silent refresh

## Blockers
- Token refresh strategy (silent vs. re-login) undecided
```

### Requirements

- Python 3.10+
- `uvx` (installed automatically with uv)

---

## video-insight

> Give Claude eyes. Drop any video — get keyframes, OCR text, colors, motion, transcript, and production-ready code.

video-insight extracts 13 signals from any video recording and exposes 17 skills to turn that data into frontend code, design specs, test files, PRDs, user flows, and more.

### Skills

| Skill | What it does |
|-------|-------------|
| `/video-insight:analyze-video` | Full analysis — keyframes, OCR, motion, transcript, colors |
| `/video-insight:build-from-video` | Generate React or HTML from a screen recording |
| `/video-insight:extract-colors` | Pull exact color palette with semantic token assignments |
| `/video-insight:design-spec` | Figma-style design spec — tokens, components, copy, motion |
| `/video-insight:write-copy` | Extract all visible text and narration verbatim |
| `/video-insight:generate-tests` | Screen recording → Playwright or Cypress test file |
| `/video-insight:playwright-tests` | Generate TypeScript Playwright test file from recording |
| `/video-insight:export-tokens` | Export colors as Tailwind config, CSS variables, or Figma tokens |
| `/video-insight:figma-tokens` | Export Figma Variables tokens, CSS properties, and Tailwind config |
| `/video-insight:user-flow` | Reconstruct step-by-step user journey from a recording |
| `/video-insight:generate-animations` | CSS @keyframes or Framer Motion from animated scenes |
| `/video-insight:describe-3d` | Analyze 3D walkthroughs — camera path, materials, geometry |
| `/video-insight:generate-prd` | Full PRD from a product demo video |
| `/video-insight:compare-videos` | A/B diff two recordings — visual, text, flow, motion |
| `/video-insight:changelog` | User-facing changelog from before/after recordings |
| `/video-insight:storybook` | Generate Storybook stories for detected UI components |
| `/video-insight:watch` | Scan a directory and auto-analyze new video files |

### What gets extracted

- **Keyframes** — one representative frame per scene
- **OCR text** — every string visible on screen, timestamped
- **Color palette** — hex codes by dominance + semantic token assignments
- **Motion events** — which scenes have animations and what type
- **Transcript** — full speech-to-text with timestamps
- **Cursor path** — where the user clicked and moved
- **Loading states** — spinners, skeletons, progress bars detected
- **Confidence scores** — reliability rating per extracted signal

### Requirements

- Python 3.10+
- `uv` (manages all ML dependencies automatically)
- `ffmpeg` (includes `ffprobe`) — required for video metadata extraction
- Optional: GPU for faster transcription with faster-whisper

---

## License

MIT — use freely, attribution appreciated.
