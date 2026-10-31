# Demo script: 3 minutes, five beats, new dashboard design

Autonomous SG 2026, Airbus track, Challenge 2. Read aloud at 150 words a minute. The spoken text is 332 words in total (about 133 seconds of speech, counting each `[RESULT]` as two words), which leaves about 47 seconds for the clicks. Each beat has its own word budget in its heading. Rehearse once with a timer.

Every click and screen text below was checked on the integrated design at 1280x720, on the real API with the real dataset, the saved WN4832 answers, and every non-local request aborted. The results are at the end.

## Marks used in this file

- `[RESULT]` is a number from a rules-only evaluation run. No figure is typed in the spoken text. Read it from `apps/api/eval_results/latest_off_none.md` before the talk (table at the end), copy it exactly, and say its commit, mode and seed.
- `[LIVE RESULT]` needs a live model run that has not happened. Do not say it until the screen shows it.
- `[IF MERGED]` is a feature still being built. Skip it unless it is on screen.

## Before you go on stage

Follow `runbook.md` first. Then:

1. The intro (a plane crossing the screen) plays once per browser tab. Open `http://localhost:3000` in the tab you will use, click anywhere to skip it, and leave the tab open on the overview. Landing and intro are not part of the 3 minutes.
2. The flights page opens in **Recorded** when the flight has saved answers, and in **Model off** when it has none. Never use **Live** on stage. Restart the API before each rehearsal: a used approval is refused until then.
3. Know where WN4832 is. In the overview's **Arrivals** list (scroll down past the globe), look for the row "DCA → MDW" with "WN4832" under it. The list holds 12 flights, those with saved answers first, then by scheduled arrival. If it is not there, on the flights page type WN4832 in **Search** in the left panel. The first load after an API restart takes several seconds, so open the overview once before you go on.

## Beat 1. The user (0:00 to 0:20). Budget 50 words, spoken text 42

**Screen:** the overview. The globe is headed "Delayed arrivals", with the **Arrivals** list under it.

**Click:** in the **Arrivals** list, click the row "DCA → MDW" (WN4832). It opens the flights page with that flight selected and a recovery plan already running.

**Say:**

> A flight is late. Today a duty manager phones air traffic control, the crew and the ramp, one by one, while the delay spreads. These are delayed arrivals from the real 2015 US record. I pick WN4832, Washington National to Chicago Midway.

## Beat 2. The negotiation (0:20 to 1:20). Budget 150 words, spoken text 100 (fallback wording 46)

**Screen:** the flights page. Flights list on the left, the map in the middle, the plan and sign-off on the right. Across the top of the map is the agent strip with ATC, Pilot and Ground, each with a count per turn.

**Click, in order:**

1. Point at the agent strip (ATC 4 › 12, Pilot 8 › 8, Ground 7 › 12), then at the route on the map. The **Try to break it** card at the bottom right starts closed, so the route is clear. The map is illustrative: the plan's action is a hold, so a hold is drawn and labelled "Illustrative hold". It is not tracked.
2. At the bottom, click **Negotiation** (in the bar with Plan, Negotiation, Log, Evidence).
3. The drawer opens on the outcome and the turns. Point at **Turn 1**, the three columns ATC, Pilot, Ground, each "Would accept N plans", and the dashed note marked **Unverified**. Then scroll to **Turn 2** and point at ATC's and Ground's "Withdrew its objection to" and the notes beside them.
4. Click the **X** (Close) at the top right of the drawer.
5. Point at the right panel: "Agents agreed", "Passes the rules checked", "2 turns".

The view shows each agent's accepted count, reasons in plain words, objections withdrawn, and the model's own note, labelled **Unverified**. The private synthetic notes themselves are not shown: the words "no direct" and "R3" on screen are the model's, in its note. Say only what the screen shows.

**Say**:

