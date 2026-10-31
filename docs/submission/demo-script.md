# Demo script: 3 minutes, five beats

Autonomous SG 2026, Airbus track, Challenge 2. Speak at a steady pace. The script is about 430 words. Rehearse once with a timer.

## Marks used in this file

- `[RESULT]` is a number from a rules-only evaluation run. The run is being regenerated after a rule fix, so no figure is typed here. After the new run, read the file `apps/api/eval_results/latest_off_none.md`, copy the value from the row named in the table at the end, and note its commit, mode and seed on the slide or aloud.
- `[LIVE RESULT]` is anything that needs a live or recorded model run. It is not available yet. Do not say it until the screen shows it.
- `[IF MERGED]` marks a feature still being built. Skip it unless it is on the screen.

## Before you go on stage

Follow `runbook.md` first. Then:

1. Open the dashboard. The model mode toggle ("Run mode") is at the top right.
2. In the left list, click **MQ3015, DFW to BTR**. It is a weather delay with a next leg for the same aircraft. In the build checked for this file, the airport has one runway (R1) and three gates (G1 to G3).
3. Click **Recovery plan** (the first tab). Keep the **Try to break it** bar visible at the bottom.

## Beat 1. The user (0:00 to 0:20)

**Screen:** the flight list, MQ3015 selected.

**Click:** none. Point at the card for MQ3015 and at the line "Same aircraft next".

**Say:**

> A flight is late. Today a duty manager phones air traffic control, the crew and the ramp, one by one, while the delay spreads. This is MQ3015, Dallas to Baton Rouge, late for weather. The same aircraft leaves again at 08:46. The list shows the delay reaching that next flight, and labels it synthetic.

## Beat 2. The negotiation (0:20 to 1:20)

**Click, in order:**

1. In "Run mode" at the top, click **Recorded**. The plan rebuilds.
2. Click the **Negotiation** tab.
3. Point at Turn 1, then Turn 2. Each shows ATC, Pilot and Ground.
4. Click the **Recovery plan** tab.
5. Point at the three chips at the top: "Agents agreed?", "Rules passed?", "Chosen by".
6. Point at "You decide" and "You request" on the right.

**Say:**

> Three agents now negotiate: ATC, the pilot and the ground crew. Each sees only its own data. Code first removes every plan that breaks a rule. Each agent then says which of the rest it accepts, and ranks them.
>
> `[LIVE RESULT: one sentence on what each agent preferred in turn 1, read from the screen]`
>
> In turn two they see which kinds of rule removed plans, never the private values behind them.
>
> `[LIVE RESULT: say "they agreed in turn two" or "they did not agree, so the rule-based fallback chose", whichever the chips show]`
>
> The cap is two turns. The organisers' brief lets the fallback decide after three. We stop at two, which is stricter than asked.
>
> Look at the split on the right. The airline decides the gate. The arrival slot and the flight plan are only requests, because ATC grants those. The pilot keeps fuel and safety authority.

**If recorded answers are not ready:** the Recorded button will show "No recording" faults and the chip "Chosen by" will say "rules only, not agents". Say this instead of the two `[LIVE RESULT]` lines, and say nothing about agents agreeing:

> In this build the model is off, so the agents did not negotiate. The rules alone chose this plan, and the screen says so. The live evaluation is not finished.

## Beat 3. The trust (1:20 to 2:00)

**Click, in order:**

1. Point at the small labels Real, Derived and Synthetic on the plan facts.
2. In "Try to break it", click **Change airport state**. This blocks the plan's gate on the server while the screen still shows the old plan.
3. In the Sign off panel, tick **I approve these decisions** and **Send these requests**, then click **Approve**.
4. The red banner appears: "Sign-off refused: the airport changed after you looked."
5. Click the **Log** tab. Point at "The log checks out."
6. Click **Tamper with log** in the bottom bar. Point at "Tampered copy: detected" and the first bad entry.

**Say:**

> Every field carries a label: real from the US transport record, derived from it, or synthetic. Fuel, runways and gates are synthetic. We say so on screen.
>
> Now I block this plan's gate after the manager looked, and try to approve. Sign-off runs every rule again on the current airport, and refuses. Nothing is issued.
>
> Every message and verdict goes into a hash-chained log. I edit a copy: caught, with the first bad entry. A chain alone cannot catch a full rewrite. That is why its head is recorded on the sign-off.

## Beat 4. The failure (2:00 to 2:30)

**Click, in order:**

1. In the bottom bar, click **Reset**. The plan is rebuilt with nothing blocked.
2. Under "Close runway", click **R1**. If the airport shows more runways, close each one in turn. The last click gives the no-go.
3. The Recovery plan tab shows "No-go: nothing is legal". Point at "Rules that block every plan" (ATC-RWY-CLOSED in the build checked for this file), then "Closest plan" and "What would have to change".
4. In the Sign off panel, point at "Nothing to approve". Click **I've taken this case**.

**Say:**

> Now I close every runway. The system does not guess. It says no-go: nothing is legal, names the rule that blocks every plan, and shows the closest plan and what would have to change.
>
> No-go means no plan was cleared and a person decides. It does not mean the flight should not land.
>
> The manager clicks "I've taken this case". That is logged. Nothing was approved or requested.

## Beat 5. The numbers (2:30 to 3:00)

**Click:** the **Evidence** tab. Scroll to the rows named in the table below.

**Say:**

> Every number here comes from a run, with its commit, mode and seed, and an evidence class. The classes are never compared.
>
> On `[RESULT]` sampled flights, with the model off, first-come-first-served plans broke a rule on `[RESULT]`. Our final plans broke a rule on `[RESULT]`. A rule of thumb that checks the rules first also breaks none, so the gate does the safety work.
>
> Whether the agents add value over the fallback: `[LIVE RESULT]`. Until then it is unproven.
>
> The no-go rate is `[RESULT]`. It moves from `[RESULT]` to `[RESULT]` when one synthetic setting changes. These are simulated outcomes on 2015 data with synthetic fields. They are not measured savings.

## Slots to fill before the talk

Copy the value exactly as the file prints it. Do not round or recompute. Note the commit, mode and seed from the file's header.

| Slot | Row to copy (name as printed in the file) |
|---|---|
| Sampled flights | "Rows evaluated" |
| First-come-first-served broke a rule | "first_come_first_served: packages breaking a rule" |
| Our final plans broke a rule | "Final packages breaking a rule" |
| No-go rate | "NO_GO NOTHING_LEGAL rate, all rows" |
| No-go rate, low and high | "NO_GO rate, all rows, p_next_leg_hard=..." (the lowest and the highest setting) |
| Agents versus fallback | "LLM versus fallback on the same rows" (`[LIVE RESULT]`) |

Also read these before the talk, because judges ask: "Outcome flips between deal and NO_GO across synthetic seeds", "Pick is no worse than every legal package on every cost component", and "Fallback picks the same package as human_heuristic".

## If something goes wrong on stage

See `runbook.md`, section "If something fails on stage". Short version: if the API stops, say so, restart it, and carry on from the beat you were in. Never invent a number.
