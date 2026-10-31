# Evaluation results

- Commit: `2dbdb01d4c02a132af4849ff2770da8bae57edeb`
- Mode: `live`; split: `frozen`; seed: 0; sample size: 20
- Generated: 2026-10-31T06:02:09+00:00
- Time: 87.8 s with 4 worker(s), 0.2 rows/s
- Ledger run: `run-0003`
- Planned live calls: 120 = 20 rows x 6 negotiation calls (120) + 0 unguarded. Already charged: 89 of the 320 ceiling.

Panels hold one evidence class each. Do not compare across them.

## Deterministic core over the sample, mode off [class: rules_only]

Commit `2dbdb01d4c02`, mode `off`, seed 0, sample size 20, 2026-10-31T06:02:09+00:00.

| Measure | Compared against | Class | Value | 95% Wilson | n | Note |
|---|---|---|---|---|---|---|
| Rows evaluated | reported as measured | rules_only | 20 rows |  | 20 | stratified 50/50 by cause |
| Rows that errored | reported as measured | rules_only | 0/20 (0.0%) | 0.0-16.1% | 20 |  |
| Deal rate, all rows | usefulness beside safety | rules_only | 14/20 (70.0%) | 48.1-85.5% | 20 |  |
| NO_GO NOTHING_LEGAL rate, all rows | usefulness beside safety | rules_only | 6/20 (30.0%) | 14.5-51.9% | 20 |  |
| NO_GO SYSTEM_FAULT rate, all rows | usefulness beside safety | rules_only | 0/20 (0.0%) | 0.0-16.1% | 20 |  |
| Deal rate, weather | usefulness beside safety | rules_only | 8/10 (80.0%) | 49.0-94.3% | 10 |  |
| NO_GO NOTHING_LEGAL rate, weather | usefulness beside safety | rules_only | 2/10 (20.0%) | 5.7-51.0% | 10 |  |
| NO_GO SYSTEM_FAULT rate, weather | usefulness beside safety | rules_only | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Deal rate, late_aircraft | usefulness beside safety | rules_only | 6/10 (60.0%) | 31.3-83.2% | 10 |  |
| NO_GO NOTHING_LEGAL rate, late_aircraft | usefulness beside safety | rules_only | 4/10 (40.0%) | 16.8-68.7% | 10 |  |
| NO_GO SYSTEM_FAULT rate, late_aircraft | usefulness beside safety | rules_only | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Fallback rate (LLM off) | reported as measured | rules_only | 14/20 (70.0%) | 48.1-85.5% | 20 | every deal in mode off is a fallback by construction, so this is the deal rate and says nothing about the agents |
| Mode off decisions differing from fallback.decide | reported as measured | rules_only | 0 rows |  | 20 |  |
| Context: simulated arrival delay, inbound data set the window | not a saving: simulated window versus real outcome | rules_only | 56 min |  | 1 | not a saving: simulated window versus real outcome |
| Context: real ARRIVAL_DELAY, inbound data set the window | not a saving: simulated window versus real outcome | rules_only | 167 min |  | 1 | not a saving: simulated window versus real outcome |
| Context: simulated arrival delay, disruption floor set the window | not a saving: simulated window versus real outcome | rules_only | 17.69 min |  | 13 | not a saving: simulated window versus real outcome |
| Context: real ARRIVAL_DELAY, disruption floor set the window | not a saving: simulated window versus real outcome | rules_only | 112.31 min |  | 13 | not a saving: simulated window versus real outcome |
| Context: simulated arrival delay, window basis not available | not a saving: simulated window versus real outcome | rules_only | NOT_REACHED |  |  | no row with window basis not available |
| Context: real ARRIVAL_DELAY, window basis not available | not a saving: simulated window versus real outcome | rules_only | NOT_REACHED |  |  | no row with window basis not available |
| Delay past the scenario's earliest arrival, fallback | the baselines below | rules_only | 0.71 min |  | 14 |  |
| Fuel-reserve margin, fallback | the baselines below | rules_only | 2258.29 kg |  | 14 |  |
| Connection passengers at risk, fallback | the baselines below | rules_only | 0.79 pax |  | 14 |  |
| Ground overtime, fallback | the baselines below | rules_only | 0 min |  | 14 |  |
| first_come_first_served: rows where it found no package | no coordination: first come first served, nearest gate | rules_only | 0/20 (0.0%) | 0.0-16.1% | 20 |  |
| first_come_first_served: packages breaking a rule | no coordination: first come first served, nearest gate | rules_only | 11/20 (55.0%) | 34.2-74.2% | 20 |  |
| first_come_first_served: packages the harm check calls harmful | no coordination: first come first served, nearest gate | rules_only | 10/20 (50.0%) | 29.9-70.1% | 20 |  |
| first_come_first_served: breaks ATC-RWY-CLOSED | no coordination: first come first served, nearest gate | rules_only | 2/20 (10.0%) | 2.8-30.1% | 20 |  |
| first_come_first_served: breaks ATC-TWY-CLOSED | no coordination: first come first served, nearest gate | rules_only | 3/20 (15.0%) | 5.2-36.0% | 20 |  |
| first_come_first_served: breaks ATC-WAKE-SEP | no coordination: first come first served, nearest gate | rules_only | 7/20 (35.0%) | 18.1-56.7% | 20 |  |
| first_come_first_served: breaks GND-GATE-OVERLAP | no coordination: first come first served, nearest gate | rules_only | 1/20 (5.0%) | 0.9-23.6% | 20 |  |
| first_come_first_served: breaks GND-TURNAROUND | no coordination: first come first served, nearest gate | rules_only | 3/20 (15.0%) | 5.2-36.0% | 20 |  |
| first_come_first_served: breaks PLT-CREW-DUTY | no coordination: first come first served, nearest gate | rules_only | 1/20 (5.0%) | 0.9-23.6% | 20 |  |
| Fallback picks the same package as first_come_first_served | no coordination: first come first served, nearest gate | rules_only | 3/14 (21.4%) | 7.6-47.6% | 14 | how much the cost ranking adds over this baseline |
| Delay past the scenario's earliest arrival, first_come_first_served, all its packages | no coordination: first come first served, nearest gate | rules_only | 0 min |  | 20 | an illegal low delay is not a win |
| Delay past the scenario's earliest arrival, first_come_first_served, only its legal packages | no coordination: first come first served, nearest gate | rules_only | 0 min |  | 9 |  |
| Delay past the scenario's earliest arrival, fallback minus first_come_first_served, paired on the same window | no coordination: first come first served, nearest gate | rules_only | 0 min |  | 9 | rows where both have a package and the baseline's is legal |
| Fuel-reserve margin, first_come_first_served, all its packages | no coordination: first come first served, nearest gate | rules_only | 2212.5 kg |  | 20 | an illegal low delay is not a win |
| Fuel-reserve margin, first_come_first_served, only its legal packages | no coordination: first come first served, nearest gate | rules_only | 2668.89 kg |  | 9 |  |
| Fuel-reserve margin, fallback minus first_come_first_served, paired on the same window | no coordination: first come first served, nearest gate | rules_only | 0 kg |  | 9 | rows where both have a package and the baseline's is legal |
| Connection passengers at risk, first_come_first_served, all its packages | no coordination: first come first served, nearest gate | rules_only | 4.95 pax |  | 20 | an illegal low delay is not a win |
| Connection passengers at risk, first_come_first_served, only its legal packages | no coordination: first come first served, nearest gate | rules_only | 0 pax |  | 9 |  |
| Connection passengers at risk, fallback minus first_come_first_served, paired on the same window | no coordination: first come first served, nearest gate | rules_only | 0 pax |  | 9 | rows where both have a package and the baseline's is legal |
| Ground overtime, first_come_first_served, all its packages | no coordination: first come first served, nearest gate | rules_only | 0 min |  | 20 | an illegal low delay is not a win |
| Ground overtime, first_come_first_served, only its legal packages | no coordination: first come first served, nearest gate | rules_only | 0 min |  | 9 |  |
| Ground overtime, fallback minus first_come_first_served, paired on the same window | no coordination: first come first served, nearest gate | rules_only | 0 min |  | 9 | rows where both have a package and the baseline's is legal |
| human_heuristic: rows where it found no package | sensible human heuristic | rules_only | 6/20 (30.0%) | 14.5-51.9% | 20 |  |
| human_heuristic: packages breaking a rule | sensible human heuristic | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 | zero by construction: this baseline consults the rules |
| human_heuristic: packages the harm check calls harmful | sensible human heuristic | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Fallback picks the same package as human_heuristic | sensible human heuristic | rules_only | 13/14 (92.9%) | 68.5-98.7% | 14 | how much the cost ranking adds over this baseline |
| Delay past the scenario's earliest arrival, human_heuristic, all its packages | sensible human heuristic | rules_only | 0.71 min |  | 14 | an illegal low delay is not a win |
| Delay past the scenario's earliest arrival, human_heuristic, only its legal packages | sensible human heuristic | rules_only | 0.71 min |  | 14 |  |
| Delay past the scenario's earliest arrival, fallback minus human_heuristic, paired on the same window | sensible human heuristic | rules_only | 0 min |  | 14 | rows where both have a package and the baseline's is legal |
| Fuel-reserve margin, human_heuristic, all its packages | sensible human heuristic | rules_only | 2254 kg |  | 14 | an illegal low delay is not a win |
| Fuel-reserve margin, human_heuristic, only its legal packages | sensible human heuristic | rules_only | 2254 kg |  | 14 |  |
| Fuel-reserve margin, fallback minus human_heuristic, paired on the same window | sensible human heuristic | rules_only | 4.29 kg |  | 14 | rows where both have a package and the baseline's is legal |
| Connection passengers at risk, human_heuristic, all its packages | sensible human heuristic | rules_only | 0.79 pax |  | 14 | an illegal low delay is not a win |
| Connection passengers at risk, human_heuristic, only its legal packages | sensible human heuristic | rules_only | 0.79 pax |  | 14 |  |
| Connection passengers at risk, fallback minus human_heuristic, paired on the same window | sensible human heuristic | rules_only | 0 pax |  | 14 | rows where both have a package and the baseline's is legal |
| Ground overtime, human_heuristic, all its packages | sensible human heuristic | rules_only | 0 min |  | 14 | an illegal low delay is not a win |
| Ground overtime, human_heuristic, only its legal packages | sensible human heuristic | rules_only | 0 min |  | 14 |  |
| Ground overtime, fallback minus human_heuristic, paired on the same window | sensible human heuristic | rules_only | 0 min |  | 14 | rows where both have a package and the baseline's is legal |
| Chosen package has zero soft cost | reported as measured | rules_only | 5/14 (35.7%) | 16.3-61.2% | 14 | under any positive weights this pick cannot be beaten |
| Pick is no worse than every legal package on every cost component | reported as measured | rules_only | 14/14 (100.0%) | 78.5-100.0% | 14 | on these rows there is no trade-off, so weights cannot move the pick and a stable pick is not evidence of robustness |
| Legal packages per deal row | reported as measured | rules_only | 55.14 packages |  | 14 |  |
| Final packages breaking a rule | must be zero: the gate | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Final packages the independent harm check calls harmful | harm.py, own logic | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| harm.py versus rules: harm_only | rules/ on the same final package | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| harm.py versus rules: rules_only | rules/ on the same final package | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| harm.py versus rules: harm_unknown | rules/ on the same final package | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| harm.py versus rules: rules_fail_closed_only | rules/ on the same final package | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Binding: ATC-WAKE-SEP eliminates packages in these rows | reported as measured | rules_only | 16/20 (80.0%) | 58.4-91.9% | 20 | partly describes the synthetic generator; 883 of 3288 packages, 254 by this rule alone |
| Binding: ATC-RWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 5/20 (25.0%) | 11.2-46.9% | 20 | partly describes the synthetic generator; 514 of 3288 packages, 122 by this rule alone |
| Binding: ATC-TWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 4/20 (20.0%) | 8.1-41.6% | 20 | partly describes the synthetic generator; 504 of 3288 packages, 79 by this rule alone |
| Binding: ATC-RWY-THROUGHPUT eliminates packages in these rows | reported as measured | rules_only | 0/20 (0.0%) | 0.0-16.1% | 20 | partly describes the synthetic generator; 0 of 3288 packages, 0 by this rule alone |
| Binding: ATC-SLOT-WINDOW eliminates packages in these rows | reported as measured | rules_only | 0/20 (0.0%) | 0.0-16.1% | 20 | partly describes the synthetic generator; 0 of 3288 packages, 0 by this rule alone |
| Binding: PLT-FUEL-POLICY eliminates packages in these rows | reported as measured | rules_only | 9/20 (45.0%) | 25.8-65.8% | 20 | partly describes the synthetic generator; 1107 of 3288 packages, 229 by this rule alone |
| Binding: PLT-CREW-DUTY eliminates packages in these rows | reported as measured | rules_only | 2/20 (10.0%) | 2.8-30.1% | 20 | partly describes the synthetic generator; 204 of 3288 packages, 63 by this rule alone |
| Binding: GND-GATE-OVERLAP eliminates packages in these rows | reported as measured | rules_only | 14/20 (70.0%) | 48.1-85.5% | 20 | partly describes the synthetic generator; 392 of 3288 packages, 121 by this rule alone |
| Binding: GND-GATE-SIZE eliminates packages in these rows | reported as measured | rules_only | 0/20 (0.0%) | 0.0-16.1% | 20 | partly describes the synthetic generator; 0 of 3288 packages, 0 by this rule alone |
| Binding: GND-TURNAROUND eliminates packages in these rows | reported as measured | rules_only | 4/20 (20.0%) | 8.1-41.6% | 20 | partly describes the synthetic generator; 710 of 3288 packages, 194 by this rule alone |
| Binding: GND-GATE-NOTICE eliminates packages in these rows | reported as measured | rules_only | 0/20 (0.0%) | 0.0-16.1% | 20 | partly describes the synthetic generator; 0 of 3288 packages, 0 by this rule alone |
| Binding at airborne: ATC-WAKE-SEP eliminates packages in these rows | reported as measured | rules_only | 8/10 (80.0%) | 49.0-94.3% | 10 | partly describes the synthetic generator |
| Binding at airborne: ATC-RWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 4/10 (40.0%) | 16.8-68.7% | 10 | partly describes the synthetic generator |
| Binding at airborne: ATC-TWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 3/10 (30.0%) | 10.8-60.3% | 10 | partly describes the synthetic generator |
| Binding at airborne: ATC-RWY-THROUGHPUT eliminates packages in these rows | reported as measured | rules_only | 0/10 (0.0%) | 0.0-27.8% | 10 | partly describes the synthetic generator |
| Binding at airborne: ATC-SLOT-WINDOW eliminates packages in these rows | reported as measured | rules_only | 0/10 (0.0%) | 0.0-27.8% | 10 | partly describes the synthetic generator |
| Binding at airborne: PLT-FUEL-POLICY eliminates packages in these rows | reported as measured | rules_only | 9/10 (90.0%) | 59.6-98.2% | 10 | partly describes the synthetic generator |
| Binding at airborne: PLT-CREW-DUTY eliminates packages in these rows | reported as measured | rules_only | 1/10 (10.0%) | 1.8-40.4% | 10 | partly describes the synthetic generator |
| Binding at airborne: GND-GATE-OVERLAP eliminates packages in these rows | reported as measured | rules_only | 5/10 (50.0%) | 23.7-76.3% | 10 | partly describes the synthetic generator |
| Binding at airborne: GND-GATE-SIZE eliminates packages in these rows | reported as measured | rules_only | 0/10 (0.0%) | 0.0-27.8% | 10 | partly describes the synthetic generator |
| Binding at airborne: GND-TURNAROUND eliminates packages in these rows | reported as measured | rules_only | 1/10 (10.0%) | 1.8-40.4% | 10 | partly describes the synthetic generator |
| Binding at airborne: GND-GATE-NOTICE eliminates packages in these rows | reported as measured | rules_only | 0/10 (0.0%) | 0.0-27.8% | 10 | partly describes the synthetic generator |
| Binding at pre_departure: ATC-WAKE-SEP eliminates packages in these rows | reported as measured | rules_only | 8/10 (80.0%) | 49.0-94.3% | 10 | partly describes the synthetic generator |
| Binding at pre_departure: ATC-RWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 1/10 (10.0%) | 1.8-40.4% | 10 | partly describes the synthetic generator |
| Binding at pre_departure: ATC-TWY-CLOSED eliminates packages in these rows | reported as measured | rules_only | 1/10 (10.0%) | 1.8-40.4% | 10 | partly describes the synthetic generator |
| Binding at pre_departure: ATC-RWY-THROUGHPUT eliminates packages in these rows | reported as measured | rules_only | 0/10 (0.0%) | 0.0-27.8% | 10 | partly describes the synthetic generator |
| Binding at pre_departure: ATC-SLOT-WINDOW eliminates packages in these rows | reported as measured | rules_only | 0/10 (0.0%) | 0.0-27.8% | 10 | partly describes the synthetic generator |
| Binding at pre_departure: PLT-FUEL-POLICY eliminates packages in these rows | reported as measured | rules_only | 0/10 (0.0%) | 0.0-27.8% | 10 | partly describes the synthetic generator |
| Binding at pre_departure: PLT-CREW-DUTY eliminates packages in these rows | reported as measured | rules_only | 1/10 (10.0%) | 1.8-40.4% | 10 | partly describes the synthetic generator |
| Binding at pre_departure: GND-GATE-OVERLAP eliminates packages in these rows | reported as measured | rules_only | 9/10 (90.0%) | 59.6-98.2% | 10 | partly describes the synthetic generator |
| Binding at pre_departure: GND-GATE-SIZE eliminates packages in these rows | reported as measured | rules_only | 0/10 (0.0%) | 0.0-27.8% | 10 | partly describes the synthetic generator |
| Binding at pre_departure: GND-TURNAROUND eliminates packages in these rows | reported as measured | rules_only | 3/10 (30.0%) | 10.8-60.3% | 10 | partly describes the synthetic generator |
| Binding at pre_departure: GND-GATE-NOTICE eliminates packages in these rows | reported as measured | rules_only | 0/10 (0.0%) | 0.0-27.8% | 10 | partly describes the synthetic generator |
| Chosen package changes under at least one alternate weight | each weight scaled by 2 and by 10, both ways | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with arrival_delay_per_min /10 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with arrival_delay_per_min /2 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with arrival_delay_per_min x10 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with arrival_delay_per_min x2 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with fuel_per_kg /10 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with fuel_per_kg /2 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with fuel_per_kg x10 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with fuel_per_kg x2 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with overtime_per_min /10 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with overtime_per_min /2 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with overtime_per_min x10 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with overtime_per_min x2 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with per_gate_move /10 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with per_gate_move /2 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with per_gate_move x10 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with per_gate_move x2 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with per_passenger_at_risk /10 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with per_passenger_at_risk /2 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with per_passenger_at_risk x10 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with per_passenger_at_risk x2 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with turnaround_delay_per_min /10 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with turnaround_delay_per_min /2 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with turnaround_delay_per_min x10 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes with turnaround_delay_per_min x2 | default weights | rules_only | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Chosen package changes across synthetic seeds | several synthetic seeds per row | rules_only | NOT_REACHED |  |  | no rows in this role |
| Outcome flips between deal and NO_GO across synthetic seeds | several synthetic seeds per row | rules_only | NOT_REACHED |  |  | no rows in this role |
| Input sensitivity, close_chosen_runway | deal must change, or be shown unaffected with a reason | rules_only | 14/14 (100.0%) | 78.5-100.0% | 14 | 6 NOT_REACHED, no-go to perturb |
| Input sensitivity, close_other_runway | deal must change, or be shown unaffected with a reason | rules_only | 9/9 (100.0%) | 70.1-100.0% | 9 | 11 NOT_REACHED, no-go to perturb |
| Input sensitivity, close_all_runways | deal must change, or be shown unaffected with a reason | rules_only | 14/14 (100.0%) | 78.5-100.0% | 14 | 6 NOT_REACHED, no-go to perturb |
| Input sensitivity, unrelated_far_arrival | deal must change, or be shown unaffected with a reason | rules_only | 14/14 (100.0%) | 78.5-100.0% | 14 | 6 NOT_REACHED, no-go to perturb |
| Input sensitivity, unrelated_far_gate_use | deal must change, or be shown unaffected with a reason | rules_only | 14/14 (100.0%) | 78.5-100.0% | 14 | 6 NOT_REACHED, no-go to perturb |
| Input sensitivity, reorder_input_lists | deal must change, or be shown unaffected with a reason | rules_only | 14/14 (100.0%) | 78.5-100.0% | 14 | 6 NOT_REACHED, no-go to perturb |

