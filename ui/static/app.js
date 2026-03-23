const BASE_WINDOW_TEXT = "llm/framework_v1_mc1/window_text_mc1_pilot20k_stratified_v2.jsonl";
const BASE_REFERENCE = "llm/framework_v1_mc1/reference_mc1_pilot20k_stratified_v2.json";
const BASELINE_CSV = "mc1_mlp/example_mc1_nollm_20180103_20180313_compare_aligned_i10.csv";
const DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1";

const MODEL_PRESET_DEFAULTS = {
  qwen3instruct2507: {
    hddFull: {
      RUN_TAG: "pilot20k_qwen3instruct2507",
      PHASE3_RUN_TAG: "pilot20k_qwen3instruct2507",
      PHASE3_TAG_SUFFIX: "qwen3instruct2507",
      MODEL_PATH: "../models/Qwen/Qwen3-4B-Instruct-2507",
      BACKEND: "vllm",
      API_BASE_URL: "",
      API_KEY_ENV: "OPENAI_API_KEY",
    },
    hddPhase2: {
      RUN_TAG: "pilot20k_qwen3instruct2507",
      TARGET_KEYS: "",
      MODEL_PATH: "../models/Qwen/Qwen3-4B-Instruct-2507",
      BACKEND: "vllm",
      API_BASE_URL: "",
      API_KEY_ENV: "OPENAI_API_KEY",
      BATCH_SIZE: "8",
      VLLM_GPU_MEMORY_UTILIZATION: "0.80",
      VLLM_MAX_MODEL_LEN: "3072",
      VLLM_MAX_NUM_BATCHED_TOKENS: "1024",
      MAX_NEW_TOKENS: "128",
    },
    hddPhase3: {
      PHASE3_RUN_TAG: "pilot20k_qwen3instruct2507",
      PHASE3_TAG_SUFFIX: "qwen3instruct2507",
      MAX_WINDOWS: "20000",
    },
    mc1Phase2: {
      RUN_TAG: "pilot20k_stratified_v2_qwen3instruct2507",
      MODEL_PATH: "../models/Qwen/Qwen3-4B-Instruct-2507",
      BACKEND: "vllm",
      API_BASE_URL: "",
      API_KEY_ENV: "OPENAI_API_KEY",
      BATCH_SIZE: "64",
      VLLM_TENSOR_PARALLEL_SIZE: "1",
      VLLM_ENFORCE_EAGER: "0",
      VLLM_GPU_MEM: "0.90",
      VLLM_MAX_MODEL_LEN: "8192",
      VLLM_MAX_NUM_BATCHED_TOKENS: "8192",
      SKIP_WINDOW_BUILD: "1",
      WINDOW_TEXT_IN: BASE_WINDOW_TEXT,
      REFERENCE_IN: BASE_REFERENCE,
    },
    mc1Full: {
      PHASE2_RUN_TAG: "pilot20k_stratified_v2_qwen3instruct2507",
      PHASE3_RUN_TAG: "pilot20k_stratified_v2",
      PHASE3_TAG_SUFFIX: "qwen3instruct2507",
      WINDOW_TEXT_IN: BASE_WINDOW_TEXT,
      REFERENCE_IN: BASE_REFERENCE,
      BASELINE_CSV,
      MODEL_PATH: "../models/Qwen/Qwen3-4B-Instruct-2507",
      BACKEND: "vllm",
      API_BASE_URL: "",
      API_KEY_ENV: "OPENAI_API_KEY",
      BATCH_SIZE: "64",
      VLLM_TENSOR_PARALLEL_SIZE: "1",
      VLLM_ENFORCE_EAGER: "0",
      VLLM_GPU_MEM: "0.90",
      VLLM_MAX_MODEL_LEN: "8192",
      VLLM_MAX_NUM_BATCHED_TOKENS: "8192",
    },
    mc1Phase3: {
      RUN_TAG: "pilot20k_stratified_v2",
      WINDOW_TEXT: BASE_WINDOW_TEXT,
      CACHE_IN: "llm/framework_v1_mc1/cache_mc1_zs_structured_v2_pilot20k_stratified_v2_qwen3instruct2507.jsonl",
      BASELINE_CSV,
      TAG_SUFFIX: "qwen3instruct2507",
      PHASE3_COMBO_LIMIT: "24",
      PHASE3_EXTRACT_MODE: "zs",
      PHASE3_PROMPT_PROFILE: "structured_v2",
      PHASE3_DIM_KEYS: "compact9,compact14",
    },
  },
  qwen35plusapi: {
    hddFull: {
      RUN_TAG: "pilot20k_qwen35plus_api",
      PHASE3_RUN_TAG: "pilot20k_qwen35plus_api",
      PHASE3_TAG_SUFFIX: "qwen35plusapi",
      MODEL_PATH: "qwen3.5-plus",
      BACKEND: "openai",
      API_BASE_URL: DASHSCOPE_BASE_URL,
      API_KEY_ENV: "DASHSCOPE_API_KEY",
    },
    hddPhase2: {
      RUN_TAG: "pilot20k_qwen35plus_api",
      TARGET_KEYS: "",
      MODEL_PATH: "qwen3.5-plus",
      BACKEND: "openai",
      API_BASE_URL: DASHSCOPE_BASE_URL,
      API_KEY_ENV: "DASHSCOPE_API_KEY",
      BATCH_SIZE: "16",
      VLLM_GPU_MEMORY_UTILIZATION: "0.80",
      VLLM_MAX_MODEL_LEN: "3072",
      VLLM_MAX_NUM_BATCHED_TOKENS: "1024",
      MAX_NEW_TOKENS: "96",
    },
    hddPhase3: {
      PHASE3_RUN_TAG: "pilot20k_qwen35plus_api",
      PHASE3_TAG_SUFFIX: "qwen35plusapi",
      MAX_WINDOWS: "20000",
    },
    mc1Phase2: {
      RUN_TAG: "pilot20k_stratified_v2_qwen35plus_api",
      MODEL_PATH: "qwen3.5-plus",
      BACKEND: "openai",
      API_BASE_URL: DASHSCOPE_BASE_URL,
      API_KEY_ENV: "DASHSCOPE_API_KEY",
      BATCH_SIZE: "16",
      VLLM_TENSOR_PARALLEL_SIZE: "1",
      VLLM_ENFORCE_EAGER: "0",
      VLLM_GPU_MEM: "0.90",
      VLLM_MAX_MODEL_LEN: "8192",
      VLLM_MAX_NUM_BATCHED_TOKENS: "8192",
      SKIP_WINDOW_BUILD: "1",
      WINDOW_TEXT_IN: BASE_WINDOW_TEXT,
      REFERENCE_IN: BASE_REFERENCE,
    },
    mc1Full: {
      PHASE2_RUN_TAG: "pilot20k_stratified_v2_qwen35plus_api",
      PHASE3_RUN_TAG: "pilot20k_stratified_v2",
      PHASE3_TAG_SUFFIX: "qwen35plusapi",
      WINDOW_TEXT_IN: BASE_WINDOW_TEXT,
      REFERENCE_IN: BASE_REFERENCE,
      BASELINE_CSV,
      MODEL_PATH: "qwen3.5-plus",
      BACKEND: "openai",
      API_BASE_URL: DASHSCOPE_BASE_URL,
      API_KEY_ENV: "DASHSCOPE_API_KEY",
      BATCH_SIZE: "16",
    },
    mc1Phase3: {
      RUN_TAG: "pilot20k_stratified_v2",
      WINDOW_TEXT: BASE_WINDOW_TEXT,
      CACHE_IN: "llm/framework_v1_mc1/cache_mc1_zs_structured_v2_pilot20k_stratified_v2_qwen35plus_api.jsonl",
      BASELINE_CSV,
      TAG_SUFFIX: "qwen35plusapi",
      PHASE3_COMBO_LIMIT: "24",
      PHASE3_EXTRACT_MODE: "zs",
      PHASE3_PROMPT_PROFILE: "structured_v2",
      PHASE3_DIM_KEYS: "compact9,compact14",
    },
  },
  qwen35tp2eager: {
    hddFull: {
      RUN_TAG: "pilot20k_qwen35",
      PHASE3_RUN_TAG: "pilot20k_qwen35",
      PHASE3_TAG_SUFFIX: "qwen35p20k",
      MODEL_PATH: "../models/Qwen/Qwen3.5-4B",
      BACKEND: "vllm",
      API_BASE_URL: "",
      API_KEY_ENV: "OPENAI_API_KEY",
    },
    hddPhase2: {
      RUN_TAG: "pilot20k_qwen35",
      TARGET_KEYS: "",
      MODEL_PATH: "../models/Qwen/Qwen3.5-4B",
      BACKEND: "vllm",
      API_BASE_URL: "",
      API_KEY_ENV: "OPENAI_API_KEY",
      BATCH_SIZE: "8",
      VLLM_GPU_MEMORY_UTILIZATION: "0.80",
      VLLM_MAX_MODEL_LEN: "3072",
      VLLM_MAX_NUM_BATCHED_TOKENS: "1024",
      MAX_NEW_TOKENS: "128",
    },
    hddPhase3: {
      PHASE3_RUN_TAG: "pilot20k_qwen35",
      PHASE3_TAG_SUFFIX: "qwen35p20k",
      MAX_WINDOWS: "20000",
    },
    mc1Phase2: {
      RUN_TAG: "pilot20k_stratified_v2_qwen35_tp2eager",
      MODEL_PATH: "../models/Qwen/Qwen3.5-4B",
      BACKEND: "vllm",
      API_BASE_URL: "",
      API_KEY_ENV: "OPENAI_API_KEY",
      BATCH_SIZE: "4",
      VLLM_TENSOR_PARALLEL_SIZE: "2",
      VLLM_ENFORCE_EAGER: "1",
      VLLM_GPU_MEM: "0.85",
      VLLM_MAX_MODEL_LEN: "3072",
      VLLM_MAX_NUM_BATCHED_TOKENS: "2048",
      SKIP_WINDOW_BUILD: "1",
      WINDOW_TEXT_IN: BASE_WINDOW_TEXT,
      REFERENCE_IN: BASE_REFERENCE,
    },
    mc1Full: {
      PHASE2_RUN_TAG: "pilot20k_stratified_v2_qwen35_tp2eager",
      PHASE3_RUN_TAG: "pilot20k_stratified_v2",
      PHASE3_TAG_SUFFIX: "qwen35tp2eager",
      WINDOW_TEXT_IN: BASE_WINDOW_TEXT,
      REFERENCE_IN: BASE_REFERENCE,
      BASELINE_CSV,
      MODEL_PATH: "../models/Qwen/Qwen3.5-4B",
      BACKEND: "vllm",
      API_BASE_URL: "",
      API_KEY_ENV: "OPENAI_API_KEY",
      BATCH_SIZE: "4",
      VLLM_TENSOR_PARALLEL_SIZE: "2",
      VLLM_ENFORCE_EAGER: "1",
      VLLM_GPU_MEM: "0.85",
      VLLM_MAX_MODEL_LEN: "3072",
      VLLM_MAX_NUM_BATCHED_TOKENS: "2048",
    },
    mc1Phase3: {
      RUN_TAG: "pilot20k_stratified_v2",
      WINDOW_TEXT: BASE_WINDOW_TEXT,
      CACHE_IN: "llm/framework_v1_mc1/cache_mc1_zs_structured_v2_pilot20k_stratified_v2_qwen35_tp2eager.jsonl",
      BASELINE_CSV,
      TAG_SUFFIX: "qwen35tp2eager",
      PHASE3_COMBO_LIMIT: "24",
      PHASE3_EXTRACT_MODE: "zs",
      PHASE3_PROMPT_PROFILE: "structured_v2",
      PHASE3_DIM_KEYS: "compact9,compact14",
    },
  },
};

