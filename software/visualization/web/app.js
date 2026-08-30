"use strict";

const $ = (id) => document.getElementById(id);
const numberFormat = (value, digits = 1) => new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: digits,
  maximumFractionDigits: digits,
}).format(Number.isFinite(value) ? value : 0);

const colors = (() => {
  const style = getComputedStyle(document.documentElement);
  return {
    cyan: style.getPropertyValue("--cyan").trim(),
    green: style.getPropertyValue("--green").trim(),
    orange: style.getPropertyValue("--orange").trim(),
    blue: style.getPropertyValue("--blue").trim(),
    text: style.getPropertyValue("--text").trim(),
    muted: style.getPropertyValue("--muted").trim(),
    grid: style.getPropertyValue("--grid").trim(),
  };
})();

let catalog;
let currentRunState = "idle";
let finalMetrics = null;
let currentHistoryDetail = null;
let offlineReplayActive = false;
let currentComparison = null;
let comparisonCurves = [];
const comparisonSelection = new Map();
const comparisonPalette = ["#53d8d2", "#d98cff", "#71e391", "#ff7aa8"];

const runStateLabels = {
  idle: "Prêt",
  starting: "Démarrage",
  running: "En cours",
  stopping: "Arrêt en cours",
  analyzing: "Analyse finale",
  completed: "Terminé",
  stopped: "Arrêté",
  cancelled: "Annulé",
  failed: "Échec",
};

async function apiRequest(path, options = {}) {
  const response = await fetch(path, options);
  let payload = {};
  try {
    payload = await response.json();
  } catch (_error) {
    payload = {};
  }
  if (!response.ok) throw new Error(payload.error || `Erreur HTTP ${response.status}`);
  return payload;
}

async function apiTextRequest(path, options = {}) {
  const response = await fetch(path, options);
  const content = await response.text();
  if (!response.ok) {
    try { throw new Error(JSON.parse(content).error || `Erreur HTTP ${response.status}`); }
    catch (error) {
      if (error instanceof SyntaxError) throw new Error(`Erreur HTTP ${response.status}`);
      throw error;
    }
  }
  return { content, disposition: response.headers.get("Content-Disposition") || "" };
}

function selectedSimulation() {
  return catalog?.simulations.find((value) => value.simulation_id === $("control-simulation").value);
}

function selectedDataset() {
  return catalog?.datasets.find((value) => value.dataset_id === $("control-dataset").value);
}

function selectedSequence() {
  return selectedDataset()?.sequences.find((value) => value.sequence_id === $("control-sequence").value);
}

function selectedAlgorithm() {
  return selectedSimulation()?.variants.find((value) => value.variant_id === $("control-algorithm").value);
}

function simulationNeedsDataset() {
  return Boolean(selectedSimulation()?.selectors?.some((value) => value.kind === "dataset_sequence" && value.required));
}

function compatibleSequences() {
  const simulation = selectedSimulation();
  const variant = selectedAlgorithm();
  return catalog?.compatibility?.[simulation?.simulation_id]?.[variant?.variant_id] || [];
}

function createParameterField(definition) {
  const label = document.createElement("label");
  const caption = document.createElement("span");
  caption.textContent = definition.label;
  label.appendChild(caption);
  const wrapper = document.createElement("div");
  wrapper.className = "parameter-input";
  let input;
  if (definition.type === "enum") {
    input = document.createElement("select");
    for (const choice of definition.choices || []) {
      const option = document.createElement("option");
      option.value = JSON.stringify(choice.value);
      option.textContent = choice.label;
      option.selected = choice.value === definition.default;
      input.appendChild(option);
    }
  } else {
    input = document.createElement("input");
    input.type = definition.type === "boolean" ? "checkbox" : definition.type === "string" ? "text" : "number";
  }
  input.id = `parameter-${definition.id}`;
  input.dataset.parameterId = definition.id;
  input.dataset.parameterType = definition.type;
  if (definition.minimum != null) input.min = definition.minimum;
  if (definition.maximum != null) input.max = definition.maximum;
  if (definition.step != null) input.step = definition.step;
  if (definition.type === "boolean") input.checked = Boolean(definition.default);
  else if (definition.type !== "enum") input.value = definition.default;
  input.required = true;
  input.setAttribute("aria-label", `${definition.label}. ${definition.description || ""}`);
  wrapper.appendChild(input);
  if (definition.unit) {
    const unit = document.createElement("span");
    unit.className = "parameter-unit";
    unit.textContent = definition.unit;
    wrapper.appendChild(unit);
  }
  label.appendChild(wrapper);
  return label;
}

function renderParameters() {
  const simulation = selectedSimulation();
  const algorithm = selectedAlgorithm();
  const definitions = [...(simulation?.parameters || []), ...(algorithm?.parameters || [])];
  const primary = $("primary-parameters");
  const advanced = $("advanced-parameters");
  primary.replaceChildren();
  advanced.replaceChildren();
  for (const definition of definitions) {
    const destination = definition.group === "principal" ? primary : advanced;
    destination.appendChild(createParameterField(definition));
  }
  refreshStartAvailability();
}

function renderInputs() {
  const requiresDataset = simulationNeedsDataset();
  $("dataset-selector").hidden = !requiresDataset;
  $("sequence-selector").hidden = !requiresDataset;
  $("control-dataset").required = requiresDataset;
  $("control-sequence").required = requiresDataset;
  if (!requiresDataset) {
    $("control-dataset").replaceChildren();
    $("control-sequence").replaceChildren();
    renderProfiles();
    updateSelectionDescription();
    refreshStartAvailability();
    return;
  }
  const compatible = compatibleSequences();
  const datasetSelect = $("control-dataset");
  const previousDataset = datasetSelect.value;
  const datasetIds = [...new Set(compatible.map((value) => value.dataset_id))];
  datasetSelect.replaceChildren();
  for (const datasetId of datasetIds) {
    const dataset = catalog.datasets.find((value) => value.dataset_id === datasetId);
    if (!dataset) continue;
    const option = document.createElement("option");
    option.value = dataset.dataset_id;
    option.textContent = dataset.label;
    datasetSelect.appendChild(option);
  }
  if (datasetIds.includes(previousDataset)) datasetSelect.value = previousDataset;
  renderSequences();
}

function renderSequences() {
  const sequenceSelect = $("control-sequence");
  const previousSequence = sequenceSelect.value;
  sequenceSelect.replaceChildren();
  const compatibleIds = new Set(
    compatibleSequences()
      .filter((value) => value.dataset_id === selectedDataset()?.dataset_id)
      .map((value) => value.sequence_id),
  );
  for (const sequence of selectedDataset()?.sequences || []) {
    if (!compatibleIds.has(sequence.sequence_id)) continue;
    const compatibility = compatibleSequences().find(
      (value) => value.dataset_id === selectedDataset()?.dataset_id && value.sequence_id === sequence.sequence_id,
    );
    const option = document.createElement("option");
    option.value = sequence.sequence_id;
    option.textContent = sequence.label
      + (sequence.recommended ? " · recommandé" : "")
      + (compatibility?.runnable === false && sequence.available ? " · profil requis" : "");
    option.disabled = !sequence.available || compatibility?.runnable === false;
    sequenceSelect.appendChild(option);
  }
  if ([...sequenceSelect.options].some((option) => option.value === previousSequence && !option.disabled)) {
    sequenceSelect.value = previousSequence;
  } else {
    const firstAvailable = [...sequenceSelect.options].find((option) => !option.disabled);
    if (firstAvailable) sequenceSelect.value = firstAvailable.value;
  }
  renderProfiles();
  updateSelectionDescription();
  refreshStartAvailability();
}

function renderProfiles() {
  const simulation = selectedSimulation();
  const variant = selectedAlgorithm();
  const profiles = (simulation?.profiles || []).filter((profile) => {
    if (!profile.variant_settings?.[variant?.variant_id]) return false;
    if (profile.selectors?.dataset_id && profile.selectors.dataset_id !== selectedDataset()?.dataset_id) return false;
    const sequences = profile.selectors?.sequence_ids || [];
    return !sequences.length || sequences.includes(selectedSequence()?.sequence_id);
  });
  const wrapper = $("profile-selector");
  const select = $("control-profile");
  wrapper.hidden = profiles.length === 0;
  select.disabled = profiles.length === 0;
  select.required = profiles.length > 0;
  select.replaceChildren();
  for (const profile of profiles) {
    const option = document.createElement("option");
    option.value = profile.profile_id;
    option.textContent = profile.label + (profile.default ? " · défaut" : "");
    option.selected = Boolean(profile.default);
    select.appendChild(option);
  }
}

