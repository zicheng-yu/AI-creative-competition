import './style.css';
import { mountChart } from './charts.js';
import { benchmarkPanel, evidenceDetails, evidencePanel, findingsPanel, reportPanel } from './components.js';
import { html } from './format.js';
import { readCharts } from './import.js';

const root = document.querySelector('#app');
const state = {
  theme: localStorage.getItem('workbench-theme') === 'dark' ? 'dark' : 'light',
  mode: 'mock', id: null, list: [], workspace: null, selectedChart: null, filter: 'all',
  loading: false, error: '', importNote: '', imports: null,
};
let requested = 0;
let importRequested = 0;
let disposeChart;

async function request(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const detail = typeof data?.detail === 'string' ? data.detail : `接口返回 ${response.status}`;
    throw new Error(detail);
  }
  return response;
}

function remember() {
  document.documentElement.dataset.theme = state.theme;
  localStorage.setItem('workbench-theme', state.theme);
}

function focused() {
  const element = document.activeElement;
  if (!element || !root.contains(element)) return null;
  if (element.id) return `#${CSS.escape(element.id)}`;
  const key = ['theme', 'mode', 'chart', 'workspace', 'export', 'import'].find((name) => element.hasAttribute(`data-${name}`));
  if (!key) return null;
  return `[data-${key}="${CSS.escape(element.getAttribute(`data-${key}`))}"]`;
}

function render() {
  const focusTarget = focused();
  disposeChart?.();
  disposeChart = undefined;
  const data = state.workspace;
  const charts = state.imports || data?.charts || [];
  const current = charts.find((chart) => chart.id === state.selectedChart) ?? charts[0];
  root.innerHTML = `<div class="workbench">
    <aside class="rail">
      <div class="brand"><span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span><strong>赛道演示工作台</strong></div>
      <nav aria-label="赛道" class="workspace-nav">
        ${state.list.map((item) => `<button data-workspace="${html(item.id)}" aria-current="${item.id === state.id ? 'page' : 'false'}">
          <span>${html(item.title)}</span><small>${html(item.subtitle)}</small>
        </button>`).join('')}
      </nav>
      <button class="theme-button" data-theme aria-pressed="${state.theme === 'dark'}">${state.theme === 'dark' ? '☀ 切换浅色' : '◐ 切换深色'}</button>
    </aside>
    <main id="main" tabindex="-1">
      <header class="top"><div class="path"><span>工作台</span>${data ? `<span aria-hidden="true">/</span><span>${html(data.subtitle)}</span>` : ''}</div>
        <div class="segmented mode" aria-label="数据模式">
          <button data-mode="mock" aria-pressed="${state.mode === 'mock'}">样例</button>
          <button data-mode="real" aria-pressed="${state.mode === 'real'}">真实数据</button>
        </div>
      </header>
      ${state.loading ? '<p class="state-note" role="status">正在加载工作区…</p>' : ''}
      ${state.error ? `<div class="state-note error" role="alert"><p>${html(state.error)}</p><button class="quiet" data-retry>重新加载</button></div>` : ''}
      ${data ? `<section class="intro" aria-labelledby="workspace-title">
        <div><div class="version"><span class="mode-dot ${state.mode}"></span>${state.mode === 'mock' ? '样例数据' : '真实数据'} <span>·</span> ${html(data.version)}</div>
        <h1 id="workspace-title">${html(data.title)}</h1><p>${html(data.summary)}</p></div>
        <div class="import-control">
          ${data.id === "sucompute" ? '<a class="quiet workbench-link" href="./sucompute.html">打开算网沙盘</a>' : ""}
          ${data.id === "electrical" ? '<a class="quiet workbench-link" href="./electrical.html">打开审图工作台</a>' : ""}
          <button class="quiet" data-import>导入评测数据</button><input type="file" id="import-file" aria-label="导入评测数据" accept=".json,.csv,application/json,text/csv" hidden>
        </div>
      </section>
      ${state.importNote ? `<div class="import-note" role="status"><p>${html(state.importNote)}</p>
        ${state.imports ? '<button class="text-button" data-restore>恢复工作区数据</button>' : ''}</div>` : ''}
      <div class="work-area">
        <div class="evaluation">${benchmarkPanel(charts, current)}${evidencePanel(data.sources)}</div>
        <div class="review">${findingsPanel(data.findings, state.filter)}${reportPanel()}</div>
      </div>` : ''}
    </main>
    <dialog id="drawer" aria-labelledby="source-title"></dialog>
  </div>`;
  if (current) {
    disposeChart = mountChart(document.querySelector('#chart'), current, state.theme === 'dark');
  }
  if (focusTarget) root.querySelector(focusTarget)?.focus({ preventScroll: true });
}

