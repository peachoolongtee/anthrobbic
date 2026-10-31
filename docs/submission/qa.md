# Likely judge questions, with short honest answers

Every figure here comes from `apps/api/eval_results/`. Rules-only figures: the mode off run at commit `e3fe575`, seed 0, 5000 flights (`latest_off_none.md`). Live figures: the first frozen run, run-0002, at commit `db54b25`, seed 0, 20 flights, class unseen (`eval_live_frozen_seed0_2026-10-31T055759Z.md`). Say the commit, mode and seed, and never compare the two classes.

Dataset counts are fixed and safe to say: the eligible rows number 358,774, and they match the organisers' filtered file exactly. They come from the full Kaggle file of 5,819,079 rows, with October left out (17,351 eligible rows dropped, because its airport codes are numeric).

---

## 1. Where does this fail, and how would your user know?

It fails in four ways. Each one is shown on screen.

- **Nothing is legal.** Every plan breaks a rule. The screen says "No-go: nothing is legal", names the rules that block every plan, shows the closest plan and what would have to change. A person decides what happens next, and the "I've taken this case" button logs that. The rate of this no-go is 1081/5000 (21.6%).
- **The system cannot decide.** Data is missing or a part failed. The screen says "No-go: system fault" and says not to read it as an unrecoverable flight. It is kept apart from the first kind.
- **The model fails.** A timeout, an unreadable answer, a plan that was never offered, or a missing recording. The run falls back to the rules. The screen says the fallback chose and lists the fault. A model-off run is never shown as a clean fallback.
- **The airport changed after the manager looked.** Sign-off runs every rule again and refuses.

It also fails where the screen cannot show it. Our rules are a subset of real ATC procedure, and the limits are synthetic. A real hazard that we do not model would not appear. We say this in the limits.

## 2. Do the agents add value?

Not shown. On 20 held-out flights a model answered on 14, and all 14 agreed on turn 1. The agents' plan cost more than the rule-based fallback's on 9/14 (64.3%, interval 38.8-83.7%) and was the same plan on 5/14 (35.7%). Cost does not price the notes (question 20), so this does not show them worse either. The agents are not shown to beat the rules. The evidence supports the gate: on the same 20 flights, a model's unguarded pick broke a rule on 7/20 (35.0%), and guarded plans on 0/14 (0.0%, interval 0.0-21.5%).

## 3. Is the no-go rate a property of the system?

No. It depends strongly on our synthetic settings. When one setting, `p_next_leg_hard` (how often the next leg is hard-limited), moves between the values we tried, the no-go rate moves from 27/500 (5.4%) to 186/500 (37.2%), on a 500-flight sample. The other settings we moved changed it little. So the rate describes our generator, not real operations. Do not quote it as how often real flights are stuck.

## 4. Is the answer stable?

No. Across synthetic seeds for the same flight, 2095/5000 (41.9%) of flights flip between a plan and a no-go. The operational fields are synthetic, and a different draw changes what is legal. The real fields do not change. This says the outcome is sensitive to fields we invented.

## 5. Do the flights contain real trade-offs?

Few do. In the first generator, the planned gate was always clear, so the chosen plan was never worse on any cost than the others, and there was nothing to trade off. Before any model ran, we added a synthetic gate conflict to a fixed share of flights. The before-and-after is in `apps/api/eval_results/generator_change_before_after.md` (those figures are from older commits; check them against a fresh run). On the rules-only sample, the share of deals where the pick is no worse than every legal plan on every cost is 3656/3919 (93.3%). On the frozen run's flights it is 14/14 (100.0%, interval 78.5-100.0%). Where there is no trade-off, a stable pick is not evidence of robustness.

## 6. A simple rule of thumb also breaks no rules. So what do the agents add?

That is the right challenge. The rule of thumb breaks no rules because it consults our rules first, so zero violations is by construction. The safety comes from the rule gate, not from the agents. What the agents might add is a better choice among legal plans, using free-text notes the code cannot read. The rule of thumb picks the same plan as our fallback on 2963/3919 (75.6%) of deals. The agents are not shown to add that better choice (question 2).

## 7. Are the limits real?

