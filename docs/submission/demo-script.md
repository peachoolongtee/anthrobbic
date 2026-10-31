# Demo script: 3 minutes, five beats, new dashboard design

Autonomous SG 2026, Airbus track, Challenge 2. Read aloud at 150 words a minute. The spoken text is 332 words in total (about 133 seconds of speech, counting each `[RESULT]` as two words), which leaves about 47 seconds for the clicks. Each beat has its own word budget in its heading. Rehearse once with a timer.

This script is written from the code of `origin/feat/frontend` (commit `ff4e74e`), read without checking it out. Another agent is still merging that design, so every click or screen text inferred from code carries `[CHECK ON SCREEN]`. Confirm each one against the running build and fix the script, not the screen. The full list is at the end.

## Marks used in this file

- `[RESULT]` is a number from a rules-only evaluation run. No figure is typed in the spoken text. Read it from `apps/api/eval_results/latest_off_none.md` before the talk (table at the end), copy it exactly, and say its commit, mode and seed.
- `[LIVE RESULT]` needs a live model run that has not happened. Do not say it until the screen shows it.
- `[RE-RECORD PENDING]` marks the negotiation story for WN4832, DCA to MDW. The saved model answers do not match the current prompts, and the story below is the one we expect from a re-recording. Say it only after the re-recording is saved and you have seen it on screen. Otherwise use the "If the recording is not ready" wording.
- `[CHECK ON SCREEN]` is a label or behaviour inferred from code, not seen running.
- `[IF MERGED]` is a feature still being built. Skip it unless it is on screen.

## Before you go on stage

Follow `runbook.md` first. Then:

1. The intro (a plane crossing the screen) plays once per browser tab. Open `http://localhost:3000` in the tab you will use, click anywhere to skip it, and leave the tab open on the overview. Landing and intro are not part of the 3 minutes. `[CHECK ON SCREEN]`
2. The flights page opens in **Recorded** by default. Never use **Live** on stage. `[CHECK ON SCREEN]`
3. Know where WN4832 is. In the overview's **Arrivals** list, look for the row "DCA → MDW" with "WN4832" under it. The list holds 12 flights, sorted by scheduled arrival. If it is not there, on the flights page type WN4832 in **Search** in the left panel. `[CHECK ON SCREEN]`

## Beat 1. The user (0:00 to 0:20). Budget 50 words, spoken text 42

**Screen:** the overview. The globe is headed "Delayed arrivals", with the **Arrivals** list under it.

**Click:** in the **Arrivals** list, click the row "DCA → MDW" (WN4832). It opens the flights page with that flight selected and a recovery plan already running. `[CHECK ON SCREEN]`

**Say:**

> A flight is late. Today a duty manager phones air traffic control, the crew and the ramp, one by one, while the delay spreads. These are delayed arrivals from the real 2015 US record. I pick WN4832, Washington National to Chicago Midway.

## Beat 2. The negotiation (0:20 to 1:20). Budget 150 words, spoken text 100 (fallback wording 46)

**Screen:** the flights page. Flights list on the left, the map in the middle, the plan and sign-off on the right. Across the top of the map is the agent strip with ATC, Pilot and Ground, each with a count per turn. `[CHECK ON SCREEN]`

**Click, in order:**

1. Point at the agent strip, then at the amber route on the map. The map is illustrative: the aircraft circling a hold is drawn, not tracked. `[CHECK ON SCREEN]`
2. At the bottom, click **Negotiation** (in the bar with Plan, Negotiation, Log, Evidence). `[CHECK ON SCREEN]`
3. Point at **Turn 1**, the three columns ATC, Pilot, Ground, and each "Would accept N plans". Then scroll to **Turn 2**. `[CHECK ON SCREEN]`
4. Click the **X** (Close) at the top right of the drawer.
5. Point at the right panel: "Agents agreed" or "Rule-based fallback", "All rules pass", "2 of 2 turns". `[CHECK ON SCREEN]`

The negotiation view in the code shows each agent's accepted count, ranking summary and reason codes. It does not obviously print the raw notes, so "firm no direct" and "soft avoid R3" may only be visible through the reasons. Say only what the screen shows. `[CHECK ON SCREEN]`

**Say** `[RE-RECORD PENDING]`:

> Three agents negotiate: ATC, the pilot and the ground crew. Code first removes every plan that breaks a rule. The agents choose only among what is left. Each reads a short note about its own side. Those notes are synthetic, written by our generator.
>
> Turn one: no shared plan. The pilot's firm note says no direct routing. ATC's soft note says avoid runway R3. They conflict.
>
> Turn two: the prompt invites each agent to withdraw soft objections, so this is not persuasion. ATC and Ground withdraw theirs. The pilot holds. A shared plan appears. Code still decides what is legal.

**If the recording is not ready.** The agent strip will show no counts or a warning, and the right panel will say "Rule-based fallback" with a fault such as "Model off". `[CHECK ON SCREEN]` Say this instead, and say nothing about agents agreeing:

> Three agents are meant to negotiate here. In this build they did not: the saved model answers are being re-recorded. The rules alone chose this plan, and the screen says so. Code removes every illegal plan first, so even a fallback plan has passed every rule.

## Beat 3. The trust (1:20 to 2:00). Budget 100 words, spoken text 76