const SCENARIOS = [
  {
    id: "hddFull",
    category: "HDD",
    title: "HDD 完整流程",
    subtitle: "Phase2 + Phase3 一键串联",
    workflowId: "llm.pilot20k.full-all12",
    presetScope: "hddFull",
    recommendedPreset: "qwen3instruct2507",
    description: "一次启动 12 个 HDD 盘型的抽取和网格评估，适合新一轮统一对照实验。",
    steps: ["检查模型与磁盘空间", "运行 HDD Phase2 抽取", "自动切到 HDD Phase3 评估", "查看 docs 和 logs 汇总"],
    outputs: ["logs/framework_v1", "logs/framework_v1_phase3", "docs/tables", "docs/reports"],
    primaryFields: [
      ["RUN_TAG", "Phase2 运行标签"],
      ["PHASE3_RUN_TAG", "Phase3 输入标签"],
      ["PHASE3_TAG_SUFFIX", "Phase3 结果后缀"],
      ["MODEL_PATH", "模型路径 / API 模型名"],
      ["BACKEND", "后端"],
      ["API_BASE_URL", "API Base URL"],
      ["API_KEY_ENV", "API Key 环境变量"],
    ],
    advancedFields: [],
  },
  {
    id: "hddPhase2",
    category: "HDD",
    title: "HDD 仅跑 Phase2",
    subtitle: "先抽取，再决定是否继续 Phase3",
    workflowId: "llm.pilot20k.phase2-all12",
    presetScope: "hddPhase2",
    recommendedPreset: "qwen3instruct2507",
    description: "适合只补 cache 或先做模型抽取质量对比。",
    steps: ["选择盘型范围", "启动批量抽取", "检查 cache 与 quality 输出"],
    outputs: ["llm/framework_v1/cache_*.jsonl", "logs/framework_v1", "docs/extract_quality_*.csv"],
    primaryFields: [
      ["RUN_TAG", "运行标签"],
      ["TARGET_KEYS", "盘型子集"],
      ["MODEL_PATH", "模型路径 / API 模型名"],
      ["BACKEND", "后端"],
      ["API_BASE_URL", "API Base URL"],
      ["API_KEY_ENV", "API Key 环境变量"],
      ["BATCH_SIZE", "批大小"],
    ],
    advancedFields: [
      ["VLLM_GPU_MEMORY_UTILIZATION", "GPU 利用率"],
      ["VLLM_MAX_MODEL_LEN", "Max Model Len"],
      ["VLLM_MAX_NUM_BATCHED_TOKENS", "Max Batched Tokens"],
      ["MAX_NEW_TOKENS", "Max New Tokens"],
    ],
  },
  {
    id: "hddPhase3",
    category: "HDD",
    title: "HDD 仅跑 Phase3",
    subtitle: "使用已有 cache 做 CPU/Java 网格",
    workflowId: "llm.pilot20k.phase3-all12",
    presetScope: "hddPhase3",
    recommendedPreset: "qwen3instruct2507",
    description: "适合 cache 已备好、只需要跑 Phase3 网格评估的场景。",
    steps: ["检查 baseline 与 cache", "启动 Phase3 网格", "查看 docs 汇总和组合记录"],
    outputs: ["logs/framework_v1_phase3", "logs/framework_v1_phase3_batch7", "docs/prearff_grid_*"],
    primaryFields: [
      ["PHASE3_RUN_TAG", "Phase3 输入标签"],
      ["PHASE3_TAG_SUFFIX", "结果后缀"],
      ["MAX_WINDOWS", "最大窗口数"],
    ],
    advancedFields: [],
  },
  {
    id: "mc1Full",
    category: "MC1",
    title: "MC1 完整流程",
    subtitle: "复用 stratified_v2 输入跑完整链路",
    workflowId: "llm.mc1.full-stratified-v2",
    presetScope: "mc1Full",
    recommendedPreset: "qwen3instruct2507",
    description: "直接复用已修正的 MC1 stratified_v2 输入，自动串联 Phase2 与 Phase3。",
    steps: ["复用 stratified_v2 window_text/reference", "运行 MC1 Phase2", "运行 MC1 Phase3", "输出 docs 对照表"],
    outputs: ["llm/framework_v1_mc1/cache_*.jsonl", "logs/framework_v1_phase2_mc1", "logs/framework_v1_phase3_mc1", "docs/prearff_grid_mc1_*"],
    primaryFields: [
      ["PHASE2_RUN_TAG", "Phase2 运行标签"],
      ["PHASE3_RUN_TAG", "Phase3 输入标签"],
      ["PHASE3_TAG_SUFFIX", "Phase3 结果后缀"],
      ["MODEL_PATH", "模型路径 / API 模型名"],
      ["BACKEND", "后端"],
      ["WINDOW_TEXT_IN", "window_text 路径"],
      ["REFERENCE_IN", "reference 路径"],
      ["BASELINE_CSV", "baseline CSV"],
      ["API_BASE_URL", "API Base URL"],
      ["API_KEY_ENV", "API Key 环境变量"],
    ],
    advancedFields: [
      ["BATCH_SIZE", "批大小"],
      ["VLLM_TENSOR_PARALLEL_SIZE", "Tensor Parallel"],
      ["VLLM_ENFORCE_EAGER", "Enforce Eager"],
      ["VLLM_GPU_MEM", "GPU 利用率"],
      ["VLLM_MAX_MODEL_LEN", "Max Model Len"],
      ["VLLM_MAX_NUM_BATCHED_TOKENS", "Max Batched Tokens"],
    ],
  },
  {
    id: "mc1Phase2",
    category: "MC1",
    title: "MC1 仅跑 Phase2",
    subtitle: "复用修正输入做模型抽取对比",
    workflowId: "llm.mc1.phase2",
    presetScope: "mc1Phase2",
    recommendedPreset: "qwen3instruct2507",
    description: "面向 MC1 的单模型抽取入口，默认不再重扫全年 SSD 数据。",
    steps: ["检查 stratified_v2 输入", "启动 MC1 抽取", "查看 quality 与 cache 输出"],
    outputs: ["llm/framework_v1_mc1/cache_*.jsonl", "logs/framework_v1_phase2_mc1", "docs/extract_quality_mc1_*"],
    primaryFields: [
      ["RUN_TAG", "运行标签"],
      ["MODEL_PATH", "模型路径 / API 模型名"],
      ["BACKEND", "后端"],
      ["WINDOW_TEXT_IN", "window_text 路径"],
      ["REFERENCE_IN", "reference 路径"],
      ["SKIP_WINDOW_BUILD", "跳过 Phase1 重建"],
      ["API_BASE_URL", "API Base URL"],
      ["API_KEY_ENV", "API Key 环境变量"],
      ["BATCH_SIZE", "批大小"],
    ],
    advancedFields: [
      ["VLLM_TENSOR_PARALLEL_SIZE", "Tensor Parallel"],
      ["VLLM_ENFORCE_EAGER", "Enforce Eager"],
      ["VLLM_GPU_MEM", "GPU 利用率"],
      ["VLLM_MAX_MODEL_LEN", "Max Model Len"],
      ["VLLM_MAX_NUM_BATCHED_TOKENS", "Max Batched Tokens"],
    ],
  },
  {
    id: "mc1Phase3",
    category: "MC1",
    title: "MC1 仅跑 Phase3",
    subtitle: "用已有 cache 做 24 组网格",
    workflowId: "llm.mc1.phase3-grid",
    presetScope: "mc1Phase3",
    recommendedPreset: "qwen3instruct2507",
    description: "适合 cache 已备好，只补 CPU/Java 侧的网格评估。",
    steps: ["检查 cache、window_text、baseline", "启动 compact9/compact14 网格", "查看 docs 与 combo record"],
    outputs: ["logs/framework_v1_phase3_mc1", "mc1_mlp/phase3_mc1_*.csv", "docs/prearff_grid_mc1_*"],
    primaryFields: [
      ["RUN_TAG", "运行标签"],
      ["WINDOW_TEXT", "window_text 路径"],
      ["CACHE_IN", "cache 路径"],
      ["BASELINE_CSV", "baseline CSV"],
      ["TAG_SUFFIX", "结果后缀"],
      ["PHASE3_COMBO_LIMIT", "组合数"],
    ],
    advancedFields: [
      ["PHASE3_EXTRACT_MODE", "抽取模式"],
      ["PHASE3_PROMPT_PROFILE", "提示词配置"],
      ["PHASE3_DIM_KEYS", "维度子集"],
    ],
  },
];

