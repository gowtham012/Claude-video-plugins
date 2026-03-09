<p align="center">
  <img src="assets/pitlane-logo.png" alt="Pitlane" width="400" />
</p>

<h1 align="center">Pitlane Plugins for Claude Code</h1>

<p align="center">
  <strong>Three open-source plugins that give Claude Code superpowers — persistent memory, deep video understanding, and disciplined engineering.</strong>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#-carry-forward">carry-forward</a> &bull;
  <a href="#-video-insight">video-insight</a> &bull;
  <a href="#-deep-engineer">deep-engineer</a> &bull;
  <a href="#contributing">Contributing</a> &bull;
  <a href="#license">License</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT License" />
  <img src="https://img.shields.io/badge/claude_code-plugin-blueviolet?style=flat-square" alt="Claude Code Plugin" />
</p>

---

## Quick Start

### Prerequisites

- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** — manages all dependencies automatically

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

For **video-insight**, you also need **ffmpeg**:

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows (chocolatey)
choco install ffmpeg
```

### Install

Inside Claude Code, run:

```
/plugin marketplace add gowtham012/Claude-plugins
/plugin install carry-forward@Claude-plugins
/plugin install video-insight@Claude-plugins
/plugin install deep-engineer@Claude-plugins
```

That's it. All three plugins are ready to use.

---

<br/>

## <img src="https://img.shields.io/badge/plugin-carry--forward-orange?style=for-the-badge" alt="carry-forward" />

### Never lose context between Claude Code sessions again.

Every time you start a new Claude Code session, it forgets everything — what you were building, decisions you made, files you touched, what comes next. **carry-forward** fixes that permanently.

It auto-saves a structured summary of your work after every Claude response and auto-loads it when you start a new session. Zero friction, zero commands after the one-time setup.

### How it works

```
Session 1                     Disk                      Session 2
───────────────────           ───────────────────        ───────────────────
/carry-forward:setup  -->     CLAUDE.md gets             Open Claude Code
                              @carry-forward/            Claude reads context.md
... work normally ...         context.md                 automatically at startup

Stop hook fires       -->     log.jsonl grows            Claude already knows:
after every response          (auto, silent)             - Current task
                                                         - Files in play
/carry-forward:save   -->     context.md updated         - Decisions made
                              (rich summary)             - Next steps

Close Claude Code                                        Just say "continue"
```

### One-time setup

```
/carry-forward:setup
```

This creates a `carry-forward/` directory in your project, wires up `CLAUDE.md` with an `@import`, and you're done. Restart Claude Code once — from then on, context loads automatically at every session start.

### What gets saved

```markdown
---
last_saved: 2026-03-07T10:30:00Z
project: my-app
---

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

### Skills

| Skill | What it does |
|:------|:-------------|
| `/carry-forward:setup` | One-time setup — creates directory, wires CLAUDE.md `@import` |
| `/carry-forward:save` | Save a rich structured summary of the current session |
| `/carry-forward:load` | Review what was saved from your last session |
| `/carry-forward:clear` | Reset context and archive the log |

### Storage

```
your-project/
├── CLAUDE.md                           <-- @carry-forward/context.md added here
└── carry-forward/
    ├── context.md                      <-- auto-loaded every session start
    ├── log.jsonl                       <-- auto-appended after every response
    └── log.2026-03-07T10-30.jsonl.bak  <-- created by /clear
```

### Requirements

- Python 3.10+
- `uvx` (installed automatically with `uv`)

---

<br/>

## <img src="https://img.shields.io/badge/plugin-video--insight-blue?style=for-the-badge" alt="video-insight" />

### Give Claude eyes. Drop any video — get structured data and production-ready code.

**video-insight** deeply understands video recordings. Point it at any screen recording, product demo, 3D walkthrough, or marketing video and it extracts **13 structured signals** — then use **17 skills** to turn that data into frontend code, design specs, tests, PRDs, user flows, changelogs, Storybook stories, and more.