**Click, in order:**

1. On the right panel, point at the small letter marks R, D and S next to the plan facts. Hovering one shows Real, Derived or Synthetic. `[CHECK ON SCREEN]`
2. In the bottom dock, click **Change behind**. This blocks the plan's gate on the server while the screen keeps the old plan.
3. In the **Sign off** panel, tick **I approve these decisions** and **Send these requests**, then click **Approve**.
4. A red alert appears: "Out of date." In the Sign off panel the refusal reads "Refused: the airport changed after you looked". `[CHECK ON SCREEN]`
5. In the dock, click **Tamper log**. It opens the **Log** view. Point at "Tampered copy: detected" and "First bad entry". If you have time, point at "The log checks out." for the real log. `[CHECK ON SCREEN]`

**Say:**

> Every field is marked real, derived or synthetic. Fuel, runways and gates are synthetic, and we say so.
>
> I block this plan's gate after the manager looked, then approve. Sign-off runs every rule again on the current airport, and refuses. Nothing is issued.
>
> Every message goes into a hash-chained log. I edit a copy: caught, with the first bad entry. A chain alone cannot catch a full rewrite, so its head is recorded on the sign-off.

## Beat 4. The failure (2:00 to 2:30). Budget 75 words, spoken text 54

**Click, in order:**

1. If a refusal is still on screen, click **Make a new recovery plan** in the right panel first. If **Reset** (the circular arrow at the right end of the dock) is enabled, click it. It is enabled only after a runway or gate has been closed from the map. `[CHECK ON SCREEN]`
2. In the **Runways and gates** panel on the map (keep **Map** selected, not **Airport 3D**), click each runway tile in turn, for example **R1**. Each click re-runs the plan. The last runway gives the no-go. `[CHECK ON SCREEN]`
3. Point at the right panel: "No recovery plan passes". Click **Plan** at the bottom and point at "No legal recovery plan", "Nothing is legal", "Rules that block every plan" and "Closest plan". `[CHECK ON SCREEN]`
4. Point at the Sign off panel: "Nothing to approve."

The earlier design had an **I've taken this case** button. It is not in the code read for this design, so do not click for it. If it is on screen, it is `[IF MERGED]` until the merge is confirmed. `[CHECK ON SCREEN]`

**Say:**

> Now I close every runway. The system does not guess. It says no legal recovery plan, names the rules that block every plan, and shows the closest one. This is a no-go. No-go means no plan was cleared and a person decides. It does not mean the flight should not land. Nothing was approved.

## Beat 5. The numbers (2:30 to 3:00). Budget 75 words, spoken text 60

**Click:** the **Evidence** tab at the bottom. Scroll to the rows named in the table below. The tab reads the evaluation through the API, so check that it shows the same commit as the file. `[CHECK ON SCREEN]`

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

## Every `[CHECK ON SCREEN]`

| # | What was inferred from code | Where it is used |
|---|---|---|
| C1 | The intro plays once per tab and any click skips it | Before stage |
| C2 | The flights page defaults to Recorded; the toggle reads Model off, Recorded, Live | Before stage |
| C3 | WN4832 DCA to MDW appears in the overview **Arrivals** list (12 flights) or is found by **Search** | Beat 1 |
| C4 | Clicking an Arrivals row opens `/dashboard/flights?flight=...` with that flight selected and a Recorded run started | Beat 1 |
| C5 | The agent strip shows ATC, Pilot, Ground with accepted counts per turn | Beat 2 |
| C6 | The map draws the route and a circling aircraft, is illustrative, and needs the network for its tiles | Beat 2, runbook |
| C7 | The bottom bar reads Plan, Negotiation, Log, Evidence and opens a drawer with an X (Close) | Beats 2 to 5 |
| C8 | The Negotiation view shows Turn 1 and Turn 2 and "Would accept N plans"; the raw notes ("no direct", "avoid R3") may not appear | Beat 2 |
| C9 | The right panel pills read "Agents agreed" or "Rule-based fallback", "All rules pass", "2 of 2 turns" | Beat 2 |
| C10 | A fault such as "Model off" shows when the recording is missing | Beat 2 |
| C11 | Provenance shows as small letters R, D, S with a hover name | Beat 3 |
| C12 | **Change behind**, **I approve these decisions**, **Send these requests**, **Approve**, the "Out of date." alert and the refusal text | Beat 3 |
| C13 | **Tamper log** opens the Log view with "Tampered copy: detected", "First bad entry" and "The log checks out." | Beat 3 |
| C14 | **Make a new recovery plan** and the **Reset** icon behave as described | Beat 4 |
| C15 | **Runways and gates** shows runway tiles such as R1 on the Map view, and the number of runways at MDW | Beat 4 |
| C16 | No-go wording: "No recovery plan passes", "No legal recovery plan", "Nothing is legal", "Rules that block every plan", "Closest plan", "Nothing to approve." | Beat 4 |
| C17 | The **I've taken this case** button is absent in this design | Beat 4 |
| C18 | The Evidence tab shows the rows above with commit, mode and seed, and matches the file | Beat 5 |

## If something goes wrong on stage

See `runbook.md`, sections "If a visual fails: the 30-second plan" and "If something fails on stage". Never invent a number.