function renderVariants() {
  const simulation = selectedSimulation();
  const select = $("control-algorithm");
  select.replaceChildren();
  for (const variant of simulation?.variants || []) {
    const option = document.createElement("option");
    option.value = variant.variant_id;
    option.textContent = variant.label;
    option.disabled = !variant.available;
    select.appendChild(option);
  }
  $("variant-label").textContent = simulation?.domain === "localization" ? "Algorithme" : "Scénario";
  renderInputs();
  renderParameters();
}

function updateSelectionDescription() {
  if (["starting", "running", "stopping", "analyzing"].includes(currentRunState)) return;
  const dataset = selectedDataset();
  const sequence = selectedSequence();
  const algorithm = selectedAlgorithm();
  const simulation = selectedSimulation();
  if (!simulation || !algorithm || (simulationNeedsDataset() && (!dataset || !sequence))) return;
  $("run-message").textContent = [simulation.label, dataset?.label, algorithm.label].filter(Boolean).join(" · ");
  const duration = sequence ? `Durée nominale ${numberFormat(sequence.duration_s, sequence.duration_s < 10 ? 1 : 0)} s. ` : "";
  const safety = simulation.safety_class === "sitl_confirmed"
    ? "SITL uniquement : PX4 conserve le contrôle du vol et des failsafes. "
    : "";
  $("run-detail").textContent = `${sequence?.label ? `${sequence.label} — ` : ""}${duration}${safety}Les résultats et la configuration effective seront conservés.`;
}

function refreshStartAvailability() {
  const active = ["starting", "running", "stopping", "analyzing"].includes(currentRunState);
  const compatibility = compatibleSequences().find(
    (value) => value.dataset_id === selectedDataset()?.dataset_id && value.sequence_id === selectedSequence()?.sequence_id,
  );
  const inputReady = !simulationNeedsDataset()
    || Boolean(selectedSequence()?.available && compatibility?.runnable !== false);
  $("start-run").disabled = active || !selectedAlgorithm()?.available || !inputReady;
}

function setControlsLocked(locked) {
  for (const element of document.querySelectorAll("#run-form select, #run-form input")) {
    element.disabled = locked;
  }
  if (!locked) {
    $("control-dataset").disabled = !simulationNeedsDataset();
    $("control-sequence").disabled = !simulationNeedsDataset();
    $("control-profile").disabled = $("profile-selector").hidden;
  }
  refreshStartAvailability();
  $("stop-run").disabled = !["starting", "running"].includes(currentRunState);
}

function optionalMetric(value, digits, unit) {
  return Number.isFinite(value) ? `${numberFormat(value, digits)}${unit}` : "—";
}

function summaryMetricValue(metric) {
  if (metric.value == null) return "—";
  if (typeof metric.value === "boolean") return metric.value ? "Oui" : "Non";
  if (typeof metric.value === "number") {
    const absolute = Math.abs(metric.value);
    const digits = absolute >= 100 ? 0 : absolute >= 10 ? 1 : absolute >= 1 ? 2 : 3;
    return `${numberFormat(metric.value, digits)}${metric.unit ? ` ${metric.unit}` : ""}`;
  }
  return `${metric.value}${metric.unit ? ` ${metric.unit}` : ""}`;
}

function renderFinalMetrics(metrics, resultDirectory, summaryMetrics, domain) {
  finalMetrics = metrics || null;
  const button = $("toggle-final-metrics");
  button.disabled = !finalMetrics;
  if (!finalMetrics) {
    $("final-results").hidden = true;
    button.setAttribute("aria-expanded", "false");
    button.textContent = "Afficher les métriques finales";
    return;
  }
  const generic = $("generic-final-metrics");
  const lio = $("lio-final-metrics");
  const pipelinePanel = $("lio-pipeline-results");
  const useGeneric = domain !== "localization" && Array.isArray(summaryMetrics);
  generic.hidden = !useGeneric;
  lio.hidden = useGeneric;
  pipelinePanel.hidden = useGeneric;
  $("final-results-source").textContent = `${resultDirectory || "Résultat courant"}/${useGeneric ? "t0_metrics.json" : "metrics.json"}`;
  if (useGeneric) {
    generic.replaceChildren();
    for (const metric of summaryMetrics) {
      const article = document.createElement("article");
      const label = document.createElement("span");
      const value = document.createElement("strong");
      const detail = document.createElement("small");
      label.textContent = metric.label;
      value.textContent = summaryMetricValue(metric);
      detail.textContent = metric.status === "unknown" ? "Mesure enregistrée" : metric.status;
      article.append(label, value, detail);
      generic.appendChild(article);
    }
    return;
  }
  $("final-ate-translation").textContent = optionalMetric(finalMetrics.ate_translation_m?.rmse, 3, " m");
  $("final-ate-orientation").textContent = optionalMetric(finalMetrics.ate_orientation_deg?.rmse, 3, "°");
  $("final-rpe-translation").textContent = optionalMetric(finalMetrics.rpe?.translation_m?.rmse, 4, " m");
  $("final-rpe-rotation").textContent = optionalMetric(finalMetrics.rpe?.rotation_deg?.rmse, 3, "°");
  const estimate = finalMetrics.estimate_poses;
  const truth = finalMetrics.ground_truth_poses;
  const outputRatio = Number.isFinite(estimate) && Number.isFinite(truth) && truth > 0
    ? 100 * estimate / truth
    : null;
  $("final-output-ratio").textContent = optionalMetric(outputRatio, 2, " %");
  $("final-output-counts").textContent = Number.isFinite(estimate) && Number.isFinite(truth)
    ? `${estimate} / ${truth} poses`
    : "—";
  const pathRatio = finalMetrics.matched_path_length_m?.ratio_estimate_over_ground_truth;
  $("final-path-ratio").textContent = optionalMetric(
    Number.isFinite(pathRatio) ? 100 * pathRatio : null,
    2,
    " %",
  );

  const counters = finalMetrics.pipeline_counters;
  const accounting = finalMetrics.pipeline_accounting;
  const counterValue = (key) => Number.isFinite(counters?.[key]) ? String(counters[key]) : "—";
  $("pipeline-received").textContent = counterValue("scans_received");
  $("pipeline-preprocessed").textContent = counterValue("scans_preprocessed");
  $("pipeline-synchronized").textContent = counterValue("scans_synchronized");
  const rejected = counters
    ? (counters.scans_initialization || 0)
      + (counters.scans_rejected_undistort_empty || 0)
      + (counters.scans_map_initialization || 0)
      + (counters.scans_rejected_downsample || 0)
    : null;
  $("pipeline-rejected").textContent = Number.isFinite(rejected) ? String(rejected) : "—";
  $("pipeline-updates").textContent = counterValue("state_updates");
  $("pipeline-odometry").textContent = counterValue("odometry_published");
  if (counters && accounting) {
    $("pipeline-detail").textContent = `${accounting.preprocessed_minus_synchronized} scans prétraités non synchronisés · ${accounting.unaccounted_synchronized_scans} scans synchronisés non expliqués · ${accounting.state_updates_minus_odometry} mise(s) à jour sans odométrie.`;
  } else {
    $("pipeline-detail").textContent = "Ce résultat a été produit avant l'ajout de l'instrumentation interne.";
  }
}

function updateRunPanel(run) {
  if (!run?.state) return;
  const previousState = currentRunState;
  currentRunState = run.state;
  $("run-state").dataset.state = run.state;
  $("run-state-label").textContent = runStateLabels[run.state] || run.state;
  $("run-message").textContent = run.message || "";
  const active = ["starting", "running", "stopping", "analyzing"].includes(run.state);
  setControlsLocked(active);
  renderFinalMetrics(run.final_metrics, run.result_directory, run.summary_metrics, run.domain);
  if (run.result_directory) {
    const selection = [run.simulation_label, run.sequence_label, run.variant_label || run.algorithm_label].filter(Boolean).join(" · ");
    $("run-detail").textContent = `${selection}${selection ? " — " : ""}${run.result_directory}`;
  } else if (!active) {
    updateSelectionDescription();
  }
  if (["starting", "running", "stopping", "analyzing"].includes(previousState) && !active) {
    setTimeout(() => loadHistory(true), 0);
  }
}

function collectParameters() {
  const parameters = {};
  for (const input of document.querySelectorAll("[data-parameter-id]")) {
    if (input.dataset.parameterType === "boolean") parameters[input.dataset.parameterId] = input.checked;
    else if (input.dataset.parameterType === "enum") parameters[input.dataset.parameterId] = JSON.parse(input.value);
    else if (input.dataset.parameterType === "string") parameters[input.dataset.parameterId] = input.value;
    else parameters[input.dataset.parameterId] = Number(input.value);
  }
  return parameters;
}

