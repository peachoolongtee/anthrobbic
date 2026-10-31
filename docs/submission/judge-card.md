# Judge card: things you can try

One page. Start on the **Overview**, click any delayed flight in **Arrivals**, or open **Flights** in the top bar and pick one from the left list. Everything runs on this laptop, except **Live**, which calls the model.

## What you are looking at

A duty manager picks a late flight. Three agents (ATC, pilot, ground) negotiate for at most 2 turns. Code checks every limit. A person approves the plan or does not. If no plan is legal, the answer is a no-go ("No legal recovery plan" on screen), and a person decides. A no-go means no plan was cleared. It does not mean the flight should not land.

Labels on every field: **Real** (US DOT record), **Derived** (worked out from it), **Synthetic** (invented for this demo, seeded per flight). On screen they are small letters R, D and S next to a fact, with the full name on hover, and in words in **Sign off**.

The map and the 3D airport are illustrative. The route is a curve between two airports, the aircraft circling a hold is drawn, and the 3D airport is not the real layout. The rules read the plan data, not the pictures.

## The screen

- **Overview** (home page): a globe headed "Demo flights", labelled as an illustration, an **Arrivals** list of 12 flights, and 2015 record counts. Panels are tagged "Demo flights" or "US DOT 2015" (real counts).
- **Flights**: the flight list on the left, the map in the middle with the agent strip (ATC, Pilot, Ground) above it, a **Try to break it** card at the bottom right of the map (closed at first; click its heading to open it), a bottom bar with **Plan**, **Negotiation**, **Log** and **Evidence**, and the plan summary and **Sign off** on the right. A **Map** and **Airport 3D** switch sits at the top left of the map area.
- **Run mode** at the top right: **Model off**, **Recorded** or **Live**. A flight marked "Recorded" opens in Recorded; any other opens in Model off. Live is available only when the API is started with `ALLOW_LIVE=1`. Live spends money, so please leave it to the presenter.

## Things to try

| Try this | You should see |
|---|---|
| Set **Run mode** to **Model off**, then click a flight | A plan built by rules alone. The right panel says "Rule-based fallback", and the strip says "The agents did not run". |
| Pick WN4832 (DCA to MDW) in **Recorded**, then click **Negotiation** | "Agents agreed? Yes", "Rules passed? Yes", then Turn 1 and Turn 2, with "Would accept N plans" for each agent and notes marked **Unverified**. Notes are synthetic, and the turn-2 prompt invites agents to withdraw soft objections. |
| Open **Try to break it** and click a runway on its diagram (for example R1) | A new plan on another runway, or "No-go: no recovery plan passes" if none is left. Saved answers cover the airport only as recorded, so the panel says "This plan is for the changed airport" and lists "No recording" faults. Closing a runway does not lower the airport's arrivals-per-hour limit. That limit stays as the workbook sets it, so fewer runways can still show the same cap. |
| Close every runway | "No legal recovery plan", "No-go: nothing is legal", "Rules that block every plan", "Closest plan". In **Sign off**: "Nothing to approve." |
| Click a gate on the diagram | A plan on another gate, or no legal plan if every gate fails a rule. |
| In the card, pick "Too little fuel" (or another unsafe plan) and click **Inject** | "Caught before it could be chosen". The plan is listed under "Plans the rules removed" in **Negotiation**, with the rule IDs that stopped it. It is never offered to an agent or to sign-off. |
| In the card, click **Late change**, tick the two boxes in **Sign off**, and click **Approve** | A red alert, "This plan is out of date. Sign-off refused: the airport changed after you looked.", and "Refused: the airport changed after you looked". Nothing is issued. Click **Make a new recovery plan** to start again, or the card's reset arrow to clear the change. |
| Tick both boxes and click **Approve** on a good plan | "Requests issued, nothing executed" and the button reads "Approved". With only the first box ticked it reads "No requests issued, nothing executed". Approving is not executing, and each plan takes one decision. |
| Click **Reject plan**, or **I've taken this case** on a no-go | Reject asks you to confirm, then "Plan rejected. Nothing was issued." Taking a case reads "Logged: this case is with the duty manager. Nothing was approved or requested." Either one is logged, and the run takes no later decision. |
| Click **Find any flight** in the left panel | Searches all 358,774 eligible flights by date and number. It says why when a flight is excluded (October) or is not a disruption case. A found flight with no saved answers runs on rules only, and the page says so. |
| Click a preset in the card: **Runway closes**, **Ground equipment fails** or **Weather worsens** | A new plan, and a notice saying how the preset is modelled, such as "Runway closure, modelled as closing runway R3". |
| Click **Tamper log** in the card | The **Log** view opens with "Tampered copy: detected" and the first bad entry. The real log is not changed. "The log checks out." is for the real one. **Download consensus log** saves the run as a JSON file. |
| Click **Plan** | The plan's detail, and **Delay spread**: this aircraft's later flights that day, as a scheduled projection, not what actually happened. |
| Click **Evidence** | The headline numbers first, rules only apart from the model runs, each with its class, commit, mode and seed. Then where we differ from the workbook and the limits, as closed sections, then full tables. |
| Switch **Map** to **Airport 3D** | A 3D view of the synthetic runways and gates, which also closes runways and gates when clicked. Illustrative only. |