No. The wake, runway, taxiway, gate, fuel and crew limits are the organisers' workbook values. They are synthetic planning limits, not regulations. The screen labels them "Challenge workbook limit". A few values are our own assumptions (for example a 15-minute gate buffer and the approach speeds used to turn miles into minutes), and some are shaped on a regulation but are our policy. Each shows its status on screen.

## 8. What did you change from the organisers' limits?

The turn cap. The brief lets the fallback decide after 3 turns with no agreement. We stop at 2, so we fall back one turn earlier than the brief allows. We read the other limits from the workbook into `rule_values.py` and `airport_limits.py`. Where the workbook was silent we added a labelled assumption, such as treating "super behind super" as the 3-mile default, and not modelling a small aircraft behind a B757. These are listed in the README.

## 9. Is first-come-first-served a fair comparison?

No, it is an uncoordinated comparison. It shows what happens when nobody checks the other domains. It is not what a good duty manager would do. For that we also run a rule of thumb that consults the rules (question 6). The first-come-first-served plans broke a rule on 3150/5000 (63.0%) of flights. Read that as "uncoordinated plans are unsafe", not as "we beat a human".

## 10. Is fuel realistic?

No. Fuel on board is synthetic. By the generator's design it is usually above the workbook's 45-minute default, so most flights are not fuel-limited. A fuel rule that rarely binds on easy flights tells you little about hard ones. The fuel rule is defended by tests that inject a violation and check it is caught.

## 11. You close a runway. Does capacity drop?

No. Closing a runway removes it from use, but the airport's arrivals-per-hour limit from the workbook stays as it is. The cap is set per airport, and closing a runway does not lower it. The demo does not model reduced airport capacity, so do not read it that way.

## 12. Does the model make safety decisions?

No. Agents propose. Code removes illegal plans before they see them, checks the agreed plan again, and sign-off checks it a third time on the current state. An agent that names a plan it was not offered causes a fault, not a deal. Agents choose reason codes, and the card text is written by code, not by the model.

## 13. What if the agents all agree on something unsafe?

A test covers it with scripted agents that agree to anything, and the rule gate keeps the unsafe plan out. The same test disables the rule and checks the test notices. This is a test class, not a sample.

## 14. Is anything executed?

No. Approving is not executing. The screen says "Nothing has been executed." The airline decides the gate. The arrival slot and flight plan are requests that ATC grants or refuses. The pilot in command keeps fuel and safety authority. The approver in the demo is "Duty manager (demo, not authenticated)". There is no sign-in.

## 15. Can the log be forged?

A single edit is caught. A full rewrite is not, unless the head is compared with a copy kept elsewhere. We record the head on the sign-off, so you can compare. The "Tamper log" button shows a caught edit on a copy.

## 16. Why 2015 US data?

The brief requires the organisers' file. Our eligible rows match their filtered file exactly. It has no cancelled or diverted flights, so the worst disruptions are missing. Results are simulated outcomes, not measured savings. Real arrival delay is shown as context only and is not claimed as a saving.

## 17. How many flights did you test, and is that enough?

The rules-only run uses a sample of 5000 flights, half weather and half late-aircraft, so pooled rates do not describe the real mix, where late aircraft is the large majority. A zero rate on a sample still allows a small true rate, up to 0.1% for 0/3919 at 95% confidence, and up to 21.5% for the 0/14 in the live run. Safety rests on the gate, not on the sample.

## 18. Has anyone but the author checked the rules?

An independent verifier found a defect in the crew-duty and gate-notice rules (see question 25), which is why the numbers were regenerated. As of the last run, the hand-worked scenarios had not been checked by someone who did not write them. We say so rather than claim they were.

## 19. Is this novel?

We do not claim it is. We have not completed a check against collaborative decision making and ground-delay slot substitution. The contribution we claim is the evaluation and the visible failure.

## 20. The agents' plan costs more than the fallback's. Does that mean they are worse?

Not necessarily, and we cannot show either way with cost. The cost model prices delay, fuel margin, connection passengers and ground overtime. The agents' extra cost comes from the notes: free-text preferences, such as a crew wanting one gate or the ramp wanting to avoid a runway, which cost does not price. So an agent pick that costs more than the rule-based pick may have followed a note, and one that costs the same may have ignored it. That means we cannot show, with our cost numbers, that the agents beat the rules. On the held-out flights the agents' plan cost more on 9/14 (64.3%, interval 38.8-83.7%). We do not know whether those picks followed a note to some real benefit, so the agents are not shown to beat the rules (question 2).

