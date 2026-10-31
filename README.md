# Magic Airbus: arrival recovery

Autonomous SG 2026, Airbus track, Challenge 2.

A duty manager picks a late flight. Three agents, for air traffic control (ATC), the pilot and ground operations, negotiate a recovery plan in at most 2 turns. Code checks every limit. A person approves, rejects or takes over.

The agents propose and code decides. The model never does arithmetic or legality checks.

Every figure in this file comes from `apps/api/eval_results/`. Rules-only figures are from the mode off run at commit `e3fe575`, seed 0, 5000 flights (`latest_off_none.md`). Live figures are from the first frozen run, run-0002, at commit `db54b25`, seed 0, 20 flights, class unseen (`eval_live_frozen_seed0_2026-10-31T055759Z.md`). These are different evidence classes, so do not compare them.

## What is built

Read from the code in this repo.

- **API** (`apps/api`, FastAPI): builds a scenario from a real US DOT flight row, enumerates candidate plans (arrival slot, gate, flight-plan action), removes every plan that breaks a rule, runs the negotiation, and holds the result for sign-off.
- **Rules** (`apps/api/app/negotiation/rules/`): hard limits for ATC, pilot and ground, each with a stable rule ID and a source. A separate harm check (`harm.py`) reads the final plan with its own logic.
- **Fallback** (`fallback.py`): picks the lowest-cost plan that passes every rule, or says no-go.
- **Protocol** (`protocol.py`): turn cap of 2, enforced in Python. The model cannot change it.
- **Sign-off** (`signoff.py`): re-runs all rules on the current state and refuses if the airport, the plan or the card changed.
- **Log** (`log.py`): a hash-chained log of every message and verdict, with a verifier.
- **Dashboard** (`apps/web`, Next.js): flight list, recovery plan, negotiation, log and evidence views, a sign-off panel, and a "Try to break it" bar.
- **Evaluation** (`apps/api/app/negotiation/evaluate.py`, `scripts/evaluate.py`): one command prints the table, with an evidence class on each number.

Run modes: **Model off** (rules only), **Recorded** (replays saved model answers) and **Live** (calls the model; available only when the API is started with `ALLOW_LIVE=1` and a credential). The presenter's build starts in Live with `NEXT_PUBLIC_DEFAULT_RUN_MODE=live`, and then runs only a flight someone picks. Unset, the flights page opens in Recorded or Model off.

## Design choices that matter for judging

- **A failure is a visible answer.** When no plan is legal, the answer is a no-go. It lists the rules that block every plan, the closest plan and what would have to change. No-go means no plan was cleared and a person decides. It does not mean the flight should not land. A system fault is shown as a different kind of no-go.
- **Trust.** Every field is labelled Real, Derived or Synthetic. Every limit shows its status: workbook limit, our policy, an assumption, or set by the scenario. A limit is never described as a regulation unless it is one.
- **Traceability.** Every message and verdict goes into a hash-chained log. The log head is recorded on the sign-off.
- **Authority.** The airline decides the gate. The arrival slot and flight-plan action are requests to ATC. The pilot in command keeps fuel and safety authority. Approved does not mean executed.
- **One decision per run.** A plan is approved or rejected, and a no-go is taken over. A later decision on the same run is refused.
- **Honest evaluation.** Evidence classes are never compared. Rows that need a model show NOT_REACHED until one has run. The agents are compared against the rule-based fallback on the same rows, and the result is reported below whatever it says.

## Run it

You need Node 24, pnpm, `uv` and Python 3.13. The full steps, restarts and stage failures are in `docs/submission/runbook.md`.

```bash
pnpm install
pnpm dev:api    # FastAPI on http://localhost:8000
pnpm dev:web    # dashboard on http://localhost:3000
```

The flight file is not in the repo. The API reads `FLIGHTS_CSV` (a path) from its environment. If unset, it uses a path fixed in `apps/api/app/negotiation/dot.py`. The web app and the API start with no other setting. See `.env.example` for every variable and what kind of value it is.

Tests:

```bash
uv --directory apps/api run pytest
pnpm typecheck
pnpm lint
```

## Reproduce the evaluation

Model off, a stratified sample of 5000 rows (half weather, half late aircraft), seed 0:

```bash
uv --directory apps/api run python scripts/evaluate.py --mode off --sample 5000
```

It writes a timestamped file and `latest_off_none.md` and `.json` to `apps/api/eval_results/`. Each file starts with the commit, mode, seed and sample size. It takes several minutes. The dashboard's Evidence tab shows the latest file.

The live run uses a frozen split held out by season (July to December, without October) and by destination airport. Print the plan first. It spends nothing:

```bash
uv --directory apps/api run python scripts/evaluate.py --print-live-plan
```

