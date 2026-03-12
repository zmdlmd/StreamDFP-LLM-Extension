# all12 指标对比（含 NA 原因）

- 源文件: `docs/llm_vs_nollm_metrics_all12_summary.csv`
- 说明: NA 不是缺文件，而是指标在数学上无定义（例如 `TP+FP=0` 或 `TP=0`）。

## NA 盘型明细

- `hitachihds5c4040ale630`: precision差值=NA (UNDEFINED(both sides undefined: LLM=UNDEFINED(TP+FP=0; no predicted positives); noLLM=UNDEFINED(TP+FP=0; no predicted positives)))；F1差值=NA (UNDEFINED(both sides undefined: LLM=UNDEFINED(TP+FP=0; no predicted positives); noLLM=UNDEFINED(TP+FP=0; no predicted positives)))；Days差值=NA (UNDEFINED(both sides undefined: LLM=UNDEFINED(TP=0; no true positives); noLLM=UNDEFINED(TP=0; no true positives)))；支持计数均值: LLM(TP=0.0,FP=0.0,FN=2.0), noLLM(TP=0.0,FP=0.0,FN=2.0)
- `wdcwd10eads`: precision差值=NA (UNDEFINED(LLM side undefined: UNDEFINED(TP+FP=0; no predicted positives)))；F1差值=NA (UNDEFINED(LLM side undefined: UNDEFINED(TP+FP=0; no predicted positives)))；Days差值=NA (UNDEFINED(LLM side undefined: UNDEFINED(TP=0; no true positives)))；支持计数均值: LLM(TP=0.0,FP=0.0,FN=1.0), noLLM(TP=0.9,FP=0.0,FN=0.1)
- `wdcwd30efrx`: precision差值=NA (UNDEFINED(noLLM side undefined: UNDEFINED(TP+FP=0; no predicted positives)))；F1差值=NA (UNDEFINED(noLLM side undefined: UNDEFINED(TP+FP=0; no predicted positives)))；Days差值=NA (UNDEFINED(noLLM side undefined: UNDEFINED(TP=0; no true positives)))；支持计数均值: LLM(TP=0.3,FP=0.0,FN=0.7), noLLM(TP=0.0,FP=0.0,FN=1.0)