const state = {
  workflows: [],
  results: null,
  storage: null,
  preflight: null,
  cleanupPreview: null,
  jobs: [],
  selectedJobId: null,
  activeTab: "overview",
  wizardScenarioId: "mc1Full",
  wizardPresetId: "qwen3instruct2507",
  wizardValues: {},
  cleanupStatus: "",
};

const els = {
  baseModelBadge: document.getElementById("baseModelBadge"),
  modelPresetCards: document.getElementById("modelPresetCards"),
  overviewHighlights: document.getElementById("overviewHighlights"),
  recentJobsOverview: document.getElementById("recentJobsOverview"),
  scenarioCards: document.getElementById("scenarioCards"),
  preflightList: document.getElementById("preflightList"),
  focusCards: document.getElementById("focusCards"),
  wizardScenarioRail: document.getElementById("wizardScenarioRail"),
  wizardPresetRail: document.getElementById("wizardPresetRail"),
  wizardWorkflowBadge: document.getElementById("wizardWorkflowBadge"),
  wizardHeader: document.getElementById("wizardHeader"),
  wizardStepList: document.getElementById("wizardStepList"),
  wizardRelevantChecks: document.getElementById("wizardRelevantChecks"),
  wizardPrimaryFields: document.getElementById("wizardPrimaryFields"),
  wizardAdvancedFields: document.getElementById("wizardAdvancedFields"),
  wizardOutputs: document.getElementById("wizardOutputs"),
  wizardPreview: document.getElementById("wizardPreview"),
  wizardApplyPresetButton: document.getElementById("wizardApplyPresetButton"),
  wizardRunButton: document.getElementById("wizardRunButton"),
  resultsHighlights: document.getElementById("resultsHighlights"),
  mc1Overview: document.getElementById("mc1Overview"),
  hddOverview: document.getElementById("hddOverview"),
  mc1Phase2Path: document.getElementById("mc1Phase2Path"),
  mc1Phase2Table: document.getElementById("mc1Phase2Table"),
  mc1Phase3Path: document.getElementById("mc1Phase3Path"),
  mc1Phase3Table: document.getElementById("mc1Phase3Table"),
  hddPath: document.getElementById("hddPath"),
  hddSummaryTable: document.getElementById("hddSummaryTable"),
  storageHeadline: document.getElementById("storageHeadline"),
  cleanupSuggestions: document.getElementById("cleanupSuggestions"),
  cleanupExperimentButton: document.getElementById("cleanupExperimentButton"),
  cleanupStatus: document.getElementById("cleanupStatus"),
  refreshPreflightButton: document.getElementById("refreshPreflightButton"),
  jobList: document.getElementById("jobList"),
  jobLog: document.getElementById("jobLog"),
  jobArtifacts: document.getElementById("jobArtifacts"),
  refreshJobsButton: document.getElementById("refreshJobsButton"),
  stopJobButton: document.getElementById("stopJobButton"),
  tabButtons: Array.from(document.querySelectorAll(".tab-button")),
  tabPanels: Array.from(document.querySelectorAll(".tab-panel")),
};

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ error: response.statusText }));
    throw new Error(payload.error || response.statusText);
  }
  return response.json();
}