> Three agents negotiate: ATC, the pilot and the ground crew. Code first removes every plan that breaks a rule. The agents choose only among what is left. Each reads a short note about its own side. Those notes are synthetic, written by our generator.
>
> Turn one: no shared plan. The pilot's firm note says no direct routing. ATC's soft note says avoid runway R3. They conflict.
>
> Turn two: the prompt invites each agent to withdraw soft objections, so this is not persuasion. ATC and Ground withdraw theirs. The pilot holds. A shared plan appears. Code still decides what is legal.

**If the screen says "Rule-based fallback".** The saved answers did not load, the right panel lists "No recording: ATC, Pilot, Ground", and the agent strip shows × for each agent. Say this instead, and say nothing about agents agreeing:

> Three agents are meant to negotiate here. This time they did not: the saved model answers did not load. The rules alone chose this plan, and the screen says so. Code removes every illegal plan first, so even a fallback plan has passed every rule.

## Beat 3. The trust (1:20 to 2:00). Budget 100 words, spoken text 76

**Click, in order:**

1. On the right panel, point at the small letter marks next to the plan facts, and the line under them: "R real, D derived from the file, S synthetic." Hovering one shows the word.
2. Click the **Try to break it** heading to open the card, which stays open for the rest of the talk. Click **Late change**. This blocks the plan's gate on the server while the screen keeps the old plan.
3. In the **Sign off** panel, the two boxes sit directly above **Approve**, with no scrolling. Tick **I approve these decisions** and **Send these requests**, then click **Approve**.
4. A red alert appears: "This plan is out of date. Sign-off refused: the airport changed after you looked." In the Sign off panel the refusal reads "Refused: the airport changed after you looked", and it names "Gate occupancy".
5. In the **Try to break it** card, click **Tamper log**. It opens the **Log** view. Point at "Tampered copy: detected" and "First bad entry". If you have time, point at "The log checks out." for the real log. Click the **X** to close the drawer.

**Say:**

> Every field is marked real, derived or synthetic. Fuel, runways and gates are synthetic, and we say so.
>
> I block this plan's gate after the manager looked, then approve. Sign-off runs every rule again on the current airport, and refuses. Nothing is issued.
>
> Every message goes into a hash-chained log. I edit a copy: caught, with the first bad entry. A chain alone cannot catch a full rewrite, so its head is recorded on the sign-off.

## Beat 4. The failure (2:00 to 2:30). Budget 75 words, spoken text 54

**Click, in order:**

1. Click **Reset every change** (the circular arrow at the top of the **Try to break it** card). It clears the blocked gate and returns to the recorded agreement. Do not use **Make a new recovery plan** here: it keeps the blocked gate, which no recording covers, so it lists "No recording" faults.
2. In the **Try to break it** card, on the diagram (keep **Map** selected, not **Airport 3D**), click **R1**, then **R3**. R2 at MDW is already closed in this scenario and cannot be clicked. After R1 the panel lists "No recording: ATC, Pilot, Ground" and a rule-based plan, because a changed airport is not what was recorded. Say so if asked. R3 gives the no-go.
3. Point at the right panel: "No-go" and "No-go: no recovery plan passes". Click **Plan** at the bottom and point at "No legal recovery plan", "No-go: nothing is legal", "Rules that block every plan" and "Closest plan". Click the **X**.
4. Point at the Sign off panel: "Nothing to approve." Click **I've taken this case**. It reads "Logged: this case is with the duty manager. Nothing was approved or requested."

**Say:**

> Now I close every runway. The system does not guess. It says no legal recovery plan, names the rules that block every plan, and shows the closest one. This is a no-go. No-go means no plan was cleared and a person decides. It does not mean the flight should not land. Nothing was approved.

## Beat 5. The numbers (2:30 to 3:00). Budget 75 words, spoken text 60

**Click:** the **Evidence** tab at the bottom. It opens on the numbers, with no scrolling: **Rules only** on the left, **With the model: tuned and unseen flights** on the right, each set with its class, commit, mode and seed. "Where we differ from the challenge workbook" and the limits are closed sections under them, then the full tables. The tab reads the evaluation through the API, so check that it shows the same commit as the file.

**Say:**

