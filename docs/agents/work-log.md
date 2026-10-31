# Agent work log

The running record of delegated work, so a new session can resume it. Newest round first. Tasks and bugs live on the issue tracker, so this log holds only who did what and what was proven.

An entry is **completed** only when its acceptance criteria are met and the lead has checked the result. Other statuses are **not started**, **in progress** and **blocked**. Record results from real command output, and leave out passwords, keys, tokens and connection strings.

## Round 1: workspace scaffold (2026-10-31)

| # | Agent and model | Scope | Branch | Acceptance criteria | Status |
|---|---|---|---|---|---|
| 1.1 | `frontend-engineer`, `sonnet` | Root workspace files, `apps/web` | Agent worktree | Install, typecheck, lint and build pass; a shadcn component renders; the app starts with no env set | **Completed** |
| 1.2 | `implementer`, `sonnet` | `apps/api`, `supabase/` | Agent worktree | Tests and lint pass; `GET /health` answers on a real server; the app starts with no env set | **Completed** |

### Integration check by the lead: completed

Both branches merged cleanly in a throwaway worktree, since removed.

- **Files changed by the lead:** root `.gitignore` gains `node_modules/`, which pnpm's root install needs.
- **Verified, all exit 0 with no env set:** `pnpm install --frozen-lockfile`, `pnpm typecheck`, `pnpm lint`, `pnpm build`, `uv sync --frozen`, `pytest` (7 passed, 1 warning), and `ruff` on the API branch.
- **Verified on real servers:** `pnpm dev:api` answers `/health` with 200 and `{"status":"ok"}`. A preflight from `http://localhost:3000` is allowed; one from another origin gets 400. `next start` serves `/` with 200 and the shadcn button, with no env set and with fake Supabase env. All test ports were free afterwards.
- **Not verified:** real session refresh, sign-in, or any call to Supabase. With fake env, the requests carried no valid session, so they show only that the proxy doesn't crash. The local stack (`supabase/config.toml`) has never run, because Docker and the Supabase CLI aren't installed.
- **Remaining:** `site_url` in `supabase/config.toml` uses `127.0.0.1:3000` while the web app and CORS default to `localhost:3000`, and auth cookies won't carry between the two. Pytest warns that `httpx` is deprecated for Starlette's test client. The build fetches the Geist font from Google, so it fails offline.

## Round template

```markdown
## Round N: <parent task> (YYYY-MM-DD)

| # | Agent and model | Scope | Branch | Acceptance criteria | Status |
|---|---|---|---|---|---|

### N.1 <role>: <status>

- **Files changed:**
- **Verified by the lead:** what was checked, with the command and its result
- **Not verified:**
- **Findings and remaining work:**
```