## Facts to know before you judge

- **Fuel on board is synthetic.** By the generator's design it is usually above the workbook's 45-minute default. A flight with plenty of fuel is easy. Do not read a fuel result as a finding about real airlines.
- **Runway, taxiway, gate, wake and crew limits come from the organisers' workbook.** They are synthetic planning limits, not regulations. We label them so on screen.
- **Runway, taxiway and gate blockages, wake class, fuel, gate map and connections are synthetic**, seeded per flight. Flight times, airline, tail and route are from the real file. Taxi-in is derived: the destination's median. The same aircraft's next flight is derived from the file. The delay that reaches it is labelled synthetic where the list says so.
- **The notes the agents read are synthetic.** Soft notes can act like vetoes on turn 1, and the agents see at most 12 of the legal plans. Code, not the agents, decides what is legal.
- **Turn cap:** we fall back one turn earlier than the brief allows: at most 2 turns, where the brief allows 3.
- **Results are simulated on 2015 US data.** They are not measured savings. The data has no cancelled or diverted flights, so the worst disruptions are missing. October is left out.
- **A failure is a feature here.** Please try to break it.

## Numbers (copied from the evaluation files, with commit, mode and seed)

Rules only. Commit `e3fe575`, mode off, seed 0, 5000 flights (`apps/api/eval_results/latest_off_none.md`). This is a different evidence class from the live table, so do not compare the two.

| Measure | Value |
|---|---|
| Final plans that break a rule | 0/3919 (0.0%) |
| First-come-first-served plans that break a rule | 3150/5000 (63.0%) |
| Rule of thumb that checks the rules first, plans that break a rule (zero by construction) | 0/3919 (0.0%) |
| No-go rate, nothing legal | 1081/5000 (21.6%) |
| No-go rate when one synthetic setting moves (`p_next_leg_hard` 0.0 to 0.7, 500 flights) | 27/500 (5.4%) to 186/500 (37.2%) |
| Outcomes that flip between plan and no-go across synthetic seeds | 2095/5000 (41.9%) |

Live. First frozen run, run-0002, commit `db54b25`, mode live, seed 0, 20 unseen flights (`apps/api/eval_results/eval_live_frozen_seed0_2026-10-31T055759Z.md`). A later frozen run is listed in `frozen_runs.json`; it is not the headline.

| Measure | Value |
|---|---|
| Flights a model answered | 14/20 (70.0%) |
| Of those, agents agreed and every rule passed | 14/14 (100.0%), all 14 on turn 1 |
| No-go, nothing legal | 6/20 (30.0%) |
| Fallback used | 0/20 (0.0%) |
| Final plans that break a rule | 0/14 (0.0%), interval 0.0-21.5% |
| Agents' plan costs more than the fallback's | 9/14 (64.3%), interval 38.8-83.7% |
| Agents pick the same plan as the fallback | 5/14 (35.7%) |

**Agents are not shown to beat the rules.** All 14 agreed on turn 1, so this run did not need the turn-2 withdrawal that WN4832 shows. Both costs use the same weights, so the value of the notes is not priced. Twenty flights prove little.
