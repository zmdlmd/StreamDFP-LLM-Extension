# pre-ARFF Grid (MC1, v1)

total_rows=24
baseline_recall=97.7704
baseline_acc=99.4956
grid_completion=compact9(12/12)+compact14(12/12)

- best: dim=compact14 q=0.0 sev=0.0 rule=0
- recall=100.0000 (delta_vs_nollm=+2.2296)
- acc=99.5489 (delta_vs_nollm=+0.0532)
- pass_acc_guard=True

## Dimension-level summary
- compact14: 12/12 finished; metrics stable across all gates (`recall=100.0000`, `acc=99.5489`)
- compact9: 12/12 finished; metrics stable across all gates (`recall=97.3780`, `acc=99.8322`)
- selection rule: prioritize recall under ACC guard => keep `compact14` as MC1 pilot default