async function initializeControls() {
  try {
    catalog = await apiRequest("/api/options");
    const simulationSelect = $("control-simulation");
    simulationSelect.replaceChildren();
    for (const simulation of catalog.simulations) {
      const option = document.createElement("option");
      option.value = simulation.simulation_id;
      option.textContent = simulation.label;
      simulationSelect.appendChild(option);
    }
    simulationSelect.disabled = false;
    $("control-dataset").disabled = false;
    $("control-sequence").disabled = false;
    $("control-algorithm").disabled = false;
    simulationSelect.addEventListener("change", renderVariants);
    $("control-dataset").addEventListener("change", renderSequences);
    $("control-sequence").addEventListener("change", () => {
      renderProfiles();
      updateSelectionDescription();
      refreshStartAvailability();
    });
    $("control-algorithm").addEventListener("change", () => {
      renderInputs();
      renderParameters();
      updateSelectionDescription();
    });
    $("control-profile").addEventListener("change", updateSelectionDescription);
    renderVariants();
    updateRunPanel(await apiRequest("/api/run/status"));
  } catch (error) {
    $("run-state").dataset.state = "failed";
    $("run-state-label").textContent = "Indisponible";
    $("run-message").textContent = error.message;
    $("run-detail").textContent = "Vérifiez le service fast-lio-dashboard.";
  }
}

function humanDate(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "medium" }).format(parsed);
}

function simulationLabel(simulationId) {
  return catalog?.simulations.find((value) => value.simulation_id === simulationId)?.label || simulationId;
}

function variantLabel(simulationId, variantId) {
  const simulation = catalog?.simulations.find((value) => value.simulation_id === simulationId);
  return simulation?.variants.find((value) => value.variant_id === variantId)?.label || variantId;
}

function datasetLabel(datasetId) {
  return catalog?.datasets.find((value) => value.dataset_id === datasetId)?.label || datasetId || "Sans dataset";
}

function sequenceLabel(datasetId, sequenceId) {
  const dataset = catalog?.datasets.find((value) => value.dataset_id === datasetId);
  return dataset?.sequences.find((value) => value.sequence_id === sequenceId)?.label || sequenceId || "—";
}

function populateHistoryFacet(id, values) {
  const select = $(id);
  const previous = select.value;
  const first = select.options[0]?.textContent || "Tous";
  select.replaceChildren();
  const all = document.createElement("option");
  all.value = "";
  all.textContent = first;
  select.appendChild(all);
  for (const facet of values || []) {
    const option = document.createElement("option");
    option.value = facet.value;
    option.textContent = `${facet.value} (${facet.count})`;
    select.appendChild(option);
  }
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
}

function historyQuery(forceRefresh = false) {
  const parameters = new URLSearchParams();
  const mapping = {
    q: "history-query",
    domain: "history-domain",
    dataset_id: "history-dataset",
    algorithm_id: "history-algorithm",
    scenario_id: "history-scenario",
    state: "history-state",
    date_from: "history-date-from",
    date_to: "history-date-to",
    tag: "history-tag",
  };
  for (const [name, id] of Object.entries(mapping)) {
    const value = $(id).value.trim();
    if (value) parameters.set(name, value);
  }
  if (forceRefresh) parameters.set("refresh", "1");
  return parameters.toString();
}

function createHistoryResult(item) {
  const wrapper = document.createElement("div");
  wrapper.className = "history-result-row";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "history-result";
  button.dataset.resultId = item.result_id;
  button.setAttribute("aria-current", String(currentHistoryDetail?.summary?.result_id === item.result_id));
  const title = document.createElement("span");
  title.className = "history-result-title";
  title.textContent = `${simulationLabel(item.simulation_id)} · ${variantLabel(item.simulation_id, item.variant_id)}`;
  const state = document.createElement("span");
  state.className = "history-result-state";
  state.textContent = item.state;
  const meta = document.createElement("span");
  meta.className = "history-result-meta";
  meta.textContent = `${humanDate(item.created_at_utc)} · ${datasetLabel(item.dataset_id)}${item.sequence_id ? ` · ${sequenceLabel(item.dataset_id, item.sequence_id)}` : ""}`;
  const metrics = document.createElement("span");
  metrics.className = "history-result-metrics";
  metrics.textContent = (item.metric_preview || []).slice(0, 3).map((metric) => `${metric.label}: ${summaryMetricValue(metric)}`).join(" · ") || "Métriques non disponibles";
  button.append(title, state, meta, metrics);
  button.addEventListener("click", () => openHistoryDetail(item.result_id));
  const compare = document.createElement("button");
  compare.type = "button";
  compare.className = "history-compare-toggle";
  compare.dataset.compareResultId = item.result_id;
  compare.setAttribute("aria-pressed", String(comparisonSelection.has(item.result_id)));
  compare.textContent = comparisonSelection.has(item.result_id) ? "Retirer" : "Ajouter";
  compare.addEventListener("click", () => toggleComparisonResult(item));
  wrapper.append(button, compare);
  return wrapper;
}

async function loadHistory(forceRefresh = false) {
  const results = $("history-results");
  results.replaceChildren();
  const loading = document.createElement("p");
  loading.className = "history-empty";
  loading.textContent = forceRefresh ? "Reconstruction de l’index…" : "Recherche des résultats…";
  results.appendChild(loading);
  try {
    const index = await apiRequest(`/api/results?${historyQuery(forceRefresh)}`);
    $("history-count").textContent = `${index.total} résultat${index.total === 1 ? "" : "s"} · ${index.invalid_result_count} invalide${index.invalid_result_count === 1 ? "" : "s"}`;
    populateHistoryFacet("history-domain", index.facets.domain);
    populateHistoryFacet("history-dataset", index.facets.dataset_id);
    populateHistoryFacet("history-algorithm", index.facets.algorithm_id);
    populateHistoryFacet("history-scenario", index.facets.scenario_id);
    populateHistoryFacet("history-state", index.facets.state);
    populateHistoryFacet("history-tag", index.facets.tags);
    results.replaceChildren();
    if (!index.items.length) {
      loading.textContent = "Aucun résultat ne correspond aux filtres.";
      results.appendChild(loading);
      return;
    }
    for (const item of index.items) results.appendChild(createHistoryResult(item));
  } catch (error) {
    results.replaceChildren();
    loading.textContent = error.message;
    results.appendChild(loading);
    $("history-count").textContent = "Index indisponible";
  }
}

function selectedComparisonIds() {
  return [...comparisonSelection.keys()];
}

function setComparisonStatus(message, state = "waiting") {
  const status = $("comparison-status");
  status.textContent = message;
  status.dataset.state = state;
}

function updateHistoryComparisonButtons() {
  for (const button of document.querySelectorAll("[data-compare-result-id]")) {
    const selected = comparisonSelection.has(button.dataset.compareResultId);
    button.setAttribute("aria-pressed", String(selected));
    button.textContent = selected ? "Retirer" : "Ajouter";
  }
}

function renderComparisonSelection() {
  const tray = $("comparison-selection");
  tray.replaceChildren();
  if (!comparisonSelection.size) {
    const empty = document.createElement("p");
    empty.textContent = "Sélection vide · utilisez le bouton « Ajouter » sur un résultat.";
    tray.appendChild(empty);
  } else {
    [...comparisonSelection.values()].forEach((item, index) => {
      const chip = document.createElement("div");
      chip.className = "comparison-chip";
      chip.style.setProperty("--chip-color", comparisonPalette[index]);
      const label = document.createElement("span");
      label.textContent = `${variantLabel(item.simulation_id, item.variant_id)} · ${item.run_id}`;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "×";
      remove.setAttribute("aria-label", `Retirer ${label.textContent}`);
      remove.addEventListener("click", () => toggleComparisonResult(item));
      chip.append(label, remove);
      tray.appendChild(chip);
    });
  }
  $("comparison-run").disabled = comparisonSelection.size < 2;
  $("comparison-clear").disabled = comparisonSelection.size === 0;
  updateHistoryComparisonButtons();
}

function invalidateComparison() {
  currentComparison = null;
  $("comparison-results").hidden = true;
  $("comparison-report").hidden = true;
  setComparisonStatus(
    comparisonSelection.size < 2
      ? "Sélectionnez au moins deux résultats."
      : `${comparisonSelection.size} résultats prêts · lancez la vérification de compatibilité.`,
  );
}

