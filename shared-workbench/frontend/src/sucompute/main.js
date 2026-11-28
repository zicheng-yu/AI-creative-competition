import '../style.css';
import './style.css';
import { mountChart } from '../charts.js';
import { benchmarkPanel } from '../components.js';
import { html } from '../format.js';
import {
  DAYS, SCENARIOS, STRATEGIES, STRATEGY_NAMES, TREND_KEYS, comparisonCsv, comparisonMarkdown,
  createApi, createReplayStore, dailyChart, decimal, flightsAt, hourLabel, ledgerCsv, postText, validateReplay,
} from './data.js';
import { createDeltaMap } from './map.js';
import { auditBody, auditShell, faultSummary, kpisInline, paragraphs, renderMetrics, renderRoutes, shell } from './view.js';

const root = document.querySelector('#app');
root.innerHTML = shell;
const $ = (id) => document.getElementById(id);
const store = createReplayStore(new URL('./sucompute-data/', location.href));
const api = createApi(import.meta.env.VITE_SUCOMPUTE_API_BASE || '/sucompute-api');
const themeStorage = 'workbench-theme';
const state = {
  topology: null, index: null, runs: null, mode: 'fixed', weights: {},
  scene: 'normal_weekday', strategy: 'SuCompute', node: 0, hour: 14,
  metric: 'utilization', faults: [], customFault: null, pendingFaultNode: null,
  animation: false, theme: localStorage.getItem(themeStorage) === 'dark' ? 'dark' : 'light',
  auditSource: 'sample', auditReceipts: [], focusTask: null,
};
let map, clock, disposeChart, chartKey, sceneSequence = 0, auditSequence = 0, busy = false, auditTrigger;

function status(text, type = '') {
  $('operation').textContent = text;
  $('operation').dataset.kind = type;
}

function modeName() {
  return state.mode === 'live' ? '即时仿真' : '固定仿真回放';
}

function maxHour() {
  return state.runs?.SuCompute.hourly.length - 1;
}

function getConfig() {
  return { seed: state.index.seed, scenario: state.scene, strategy: state.strategy, hours: 24, weights: state.weights };
}

function applyTheme() {
  document.documentElement.dataset.theme = state.theme;
  $('theme').textContent = state.theme === 'dark' ? '切换浅色' : '切换深色';
  $('theme').setAttribute('aria-pressed', String(state.theme === 'dark'));
}

function setPlaying(on) {
  state.animation = on;
  clearInterval(clock);
  clock = on ? setInterval(() => {
    state.hour = state.hour >= maxHour() ? 0 : state.hour + 1;
    renderFrame();
  }, 820) : undefined;
  $('play').setAttribute('aria-pressed', String(on));
  $('play').textContent = on ? 'Ⅱ 暂停' : '▶ 播放';
  if (state.runs) renderFrame();
}

function setBusy(active) {
  busy = active;
  $('simulate').disabled = active;
  $('open-inject').disabled = active;
  for (const button of $('command-form').querySelectorAll('button')) button.disabled = active;
  for (const button of root.querySelectorAll('[data-command]')) button.disabled = active;
}

function renderTrend() {
  const day = Math.floor(state.hour / 24);
  const key = `${state.scene}/${state.mode}/${day}/${state.metric}/${state.theme}`;
  if (chartKey === key) return;
  chartKey = key;
  disposeChart?.();
  const charts = TREND_KEYS.map((metric) => dailyChart(state.runs, day, metric));
  const selected = charts.find((chart) => chart.id === state.metric);
  $('delta-chart').innerHTML = benchmarkPanel(charts, selected, `${DAYS[day]} · ${modeName()}`);
  disposeChart = mountChart($('chart'), selected, state.theme === 'dark');
}