function workflowById(id) {
  return state.workflows.find((item) => item.id === id) || null;
}

function scenarioById(id) {
  return SCENARIOS.find((item) => item.id === id) || SCENARIOS[0];
}

function presetById(id) {
  return (state.results?.model_presets || []).find((item) => item.id === id) || null;
}

function presetDefaults(presetId, scope) {
  return { ...(MODEL_PRESET_DEFAULTS[presetId] || {})[scope] };
}

function setActiveTab(tabId) {
  state.activeTab = tabId;
  els.tabButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tabId);
  });
  els.tabPanels.forEach((panel) => {
    panel.classList.toggle("hidden", panel.id !== `tab-${tabId}`);
  });
}

function setWizardScenario(scenarioId) {
  const scenario = scenarioById(scenarioId);
  state.wizardScenarioId = scenario.id;
  state.wizardPresetId = scenario.recommendedPreset;
  state.wizardValues = presetDefaults(state.wizardPresetId, scenario.presetScope);
  renderWizard();
  renderLaunchpad();
}

function setWizardPreset(presetId) {
  const scenario = scenarioById(state.wizardScenarioId);
  state.wizardPresetId = presetId;
  state.wizardValues = presetDefaults(presetId, scenario.presetScope);
  renderWizard();
}

function humanPercent(value) {
  const num = Number(value);
  if (Number.isNaN(num)) {
    return "-";
  }
  return `${num.toFixed(2)}%`;
}

