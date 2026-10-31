# Judge card: things you can try

One page. Start on the **Overview**, click any delayed flight in **Arrivals**, or open **Flights** in the top bar and pick one from the left list. Everything runs on this laptop.

Marks: `[RESULT]` is a number from an evaluation run whose results are still being checked. `[LIVE RESULT]` needs a model run that has not finished. `[RE-RECORD PENDING]` needs saved model answers that are being re-recorded. `[CHECK ON SCREEN]` is a label read from the new design's code, not yet seen running. `[IF MERGED]` is a feature still being built.

## What you are looking at

A duty manager picks a late flight. Three agents (ATC, pilot, ground) negotiate for at most 2 turns. Code checks every limit. A person approves the plan or does not. If no plan is legal, the answer is a no-go ("No legal recovery plan" on screen), and a person decides. A no-go means no plan was cleared. It does not mean the flight should not land.

Labels on every field: **Real** (US DOT record), **Derived** (worked out from it), **Synthetic** (invented for this demo, seeded per flight). On screen they are small letters R, D and S next to a fact, with the full name on hover. `[CHECK ON SCREEN]`

The map and the 3D airport are illustrative. The route is a curve between two airports, the aircraft circling a hold is drawn, and the 3D airport is not the real layout. The rules read the plan data, not the pictures.

## The screen

- **Overview** (home page): a globe of the delayed arrivals, an **Arrivals** list of 12 flights with how each ended ("Agents agreed", "Fallback" or "No recovery plan"), an **Outcomes** ring, **Rules that removed recovery plans**, and 2015 record counts. Panels are tagged "2015 DOT" (real counts) or "Runs" (recorded runs of the demo flights). `[CHECK ON SCREEN]`
- **Flights**: the flight list on the left, the map in the middle with the agent strip (ATC, Pilot, Ground) above it, **Runways and gates** on the map, a dock with the **Try to break it** controls, a bottom bar with **Plan**, **Negotiation**, **Log** and **Evidence**, and the plan summary and **Sign off** on the right. A **Map** and **Airport 3D** switch sits at the top left of the map area. `[CHECK ON SCREEN]`
- **Run mode** at the top right: **Model off**, **Recorded** or **Live**. Recorded is the default. Live is refused on this laptop. `[CHECK ON SCREEN]`

## Things to try

| Try this | You should see |
|---|---|
| Set **Run mode** to **Model off**, then click a flight | A plan built by rules alone. The right panel says "Rule-based fallback", with a "Model off" fault. The agents do not negotiate. |
| Set **Run mode** to **Recorded**, then click **Negotiation** | `[RE-RECORD PENDING]` Turn 1 and Turn 2, with each agent's accepted plans. Until the saved answers are rebuilt, the plan falls back to rules and a fault says "No recording". Notes are synthetic, and the turn-2 prompt invites agents to withdraw soft objections. |
| Click a runway tile under **Runways and gates** (for example R1) | A new plan on another runway, or "No recovery plan passes" if none is left. Closing a runway does not lower the airport's arrivals-per-hour limit. That limit stays as the workbook sets it, so fewer runways can still show the same cap. |
| Close every runway | "No legal recovery plan", "Nothing is legal", "Rules that block every plan", "Closest plan". In **Sign off**: "Nothing to approve." |
| Click a gate tile under **Runways and gates** | A plan on another gate, or no legal plan if every gate fails a rule. |
| In the dock, pick "Too little fuel" (or another unsafe plan) and click **Inject** | "Caught before it could be chosen". The plan is listed under "Plans the rules removed" in **Negotiation**, with the rule IDs that stopped it. It is never offered to an agent or to sign-off. |
| In the dock, click **Change behind**, tick the two boxes in **Sign off**, and click **Approve** | A red "Out of date." alert and "Refused: the airport changed after you looked". Nothing is issued. Click **Make a new recovery plan** to start again. |
| Click **Approve** on a good plan | "Requests issued, nothing executed" and the button reads "Approved". Approving is not executing, and each plan takes one decision. |
| Click **Tamper log** in the dock | The **Log** view opens with "Tampered copy: detected" and the first bad entry. The real log is not changed. "The log checks out." is for the real one. |
| Click **Evidence** | A table of measures with a value, an interval, the number of cases, an evidence class, and the commit, mode and seed. Rows that need a model show NOT_REACHED. |
| Switch **Map** to **Airport 3D** | A 3D view of the synthetic runways and gates, which also closes runways and gates when clicked. Illustrative only. `[CHECK ON SCREEN]` |

## Facts to know before you judge

- **Fuel on board is synthetic.** By the generator's design it is usually above the workbook's 45-minute default. A flight with plenty of fuel is easy. Do not read a fuel result as a finding about real airlines.
- **Runway, taxiway, gate, wake and crew limits come from the organisers' workbook.** They are synthetic planning limits, not regulations. We label them so on screen.
- **Runway, taxiway and gate blockages, wake class, fuel, gate map and connections are synthetic**, seeded per flight. Flight times, airline, tail and route are from the real file. Taxi-in is derived: the destination's median. The same aircraft's next flight is derived from the file. The delay that reaches it is labelled synthetic where the list says so.
- **The notes the agents read are synthetic.** Soft notes can act like vetoes on turn 1, and the agents see at most 12 of the legal plans. Code, not the agents, decides what is legal.
- **Turn cap:** the brief lets the fallback decide after 3 turns. We stop at 2.
- **Results are simulated on 2015 US data.** They are not measured savings. The data has no cancelled or diverted flights, so the worst disruptions are missing. October is left out.
- **A failure is a feature here.** Please try to break it.

## Numbers (copied from the evaluation file, with commit, mode and seed)

Rules-only. Model off. These come from a different evidence class from any live result and must not be compared with one.

| Measure | Value |
|---|---|
| Final plans that break a rule | `[RESULT]` |
| First-come-first-served plans that break a rule | `[RESULT]` |
| Rule of thumb that checks the rules first, plans that break a rule (zero by construction) | `[RESULT]` |
| No-go rate | `[RESULT]` |
| No-go rate when one synthetic setting moves | `[RESULT]` to `[RESULT]` |
| Outcomes that flip between plan and no-go across synthetic seeds | `[RESULT]` |

Live. Not available yet.

| Measure | Value |
|---|---|
| Agents versus the rule-based fallback | `[LIVE RESULT]` |

Commit: `[RESULT]`. Mode: off. Seed: 0.

## Not on this card yet

Flight lookup by number `[IF MERGED]` (the **Search** box in the flight list only filters the flights already loaded `[CHECK ON SCREEN]`). Log download `[IF MERGED]`. Presets `[IF MERGED]`. A reject or take-over button in **Sign off** `[IF MERGED]`. Delay spread view `[IF MERGED]`. Headline panel `[IF MERGED]`.
