import '../style.css';
import './style.css';
import { mountChart } from '../charts.js';
import { benchmarkPanel, evidenceDetails } from '../components.js';
import { readCharts } from '../import.js';
import { html } from '../format.js';
import { csv, download, xlsx } from './export.js';
import { renderGraph } from './graph.js';
import { bomRows, connected, decodeCommand, diffInstances, editBom } from './model.js';
import { renderBom, renderChecks, renderDrawing, shell } from './view.js';

const root = document.querySelector('#app');
root.innerHTML = shell;
const $ = (id) => document.getElementById(id);
const publicRoot = new URL('./electrical/', location.href);
const apiBase = (import.meta.env.VITE_ELECTRICAL_API || '/electrical-api').replace(/\/$/, '');
const cases = new Map();
const state = {
  docs: new Map(), work: null, selected: null, found: null, located: new Set(), zoom: 1,
  theme: localStorage.getItem('workbench-theme') === 'dark' ? 'dark' : 'light',
  view: 'review', clauses: {}, charts: null, chartId: null, chartDispose: null, activeSpeech: null,
};
let sequence = 0, operation = false, previewFinding, dialogTrigger;

async function asset(name, type = 'json') {
  const response = await fetch(new URL(name, publicRoot));
  if (!response.ok) throw new Error('无法读取内置审图样例。');
  return response[type]();
}

async function api(endpoint, data, params = '') {
  const isFile = data instanceof File;
  let response;
  try {
    response = await fetch(`${apiBase}/api/v1/electrical/${endpoint}${params}`, {
      method: 'POST', headers: {'Content-Type': isFile ? 'application/octet-stream' : 'application/json'},
      body: isFile ? data : JSON.stringify(data), signal: AbortSignal.timeout(90_000),
    });
  } catch (error) {
    if (error instanceof TypeError) throw new Error('未连接本地审图服务。可以先使用内置样例。');
    throw error;
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload) throw new Error(typeof payload?.detail === 'string' ? payload.detail : '本地审图服务未返回有效数据。');
  return payload;
}

function notice(message = '', kind = '') {
  $('notice').textContent = message;
  $('notice').dataset.kind = kind;
}

function board() { return state.work?.page; }

function applyTheme() {
  document.documentElement.dataset.theme = state.theme;
  $('theme').textContent = state.theme === 'dark' ? '切换浅色' : '切换深色';
}

function activate(page) {
  state.work = state.docs.get(page.id) ?? { page, log: [], history: [], dirty: false, revision: 0 };
  state.docs.set(page.id, state.work);
  state.selected = state.work.page.annotation.instances.find((item) => item.tag === 'QF1')?.id
    ?? state.work.page.annotation.instances[0]?.id ?? null;
  state.found = null;
  state.located = new Set();
  state.zoom = 1;
  $('bom-filter').value = '';
  $('severity').value = 'all';
  $('command-result').textContent = '';
  render();
}

async function loadSample(id) {
  const turn = ++sequence;
  notice('载入样例…');
  try {
    if (state.docs.has(id)) {
      activate(state.docs.get(id).page);
    } else {
      const page = await asset(cases.get(id).filename);
      if (sequence !== turn) return;
      page.preview = new URL(page.preview, publicRoot).href;
      activate(page);
    }
    notice('');
  } catch (error) {
    if (turn === sequence) notice(error.message, 'error');
  }
}

async function loadUpload(file) {
  if (!/\.(dxf|pdf|png)$/i.test(file.name) || file.size > 10 * 1024 * 1024) {
    notice('支持 10 MB 以内的 DXF、单页 PDF 和 PNG。', 'error');
    return;
  }
  const turn = ++sequence;
  notice(`正在解析 ${file.name} 的器件、拓扑和规则检查…`);
  try {
    const parameters = new URLSearchParams({filename: file.name});
    const page = await api('parse', file, '?' + parameters);
    if (sequence !== turn) return;
    activate({ ...page, id: 'upload-' + turn });
    $('fixture').value = '';
    notice(`解析完成，推理耗时 ${page.elapsed_s.toFixed(2)} 秒。`, 'success');
  } catch (error) {
    if (sequence === turn) notice(error.message, 'error');
  }
}

