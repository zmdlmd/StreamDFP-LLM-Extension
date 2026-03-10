# pre-ARFF Grid batch7 ZS Best v1

- source: `docs/prearff_grid_batch7_zs_v1.csv`
- models: 7
- PASS: 4 / 7

| model | status | action | dim | q | sev | rule | recall | Δrecall | acc | Δacc |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| hds5c3030ala630 | FALLBACK | nollm | full70 | 0.00 | 0.0 | 0 | 65.0000 | -30.0000 | 99.8824 | +9.7701 |
| hgsthms5c4040ale640 | PASS | llm_enabled | full70 | 0.00 | 0.0 | 0 | 75.8929 | +0.6548 | 99.4447 | +0.0483 |
| hitachihds5c4040ale630 | PASS | llm_enabled | compact9 | 0.00 | 0.0 | 0 | 0.0000 | +0.0000 | 99.9213 | +0.0000 |
| st31500341as | PASS | llm_enabled | compact9 | 0.00 | 0.8 | 0 | 70.2381 | +1.6667 | 99.4381 | +0.0847 |
| st4000dm000 | FALLBACK | nollm | compact14 | 0.00 | 0.0 | 0 | 54.1005 | -3.8043 | 99.9137 | +0.0342 |
| wdcwd10eads | FALLBACK | nollm | compact9 | 0.00 | 0.0 | 0 | 0.0000 | -90.0000 | 99.7890 | -0.1899 |
| wdcwd30efrx | PASS | llm_enabled | compact14 | 0.00 | 0.0 | 0 | 30.0000 | +30.0000 | 99.9003 | +0.0423 |

## Selected Result CSV

See the full per-combination table in `docs/prearff_grid_batch7_zs_v1.csv`.