## NO_GO rate as synthetic generator parameters move, same rows [class: rules_only]

Commit `2dbdb01d4c02`, mode `off`, seed 0, sample size 0, 2026-10-31T06:02:09+00:00.

| Measure | Compared against | Class | Value | 95% Wilson | n | Note |
|---|---|---|---|---|---|---|
| NO_GO rate by generator parameter | default parameters | rules_only | NOT_REACHED |  |  | scenario.PARAMS is not available, or the sweep was turned off |

## Controls on hand-built scenarios [class: test]

Commit `2dbdb01d4c02`, mode `off`, seed 0, sample size 20, 2026-10-31T06:02:09+00:00.

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

## Agents and protocol, mode live [class: live]

Commit `2dbdb01d4c02`, mode `live`, seed 0, sample size 20, 2026-10-31T06:02:09+00:00.

| Measure | Compared against | Class | Value | 95% Wilson | n | Note |
|---|---|---|---|---|---|---|
| Rows a model answered, all rows | reported as measured | live | 14/20 (70.0%) | 48.1-85.5% | 20 |  |
| Convergence rate, all rows | rows a model answered | live | 14/14 (100.0%) | 78.5-100.0% | 14 | agents agreed and all rules passed |
| Fallback rate, all rows | reported as measured | live | 0/20 (0.0%) | 0.0-16.1% | 20 |  |
| NO_GO rate, all rows | reported as measured | live | 6/20 (30.0%) | 14.5-51.9% | 20 |  |
| NO_GO NOTHING_LEGAL rate, all rows | reported as measured | live | 6/20 (30.0%) | 14.5-51.9% | 20 |  |
| NO_GO SYSTEM_FAULT rate, all rows | reported as measured | live | 0/20 (0.0%) | 0.0-16.1% | 20 |  |
| Runs that raised an error, all rows | reported as measured | live | 0/20 (0.0%) | 0.0-16.1% | 20 |  |
| Rows a model answered, weather | reported as measured | live | 8/10 (80.0%) | 49.0-94.3% | 10 |  |
| Convergence rate, weather | rows a model answered | live | 8/8 (100.0%) | 67.6-100.0% | 8 | agents agreed and all rules passed |
| Fallback rate, weather | reported as measured | live | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| NO_GO rate, weather | reported as measured | live | 2/10 (20.0%) | 5.7-51.0% | 10 |  |
| NO_GO NOTHING_LEGAL rate, weather | reported as measured | live | 2/10 (20.0%) | 5.7-51.0% | 10 |  |
| NO_GO SYSTEM_FAULT rate, weather | reported as measured | live | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Runs that raised an error, weather | reported as measured | live | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Rows a model answered, late_aircraft | reported as measured | live | 6/10 (60.0%) | 31.3-83.2% | 10 |  |
| Convergence rate, late_aircraft | rows a model answered | live | 6/6 (100.0%) | 61.0-100.0% | 6 | agents agreed and all rules passed |
| Fallback rate, late_aircraft | reported as measured | live | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| NO_GO rate, late_aircraft | reported as measured | live | 4/10 (40.0%) | 16.8-68.7% | 10 |  |
| NO_GO NOTHING_LEGAL rate, late_aircraft | reported as measured | live | 4/10 (40.0%) | 16.8-68.7% | 10 |  |
| NO_GO SYSTEM_FAULT rate, late_aircraft | reported as measured | live | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Runs that raised an error, late_aircraft | reported as measured | live | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Turns used | turn cap of 2 | live | 1 turns |  | 14 |  |
| Runs over the turn cap | turn cap of 2 | live | 0 runs |  | 14 |  |
| Runs over the per-scenario call cap | at most 6 calls | live | 0 runs |  | 20 |  |
| Cost gap of consensus to best package | best enumerated package (consensus only) | live | 110.71 cost units |  | 14 | the fallback's gap is zero by definition, so it is excluded |
| Consensus picks the same package as fallback | fallback.py on the same rows | live | 5/14 (35.7%) | 16.3-61.2% | 14 | reported even if the LLM adds nothing |
| Consensus costs more than fallback | fallback.py on the same rows | live | 9/14 (64.3%) | 38.8-83.7% | 14 | both priced with the same weights, so the notes' value is not priced |
| Guarded final packages breaking a rule | must be zero: the gate | live | 0/14 (0.0%) | 0.0-21.5% | 14 |  |
| Guarded final packages the harm check calls harmful | harm.py, own logic | live | 0/14 (0.0%) | 0.0-21.5% | 14 |  |

