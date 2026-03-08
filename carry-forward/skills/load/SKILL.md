---
name: load
description: Load and display saved context for the current project. Use when the user wants to review what was previously saved, catch up on saved context mid-session, or asks "what was I working on?" or "where did we leave off?" or "catch me up".
allowed-tools: mcp__carry-forward__read_context
argument-hint: [optional section filter, e.g. "next steps" or "decisions" or "files"]
---

## Current time (for reference)

!`date -u +"%Y-%m-%d %H:%M UTC" 2>/dev/null || echo "(unknown)"`

---

## Section filter (if provided)

$ARGUMENTS

If `$ARGUMENTS` is non-empty (e.g. "next steps", "decisions", "files"), show only that section of the context plus the Recent Activity log. Still call `read_context` to get the full data.

---

## Instructions

Call `mcp__carry-forward__read_context` with `cwd` set to the current working directory.

### If no context exists

Tell the user:
> No saved context found for this project. Run `/carry-forward:setup` first, then use `/carry-forward:save` at the end of your next session.

### If context exists — full load (no $ARGUMENTS filter)

Present it conversationally — **not as raw markdown**. Format your response as:

---

**Picking up from your last session** *(saved DATE from frontmatter)*

**Current Task**
Restate in plain language. If the task is ambiguous or vague, say so.

**Files in play**
List with brief notes. If git is available, cross-reference with `git status` mentally — note if files were removed or renamed since the save.

**Key Decisions (still active)**
Include the WHY. If a decision seems outdated, flag it.

**Next up**
Ordered list, most urgent first. If Next Steps are vague ("finish auth"), flag it and offer to clarify.

**Open Questions** (if any recorded)

**Recent activity** (last 10 log entries, most recent first)

---

Then close with:
> Ready to continue. Want to start on [item 1 from Next Steps]?

### Sparse or stale context

If the context is missing sections, has vague Next Steps, or the `last_saved` date is old (more than a few days), say so clearly:
> "The saved context is missing [X]. Want me to help fill it in before we continue?"

---

## Supporting files

- [examples/sample-context.md](examples/sample-context.md) — example of a well-presented context summary