No API keys needed. No cloud uploads. Everything runs locally.

### What gets extracted

| Signal | Description |
|:-------|:------------|
| **Keyframes** | One representative frame per scene, extracted via scene detection |
| **OCR text** | Every string visible on screen, timestamped and organized by scene |
| **Color palette** | Hex codes ranked by dominance + semantic token assignments (background/surface/accent/text) |
| **Motion events** | Per-scene animation classification (scroll, fade, slide, cut, none) |
| **Transcript** | Full speech-to-text with timestamps via faster-whisper |
| **Cursor path** | Click positions and movement tracking across scenes |
| **Scroll indicators** | Scroll events detected per scene |
| **Loading states** | Spinners, skeleton loaders, and progress bars detected |
| **Burst frames** | High-FPS capture of fast animations for precise reproduction |
| **Scene diffs** | Pixel-level visual change detection between consecutive keyframes |
| **Font hints** | Font size, weight, and role estimation from text bounding boxes |
| **Confidence scores** | Reliability rating per extracted signal |
| **Video hash** | SHA-256 deduplication — skips re-analysis of unchanged files |

### Skills

#### Analysis

| Skill | What it does |
|:------|:-------------|
| `/video-insight:analyze-video` | Full pipeline — extracts all 13 signals, produces structured markdown report |
| `/video-insight:extract-colors` | K-means color clustering across keyframes with semantic token assignments |
| `/video-insight:write-copy` | All visible text via OCR + full narration transcript, organized by scene |
| `/video-insight:user-flow` | Step-by-step user journey from scene transitions, motion, and text changes |
| `/video-insight:describe-3d` | Tuned for 3D walkthroughs — camera movement classification per scene |
| `/video-insight:compare-videos` | Structural A/B diff — visual, text, flow, motion, similarity score |

#### Code generation

| Skill | What it does |
|:------|:-------------|
| `/video-insight:build-from-video` | Pixel-perfect React or HTML from a screen recording |
| `/video-insight:generate-tests` | Infers user actions, generates Playwright or Cypress test file |
| `/video-insight:playwright-tests` | TypeScript Playwright tests with typed selectors and assertions |
| `/video-insight:generate-animations` | CSS `@keyframes` or Framer Motion from animated scenes |
| `/video-insight:storybook` | Storybook `.stories.jsx` for every detected UI component |

#### Design & documentation

| Skill | What it does |
|:------|:-------------|
| `/video-insight:design-spec` | Figma-style spec — color tokens, component inventory, copy, motion, spacing |
| `/video-insight:export-tokens` | Colors as Tailwind config, CSS custom properties, or Figma tokens |
| `/video-insight:figma-tokens` | All three formats (Figma Variables, CSS, Tailwind) from one recording |
| `/video-insight:generate-prd` | Full PRD — overview, user stories, functional requirements, UI specs |
| `/video-insight:changelog` | User-facing changelog from before/after recordings |

#### Automation

| Skill | What it does |
|:------|:-------------|
| `/video-insight:watch` | Scan a directory, auto-analyze new videos, skip unchanged files via hash cache |

### Requirements

- Python 3.10+
- `uv` — manages all ML dependencies automatically on first run
- `ffmpeg` (includes `ffprobe`) — required for video metadata extraction
- Optional: GPU with CUDA support for faster transcription

---

<br/>

## <img src="https://img.shields.io/badge/plugin-deep--engineer-red?style=for-the-badge" alt="deep-engineer" />

### Stop Claude from hardcoding. Force a real engineering loop.

Claude Code's biggest pain points: it hardcodes solutions for your specific example instead of solving generally, skips edge cases you didn't mention, and writes code before thinking. **deep-engineer** fixes all three with mechanical enforcement — not just instructions, but hooks and tools that physically prevent shortcuts.

### How it works