> Rules-only numbers first, from a run of `[RESULT]` flights, model off. First-come-first-served plans broke a rule on `[RESULT]`. Our final plans broke a rule on `[RESULT]`. A rule of thumb that checks the rules first also breaks none, so the gate does the safety work. Live, agents versus fallback: `[LIVE RESULT]`. Unproven. These are simulated, not savings.

## Slots to fill before the talk

Copy each value exactly as the file prints it. Do not round or recompute. Say the commit, mode and seed from the file header aloud, or have them on the Evidence tab. The last column shows what the file printed when this script was written (commit `e3fe575`, mode `off`, seed 0, in `apps/api/eval_results/latest_off_none.md`). Verification is pending, so re-read the file. The speaker must not use this column.

| Slot | Row to copy (name as printed in the file) | Printed when this was written (unverified) |
|---|---|---|
| Sampled flights | "Rows evaluated" | 5000 rows |
| First-come-first-served broke a rule | "first_come_first_served: packages breaking a rule" | 3150/5000 (63.0%) |
| Our final plans broke a rule | "Final packages breaking a rule" | 0/3919 (0.0%) |
| Rule of thumb broke a rule | "human_heuristic: packages breaking a rule" | 0/3919 (0.0%), zero by construction |
| Agents versus fallback | "LLM versus fallback on the same rows" | NOT_REACHED. `[LIVE RESULT]` |

The denominators differ: 5000 rows are sampled, and 3919 are rows with a plan. Say which one you mean. Rules-only and live rows are different evidence classes, so never put them in one comparison.

Also read these before the talk, because judges ask: "NO_GO NOTHING_LEGAL rate, all rows", "NO_GO rate, all rows, p_next_leg_hard=..." (the lowest and highest setting), "Outcome flips between deal and NO_GO across synthetic seeds", "Pick is no worse than every legal package on every cost component", "Fallback picks the same package as human_heuristic" and "Binding: GND-GATE-NOTICE eliminates packages in these rows".

## What was checked on screen

| # | Checked | Result |
|---|---|---|
| C1 | The intro plays once per tab and a click skips it | Yes |
| C2 | Toggle reads Model off, Recorded, Live; a flight with saved answers opens in Recorded | Yes |
| C3 | WN4832 DCA to MDW is in the overview **Arrivals** list | Yes, row 10 of 12 |
| C4 | Clicking it opens the flights page with that flight selected and a Recorded run | Yes |
| C5 | Agent strip shows counts per turn | ATC 4 › 12, Pilot 8 › 8, Ground 7 › 12 |
| C6 | Map draws the route, labelled illustrative, and works with no network | Yes, on a local basemap; the hold is drawn only because this plan's action is a hold |
| C7 | Bottom bar reads Plan, Negotiation, Log, Evidence; a drawer opens with an X | Yes |
| C8 | Negotiation opens on the outcome and shows Turn 1, Turn 2, "Would accept N plans", withdrawn objections and unverified notes | Yes |
| C9 | Right panel pills | "Agents agreed", "Passes the rules checked", "2 turns" |
| C10 | A missing recording shows as a fault | "No recording: ATC, Pilot, Ground" |
| C11 | Marks R, D, S with a hover name and a legend line | Yes |
| C12 | **Late change**, the two ticks, **Approve**, the alert and refusal | Yes, wording corrected above |
| C13 | **Tamper log** opens the Log view with its results | Yes |
| C14 | **Reset** returns to the recorded agreement | Yes; **Make a new recovery plan** keeps the blocked gate and shows "No recording" |
| C15 | Runway tiles at MDW | R1, R2 (closed in the scenario), R3 |
| C16 | No-go wording | Corrected above |
| C17 | **I've taken this case** | Present, and two-step **Reject plan** too |
| C18 | Evidence opens on the headline numbers with commit, mode and seed, then the rows | Yes; re-read the values before the talk |

## If something goes wrong on stage

See `runbook.md`, sections "If a visual fails: the 30-second plan" and "If something fails on stage". Never invent a number.
