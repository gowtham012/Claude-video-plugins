---
name: save
description: Save the current session context to carry-forward/context.md. Run at the end of a work session to persist what was accomplished, decisions made, files touched, and next steps.
disable-model-invocation: true
allowed-tools: mcp__carry-forward__read_context, mcp__carry-forward__write_context, mcp__carry-forward__append_log, Bash(git log *), Bash(git diff *), Bash(git status *)
argument-hint: [optional focus, e.g. "auth refactor" or "api layer"]
---

## Live project snapshot (auto-injected before you start)

**Current branch & recent commits:**
```
!`git log --oneline -10 2>/dev/null || echo "(no git history)"`
```

**Files changed since last 5 commits:**
```
!`git diff --name-only HEAD~5 2>/dev/null || echo "(none)"`
```

**Uncommitted changes:**
```
!`git status --short 2>/dev/null || echo "(no git repo)"`
```

---

## Focus area (if provided)

$ARGUMENTS

If `$ARGUMENTS` is non-empty, bias the summary toward that area. Still capture everything else, but lead with it.

---

## Step 1 — Read existing context

Call `mcp__carry-forward__read_context` with `cwd` = current working directory.
Use it as a baseline — carry forward decisions and open questions that are still active. Update stale entries. Don't delete history, refine it.

---

## Step 2 — Write the updated context

Use the git snapshot above plus the conversation history to fill in the template. The git diff is your ground truth for which files were actually touched — don't guess.

**Quality rules (strictly enforced):**

| Bad (vague, useless) | Good (specific, actionable) |
|---|---|
| "worked on auth" | "Built JWT login/logout in `src/hooks/useAuth.ts`; token is stored in httpOnly cookie" |
| "fixed a bug" | "Fixed `exp` field parsed as string not int in `src/middleware/auth.py:L42`" |
| "next: finish auth" | "Next: implement silent token refresh — undecided between `axios` interceptor vs. React context effect" |
| "blocked on design" | "Blocked: token refresh strategy (silent vs. re-login) — trade-offs not resolved" |

**Template:**

```markdown
---
last_saved: (leave blank — server updates this)
project: <project directory name>
---

## Current Task
<1–3 sentences: what is actively being built, fixed, or investigated.
Be specific: name the feature, the bug, the refactor. Not "working on auth" — "implementing JWT refresh flow in useAuth.ts">

## Files Being Worked On
<Use the git diff above as ground truth. Add a note on WHY each file matters.>
- `path/to/file.ext` — what changed and why it matters

## Key Decisions
<Include the WHY and what was ruled out. Future Claude needs the reasoning, not just the choice.>
- Decision made — why this over the alternative

## Patterns & Conventions Discovered
<Codebase-specific things worth remembering: naming conventions, surprising behaviour, non-obvious architecture.>
- Pattern — where it applies

## Next Steps
<Most urgent first. Specific enough that step 1 can be acted on immediately without re-reading code.>
1. Concrete next action (e.g. "Add `refresh_token` field to auth state in `useAuth.ts`")
2. Follow-up

## Blockers
<What is genuinely blocking progress. If none, write "None".>
- Specific blocker, or "None"

## Open Questions
<Unresolved questions that need a decision before work can proceed.>
- Question / uncertainty
```

---

## Step 3 — Call the MCP tools

Call `mcp__carry-forward__write_context`:
- `cwd` = current working directory
- `content` = filled-out template above

Then call `mcp__carry-forward__append_log`:
- `cwd` = current working directory
- `entry` = one sentence: the single most significant thing accomplished this session

---

## Step 4 — Confirm

Reply:
> "Context saved. Here's what was recorded:"

Show **Current Task** and **Next Steps** so the user can verify accuracy. If anything looks wrong, offer to correct it before finishing.

---

## Supporting files

- [templates/context-template.md](templates/context-template.md) — annotated template with field descriptions
