# Judge card: things you can try

One page. Pick any delayed flight in the left list. Everything runs on this laptop.

Marks: `[RESULT]` is a number from an evaluation run that is being regenerated. `[LIVE RESULT]` needs a model run that has not finished. `[IF MERGED]` is a feature still being built.

## What you are looking at

A duty manager picks a late flight. Three agents (ATC, pilot, ground) negotiate for at most 2 turns. Code checks every limit. A person approves, rejects or takes over. If no plan is legal, the answer is a no-go, and a person decides. A no-go means no plan was cleared. It does not mean the flight should not land.

Labels on every field: **Real** (US DOT record), **Derived** (worked out from it), **Synthetic** (invented for this demo, seeded per flight).

## Things to try

| Try this | You should see |
|---|---|
| Click a flight, with "Model off" in Run mode | A plan, built by rules alone. The chip "Agents agreed?" says "Not asked: model off". |
| Click **Recorded** in Run mode | `[LIVE RESULT]` Turn 1 and Turn 2 under **Negotiation**. Until saved answers are rebuilt, the plan falls back to rules, and a fault says "No recording". |
| Under "Try to break it", close a runway | A new plan on another runway, or a no-go if none is left. Closing a runway does not lower the airport's arrivals-per-hour limit. That limit stays as the workbook sets it, so fewer runways can still show the same cap. |
| Close every runway | "No-go: nothing is legal", the rule that blocks every plan, the closest plan, and what would have to change. "Nothing to approve." Click **I've taken this case** to log it. |
| Block a gate | A plan on another gate, or a no-go if every gate fails a rule. |
| Choose an unsafe plan, such as "Too little fuel", and click **Inject** | "Caught before it could be chosen". The plan is listed under "Plans the rules removed" with the rule IDs that stopped it. It is never offered to an agent or to sign-off. |
| Click **Change airport state**, then tick the boxes and click **Approve** | A red banner: sign-off refused because the airport changed after you looked. Nothing is issued. |
| Click **Approve** on a good plan | "Approved", and "Nothing has been executed." Approving is not executing. |
| Approve, then try **Reject plan** (or the other way round) | The second action is disabled or refused. Each run takes one decision. |
| Open **Log**, click **Tamper with log** | "Tampered copy: detected" and the first bad entry. The real log is not changed. |
| Open **Evidence** | A table of measures with a value, an interval, the number of cases, an evidence class and the run. Rows that need a model show NOT_REACHED. |

## Facts to know before you judge

- **Fuel on board is synthetic.** By the generator's design it is usually above the workbook's 45-minute default. A flight with plenty of fuel is easy. Do not read a fuel result as a finding about real airlines.
- **Runway, taxiway, gate, wake and crew limits come from the organisers' workbook.** They are synthetic planning limits, not regulations. We label them so on screen.
- **Runway, taxiway and gate blockages, wake class, fuel, gate map and connections are synthetic**, seeded per flight. Flight times, airline, tail and route are from the real file. Taxi-in is derived: the destination's median. The same aircraft's next flight is derived from the file. The delay that reaches it is labelled synthetic where the list says so.
- **Turn cap:** the brief lets the fallback decide after 3 turns. We stop at 2.
- **Results are simulated on 2015 US data.** They are not measured savings. The data has no cancelled or diverted flights, so the worst disruptions are missing. October is left out.
- **A failure is a feature here.** Please try to break it.

## Numbers (copied from the evaluation file, with commit, mode and seed)

| Measure | Value |
|---|---|
| Final plans that break a rule | `[RESULT]` |
| First-come-first-served plans that break a rule | `[RESULT]` |
| No-go rate | `[RESULT]` |
| No-go rate when one synthetic setting moves | `[RESULT]` to `[RESULT]` |
| Outcomes that flip between plan and no-go across synthetic seeds | `[RESULT]` |
| Agents versus the rule-based fallback | `[LIVE RESULT]` |

Commit: `[RESULT]`. Mode: off. Seed: 0.

## Not on this card yet

Flight lookup by number `[IF MERGED]`. Delay spread view `[IF MERGED]`. Log download `[IF MERGED]`. Headline panel `[IF MERGED]`. Presets `[IF MERGED]`.
