# LLM vs no-LLM 逐盘型鲁棒评估

- 验收约束: Recall(LLM) >= Recall(no-LLM), ACC(LLM) >= ACC(no-LLM) - 1.00pp

| model | status | action | recall_llm | recall_nollm | delta_recall | acc_llm | acc_nollm | delta_acc |
|---|---|---|---:|---:|---:|---:|---:|---:|
| hds5c3030ala630 | FALLBACK | nollm | 65.0000 | 95.0000 | -30.0000 | 99.8824 | 90.1123 | +9.7701 |
| hgsthms5c4040ale640 | PASS | llm_enabled | 75.8929 | 75.2381 | +0.6548 | 99.4447 | 99.3963 | +0.0483 |
| hitachihds5c4040ale630 | PASS | llm_enabled | 0.0000 | 0.0000 | +0.0000 | 99.9213 | 99.9213 | +0.0000 |
| st31500341as | PASS | llm_enabled | 70.2381 | 68.5714 | +1.6667 | 99.4381 | 99.3534 | +0.0847 |
| st4000dm000 | FALLBACK | nollm | 54.1005 | 57.9049 | -3.8043 | 99.9137 | 99.8795 | +0.0342 |
| wdcwd10eads | FALLBACK | nollm | 0.0000 | 90.0000 | -90.0000 | 99.7890 | 99.9789 | -0.1899 |
| wdcwd30efrx | PASS | llm_enabled | 30.0000 | 0.0000 | +30.0000 | 99.9003 | 99.8580 | +0.0423 |

## N/A / 回退说明
- hds5c3030ala630: recall/acc 未同时满足约束，建议上线回退 no-LLM
- st4000dm000: recall/acc 未同时满足约束，建议上线回退 no-LLM
- wdcwd10eads: recall/acc 未同时满足约束，建议上线回退 no-LLM
