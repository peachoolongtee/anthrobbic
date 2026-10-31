# Runbook: run the demo offline on this laptop

Everything below uses commands that exist in the repo. The scripts were read in `package.json` and `apps/api/pyproject.toml`. The dashboard steps were read from the code of `origin/feat/frontend`, not run, and are marked `[CHECK ON SCREEN]`. Two checks are marked as not yet done.

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
| `ALLOW_LIVE` | The process environment, for the live moment | A switch. Only `1` allows live model runs | Only for the Live demo (see "Start for the Live demo"). Live runs spend money. |
| `FLIGHTS_CSV` | The process environment only | A file path | Only off this laptop. |

Live mode also needs a model credential in the process environment. The wifi-off Recorded backup works with no key.

## Start for the Live demo (the plan)

The demo runs on Live. Use two terminal tabs, both at the repo root.

1. API, with the key in the process environment and `ALLOW_LIVE=1`, from `apps/api/.env`. This command never prints the value:

   ```bash
   set -a; . apps/api/.env; set +a; ALLOW_LIVE=1 uv --directory apps/api run uvicorn app.main:app --port 8000
   ```

   The coordinator's test used this form. Relying on `.env` alone was not tested.

2. Web, built so the flights page starts in Live:

   ```bash
   NEXT_PUBLIC_DEFAULT_RUN_MODE=live pnpm --filter web build
   pnpm --filter web start
   ```

   With this setting the flights page runs only a flight someone picks, so loading it spends nothing. Unset, the page opens as it does in the backup below.

3. Check the network before going on. Any HTTP status means it is reachable; no status means it is not:

   ```bash
   curl -sS -o /dev/null -w "%{http_code}\n" https://api.anthropic.com
   ```

4. Warm it without spending. Open `http://localhost:3000/dashboard/flights` once and wait for the map and the list. Do not pick a flight. Then open `http://localhost:3000` in the tab you will present from, skip the intro and stay there.

**What it costs.** One run-through makes up to 6 model calls, about $0.15, because only beat 1 is Live. Every other flight, runway, gate, preset, **Inject**, **Reset every change** or **Make a new recovery plan** while the mode is Live can use up to 6 more.

**Recovery.** If a Live run has not returned after 40 seconds or shows faults, click **Recorded**. It answers at once from the saved run, and the script has the wording. With no network, use the backup below.

**Before handing the laptop over,** click **Recorded**. Judges trying flights in Live spend up to 6 calls per run. Reloading the page returns it to Live, though it runs nothing until a flight is picked. To be sure, restart the API without `ALLOW_LIVE`, so Live is refused and spends nothing.

## Backup: the wifi-off Recorded demo

Needs no key and no network. Build the web app without `NEXT_PUBLIC_DEFAULT_RUN_MODE`, then follow these steps. Use flights marked "Recorded" and the script's recorded wording in beat 2.


The new dashboard has two pages: the overview at `/` and the flights page at `/dashboard/flights`. The overview, when it opens, asks the API for 50 flights and makes one recorded run of each flight with saved answers (19 today). Those replay, so they make no model calls, whatever the mode, and the **Arrivals** table takes a few seconds to fill on the first load (about 8 when measured). The flights page asks for 200. Both need the API to be up, and the first list call after an API restart takes several seconds (7.8 seconds when measured). So the order matters. Use two terminal tabs, both at the repo root.

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

3. Load the flight list once (next section), for the 50-flight overview and the 200-flight flights page.

4. Web (port 3000), from a production build, not `pnpm dev:web`, which compiles each page on first use and leaves the map blank for several seconds:

   ```bash
   pnpm --filter web build
   pnpm --filter web start
   ```

5. Open `http://localhost:3000` in the tab you will present from. Skip the intro (see below). Wait until the **Outcomes** panel on the overview shows its ring and counts.
6. Do the wifi-off check (see below), then turn wifi back on or leave it off, as you plan to present.
7. Click one flight and wait for the map, so the flights page and its map have loaded once. Then return to the overview and stay there.

The web app talks to the API at `http://localhost:8000` unless `NEXT_PUBLIC_API_URL` says otherwise. The web build can also run on invented data with `NEXT_PUBLIC_API_MODE=mock`. The page, named Magic Airbus in the top bar, then shows a "Mock sample data" tag in the top bar and says run outcomes are invented. Never use mock mode on stage.

## Skip the intro

A plane crossing the screen plays when the home page opens. It plays once per browser tab, and any click or key skips it. Open the home page in the tab you will present from, click once to skip it, and keep that tab. A new tab or a reloaded session plays it again, which costs about 3 seconds. `[CHECK ON SCREEN]`

## Load the flight list once

The flight list is built on the first request after the API starts. The team measured about 4 seconds for that first load. In a quick check for the earlier runbook with a warm cache, a request took well under a second, so the 4 seconds is not reproduced here. Either way, load it before the talk, for both page sizes:

```bash
curl -s "localhost:8000/scenarios?limit=12" -o /dev/null
curl -s "localhost:8000/scenarios?limit=50" -o /dev/null
```

Then open the page. The list stays in memory until the API restarts, so repeat these after every restart.

## Restart the API after recordings

Saved model answers are in `apps/api/recordings/`. The six that exist do not match the current prompts, and the negotiation for WN4832, DCA to MDW, needs a re-recording `[RE-RECORD PENDING]`. After any new recording is saved:

