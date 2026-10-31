# Evaluation results

- Commit: `e3fe575472a09012668bab0a018a6d995ee7b5c7`
- Mode: `off`; split: `none`; seed: 0; sample size: 5000
- Generated: 2026-10-31T05:49:45+00:00
- Time: 231.4 s with 10 worker(s), 21.6 rows/s

Panels hold one evidence class each. Do not compare across them.

## Deterministic core over the sample, mode off [class: rules_only]

Commit `e3fe575472a0`, mode `off`, seed 0, sample size 5000, 2026-10-31T05:49:45+00:00.

| Measure | Compared against | Class | Value | 95% Wilson | n | Note |
|---|---|---|---|---|---|---|
| Rows evaluated | reported as measured | rules_only | 5000 rows |  | 5000 | stratified 50/50 by cause |
| Rows that errored | reported as measured | rules_only | 0/5000 (0.0%) | 0.0-0.1% | 5000 |  |
| Deal rate, all rows | usefulness beside safety | rules_only | 3919/5000 (78.4%) | 77.2-79.5% | 5000 |  |
| NO_GO NOTHING_LEGAL rate, all rows | usefulness beside safety | rules_only | 1081/5000 (21.6%) | 20.5-22.8% | 5000 |  |
| NO_GO SYSTEM_FAULT rate, all rows | usefulness beside safety | rules_only | 0/5000 (0.0%) | 0.0-0.1% | 5000 |  |
| Deal rate, weather | usefulness beside safety | rules_only | 1897/2500 (75.9%) | 74.2-77.5% | 2500 |  |
| NO_GO NOTHING_LEGAL rate, weather | usefulness beside safety | rules_only | 603/2500 (24.1%) | 22.5-25.8% | 2500 |  |
| NO_GO SYSTEM_FAULT rate, weather | usefulness beside safety | rules_only | 0/2500 (0.0%) | 0.0-0.2% | 2500 |  |
| Deal rate, late_aircraft | usefulness beside safety | rules_only | 2022/2500 (80.9%) | 79.3-82.4% | 2500 |  |
| NO_GO NOTHING_LEGAL rate, late_aircraft | usefulness beside safety | rules_only | 478/2500 (19.1%) | 17.6-20.7% | 2500 |  |
| NO_GO SYSTEM_FAULT rate, late_aircraft | usefulness beside safety | rules_only | 0/2500 (0.0%) | 0.0-0.2% | 2500 |  |
| Fallback rate (LLM off) | reported as measured | rules_only | 3919/5000 (78.4%) | 77.2-79.5% | 5000 | every deal in mode off is a fallback by construction, so this is the deal rate and says nothing about the agents |
| Mode off decisions differing from fallback.decide | reported as measured | rules_only | 0 rows |  | 5000 |  |
| Context: simulated arrival delay, inbound data set the window | not a saving: simulated window versus real outcome | rules_only | 42.72 min |  | 961 | not a saving: simulated window versus real outcome |
| Context: real ARRIVAL_DELAY, inbound data set the window | not a saving: simulated window versus real outcome | rules_only | 49.15 min |  | 961 | not a saving: simulated window versus real outcome |
| Context: simulated arrival delay, disruption floor set the window | not a saving: simulated window versus real outcome | rules_only | 18.49 min |  | 2958 | not a saving: simulated window versus real outcome |
| Context: real ARRIVAL_DELAY, disruption floor set the window | not a saving: simulated window versus real outcome | rules_only | 107.71 min |  | 2958 | not a saving: simulated window versus real outcome |
| Context: simulated arrival delay, window basis not available | not a saving: simulated window versus real outcome | rules_only | NOT_REACHED |  |  | no row with window basis not available |
| Context: real ARRIVAL_DELAY, window basis not available | not a saving: simulated window versus real outcome | rules_only | NOT_REACHED |  |  | no row with window basis not available |
| Delay past the scenario's earliest arrival, fallback | the baselines below | rules_only | 1.6 min |  | 3919 |  |
| Fuel-reserve margin, fallback | the baselines below | rules_only | 2488.33 kg |  | 3919 |  |
| Connection passengers at risk, fallback | the baselines below | rules_only | 8.46 pax |  | 3919 |  |
| Ground overtime, fallback | the baselines below | rules_only | 2.94 min |  | 3919 |  |
| first_come_first_served: rows where it found no package | no coordination: first come first served, nearest gate | rules_only | 0/5000 (0.0%) | 0.0-0.1% | 5000 |  |
| first_come_first_served: packages breaking a rule | no coordination: first come first served, nearest gate | rules_only | 3150/5000 (63.0%) | 61.7-64.3% | 5000 |  |
| first_come_first_served: packages the harm check calls harmful | no coordination: first come first served, nearest gate | rules_only | 2800/5000 (56.0%) | 54.6-57.4% | 5000 |  |
| first_come_first_served: breaks ATC-RWY-CLOSED | no coordination: first come first served, nearest gate | rules_only | 592/5000 (11.8%) | 11.0-12.8% | 5000 |  |
| first_come_first_served: breaks ATC-RWY-THROUGHPUT | no coordination: first come first served, nearest gate | rules_only | 96/5000 (1.9%) | 1.6-2.3% | 5000 |  |
| first_come_first_served: breaks ATC-TWY-CLOSED | no coordination: first come first served, nearest gate | rules_only | 502/5000 (10.0%) | 9.2-10.9% | 5000 |  |
| first_come_first_served: breaks ATC-WAKE-SEP | no coordination: first come first served, nearest gate | rules_only | 1522/5000 (30.4%) | 29.2-31.7% | 5000 |  |
| first_come_first_served: breaks GND-GATE-OVERLAP | no coordination: first come first served, nearest gate | rules_only | 687/5000 (13.7%) | 12.8-14.7% | 5000 |  |
| first_come_first_served: breaks GND-TURNAROUND | no coordination: first come first served, nearest gate | rules_only | 775/5000 (15.5%) | 14.5-16.5% | 5000 |  |
| first_come_first_served: breaks PLT-CREW-DUTY | no coordination: first come first served, nearest gate | rules_only | 94/5000 (1.9%) | 1.5-2.3% | 5000 |  |
| first_come_first_served: breaks PLT-FUEL-POLICY | no coordination: first come first served, nearest gate | rules_only | 100/5000 (2.0%) | 1.6-2.4% | 5000 |  |
| Fallback picks the same package as first_come_first_served | no coordination: first come first served, nearest gate | rules_only | 1126/3919 (28.7%) | 27.3-30.2% | 3919 | how much the cost ranking adds over this baseline |
| Delay past the scenario's earliest arrival, first_come_first_served, all its packages | no coordination: first come first served, nearest gate | rules_only | 0 min |  | 5000 | an illegal low delay is not a win |
| Delay past the scenario's earliest arrival, first_come_first_served, only its legal packages | no coordination: first come first served, nearest gate | rules_only | 0 min |  | 1850 |  |
| Delay past the scenario's earliest arrival, fallback minus first_come_first_served, paired on the same window | no coordination: first come first served, nearest gate | rules_only | 0 min |  | 1850 | rows where both have a package and the baseline's is legal |
| Fuel-reserve margin, first_come_first_served, all its packages | no coordination: first come first served, nearest gate | rules_only | 2435.64 kg |  | 5000 | an illegal low delay is not a win |
| Fuel-reserve margin, first_come_first_served, only its legal packages | no coordination: first come first served, nearest gate | rules_only | 2665.3 kg |  | 1850 |  |
| Fuel-reserve margin, fallback minus first_come_first_served, paired on the same window | no coordination: first come first served, nearest gate | rules_only | 0 kg |  | 1850 | rows where both have a package and the baseline's is legal |
| Connection passengers at risk, first_come_first_served, all its packages | no coordination: first come first served, nearest gate | rules_only | 8.01 pax |  | 5000 | an illegal low delay is not a win |
| Connection passengers at risk, first_come_first_served, only its legal packages | no coordination: first come first served, nearest gate | rules_only | 7.77 pax |  | 1850 |  |
| Connection passengers at risk, fallback minus first_come_first_served, paired on the same window | no coordination: first come first served, nearest gate | rules_only | 0 pax |  | 1850 | rows where both have a package and the baseline's is legal |
| Ground overtime, first_come_first_served, all its packages | no coordination: first come first served, nearest gate | rules_only | 2.75 min |  | 5000 | an illegal low delay is not a win |
| Ground overtime, first_come_first_served, only its legal packages | no coordination: first come first served, nearest gate | rules_only | 2.71 min |  | 1850 |  |
| Ground overtime, fallback minus first_come_first_served, paired on the same window | no coordination: first come first served, nearest gate | rules_only | 0 min |  | 1850 | rows where both have a package and the baseline's is legal |
| human_heuristic: rows where it found no package | sensible human heuristic | rules_only | 1081/5000 (21.6%) | 20.5-22.8% | 5000 |  |
| human_heuristic: packages breaking a rule | sensible human heuristic | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 | zero by construction: this baseline consults the rules |
| human_heuristic: packages the harm check calls harmful | sensible human heuristic | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Fallback picks the same package as human_heuristic | sensible human heuristic | rules_only | 2963/3919 (75.6%) | 74.2-76.9% | 3919 | how much the cost ranking adds over this baseline |
| Delay past the scenario's earliest arrival, human_heuristic, all its packages | sensible human heuristic | rules_only | 1.6 min |  | 3919 | an illegal low delay is not a win |
| Delay past the scenario's earliest arrival, human_heuristic, only its legal packages | sensible human heuristic | rules_only | 1.6 min |  | 3919 |  |
| Delay past the scenario's earliest arrival, fallback minus human_heuristic, paired on the same window | sensible human heuristic | rules_only | 0 min |  | 3919 | rows where both have a package and the baseline's is legal |
| Fuel-reserve margin, human_heuristic, all its packages | sensible human heuristic | rules_only | 2486.35 kg |  | 3919 | an illegal low delay is not a win |
| Fuel-reserve margin, human_heuristic, only its legal packages | sensible human heuristic | rules_only | 2486.35 kg |  | 3919 |  |
| Fuel-reserve margin, fallback minus human_heuristic, paired on the same window | sensible human heuristic | rules_only | 1.97 kg |  | 3919 | rows where both have a package and the baseline's is legal |
| Connection passengers at risk, human_heuristic, all its packages | sensible human heuristic | rules_only | 8.46 pax |  | 3919 | an illegal low delay is not a win |
| Connection passengers at risk, human_heuristic, only its legal packages | sensible human heuristic | rules_only | 8.46 pax |  | 3919 |  |
| Connection passengers at risk, fallback minus human_heuristic, paired on the same window | sensible human heuristic | rules_only | 0 pax |  | 3919 | rows where both have a package and the baseline's is legal |
| Ground overtime, human_heuristic, all its packages | sensible human heuristic | rules_only | 2.94 min |  | 3919 | an illegal low delay is not a win |
| Ground overtime, human_heuristic, only its legal packages | sensible human heuristic | rules_only | 2.94 min |  | 3919 |  |
| Ground overtime, fallback minus human_heuristic, paired on the same window | sensible human heuristic | rules_only | 0 min |  | 3919 | rows where both have a package and the baseline's is legal |
| Chosen package has zero soft cost | reported as measured | rules_only | 835/3919 (21.3%) | 20.1-22.6% | 3919 | under any positive weights this pick cannot be beaten |
| Pick is no worse than every legal package on every cost component | reported as measured | rules_only | 3656/3919 (93.3%) | 92.5-94.0% | 3919 | on these rows there is no trade-off, so weights cannot move the pick and a stable pick is not evidence of robustness |
| Legal packages per deal row | reported as measured | rules_only | 59.97 packages |  | 3919 |  |
| Final packages breaking a rule | must be zero: the gate | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Final packages the independent harm check calls harmful | harm.py, own logic | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| harm.py versus rules: harm_only | rules/ on the same final package | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| harm.py versus rules: rules_only | rules/ on the same final package | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| harm.py versus rules: harm_unknown | rules/ on the same final package | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| harm.py versus rules: rules_fail_closed_only | rules/ on the same final package | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Binding: ATC-WAKE-SEP eliminates packages in these rows | reported as measured | rules_only | 4438/5000 (88.8%) | 87.9-89.6% | 5000 | partly describes the synthetic generator; 319815 of 988361 packages, 126611 by this rule alone |
| Binding: ATC-RWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 1397/5000 (27.9%) | 26.7-29.2% | 5000 | partly describes the synthetic generator; 157840 of 988361 packages, 46054 by this rule alone |
| Binding: ATC-TWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 940/5000 (18.8%) | 17.7-19.9% | 5000 | partly describes the synthetic generator; 108250 of 988361 packages, 22653 by this rule alone |
| Binding: ATC-RWY-THROUGHPUT eliminates packages in these rows | reported as measured | rules_only | 135/5000 (2.7%) | 2.3-3.2% | 5000 | partly describes the synthetic generator; 23224 of 988361 packages, 2973 by this rule alone |
| Binding: ATC-SLOT-WINDOW eliminates packages in these rows | reported as measured | rules_only | 0/5000 (0.0%) | 0.0-0.1% | 5000 | partly describes the synthetic generator; 0 of 988361 packages, 0 by this rule alone |
| Binding: PLT-FUEL-POLICY eliminates packages in these rows | reported as measured | rules_only | 2022/5000 (40.4%) | 39.1-41.8% | 5000 | partly describes the synthetic generator; 300156 of 988361 packages, 80059 by this rule alone |
| Binding: PLT-CREW-DUTY eliminates packages in these rows | reported as measured | rules_only | 239/5000 (4.8%) | 4.2-5.4% | 5000 | partly describes the synthetic generator; 36922 of 988361 packages, 8289 by this rule alone |
| Binding: GND-GATE-OVERLAP eliminates packages in these rows | reported as measured | rules_only | 3456/5000 (69.1%) | 67.8-70.4% | 5000 | partly describes the synthetic generator; 147712 of 988361 packages, 42286 by this rule alone |
| Binding: GND-GATE-SIZE eliminates packages in these rows | reported as measured | rules_only | 0/5000 (0.0%) | 0.0-0.1% | 5000 | partly describes the synthetic generator; 0 of 988361 packages, 0 by this rule alone |
| Binding: GND-TURNAROUND eliminates packages in these rows | reported as measured | rules_only | 957/5000 (19.1%) | 18.1-20.3% | 5000 | partly describes the synthetic generator; 177101 of 988361 packages, 48777 by this rule alone |
| Binding: GND-GATE-NOTICE eliminates packages in these rows | reported as measured | rules_only | 1/5000 (0.0%) | 0.0-0.1% | 5000 | partly describes the synthetic generator; 6 of 988361 packages, 6 by this rule alone |
| Binding at airborne: ATC-WAKE-SEP eliminates packages in these rows | reported as measured | rules_only | 2201/2500 (88.0%) | 86.7-89.3% | 2500 | partly describes the synthetic generator |
| Binding at airborne: ATC-RWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 1203/2500 (48.1%) | 46.2-50.1% | 2500 | partly describes the synthetic generator |
| Binding at airborne: ATC-TWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 698/2500 (27.9%) | 26.2-29.7% | 2500 | partly describes the synthetic generator |
| Binding at airborne: ATC-RWY-THROUGHPUT eliminates packages in these rows | reported as measured | rules_only | 67/2500 (2.7%) | 2.1-3.4% | 2500 | partly describes the synthetic generator |
| Binding at airborne: ATC-SLOT-WINDOW eliminates packages in these rows | reported as measured | rules_only | 0/2500 (0.0%) | 0.0-0.2% | 2500 | partly describes the synthetic generator |
| Binding at airborne: PLT-FUEL-POLICY eliminates packages in these rows | reported as measured | rules_only | 2022/2500 (80.9%) | 79.3-82.4% | 2500 | partly describes the synthetic generator |
| Binding at airborne: PLT-CREW-DUTY eliminates packages in these rows | reported as measured | rules_only | 123/2500 (4.9%) | 4.1-5.8% | 2500 | partly describes the synthetic generator |
| Binding at airborne: GND-GATE-OVERLAP eliminates packages in these rows | reported as measured | rules_only | 1664/2500 (66.6%) | 64.7-68.4% | 2500 | partly describes the synthetic generator |
| Binding at airborne: GND-GATE-SIZE eliminates packages in these rows | reported as measured | rules_only | 0/2500 (0.0%) | 0.0-0.2% | 2500 | partly describes the synthetic generator |
| Binding at airborne: GND-TURNAROUND eliminates packages in these rows | reported as measured | rules_only | 474/2500 (19.0%) | 17.5-20.5% | 2500 | partly describes the synthetic generator |
| Binding at airborne: GND-GATE-NOTICE eliminates packages in these rows | reported as measured | rules_only | 0/2500 (0.0%) | 0.0-0.2% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: ATC-WAKE-SEP eliminates packages in these rows | reported as measured | rules_only | 2237/2500 (89.5%) | 88.2-90.6% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: ATC-RWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 194/2500 (7.8%) | 6.8-8.9% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: ATC-TWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 242/2500 (9.7%) | 8.6-10.9% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: ATC-RWY-THROUGHPUT eliminates packages in these rows | reported as measured | rules_only | 68/2500 (2.7%) | 2.2-3.4% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: ATC-SLOT-WINDOW eliminates packages in these rows | reported as measured | rules_only | 0/2500 (0.0%) | 0.0-0.2% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: PLT-FUEL-POLICY eliminates packages in these rows | reported as measured | rules_only | 0/2500 (0.0%) | 0.0-0.2% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: PLT-CREW-DUTY eliminates packages in these rows | reported as measured | rules_only | 116/2500 (4.6%) | 3.9-5.5% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: GND-GATE-OVERLAP eliminates packages in these rows | reported as measured | rules_only | 1792/2500 (71.7%) | 69.9-73.4% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: GND-GATE-SIZE eliminates packages in these rows | reported as measured | rules_only | 0/2500 (0.0%) | 0.0-0.2% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: GND-TURNAROUND eliminates packages in these rows | reported as measured | rules_only | 483/2500 (19.3%) | 17.8-20.9% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: GND-GATE-NOTICE eliminates packages in these rows | reported as measured | rules_only | 1/2500 (0.0%) | 0.0-0.2% | 2500 | partly describes the synthetic generator |
| Chosen package changes under at least one alternate weight | each weight scaled by 2 and by 10, both ways | rules_only | 29/3919 (0.7%) | 0.5-1.1% | 3919 |  |
| Chosen package changes with arrival_delay_per_min /10 | default weights | rules_only | 26/3919 (0.7%) | 0.5-1.0% | 3919 |  |
| Chosen package changes with arrival_delay_per_min /2 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with arrival_delay_per_min x10 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with arrival_delay_per_min x2 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with fuel_per_kg /10 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with fuel_per_kg /2 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with fuel_per_kg x10 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with fuel_per_kg x2 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with overtime_per_min /10 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with overtime_per_min /2 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with overtime_per_min x10 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with overtime_per_min x2 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with per_gate_move /10 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with per_gate_move /2 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with per_gate_move x10 | default weights | rules_only | 29/3919 (0.7%) | 0.5-1.1% | 3919 |  |
| Chosen package changes with per_gate_move x2 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with per_passenger_at_risk /10 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with per_passenger_at_risk /2 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with per_passenger_at_risk x10 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with per_passenger_at_risk x2 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with turnaround_delay_per_min /10 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with turnaround_delay_per_min /2 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with turnaround_delay_per_min x10 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes with turnaround_delay_per_min x2 | default weights | rules_only | 0/3919 (0.0%) | 0.0-0.1% | 3919 |  |
| Chosen package changes across synthetic seeds | several synthetic seeds per row | rules_only | 4642/5000 (92.8%) | 92.1-93.5% | 5000 | 3 seeds per row; the operational fields are synthetic |
| Outcome flips between deal and NO_GO across synthetic seeds | several synthetic seeds per row | rules_only | 2095/5000 (41.9%) | 40.5-43.3% | 5000 |  |
| Input sensitivity, close_chosen_runway | deal must change, or be shown unaffected with a reason | rules_only | 3919/3919 (100.0%) | 99.9-100.0% | 3919 | 1081 NOT_REACHED, no-go to perturb |
| Input sensitivity, close_other_runway | deal must change, or be shown unaffected with a reason | rules_only | 3077/3077 (100.0%) | 99.9-100.0% | 3077 | 1923 NOT_REACHED, no-go to perturb |
| Input sensitivity, close_all_runways | deal must change, or be shown unaffected with a reason | rules_only | 3919/3919 (100.0%) | 99.9-100.0% | 3919 | 1081 NOT_REACHED, no-go to perturb |
| Input sensitivity, unrelated_far_arrival | deal must change, or be shown unaffected with a reason | rules_only | 3919/3919 (100.0%) | 99.9-100.0% | 3919 | 1081 NOT_REACHED, no-go to perturb |
| Input sensitivity, unrelated_far_gate_use | deal must change, or be shown unaffected with a reason | rules_only | 3919/3919 (100.0%) | 99.9-100.0% | 3919 | 1081 NOT_REACHED, no-go to perturb |
| Input sensitivity, reorder_input_lists | deal must change, or be shown unaffected with a reason | rules_only | 3919/3919 (100.0%) | 99.9-100.0% | 3919 | 1081 NOT_REACHED, no-go to perturb |

