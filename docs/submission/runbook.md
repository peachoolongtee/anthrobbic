# Runbook: run the demo offline on this laptop

Everything below uses commands that exist in the repo. The scripts were read in `package.json` and `apps/api/pyproject.toml`. Two checks are marked as not yet done.

## What you need

- Node 24 and pnpm (`.nvmrc` says 24; the root `package.json` pins pnpm).
- `uv` for the Python API (Python 3.13).
- The flight file. The API reads `FLIGHTS_CSV` from the process environment. If it is unset, it uses a path fixed in `apps/api/app/negotiation/dot.py`: `/Users/ianpong/Hackathons/anthrobbic/data/flight-delays/flights.csv`. On this laptop that file exists, so no setting is needed. On another machine, set `FLIGHTS_CSV` before starting the API.
- The API builds a small SQLite cache beside that file the first time it reads it (a `.cache` folder, git-ignored). Run the API once with wifi on, or at least once before the talk, so the cache exists.

## Environment variables

Nothing loads a `.env` from the repo root. The root `.env.example` lists every variable. The kinds below are from the example files. No values are shown here.

| Variable | File it goes in | Kind | Needed for the offline demo |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | `apps/web/.env.local` | A URL for the API | No. Defaults to `http://localhost:8000`. |
| `NEXT_PUBLIC_SUPABASE_URL` | `apps/web/.env.local` | A URL for a Supabase project | No. The demo does not use Supabase. |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | `apps/web/.env.local` | A public key, safe in the browser | No. |
| `SUPABASE_URL` | `apps/api/.env` | A URL for a Supabase project | No. |
| `SUPABASE_SECRET_KEY` | `apps/api/.env` | A server-only secret key | No. Never put it in the web app. |
| `CORS_ORIGINS` | `apps/api/.env` | A comma-separated list of browser origins | Only if the web app is not on `http://localhost:3000`. That is the default. |
| `ALLOW_LIVE` | `apps/api/.env` | A switch. Only `1` allows live model runs | No. Leave it unset. Live runs spend money. |
| `FLIGHTS_CSV` | The process environment only | A file path | Only off this laptop. |

Live mode also needs a model credential in the environment. Do not set one for the stage demo. The demo needs no key.

## Start

Use two terminal tabs, both at the repo root. The API comes first.

1. API (port 8000):

   ```bash
   pnpm dev:api
   ```

   This runs `uv --directory apps/api run uvicorn app.main:app --reload --port 8000`. On the first run `uv` installs dependencies, so do that with wifi on, once.

2. Check it:

   ```bash
   curl -s localhost:8000/health
   ```

   You should see `{"status":"ok"}`.

3. Web (port 3000):

   ```bash
   pnpm dev:web
   ```

   Open `http://localhost:3000`.

The web app talks to the API at `http://localhost:8000` unless `NEXT_PUBLIC_API_URL` says otherwise. The web build can also run on invented data with `NEXT_PUBLIC_API_MODE=mock`. The page then shows a "Mock" badge and says every figure is invented. Never use mock mode on stage.

## Load the flight list once

The flight list is built on the first request after the API starts. The team measured about 4 seconds for that first load. In a quick check for this file with a warm cache, a request took well under a second, so the 4 seconds is not reproduced here. Either way, load it before the talk:

```bash
curl -s "localhost:8000/scenarios?limit=50" -o /dev/null
```

Then open the page. The list shows "Delayed flights". The list stays in memory until the API restarts.

## Restart between rehearsals

Runs live in the API's memory and vanish on restart. Each run's evidence log is also a file under `apps/api/run_logs/` (git-ignored). Restarting clears the in-memory runs. Each click on a flight makes a new run, so a flight you approved or rejected earlier can be planned again.

1. Stop the API (Ctrl+C in its tab).
2. Start it again with `pnpm dev:api`.
3. Reload the browser page. Reload the list once with the `curl` line above.
4. In the browser, click the flight again. Click **Reset** in the bottom bar if any runway or gate is still marked closed.

To clear old log files too, delete `apps/api/run_logs/`. It is safe: the folder is git-ignored and is rebuilt on the next run.

The web app does not need a restart between rehearsals. Reload the page.

## Offline notes

- The web app loads the Geist fonts from Google through `next/font/google`. The team's work log says the production build fails offline for this reason. Not checked here: whether `pnpm dev:web` shows the fonts offline. Run it once with wifi on, and check the page with wifi off before the talk.
- `pnpm build` and `pnpm install` need the network. Do them before the venue.
- Not yet done: a full run of the demo with wifi off.

## Check the data and the tests

```bash
uv --directory apps/api run pytest
pnpm typecheck
pnpm lint
```

Write the test output to a file and read the exit code before relying on it. A pipe through `grep` or `head` hides a failure.

## What to expect today

- **Model off** works with no key. A flight list loads, a run builds, sign-off and the log work.
- **Recorded** replays saved model answers. The six saved answers in `apps/api/recordings/` do not match the current prompts. In a check for this file, recorded mode on a flight returned the rule-based fallback with "No recording" faults. The flight list marks a row "Recorded" only when saved answers replay cleanly, and no row showed that mark. Until the answers are saved again, the negotiation in the demo is `[LIVE RESULT]`.
- **Live** is refused unless `ALLOW_LIVE=1` and a credential is set. Do not use it on stage.

## If something fails on stage

Say what happened in one sentence. Do not hide it. Then:

| What you see | What to do |
|---|---|
| "Cannot reach the planning service" | The API stopped. In its tab, run `pnpm dev:api` again. Click **Retry** on the page. The current run is lost. Click the flight again. |
| The flight list is empty or says the flight data is not available | The API cannot find the flight file. Check that the path above exists, or set `FLIGHTS_CSV`, then restart the API. |
| Recorded mode shows "No recording" and "rules only, not agents" | Expected until the answers are saved again. Use the model-off wording in `demo-script.md`. Do not claim the agents negotiated. |
| A page of red text or a blank page | Reload the browser. If it persists, restart `pnpm dev:web`. |
| Sign-off says "Unknown run" | The API restarted. Click the flight again. |
| The log says it no longer checks out | Make a new plan by clicking the flight again. Say so. This is the system working as designed. |
| The talk is running long | Skip Beat 3's log tamper, then Beat 5's second half. Keep Beat 4. The failure is the point. |
| Nothing works | Show the evidence file `apps/api/eval_results/latest_off_none.md` in a text editor and talk through `judge-card.md`. |

Do not start live model runs to recover. They spend money and are not part of the demo.