function toggleComparisonResult(item) {
  if (comparisonSelection.has(item.result_id)) {
    comparisonSelection.delete(item.result_id);
  } else if (comparisonSelection.size >= 4) {
    setComparisonStatus("La comparaison est limitée à quatre résultats.", "error");
    return;
  } else {
    comparisonSelection.set(item.result_id, item);
  }
  invalidateComparison();
  renderComparisonSelection();
}

function comparisonHeaderCell(run) {
  const cell = document.createElement("th");
  const marker = document.createElement("span");
  marker.textContent = "● ";
  marker.style.color = run.color;
  cell.append(marker, document.createTextNode(run.label));
  return cell;
}

function comparisonTable(runs, rows) {
  const table = document.createElement("table");
  table.className = "comparison-table";
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  const first = document.createElement("th");
  first.textContent = "Élément";
  headRow.append(first, ...runs.map(comparisonHeaderCell));
  head.appendChild(headRow);
  const body = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    if (row.className) tr.className = row.className;
    const label = document.createElement("td");
    label.textContent = row.label;
    if (row.note) {
      const note = document.createElement("small");
      note.textContent = row.note;
      label.appendChild(note);
    }
    tr.appendChild(label);
    for (const cellValue of row.cells) {
      const cell = document.createElement("td");
      cell.textContent = cellValue.text;
      if (cellValue.best) cell.className = "comparison-best";
      tr.appendChild(cell);
    }
    body.appendChild(tr);
  }
  table.append(head, body);
  return table;
}

function comparisonValue(value) {
  if (value == null) return "—";
  if (typeof value === "number") {
    const digits = Math.abs(value) >= 100 ? 1 : Math.abs(value) >= 10 ? 2 : 4;
    return numberFormat(value, digits);
  }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function renderComparison(comparison) {
  currentComparison = comparison;
  const runs = comparison.runs;
  const compatibility = comparison.compatibility;
  const statusText = compatibility.compatible
    ? `Compatibilité validée · ${compatibility.comparison_group} · ${compatibility.common_metric_ids.length} métriques communes.`
    : `Comparaison refusée · ${compatibility.reasons.join(" ")}`;
  setComparisonStatus(statusText, compatibility.compatible ? "valid" : "error");
  $("comparison-results").hidden = false;
  $("comparison-overlay").disabled = !(compatibility.compatible && compatibility.overlay_available);

  const metricRows = comparison.metrics.map((metric) => ({
    label: metric.label,
    note: `${metric.unit || "sans unité"} · ${metric.comparable ? (metric.direction === "lower" ? "plus bas = mieux" : metric.direction === "higher" ? "plus haut = mieux" : "informatif") : "non classable"}`,
    cells: runs.map((run) => {
      const value = metric.values.find((candidate) => candidate.result_id === run.result_id);
      return {
        text: comparisonValue(value?.value),
        best: metric.best_result_ids.includes(run.result_id),
      };
    }),
  }));
  $("comparison-metrics").replaceChildren(comparisonTable(runs, metricRows));

  const parameterRows = comparison.parameters.map((parameter) => ({
    label: parameter.parameter_id,
    className: parameter.same_for_all ? "" : "comparison-different",
    cells: runs.map((run) => ({
      text: comparisonValue(parameter.values.find((candidate) => candidate.result_id === run.result_id)?.value),
    })),
  }));
  $("comparison-parameters").replaceChildren(comparisonTable(runs, parameterRows));

  const versionRows = [
    ["Runner", "runner_id"],
    ["Algorithme déclaré", "algorithm"],
    ["Source", "source_kind"],
    ["Version du contrat", "result_contract_version"],
    ["Schéma du processus", "process_schema_version"],
    ["Code de sortie", "process_exit_code"],
  ].map(([label, field]) => ({
    label,
    cells: runs.map((run) => ({
      text: comparisonValue(comparison.versions.find((candidate) => candidate.result_id === run.result_id)?.[field]),
    })),
  }));
  $("comparison-versions").replaceChildren(comparisonTable(runs, versionRows));
}

async function compareSelectedResults() {
  $("comparison-run").disabled = true;
  setComparisonStatus("Vérification des résultats et construction des tableaux…", "loading");
  try {
    const comparison = await apiRequest("/api/comparisons/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ result_ids: selectedComparisonIds() }),
    });
    renderComparison(comparison);
  } catch (error) {
    setComparisonStatus(error.message, "error");
  } finally {
    $("comparison-run").disabled = comparisonSelection.size < 2;
  }
}

function comparisonRequestOptions() {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ result_ids: selectedComparisonIds() }),
  };
}

async function overlayComparison() {
  $("comparison-overlay").disabled = true;
  setComparisonStatus("Lecture sécurisée des trajectoires archivées…", "loading");
  try {
    const replay = await apiRequest("/api/comparisons/replay", comparisonRequestOptions());
    offlineReplayActive = true;
    comparisonCurves = replay.curves || [];
    Object.values(histories).forEach((values) => values.splice(0));
    $("chart-cpu-label").textContent = "CPU · voir le tableau comparatif";
    $("chart-memory-label").textContent = "Mémoire · voir le tableau comparatif";
    $("chart-realtime-label").textContent = "Temps réel · voir le tableau comparatif";
    $("chart-ate-label").textContent = comparisonCurves.length ? "ATE cumulée comparée (m)" : "Courbes non disponibles";
    $("chart-cpu-value").textContent = "—";
    $("chart-memory-value").textContent = "—";
    $("chart-realtime-value").textContent = "—";
    $("chart-ate-value").textContent = `${comparisonCurves.length} courbe${comparisonCurves.length === 1 ? "" : "s"}`;
    if (renderer) {
      renderer.autoFit = true;
      renderer.setData(replay.scene, true);
    }
    $("scene-detail").textContent = `${replay.scene.comparison_paths.length} trajectoires archivées superposées · ${replay.notes.join(" ")}`;
    $("resume-live").hidden = false;
    setComparisonStatus("Superposition chargée sans relancer les algorithmes.", "valid");
    $("scene").scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    setComparisonStatus(error.message, "error");
  } finally {
    $("comparison-overlay").disabled = !(currentComparison?.compatibility?.compatible && currentComparison?.compatibility?.overlay_available);
  }
}

async function loadComparisonReport(exportFile) {
  const button = exportFile ? $("comparison-report-export") : $("comparison-report-open");
  button.disabled = true;
  try {
    const response = await apiTextRequest("/api/comparisons/report", comparisonRequestOptions());
    if (exportFile) {
      const match = response.disposition.match(/filename="?([^";]+)"?/i);
      const link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob([response.content], { type: "text/markdown;charset=utf-8" }));
      link.download = match?.[1] || "comparaison_T0_4.md";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(link.href);
      setComparisonStatus("Rapport Markdown exporté.", "valid");
    } else {
      $("comparison-report-content").textContent = response.content;
      $("comparison-report").hidden = false;
      $("comparison-report").open = true;
    }
  } catch (error) {
    setComparisonStatus(error.message, "error");
  } finally {
    button.disabled = false;
  }
}

function initializeComparison() {
  $("comparison-run").addEventListener("click", compareSelectedResults);
  $("comparison-clear").addEventListener("click", () => {
    comparisonSelection.clear();
    invalidateComparison();
    renderComparisonSelection();
  });
  $("comparison-overlay").addEventListener("click", overlayComparison);
  $("comparison-report-open").addEventListener("click", () => loadComparisonReport(false));
  $("comparison-report-export").addEventListener("click", () => loadComparisonReport(true));
  renderComparisonSelection();
}

function fact(label, value) {
  const wrapper = document.createElement("div");
  const caption = document.createElement("span");
  const content = document.createElement("strong");
  caption.textContent = label;
  content.textContent = value || "—";
  wrapper.append(caption, content);
  return wrapper;
}

