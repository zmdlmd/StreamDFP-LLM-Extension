# LLM 接入（离线批处理 + Cache）

本阶段目标：
- LLM 仅用于**离线特征抽取**，输出结构化 JSON。
- JSON 映射为可配置维度向量 `z_llm`（由 event mapping 决定），通过 cache 复用。
- 训练阶段只读 cache，不依赖在线 LLM。
- 特征选择使用“盘型特征契约”（`pyloader/features_erg/contracts/<model_key>.txt`），避免盘型缺失列导致全量 `dropna` 清空样本。

## 改动点

- 新增：`llm/window_to_text.py`
  - 按项目原始特征清单将滑窗样本转换为文本（`disk_id/window_end_time/summary_text`）。
  - 可输出基于真实数据自动分析得到的 few-shot 参考样本。
  - 新增分层规则 Profile：`base -> medium -> vendor -> model -> --rule_config(显式覆盖)`。
  - 新增特征语义归一化：`smart_199_raw / r_199 / n_199 / 厂商别名` 会映射到统一 canonical key 后再做规则判断。
  - 归因分数改为“按可用特征归一”，并对 `workload` 使用动态门槛，避免不同型号可用特征数差异导致偏置。
  - 新增 reference 质量报告：覆盖率、非 unknown 比例、缺失根因等。
  - 支持固定结构化摘要契约：`--summary_schema structured_v2`，块顺序固定（`WINDOW/DATA_QUALITY/RULE_SCORE/RULE_TOP2/ALLOWED_EVENT_FEATURES/ANOMALY_TABLE/CAUSE_EVIDENCE/RULE_PRED`）。
  - 支持 `--summary_anomaly_top_k` 控制 `ANOMALY_TABLE` 行数，`--summary_emit_legacy_text` 可追加旧版辅助行。
- 修改：`llm/llm_offline_extract.py`
  - 改为读取 `window_to_text.py` 输出文本，再调用本地 LLM 生成 cache。
  - 支持 few-shot 覆盖门控（`auto/force/off`），`auto` 下覆盖不足自动回退 0-shot。
  - 使用短 JSON schema 抽取，并对输出执行归一化与 RULE_SCORE 门控。
  - 新增 `--prompt_profile legacy|structured_v2`，与摘要 schema 对齐。
  - 新增 `--event_type_policy legacy|strict`（strict 依据 persistence/trend/burst 纠正事件类型）。
  - 新增 `--rule_blend_mode three_stage|hard_gate`（默认 three_stage）。
  - 支持 `--event_mapping_config`，按数据集载入事件映射与维度。
- 新增：`llm/feature_mapping.py`
  - 将 JSON 映射为可配置维度向量（事件 one-hot + severity + root_cause 等）。
- 修改：`pyloader/run.py`
  - 新增开关与 cache 读取逻辑：`--use_llm_features 1` 时拼接 `z_llm_0..(llm_dim-1)`。
  - cache miss 记录到 `logs/llm_cache_miss.log`。

## 运行流程（端到端）

### 0) 先生成盘型特征契约（推荐）

```bash
python llm/scripts/build_feature_contracts.py \
  --data_root /root/autodl-tmp/StreamDFP/data/data_2014/2014 \
  --features_path /root/autodl-tmp/StreamDFP/pyloader/features_erg/hi7_all.txt \
  --date_format %Y-%m-%d \
  --train_start_date 2014-01-01 \
  --train_end_date 2014-08-31 \
  --disk_models "ST31500541AS,ST3000DM001,Hitachi HDS722020ALA330" \
  --out_dir /root/autodl-tmp/StreamDFP/pyloader/features_erg/contracts \
  --summary_out /root/autodl-tmp/StreamDFP/llm/contracts/feature_contract_batch_20140101_20140831.json \
  --min_non_null_ratio 0.99 \
  --fallback_non_null_ratios 0.95,0.9,0.8,0.5 \
  --min_features 5 \
  --overwrite
```

说明：
- 只使用训练期统计（防泄露）。
- 生成后的 contract 会同时喂给 `window_to_text.py` 与 `run.py`，保证同一盘型同一特征契约。
- 对缺失严重盘型会自动降阈值；仍不足 `min_features` 时走 `topk_backstop`，并在 summary 里标记。