1. Stop the API (Ctrl+C in its tab) and start it again with `pnpm dev:api`. We have not checked whether the API reads the folder afresh on each run, so restart to be sure. Restart also clears runs held in memory.
2. Run the two `curl` lines above.
3. Reload the browser tab, not a new tab (a new tab replays the intro).
4. Look at the overview: the **Arrivals** list marks each flight "Agents agreed", "Fallback" or "No recovery plan". Open WN4832 and check that the agent strip shows counts for two turns and the right panel says "Agents agreed". If it says "Rule-based fallback" with a fault, the recording did not replay, and Beat 2 uses its fallback wording. `[CHECK ON SCREEN]`

## Restart between rehearsals

Runs live in the API's memory and vanish on restart. Each run's evidence log is also a file under `apps/api/run_logs/` (git-ignored). Restarting clears the in-memory runs. Each click on a flight makes a new run, so a flight you approved or rejected earlier can be planned again.

1. Stop the API (Ctrl+C in its tab).
2. Start it again with `pnpm dev:api`.
3. Run the two `curl` lines above.
4. Reload the browser tab. Click the flight again. Click **Reset** (the circular arrow in the dock) if any runway or gate is still marked closed on the map. `[CHECK ON SCREEN]`

To clear old log files too, delete `apps/api/run_logs/`. It is safe: the folder is git-ignored and is rebuilt on the next run.

The web app does not need a restart between rehearsals. Reload the page.

## Offline notes and the wifi-off check

- The fonts are bundled with the web app, so they need no network.
- The map on the flights page draws its tiles from a free online basemap (CARTO Dark Matter), so the map needs the network. The code says that without it a dotted backdrop stays visible and nothing else changes. Not seen running. `[CHECK ON SCREEN]`
- `pnpm build` and `pnpm install` need the network. Do them before the venue.
- Not yet done: a full run of the demo with wifi off.

**Wifi-off check, before the talk:** with the API and web up and the overview loaded, turn wifi off. Reload the tab, click WN4832, and go through all five beats once. Look for: the map (route lines and labels may be missing but the page must still work), the globe on the overview, and the **Evidence** tab. If the map is blank, decide now whether to keep wifi on for the talk (the venue network is then a risk) or to present with the dotted backdrop and say the map needs a network. Do not find this out on stage.

## Check the data and the tests

```bash
uv --directory apps/api run pytest
pnpm typecheck
pnpm lint
```

Write the test output to a file and read the exit code before relying on it. A pipe through `grep` or `head` hides a failure.

## What to expect today

- **Model off** works with no key. A flight list loads, a run builds, sign-off and the log work.
- **Recorded** replays saved model answers, and it is the default on the flights page and the only mode the overview uses. It is the recovery from a Live run that fails, and the backup with no network. Any change to runways or gates is not what was recorded, so the rules choose the plan, and the page lists "No recording" and says why.
- **Live** is available only when the API is started with `ALLOW_LIVE=1` and a credential; otherwise it is refused. The stage demo runs on it, in beat 1 only: see "Start for the Live demo".

## If a visual fails: the 30-second plan

Stay calm, say what happened in one sentence, and take the first row that fits. Each fix is meant to take no more than 30 seconds. Never start a live model run to recover.

| What fails | First 10 seconds | Then |
|---|---|---|
| The map is blank or has no tiles | Say: "The map needs a network; the plan does not." | Carry on. The panels, the agent strip and the sign-off work without it. If it matters, click **Airport 3D** in the top-left group of the map area and carry on. `[CHECK ON SCREEN]` |
| The globe or the overview does not draw, or the **Arrivals** list is empty | Reload the tab once. | If still empty, go straight to `http://localhost:3000/dashboard/flights` and click the flight in the left list. Skip Beat 1's overview click. |
| The intro plays again | Click anywhere to skip it. | Continue. |
| The agent strip shows no counts or a warning | Look at the right panel. If it says "Rule-based fallback", the recording did not replay. | Switch to the "If the recording is not ready" wording in Beat 2. Say nothing about agents agreeing. |
| A drawer view shows a red error or stays empty | Click **X** (Close), then click the view's name again. | If it persists, reload the tab and click the flight again, and skip the rest of that beat. |
| **Approve** or **Tamper log** does nothing | Click the flight in the left list to make a new run. | Redo the click once. If it fails again, say so and move to Beat 4. |
| A runway click does not re-run the plan | Wait 3 seconds (the dock shows "Re-running"). | Click the runway tile again. If the airport has more runways, close each one in turn. |
| The Evidence tab is empty or shows an error | Click **Retry** in the panel. | Say the numbers are in `apps/api/eval_results/latest_off_none.md`, and open that file in a text editor. |

## If something fails on stage

Say what happened in one sentence. Do not hide it. Then:

| What you see | What to do |
|---|---|
| "Cannot reach the planning service" | The API stopped. In its tab, run `pnpm dev:api` again. Click **Retry** on the page. The current run is lost. Click the flight again. |
| The flight list is empty or says the flight data is not available | The API cannot find the flight file. Check that the path above exists, or set `FLIGHTS_CSV`, then restart the API. |
| The right panel says "Rule-based fallback" with a "No recording" or "Model off" fault | Expected until the answers are saved again. Use the fallback wording in `demo-script.md` Beat 2. Do not claim the agents negotiated. |
| A page of red text or a blank page | Reload the browser. If it persists, restart `pnpm dev:web`. |
| Sign-off says "Unknown run" | The API restarted. Click the flight again. |
| The log says it no longer checks out | Make a new plan by clicking the flight again. Say so. This is the system working as designed. |
| The talk is running long | Skip Beat 3's log tamper, then Beat 5's second half. Keep Beat 4. The failure is the point. |
| Nothing works | Show the evidence file `apps/api/eval_results/latest_off_none.md` in a text editor and talk through `judge-card.md`. |

Do not start live model runs to recover. They spend money and are not part of the demo.