function metricCard(label, value, tone = "", helpText = "") {
  const div = document.createElement("div");
  div.className = `metric-card ${tone}`.trim();
  div.innerHTML = `
    <span>${label}</span>
    <strong>${value}</strong>
    ${helpText ? `<small>${helpText}</small>` : ""}
  `;
  return div;
}

function listItem(title, lines = [], classes = "") {
  const div = document.createElement("div");
  div.className = `list-item ${classes}`.trim();
  div.innerHTML = `<strong>${title}</strong>${lines.map((line) => `<span>${line}</span>`).join("")}`;
  return div;
}

function selectedScenario() {
  return scenarioById(state.wizardScenarioId);
}

function selectedWorkflow() {
  return workflowById(selectedScenario().workflowId);
}

function runningJobsCount() {
  return state.jobs.filter((job) => job.status === "running").length;
}

function renderModelPresets() {
  const presets = state.results?.model_presets || [];
  els.modelPresetCards.innerHTML = "";
  presets.forEach((preset) => {
    const card = document.createElement("div");
    card.className = `preset-card ${preset.recommended ? "recommended" : ""}`;
    card.innerHTML = `
      <div class="preset-topline">
        <strong>${preset.name}</strong>
        <span class="pill ${preset.recommended ? "" : "muted"}">${preset.role}</span>
      </div>
      <p class="preset-family">${preset.family} · ${preset.kind === "local" ? "本地模型" : "API 模型"}</p>
      <p class="preset-description">${preset.description}</p>
      <code>${preset.model_path || "-"}</code>
    `;
    els.modelPresetCards.appendChild(card);
  });
}

function renderOverviewHighlights() {
  const hddModels = state.results?.hdd?.models || [];
  const mc1Phase3Rows = state.results?.mc1_phase3?.rows || [];
  const disk = state.storage?.disk;
  const bestMc1 = mc1Phase3Rows.reduce((best, row) => {
    if (!best) {
      return row;
    }
    return Number(row.delta_recall_vs_nollm) > Number(best.delta_recall_vs_nollm) ? row : best;
  }, null);
  const bestHddCoverage = hddModels.reduce((best, row) => {
    if (!best) {
      return row;
    }
    return Number(row.enabled_count) > Number(best.enabled_count) ? row : best;
  }, null);

  els.baseModelBadge.textContent = "Qwen3-4B-Instruct-2507";
  els.overviewHighlights.innerHTML = "";
  els.overviewHighlights.appendChild(metricCard("默认本地基线", "Qwen3-4B-Instruct-2507", "accent", "当前仓库默认推荐"));
  els.overviewHighlights.appendChild(metricCard("运行中作业", String(runningJobsCount()), runningJobsCount() > 0 ? "accent" : ""));
  els.overviewHighlights.appendChild(
    metricCard(
      "MC1 最佳 ΔRecall",
      bestMc1 ? Number(bestMc1.delta_recall_vs_nollm).toFixed(4) : "-",
      "success",
      bestMc1 ? bestMc1.model : "尚无结果"
    )
  );
  els.overviewHighlights.appendChild(
    metricCard(
      "HDD 覆盖最多模型",
      bestHddCoverage ? `${bestHddCoverage.label} · ${bestHddCoverage.enabled_count}` : "-",
      "",
      "可启用盘型数"
    )
  );
  els.overviewHighlights.appendChild(
    metricCard("磁盘可用空间", disk ? disk.free_human : "-", disk && disk.free_bytes > 50 * 1024 ** 3 ? "success" : "")
  );
}

function launchScenarioCard(scenarioId, presetId) {
  const scenario = scenarioById(scenarioId);
  const env = presetDefaults(presetId, scenario.presetScope);
  return fetchJson("/api/run_custom", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workflow_id: scenario.workflowId, env }),
  });
}

function renderLaunchpad() {
  els.scenarioCards.innerHTML = "";
  SCENARIOS.forEach((scenario) => {
    const preset = presetById(scenario.recommendedPreset);
    const card = document.createElement("div");
    card.className = "scenario-card";
    card.innerHTML = `
      <div class="scenario-topline">
        <strong>${scenario.title}</strong>
        <span class="pill">${scenario.category}</span>
      </div>
      <p class="scenario-subtitle">${scenario.subtitle}</p>
      <p class="preset-description">${scenario.description}</p>
      <span class="scenario-hint">推荐模型：${preset ? preset.name : scenario.recommendedPreset}</span>
      <div class="button-row">
        <button class="ghost-button" type="button" data-role="open">进入向导</button>
        <button class="primary-button" type="button" data-role="run">快速启动默认配置</button>
      </div>
    `;
    card.querySelector('[data-role="open"]').addEventListener("click", () => {
      setWizardScenario(scenario.id);
      setActiveTab("wizard");
    });
    card.querySelector('[data-role="run"]').addEventListener("click", async () => {
      try {
        const payload = await launchScenarioCard(scenario.id, scenario.recommendedPreset);
        state.selectedJobId = payload.job.job_id;
        setActiveTab("jobs");
        await refreshJobs();
        await refreshLog();
      } catch (error) {
        window.alert(`启动失败: ${error.message}`);
      }
    });
    els.scenarioCards.appendChild(card);
  });
}

function renderPreflight() {
  const checks = state.preflight?.checks || [];
  els.preflightList.innerHTML = "";
  checks.forEach((check) => {
    const scopeLabel = check.scope === "global" ? "全局" : check.scope.toUpperCase();
    const item = listItem(check.label, [`${scopeLabel} · ${check.ok ? "通过" : "缺失/异常"}`, check.detail], check.ok ? "" : "preflight-fail");
    els.preflightList.appendChild(item);
  });
}

