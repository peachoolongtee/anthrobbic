# Before and after seeded planned-gate conflicts

- Before: commit `666ce5e45dd8c37a6c681cff76e695bf7a1c3888`, mode `off`, seed 0, sample size 5000, generated 2026-10-31T04:09:22+00:00, control failures: 0
- After: commit `24697acf15e518d51a5e79be5aab47f6e4567f25`, mode `off`, seed 0, sample size 5000, generated 2026-10-31T04:21:02+00:00, control failures: 0

Both runs are class `rules_only`. No model ran in either.

| Measure | Before | After |
|---|---|---|
| Deal rate, all rows | 4014/5000 (80.3%), 79.2-81.4% | 3961/5000 (79.2%), 78.1-80.3% |
| Deal rate, weather | 1903/2500 (76.1%), 74.4-77.8% | 1859/2500 (74.4%), 72.6-76.0% |
| Deal rate, late_aircraft | 2111/2500 (84.4%), 83.0-85.8% | 2102/2500 (84.1%), 82.6-85.5% |
| NO_DEAL NOTHING_LEGAL rate, all rows | 986/5000 (19.7%), 18.6-20.8% | 1039/5000 (20.8%), 19.7-21.9% |
| NO_DEAL SYSTEM_FAULT rate, all rows | 0/5000 (0.0%), 0.0-0.1% | 0/5000 (0.0%), 0.0-0.1% |
| Pick is no worse than every legal package on every cost component | 4014/4014 (100.0%), 99.9-100.0% | 3507/3961 (88.5%), 87.5-89.5% |
| Chosen package changes under at least one alternate weight | 0/4014 (0.0%), 0.0-0.1% | 68/3961 (1.7%), 1.4-2.2% |
| Chosen package has zero soft cost | 1683/4014 (41.9%), 40.4-43.5% | 1219/3961 (30.8%), 29.4-32.2% |
| Fallback picks the same package as human_heuristic | 3943/4014 (98.2%), 97.8-98.6% | 3626/3961 (91.5%), 90.6-92.4% |
| Fallback picks the same package as first_come_first_served | 283/4014 (7.1%), 6.3-7.9% | 366/3961 (9.2%), 8.4-10.2% |
| Final packages breaking a rule | 0/4014 (0.0%), 0.0-0.1% | 0/3961 (0.0%), 0.0-0.1% |
| Final packages the independent harm check calls harmful | 0/4014 (0.0%), 0.0-0.1% | 0/3961 (0.0%), 0.0-0.1% |
| harm.py versus rules: harm_only | 0/4014 (0.0%), 0.0-0.1% | 0/3961 (0.0%), 0.0-0.1% |
| harm.py versus rules: rules_only | 0/4014 (0.0%), 0.0-0.1% | 0/3961 (0.0%), 0.0-0.1% |
| first_come_first_served: packages breaking a rule | 4288/5000 (85.8%), 84.8-86.7% | 4369/5000 (87.4%), 86.4-88.3% |
| Chosen package changes across synthetic seeds | 4867/5000 (97.3%), 96.9-97.8% | 4852/5000 (97.0%), 96.5-97.5% |
| Outcome flips between deal and NO_DEAL across synthetic seeds | 1984/5000 (39.7%), 38.3-41.0% | 2058/5000 (41.2%), 39.8-42.5% |
| Delay past the scenario's earliest arrival, fallback | 2.1 min | 2.83 min |
| Delay past the scenario's earliest arrival, fallback minus human_heuristic, paired on the same window | 0 min | 0 min |
| Connection passengers at risk, fallback minus human_heuristic, paired on the same window | 0 pax | 0 pax |
| Legal packages per deal row | 46.17 packages | 42.36 packages |