## NO_GO rate as synthetic generator parameters move, same rows [class: rules_only]

Commit `e3fe575472a0`, mode `off`, seed 0, sample size 500, 2026-10-31T05:49:45+00:00.

| Measure | Compared against | Class | Value | 95% Wilson | n | Note |
|---|---|---|---|---|---|---|
| NO_GO rate, all rows, default parameters | default parameters | rules_only | 114/500 (22.8%) | 19.3-26.7% | 500 | +0.0 points against default; most binding: GND-TURNAROUND in 91 |
| NO_GO rate, all rows, p_next_leg_hard=0.0 | default parameters | rules_only | 27/500 (5.4%) | 3.7-7.7% | 500 | -17.4 points against default; most binding: PLT-FUEL-POLICY in 14 |
| NO_GO rate, all rows, p_next_leg_hard=0.7 | default parameters | rules_only | 186/500 (37.2%) | 33.1-41.5% | 500 | +14.4 points against default; most binding: GND-TURNAROUND in 164 |
| NO_GO rate, all rows, gate_util_base=0.15 | default parameters | rules_only | 114/500 (22.8%) | 19.3-26.7% | 500 | +0.0 points against default; most binding: GND-TURNAROUND in 91 |
| NO_GO rate, all rows, gate_util_base=0.55 | default parameters | rules_only | 113/500 (22.6%) | 19.2-26.5% | 500 | -0.2 points against default; most binding: GND-TURNAROUND in 91 |
| NO_GO rate, all rows, surplus_pre_departure_min=(0, 10) | default parameters | rules_only | 114/500 (22.8%) | 19.3-26.7% | 500 | +0.0 points against default; most binding: GND-TURNAROUND in 91 |
| NO_GO rate, all rows, surplus_pre_departure_min=(-10, 5) | default parameters | rules_only | 117/500 (23.4%) | 19.9-27.3% | 500 | +0.6 points against default; most binding: GND-TURNAROUND in 91 |
| NO_GO rate, all rows, p_planned_gate_conflict=0.0 | default parameters | rules_only | 113/500 (22.6%) | 19.2-26.5% | 500 | -0.2 points against default; most binding: GND-TURNAROUND in 91 |
| NO_GO rate, weather, default parameters | default parameters | rules_only | 66/250 (26.4%) | 21.3-32.2% | 250 | +0.0 points against default; most binding: GND-TURNAROUND in 48 |
| NO_GO rate, weather, p_next_leg_hard=0.0 | default parameters | rules_only | 22/250 (8.8%) | 5.9-13.0% | 250 | -17.6 points against default; most binding: PLT-FUEL-POLICY in 14 |
| NO_GO rate, weather, p_next_leg_hard=0.7 | default parameters | rules_only | 98/250 (39.2%) | 33.4-45.4% | 250 | +12.8 points against default; most binding: GND-TURNAROUND in 81 |
| NO_GO rate, weather, gate_util_base=0.15 | default parameters | rules_only | 66/250 (26.4%) | 21.3-32.2% | 250 | +0.0 points against default; most binding: GND-TURNAROUND in 48 |
| NO_GO rate, weather, gate_util_base=0.55 | default parameters | rules_only | 65/250 (26.0%) | 21.0-31.8% | 250 | -0.4 points against default; most binding: GND-TURNAROUND in 48 |
| NO_GO rate, weather, surplus_pre_departure_min=(0, 10) | default parameters | rules_only | 66/250 (26.4%) | 21.3-32.2% | 250 | +0.0 points against default; most binding: GND-TURNAROUND in 48 |
| NO_GO rate, weather, surplus_pre_departure_min=(-10, 5) | default parameters | rules_only | 66/250 (26.4%) | 21.3-32.2% | 250 | +0.0 points against default; most binding: GND-TURNAROUND in 48 |
| NO_GO rate, weather, p_planned_gate_conflict=0.0 | default parameters | rules_only | 64/250 (25.6%) | 20.6-31.4% | 250 | -0.8 points against default; most binding: GND-TURNAROUND in 48 |
| NO_GO rate, late_aircraft, default parameters | default parameters | rules_only | 48/250 (19.2%) | 14.8-24.5% | 250 | +0.0 points against default; most binding: GND-TURNAROUND in 43 |
| NO_GO rate, late_aircraft, p_next_leg_hard=0.0 | default parameters | rules_only | 5/250 (2.0%) | 0.9-4.6% | 250 | -17.2 points against default; most binding: PLT-CREW-DUTY in 5 |
| NO_GO rate, late_aircraft, p_next_leg_hard=0.7 | default parameters | rules_only | 88/250 (35.2%) | 29.5-41.3% | 250 | +16.0 points against default; most binding: GND-TURNAROUND in 83 |
| NO_GO rate, late_aircraft, gate_util_base=0.15 | default parameters | rules_only | 48/250 (19.2%) | 14.8-24.5% | 250 | +0.0 points against default; most binding: GND-TURNAROUND in 43 |
| NO_GO rate, late_aircraft, gate_util_base=0.55 | default parameters | rules_only | 48/250 (19.2%) | 14.8-24.5% | 250 | +0.0 points against default; most binding: GND-TURNAROUND in 43 |
| NO_GO rate, late_aircraft, surplus_pre_departure_min=(0, 10) | default parameters | rules_only | 48/250 (19.2%) | 14.8-24.5% | 250 | +0.0 points against default; most binding: GND-TURNAROUND in 43 |
| NO_GO rate, late_aircraft, surplus_pre_departure_min=(-10, 5) | default parameters | rules_only | 51/250 (20.4%) | 15.9-25.8% | 250 | +1.2 points against default; most binding: GND-TURNAROUND in 43 |
| NO_GO rate, late_aircraft, p_planned_gate_conflict=0.0 | default parameters | rules_only | 49/250 (19.6%) | 15.2-25.0% | 250 | +0.4 points against default; most binding: GND-TURNAROUND in 43 |