function renderHistoryDetail(detail) {
  currentHistoryDetail = detail;
  const summary = detail.summary;
  const panel = $("history-detail");
  panel.hidden = false;
  $("history-detail-domain").textContent = summary.domain === "localization" ? "LOCALISATION · ARCHIVE" : "VOL PX4 · ARCHIVE";
  $("history-detail-title").textContent = `${simulationLabel(summary.simulation_id)} · ${variantLabel(summary.simulation_id, summary.variant_id)}`;
  $("history-detail-path").textContent = summary.relative_directory;
  $("history-detail-state").textContent = summary.state;
  $("history-detail-state").dataset.state = summary.state;
  $("history-replay").disabled = !summary.replay_available;
  $("history-duplicate").disabled = !detail.duplicate_request;
  const facts = $("history-facts");
  facts.replaceChildren(
    fact("Run", summary.run_id),
    fact("Date", humanDate(summary.created_at_utc)),
    fact("Dataset", datasetLabel(summary.dataset_id)),
    fact("Séquence", sequenceLabel(summary.dataset_id, summary.sequence_id)),
    fact("Runner", summary.runner_id),
    fact("Contrat source", summary.source_kind),
  );
  const metrics = $("history-metrics");
  metrics.replaceChildren();
  for (const metric of detail.metrics.summary || []) {
    const article = document.createElement("article");
    const label = document.createElement("span");
    const value = document.createElement("strong");
    const status = document.createElement("small");
    label.textContent = metric.label;
    value.textContent = summaryMetricValue(metric);
    status.textContent = metric.status === "unknown" ? "Mesure enregistrée" : metric.status;
    article.append(label, value, status);
    metrics.appendChild(article);
  }
  if (!metrics.children.length) metrics.appendChild(fact("Métriques", "Indisponibles"));
  const events = $("history-events");
  events.replaceChildren();
  for (const event of detail.events || []) {
    const row = document.createElement("div");
    row.className = "history-event";
    row.dataset.severity = event.severity;
    const timestamp = document.createElement("time");
    timestamp.textContent = Number.isFinite(event.elapsed_s) ? `${numberFormat(event.elapsed_s, 2)} s` : humanDate(event.timestamp_utc);
    const type = document.createElement("strong");
    type.textContent = event.event_type;
    const message = document.createElement("p");
    message.textContent = event.message || event.state || "—";
    row.append(timestamp, type, message);
    events.appendChild(row);
  }
  if (!events.children.length) events.appendChild(fact("Événements", "Non archivés"));
  const artifacts = $("history-artifacts");
  artifacts.replaceChildren();
  for (const artifact of detail.artifacts.items || []) {
    const row = document.createElement("div");
    row.className = "history-artifact";
    row.dataset.available = String(artifact.available);
    const kind = document.createElement("span");
    kind.textContent = artifact.kind;
    const label = document.createElement("strong");
    label.textContent = artifact.label;
    const path = document.createElement("small");
    path.textContent = `${artifact.path}${artifact.available ? "" : " · absent"}`;
    row.append(kind, label, path);
    artifacts.appendChild(row);
  }
  if (!artifacts.children.length) artifacts.appendChild(fact("Artefacts", "Non déclarés"));
  $("history-note").textContent = detail.duplicate_request
    ? "La duplication recharge les sélecteurs et paramètres, sans démarrer automatiquement un essai."
    : "Cette archive ne contient pas assez d’informations compatibles pour être dupliquée.";
  for (const item of document.querySelectorAll(".history-result")) {
    item.setAttribute("aria-current", String(item.dataset.resultId === summary.result_id));
  }
}

async function openHistoryDetail(resultId) {
  $("history-note").textContent = "Chargement de la fiche…";
  try {
    renderHistoryDetail(await apiRequest(`/api/results/${encodeURIComponent(resultId)}`));
  } catch (error) {
    $("history-detail").hidden = false;
    $("history-note").textContent = error.message;
  }
}

function duplicateHistoryConfiguration() {
  const payload = currentHistoryDetail?.duplicate_request;
  if (!payload || !catalog) return;
  const simulation = $("control-simulation");
  simulation.value = payload.simulation_id;
  renderVariants();
  $("control-algorithm").value = payload.variant_id;
  renderInputs();
  renderParameters();
  const datasetInput = (payload.inputs || []).find((value) => value.kind === "dataset_sequence");
  if (datasetInput?.reference) {
    $("control-dataset").value = datasetInput.reference.dataset_id;
    renderSequences();
    $("control-sequence").value = datasetInput.reference.sequence_id;
    renderProfiles();
  }
  if (payload.profile_id && [...$("control-profile").options].some((option) => option.value === payload.profile_id)) {
    $("control-profile").value = payload.profile_id;
  }
  for (const [parameterId, parameterValue] of Object.entries(payload.parameters || {})) {
    const input = $(`parameter-${parameterId}`);
    if (!input) continue;
    if (input.dataset.parameterType === "boolean") input.checked = Boolean(parameterValue);
    else if (input.dataset.parameterType === "enum") input.value = JSON.stringify(parameterValue);
    else input.value = parameterValue;
  }
  updateSelectionDescription();
  refreshStartAvailability();
  $("run-message").textContent = "Configuration historique chargée · vérifiez les paramètres avant lancement.";
  $("history-note").textContent = "Configuration copiée dans la console d’essai. Aucun runner n’a été lancé.";
  $("control-title").scrollIntoView({ behavior: "smooth", block: "start" });
}

function resetChartLabels() {
  $("chart-cpu-label").textContent = "CPU instantané";
  $("chart-memory-label").textContent = "Mémoire résidente";
  $("chart-realtime-label").textContent = "Facteur temps réel";
  $("chart-ate-label").textContent = "ATE en ligne";
}

async function replayHistoryResult() {
  const resultId = currentHistoryDetail?.summary?.result_id;
  if (!resultId) return;
  $("history-replay").disabled = true;
  $("history-note").textContent = "Lecture des artefacts enregistrés…";
  try {
    const replay = await apiRequest(`/api/results/${encodeURIComponent(resultId)}/replay`);
    offlineReplayActive = true;
    comparisonCurves = [];
    Object.values(histories).forEach((values) => values.splice(0));
    const curve = replay.curves?.[0];
    if (curve) histories.ate.push(...curve.values);
    $("chart-cpu-label").textContent = "CPU · non archivé";
    $("chart-memory-label").textContent = "Mémoire · valeur synthétique";
    $("chart-realtime-label").textContent = "Temps réel · valeur synthétique";
    $("chart-ate-label").textContent = curve ? `${curve.label} (${curve.unit})` : "Courbe non disponible";
    $("chart-cpu-value").textContent = "—";
    $("chart-memory-value").textContent = "—";
    $("chart-realtime-value").textContent = "—";
    $("chart-ate-value").textContent = curve?.values?.length ? `${numberFormat(curve.values.at(-1)[1], 3)} ${curve.unit}` : "—";
    if (renderer) {
      renderer.autoFit = true;
      renderer.setData(replay.scene, true);
    }
    $("scene-detail").textContent = `Archive ${currentHistoryDetail.summary.run_id} · ${replay.notes.join(" ")}`;
    $("resume-live").hidden = false;
    $("history-note").textContent = "Archive rechargée dans la scène et les graphiques, sans exécuter de simulation.";
    $("scene").scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    $("history-note").textContent = error.message;
  } finally {
    $("history-replay").disabled = !currentHistoryDetail?.summary?.replay_available;
  }
}

function resumeLiveDashboard() {
  offlineReplayActive = false;
  comparisonCurves = [];
  Object.values(histories).forEach((values) => values.splice(0));
  lastHistoryTime = -Infinity;
  resetChartLabels();
  $("resume-live").hidden = true;
  $("scene-detail").textContent = "Retour au flux ROS 2 en direct…";
  if (renderer) renderer.autoFit = true;
}

function initializeHistory() {
  $("history-filters").addEventListener("submit", (event) => {
    event.preventDefault();
    loadHistory(false);
  });
  $("history-refresh").addEventListener("click", () => loadHistory(true));
  $("history-reset").addEventListener("click", () => {
    $("history-filters").reset();
    loadHistory(false);
  });
  $("history-replay").addEventListener("click", replayHistoryResult);
  $("history-duplicate").addEventListener("click", duplicateHistoryConfiguration);
  $("resume-live").addEventListener("click", resumeLiveDashboard);
  loadHistory(false);
}

function compileShader(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    throw new Error(gl.getShaderInfoLog(shader));
  }
  return shader;
}

function createProgram(gl, vertex, fragment) {
  const program = gl.createProgram();
  gl.attachShader(program, compileShader(gl, gl.VERTEX_SHADER, vertex));
  gl.attachShader(program, compileShader(gl, gl.FRAGMENT_SHADER, fragment));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    throw new Error(gl.getProgramInfoLog(program));
  }
  return program;
}

function normalize3(vector) {
  const length = Math.hypot(vector[0], vector[1], vector[2]) || 1;
  return vector.map((value) => value / length);
}