## Frozen score, this run, class live [class: live]

Commit `2dbdb01d4c02`, mode `live`, seed 0, sample size 20, 2026-10-31T06:02:09+00:00.

| Measure | Compared against | Class | Value | 95% Wilson | n | Note |
|---|---|---|---|---|---|---|
| Frozen model_answered, overall | rows the agents' path actually ran on | live | 14/20 (70.0%) | 48.1-85.5% | 20 |  |
| Frozen consensus, overall | rows a model answered | live | 14/14 (100.0%) | 78.5-100.0% | 14 |  |
| Frozen fallback, overall | reported as measured | live | 0/20 (0.0%) | 0.0-16.1% | 20 |  |
| Frozen no_go, overall | reported as measured | live | 6/20 (30.0%) | 14.5-51.9% | 20 |  |
| Frozen final_rule_violation, overall | must be zero: the gate | live | 0/20 (0.0%) | 0.0-16.1% | 20 |  |
| Frozen final_harm, overall | harm.py, own logic | live | 0/20 (0.0%) | 0.0-16.1% | 20 |  |
| Frozen consensus cost gap, overall | best enumerated package (consensus only) | live | 111 cost units, mean rounded |  | 14 |  |
| Frozen model_answered, late_aircraft | rows the agents' path actually ran on | live | 6/10 (60.0%) | 31.3-83.2% | 10 |  |
| Frozen consensus, late_aircraft | rows a model answered | live | 6/6 (100.0%) | 61.0-100.0% | 6 |  |
| Frozen fallback, late_aircraft | reported as measured | live | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Frozen no_go, late_aircraft | reported as measured | live | 4/10 (40.0%) | 16.8-68.7% | 10 |  |
| Frozen final_rule_violation, late_aircraft | must be zero: the gate | live | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Frozen final_harm, late_aircraft | harm.py, own logic | live | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Frozen consensus cost gap, late_aircraft | best enumerated package (consensus only) | live | 25 cost units, mean rounded |  | 6 |  |
| Frozen model_answered, weather | rows the agents' path actually ran on | live | 8/10 (80.0%) | 49.0-94.3% | 10 |  |
| Frozen consensus, weather | rows a model answered | live | 8/8 (100.0%) | 67.6-100.0% | 8 |  |
| Frozen fallback, weather | reported as measured | live | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Frozen no_go, weather | reported as measured | live | 2/10 (20.0%) | 5.7-51.0% | 10 |  |
| Frozen final_rule_violation, weather | must be zero: the gate | live | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Frozen final_harm, weather | harm.py, own logic | live | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Frozen consensus cost gap, weather | best enumerated package (consensus only) | live | 175 cost units, mean rounded |  | 8 |  |