## Controls on hand-built scenarios [class: test]

Commit `e3fe575472a0`, mode `off`, seed 0, sample size 20, 2026-10-31T05:49:45+00:00.

| Measure | Compared against | Class | Value | 95% Wilson | n | Note |
|---|---|---|---|---|---|---|
| Rules defended: injected violation caught, and noticed when disabled | one injected unsafe package per rule, then a mutation run per rule | test | 11/11 (100.0%) | 74.1-100.0% | 11 |  |
| Rule ATC-WAKE-SEP: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | wake_spacing_1_min |
| Rule ATC-RWY-CLOSED: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | closed_runway |
| Rule ATC-TWY-CLOSED: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | closed_taxiway |
| Rule ATC-RWY-THROUGHPUT: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | runway_over_hourly_cap |
| Rule ATC-SLOT-WINDOW: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | slot_off_the_grid |
| Rule PLT-FUEL-POLICY: DEFENDED | injected case and mutation | test | 3 cases defended |  | 3 | fuel_below_reserve, hold_before_departure, direct_cannot_absorb_delay |
| Rule PLT-CREW-DUTY: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | crew_past_maximum_duty |
| Rule GND-GATE-OVERLAP: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | gate_overlap |
| Rule GND-GATE-SIZE: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | aircraft_too_big_for_gate |
| Rule GND-TURNAROUND: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | turnaround_too_short |
| Rule GND-GATE-NOTICE: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | gate_change_without_notice |
| Mutants that make the decision pick the unsafe package | rule disabled, cheapest package breaks it | test | 10/10 (100.0%) | 72.2-100.0% | 10 |  |
| Injected violations the harm check also flags | independent harm check, in its scope only | test | 8/8 (100.0%) | 67.6-100.0% | 8 |  |
| Controls that must succeed, on fallback.decide | expected answers worked by hand | test | 7/7 (100.0%) | 64.6-100.0% | 7 | positive runs and named failures |
| Controls that must succeed, through protocol mode off | expected answers worked by hand | test | 7/7 (100.0%) | 64.6-100.0% | 7 |  |
| Mode off runs labelled as a fault or a fallback trigger, never clean | plan: an LLM-off run is never logged as a clean fallback | test | 7/7 (100.0%) | 64.6-100.0% | 7 |  |
| Agents agreeing to anything, stopped by the protocol gate: unsafe package kept out | scripted agents through protocol, then the rule disabled | test | 10/10 (100.0%) | 72.2-100.0% | 10 |  |
| Agents agreeing to anything, stopped by the protocol gate: mutation noticed, unsafe package let through | scripted agents through protocol, then the rule disabled | test | 10/10 (100.0%) | 72.2-100.0% | 10 |  |
| Reply naming a package never offered ends in a fault | scripted hostile agents through protocol | test | 1/1 (100.0%) | 20.7-100.0% | 1 |  |
| Hand-calculated scenarios checked by someone who did not write the code | independent reviewer | test | NOT_REACHED |  |  | no independent reviewer has checked these; the author worked them |
| Input-sensitivity pairs on a hand-built scenario | close a runway, alter an unrelated flight | test | 6/6 (100.0%) | 61.0-100.0% | 6 |  |