function subtract3(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
function dot3(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
function cross3(a, b) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

function perspective(fov, aspect, near, far) {
  const f = 1 / Math.tan(fov / 2);
  const range = 1 / (near - far);
  return new Float32Array([
    f / aspect, 0, 0, 0,
    0, f, 0, 0,
    0, 0, (far + near) * range, -1,
    0, 0, 2 * far * near * range, 0,
  ]);
}

function lookAt(eye, center) {
  const z = normalize3(subtract3(eye, center));
  const x = normalize3(cross3([0, 0, 1], z));
  const y = cross3(z, x);
  return new Float32Array([
    x[0], y[0], z[0], 0,
    x[1], y[1], z[1], 0,
    x[2], y[2], z[2], 0,
    -dot3(x, eye), -dot3(y, eye), -dot3(z, eye), 1,
  ]);
}

function multiply4(a, b) {
  const result = new Float32Array(16);
  for (let column = 0; column < 4; column += 1) {
    for (let row = 0; row < 4; row += 1) {
      let value = 0;
      for (let index = 0; index < 4; index += 1) {
        value += a[index * 4 + row] * b[column * 4 + index];
      }
      result[column * 4 + row] = value;
    }
  }
  return result;
}

function hexToRgb(hex) {
  const value = hex.replace("#", "");
  return [0, 2, 4].map((offset) => parseInt(value.slice(offset, offset + 2), 16) / 255);
}

function rotateByQuaternion(vector, quaternion) {
  const [x, y, z, w] = quaternion;
  const q = [x, y, z];
  const t = cross3(q, vector).map((value) => 2 * value);
  const correction = cross3(q, t);
  return vector.map((value, index) => value + w * t[index] + correction[index]);
}

function buildPx4Vehicle(pose) {
  if (!pose?.position || !pose?.orientation_xyzw) return [];
  const localLines = [
    [-0.32, -0.32, 0], [0.32, 0.32, 0],
    [-0.32, 0.32, 0], [0.32, -0.32, 0],
    [0, 0, -0.14], [0, 0, 0.16],
    [0, 0, 0], [0.55, 0, 0],
    [0.55, 0, 0], [0.43, -0.09, 0],
    [0.55, 0, 0], [0.43, 0.09, 0],
  ];
  const [px, py, pz] = pose.position;
  return localLines.map((point) => {
    const rotated = rotateByQuaternion(point, pose.orientation_xyzw);
    return [rotated[0] + px, rotated[1] + py, rotated[2] + pz];
  });
}

class SceneRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.gl = canvas.getContext("webgl", { antialias: true, alpha: false });
    if (!this.gl) throw new Error("WebGL n'est pas disponible sur ce navigateur.");
    this.target = [0, 0, 0];
    this.distance = 45;
    this.yaw = -0.8;
    this.pitch = 0.55;
    this.cloudVisible = true;
    this.autoFit = true;
    this.dragging = false;
    this.lastPointer = [0, 0];
    this.cloudCount = 0;
    this.estimateCount = 0;
    this.truthCount = 0;
    this.px4PathCount = 0;
    this.px4VehicleCount = 0;
    this.comparisonBuffers = [];

    const pointVertex = `
      attribute vec4 a_point;
      uniform mat4 u_mvp;
      uniform float u_size;
      varying float v_intensity;
      void main() {
        gl_Position = u_mvp * vec4(a_point.xyz, 1.0);
        gl_PointSize = u_size;
        v_intensity = a_point.w;
      }
    `;
    const pointFragment = `
      precision mediump float;
      varying float v_intensity;
      void main() {
        vec2 centered = gl_PointCoord - vec2(0.5);
        if (dot(centered, centered) > 0.25) discard;
        vec3 low = vec3(0.10, 0.48, 0.62);
        vec3 high = vec3(0.55, 0.98, 0.78);
        gl_FragColor = vec4(mix(low, high, v_intensity), 0.92);
      }
    `;
    const lineVertex = `
      attribute vec3 a_position;
      uniform mat4 u_mvp;
      void main() { gl_Position = u_mvp * vec4(a_position, 1.0); }
    `;
    const lineFragment = `
      precision mediump float;
      uniform vec3 u_color;
      uniform float u_alpha;
      void main() { gl_FragColor = vec4(u_color, u_alpha); }
    `;
    this.pointProgram = createProgram(this.gl, pointVertex, pointFragment);
    this.lineProgram = createProgram(this.gl, lineVertex, lineFragment);
    this.cloudBuffer = this.gl.createBuffer();
    this.estimateBuffer = this.gl.createBuffer();
    this.truthBuffer = this.gl.createBuffer();
    this.px4PathBuffer = this.gl.createBuffer();
    this.px4VehicleBuffer = this.gl.createBuffer();
    this.gridBuffer = this.gl.createBuffer();
    this.gridCount = 0;
    this.installControls();
    this.buildGrid([-25, -25, 0], [25, 25, 0]);
    requestAnimationFrame(() => this.render());
  }

  installControls() {
    this.canvas.addEventListener("pointerdown", (event) => {
      this.dragging = true;
      this.lastPointer = [event.clientX, event.clientY];
      this.canvas.setPointerCapture(event.pointerId);
    });
    this.canvas.addEventListener("pointermove", (event) => {
      if (!this.dragging) return;
      const dx = event.clientX - this.lastPointer[0];
      const dy = event.clientY - this.lastPointer[1];
      this.lastPointer = [event.clientX, event.clientY];
      this.yaw -= dx * 0.006;
      this.pitch = Math.max(-1.35, Math.min(1.35, this.pitch + dy * 0.006));
    });
    const release = () => { this.dragging = false; };
    this.canvas.addEventListener("pointerup", release);
    this.canvas.addEventListener("pointercancel", release);
    this.canvas.addEventListener("wheel", (event) => {
      event.preventDefault();
      this.distance = Math.max(2, Math.min(2000, this.distance * Math.exp(event.deltaY * 0.001)));
    }, { passive: false });
  }

  upload(buffer, data) {
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, buffer);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, data, this.gl.DYNAMIC_DRAW);
  }

  setData(scene, cloudChanged) {
    if (cloudChanged) {
      const cloud = new Float32Array(scene.cloud);
      this.upload(this.cloudBuffer, cloud);
      this.cloudCount = cloud.length / 4;
    }
    const estimate = new Float32Array(scene.estimate.flat());
    const truth = new Float32Array(scene.truth.flat());
    const px4Path = new Float32Array((scene.px4_path || []).flat());
    const px4Vehicle = new Float32Array(buildPx4Vehicle(scene.px4_pose).flat());
    this.upload(this.estimateBuffer, estimate);
    this.upload(this.truthBuffer, truth);
    this.upload(this.px4PathBuffer, px4Path);
    this.upload(this.px4VehicleBuffer, px4Vehicle);
    this.estimateCount = estimate.length / 3;
    this.truthCount = truth.length / 3;
    this.px4PathCount = px4Path.length / 3;
    this.px4VehicleCount = px4Vehicle.length / 3;
    const comparisonPaths = scene.comparison_paths || [];
    while (this.comparisonBuffers.length < comparisonPaths.length) {
      this.comparisonBuffers.push({ buffer: this.gl.createBuffer(), count: 0, color: colors.cyan });
    }
    this.comparisonBuffers.forEach((entry, index) => {
      const path = comparisonPaths[index];
      if (!path) {
        entry.count = 0;
        return;
      }
      const points = new Float32Array((path.points || []).flat());
      this.upload(entry.buffer, points);
      entry.count = points.length / 3;
      entry.color = path.color || comparisonPalette[index % comparisonPalette.length];
    });
    updateComparisonLegend(comparisonPaths, Boolean(scene.truth?.length));
    this.latestScene = scene;
    if (this.autoFit && (this.estimateCount > 8 || this.cloudCount > 100 || scene.px4_pose || comparisonPaths.length)) {
      this.fitView();
      this.autoFit = false;
    }
  }

  fitView() {
    if (!this.latestScene) return;
    const points = [];
    for (const point of this.latestScene.estimate) points.push(point);
    for (const point of this.latestScene.truth) points.push(point);
    for (const point of this.latestScene.px4_path || []) points.push(point);
    for (const path of this.latestScene.comparison_paths || []) {
      for (const point of path.points || []) points.push(point);
    }
    if (this.latestScene.px4_pose?.position) points.push(this.latestScene.px4_pose.position);
    const cloud = this.latestScene.cloud;
    const cloudStep = Math.max(4, Math.floor(cloud.length / 2000 / 4) * 4);
    for (let index = 0; index < cloud.length; index += cloudStep) {
      points.push([cloud[index], cloud[index + 1], cloud[index + 2]]);
    }
    if (!points.length) return;
    const minimum = [Infinity, Infinity, Infinity];
    const maximum = [-Infinity, -Infinity, -Infinity];
    for (const point of points) {
      for (let axis = 0; axis < 3; axis += 1) {
        minimum[axis] = Math.min(minimum[axis], point[axis]);
        maximum[axis] = Math.max(maximum[axis], point[axis]);
      }
    }
    this.target = minimum.map((value, index) => (value + maximum[index]) / 2);
    const span = Math.max(8, ...maximum.map((value, index) => value - minimum[index]));
    this.distance = Math.max(12, span * 1.45);
    this.buildGrid(minimum, maximum);
  }

  buildGrid(minimum, maximum) {
    const span = Math.max(20, maximum[0] - minimum[0], maximum[1] - minimum[1]);
    const exponent = Math.floor(Math.log10(span / 10));
    const base = 10 ** exponent;
    const raw = span / 10 / base;
    const step = (raw <= 1 ? 1 : raw <= 2 ? 2 : raw <= 5 ? 5 : 10) * base;
    const centerX = (minimum[0] + maximum[0]) / 2;
    const centerY = (minimum[1] + maximum[1]) / 2;
    const half = Math.ceil(span / step / 2 + 2) * step;
    const startX = Math.floor((centerX - half) / step) * step;
    const endX = Math.ceil((centerX + half) / step) * step;
    const startY = Math.floor((centerY - half) / step) * step;
    const endY = Math.ceil((centerY + half) / step) * step;
    const lines = [];
    for (let x = startX; x <= endX + step / 2; x += step) {
      lines.push(x, startY, 0, x, endY, 0);
    }
    for (let y = startY; y <= endY + step / 2; y += step) {
      lines.push(startX, y, 0, endX, y, 0);
    }
    const grid = new Float32Array(lines);
    this.upload(this.gridBuffer, grid);
    this.gridCount = grid.length / 3;
  }

  resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.floor(this.canvas.clientWidth * dpr));
    const height = Math.max(1, Math.floor(this.canvas.clientHeight * dpr));
    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width;
      this.canvas.height = height;
    }
  }

  drawLine(buffer, count, mode, color, alpha, mvp) {
    if (!count) return;
    const gl = this.gl;
    gl.useProgram(this.lineProgram);
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    const position = gl.getAttribLocation(this.lineProgram, "a_position");
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 3, gl.FLOAT, false, 0, 0);
    gl.uniformMatrix4fv(gl.getUniformLocation(this.lineProgram, "u_mvp"), false, mvp);
    gl.uniform3fv(gl.getUniformLocation(this.lineProgram, "u_color"), hexToRgb(color));
    gl.uniform1f(gl.getUniformLocation(this.lineProgram, "u_alpha"), alpha);
    gl.drawArrays(mode, 0, count);
  }

  render() {
    this.resize();
    const gl = this.gl;
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.clearColor(0.027, 0.063, 0.082, 1);
    gl.clearDepth(1);
    gl.enable(gl.DEPTH_TEST);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

    const cosPitch = Math.cos(this.pitch);
    const eye = [
      this.target[0] + this.distance * cosPitch * Math.cos(this.yaw),
      this.target[1] + this.distance * cosPitch * Math.sin(this.yaw),
      this.target[2] + this.distance * Math.sin(this.pitch),
    ];
    const projection = perspective(Math.PI / 4, this.canvas.width / this.canvas.height, 0.05, 5000);
    const mvp = multiply4(projection, lookAt(eye, this.target));
    this.drawLine(this.gridBuffer, this.gridCount, gl.LINES, "#31505c", 0.58, mvp);
    this.drawLine(this.truthBuffer, this.truthCount, gl.LINE_STRIP, colors.orange, 0.95, mvp);
    this.drawLine(this.estimateBuffer, this.estimateCount, gl.LINE_STRIP, colors.green, 1, mvp);
    for (const entry of this.comparisonBuffers) {
      this.drawLine(entry.buffer, entry.count, gl.LINE_STRIP, entry.color, 1, mvp);
    }
    this.drawLine(this.px4PathBuffer, this.px4PathCount, gl.LINE_STRIP, colors.blue, 1, mvp);
    this.drawLine(this.px4VehicleBuffer, this.px4VehicleCount, gl.LINES, colors.cyan, 1, mvp);

    if (this.cloudVisible && this.cloudCount) {
      gl.useProgram(this.pointProgram);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.cloudBuffer);
      const point = gl.getAttribLocation(this.pointProgram, "a_point");
      gl.enableVertexAttribArray(point);
      gl.vertexAttribPointer(point, 4, gl.FLOAT, false, 0, 0);
      gl.uniformMatrix4fv(gl.getUniformLocation(this.pointProgram, "u_mvp"), false, mvp);
      gl.uniform1f(gl.getUniformLocation(this.pointProgram, "u_size"), Math.min(5, 2.2 * (window.devicePixelRatio || 1)));
      gl.drawArrays(gl.POINTS, 0, this.cloudCount);
    }
    requestAnimationFrame(() => this.render());
  }
}