async function load(mode, id) {
  const call = ++requested;
  Object.assign(state, { mode, id, workspace: null, imports: null, filter: 'all', importNote: '', error: '', loading: true });
  render();
  try {
    const query = new URLSearchParams({ mode });
    const index = await (await request(`/api/v1/workspaces?${query}`)).json();
    if (call !== requested) return;
    state.list = index.workspaces;
    state.id = index.workspaces.find((item) => item.id === id)?.id ?? index.workspaces[0]?.id ?? null;
    if (!state.id) throw new Error('真实数据目录没有可用工作区。');
    const data = await (await request(`/api/v1/workspaces/${encodeURIComponent(state.id)}?${query}`)).json();
    if (call !== requested) return;
    Object.assign(state, { workspace: data, selectedChart: data.charts[0]?.id });
  } catch (error) {
    if (call !== requested) return;
    Object.assign(state, { error: error.message, list: [] });
  }
  if (call === requested) {
    state.loading = false;
    render();
  }
}

function openSource(id, trigger) {
  const item = state.workspace.sources.find((source) => source.source_id === id);
  if (!item) return;
  const drawer = document.querySelector('#drawer');
  drawer.innerHTML = evidenceDetails(item);
  drawer.showModal();
  drawer.addEventListener('close', () => trigger.focus({ preventScroll: true }), { once: true });
}

async function exportReport(format, button) {
  const workspace = state.workspace;
  const payload = { ...workspace, charts: state.imports || workspace.charts };
  const notice = document.querySelector('#export-status');
  button.disabled = true;
  notice.textContent = '正在生成报告…';
  try {
    const blob = await (await request(`/api/v1/reports/${format}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    })).blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${workspace.id}-report.${format}`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    notice.textContent = '报告已生成。';
  } catch (error) {
    notice.textContent = `导出失败。 ${error.message}`;
  } finally {
    button.disabled = false;
  }
}

root.addEventListener('click', (event) => {
  const button = event.target.closest('button');
  if (!button) return;
  const action = button.dataset;
  if ('theme' in action) {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    remember();
    render();
  } else if (action.workspace && action.workspace !== state.id) {
    void load(state.mode, action.workspace);
  } else if (action.mode && action.mode !== state.mode) {
    state.list = [];
    void load(action.mode, state.id);
  } else if ('retry' in action) {
    void load(state.mode, state.id);
  } else if (action.chart) {
    state.selectedChart = action.chart;
    render();
  } else if (action.source) {
    openSource(action.source, button);
  } else if ('close' in action) {
    document.querySelector('#drawer').close();
  } else if ('highlight' in action) {
    const mark = document.querySelector('#highlight');
    mark.scrollIntoView({ block: 'center' });
    mark.focus({ preventScroll: true });
  } else if ('import' in action) {
    document.querySelector('#import-file').click();
  } else if ('restore' in action) {
    Object.assign(state, { imports: null, importNote: '', selectedChart: state.workspace.charts[0]?.id });
    render();
    document.querySelector('[data-import]').focus();
  } else if (action.export) {
    void exportReport(action.export, button);
  }
});

root.addEventListener('change', async (event) => {
  const target = event.target;
  if (target.id === 'severity') {
    state.filter = target.value;
    render();
  } else if (target.id === 'import-file' && target.files[0]) {
    const selection = ++importRequested;
    const file = target.files[0];
    const workspace = state.workspace;
    try {
      if (file.size > 2_000_000) throw new Error('请选择小于 2 MB 的文件。');
      const charts = await readCharts(file);
      if (state.workspace !== workspace || selection !== importRequested) return;
      Object.assign(state, { imports: charts, selectedChart: charts[0].id, importNote: `已载入 ${file.name}` });
    } catch (error) {
      if (state.workspace !== workspace || selection !== importRequested) return;
      state.importNote = error.message;
    }
    render();
    document.querySelector('[data-import]').focus();
  }
});

remember();
void load('mock', null);