```
User says "fix X"
    │
    ▼
Phase 1: GENERALIZE ──────── Restate as general problem, list 5+ scenarios
    │                         save_task REJECTS fewer than 5 scenarios
    │                         PreToolUse hook BLOCKS Write/Edit
    ▼
Phase 2: HYPOTHETICAL TEST ── Walk through approach mentally against ALL scenarios
    │                         Document pass/fail table, revise until all pass
    │                         PreToolUse hook BLOCKS Write/Edit
    ▼
Phase 3: TDD ─────────────── Write tests covering ALL scenarios
    │                         PreToolUse hook ALLOWS test files only
    │                         BLOCKS implementation files
    ▼
Phase 4: IMPLEMENT ────────── Write code to pass all tests
    │                         Anti-hardcoding checklist enforced
    │                         All Write/Edit allowed
    ▼
Phase 5: VERIFY ──────────── Run tests, fix failures, loop until green
    │                         complete_task REJECTS unless all phases done
    ▼
Done ── Task archived to history/
```

### What makes it different

This isn't prompt engineering. The plugin uses **three enforcement layers**:

| Layer | Mechanism | What it does |
|:------|:----------|:-------------|
| **PreToolUse hook** | Intercepts Write/Edit before execution | Physically blocks code files during Phases 1-2. During Phase 3, only allows test files. |
| **MCP tool validation** | Server-side rejection | `save_task` rejects <5 scenarios. `update_phase` rejects skipping/backwards. `complete_task` rejects until verify phase. |
| **Stop hook** | Injects `additionalContext` JSON | Claude sees phase reminders and violation warnings in every turn. |

### One-time setup

```
/deep-engineer:setup
```

### Usage

```
/deep-engineer:solve Fix the date parser to handle ISO 8601 dates
```

Claude will:
1. Restate as "parse date strings in multiple formats" (not just ISO 8601)
2. List 5+ scenarios (with timezone, empty string, invalid format, unix timestamp, etc.)
3. Walk through approach mentally against all scenarios
4. Write tests covering all scenarios — implementation files are **blocked** by hooks
5. Write implementation — no hardcoded values
6. Run tests and loop until all pass

### Skills

| Skill | What it does |
|:------|:-------------|
| `/deep-engineer:setup` | One-time setup — creates directory, wires CLAUDE.md `@import` |
| `/deep-engineer:solve` | Main engineering loop — all 5 phases with enforcement |
| `/deep-engineer:status` | Current phase, scenarios, warnings, test runner info |

### Test runner auto-detection

Supports 20+ frameworks out of the box:

| Language | Frameworks |
|:---------|:-----------|
| Python | pytest, unittest |
| JavaScript/TypeScript | vitest, jest, mocha |
| Go | go test |
| Rust | cargo test |
| Ruby | rspec, rake |
| Java | maven, gradle |
| PHP | phpunit |
| Elixir | mix test |

### Storage

```
your-project/
├── CLAUDE.md                         <-- @deep-engineer/current-task.md added here
└── deep-engineer/
    ├── current-task.md               <-- active task (auto-loaded every session)
    ├── log.jsonl                     <-- phase transitions + violation log
    └── history/
        └── task-2026-03-09T....md    <-- archived completed tasks
```

### Requirements

- Python 3.10+
- `uvx` (installed automatically with `uv`)

---

<br/>

## Contributing

We welcome contributions! See [CONTRIBUTING.md](video-insight/CONTRIBUTING.md) for development setup and guidelines.

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make changes and add tests
4. Open a PR

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before contributing.

## Security

To report a vulnerability, see [SECURITY.md](SECURITY.md). **Do not open a public issue for security bugs.**

## License

MIT - see [LICENSE](LICENSE) for details.

Use freely, attribution appreciated.

---

<p align="center">
  Built by <a href="https://github.com/gowtham012">Gowtham</a> &bull;
  <a href="https://x.com/SolletiKumar">Follow on X</a>
</p>