function select(id, scroll = false, keepFinding = false) {
  if (!board()?.annotation.instances.some((item) => item.id === id)) return;
  const focused = document.activeElement;
  const focusData = focused?.hasAttribute('data-graph') ? 'data-graph' : focused?.classList.contains('symbol-box') ? 'data-symbol' : null;
  state.selected = id;
  if (!keepFinding) { state.located = new Set(); state.found = null; }
  render();
  if (focusData) root.querySelector(`[${focusData}="${CSS.escape(id)}"]`)?.focus({preventScroll: true});
  if (scroll) root.querySelector(`[data-symbol="${CSS.escape(id)}"].symbol-box`)?.scrollIntoView({block:'nearest',inline:'nearest'});
}

function applyPage(page, reason, changes, dirty, preserveBom = false) {
  const current = state.work;
  current.history.push({page: current.page, dirty: current.dirty});
  current.page = page;
  current.revision++;
  current.dirty = dirty;
  current.log.unshift({ reason, changes, timestamp: new Date() });
  state.located = new Set();
  state.found = null;
  render(preserveBom);
}

function renderTopology() {
  const model = board();
  if (!model || state.view !== 'review') return;
  const connections = connected(model.annotation, state.selected);
  renderGraph($('graph'), model.annotation, state.selected, connections);
  const device = model.annotation.instances.find((item) => item.id === state.selected);
  const count = model.annotation.netlist?.edges?.length ?? 0;
  $('graph-count').textContent = `${count} 条连线`;
  $('device-detail').innerHTML = device ? `<div><strong>${html(device.tag || device.class_code)}</strong><span>${html(device.specs?.model || device.class_code)} · ${html(device.specs?.spec || '规格待核对')}</span></div><small>上游 ${connections.upstream.length} · 下游 ${connections.downstream.length}${device.layout_pending ? ' · 待布点' : ''}</small>` : '<p class="small-empty">选择图纸里的一个器件。</p>';
}

function render(preserveBom = false) {
  const model = board();
  if (!model) return;
  const input = state.work;
  $('sheet-heading').textContent = model.title;
  $('source-mode').textContent = model.kind === 'fixture' ? '固定样例 · ElectroBench-JS' : '本地解析结果';
  $('drawing-stage').innerHTML = renderDrawing(model, state.selected, state.located);
  $('drawing-stage').style.setProperty('--zoom', state.zoom);
  $('drawing-stage').style.setProperty('--image-ratio', model.width / model.height);
  $('zoom-value').textContent = Math.round(state.zoom * 100) + '%';
  const confidence = model.confidence?.[state.selected];
  $('drawing-footer').textContent = `${model.annotation.instances.length} 个器件${model.kind === 'fixture' ? ' · 样例标注层' : confidence == null ? ' · 解析标注层' : ' · 当前器件置信度 ' + Math.round(confidence * 100) + '%'}`;
  const scroll = $('drawing-scroll');
  scroll.setAttribute('aria-label', model.title + '图纸');
  renderTopology();
  if (preserveBom !== true) renderBomTable();
  $('drawing-stage').classList.toggle('finding-location', state.found !== null);
  $('bom-count').textContent = bomRows(model.annotation).length + ' 项';
  const counts = model.checks?.counts ?? {};
  $('check-meta').textContent = input.dirty ? '工作副本已更改，待重新体检。' : `${counts.error ?? 0} 严重 / ${counts.warning ?? 0} 警告 / ${counts.pass ?? 0} 通过`;
  $('checks').innerHTML = renderChecks(model.checks, $('severity').value, state.found);
  $('undo').disabled = !input.history.length;
  $('log').innerHTML = input.log.length ? input.log.map((entry) => `<div class="log-line"><span>${html(entry.timestamp.toLocaleTimeString('zh-CN'))}</span><div><strong>${html(entry.reason)}</strong><p>${entry.changes.map((change) => `${html(change.tag || change.id)} ${html(change.field)}：${html(change.before || '空')} → ${html(change.after || '空')}`).join('；')}</p></div></div>`).join('') : '<p class="small-empty">本工作副本暂无更改。</p>';
}

