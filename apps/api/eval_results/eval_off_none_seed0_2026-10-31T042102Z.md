# Evaluation results

- Commit: `24697acf15e518d51a5e79be5aab47f6e4567f25`
- Mode: `off`; split: `none`; seed: 0; sample size: 5000
- Generated: 2026-10-31T04:21:02+00:00
- Time: 373.0 s with 10 worker(s), 13.4 rows/s

Panels hold one evidence class each. Do not compare across them.

## Deterministic core over the sample, mode off [class: rules_only]

Commit `24697acf15e5`, mode `off`, seed 0, sample size 5000, 2026-10-31T04:21:02+00:00.

| Measure | Compared against | Class | Value | 95% Wilson | n | Note |
|---|---|---|---|---|---|---|
| Rows evaluated | reported as measured | rules_only | 5000 rows |  | 5000 | stratified 50/50 by cause |
| Rows that errored | reported as measured | rules_only | 0/5000 (0.0%) | 0.0-0.1% | 5000 |  |
| Deal rate, all rows | usefulness beside safety | rules_only | 3961/5000 (79.2%) | 78.1-80.3% | 5000 |  |
| NO_DEAL NOTHING_LEGAL rate, all rows | usefulness beside safety | rules_only | 1039/5000 (20.8%) | 19.7-21.9% | 5000 |  |
| NO_DEAL SYSTEM_FAULT rate, all rows | usefulness beside safety | rules_only | 0/5000 (0.0%) | 0.0-0.1% | 5000 |  |
| Deal rate, weather | usefulness beside safety | rules_only | 1859/2500 (74.4%) | 72.6-76.0% | 2500 |  |
| NO_DEAL NOTHING_LEGAL rate, weather | usefulness beside safety | rules_only | 641/2500 (25.6%) | 24.0-27.4% | 2500 |  |
| NO_DEAL SYSTEM_FAULT rate, weather | usefulness beside safety | rules_only | 0/2500 (0.0%) | 0.0-0.2% | 2500 |  |
| Deal rate, late_aircraft | usefulness beside safety | rules_only | 2102/2500 (84.1%) | 82.6-85.5% | 2500 |  |
| NO_DEAL NOTHING_LEGAL rate, late_aircraft | usefulness beside safety | rules_only | 398/2500 (15.9%) | 14.5-17.4% | 2500 |  |
| NO_DEAL SYSTEM_FAULT rate, late_aircraft | usefulness beside safety | rules_only | 0/2500 (0.0%) | 0.0-0.2% | 2500 |  |
| Fallback rate (LLM off) | reported as measured | rules_only | 3961/5000 (79.2%) | 78.1-80.3% | 5000 | every deal in mode off is a fallback by construction, so this is the deal rate and says nothing about the agents |
| Mode off decisions differing from fallback.decide | reported as measured | rules_only | 0 rows |  | 5000 |  |
| Context: simulated arrival delay, inbound data set the window | not a saving: simulated window versus real outcome | rules_only | 38.33 min |  | 763 | not a saving: simulated window versus real outcome |
| Context: real ARRIVAL_DELAY, inbound data set the window | not a saving: simulated window versus real outcome | rules_only | 52.05 min |  | 763 | not a saving: simulated window versus real outcome |
| Context: simulated arrival delay, disruption floor set the window | not a saving: simulated window versus real outcome | rules_only | 19.91 min |  | 3198 | not a saving: simulated window versus real outcome |
| Context: real ARRIVAL_DELAY, disruption floor set the window | not a saving: simulated window versus real outcome | rules_only | 100.89 min |  | 3198 | not a saving: simulated window versus real outcome |
| Context: simulated arrival delay, window basis not available | not a saving: simulated window versus real outcome | rules_only | NOT_REACHED |  |  | no row with window basis not available |
| Context: real ARRIVAL_DELAY, window basis not available | not a saving: simulated window versus real outcome | rules_only | NOT_REACHED |  |  | no row with window basis not available |
| Delay past the scenario's earliest arrival, fallback | the baselines below | rules_only | 2.83 min |  | 3961 |  |
| Fuel-reserve margin, fallback | the baselines below | rules_only | 2491.13 kg |  | 3961 |  |
| Connection passengers at risk, fallback | the baselines below | rules_only | 8.1 pax |  | 3961 |  |
| Ground overtime, fallback | the baselines below | rules_only | 0.99 min |  | 3961 |  |
| first_come_first_served: rows where it found no package | no coordination: first come first served, nearest gate | rules_only | 0/5000 (0.0%) | 0.0-0.1% | 5000 |  |
| first_come_first_served: packages breaking a rule | no coordination: first come first served, nearest gate | rules_only | 4369/5000 (87.4%) | 86.4-88.3% | 5000 |  |
| first_come_first_served: packages the harm check calls harmful | no coordination: first come first served, nearest gate | rules_only | 4131/5000 (82.6%) | 81.5-83.6% | 5000 |  |
| first_come_first_served: breaks ATC-RWY-CLOSED | no coordination: first come first served, nearest gate | rules_only | 517/5000 (10.3%) | 9.5-11.2% | 5000 |  |
| first_come_first_served: breaks ATC-RWY-THROUGHPUT | no coordination: first come first served, nearest gate | rules_only | 180/5000 (3.6%) | 3.1-4.2% | 5000 |  |
| first_come_first_served: breaks ATC-TWY-CLOSED | no coordination: first come first served, nearest gate | rules_only | 493/5000 (9.9%) | 9.1-10.7% | 5000 |  |
| first_come_first_served: breaks ATC-WAKE-SEP | no coordination: first come first served, nearest gate | rules_only | 1607/5000 (32.1%) | 30.9-33.4% | 5000 |  |
| first_come_first_served: breaks GND-GATE-OVERLAP | no coordination: first come first served, nearest gate | rules_only | 3559/5000 (71.2%) | 69.9-72.4% | 5000 |  |
| first_come_first_served: breaks GND-GATE-SIZE | no coordination: first come first served, nearest gate | rules_only | 967/5000 (19.3%) | 18.3-20.5% | 5000 |  |
| first_come_first_served: breaks GND-TURNAROUND | no coordination: first come first served, nearest gate | rules_only | 581/5000 (11.6%) | 10.8-12.5% | 5000 |  |
| first_come_first_served: breaks PLT-FUEL-POLICY | no coordination: first come first served, nearest gate | rules_only | 117/5000 (2.3%) | 2.0-2.8% | 5000 |  |
| Fallback picks the same package as first_come_first_served | no coordination: first come first served, nearest gate | rules_only | 366/3961 (9.2%) | 8.4-10.2% | 3961 | how much the cost ranking adds over this baseline |
| Delay past the scenario's earliest arrival, first_come_first_served, all its packages | no coordination: first come first served, nearest gate | rules_only | 0 min |  | 5000 | an illegal low delay is not a win |
| Delay past the scenario's earliest arrival, first_come_first_served, only its legal packages | no coordination: first come first served, nearest gate | rules_only | 0 min |  | 631 |  |
| Delay past the scenario's earliest arrival, fallback minus first_come_first_served, paired on the same window | no coordination: first come first served, nearest gate | rules_only | 0 min |  | 631 | rows where both have a package and the baseline's is legal |
| Fuel-reserve margin, first_come_first_served, all its packages | no coordination: first come first served, nearest gate | rules_only | 2424.76 kg |  | 5000 | an illegal low delay is not a win |
| Fuel-reserve margin, first_come_first_served, only its legal packages | no coordination: first come first served, nearest gate | rules_only | 2521.06 kg |  | 631 |  |
| Fuel-reserve margin, fallback minus first_come_first_served, paired on the same window | no coordination: first come first served, nearest gate | rules_only | 0 kg |  | 631 | rows where both have a package and the baseline's is legal |
| Connection passengers at risk, first_come_first_served, all its packages | no coordination: first come first served, nearest gate | rules_only | 6.95 pax |  | 5000 | an illegal low delay is not a win |
| Connection passengers at risk, first_come_first_served, only its legal packages | no coordination: first come first served, nearest gate | rules_only | 6.15 pax |  | 631 |  |
| Connection passengers at risk, fallback minus first_come_first_served, paired on the same window | no coordination: first come first served, nearest gate | rules_only | 0 pax |  | 631 | rows where both have a package and the baseline's is legal |
| Ground overtime, first_come_first_served, all its packages | no coordination: first come first served, nearest gate | rules_only | 0.65 min |  | 5000 | an illegal low delay is not a win |
| Ground overtime, first_come_first_served, only its legal packages | no coordination: first come first served, nearest gate | rules_only | 0.8 min |  | 631 |  |
| Ground overtime, fallback minus first_come_first_served, paired on the same window | no coordination: first come first served, nearest gate | rules_only | 0 min |  | 631 | rows where both have a package and the baseline's is legal |
| human_heuristic: rows where it found no package | sensible human heuristic | rules_only | 1039/5000 (20.8%) | 19.7-21.9% | 5000 |  |
| human_heuristic: packages breaking a rule | sensible human heuristic | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 | zero by construction: this baseline consults the rules |
| human_heuristic: packages the harm check calls harmful | sensible human heuristic | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Fallback picks the same package as human_heuristic | sensible human heuristic | rules_only | 3626/3961 (91.5%) | 90.6-92.4% | 3961 | how much the cost ranking adds over this baseline |
| Delay past the scenario's earliest arrival, human_heuristic, all its packages | sensible human heuristic | rules_only | 2.83 min |  | 3961 | an illegal low delay is not a win |
| Delay past the scenario's earliest arrival, human_heuristic, only its legal packages | sensible human heuristic | rules_only | 2.83 min |  | 3961 |  |
| Delay past the scenario's earliest arrival, fallback minus human_heuristic, paired on the same window | sensible human heuristic | rules_only | 0 min |  | 3961 | rows where both have a package and the baseline's is legal |
| Fuel-reserve margin, human_heuristic, all its packages | sensible human heuristic | rules_only | 2491.13 kg |  | 3961 | an illegal low delay is not a win |
| Fuel-reserve margin, human_heuristic, only its legal packages | sensible human heuristic | rules_only | 2491.13 kg |  | 3961 |  |
| Fuel-reserve margin, fallback minus human_heuristic, paired on the same window | sensible human heuristic | rules_only | 0 kg |  | 3961 | rows where both have a package and the baseline's is legal |
| Connection passengers at risk, human_heuristic, all its packages | sensible human heuristic | rules_only | 8.1 pax |  | 3961 | an illegal low delay is not a win |
| Connection passengers at risk, human_heuristic, only its legal packages | sensible human heuristic | rules_only | 8.1 pax |  | 3961 |  |
| Connection passengers at risk, fallback minus human_heuristic, paired on the same window | sensible human heuristic | rules_only | 0 pax |  | 3961 | rows where both have a package and the baseline's is legal |
| Ground overtime, human_heuristic, all its packages | sensible human heuristic | rules_only | 0.99 min |  | 3961 | an illegal low delay is not a win |
| Ground overtime, human_heuristic, only its legal packages | sensible human heuristic | rules_only | 0.99 min |  | 3961 |  |
| Ground overtime, fallback minus human_heuristic, paired on the same window | sensible human heuristic | rules_only | 0 min |  | 3961 | rows where both have a package and the baseline's is legal |
| Chosen package has zero soft cost | reported as measured | rules_only | 1219/3961 (30.8%) | 29.4-32.2% | 3961 | under any positive weights this pick cannot be beaten |
| Pick is no worse than every legal package on every cost component | reported as measured | rules_only | 3507/3961 (88.5%) | 87.5-89.5% | 3961 | on these rows there is no trade-off, so weights cannot move the pick and a stable pick is not evidence of robustness |
| Legal packages per deal row | reported as measured | rules_only | 42.36 packages |  | 3961 |  |
| Final packages breaking a rule | must be zero: the gate | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Final packages the independent harm check calls harmful | harm.py, own logic | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| harm.py versus rules: harm_only | rules/ on the same final package | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| harm.py versus rules: rules_only | rules/ on the same final package | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| harm.py versus rules: harm_unknown | rules/ on the same final package | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| harm.py versus rules: rules_fail_closed_only | rules/ on the same final package | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Binding: ATC-WAKE-SEP eliminates packages in these rows | reported as measured | rules_only | 4434/5000 (88.7%) | 87.8-89.5% | 5000 | partly describes the synthetic generator; 1130942 of 3136573 packages, 83278 by this rule alone |
| Binding: ATC-RWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 1191/5000 (23.8%) | 22.7-25.0% | 5000 | partly describes the synthetic generator; 484495 of 3136573 packages, 28414 by this rule alone |
| Binding: ATC-TWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 1508/5000 (30.2%) | 28.9-31.4% | 5000 | partly describes the synthetic generator; 360495 of 3136573 packages, 16662 by this rule alone |
| Binding: ATC-RWY-THROUGHPUT eliminates packages in these rows | reported as measured | rules_only | 421/5000 (8.4%) | 7.7-9.2% | 5000 | partly describes the synthetic generator; 174482 of 3136573 packages, 2057 by this rule alone |
| Binding: ATC-SLOT-WINDOW eliminates packages in these rows | reported as measured | rules_only | 0/5000 (0.0%) | 0.0-0.1% | 5000 | partly describes the synthetic generator; 0 of 3136573 packages, 0 by this rule alone |
| Binding: PLT-FUEL-POLICY eliminates packages in these rows | reported as measured | rules_only | 2007/5000 (40.1%) | 38.8-41.5% | 5000 | partly describes the synthetic generator; 908234 of 3136573 packages, 56884 by this rule alone |
| Binding: GND-GATE-OVERLAP eliminates packages in these rows | reported as measured | rules_only | 5000/5000 (100.0%) | 99.9-100.0% | 5000 | partly describes the synthetic generator; 2455439 of 3136573 packages, 527539 by this rule alone |
| Binding: GND-GATE-SIZE eliminates packages in these rows | reported as measured | rules_only | 3582/5000 (71.6%) | 70.4-72.9% | 5000 | partly describes the synthetic generator; 643729 of 3136573 packages, 36699 by this rule alone |
| Binding: GND-TURNAROUND eliminates packages in these rows | reported as measured | rules_only | 942/5000 (18.8%) | 17.8-19.9% | 5000 | partly describes the synthetic generator; 510059 of 3136573 packages, 35705 by this rule alone |
| Binding at airborne: ATC-WAKE-SEP eliminates packages in these rows | reported as measured | rules_only | 2201/2500 (88.0%) | 86.7-89.3% | 2500 | partly describes the synthetic generator |
| Binding at airborne: ATC-RWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 1018/2500 (40.7%) | 38.8-42.7% | 2500 | partly describes the synthetic generator |
| Binding at airborne: ATC-TWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 1103/2500 (44.1%) | 42.2-46.1% | 2500 | partly describes the synthetic generator |
| Binding at airborne: ATC-RWY-THROUGHPUT eliminates packages in these rows | reported as measured | rules_only | 321/2500 (12.8%) | 11.6-14.2% | 2500 | partly describes the synthetic generator |
| Binding at airborne: ATC-SLOT-WINDOW eliminates packages in these rows | reported as measured | rules_only | 0/2500 (0.0%) | 0.0-0.2% | 2500 | partly describes the synthetic generator |
| Binding at airborne: PLT-FUEL-POLICY eliminates packages in these rows | reported as measured | rules_only | 2007/2500 (80.3%) | 78.7-81.8% | 2500 | partly describes the synthetic generator |
| Binding at airborne: GND-GATE-OVERLAP eliminates packages in these rows | reported as measured | rules_only | 2500/2500 (100.0%) | 99.8-100.0% | 2500 | partly describes the synthetic generator |
| Binding at airborne: GND-GATE-SIZE eliminates packages in these rows | reported as measured | rules_only | 1848/2500 (73.9%) | 72.2-75.6% | 2500 | partly describes the synthetic generator |
| Binding at airborne: GND-TURNAROUND eliminates packages in these rows | reported as measured | rules_only | 467/2500 (18.7%) | 17.2-20.3% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: ATC-WAKE-SEP eliminates packages in these rows | reported as measured | rules_only | 2233/2500 (89.3%) | 88.0-90.5% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: ATC-RWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 173/2500 (6.9%) | 6.0-8.0% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: ATC-TWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 405/2500 (16.2%) | 14.8-17.7% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: ATC-RWY-THROUGHPUT eliminates packages in these rows | reported as measured | rules_only | 100/2500 (4.0%) | 3.3-4.8% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: ATC-SLOT-WINDOW eliminates packages in these rows | reported as measured | rules_only | 0/2500 (0.0%) | 0.0-0.2% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: PLT-FUEL-POLICY eliminates packages in these rows | reported as measured | rules_only | 0/2500 (0.0%) | 0.0-0.2% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: GND-GATE-OVERLAP eliminates packages in these rows | reported as measured | rules_only | 2500/2500 (100.0%) | 99.8-100.0% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: GND-GATE-SIZE eliminates packages in these rows | reported as measured | rules_only | 1734/2500 (69.4%) | 67.5-71.1% | 2500 | partly describes the synthetic generator |
| Binding at pre_departure: GND-TURNAROUND eliminates packages in these rows | reported as measured | rules_only | 475/2500 (19.0%) | 17.5-20.6% | 2500 | partly describes the synthetic generator |
| Chosen package changes under at least one alternate weight | each weight scaled by 2 and by 10, both ways | rules_only | 68/3961 (1.7%) | 1.4-2.2% | 3961 |  |
| Chosen package changes with arrival_delay_per_min /10 | default weights | rules_only | 63/3961 (1.6%) | 1.2-2.0% | 3961 |  |
| Chosen package changes with arrival_delay_per_min /2 | default weights | rules_only | 2/3961 (0.1%) | 0.0-0.2% | 3961 |  |
| Chosen package changes with arrival_delay_per_min x10 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with arrival_delay_per_min x2 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with fuel_per_kg /10 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with fuel_per_kg /2 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with fuel_per_kg x10 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with fuel_per_kg x2 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with overtime_per_min /10 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with overtime_per_min /2 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with overtime_per_min x10 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with overtime_per_min x2 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with per_gate_move /10 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with per_gate_move /2 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with per_gate_move x10 | default weights | rules_only | 68/3961 (1.7%) | 1.4-2.2% | 3961 |  |
| Chosen package changes with per_gate_move x2 | default weights | rules_only | 2/3961 (0.1%) | 0.0-0.2% | 3961 |  |
| Chosen package changes with per_passenger_at_risk /10 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with per_passenger_at_risk /2 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with per_passenger_at_risk x10 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with per_passenger_at_risk x2 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with turnaround_delay_per_min /10 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with turnaround_delay_per_min /2 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with turnaround_delay_per_min x10 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes with turnaround_delay_per_min x2 | default weights | rules_only | 0/3961 (0.0%) | 0.0-0.1% | 3961 |  |
| Chosen package changes across synthetic seeds | several synthetic seeds per row | rules_only | 4852/5000 (97.0%) | 96.5-97.5% | 5000 | 3 seeds per row; the operational fields are synthetic |
| Outcome flips between deal and NO_DEAL across synthetic seeds | several synthetic seeds per row | rules_only | 2058/5000 (41.2%) | 39.8-42.5% | 5000 |  |
| Input sensitivity, close_chosen_runway | deal must change, or be shown unaffected with a reason | rules_only | 3961/3961 (100.0%) | 99.9-100.0% | 3961 | 1039 NOT_REACHED, no deal to perturb |
| Input sensitivity, close_other_runway | deal must change, or be shown unaffected with a reason | rules_only | 2686/2686 (100.0%) | 99.9-100.0% | 2686 | 2314 NOT_REACHED, no deal to perturb |
| Input sensitivity, close_all_runways | deal must change, or be shown unaffected with a reason | rules_only | 3961/3961 (100.0%) | 99.9-100.0% | 3961 | 1039 NOT_REACHED, no deal to perturb |
| Input sensitivity, unrelated_far_arrival | deal must change, or be shown unaffected with a reason | rules_only | 3961/3961 (100.0%) | 99.9-100.0% | 3961 | 1039 NOT_REACHED, no deal to perturb |
| Input sensitivity, unrelated_far_gate_use | deal must change, or be shown unaffected with a reason | rules_only | 3961/3961 (100.0%) | 99.9-100.0% | 3961 | 1039 NOT_REACHED, no deal to perturb |
| Input sensitivity, reorder_input_lists | deal must change, or be shown unaffected with a reason | rules_only | 3961/3961 (100.0%) | 99.9-100.0% | 3961 | 1039 NOT_REACHED, no deal to perturb |

