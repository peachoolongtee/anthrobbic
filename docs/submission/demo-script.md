# Demo script: 3 minutes, five beats, on Live, new dashboard design

Autonomous SG 2026, Airbus track, Challenge 2. Read aloud at 150 words a minute. The spoken text is 295 words in total on the two-turn path (about 118 seconds of speech), which leaves about 62 seconds for the clicks. You speak over the wait for the live run. Each beat has its own word budget in its heading. Rehearse once with a timer.

Every click and screen text below was checked on the integrated design at 1280x720, on the real API with the real dataset, the saved WN4832 answers, and every non-local request aborted, with Live faked by relabelling a saved run. A real Live answer differs, which is why the wording depends on the screen. The results are at the end.

## Marks used in this file

- Every number in the spoken text is copied from `apps/api/eval_results/`. The table at the end names each file and row.

## Before you go on stage

Follow `runbook.md` first. Then:

1. The intro (a plane crossing the screen) plays once per browser tab. Open `http://localhost:3000` in the tab you will use, click anywhere to skip it, and leave the tab open on the overview. Landing and intro are not part of the 3 minutes.
2. The demo runs on **Live**: the flights page starts in Live, built as the runbook says, and runs only the flight you pick. One run-through makes up to 6 model calls, about $0.15. Check the network. Restart the API before each rehearsal: a used approval is refused until then.
3. Know where WN4832 is. In the overview's **Arrivals** list (scroll down past the globe), look for the row "DCA → MDW" with "WN4832" under it. The list shows 50 flights, those with saved answers first, then by scheduled arrival, and it scrolls inside its own panel. WN4832 is row 16, in the left column, so scroll the list about two rows. Do not click another flight first: each one you pick in Live spends up to 6 calls.

**Stage rule.** If the Live run has not come back after 40 seconds (the strip counts them), or it shows faults, click **Recorded** and say "the live call did not come back, so this is a saved run". Then use the recorded wording in beat 2.

**In Live, do not** click another flight, a runway, a gate, a preset, **Inject**, **Reset every change** or **Make a new recovery plan**. Each one is a new run. The clicks below keep to those that spend nothing until **Model off** in beat 4.

## Beat 1. The user (0:00 to 0:22). Budget 55 words, spoken text 52

**Screen:** the overview. The globe is headed "Demo flights", with the **Arrivals** list under it.

**Click:** in the **Arrivals** list, scroll the list about two rows and click the row "DCA → MDW" (WN4832), as you say "I pick". It opens the flights page, and the strip shows "Agents working, live" with a seconds count. It takes about 15 to 20 seconds, and the rest of beat 1 and the opening of beat 2 fill that.

**Say:**

> A flight is late. Today a duty manager phones air traffic control, the crew and the ramp, one by one, while the delay spreads. These are delayed arrivals from the real 2015 US record. I pick WN4832, Washington National to Chicago Midway. This runs live, right now, so nothing here is rehearsed.

## Beat 2. The negotiation (0:22 to 1:00). Budget 100 words, spoken text 64

**Screen:** the flights page. Flights list on the left, the map in the middle, the plan and sign-off on the right. Across the top of the map is the agent strip with ATC, Pilot and Ground.

**Say, while it runs:**

> Three agents negotiate: ATC, the pilot and the ground crew. Code first removes every plan that breaks a rule. Each agent reads a synthetic note about its own side.

**When it comes back,** point at the strip and the route. Never state a count or a gate in advance: they differ between runs. Choose by what the strip shows.

**Two turns** (a count like "4 › 12"). Click **Negotiation**, scroll to **Turn 2**, and read who is under "Withdrew its objection to". Click the **X**. Name only those agents.

> Turn one: no shared plan. Turn two: the prompt invites them to withdraw soft objections, so this is not persuasion. [Agents the screen names] withdrew. A shared plan appears. Code still decides what is legal.

**One turn** (a single count on each agent):

> They agreed straight away, which is what happened on all 14 unseen flights. Code still decides what is legal.