function renderFocusCards() {
  const mc1Phase2 = state.results?.mc1_phase2?.rows || [];
  const hddModels = state.results?.hdd?.models || [];
  const bestPhase2 = mc1Phase2.reduce((best, row) => {
    if (!best) {
      return row;
    }
    return Number(row.non_unknown_pct) > Number(best.non_unknown_pct) ? row : best;
  }, null);
  const bestHddAvg = hddModels.reduce((best, row) => {
    if (!best) {
      return row;
    }
    return Number(row.avg_enabled_delta_recall || -9999) > Number(best.avg_enabled_delta_recall || -9999) ? row : best;
  }, null);
  const suggestions = [
    {
      title: "MC1 默认推荐",
      lines: bestPhase2
        ? [`优先模型：${bestPhase2.model}`, `non-unknown ${bestPhase2.non_unknown_pct}% · q_score ${bestPhase2.avg_llm_q_score}`]
        : ["MC1 结果尚未载入"],
    },
    {
      title: "HDD 默认推荐",
      lines: bestHddAvg
        ? [`平均增益最高：${bestHddAvg.label}`, `平均 ΔRecall ${Number(bestHddAvg.avg_enabled_delta_recall).toFixed(4)}`]
        : ["HDD 结果尚未载入"],
    },
    {
      title: "流程建议",
      lines: ["先走实验向导，再进结果看板复核", "MC1 建议优先使用 stratified_v2 路线"],
    },
  ];
  els.focusCards.innerHTML = "";
  suggestions.forEach((item) => {
    els.focusCards.appendChild(listItem(item.title, item.lines));
  });
}

function renderRecentJobsOverview() {
  els.recentJobsOverview.innerHTML = "";
  const jobs = state.jobs.slice(0, 4);
  if (!jobs.length) {
    els.recentJobsOverview.appendChild(listItem("暂无作业", ["还没有通过 UI 启动的任务"]));
    return;
  }
  jobs.forEach((job) => {
    els.recentJobsOverview.appendChild(
      listItem(job.workflow_name, [`${job.status} · ${job.started_at}`, job.log_path])
    );
  });
}

function renderOverview() {
  renderOverviewHighlights();
  renderLaunchpad();
  renderPreflight();
  renderModelPresets();
  renderFocusCards();
  renderRecentJobsOverview();
}

function renderSelectorCard(container, options, selectedId, onSelect, formatter) {
  container.innerHTML = "";
  options.forEach((option) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `selector-card ${option.id === selectedId ? "active" : ""}`;
    card.innerHTML = formatter(option);
    card.addEventListener("click", () => onSelect(option.id));
    container.appendChild(card);
  });
}

function renderWizardScenarioRail() {
  renderSelectorCard(
    els.wizardScenarioRail,
    SCENARIOS,
    state.wizardScenarioId,
    setWizardScenario,
    (scenario) => `
      <strong>${scenario.title}</strong>
      <span>${scenario.subtitle}</span>
      <small>${scenario.category}</small>
    `
  );
}

function renderWizardPresetRail() {
  const presets = state.results?.model_presets || [];
  renderSelectorCard(
    els.wizardPresetRail,
    presets,
    state.wizardPresetId,
    setWizardPreset,
    (preset) => `
      <strong>${preset.name}</strong>
      <span>${preset.role}</span>
      <small>${preset.kind === "local" ? "本地" : "API"} · ${preset.family}</small>
    `
  );
}

function renderWizardFields(container, fields) {
  container.innerHTML = "";
  fields.forEach(([name, label]) => {
    const value = state.wizardValues[name] ?? "";
    const field = document.createElement("label");
    field.className = "field";
    field.innerHTML = `
      <span>${label}</span>
      <input data-env-name="${name}" type="text" value="${value}" />
    `;
    field.querySelector("input").addEventListener("input", (event) => {
      state.wizardValues[name] = event.target.value;
      updateWizardPreview();
    });
    container.appendChild(field);
  });
}

function relevantChecksForScenario(scenario) {
  const checks = state.preflight?.checks || [];
  return checks.filter((check) => check.scope === "global" || check.scope === "models" || check.scope === scenario.category.toLowerCase());
}

function renderWizard() {
  const scenario = selectedScenario();
  const workflow = selectedWorkflow();
  const preset = presetById(state.wizardPresetId);

  renderWizardScenarioRail();
  renderWizardPresetRail();

  els.wizardWorkflowBadge.textContent = workflow ? workflow.display_name : scenario.workflowId;
  els.wizardHeader.innerHTML = `
    <div class="wizard-hero">
      <strong>${scenario.title}</strong>
      <span>${scenario.description}</span>
      <small>当前模型：${preset ? preset.name : state.wizardPresetId}</small>
    </div>
  `;

  els.wizardStepList.innerHTML = "";
  scenario.steps.forEach((step, index) => {
    els.wizardStepList.appendChild(listItem(`步骤 ${index + 1}`, [step]));
  });

  els.wizardRelevantChecks.innerHTML = "";
  relevantChecksForScenario(scenario).forEach((check) => {
    els.wizardRelevantChecks.appendChild(
      listItem(check.label, [check.ok ? "通过" : "缺失/异常", check.detail], check.ok ? "" : "preflight-fail")
    );
  });

  renderWizardFields(els.wizardPrimaryFields, scenario.primaryFields);
  renderWizardFields(els.wizardAdvancedFields, scenario.advancedFields);

  els.wizardOutputs.innerHTML = "";
  scenario.outputs.forEach((line) => {
    els.wizardOutputs.appendChild(listItem(line, ["运行完成后优先检查这里"], "output-item"));
  });

  updateWizardPreview();
}

function updateWizardPreview() {
  const workflow = selectedWorkflow();
  const envLines = Object.entries(state.wizardValues)
    .filter(([, value]) => String(value).trim() !== "")
    .map(([key, value]) => `${key}=${value}`);
  const command = workflow ? workflow.command_preview : selectedScenario().workflowId;
  els.wizardPreview.textContent = `${envLines.join("\n")}\n${command}`.trim();
}