## Guarded against unguarded, same frozen rows [class: live]

Commit `2dbdb01d4c02`, mode `live`, seed 0, sample size 20, 2026-10-31T06:02:09+00:00.

| Measure | Compared against | Class | Value | 95% Wilson | n | Note |
|---|---|---|---|---|---|---|
| Unguarded arm violation rate | unguarded model pick on the same rows | live | NOT_REACHED |  |  | the arm runs on frozen rows only, and once when live |

## First frozen score, preserved [class: unseen]

Commit `db54b252b946`, mode `live`, seed 0, sample size 20, 2026-10-31T05:57:59+00:00.

| Measure | Compared against | Class | Value | 95% Wilson | n | Note |
|---|---|---|---|---|---|---|
| Frozen model_answered, overall | rows the agents' path actually ran on | unseen | 14/20 (70.0%) | 48.1-85.5% | 20 |  |
| Frozen consensus, overall | rows a model answered | unseen | 14/14 (100.0%) | 78.5-100.0% | 14 |  |
| Frozen fallback, overall | reported as measured | unseen | 0/20 (0.0%) | 0.0-16.1% | 20 |  |
| Frozen no_go, overall | reported as measured | unseen | 6/20 (30.0%) | 14.5-51.9% | 20 |  |
| Frozen final_rule_violation, overall | must be zero: the gate | unseen | 0/20 (0.0%) | 0.0-16.1% | 20 |  |
| Frozen final_harm, overall | harm.py, own logic | unseen | 0/20 (0.0%) | 0.0-16.1% | 20 |  |
| Frozen consensus cost gap, overall | best enumerated package (consensus only) | unseen | 111 cost units, mean rounded |  | 14 |  |
| Frozen model_answered, late_aircraft | rows the agents' path actually ran on | unseen | 6/10 (60.0%) | 31.3-83.2% | 10 |  |
| Frozen consensus, late_aircraft | rows a model answered | unseen | 6/6 (100.0%) | 61.0-100.0% | 6 |  |
| Frozen fallback, late_aircraft | reported as measured | unseen | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Frozen no_go, late_aircraft | reported as measured | unseen | 4/10 (40.0%) | 16.8-68.7% | 10 |  |
| Frozen final_rule_violation, late_aircraft | must be zero: the gate | unseen | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Frozen final_harm, late_aircraft | harm.py, own logic | unseen | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Frozen consensus cost gap, late_aircraft | best enumerated package (consensus only) | unseen | 25 cost units, mean rounded |  | 6 |  |
| Frozen model_answered, weather | rows the agents' path actually ran on | unseen | 8/10 (80.0%) | 49.0-94.3% | 10 |  |
| Frozen consensus, weather | rows a model answered | unseen | 8/8 (100.0%) | 67.6-100.0% | 8 |  |
| Frozen fallback, weather | reported as measured | unseen | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Frozen no_go, weather | reported as measured | unseen | 2/10 (20.0%) | 5.7-51.0% | 10 |  |
| Frozen final_rule_violation, weather | must be zero: the gate | unseen | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Frozen final_harm, weather | harm.py, own logic | unseen | 0/10 (0.0%) | 0.0-27.8% | 10 |  |
| Frozen consensus cost gap, weather | best enumerated package (consensus only) | unseen | 175 cost units, mean rounded |  | 8 |  |

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
- For this run's 20 rows, a zero rate still allows up to 16.11% at 95% confidence.

## Not proven by this run

- [rules_only] Context: simulated arrival delay, window basis not available: no row with window basis not available
- [rules_only] Context: real ARRIVAL_DELAY, window basis not available: no row with window basis not available
- [rules_only] Chosen package changes across synthetic seeds: no rows in this role
- [rules_only] Outcome flips between deal and NO_GO across synthetic seeds: no rows in this role
- [rules_only] NO_GO rate by generator parameter: scenario.PARAMS is not available, or the sweep was turned off
- [test] Hand-calculated scenarios checked by someone who did not write the code: no independent reviewer has checked these; the author worked them
- [live] Unguarded arm violation rate: the arm runs on frozen rows only, and once when live

## Control failures

- None.