**Recorded wording,** only after the stage rule, on the saved WN4832 run:

> Turn one: no shared plan. The pilot's firm note says no direct routing. ATC's soft note says avoid runway R3. Turn two: the prompt invites them to withdraw soft objections, so this is not persuasion. ATC and Ground withdraw. The pilot holds. A shared plan appears.

**If Recorded says "Rule-based fallback".** The saved answers did not load, the right panel lists "No recording: ATC, Pilot, Ground", and the agent strip shows × for each agent. Say this instead, and say nothing about agents agreeing:

> Three agents are meant to negotiate here. This time they did not: the saved model answers did not load. The rules alone chose this plan, and the screen says so. Code removes every illegal plan first, so even a fallback plan has passed every rule.

The view shows each agent's accepted count, reasons in plain words, objections withdrawn, and the model's own note, labelled **Unverified**. The private synthetic notes themselves are not shown. Say only what the screen shows.

## Beat 3. The trust (1:00 to 1:35). Budget 87 words, spoken text 50

This runs on the live plan. Name no gate: read what the screen names.

**Click, in order:**

1. On the right panel, point at the small letter marks next to the plan facts, and the line under them: "R real, D derived from the file, S synthetic." Hovering one shows the word.
2. Click the **Try to break it** heading to open the card, which stays open for the rest of the talk. Click **Late change**. This blocks the plan's gate on the server while the screen keeps the old plan, and spends nothing.
3. In the **Sign off** panel, the two boxes sit directly above **Approve**, with no scrolling. Tick **I approve these decisions** and **Send these requests**, then click **Approve**.
4. A red alert appears: "This plan is out of date. Sign-off refused: the airport changed after you looked." In the Sign off panel the refusal reads "Refused: the airport changed after you looked", and it names what changed. Point at what it names. Do not click **Make a new recovery plan**: in Live that is a new run.
5. In the **Try to break it** card, click **Tamper log**. It opens the **Log** view. Point at "Tampered copy: detected" and "First bad entry". Click the **X** to close the drawer.

**Say:**

> Every field is marked real, derived or synthetic.
>
> I block this plan's gate after the manager looked, then approve. Sign-off runs every rule again on the current airport, and refuses. Nothing is issued.
>
> Every message goes into a hash-chained log. I edit a copy: caught, with the first bad entry.

## Beat 4. The failure (1:35 to 2:10). Budget 87 words, spoken text 57

No model calls and no waiting: each click below answers at once.

**Click, in order:**

1. Click **Model off** at the top right, first. The strip reads "The agents did not run".
2. Click **Reset every change** (the circular arrow at the top of the **Try to break it** card). It clears the blocked gate.
3. On the diagram in the card (keep **Map** selected, not **Airport 3D**), click **R1**, then **R3**. R2 at MDW is already closed in this scenario and cannot be clicked. R1 gives a rules-only plan. R3 gives the no-go.
4. Point at the right panel: "No-go" and "No-go: no recovery plan passes". Click **Plan** at the bottom and point at "No legal recovery plan", "No-go: nothing is legal", "Rules that block every plan" and "Closest plan". Click the **X**.
5. Point at the Sign off panel: "Nothing to approve." Click **I've taken this case**. It reads "Logged: this case is with the duty manager. Nothing was approved or requested."

**Say:**

> Now I close every runway. No model is needed for this: when nothing is legal, code says so. It names the rules that block every plan, and shows the closest one. This is a no-go. No-go means no plan was cleared and a person decides. It does not mean the flight should not land. Nothing was approved.

## Beat 5. The numbers (2:10 to 2:45). Budget 87 words, spoken text 72

**Click:** the **Evidence** tab at the bottom. It opens on the numbers, with no scrolling: **Rules only** on the left, **With the model: tuned and unseen flights** on the right, each set with its class, commit, mode and seed. Point at those for the 3150 and the 0. The 14, the turn count and the 9 of 14 are in **Full results: with the model**, further down; scroll there only if asked. "Where we differ from the challenge workbook" and the limits are closed sections under them, then the full tables. The tab reads the evaluation through the API, so check that it shows the same commit as the file.