function renderBomTable() {
  if (board()) $('bom').innerHTML = renderBom(board().annotation, $('bom-filter').value, state.selected);
}

function findingAt(position) { return board()?.checks?.findings?.[position]; }

function locateFinding(position) {
  const item = findingAt(position);
  if (!item) return;
  state.found = position;
  state.located = new Set(item.instance_ids);
  const id = item.locations?.find((location) => location.bbox_px)?.instance_id ?? item.instance_ids[0];
  select(id, true, true);
}

function openClause(key, trigger) {
  const doc = board()?.clauses?.[key] ?? state.clauses[key];
  if (!doc) { notice('当前资料未附这条标准的来源。', 'error'); return; }
  dialogTrigger = trigger;
  $('evidence-dialog').innerHTML = evidenceDetails({
    title: doc.title, source_id: key, version: doc.standard_code, confidence: null,
    source_text: [doc.summary, doc.excerpt, doc.remediation_guide].filter(Boolean).join('\n\n'),
    raw_snippet: doc.excerpt || doc.summary, source_url: doc.source_url?.startsWith('https://') ? doc.source_url : null,
  });
  $('evidence-dialog').showModal();
}

async function recalculate(repair) {
  if (!board() || operation) return;
  const current = state.work, version = current.revision;
  const input = current.page.annotation;
  operation = true;
  $('recheck').disabled = true;
  if (repair) $('apply-fix').disabled = true;
  try {
    const payload = {annotation: input};
    if (repair) payload.finding = {rule_id: previewFinding.rule_id, instance_ids: previewFinding.instance_ids};
    const result = await api(repair ? 'repair' : 'check', payload);
    if (state.work !== current || current.revision !== version) return;
    if (repair) {
      const changes = diffInstances(input, result.annotation);
      applyPage({ ...current.page, ...result }, '应用规则修订预览并复检', changes, false);
      $('fix-dialog').close();
      notice('已更新工作副本并重新体检。', 'success');
    } else {
      Object.assign(current, {page: { ...current.page, ...result }, dirty: false, revision: version + 1});
      render();
      notice('当前工作副本已重新体检。', 'success');
    }
  } catch (error) {
    if (repair && $('fix-dialog').open) $('fix-message').textContent = error.message;
    else notice(error.message, 'error');
  } finally {
    operation = false;
    $('recheck').disabled = false;
    if ($('apply-fix')) $('apply-fix').disabled = false;
  }
}

function openFix(position, trigger) {
  if (state.work.dirty) { notice('工作副本已修改，请先重新体检，再应用规则修订。', 'error'); return; }
  previewFinding = findingAt(position);
  if (!previewFinding?.fix_suggestion?.operations?.length) return;
  dialogTrigger = trigger;
  const suggestion = previewFinding.fix_suggestion;
  const items = new Map(board().annotation.instances.map((item) => [item.id, item]));
  $('fix-content').innerHTML = `<div class="card-head"><h2 id="fix-title">规则修订预览</h2><button class="soft-button" type="button" data-close="fix" aria-label="关闭修订">×</button></div><div class="fix-details"><p>${html(suggestion.action)}</p><ul>${suggestion.operations.map((op) => {
    const label = items.get(op.id || op.target)?.tag || '清单';
    const detail = op.values ? Object.entries(op.values).map(([key, val]) => key + '→' + val).join('；') : op.instance ? '串联器件 ' + op.instance.tag + '（待布点）' : '重建物料清单';
    return `<li>${html(label)} · ${html(detail)}</li>`;
  }).join('')}</ul><p>修订只写入当前审图副本。</p><p id="fix-message" role="status"></p><button id="apply-fix" class="primary-button" type="button">应用到工作副本并复检</button></div>`;
  $('fix-dialog').showModal();
}