## Needs a model, and none ran [class: rules_only]

Commit `e3fe575472a0`, mode `off`, seed 0, sample size 5000, 2026-10-31T05:49:45+00:00.

| Measure | Compared against | Class | Value | 95% Wilson | n | Note |
|---|---|---|---|---|---|---|
| Convergence rate | reported as measured | rules_only | NOT_REACHED |  |  | mode off: no model ran |
| Turns used | turn cap of 2 | rules_only | NOT_REACHED |  |  | mode off: no model ran |
| Cost gap of consensus to best package | best enumerated package (consensus only) | rules_only | NOT_REACHED |  |  | mode off: no model ran |
| LLM versus fallback on the same rows | fallback.py on the same rows | rules_only | NOT_REACHED |  |  | mode off: no model ran |
| Unguarded arm violation rate | unguarded model pick on the same rows | rules_only | NOT_REACHED |  |  | mode off: no model ran |
| Frozen score, first live run | preserved, never overwritten | rules_only | NOT_REACHED |  |  | mode off: no model ran |

## Planned live calls

```
tune: 60
first frozen (negotiation + unguarded): 140
second frozen: 120
re-record TURN2-CONFLICT (outside this harness): 6
total: 326
The TURN2-CONFLICT re-record is 6 calls outside the ledger, so count them by hand.
```

