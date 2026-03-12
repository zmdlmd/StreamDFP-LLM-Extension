const state = {
  workflows: [],
  filtered: [],
  selectedWorkflowId: null,
  selectedJobId: null,
  category: "All",
  search: "",
};

const els = {
  workflowCount: document.getElementById("workflowCount"),
  searchInput: document.getElementById("searchInput"),
  categoryFilters: document.getElementById("categoryFilters"),
  workflowList: document.getElementById("workflowList"),
  emptyState: document.getElementById("emptyState"),
  detailView: document.getElementById("detailView"),
  detailEyebrow: document.getElementById("detailEyebrow"),
  detailTitle: document.getElementById("detailTitle"),
  detailDescription: document.getElementById("detailDescription"),
  detailWarning: document.getElementById("detailWarning"),
  detailCanonical: document.getElementById("detailCanonical"),
  detailLegacy: document.getElementById("detailLegacy"),
  detailCwd: document.getElementById("detailCwd"),
  detailNotes: document.getElementById("detailNotes"),
  detailTags: document.getElementById("detailTags"),
  selectedCategory: document.getElementById("selectedCategory"),
  envForm: document.getElementById("envForm"),
  commandPreview: document.getElementById("commandPreview"),
  runButton: document.getElementById("runButton"),
  jobList: document.getElementById("jobList"),
  jobLog: document.getElementById("jobLog"),
  refreshJobsButton: document.getElementById("refreshJobsButton"),
  stopJobButton: document.getElementById("stopJobButton"),
};

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ error: response.statusText }));
    throw new Error(payload.error || response.statusText);
  }
  return response.json();
}

function categories() {
  const set = new Set(["All"]);
  state.workflows.forEach((workflow) => set.add(workflow.category));
  return Array.from(set);
}

function selectedWorkflow() {
  return state.workflows.find((workflow) => workflow.id === state.selectedWorkflowId) || null;
}

function applyFilter() {
  const search = state.search.trim().toLowerCase();
  state.filtered = state.workflows.filter((workflow) => {
    const hitCategory = state.category === "All" || workflow.category === state.category;
    const blob = [
      workflow.display_name,
      workflow.description,
      workflow.canonical_entry,
      workflow.legacy_entry,
      workflow.command_preview,
      ...(workflow.tags || []),
    ]
      .join(" ")
      .toLowerCase();
    const hitSearch = !search || blob.includes(search);
    return hitCategory && hitSearch;
  });

  if (!state.filtered.some((workflow) => workflow.id === state.selectedWorkflowId)) {
    state.selectedWorkflowId = state.filtered.length ? state.filtered[0].id : null;
  }
}

function renderFilters() {
  els.categoryFilters.innerHTML = "";
  categories().forEach((category) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `filter-chip ${state.category === category ? "active" : ""}`;
    button.textContent = category;
    button.addEventListener("click", () => {
      state.category = category;
      applyFilter();
      render();
    });
    els.categoryFilters.appendChild(button);
  });
}

function renderWorkflowList() {
  els.workflowCount.textContent = String(state.filtered.length);
  els.workflowList.innerHTML = "";
  state.filtered.forEach((workflow) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `workflow-card ${workflow.id === state.selectedWorkflowId ? "active" : ""}`;
    card.addEventListener("click", () => {
      state.selectedWorkflowId = workflow.id;
      render();
    });
    card.innerHTML = `
      <span class="card-category">${workflow.category}</span>
      <strong>${workflow.display_name}</strong>
      <p>${workflow.description}</p>
      <code>${workflow.canonical_entry || workflow.legacy_entry}</code>
    `;
    els.workflowList.appendChild(card);
  });
}

function renderDetail() {
  const workflow = selectedWorkflow();
  if (!workflow) {
    els.emptyState.classList.remove("hidden");
    els.detailView.classList.add("hidden");
    els.selectedCategory.textContent = "Select one";
    return;
  }

  els.emptyState.classList.add("hidden");
  els.detailView.classList.remove("hidden");
  els.selectedCategory.textContent = workflow.category;
  els.detailEyebrow.textContent = workflow.id;
  els.detailTitle.textContent = workflow.display_name;
  els.detailDescription.textContent = workflow.description;
  els.detailCanonical.textContent = workflow.canonical_entry || "";
  els.detailLegacy.textContent = workflow.legacy_entry;
  els.detailCwd.textContent = workflow.cwd;
  els.commandPreview.textContent = workflow.command_preview;

  if (workflow.warning) {
    els.detailWarning.classList.remove("hidden");
    els.detailWarning.textContent = workflow.warning;
  } else {
    els.detailWarning.classList.add("hidden");
    els.detailWarning.textContent = "";
  }

  els.detailTags.innerHTML = "";
  (workflow.tags || []).forEach((tag) => {
    const span = document.createElement("span");
    span.className = "tag";
    span.textContent = tag;
    els.detailTags.appendChild(span);
  });

  els.detailNotes.innerHTML = "";
  (workflow.notes || []).forEach((note) => {
    const li = document.createElement("li");
    li.textContent = note;
    els.detailNotes.appendChild(li);
  });

  els.envForm.innerHTML = "";
  (workflow.env || []).forEach((item) => {
    const wrapper = document.createElement("label");
    wrapper.className = "field";
    wrapper.innerHTML = `
      <span>${item.label}</span>
      <input data-env-name="${item.name}" type="text" value="${item.default || ""}" placeholder="${item.placeholder || ""}" />
      <small>${item.help || ""}</small>
    `;
    els.envForm.appendChild(wrapper);
  });
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

function renderStopButton(job) {
  if (job && job.status === "running") {
    els.stopJobButton.classList.remove("hidden");
  } else {
    els.stopJobButton.classList.add("hidden");
  }
}

async function refreshJobs() {
  const payload = await fetchJson("/api/jobs");
  renderJobs(payload.jobs || []);
  const selected = (payload.jobs || []).find((job) => job.job_id === state.selectedJobId);
  renderStopButton(selected);
  if (!selected) {
    els.jobLog.textContent = "";
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

async function runSelectedWorkflow() {
  const workflow = selectedWorkflow();
  if (!workflow) {
    return;
  }
  const env = {};
  els.envForm.querySelectorAll("[data-env-name]").forEach((input) => {
    env[input.dataset.envName] = input.value;
  });
  const payload = await fetchJson("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workflow_id: workflow.id, env }),
  });
  state.selectedJobId = payload.job.job_id;
  await refreshJobs();
  await refreshLog();
}

function render() {
  renderFilters();
  renderWorkflowList();
  renderDetail();
}

async function bootstrap() {
  const payload = await fetchJson("/api/workflows");
  state.workflows = payload.workflows || [];
  applyFilter();
  render();
  await refreshJobs();
  setInterval(async () => {
    await refreshJobs();
    await refreshLog();
  }, 3000);
}

els.searchInput.addEventListener("input", (event) => {
  state.search = event.target.value;
  applyFilter();
  render();
});

els.runButton.addEventListener("click", async () => {
  try {
    await runSelectedWorkflow();
  } catch (error) {
    window.alert(error.message);
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

bootstrap().catch((error) => {
  console.error(error);
  window.alert(`Failed to load workbench: ${error.message}`);
});