function command() {
  const model = board();
  if (!model) return;
  const result = decodeCommand($('command').value, model.annotation);
  const out = $('command-result');
  if (result.kind === 'replace') {
    const ids = bomRows(model.annotation).filter((row) => row.model === result.from).map((row) => row.instance_id);
    const edited = editBom(model.annotation, ids, 'model', result.to);
    if (!edited.changes.length) { out.textContent = '当前 BOM 未找到匹配的旧型号。'; return; }
    applyPage({ ...model, annotation: edited.annotation }, 'Copilot 批量替换 BOM 型号', edited.changes, true);
    out.textContent = `已更新 ${edited.changes.length} 项物料。可在操作记录中查看或撤销。`;
  } else if (result.kind === 'circuit') {
    const item = result.targets[0];
    const graph = connected(model.annotation, item.id);
    const labels = new Map(model.annotation.instances.map((part) => [part.id, part.tag || part.class_code]));
    const nearby = (ids) => ids.slice(0, 6).map((id) => labels.get(id)).join('、') || '暂无记录';
    select(item.id, true);
    out.textContent = `${item.tag} · 上游 ${nearby(graph.upstream)}。下游 ${nearby(graph.downstream)}。`;
  } else if (result.kind === 'findings') {
    const ids = result.targets.map((item) => item.id);
    const index = model.checks?.findings.findIndex((finding) => finding.severity !== 'pass' && finding.rule_id.startsWith('selectivity_') && (!ids.length || ids.some((id) => finding.instance_ids.includes(id))));
    if (index >= 0) {
      $('severity').value = 'all';
      locateFinding(index);
      out.textContent = `${findingAt(index).message}。可打开合规体检中的对应条文和修订预览。`;
    } else out.textContent = '当前报告没有匹配的级差告警。';
  } else out.textContent = '可用指令包括「查 QF1 的回路」「查级差」及「把 OLD 替换为 NEW」。';
}

function voice() {
  if (state.activeSpeech) { state.activeSpeech.stop(); return; }
  const Constructor = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Constructor) { $('command-result').textContent = '当前浏览器没有语音识别能力。可以继续输入文字指令。'; return; }
  const recognition = new Constructor();
  recognition.lang = 'zh-CN';
  recognition.onstart = () => { $('voice').textContent = '结束语音'; $('voice').setAttribute('aria-pressed','true'); };
  recognition.onresult = (event) => { $('command').value = event.results[0][0].transcript; $('command-result').textContent = '已转写，请确认后执行指令。'; };
  recognition.onerror = () => { $('command-result').textContent = '语音不可用或未授权。可输入文字指令。'; };
  recognition.onend = () => { state.activeSpeech = null; $('voice').textContent = '语音输入'; $('voice').setAttribute('aria-pressed','false'); };
  try { recognition.start(); state.activeSpeech = recognition; } catch { $('command-result').textContent = '当前无法开始录音。'; }
}

async function showView(view) {
  state.view = view;
  $('review-view').hidden = view !== 'review';
  $('eval-view').hidden = view !== 'eval';
  for (const button of root.querySelectorAll('[data-view]')) button.setAttribute('aria-pressed', String(button.dataset.view === view));
  state.chartDispose?.();
  if (view === 'review') { renderTopology(); return; }
  try {
    if (!state.charts) {
      $('eval-charts').textContent = '正在加载离线评测表…';
      const table = await asset('eval_charts_workbench.csv','text');
      state.charts = await readCharts(new File([table], 'eval.csv'));
    }
    if (state.view !== 'eval') return;
    const chart = state.charts.find((item) => item.id === state.chartId) ?? state.charts[0];
    $('eval-charts').innerHTML = benchmarkPanel(state.charts, chart);
    state.chartDispose = mountChart($('chart'), chart, state.theme === 'dark');
  } catch (error) { $('eval-charts').textContent = error.message; }
}