## Limits

- Results are simulated outcomes on 2015 US data, not measured savings.
- Wake category, fuel, runway configuration, taxiway blockage, gate map, ground shift and connections are synthetic, seeded per flight.
- Eligible rows contain no cancelled or diverted flights, so the worst disruptions are missing.
- October is excluded because its airport codes are numeric.
- Samples are stratified half weather, half late-aircraft, so pooled rates do not describe the population, where about 91% are late-aircraft.
- Small samples prove little. By the Wilson interval, 0 violations in 30 runs still allows a true rate up to 11.4% at 95% confidence.
- Safety rests on the gate, not on the sample: no package reaches a person without passing rules/.
- The rules are a subset of real ATC procedure, and binding counts partly describe our generator: see how NO_GO moves with its parameters above.
- Converting wake separation from miles to minutes depends on an assumed approach speed.
- Real ARRIVAL_DELAY is context only and shows no saving: a scenario's earliest arrival is schedule plus a floor, or inbound lateness where available, so the input can understate the delay. Delay claims rest on the paired baselines, run on the same scenario window.
- harm.py and rules/ share a plan and rule_values, so a shared misreading passes both.
- Numbers of different evidence classes are never comparable.
- The scenario generator adds a synthetic reassigned stay on the planned gate on 50% of flights. We added it after a rules-only run showed no package ever traded one cost against another, and before any model output existed. It creates the trade-offs measured here, so they describe our generator, not observed operations.
- For this run's 5000 rows, a zero rate still allows up to 0.08% at 95% confidence.

## Not proven by this run

- [rules_only] Context: simulated arrival delay, window basis not available: no row with window basis not available
- [rules_only] Context: real ARRIVAL_DELAY, window basis not available: no row with window basis not available
- [test] Hand-calculated scenarios checked by someone who did not write the code: no independent reviewer has checked these; the author worked them
- [rules_only] Convergence rate: mode off: no model ran
- [rules_only] Turns used: mode off: no model ran
- [rules_only] Cost gap of consensus to best package: mode off: no model ran
- [rules_only] LLM versus fallback on the same rows: mode off: no model ran
- [rules_only] Unguarded arm violation rate: mode off: no model ran
- [rules_only] Frozen score, first live run: mode off: no model ran

## Control failures

- None.
