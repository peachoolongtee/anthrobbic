# web

Next.js (App Router, `src/`), Tailwind v4, shadcn/ui, Supabase client helpers.

## Run

From the repo root (Node 24, pnpm 12):

```bash
pnpm install
cp apps/web/.env.example apps/web/.env.local   # optional; see below
pnpm dev:web                                    # http://localhost:3000
```

The app starts and renders with no env set. Supabase code throws a clear error
only where a client is actually created without `NEXT_PUBLIC_SUPABASE_URL` and
`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`. `NEXT_PUBLIC_API_URL` defaults to
`http://localhost:8000`.

## Layout

- `src/proxy.ts`: Next 16 request interception (the successor to
  `middleware.ts`); refreshes the Supabase session, skipped when env is unset.
- `src/lib/supabase/`: `client.ts` (browser), `server.ts` (server), `proxy.ts`
  (session refresh), `env.ts` (env access).
- `src/components/ui/`: shadcn components. Add more with
  `pnpm dlx shadcn@latest add <name>` from this directory.
- `AGENTS.md`: Next.js agent notes, maintained by `next dev`.