## NO_DEAL rate as synthetic generator parameters move, same rows [class: rules_only]

Commit `24697acf15e5`, mode `off`, seed 0, sample size 500, 2026-10-31T04:21:02+00:00.

| Measure | Compared against | Class | Value | 95% Wilson | n | Note |
|---|---|---|---|---|---|---|
| NO_DEAL rate, all rows, default parameters | default parameters | rules_only | 123/500 (24.6%) | 21.0-28.6% | 500 | +0.0 points against default; most binding: GND-TURNAROUND in 77 |
| NO_DEAL rate, all rows, p_next_leg_hard=0.0 | default parameters | rules_only | 54/500 (10.8%) | 8.4-13.8% | 500 | -13.8 points against default; most binding: PLT-FUEL-POLICY in 27 |
| NO_DEAL rate, all rows, p_next_leg_hard=0.7 | default parameters | rules_only | 175/500 (35.0%) | 30.9-39.3% | 500 | +10.4 points against default; most binding: GND-TURNAROUND in 129 |
| NO_DEAL rate, all rows, gate_util_base=0.15 | default parameters | rules_only | 109/500 (21.8%) | 18.4-25.6% | 500 | -2.8 points against default; most binding: GND-TURNAROUND in 77 |
| NO_DEAL rate, all rows, gate_util_base=0.55 | default parameters | rules_only | 164/500 (32.8%) | 28.8-37.0% | 500 | +8.2 points against default; most binding: GND-GATE-OVERLAP in 81 |
| NO_DEAL rate, all rows, surplus_pre_departure_min=(0, 10) | default parameters | rules_only | 123/500 (24.6%) | 21.0-28.6% | 500 | +0.0 points against default; most binding: GND-TURNAROUND in 77 |
| NO_DEAL rate, all rows, surplus_pre_departure_min=(-10, 5) | default parameters | rules_only | 139/500 (27.8%) | 24.1-31.9% | 500 | +3.2 points against default; most binding: GND-TURNAROUND in 77 |
| NO_DEAL rate, all rows, p_planned_gate_conflict=0.0 | default parameters | rules_only | 117/500 (23.4%) | 19.9-27.3% | 500 | -1.2 points against default; most binding: GND-TURNAROUND in 77 |
| NO_DEAL rate, weather, default parameters | default parameters | rules_only | 76/250 (30.4%) | 25.0-36.4% | 250 | +0.0 points against default; most binding: GND-TURNAROUND in 35 |
| NO_DEAL rate, weather, p_next_leg_hard=0.0 | default parameters | rules_only | 48/250 (19.2%) | 14.8-24.5% | 250 | -11.2 points against default; most binding: PLT-FUEL-POLICY in 27 |
| NO_DEAL rate, weather, p_next_leg_hard=0.7 | default parameters | rules_only | 96/250 (38.4%) | 32.6-44.6% | 250 | +8.0 points against default; most binding: GND-TURNAROUND in 55 |
| NO_DEAL rate, weather, gate_util_base=0.15 | default parameters | rules_only | 66/250 (26.4%) | 21.3-32.2% | 250 | -4.0 points against default; most binding: GND-TURNAROUND in 35 |
| NO_DEAL rate, weather, gate_util_base=0.55 | default parameters | rules_only | 100/250 (40.0%) | 34.1-46.2% | 250 | +9.6 points against default; most binding: GND-GATE-OVERLAP in 53 |
| NO_DEAL rate, weather, surplus_pre_departure_min=(0, 10) | default parameters | rules_only | 76/250 (30.4%) | 25.0-36.4% | 250 | +0.0 points against default; most binding: GND-TURNAROUND in 35 |
| NO_DEAL rate, weather, surplus_pre_departure_min=(-10, 5) | default parameters | rules_only | 76/250 (30.4%) | 25.0-36.4% | 250 | +0.0 points against default; most binding: GND-TURNAROUND in 35 |
| NO_DEAL rate, weather, p_planned_gate_conflict=0.0 | default parameters | rules_only | 71/250 (28.4%) | 23.2-34.3% | 250 | -2.0 points against default; most binding: GND-TURNAROUND in 35 |
| NO_DEAL rate, late_aircraft, default parameters | default parameters | rules_only | 47/250 (18.8%) | 14.4-24.1% | 250 | +0.0 points against default; most binding: GND-TURNAROUND in 42 |
| NO_DEAL rate, late_aircraft, p_next_leg_hard=0.0 | default parameters | rules_only | 6/250 (2.4%) | 1.1-5.1% | 250 | -16.4 points against default; most binding: GND-GATE-OVERLAP in 6 |
| NO_DEAL rate, late_aircraft, p_next_leg_hard=0.7 | default parameters | rules_only | 79/250 (31.6%) | 26.2-37.6% | 250 | +12.8 points against default; most binding: GND-TURNAROUND in 74 |
| NO_DEAL rate, late_aircraft, gate_util_base=0.15 | default parameters | rules_only | 43/250 (17.2%) | 13.0-22.4% | 250 | -1.6 points against default; most binding: GND-TURNAROUND in 42 |
| NO_DEAL rate, late_aircraft, gate_util_base=0.55 | default parameters | rules_only | 64/250 (25.6%) | 20.6-31.4% | 250 | +6.8 points against default; most binding: GND-TURNAROUND in 42 |
| NO_DEAL rate, late_aircraft, surplus_pre_departure_min=(0, 10) | default parameters | rules_only | 47/250 (18.8%) | 14.4-24.1% | 250 | +0.0 points against default; most binding: GND-TURNAROUND in 42 |
| NO_DEAL rate, late_aircraft, surplus_pre_departure_min=(-10, 5) | default parameters | rules_only | 63/250 (25.2%) | 20.2-30.9% | 250 | +6.4 points against default; most binding: GND-TURNAROUND in 42 |
| NO_DEAL rate, late_aircraft, p_planned_gate_conflict=0.0 | default parameters | rules_only | 46/250 (18.4%) | 14.1-23.7% | 250 | -0.4 points against default; most binding: GND-TURNAROUND in 42 |

