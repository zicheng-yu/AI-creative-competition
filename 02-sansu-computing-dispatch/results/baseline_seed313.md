# JS-ComputeSim-313 baseline episode, seed 313

One episode is 168 hourly steps. Absolute MWh, tonnes and CNY use the
sandbox coefficient `assumption_it_kw_per_eflops: 1000` in `configs/energy.yaml`.
They are not a provincial energy balance.
Random and least-loaded greedy ignore price and green power, so `green_surplus` matches `weekday` on placement and differs on carbon and green share. A price- or carbon-aware policy is what should move flexible load. Regenerate with:

```bash
python scripts/run_baselines.py --seed 313
```

| scenario | policy | served_ratio | sla_violation_ratio | mean_utilization | weighted_pue | energy_mwh | carbon_t | green_energy_share | cost_10k_cny | cross_domain_eflops | reward |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| weekday | random | 0.8109 | 0.1891 | 0.8873 | 1.3918 | 64801.7330 | 37615.8845 | 0.0280 | 4339.5601 | 2720.5613 | 50.2145 |
| weekday | greedy | 0.9404 | 0.0596 | 0.8464 | 1.3903 | 62963.5583 | 36517.3900 | 0.0288 | 4288.8947 | 3069.8185 | 131.4693 |
| green_surplus | random | 0.8109 | 0.1891 | 0.8873 | 1.3918 | 64801.7330 | 36144.9595 | 0.0660 | 4339.5601 | 2720.5613 | 50.3848 |
| green_surplus | greedy | 0.9404 | 0.0596 | 0.8464 | 1.3903 | 62963.5583 | 35046.4324 | 0.0679 | 4288.8947 | 3069.8185 | 131.6397 |
| peak_conservation | random | 0.6874 | 0.3126 | 0.9065 | 1.3927 | 62133.3623 | 36021.1673 | 0.0292 | 4035.9503 | 2671.8442 | -16.8144 |
| peak_conservation | greedy | 0.8043 | 0.1957 | 0.8921 | 1.3925 | 61783.4106 | 35810.8230 | 0.0294 | 4061.2650 | 3157.0522 | 59.8209 |
| node_failure | random | 0.8049 | 0.1951 | 0.8913 | 1.4077 | 64466.0228 | 37415.1237 | 0.0281 | 4314.9585 | 2745.9416 | 46.5022 |
| node_failure | greedy | 0.9337 | 0.0663 | 0.8541 | 1.4067 | 62854.6799 | 36451.9217 | 0.0289 | 4274.6887 | 3110.0727 | 127.6186 |