### 1) 滑窗特征转文本（按盘型 contract）

```bash
python llm/window_to_text.py \
  --data_root /path/to/alibaba \
  --features_path pyloader/features_erg/contracts/hitachihds722020ala330.txt \
  --out llm/window_text_hi7.jsonl \
  --reference_out llm/reference_examples_hi7.json \
  --rule_profile auto \
  --rule_profile_dir llm/rules/profiles \
  --rule_medium auto \
  --summary_schema structured_v2 \
  --summary_anomaly_top_k 8 \
  --sample_mode stratified_day_disk \
  --sample_seed 42 \
  --reference_start_date 2014-01-01 \
  --reference_end_date 2014-08-31 \
  --reference_min_non_unknown 3 \
  --reference_fail_on_low_quality \
  --reference_quality_report_out llm/reference_quality_hi7.json
```

### 2) 文本喂 LLM 抽取并生成 cache

先安装 vLLM（可选，但推荐）：

```bash
pip install -U vllm
```

```bash
python llm/llm_offline_extract.py \
  --window_text_path llm/window_text_hi7.jsonl \
  --reference_examples llm/reference_examples_hi7.json \
  --dataset_profile hi7 \
  --fewshot_mode auto \
  --fewshot_min_per_cause 1 \
  --prompt_profile structured_v2 \
  --rule_blend_mode three_stage \
  --event_type_policy strict \
  --event_mapping_config llm/event_mapping_hi7.yaml \
  --out llm_cache.jsonl \
  --model /path/to/qwen-instruct \
  --batch_size 32 \
  --backend vllm \
  --rule_score_gate 0.8 \
  --vllm_tensor_parallel_size 1 \
  --vllm_gpu_memory_utilization 0.9 \
  --max_new_tokens 180 \
  --temperature 0 \
  --top_p 0.9
```

真实数据参考样本（项目内已生成）：
- `llm/reference_examples_real_hi7.json`
- 来源：`data/data_2014/2014`，`features_erg/hi7_all.txt`，抽样窗口数 `500000`。
- 该文件包含 `media/interface/temperature/power/unknown` 的真实窗口样本，作为 few-shot 提示上下文。

说明：
- `window_to_text.py` 和 `llm_offline_extract.py` 通过 `(disk_id, window_end_time)` 对齐，cache key 不变。
- `llm_offline_extract.py` 仍保留 `--data_root` 兼容模式，但建议使用两段式流程。
- `--backend auto` 会优先尝试 vLLM；若本机未安装 vLLM，会自动回退到 transformers。
- few-shot 默认建议 `--fewshot_mode auto`，若参考样本无法覆盖各类根因会自动禁用 few-shot，避免 unknown-only 偏置。
- `llm_offline_extract.py` 新增 `--dataset_profile hi7|mc1|hdd|ssd`，在未显式传 `--fewshot_required_causes` 时可自动套用数据集模板。
- 若 `reference_examples` 中含 `recommended_fewshot_required_causes`，会优先作为 few-shot 覆盖门槛。
- `window_text` 每行会写入 `rule_profile_id/rule_medium/rule_vendor/rule_model_key` 便于审计。
- `window_to_text.py` 新增 `--sample_mode stratified_day_disk`，可避免 `max_windows` 只截到最早日期造成的偏差。
- `window_to_text.py` 生成的 `reference_examples` 会写入 `recommended_fewshot_required_causes`，上游 few-shot 门槛会按数据集 profile 自动适配（HDD/SSD 不同）。
- `scripts/run_cross_model_llm_framework_v1.sh` 与 `scripts/run_framework_v1_phase3_grid.sh` 已支持 `FEATURE_CONTRACT_MODE=auto`：若 contract 缺失会自动调用 `build_feature_contracts.py` 生成。

### 2.1) 自动生成新型号规则骨架（可选）

当要扩展到大量新型号时，可先自动生成 model 层 skeleton，再人工补阈值：

```bash
python llm/scripts/generate_model_profile_skeletons.py \
  --data_root /path/to/data_root \
  --features_path pyloader/features_erg/xxx_all.txt \
  --profile_dir llm/rules/profiles \
  --out_dir llm/rules/profiles/model_skeletons \
  --min_feature_presence_ratio 0.2 \
  --min_rows_per_model 1000 \
  --summary_out llm/model_profile_skeleton_summary.json
```