function updateComparisonLegend(paths = [], truthVisible = false) {
  const legend = $("comparison-legend");
  legend.replaceChildren();
  const comparing = paths.length > 0;
  for (const item of document.querySelectorAll(".base-legend")) item.hidden = comparing;
  const truth = document.querySelector(".base-legend-truth");
  if (comparing && truthVisible) truth.hidden = false;
  for (const path of paths) {
    const item = document.createElement("span");
    const marker = document.createElement("i");
    marker.style.background = path.color;
    item.append(marker, document.createTextNode(path.label));
    legend.appendChild(item);
  }
}

const histories = { cpu: [], memory: [], realtime: [], ate: [] };
let lastHistoryTime = -Infinity;

function appendHistory(timeValue, metrics) {
  if (timeValue < lastHistoryTime - 1) {
    Object.values(histories).forEach((values) => values.splice(0));
    lastHistoryTime = -Infinity;
  }
  if (timeValue - lastHistoryTime < 0.15) return;
  lastHistoryTime = timeValue;
  histories.cpu.push([timeValue, metrics.cpu_percent_one_core]);
  histories.memory.push([timeValue, metrics.memory_rss_mib]);
  histories.realtime.push([timeValue, metrics.realtime_factor]);
  if (metrics.ate_rmse_m != null) histories.ate.push([timeValue, metrics.ate_rmse_m]);
  for (const values of Object.values(histories)) {
    while (values.length && timeValue - values[0][0] > 120) values.shift();
  }
}

function drawChartSeries(canvas, series, minimumCeiling, unit, digits) {
  const rect = canvas.getBoundingClientRect();
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
  const context = canvas.getContext("2d");
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  const width = rect.width;
  const height = rect.height;
  context.clearRect(0, 0, width, height);
  const margin = { left: 42, right: 8, top: 8, bottom: 18 };
  const plotWidth = Math.max(1, width - margin.left - margin.right);
  const plotHeight = Math.max(1, height - margin.top - margin.bottom);
  const allValues = series.flatMap((value) => value.values || []);
  const currentTime = allValues.length ? Math.max(...allValues.map((value) => value[0])) : 120;
  const startTime = offlineReplayActive && allValues.length ? Math.min(...allValues.map((value) => value[0])) : Math.max(0, currentTime - 120);
  const observedMaximum = allValues.length ? Math.max(...allValues.map((value) => value[1])) : 0;
  const maximum = Math.max(minimumCeiling, observedMaximum * 1.12, 0.001);

  context.font = "11px Segoe UI, sans-serif";
  context.lineWidth = 1;
  context.strokeStyle = colors.grid;
  context.fillStyle = colors.muted;
  for (let index = 0; index <= 3; index += 1) {
    const y = margin.top + (plotHeight * index) / 3;
    context.beginPath();
    context.moveTo(margin.left, y);
    context.lineTo(width - margin.right, y);
    context.stroke();
    const value = maximum * (1 - index / 3);
    context.textAlign = "right";
    context.textBaseline = "middle";
    context.fillText(`${numberFormat(value, digits)}${unit}`, margin.left - 6, y);
  }
  context.textBaseline = "bottom";
  context.textAlign = "left";
  context.fillText(offlineReplayActive ? `${numberFormat(startTime, 0)} s` : "−120 s", margin.left, height);
  context.textAlign = "right";
  context.fillText(offlineReplayActive ? `${numberFormat(currentTime, 0)} s` : "maintenant", width - margin.right, height);

  for (const data of series) {
    if ((data.values || []).length < 2) continue;
    context.strokeStyle = data.color;
    context.lineWidth = 2;
    context.beginPath();
    let started = false;
    for (const [timestamp, value] of data.values) {
      if (timestamp < startTime) continue;
      const x = margin.left + ((timestamp - startTime) / Math.max(currentTime - startTime, 1)) * plotWidth;
      const y = margin.top + (1 - Math.max(0, value) / maximum) * plotHeight;
      if (!started) { context.moveTo(x, y); started = true; } else context.lineTo(x, y);
    }
    context.stroke();
  }
}