async function exportBom(format) {
  const model = board();
  if (!model) return;
  const rows = bomRows(model.annotation);
  const filename = model.title.replace(/[\\/:]/g, '-') + '-BOM.' + format;
  if (format === 'xlsx') download(await xlsx(rows), filename, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
  if (format === 'csv') download(csv(rows), filename, 'text/csv;charset=utf-8');
  if (format === 'json') download(JSON.stringify({ drawing_id: model.annotation.id, rows }, null, 2) + '\n', filename, 'application/json');
}

root.addEventListener('click', (event) => {
  const button = event.target.closest('button');
  if (!button) return;
  const data = button.dataset;
  if (data.view) void showView(data.view);
  if (data.symbol || data.graph) select(data.symbol || data.graph, Boolean(data.graph) || !button.classList.contains('symbol-box'));
  if (data.finding != null) locateFinding(Number(data.finding));
  if (data.clause) openClause(data.clause, button);
  if (data.fix != null) openFix(Number(data.fix), button);
  if (button.hasAttribute('data-close')) button.closest('dialog')?.close();
  if (data.highlight != null) { const marker = $('highlight'); marker?.scrollIntoView(); marker?.focus(); }
  if (data.export) void exportBom(data.export).catch((error) => notice(error.message, 'error'));
  if (data.chart) { state.chartId = data.chart; void showView('eval'); }
  if (data.zoom) { state.zoom = Math.min(2.5, Math.max(1, state.zoom + Number(data.zoom) * .25)); render(); }
  if (button.id === 'apply-fix') void recalculate(true);
});

$('pick-file').addEventListener('click', () => $('file').click());
$('file').addEventListener('change', (event) => {
  if (event.target.files[0]) void loadUpload(event.target.files[0]);
  event.target.value = '';
});
$('drawing-scroll').addEventListener('dragover', (event) => { event.preventDefault(); $('drawing-scroll').classList.add('drop-target'); });
$('drawing-scroll').addEventListener('dragleave', () => $('drawing-scroll').classList.remove('drop-target'));
$('drawing-scroll').addEventListener('drop', (event) => {
  event.preventDefault(); $('drawing-scroll').classList.remove('drop-target');
  if (event.dataTransfer.files[0]) void loadUpload(event.dataTransfer.files[0]);
});
$('fixture').addEventListener('change', () => { if ($('fixture').value) void loadSample($('fixture').value); });
$('bom-filter').addEventListener('input', renderBomTable);
$('severity').addEventListener('change', render);
$('recheck').addEventListener('click', () => { void recalculate(false); });
$('bom').addEventListener('change', (event) => {
  const { bomId, bomKey } = event.target.dataset;
  if (!bomId || !board()) return;
  try {
    const edited = editBom(board().annotation, [bomId], bomKey, event.target.value);
    if (edited.changes.length) {
      applyPage({ ...board(), annotation: edited.annotation }, '编辑 BOM', edited.changes, true, true);
      const values = new Map(edited.changes.map((change) => [change.id, change.after]));
      for (const input of $('bom').querySelectorAll(`[data-bom-key="${bomKey}"]`)) {
        if (values.has(input.dataset.bomId)) input.value = values.get(input.dataset.bomId);
      }
    } else event.target.value = event.target.value.trim();
  } catch (error) { notice(error.message, 'error'); renderBomTable(); }
});
$('undo').addEventListener('click', () => {
  const current = state.work;
  const before = current.history.pop();
  if (!before) return;
  Object.assign(current, before, {revision: current.revision + 1});
  current.log.unshift({reason:'撤销最近更改',changes:[],timestamp:new Date()});
  state.found = null; state.located = new Set();
  render(); notice('已恢复上一版工作副本。', 'success');
});
$('command-form').addEventListener('submit', (event) => { event.preventDefault(); command(); });
$('voice').addEventListener('click', voice);
$('theme').addEventListener('click', () => {
  state.theme = state.theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('workbench-theme', state.theme);
  applyTheme();
  if (state.view === 'eval') void showView('eval');
});
for (const id of ['fix-dialog', 'evidence-dialog']) $(id).addEventListener('close', () => dialogTrigger?.focus());
const observer = new ResizeObserver(renderTopology);
observer.observe($('graph'));

applyTheme();
(async function boot() {
  try {
    const [index, clauses] = await Promise.all([asset('index.json'), asset('clauses.json')]);
    state.clauses = clauses;
    for (const sample of index) cases.set(sample.id, sample);
    $('fixture').innerHTML = '<option value="" disabled>上传的图纸</option>' + index.map((item) => `<option value="${html(item.id)}">${html(item.title)}</option>`).join('');
    $('fixture').value = index[0].id;
    if (!state.work && sequence === 0) await loadSample(index[0].id);
  } catch (error) { notice(error.message, 'error'); }
})();
