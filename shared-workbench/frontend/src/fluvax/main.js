import '../style.css';
import './style.css';
import { mountChart } from '../charts.js';
import { applyReview, canSign, emptyReview, filterRecords, radarChart, reviewMarkdown, sameSnapshot, signReview } from './model.js';
import { drawer, lineChart, page } from './view.js';

const root = document.querySelector('#app');
const apiBase = (import.meta.env.VITE_FLUVAX_API || '/fluvax-api').replace(/\/$/, '');
const state = {
  doc: null, view: 'snapshot', tier: 'all', source: 'all', text: '', question: 0,
  review: null, mode: '正在读取离线演示',
};
let dispose;

function paint() {
  dispose?.();
  dispose = undefined;
  const doc = state.doc;
  if (!doc) {
    root.innerHTML = `<p class="flu-note">${state.mode}</p>`;
    return;
  }
  root.innerHTML = page(doc, { ...state, visible: filterRecords(doc.records, state) });
  const host = document.querySelector('#flu-chart');
  if (!host) return;
  const chart = state.view === 'timeline' ? lineChart(doc.timeline)
    : state.view === 'compare' ? radarChart(doc.dossiers)
      : state.view === 'review' ? doc.charts[0] : null;
  if (chart) dispose = mountChart(host, chart, document.documentElement.dataset.theme === 'dark');
}

function openRecord(token) {
  const [evidenceId, version] = token.split('|');
  const record = state.doc.records.find((row) => row.evidence_id === evidenceId && row.dataset_version === version);
  const dialog = document.querySelector('#flu-drawer');
  dialog.innerHTML = drawer(record);
  if (record) dialog.showModal();
}

function download(filename, text) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

root.addEventListener('click', (event) => {
  const button = event.target.closest('button');
  if (!button || !state.doc) return;
  if (button.dataset.view) state.view = button.dataset.view;
  else if (button.dataset.question) {
    state.question = Number(button.dataset.question);
    state.review = emptyReview(state.doc.questions[state.question].statements);
  } else if (button.dataset.record) {
    openRecord(button.dataset.record);
    return;
  } else if (button.dataset.disposition) {
    try {
      state.review = applyReview(state.review, button.dataset.statement, button.dataset.disposition);
    } catch (error) {
      document.querySelector('#flu-sign-note').textContent = error.message;
      return;
    }
  } else if (button.id === 'flu-sign') {
    const note = document.querySelector('#flu-sign-note');
    if (!canSign(state.review)) {
      note.textContent = '签批前需要逐条处置。';
      return;
    }
    state.review = signReview(state.review);
  } else if (button.id === 'flu-export') {
    download('fluvax-review.md', reviewMarkdown(state.review, state.doc.boundary, state.doc.dataset_version));
    return;
  } else if (button.id === 'flu-reset') {
    state.review = emptyReview(state.doc.questions[state.question].statements);
  } else if (button.id === 'flu-close') {
    document.querySelector('#flu-drawer').close();
    return;
  } else return;
  paint();
});

root.addEventListener('change', (event) => {
  const target = event.target;
  if (target.id === 'flu-tier') state.tier = target.value;
  else if (target.id === 'flu-source') state.source = target.value;
  else return;
  paint();
});

root.addEventListener('input', (event) => {
  const target = event.target;
  if (target.id !== 'flu-query') return;
  state.text = target.value;
  paint();
  document.querySelector('#flu-query')?.focus();
});

async function boot() {
  try {
    const response = await fetch(new URL('./fluvax/workbench.json', location.href));
    if (!response.ok) throw new Error('无法读取离线演示数据');
    state.doc = await response.json();
    state.review = emptyReview(state.doc.questions[0].statements);
    state.mode = '离线演示数据';
    paint();
  } catch (error) {
    state.mode = error.message;
    paint();
    return;
  }
  try {
    const response = await fetch(`${apiBase}/api/v1/health`, { signal: AbortSignal.timeout(1500) });
    const health = response.ok ? await response.json() : null;
    state.mode = !response.ok ? '离线演示数据（本地接口未连接）'
      : sameSnapshot(health, state.doc) ? '本地接口在线，快照一致'
        : '离线演示数据（接口快照与当前版本不一致）';
  } catch {
    state.mode = '离线演示数据（本地接口未连接）';
  }
  paint();
}

boot();