async function runWizard() {
  try {
    const payload = await fetchJson("/api/run_custom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workflow_id: selectedScenario().workflowId, env: state.wizardValues }),
    });
    state.selectedJobId = payload.job.job_id;
    setActiveTab("jobs");
    await refreshJobs();
    await refreshLog();
  } catch (error) {
    window.alert(`启动失败: ${error.message}`);
  }
}

function renderTable(table, columns, rows) {
  table.innerHTML = "";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  columns.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col.label;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    columns.forEach((col) => {
      const td = document.createElement("td");
      td.textContent = row[col.key] ?? "";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
}

function renderResultsHighlights() {
  const mc1Phase2 = state.results?.mc1_phase2?.rows || [];
  const mc1Phase3 = state.results?.mc1_phase3?.rows || [];
  const hddModels = state.results?.hdd?.models || [];
  const bestMc1Phase2 = mc1Phase2.reduce((best, row) => {
    if (!best) {
      return row;
    }
    return Number(row.non_unknown_pct) > Number(best.non_unknown_pct) ? row : best;
  }, null);
  const bestMc1Phase3 = mc1Phase3.reduce((best, row) => {
    if (!best) {
      return row;
    }
    return Number(row.delta_recall_vs_nollm) > Number(best.delta_recall_vs_nollm) ? row : best;
  }, null);
  const bestHdd = hddModels.reduce((best, row) => {
    if (!best) {
      return row;
    }
    return Number(row.avg_enabled_delta_recall || -9999) > Number(best.avg_enabled_delta_recall || -9999) ? row : best;
  }, null);
  els.resultsHighlights.innerHTML = "";
  els.resultsHighlights.appendChild(
    metricCard("MC1 Phase2 最强", bestMc1Phase2 ? bestMc1Phase2.model : "-", "accent", bestMc1Phase2 ? `non-unknown ${bestMc1Phase2.non_unknown_pct}%` : "")
  );
  els.resultsHighlights.appendChild(
    metricCard("MC1 Phase3 最优", bestMc1Phase3 ? bestMc1Phase3.model : "-", "success", bestMc1Phase3 ? `ΔRecall ${Number(bestMc1Phase3.delta_recall_vs_nollm).toFixed(4)}` : "")
  );
  els.resultsHighlights.appendChild(
    metricCard("HDD 平均增益最高", bestHdd ? bestHdd.label : "-", "", bestHdd ? `${Number(bestHdd.avg_enabled_delta_recall).toFixed(4)}` : "")
  );
}

function renderResultsNarrative() {
  const mc1Phase2 = state.results?.mc1_phase2?.rows || [];
  const hddModels = state.results?.hdd?.models || [];
  els.mc1Overview.innerHTML = "";
  mc1Phase2.forEach((row) => {
    els.mc1Overview.appendChild(
      listItem(row.model, [
        `non-unknown ${row.non_unknown_pct}% · mapped_event ${row.mapped_event_ratio_pct}%`,
        `confidence ${row.avg_confidence} · q_score ${row.avg_llm_q_score}`,
      ])
    );
  });
  els.hddOverview.innerHTML = "";
  hddModels.forEach((row) => {
    els.hddOverview.appendChild(
      listItem(row.label, [
        `可启用盘型 ${row.enabled_count} · 平均 ΔRecall ${row.avg_enabled_delta_recall ?? "-"}`,
        `最佳 ${row.best_model_key} · 最差 ${row.worst_model_key}`,
      ])
    );
  });
}

function renderResults() {
  const mc1Phase2 = state.results?.mc1_phase2 || { rows: [] };
  const mc1Phase3 = state.results?.mc1_phase3 || { rows: [] };
  const hdd = state.results?.hdd || { models: [] };

  renderResultsHighlights();
  renderResultsNarrative();

  els.mc1Phase2Path.textContent = mc1Phase2.path || "";
  renderTable(
    els.mc1Phase2Table,
    [
      { key: "model", label: "模型" },
      { key: "unknown_pct", label: "unknown%" },
      { key: "non_unknown_pct", label: "非unknown%" },
      { key: "mapped_event_ratio_pct", label: "映射事件%" },
      { key: "avg_confidence", label: "平均置信度" },
      { key: "avg_llm_q_score", label: "平均Q分数" },
    ],
    mc1Phase2.rows || []
  );

  els.mc1Phase3Path.textContent = mc1Phase3.path || "";
  renderTable(
    els.mc1Phase3Table,
    [
      { key: "model", label: "模型" },
      { key: "status_counts", label: "状态计数" },
      { key: "best_dim_key", label: "最佳维度" },
      { key: "best_q_gate", label: "q_gate" },
      { key: "best_sev_sum_gate", label: "sev_gate" },
      { key: "delta_recall_vs_nollm", label: "ΔRecall" },
      { key: "delta_acc_vs_nollm", label: "ΔACC" },
      { key: "notes", label: "说明" },
    ],
    mc1Phase3.rows || []
  );

  els.hddPath.textContent = hdd.path || "";
  renderTable(
    els.hddSummaryTable,
    [
      { key: "label", label: "模型" },
      { key: "enabled_count", label: "可启用盘型数" },
      { key: "avg_enabled_delta_recall", label: "平均ΔRecall" },
      { key: "best_model_key", label: "最佳盘型" },
      { key: "best_delta_recall", label: "最佳增益" },
      { key: "worst_model_key", label: "最差盘型" },
      { key: "worst_delta_recall", label: "最差增益" },
    ],
    hdd.models || []
  );
}

function cleanupSuggestions() {
  const targets = state.cleanupPreview?.targets || [];
  return [
    {
      title: "按钮会清理这些中间产物",
      lines: targets.length ? targets : ["save_model/*.pickle", "pyloader/phase3_train_*", "pyloader/phase3_test_*"],
    },
    {
      title: "不会清理这些结果",
      lines: ["docs 下的 csv / md 汇总", "mc1_mlp 和 hi7_example 中的最终结果 CSV", "phase2 cache 与 window_text/reference"],
    },
    {
      title: "安全限制",
      lines: ["如果当前有运行中的作业，按钮会拒绝执行", "清理后无法从中间状态续跑，只保留最终结果"],
    },
  ];
}

function renderStorage() {
  const storage = state.storage;
  if (!storage) {
    return;
  }
  els.storageHeadline.innerHTML = "";
  els.storageHeadline.appendChild(metricCard("总容量", storage.disk.total_human, "accent"));
  els.storageHeadline.appendChild(metricCard("已使用", storage.disk.used_human));
  els.storageHeadline.appendChild(metricCard("可用空间", storage.disk.free_human, storage.disk.free_bytes > 50 * 1024 ** 3 ? "success" : ""));

  els.cleanupSuggestions.innerHTML = "";
  cleanupSuggestions().forEach((item) => {
    els.cleanupSuggestions.appendChild(listItem(item.title, item.lines, item.tone || ""));
  });
  els.cleanupStatus.textContent = state.cleanupStatus || "尚未执行清理。";
}

function renderJobs(jobs) {
  els.jobList.innerHTML = "";
  jobs.forEach((job) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `job-card ${job.job_id === state.selectedJobId ? "active" : ""}`;
    card.addEventListener("click", async () => {
      state.selectedJobId = job.job_id;
      renderStopButton(job);
      renderJobArtifacts(job);
      await refreshLog();
      renderJobs(jobs);
    });
    card.innerHTML = `
      <div class="job-topline">
        <strong>${job.workflow_name}</strong>
        <span class="status ${job.status}">${job.status}</span>
      </div>
      <p>${job.job_id} · ${job.started_at}</p>
      <code>${job.log_path}</code>
    `;
    els.jobList.appendChild(card);
  });
}

function renderJobArtifacts(job) {
  els.jobArtifacts.innerHTML = "";
  if (!job) {
    els.jobArtifacts.appendChild(listItem("未选择作业", ["选中左侧作业后，这里会显示对应产物路径。"]));
    return;
  }
  const artifacts = job.artifacts || [];
  if (!artifacts.length) {
    els.jobArtifacts.appendChild(listItem("暂无推断产物", ["这个流程没有定义专门的结果路径。"]));
    return;
  }
  artifacts.forEach((item) => {
    const status = item.exists ? "已生成" : "待生成";
    els.jobArtifacts.appendChild(listItem(item.label, [`${status} · ${item.path}`], item.exists ? "" : "preflight-fail"));
  });
}

function renderStopButton(job) {
  if (job && job.status === "running") {
    els.stopJobButton.classList.remove("hidden");
  } else {
    els.stopJobButton.classList.add("hidden");
  }
}

async function refreshJobs() {
  const previous = new Map(state.jobs.map((job) => [job.job_id, job.status]));
  const payload = await fetchJson("/api/jobs");
  state.jobs = payload.jobs || [];
  if (!state.selectedJobId && state.jobs.length) {
    state.selectedJobId = state.jobs[0].job_id;
  }
  renderJobs(state.jobs);
  renderRecentJobsOverview();
  renderOverviewHighlights();
  const selected = state.jobs.find((job) => job.job_id === state.selectedJobId);
  renderStopButton(selected);
  renderJobArtifacts(selected);
  if (!selected) {
    els.jobLog.textContent = "";
  }
  const shouldRefreshResults = state.jobs.some((job) => previous.get(job.job_id) === "running" && job.status !== "running");
  if (shouldRefreshResults) {
    await refreshResultsAndStorage();
  }
}

async function refreshLog() {
  if (!state.selectedJobId) {
    els.jobLog.textContent = "";
    return;
  }
  const payload = await fetchJson(`/api/jobs/${state.selectedJobId}/log?lines=160`);
  els.jobLog.textContent = payload.log || "";
}

async function refreshResultsAndStorage() {
  state.results = await fetchJson("/api/results/summary");
  state.preflight = await fetchJson("/api/preflight");
  state.storage = await fetchJson("/api/storage");
  state.cleanupPreview = await fetchJson("/api/cleanup-preview");
  renderOverview();
  renderWizard();
  renderResults();
  renderStorage();
}

async function bootstrap() {
  const workflowPayload = await fetchJson("/api/workflows");
  state.workflows = workflowPayload.workflows || [];
  state.wizardValues = presetDefaults(state.wizardPresetId, selectedScenario().presetScope);
  await refreshResultsAndStorage();
  await refreshJobs();
  setInterval(async () => {
    await refreshJobs();
    await refreshLog();
  }, 3000);
}

els.tabButtons.forEach((button) => {
  button.addEventListener("click", () => setActiveTab(button.dataset.tab));
});

els.cleanupExperimentButton.addEventListener("click", async () => {
  try {
    const payload = await fetchJson("/api/cleanup/experiment-artifacts", { method: "POST" });
    state.cleanupStatus = `已清理 ${payload.removed_count} 项，释放 ${payload.reclaimed_human}`;
    state.storage = await fetchJson("/api/storage");
    renderStorage();
    renderOverviewHighlights();
  } catch (error) {
    window.alert(`清理失败: ${error.message}`);
  }
});

els.refreshPreflightButton.addEventListener("click", async () => {
  try {
    state.preflight = await fetchJson("/api/preflight");
    renderPreflight();
    renderWizard();
  } catch (error) {
    window.alert(`刷新检查失败: ${error.message}`);
  }
});

els.refreshJobsButton.addEventListener("click", async () => {
  await refreshJobs();
  await refreshLog();
});

els.stopJobButton.addEventListener("click", async () => {
  if (!state.selectedJobId) {
    return;
  }
  await fetchJson(`/api/jobs/${state.selectedJobId}/stop`, { method: "POST" });
  await refreshJobs();
  await refreshLog();
});

els.wizardApplyPresetButton.addEventListener("click", () => {
  state.wizardValues = presetDefaults(state.wizardPresetId, selectedScenario().presetScope);
  renderWizard();
});

els.wizardRunButton.addEventListener("click", async () => {
  await runWizard();
});

bootstrap().catch((error) => {
  console.error(error);
  window.alert(`加载工作台失败: ${error.message}`);
});
