# Context Template — Annotated

Use this as a reference when filling out the save skill. Every field has a BAD and GOOD example.

---

## last_saved
Server auto-updates this. Leave blank.

## project
The project directory name (e.g. `my-app`).

---

## Current Task

**BAD** — too vague, could mean anything:
> Working on auth

**GOOD** — specific, someone else could read this and know exactly what's happening:
> Building the JWT authentication flow — login and logout complete, token refresh is the remaining piece. Using httpOnly cookies (not localStorage) per security requirement.

---

## Files Being Worked On

Use `git diff --name-only` as ground truth. Add a note on WHY each file matters.

**BAD:**
> - auth.ts
> - login.tsx

**GOOD:**
> - `src/hooks/useAuth.ts` — main auth hook; JWT decode, state management, expiry check
> - `src/components/LoginForm.tsx` — form with Zod validation, wired to useAuth
> - `src/middleware/auth.py` — server-side token verification; fixed `exp` string bug here

---

## Key Decisions

Include the WHY and what was ruled out. Future Claude needs the reasoning.

**BAD:**
> - Using React Context

**GOOD:**
> - React Context over Redux — auth state is app-wide but simple; Redux overhead not justified for this scope
> - JWT in httpOnly cookies over localStorage — security requirement to prevent XSS token theft

---

## Patterns & Conventions Discovered

Codebase-specific things that would trip up a fresh session.

**Examples:**
> - All API errors return `{ error: string, code: string }` — never throw, always return
> - Hooks in `src/hooks/` are named `use<Domain><Action>` (e.g. `useAuthLogin`)
> - Python middleware uses decorators for auth — see `@require_auth` in `middleware/auth.py`

---

## Next Steps

Most urgent first. Step 1 must be actionable immediately — no "look into" or "figure out".

**BAD:**
> 1. Finish auth
> 2. Tests

**GOOD:**
> 1. Implement token refresh — decide between axios interceptor vs. React context effect (leaning interceptor — see open question)
> 2. Add error boundary around `/dashboard` and `/profile` routes
> 3. Write integration tests for login/logout/refresh cycle

---

## Blockers

What is genuinely stopping progress. If nothing, write "None".

**BAD:**
> - Design issues

**GOOD:**
> - Token refresh strategy undecided — silent background refresh vs. re-login on expiry; trade-offs not resolved (UX vs. complexity)

---

## Open Questions

Unresolved questions that need a decision before work can continue.

**Examples:**
> - Should token refresh be handled in axios interceptor or React context effect? Interceptor is cleaner but adds a dependency.
> - Is the `POST /auth/refresh` endpoint idempotent? Need to check with backend team before implementing retry logic.