## Controls on hand-built scenarios [class: test]

Commit `24697acf15e5`, mode `off`, seed 0, sample size 18, 2026-10-31T04:21:02+00:00.

| Measure | Compared against | Class | Value | 95% Wilson | n | Note |
|---|---|---|---|---|---|---|
| Rules defended: injected violation caught, and noticed when disabled | one injected unsafe package per rule, then a mutation run per rule | test | 9/9 (100.0%) | 70.1-100.0% | 9 |  |
| Rule ATC-WAKE-SEP: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | wake_spacing_1_min |
| Rule ATC-RWY-CLOSED: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | closed_runway |
| Rule ATC-TWY-CLOSED: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | closed_taxiway |
| Rule ATC-RWY-THROUGHPUT: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | runway_over_hourly_cap |
| Rule ATC-SLOT-WINDOW: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | slot_off_the_grid |
| Rule PLT-FUEL-POLICY: DEFENDED | injected case and mutation | test | 3 cases defended |  | 3 | fuel_below_reserve, hold_before_departure, direct_cannot_absorb_delay |
| Rule GND-GATE-OVERLAP: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | gate_overlap |
| Rule GND-GATE-SIZE: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | aircraft_too_big_for_gate |
| Rule GND-TURNAROUND: DEFENDED | injected case and mutation | test | 1 cases defended |  | 1 | turnaround_too_short |
| Mutants that make the decision pick the unsafe package | rule disabled, cheapest package breaks it | test | 8/8 (100.0%) | 67.6-100.0% | 8 |  |
| Injected violations the harm check also flags | independent harm check, in its scope only | test | 6/6 (100.0%) | 61.0-100.0% | 6 |  |
| Controls that must succeed, on fallback.decide | expected answers worked by hand | test | 7/7 (100.0%) | 64.6-100.0% | 7 | positive runs and named failures |
| Controls that must succeed, through protocol mode off | expected answers worked by hand | test | 7/7 (100.0%) | 64.6-100.0% | 7 |  |
| Mode off runs labelled as a fault or a fallback trigger, never clean | plan: an LLM-off run is never logged as a clean fallback | test | 7/7 (100.0%) | 64.6-100.0% | 7 |  |
| Agents agreeing to anything, stopped by the protocol gate: unsafe package kept out | scripted agents through protocol, then the rule disabled | test | 8/8 (100.0%) | 67.6-100.0% | 8 |  |
| Agents agreeing to anything, stopped by the protocol gate: mutation noticed, unsafe package let through | scripted agents through protocol, then the rule disabled | test | 8/8 (100.0%) | 67.6-100.0% | 8 |  |
| Reply naming a package never offered ends in a fault | scripted hostile agents through protocol | test | 1/1 (100.0%) | 20.7-100.0% | 1 |  |
| Hand-calculated scenarios checked by someone who did not write the code | independent reviewer | test | NOT_REACHED |  |  | no independent reviewer has checked these; the author worked them |
| Input-sensitivity pairs on a hand-built scenario | close a runway, alter an unrelated flight | test | 6/6 (100.0%) | 61.0-100.0% | 6 |  |

## Needs a model, and none ran [class: rules_only]

Commit `24697acf15e5`, mode `off`, seed 0, sample size 5000, 2026-10-31T04:21:02+00:00.

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
- The rules are a subset of real ATC procedure, and binding counts partly describe our generator: see how NO_DEAL moves with its parameters above.
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