说明：
- skeleton 默认继承 `base + medium + vendor`，只输出“相对父层缺失”的 feature 差异。
- 生成结果默认将新特征标为 `group=unknown, weight=0.70`，用于快速跑通，后续再按型号补充 root_cause 分组与阈值。

### 3) 生成 StreamDFP train/test（自动拼接 z_llm）

```bash
python pyloader/run.py \
  ...原参数... \
  --use_llm_features 1 \
  --llm_cache llm_cache.jsonl
```

说明：
- 若 cache 中缺失某个 `(disk_id, window_end_time)`，会回退为全 0 向量，并记录到 `logs/llm_cache_miss.log`。
- `z_llm` 维度由 event mapping 决定；训练时通过 `--llm_dim` 与 cache 对齐。

### 3.1) pre-ARFF 语义压缩（可选）

在不改训练器逻辑前提下，可先对 cache 做语义选维 + 前缀压缩：

```bash
python llm/scripts/build_cache_variant.py \
  --in_cache llm_cache.jsonl \
  --out_cache llm_cache_compact9.jsonl \
  --q_gate 0.0 \
  --sev_sum_gate 0.0 \
  --event_mapping_config llm/event_mapping_hi7.yaml \
  --keep_event_keys SMART_5:monotonic_increase,SMART_197:all,SMART_199 \
  --keep_meta_keys risk_hint,confidence,mapped_event_count \
  --compact_front
```

然后 `run.py` 使用：

```bash
python pyloader/run.py ... -U 1 -C llm_cache_compact9.jsonl -M 9
```

### 4) Java 在线训练（原命令不变）

```bash
bash run_xxx.sh
```

## LLM Prompt 模板（脚本内置）

System/Instruction：
```
你是一个信息抽取器。
你必须只输出一个严格 JSON 对象，不允许任何额外文字，不允许 markdown。
root_cause 必须严格等于以下之一：media/interface/temperature/power/workload/unknown。
root_cause 只能输出一个单词，禁止包含 "|" "/" 空格。
若证据不足，输出 unknown。
```

User 输入（`structured_v2`）：
```
Disk window summary:
WINDOW: 2014-02-12~2014-03-12 (29d) disk=...
DATA_QUALITY: valid_days=29 missing_ratio=0.03 active_features=4/34 known_features=18
RULE_SCORE: media=0.912 interface=0.000 temperature=0.000 power=0.000 workload=0.000
RULE_TOP2: media=0.912 interface=0.000 margin=0.912
ALLOWED_EVENT_FEATURES: SMART_5 SMART_197 SMART_198
ANOMALY_TABLE:
- feat=SMART_5|src=raw|mode=level|dir=high_bad|baseline=2.00|current=12.00|delta_pct=+333.0|abnormal_ratio=0.72|persistence=0.80|slope3=+0.210|slope14=+0.090|burst_ratio=1.10|severity=0.92|group=media
CAUSE_EVIDENCE: media=+SMART_5(0.92),+SMART_197(0.84),-SMART_9(0.02) interface=none temperature=none power=none workload=none
RULE_PRED: media
```

期望 JSON schema：
```
{
  "root_cause": "unknown",
  "risk_hint": 0.0,
  "hardness": 0.0,
  "confidence": 0.0,
  "events": [
    {"feature": "SMART_5", "type": "monotonic_increase", "severity": 0.0}
  ]
}
```

说明：
- 模型只需输出最小字段：`root_cause/risk_hint/hardness/confidence/events`。
- 脚本会自动补全 `near_positive` 与 `label_noise_risk`，并将数值约束到 `[0,1]`。

## 回滚/关闭

- 运行时不传 `--use_llm_features 1`，恢复原始流程；或
- 删除 `pyloader/run.py` 中 LLM 拼接逻辑。

## 说明与约束

- 仅改动 Python 侧与新增 `llm/` 目录，Java 端不变。
- 训练阶段不进行在线 LLM 调用，只读取 cache。
- 维度固定，缺字段自动回退并记录日志。
- 首批 profile 已覆盖 HDD(HI7) 与 SSD(MC1)；新型号可在 `llm/rules/profiles/model/` 增量扩展。
