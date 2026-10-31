# Likely judge questions, with short honest answers

Marks: `[RESULT]` is a number from a rules-only evaluation run that is being regenerated after a rule fix (crew duty and gate notice). Read it from `apps/api/eval_results/latest_off_none.md` once it is regenerated, copy it exactly, and say its commit, mode and seed. `[LIVE RESULT]` needs a model run that has not finished. Do not say any of these before the value is in the file.

Dataset counts are fixed and safe to say: the eligible rows number 358,774, and they match the organisers' filtered file exactly. They come from the full Kaggle file of 5,819,079 rows, with October left out (17,351 eligible rows dropped, because its airport codes are numeric).

---

## 1. Where does this fail, and how would your user know?

It fails in four ways. Each one is shown on screen.

- **Nothing is legal.** Every plan breaks a rule. The screen says "No-go: nothing is legal", names the rules that block every plan, shows the closest plan and what would have to change. The manager clicks "I've taken this case", and that is logged. The no-go rate is `[RESULT]`.
- **The system cannot decide.** Data is missing or a part failed. The screen says "No-go: system fault" and says not to read it as an unrecoverable flight. It is kept apart from the first kind.
- **The model fails.** A timeout, an unreadable answer, a plan that was never offered, or a missing recording. The run falls back to the rules. The screen says the fallback chose and lists the fault. A model-off run is never shown as a clean fallback.
- **The airport changed after the manager looked.** Sign-off runs every rule again and refuses.

It also fails where the screen cannot show it. Our rules are a subset of real ATC procedure, and the limits are synthetic. A real hazard that we do not model would not appear. We say this in the limits.

## 2. Do the agents add value?

Unproven. `[LIVE RESULT]`. The test is the agents against the rule-based fallback on the same held-out flights, and the number is not available yet. We will report it even if the agents add nothing. Today's evidence supports the gate, not the agents.

## 3. Is the no-go rate a property of the system?

No. It depends strongly on our synthetic settings. When one setting, `p_next_leg_hard` (how often the next leg is hard-limited), moves between the values we tried, the no-go rate moves from `[RESULT]` to `[RESULT]`. In the last run the other settings we moved changed it little. Check that again in the regenerated file. So the rate describes our generator, not real operations. Do not quote it as how often real flights are stuck.

## 4. Is the answer stable?

No. Across synthetic seeds for the same flight, `[RESULT]` of flights flip between a plan and a no-go. The operational fields are synthetic, and a different draw changes what is legal. The real fields do not change. This says the outcome is sensitive to fields we invented.

## 5. Do the flights contain real trade-offs?

Few do. In the first generator, the planned gate was always clear, so the chosen plan was never worse on any cost than the others, and there was nothing to trade off. Before any model ran, we added a synthetic gate conflict to a fixed share of flights. The before-and-after is in `apps/api/eval_results/generator_change_before_after.md` (those figures are from older commits; check them against a fresh run). On the rules-only sample, the share of deals where the pick is no worse than every legal plan on every cost is `[RESULT]`. We have not measured it on the frozen set `[LIVE RESULT]`. Where there is no trade-off, a stable pick is not evidence of robustness.

## 6. A simple rule of thumb also breaks no rules. So what do the agents add?

That is the right challenge. The rule of thumb breaks no rules because it consults our rules first, so zero violations is by construction. The safety comes from the rule gate, not from the agents. What the agents might add is a better choice among legal plans, using free-text notes the code cannot read. The rule of thumb picks the same plan as our fallback on `[RESULT]` of deals. The agents' own value is `[LIVE RESULT]`.

## 7. Are the limits real?

No. The wake, runway, taxiway, gate, fuel and crew limits are the organisers' workbook values. They are synthetic planning limits, not regulations. The screen labels them "Challenge workbook limit". A few values are our own assumptions (for example a 15-minute gate buffer and the approach speeds used to turn miles into minutes), and some are shaped on a regulation but are our policy. Each shows its status on screen.

## 8. What did you change from the organisers' limits?

The turn cap. The brief lets the fallback decide after 3 turns with no agreement. We stop at 2, which is stricter. We read the other limits from the workbook into `rule_values.py` and `airport_limits.py`. Where the workbook was silent we added a labelled assumption, such as treating "super behind super" as the 3-mile default, and not modelling a small aircraft behind a B757. These are listed in the README.

## 9. Is first-come-first-served a fair comparison?

No, it is an uncoordinated comparison. It shows what happens when nobody checks the other domains. It is not what a good duty manager would do. For that we also run a rule of thumb that consults the rules (question 6). The first-come-first-served plans broke a rule on `[RESULT]` of flights. Read that as "uncoordinated plans are unsafe", not as "we beat a human".

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

A single edit is caught. A full rewrite is not, unless the head is compared with a copy kept elsewhere. We record the head on the sign-off, so you can compare. The "Tamper with log" button shows a caught edit on a copy.

## 16. Why 2015 US data?

The brief requires the organisers' file. Our eligible rows match their filtered file exactly. It has no cancelled or diverted flights, so the worst disruptions are missing. Results are simulated outcomes, not measured savings. Real arrival delay is shown as context only and is not claimed as a saving.

## 17. How many flights did you test, and is that enough?

The rules-only run uses a sample of `[RESULT]` flights, half weather and half late-aircraft, so pooled rates do not describe the real mix, where late aircraft is the large majority. A zero rate on a sample still allows a small true rate, up to `[RESULT]` at 95% confidence (see the Limits section of the file). Safety rests on the gate, not on the sample.

## 18. Has anyone but the author checked the rules?

An independent verifier found a defect in the crew-duty and gate-notice rules, which is why the numbers are being regenerated. As of the last run, the hand-worked scenarios had not been checked by someone who did not write them. We say so rather than claim they were.

## 19. Is this novel?

We do not claim it is. We have not completed a check against collaborative decision making and ground-delay slot substitution. The contribution we claim is the evaluation and the visible failure.

---

## Notes for the team (not for the stage)

- Do not quote numbers from the earlier `latest_off_none` run. Wait for the regenerated file.
- The before-and-after file uses the old name "NO_DEAL" for what the product now calls "no-go".
- "Frozen" results (`--split frozen`) are quoted once, from the first live run, and never replaced.