A live run needs a model credential and `--confirm-live-calls N`, and it spends money. The first frozen score is kept and never overwritten. Do not run it without agreeing the call count first.

## Data

- Source: Kaggle `usdot/flight-delays`, `flights.csv`, 5,819,079 rows. The file is git-ignored.
- Eligible rows follow the brief: `WEATHER_DELAY` above 15 or `LATE_AIRCRAFT_DELAY` above 20. October is left out, because its airport codes are numeric (17,351 eligible rows).
- The eligible rows number 358,774. They match the organisers' filtered file exactly.
- The agents never see arrival time, arrival delay or the delay-cause split beyond what was known at the decision point.

Provenance:

| Label | Fields |
|---|---|
| Real | Schedule, airline, tail, origin, destination, `WEATHER_DELAY`, `LATE_AIRCRAFT_DELAY` |
| Derived | The same tail's next leg, arrivals per hour at the destination that day, the destination's median taxi-in |
| Synthetic, seeded per flight | Wake category, fuel on board, runway and taxiway blockage, gate map, ground shift end, connections, and the delay that reaches the next leg |
| Organisers' workbook (synthetic planning limits, not regulations) | Runway, gate and turnaround limits per airport, wake separation, fuel reserves, crew duty |

## Limits and changes to state

- **Turn cap.** The organisers' brief lets the fallback decide after 3 turns. We stop at 2, so we fall back one turn earlier than the brief allows. This is the one change to a brief limit that we are sure of.
- **Additions where the workbook is silent**, from `rule_values.py` (the author of this README has not re-compared them with the workbook file): "super behind super" takes the 3-mile default; a small aircraft behind a B757 is not modelled; the workbook's minimum-time column for departures is not used, because only arrivals are sequenced; gate buffer, approach speeds and the 5-minute slot grid are labelled assumptions; the alternate-fuel test is our policy, shaped on a US regulation.
- **Wake separation** uses the legacy classes. Real terminals use RECAT, which needs aircraft types the data lacks.
- **Results are simulated** on 2015 US data with synthetic operational fields. They are not measured savings.
- **Missing cases.** The eligible rows contain no cancelled or diverted flights, so the worst disruptions are missing.
- **Fuel on board is synthetic** and, by the generator's design, usually above the workbook's 45-minute default.
- **Closing a runway does not lower the airport's arrivals-per-hour limit.** The demo does not model reduced airport capacity.
- **The no-go rate depends strongly on synthetic settings.** It is 1081/5000 (21.6%) on the full sample. On a 500-flight sample it moves from 27/500 (5.4%) to 186/500 (37.2%) as `p_next_leg_hard` goes from 0.0 to 0.7.
- **Outcomes are unstable across synthetic seeds.** 2095/5000 flights (41.9%) flip between a plan and a no-go.
- **Few flights contain real trade-offs.** The first generator had none. We added a synthetic gate conflict before any model ran, so the trade-offs describe our generator, not real operations. See `apps/api/eval_results/generator_change_before_after.md`.
- **The rule of thumb also breaks no rules** (0/3919), because it consults the rules, as do our final plans (0/3919). Safety rests on the gate, not on the agents.
- **First-come-first-served** broke a rule on 3150/5000 (63.0%). It is an uncoordinated comparison, not a model of a good human.
- **Agents are not shown to beat the rules.** In the first frozen run a model answered on 14 of 20 flights, and all 14 agreed on turn 1. The other 6 were no-go, with nothing legal. The agents' plan cost more than the fallback's on 9/14 (64.3%, interval 38.8-83.7%) and was the same plan on 5/14 (35.7%). Both are priced with the same weights, so the value of the notes is not priced. Final plans breaking a rule were 0/14 (interval 0.0-21.5%), and 20 flights prove little.
- **The rules are a subset of real ATC procedure**, and "rules that bind most" partly describes our generator.
- **Date-line flights** (25 of the 358,774 eligible rows) land a day off and draw traffic from the wrong day. The airport taxi median uses the whole file, including the flight's own row.
- **The log** catches an edit but not a full rewrite, unless the head is compared with a copy kept elsewhere.
- **No sign-in.** The approver is recorded as "Duty manager (demo, not authenticated)".
- **Not independently checked.** An independent check found a defect in the crew-duty and gate-notice rules. It was fixed, and the rules-only figures above were generated after the fix. Hand-worked scenarios had not been checked by someone who did not write them as of the last run.
- **Recorded mode** replays saved answers from `apps/api/recordings/`, for the flights marked "Recorded" in the list. It covers each airport only as recorded: after any change to runways or gates, the rules choose the plan, the screen lists "No recording" faults and says why. A flight with no saved answers opens in Model off.

Further reading: `docs/submission/` holds the demo script, runbook, judge card and Q&A.