## 21. Do soft notes block agreement? Can the shortlist hide good plans?

Yes to both, and the demo flight shows the first. On turn 1 a soft note acts like a veto: an agent leaves a plan out of its accepted list, and if the three accepted lists share no plan, there is no deal on turn 1. The turn-2 prompt tells each agent it may take back a soft objection if that opens a plan the others can accept, and that anything a firm note rules out stays out. So a turn-2 agreement partly reflects the prompt inviting it, not agents being persuaded. That is the saved WN4832 case. In the first frozen run it did not arise: all 14 agreed on turn 1.

On the shortlist: when more than 12 plans are legal, the agents see only 12 of them (`SHORTLIST_MAX` in `protocol.py`). The 12 always include the cheapest overall and the cheapest for each of the three domains, and the rest are chosen to cover different gates, runways and actions. A cheap legal plan outside the 12, or one that a note would have favoured, is never offered. Agents cannot ask for it. Code decides what is legal, and the agents choose among what is offered.

## 22. Does the gate-notice rule do anything on real data?

Rarely, and perhaps never on real fields. In the rules-only run it eliminated plans in 1/5000 (0.0%) of rows (row "Binding: GND-GATE-NOTICE eliminates packages in these rows"), and the file notes that this partly describes our synthetic generator. The gate-change that triggers it is itself synthetic. So the sample does not defend this rule. An injected test case does, and the file lists it as defended (row "Rule GND-GATE-NOTICE: DEFENDED"). A rule that rarely binds on easy data tells you little about hard data.

## 23. Is the map real? Is the 3D airport real?

No. The route on the map is a great-circle curve between two airports, and the aircraft circling a hold on it is drawn for effect, not tracked. The basemap is bundled with the app and needs no network. The 3D airport is a drawing of synthetic runways and gates, not the real layout of the airport. Both are illustrative. The 3D view uses this run's runway and gate IDs, and their positions are not real. The rules read the plan data, never the pictures.

## 24. Why two turns?

Turn 1 is each agent answering alone. Turn 2 happens only when turn 1 gave no plan all three accept, and then each agent sees which plans code removed and a general reason, with no private values. The organisers' brief lets the fallback decide after 3 turns, so we fall back one turn earlier than the brief allows, and it caps model calls at six a run (three agents, two turns). The cap is set in Python and the model cannot change it. We did not measure whether a third turn would reach more agreements, so we do not claim two is the best number.

## 25. Give an honest example of verification catching something.

The crew-duty and gate-notice rules measured time across a time-zone difference. The crew report time and the late-aircraft decision time came from the origin airport's scheduled departure, while slots and taxi-in are on the destination's clock, so the two sides of the sum were on different clocks. The independent verification caught it. The fix (commit `83d7a7e`) moves both onto the destination clock, using the offset the arrival arithmetic already derives from the row, and adds a test file for the clocks. Because it changed what is legal, we regenerated the rules-only results and do not quote the older run. We tell you this because it is how we work: a check by someone other than the author found a real defect, we fixed it, and then we re-measured. It does not show there are no more.

## 26. Why can the live run differ from the recording?

The demo runs on Live, and falls back to the saved run if the call does not come back. A live run asks the model again. Recorded replays what it answered once. In the one live test we measured on WN4832 (n=1), the counts were ATC 4 then 12, Pilot 8 then 8, Ground 7 then 7, and the plan was gate G2, runway R3, hold, landing 21:15. The recording has Ground 7 then 12 and gate G1. We make no claim about how often they differ. In both, code decides what is legal, and Live is available only when the API is started with `ALLOW_LIVE=1`.

---

## Notes for the team (not for the stage)

- Quote only the runs named at the top of this file. Runs from before the fix in question 25 are out of date.
- The before-and-after file uses the old name "NO_DEAL" for what the product now calls "no-go".
- "Frozen" results (`--split frozen`) are quoted once, from the first live run, and never replaced.