**Say:**

> Rules only, 5000 flights, model off. First-come-first-served broke a rule on 3150 of 5000. Our final plans: 0 of 3919. A rule of thumb that checks the rules also breaks none, so the gate does the safety work. Live, 20 unseen flights: 14 reached the agents, all 14 agreed on turn 1, and 9 of 14 cost more than the fallback. Agents are not shown to beat the rules. Simulated, not savings.

The 15 seconds to 3:00 are spare, for a live call at the slow end.

## Where the spoken numbers come from

Copied exactly from `apps/api/eval_results/`. Do not round or recompute. Say the mode aloud; the Evidence tab shows the commit, mode and seed.

Rules only: `latest_off_none.md`, commit `e3fe575`, mode `off`, seed 0.

| Said | Row in the file | Value |
|---|---|---|
| 5000 flights | "Rows evaluated" | 5000 rows |
| First-come-first-served broke a rule | "first_come_first_served: packages breaking a rule" | 3150/5000 (63.0%) |
| Our final plans broke a rule | "Final packages breaking a rule" | 0/3919 (0.0%) |
| Rule of thumb breaks none | "human_heuristic: packages breaking a rule" | 0/3919 (0.0%), zero by construction |

Live: the first frozen run, run-0002, `eval_live_frozen_seed0_2026-10-31T055759Z.md`, commit `db54b25`, mode `live`, seed 0, class unseen. The second frozen run is not used for the headline.

| Said | Row in the file | Value |
|---|---|---|
| 20 unseen flights | "Rows evaluated" | 20 rows |
| 14 reached the agents | "Rows a model answered, all rows" | 14/20 (70.0%) |
| All 14 agreed | "Convergence rate, all rows" | 14/14 (100.0%) |
| On turn 1 | "Turns used" | 1 turns, the mean over 14, so every one of them |
| 9 of 14 cost more than the fallback | "Consensus costs more than fallback" | 9/14 (64.3%), interval 38.8-83.7% |

The other 6 of the 20 are no-go, nothing legal (6/20, 30.0%). The cost comparison prices both plans with the same weights, so the value of the notes is not priced. Say so if asked.

The denominators differ: 5000 rows are sampled, and 3919 are rows with a plan. Say which one you mean. Rules-only and live rows are different evidence classes, so never put them in one comparison.

Also read these before the talk, because judges ask: "NO_GO NOTHING_LEGAL rate, all rows", "NO_GO rate, all rows, p_next_leg_hard=..." (the lowest and highest setting), "Outcome flips between deal and NO_GO across synthetic seeds", "Pick is no worse than every legal package on every cost component", "Fallback picks the same package as human_heuristic" and "Binding: GND-GATE-NOTICE eliminates packages in these rows".

## What was checked on screen

| # | Checked | Result |
|---|---|---|
| C1 | The intro plays once per tab and a click skips it | Yes |
| C2 | Toggle reads Model off, Recorded, Live; a flight with saved answers opens in Recorded | Yes |
| C3 | WN4832 DCA to MDW is in the overview **Arrivals** list | Yes, row 16 of 50, in the panel's own scroll; row 4 of 200 on the flights page |
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
| C19 | With the Live setting on: no run until a flight is picked, one POST for one pick, from a row or the overview, in the production build and under dev double effects; no "Recorded" tag; working strip and panel; faults shown when refused or failed; **Recorded** recovers | Yes, on a counted fake Live response, with no model call |
| C20 | Beats 3 and 4 on a Live plan, with **Model off** first | Yes, on the fake: no further Live POST, each off run under 150 ms |
| C21 | Live on WN4832 for real | Run once by the coordinator: 6 calls, 2 turns, 0 faults. Not rerun for these checks |

## If something goes wrong on stage

See `runbook.md`, sections "If a visual fails: the 30-second plan" and "If something fails on stage". Never invent a number.
