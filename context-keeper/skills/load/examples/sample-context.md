# Example: What a well-loaded context looks like

When presenting context to the user, format it like this:

---

**Picking up from your last session** *(saved 2026-03-07 10:31 UTC)*

**Current Task**
Building the JWT authentication flow — login and logout are implemented; token refresh is the remaining piece.

**Files in play**
- `src/hooks/useAuth.ts` — main auth hook, JWT decode + state management
- `src/components/LoginForm.tsx` — form with validation, wired to useAuth
- `src/middleware/auth.py` — server-side token verification (has the parsing bug fix from last session)

**Key Decisions (still active)**
- React Context over Redux — simpler scope for this app's auth needs
- JWT stored in httpOnly cookies — security requirement, not localStorage

**Next up**
1. Implement token refresh — undecided between silent refresh vs. re-login flow
2. Add error boundary around auth routes

**Open Question**
Token refresh strategy: silent background refresh keeps UX smooth but adds complexity. Re-login on expiry is simpler. Decision pending.

**Recent activity**
- Fixed JWT parsing bug in middleware (`exp` field was being read as string not int)
- Implemented `useAuth` hook with login/logout state
- Wired `LoginForm` to the hook

---

Ready to continue. Want to tackle the token refresh strategy first?