function drawChart(canvas, values, color, minimumCeiling, unit, digits) {
  drawChartSeries(canvas, [{ values, color }], minimumCeiling, unit, digits);
}

let renderer;
try {
  renderer = new SceneRenderer($("scene"));
} catch (error) {
  $("scene-detail").textContent = error.message;
  $("connection").dataset.state = "error";
}

$("fit-view").addEventListener("click", () => renderer?.fitView());
$("toggle-cloud").addEventListener("click", (event) => {
  if (!renderer) return;
  renderer.cloudVisible = !renderer.cloudVisible;
  event.currentTarget.setAttribute("aria-pressed", String(renderer.cloudVisible));
  event.currentTarget.textContent = renderer.cloudVisible ? "Nuage visible" : "Nuage masqué";
});

let lastCloudSequence = -1;
let reconnectTimer;

function updatePx4Panel(px4) {
  const connected = Boolean(px4?.connected);
  const state = px4?.state || {};
  const vehicle = state.vehicle || {};
  const battery = state.battery || {};
  const position = px4?.pose?.position;
  const link = $("px4-link");
  link.dataset.state = connected ? "connected" : "waiting";
  link.textContent = connected
    ? `Connecté · ${numberFormat(px4.age_s, 2)} s`
    : "En attente du pont ROS 2";
  $("px4-mode").textContent = vehicle.nav_state_name || "—";
  $("px4-arming").textContent = vehicle.armed ? "Armé" : "Désarmé";
  $("px4-battery").textContent = Number.isFinite(battery.remaining)
    ? `${numberFormat(100 * battery.remaining, 1)} %`
    : "—";
  $("px4-battery-detail").textContent = Number.isFinite(battery.voltage_v)
    ? `${numberFormat(battery.voltage_v, 2)} V`
    : "Tension indisponible";
  $("px4-position").textContent = Array.isArray(position)
    ? `${numberFormat(position[0], 2)} · ${numberFormat(position[1], 2)} · ${numberFormat(position[2], 2)} m`
    : "—";
  const safety = $("px4-safety");
  if (!connected) {
    safety.textContent = "État indisponible";
    safety.dataset.state = "waiting";
  } else if (vehicle.failsafe) {
    safety.textContent = "Failsafe actif";
    safety.dataset.state = "error";
  } else if (vehicle.preflight_checks_pass) {
    safety.textContent = "Prévol validé";
    safety.dataset.state = "connected";
  } else {
    safety.textContent = "Prévol en attente";
    safety.dataset.state = "warning";
  }
  $("px4-gcs").textContent = vehicle.gcs_connection_lost === false
    ? "QGroundControl connecté"
    : "QGroundControl absent";
}

function updateDashboard(payload) {
  if (offlineReplayActive) {
    updatePx4Panel(payload.px4);
    updateRunPanel(payload.run);
    return;
  }
  const metrics = payload.metrics;
  $("metric-progress").textContent = `${numberFormat(metrics.progress_percent, 1)} %`;
  $("metric-elapsed").textContent = `${numberFormat(metrics.data_elapsed_s, 1)} s de données`;
  $("metric-realtime").textContent = `${numberFormat(metrics.realtime_factor, 3)}×`;
  $("metric-cpu").textContent = `${numberFormat(metrics.cpu_percent_one_core, 1)} %`;
  $("metric-cpu-total").textContent = `${numberFormat(metrics.cpu_total_seconds, 1)} s cumulées`;
  $("metric-memory").textContent = `${numberFormat(metrics.memory_rss_mib, 1)} Mio`;
  $("metric-ate").textContent = metrics.ate_rmse_m == null ? "—" : `${numberFormat(metrics.ate_rmse_m, 3)} m`;
  $("metric-ratio").textContent = `${numberFormat(metrics.output_ratio_percent, 1)} %`;
  $("metric-counts").textContent = `${metrics.odometry_count} / ${metrics.reference_count} poses`;
  const pipeline = metrics.pipeline_counters || {};
  $("metric-pipeline").textContent = Number.isFinite(pipeline.scans_received)
    ? `${pipeline.scans_synchronized || 0} synchronisés / ${pipeline.scans_received} reçus · ${pipeline.odometry_published || 0} odométries`
    : "Instrumentation en attente";
  $("chart-cpu-value").textContent = `${numberFormat(metrics.cpu_percent_one_core, 1)} %`;
  $("chart-memory-value").textContent = `${numberFormat(metrics.memory_rss_mib, 1)} Mio`;
  $("chart-realtime-value").textContent = `${numberFormat(metrics.realtime_factor, 3)}×`;
  $("chart-ate-value").textContent = metrics.ate_rmse_m == null ? "—" : `${numberFormat(metrics.ate_rmse_m, 3)} m`;
  const algorithmLabel = payload.run?.algorithm_label || selectedAlgorithm()?.label || "LIO";
  const px4Detail = payload.px4?.connected
    ? ` · PX4 ${payload.px4.state?.vehicle?.nav_state_name || "connecté"}`
    : "";
  $("scene-detail").textContent = `${payload.scene.cloud.length / 4} points affichés · ${metrics.odometry_count} poses ${algorithmLabel} · ${metrics.reference_count} poses de référence${px4Detail}`;

  appendHistory(metrics.wall_elapsed_s, metrics);
  const cloudChanged = payload.scene.cloud_sequence !== lastCloudSequence;
  lastCloudSequence = payload.scene.cloud_sequence;
  renderer?.setData(payload.scene, cloudChanged);
  updatePx4Panel(payload.px4);
  updateRunPanel(payload.run);
}

function renderCharts() {
  drawChart($("chart-cpu"), histories.cpu, colors.cyan, 100, "%", 0);
  drawChart($("chart-memory"), histories.memory, colors.blue, 256, "", 0);
  drawChart($("chart-realtime"), histories.realtime, colors.green, 1.2, "×", 1);
  if (comparisonCurves.length) {
    drawChartSeries($("chart-ate"), comparisonCurves, 0.1, "", 2);
  } else {
    drawChart($("chart-ate"), histories.ate, colors.orange, 0.1, "", 2);
  }
  requestAnimationFrame(renderCharts);
}
requestAnimationFrame(renderCharts);

$("run-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!event.currentTarget.reportValidity()) return;
  $("start-run").disabled = true;
  $("run-message").textContent = "Envoi de la demande…";
  try {
    const run = await apiRequest("/api/run/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        simulation_id: $("control-simulation").value,
        variant_id: $("control-algorithm").value,
        profile_id: $("profile-selector").hidden ? null : $("control-profile").value,
        inputs: simulationNeedsDataset() ? [{
          input_id: "dataset",
          kind: "dataset_sequence",
          reference: {
            dataset_id: $("control-dataset").value,
            sequence_id: $("control-sequence").value,
          },
        }] : [],
        parameters: collectParameters(),
      }),
    });
    updateRunPanel(run);
  } catch (error) {
    $("run-state").dataset.state = "failed";
    $("run-state-label").textContent = "Demande refusée";
    $("run-message").textContent = error.message;
    setControlsLocked(false);
  }
});

$("stop-run").addEventListener("click", async () => {
  $("stop-run").disabled = true;
  $("run-message").textContent = "Demande d'arrêt envoyée…";
  try {
    updateRunPanel(await apiRequest("/api/run/stop", { method: "POST" }));
  } catch (error) {
    $("run-message").textContent = error.message;
  }
});

$("toggle-final-metrics").addEventListener("click", (event) => {
  if (!finalMetrics) return;
  const panel = $("final-results");
  const show = panel.hidden;
  panel.hidden = !show;
  event.currentTarget.setAttribute("aria-expanded", String(show));
  event.currentTarget.textContent = show
    ? "Masquer les métriques finales"
    : "Afficher les métriques finales";
});

function connect() {
  clearTimeout(reconnectTimer);
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/ws`);
  socket.addEventListener("open", () => {
    $("connection").dataset.state = "connected";
    $("connection-text").textContent = "Serveur connecté · en attente de ROS 2";
  });
  socket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    updateDashboard(payload);
    $("connection-text").textContent = payload.metrics.reference_count > 0
      ? "Benchmark ROS 2 en direct"
      : payload.px4?.connected
        ? "PX4 SITL et ROS 2 connectés"
        : "Serveur connecté · en attente de ROS 2";
  });
  socket.addEventListener("close", () => {
    $("connection").dataset.state = "waiting";
    $("connection-text").textContent = "Reconnexion au serveur local…";
    reconnectTimer = setTimeout(connect, 1500);
  });
  socket.addEventListener("error", () => socket.close());
}

connect();
initializeComparison();
initializeControls().then(initializeHistory);