function renderFrame() {
  if (!state.runs) return;
  const replay = state.runs[state.strategy];
  const row = Object.fromEntries(Object.entries(replay.nodes).map(([key, rows]) => [key, rows[state.hour]]));
  const node = state.topology.nodes[state.node];
  const flights = flightsAt(replay, state.hour);
  const slots = 60 / state.topology.slot_minutes;
  const event = state.mode === 'fixed' && state.faults.find((fault) =>
    fault.strategy === state.strategy && fault.scenario === state.scene && fault.city === node.city
      && fault.slot < (state.hour + 1) * slots && fault.slot + fault.duration_slots > state.hour * slots);
  const liveFault = state.customFault?.strategy === state.strategy ? state.customFault.event : null;
  const visibleFault = event || (liveFault?.city === node.city ? liveFault : null);
  const customNode = liveFault && state.topology.nodes.find((item) => item.city === liveFault.city);

  $('hour').value = state.hour;
  $('hour').setAttribute('aria-valuetext', hourLabel(state.hour));
  $('day').value = Math.floor(state.hour / 24);
  $('map-clock').textContent = hourLabel(state.hour);
  $('node-select').value = node.id;
  $('node-heading').textContent = node.city;
  $('node-kind').textContent = node.external ? '省外协同枢纽' : '江苏地市节点';
  const values = [
    ['装机负载', decimal(row.utilization?.[node.id] * 100) + '%'],
    ['实时 PUE', row.pue?.[node.id] > 0 ? decimal(row.pue[node.id], 3) : '—'],
    ['绿电消纳', row.pue?.[node.id] > 0 ? decimal(row.green_share?.[node.id] * 100) + '%' : '—'],
    ['可用容量', decimal(row.health?.[node.id] * 100) + '%'],
  ];
  $('node-stats').innerHTML = values.map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`).join('');
  $('node-fault').innerHTML = visibleFault
    ? faultSummary(visibleFault, state.topology) : `<div class="node-capacity">${node.external ? '独立计量' : node.centres + ' 座算力中心'}<span>${decimal(node.peak_eflops)} EFlops 装机</span></div>`;
  const count = renderRoutes($('routes'), flights, state.topology, state.node, state.mode === 'live');
  $('route-count').textContent = `${count} 条汇总链路`;
  map.update({ nodes: row, selected: node.id, flights, alarm: state.pendingFaultNode ?? customNode?.id ?? (visibleFault ? node.id : null), playing: state.animation });
  renderTrend();
}

function renderRun() {
  $('source-label').textContent = modeName();
  $('source-label').classList.toggle('live', state.mode === 'live');
  $('hour').max = maxHour();
  state.hour = Math.min(state.hour, maxHour());
  for (const option of $('day').options) option.disabled = Number(option.value) * 24 > maxHour();
  for (const button of root.querySelectorAll('[data-scene]')) button.setAttribute('aria-pressed', String(button.dataset.scene === state.scene));
  $('strategy').value = state.strategy;
  $('fixed-replay').hidden = state.mode !== 'live' && !state.customFault;
  $('metric-scope').textContent = `${modeName()} · ${maxHour() + 1} 小时`;
  $('compare-scope').textContent = `${SCENARIOS[state.scene]} · 种子 ${state.index.seed}`;
  renderMetrics($('kpis'), $('comparison'), state.runs, state.strategy);
  chartKey = null;
  renderFrame();
}

async function changeScene(scene, reset = false) {
  const turn = ++sceneSequence;
  setPlaying(false);
  status('正在载入固定仿真回放…');
  try {
    const runs = await store.scene(state.index, scene);
    if (turn !== sceneSequence) return false;
    Object.assign(state, { scene, runs, mode: 'fixed', weights: {}, customFault: null, pendingFaultNode: null, auditSource: 'sample', focusTask: null });
    if (reset) state.hour = 14;
    $('command-result').replaceChildren();
    renderRun();
    status('');
    return true;
  } catch (error) {
    if (turn === sceneSequence) status(error.message, 'error');
    return false;
  }
}

async function fetchRuns(config, weights) {
  return Object.fromEntries(await Promise.all(STRATEGIES.map(async (strategy) => [
    strategy, validateReplay(await api('simulate', { ...config, strategy, weights })),
  ])));
}

function applyLive(runs, weights) {
  Object.assign(state, { runs, weights, mode: 'live', customFault: null, auditSource: 'api' });
  state.hour %= 24;
  renderRun();
}

async function liveSimulation() {
  if (busy) return;
  setBusy(true);
  setPlaying(false);
  const turn = sceneSequence;
  const config = getConfig();
  status('正在重算同场景的四种策略…');
  try {
    await api('health');
    if (turn !== sceneSequence) return;
    const runs = await fetchRuns(config, config.weights);
    if (turn !== sceneSequence) return;
    applyLive(runs, config.weights);
    $('command-result').replaceChildren();
    status('四种策略已按同一输入即时运行，可查看 24 小时曲线并导出。', 'ok');
  } catch (error) {
    if (turn === sceneSequence) status(error.message, 'error');
  } finally {
    setBusy(false);
  }
}

async function jumpToFault() {
  const turn = sceneSequence;
  try {
    const fetched = await store.faults();
    if (turn !== sceneSequence) return;
    state.faults = fetched;
    const selected = fetched.find((item) => item.scenario === 'fault_stress' && item.strategy === state.strategy && item.city === state.topology.nodes[state.node].city)
      ?? fetched.find((item) => item.scenario === 'fault_stress' && item.strategy === state.strategy);
    if (!selected) throw new Error('此策略没有预置故障记录。');
    if (!await changeScene('fault_stress')) return;
    state.node = state.topology.nodes.find((node) => node.city === selected.city).id;
    state.hour = Math.floor(selected.slot * state.topology.slot_minutes / 60);
    renderFrame();
    status(`已定位 ${selected.city}的固定故障回放。可查看实际仿真处置和调度飞线。`, 'ok');
  } catch (error) {
    status(error.message, 'error');
  }
}

function showAudit(ids, current, body) {
  const dialog = $('audit-dialog');
  dialog.innerHTML = auditShell(ids, current, body);
  if (dialog.dataset.focus === 'picker') $('audit-task')?.focus();
  else dialog.querySelector('[data-close="audit"]')?.focus();
}

async function openAudit(requestedId, trigger) {
  const turn = ++auditSequence;
  const dialog = $('audit-dialog');
  const context = { scene: state.scene, strategy: state.strategy, seed: state.index.seed };
  if (!dialog.open) {
    auditTrigger = trigger;
    dialog.innerHTML = auditShell([], null, '<p class="receipt-message">正在加载任务凭证…</p>');
    dialog.showModal();
  }
  const wanted = requestedId ?? state.focusTask;
  if (state.auditSource === 'api' || state.mode === 'live') {
    try {
      const payload = { ...getConfig(), limit: 1 };
      if (wanted != null) payload.task_id = wanted;
      const data = await api('ledger', payload);
      if (turn !== auditSequence || !dialog.open) return;
      state.auditReceipts = data.receipts;
      const ids = data.index.map((item) => item.task_id);
      const entry = data.receipts[0];
      showAudit(ids, entry?.task_id ?? null, entry ? auditBody(entry, state.topology) :
        '<p class="receipt-message">这个窗口没有可展示的任务凭证。</p>');
    } catch (error) {
      if (turn === auditSequence && dialog.open) showAudit([], null, `<p class="receipt-message">${html(error.message)}</p>`);
    }
    return;
  }
  try {
    const records = (await store.receipts()).filter((item) =>
      item.scenario === context.scene && item.strategy === context.strategy && item.seed === context.seed);
    if (turn !== auditSequence || !dialog.open) return;
    state.auditReceipts = records;
    const samples = records.map((item) => item.task_id);
    const entry = wanted == null ? records[0] : records.find((item) => item.task_id === wanted);
    showAudit(samples, entry?.task_id ?? null, entry ? auditBody(entry, state.topology) :
      '<p class="receipt-message">该飞线是汇总调度段，固定样例未收录对应凭证。可从上方选择一个有凭证的任务，或加载本窗口完整账本。</p>');
    if (!entry && samples.length) $('audit-task').selectedIndex = -1;
  } catch (error) {
    if (turn === auditSequence && dialog.open) showAudit([], null, `<p class="receipt-message">${html(error.message)}</p>`);
  }
}

function setFault(event, metrics, strategy, narrative = '') {
  state.customFault = { event, strategy };
  state.auditSource = 'api';
  state.node = state.topology.nodes.find((node) => node.city === event.city)?.id ?? state.node;
  $('fixed-replay').hidden = false;
  $('command-result').innerHTML = `${paragraphs(narrative)}<h3>故障注入结果 · ${html(STRATEGY_NAMES[strategy])}</h3><p>独立 24 小时仿真指标，地图标记指向注入节点。</p>${faultSummary(event, state.topology)}${kpisInline(metrics)}`;
  renderFrame();
}

async function sendCommand(input) {
  const command = input.trim();
  if (!command || busy) return;
  const turn = sceneSequence;
  const config = getConfig();
  setBusy(true);
  setPlaying(false);
  $('command-result').textContent = '正在执行指令…';
  try {
    const { action, result, narrative } = await api('copilot/command', { ...config, text: command });
    if (turn !== sceneSequence) return;
    if (action.kind === 'weights') {
      const scenario = action.scenario || config.scenario;
      const weights = { ...config.weights, ...action.weights };
      $('command-result').innerHTML = `<h3>已解析指令，正在重算四种策略…</h3>${paragraphs(narrative)}`;
      const runs = await fetchRuns({ ...config, scenario }, weights);
      if (turn !== sceneSequence) return;
      state.scene = scenario;
      applyLive(runs, weights);
      $('command-result').innerHTML = `<h3>权重已应用</h3>${paragraphs(narrative)}<p>已刷新四策略指标与 24 小时曲线。</p>`;
    } else if (action.kind === 'fault') {
      setFault(result.fault, result.kpis, config.strategy, narrative);
    } else {
      const receipt = result.evidence?.receipt ? {
        ...result.evidence.receipt,
        selection_reason: result.evidence.selection_reason,
        cross_region: result.evidence.cross_region,
      } : null;
      state.previewReceipt = receipt;
      state.focusTask = receipt?.task_id ?? null;
      state.auditSource = 'api';
      $('command-result').innerHTML = `<h3>调度归因</h3>${paragraphs(result.summary)}${result.global_summary ? `<h3>全局</h3>${paragraphs(result.global_summary)}` : ''}${receipt ? '<button type="button" class="s-button outline" data-preview-audit="task">在审计抽屉中查看该任务</button>' : ''}`;
    }
  } catch (error) {
    if (turn === sceneSequence) $('command-result').textContent = error.message;
  } finally {
    setBusy(false);
  }
}

function syncFaultType() {
  const choice = $('fault-kind').value;
  const severity = $('fault-severity');
  severity.disabled = choice === 'outage';
  severity.value = choice === 'outage' ? '1' : '0.3';
  severity.max = choice === 'pue' ? '3' : '1';
  $('fault-unit').textContent = choice === 'pue' ? 'PUE 增量，0–3' : choice === 'outage' ? '全部容量离线' : '容量损失比例，0–1';
}

async function injectFault(event) {
  event.preventDefault();
  if (busy) return;
  const config = getConfig();
  const turn = sceneSequence;
  const node = state.topology.nodes[Number($('fault-node').value)];
  const kind = $('fault-kind').value;
  const slot = (state.hour % 24) * 60 / state.topology.slot_minutes;
  setBusy(true);
  setPlaying(false);
  $('fault-form').querySelector('button[type="submit"]').disabled = true;
  state.pendingFaultNode = node.id;
  renderFrame();
  $('fault-status').textContent = '正在执行独立的 24 小时故障仿真…';
  try {
    const result = await api('fault/inject', {
      ...config, slot, fault: {
        city: node.city, kind, severity: kind === 'outage' ? 1 : Number($('fault-severity').value),
        duration_slots: Number($('fault-duration').value) / state.topology.slot_minutes,
      },
    });
    if (turn !== sceneSequence) return;
    setFault(result.fault, result.kpis, config.strategy);
    $('fault-dialog').close();
    status('故障仿真已生成，已标记注入节点。', 'ok');
  } catch (error) {
    if (turn === sceneSequence) $('fault-status').textContent = error.message;
  } finally {
    setBusy(false);
    $('fault-form').querySelector('button[type="submit"]').disabled = false;
    state.pendingFaultNode = null;
    renderFrame();
  }
}

function download(body, filename, contentType) {
  const url = URL.createObjectURL(new Blob([body], {type: contentType}));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

$('theme').addEventListener('click', () => {
  state.theme = state.theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem(themeStorage, state.theme);
  applyTheme();
  if (state.runs) renderFrame();
});
$('strategy').addEventListener('change', (event) => { state.strategy = event.target.value; renderRun(); });
$('node-select').addEventListener('change', (event) => { state.node = Number(event.target.value); renderFrame(); });
$('hour').addEventListener('input', (event) => { state.hour = Number(event.target.value); setPlaying(false); });
$('day').addEventListener('change', (event) => {
  state.hour = Math.min(Number(event.target.value) * 24 + state.hour % 24, maxHour());
  setPlaying(false);
});
$('play').addEventListener('click', () => setPlaying(!state.animation));
$('simulate').addEventListener('click', liveSimulation);
$('jump-fault').addEventListener('click', jumpToFault);
$('fixed-replay').addEventListener('click', () => { void changeScene(state.scene); });
$('open-audit').addEventListener('click', (event) => { void openAudit(null, event.currentTarget); });
$('audit-dialog').addEventListener('close', () => {
  auditSequence++;
  delete $('audit-dialog').dataset.focus;
  auditTrigger?.focus();
});
$('audit-dialog').addEventListener('change', (event) => {
  if (event.target.id === 'audit-task') {
    $('audit-dialog').dataset.focus = 'picker';
    void openAudit(Number(event.target.value));
  }
});
$('open-inject').addEventListener('click', () => {
  $('fault-node').value = state.node;
  $('fault-status').textContent = '按 24 小时独立重算，故障时点沿用当前选中的小时。';
  $('fault-dialog').showModal();
});
$('fault-kind').addEventListener('change', syncFaultType);
$('fault-form').addEventListener('submit', injectFault);
$('command-form').addEventListener('submit', (event) => { event.preventDefault(); void sendCommand($('command').value); });
$('export-csv').addEventListener('click', () => {
  if (state.runs) download(comparisonCsv(state.runs, state.scene, state.mode, state.index.seed, Math.floor(state.hour / 24)), `sucompute-${state.scene}.csv`, 'text/csv;charset=utf-8');
});
$('export-md').addEventListener('click', () => {
  if (state.runs) download(comparisonMarkdown(state.runs, state.scene, state.mode, state.index.seed, state.weights), `sucompute-${state.scene}.md`, 'text/markdown;charset=utf-8');
});

root.addEventListener('click', (event) => {
  const target = event.target.closest('button');
  if (!target) return;
  const { scene, chart, task, close, command, ledger, previewAudit } = target.dataset;
  if (scene && scene !== state.scene) void changeScene(scene, true);
  if (chart) {
    state.metric = chart;
    renderTrend();
    root.querySelector(`[data-chart="${chart}"]`)?.focus();
  }
  if (task != null) void openAudit(Number(task), target);
  if (close) $(`${close}-dialog`).close();
  if (command) {
    $('command').value = command;
    void sendCommand(command);
  }
  if (previewAudit && state.previewReceipt) {
    const dialog = $('audit-dialog');
    if (!dialog.open) dialog.showModal();
    state.auditReceipts = [state.previewReceipt];
    dialog.innerHTML = auditShell([state.previewReceipt.task_id], state.previewReceipt.task_id, auditBody(state.previewReceipt, state.topology));
  }
  if (ledger === 'csv') void exportLedger();
  if (ledger === 'api') {
    state.auditSource = 'api';
    $('audit-dialog').dataset.focus = 'picker';
    void openAudit(state.focusTask);
  }
});

async function exportLedger() {
  const filename = `sucompute-ledger-${state.scene}.csv`;
  if (state.auditSource === 'api' || state.mode === 'live') {
    try {
      const body = await postText(import.meta.env.VITE_SUCOMPUTE_API_BASE || '/sucompute-api', 'ledger/csv', getConfig());
      download(body, filename, 'text/csv;charset=utf-8');
    } catch (error) {
      status(error.message, 'error');
    }
    return;
  }
  if (state.auditReceipts.length) download(ledgerCsv(state.auditReceipts, state.topology), filename, 'text/csv;charset=utf-8');
}

async function boot() {
  applyTheme();
  $('export-csv').disabled = $('export-md').disabled = true;
  try {
    const { topology, index } = await store.boot();
    Object.assign(state, { topology, index });
    const nodes = topology.nodes.map((node) => `<option value="${node.id}">${html(node.city)}</option>`).join('');
    $('node-select').innerHTML = $('fault-node').innerHTML = nodes;
    map = createDeltaMap($('network-map'), $('node-targets'), topology, (id) => { state.node = id; renderFrame(); });
    state.runs = await store.scene(index, state.scene);
    $('dashboard').hidden = false;
    renderRun();
    $('boot').hidden = true;
    $('export-csv').disabled = $('export-md').disabled = false;
    void store.faults().then((events) => { state.faults = events; if (state.runs) renderFrame(); }).catch(() => {});
  } catch (error) {
    $('boot').innerHTML = `<p>${html(error.message)} 请在前端目录运行 <code>npm run sucompute:data</code> 后刷新页面。</p><button class="s-button outline" type="button" id="reload">刷新回放</button>`;
    $('reload').addEventListener('click', () => location.reload());
  }
}

void boot();
