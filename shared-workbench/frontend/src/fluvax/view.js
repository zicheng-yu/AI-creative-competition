import { html } from '../format.js';
import { VIEWS, badge } from './model.js';

const tierLabel = {
  T1_WET_LAB_ASSAY: 'T1 公开实验记录',
  T2_SURVEILLANCE: 'T2 监测元数据',
  T3_PEER_REVIEWED_LIT: 'T3 同行评议题名',
  T4_COMPUTATIONAL: 'T4 计算预测',
};

function banner(doc, mode) {
  return `<aside class="flu-banner" role="note">
    <p>${html(doc.boundary)}</p>
    <p><strong>数据版本 ${html(doc.dataset_version)}</strong> · 快照 ${html(doc.snapshot_id.slice(0, 12))} · ${html(mode)}</p>
  </aside>`;
}

function shell(doc, state) {
  return `<div class="flu-app">
    <header class="flu-top">
      <div><p class="flu-kicker">流盾智研</p><h1>证据工作台</h1></div>
      <a class="quiet" href="./index.html">返回赛道工作台</a>
    </header>
    ${banner(doc, state.mode)}
    <nav class="flu-views" aria-label="工作台视图">
      ${VIEWS.map(([id, label]) => `<button type="button" data-view="${id}" aria-pressed="${state.view === id}">${label}</button>`).join('')}
    </nav>
    <div id="flu-panel">${panel(doc, state)}</div>
  </div>
  <dialog id="flu-drawer" aria-labelledby="flu-drawer-title"></dialog>`;
}

function recordButton(row) {
  return `<button type="button" class="flu-badge" data-record="${html(row.evidence_id)}|${html(row.dataset_version)}">${html(badge(row))}</button>`;
}

function snapshot(doc, state) {
  const tiers = ['all', ...new Set(doc.records.map((row) => row.evidence_tier))];
  const sources = ['all', ...new Set(doc.records.map((row) => row.source_type))];
  return `<section>
    <h2>锁定快照</h2>
    <p class="flu-note">只读已审核材料。没有开放上传入口。</p>
    <ul class="flu-releases">${doc.releases.map((row) => `<li><strong>${html(row.dataset_version)}</strong> · ${html(row.released_at)}${row.previous_version ? ` · 上一版 ${html(row.previous_version)}` : ''}</li>`).join('')}</ul>
    <div class="flu-filters">
      <label>等级 <select id="flu-tier">${tiers.map((tier) => `<option value="${html(tier)}" ${tier === state.tier ? 'selected' : ''}>${html(tier === 'all' ? '全部' : tierLabel[tier] || tier)}</option>`).join('')}</select></label>
      <label>来源 <select id="flu-source">${sources.map((source) => `<option value="${html(source)}" ${source === state.source ? 'selected' : ''}>${html(source === 'all' ? '全部' : source)}</option>`).join('')}</select></label>
      <label>检索 <input id="flu-query" value="${html(state.text)}" placeholder="ID 或题名"></label>
    </div>
    <table class="flu-table"><thead><tr><th>记录</th><th>等级</th><th>接入时间</th><th>审阅</th></tr></thead><tbody>
      ${state.visible.map((row) => `<tr><td>${recordButton(row)}<div>${html(row.title)}</div></td><td>${html(tierLabel[row.evidence_tier] || row.evidence_tier)}</td><td>${html(row.ingested_at)}</td><td>${html(row.review_status)}</td></tr>`).join('') || '<tr><td colspan="4">没有匹配记录。</td></tr>'}
    </tbody></table>
  </section>`;
}

function timeline(doc) {
  const curve = doc.timeline.curve;
  const heat = doc.timeline.heatmap;
  return `<section>
    <h2>引用时间线与来源热力</h2>
    <p class="flu-note">曲线和热力来自资料的出版日、接入日和来源类型，不是新的进化模型。</p>
    <div id="flu-chart" class="flu-chart"></div>
    <table class="flu-table"><thead><tr><th>接入月</th><th>来源</th><th>条数</th><th>缺出版日</th></tr></thead><tbody>
      ${heat.map((cell) => `<tr><td>${html(cell.month)}</td><td>${html(cell.source)}</td><td>${cell.records}</td><td>${cell.missing.published_on}</td></tr>`).join('')}
    </tbody></table>
    <p class="flu-note">曲线点数 ${curve.length}。未标出版日的记录 ${doc.timeline.undated_documents.length} 条，日期以来源精度为准。</p>
  </section>`;
}

function qa(doc, state) {
  const question = doc.questions[state.question];
  return `<section>
    <h2>Task-1 循证问答</h2>
    <div class="flu-questions">${doc.questions.map((item, index) => `<button type="button" data-question="${index}" aria-pressed="${index === state.question}">${html(item.question_id)}</button>`).join('')}</div>
    <p>${html(question.query)}</p>
    <p class="flu-note">Recall@5 ${question.recall_at_5} · ${question.elapsed_ms.toFixed(1)} ms · 命中 ${html(question.hits.join('、'))}</p>
    <ol class="flu-statements">${question.statements.map((row) => `<li><p>${html(row.text)}</p>${recordButton(row)} <span class="flu-tier">${html(tierLabel[row.evidence_tier] || row.evidence_tier)}</span></li>`).join('')}</ol>
  </section>`;
}

function compare(doc) {
  return `<section>
    <h2>Task-2 证据维度</h2>
    <p class="flu-note">${html(doc.score_note)}</p>
    <div id="flu-chart" class="flu-chart"></div>
    <div class="flu-cards">${doc.dossiers.map((row) => {
      const dim = row.evidence_dimensions;
      const conflicts = dim.citation_conflicts.map((item) => `${item.left_ref} ↔ ${item.right_ref}`).join('；') || '无';
      return `<article class="flu-card ${dim.citation_conflicts.length || dim.evidence_gaps.length ? 'is-open' : ''}">
        <h3>${html(row.label)}</h3>
        <p>来源 ${row.source_coverage.count} · 版本 ${row.version_consistency.consistent ? '一致' : '不一致'} · ${html(Object.entries(dim.tier_distribution).map(([tier, count]) => `${tierLabel[tier] || tier} ${count}`).join(' · '))}</p>
        <p><strong>引用交叉</strong> ${html(conflicts)}</p>
        <p><strong>证据空白</strong> ${html(dim.evidence_gaps.join('、') || '无')}</p>
      </article>`;
    }).join('')}</div>
  </section>`;
}

function review(doc, state) {
  const local = state.review;
  const metrics = doc.metrics;
  return `<section>
    <h2>签批与离线评测</h2>
    <p class="flu-watermark">${html(local.watermark)}</p>
    <ol class="flu-statements">${local.statements.map((row) => `<li>
      <p>${html(row.text)}</p>${recordButton(row)}
      <span>${html(local.dispositions[row.statement_id] || '未处置')}</span>
      <span class="flu-actions">
        <button type="button" data-disposition="accept" data-statement="${html(row.statement_id)}">采纳</button>
        <button type="button" data-disposition="flag_doubt" data-statement="${html(row.statement_id)}">标疑</button>
        <button type="button" data-disposition="reject" data-statement="${html(row.statement_id)}">不采纳</button>
      </span>
    </li>`).join('')}</ol>
    <p class="flu-actions">
      <button type="button" id="flu-sign" ${local.signed ? 'disabled' : ''}>签批当前问答</button>
      <button type="button" id="flu-export">导出 Markdown</button>
      <button type="button" id="flu-reset">恢复为草稿</button>
    </p>
    <p id="flu-sign-note" class="flu-note"></p>
    <h3>已测指标</h3>
    <ul>
      <li>Task-1 Recall@5 ${metrics.task_1.recall_at_5}，nDCG@5 ${metrics.task_1.ndcg_at_5.toFixed(3)}，中位 ${metrics.task_1.median_ms.toFixed(1)} ms</li>
      <li>已接受引用与版本锁一致 ${metrics.citations.accepted_matching_lock}/${metrics.citations.accepted_total}</li>
      <li>无检索草稿被接受 ${metrics.no_retrieval_baseline.accepted_statements}/${metrics.no_retrieval_baseline.submitted}</li>
      <li>疗效承诺探针被拒绝 ${metrics.compliance_gate.probe_effect_promise_rejected}/${metrics.compliance_gate.probe_submitted}</li>
      <li>档案与标注一致 ${metrics.task_2.dossiers_matching_gold}/${metrics.task_2.dossiers}</li>
      <li>人工 SOP ${html(doc.manual_sop_baseline)}</li>
    </ul>
    <div id="flu-chart" class="flu-chart"></div>
  </section>`;
}

function panel(doc, state) {
  if (state.view === 'snapshot') return snapshot(doc, state);
  if (state.view === 'timeline') return timeline(doc);
  if (state.view === 'qa') return qa(doc, state);
  if (state.view === 'compare') return compare(doc);
  return review(doc, state);
}

export function page(doc, state) {
  return shell(doc, state);
}

export function drawer(record) {
  if (!record) return '';
  return `<h2 id="flu-drawer-title">${html(record.evidence_id)}</h2>
    <p>${html(badge(record))}</p>
    <p>${html(tierLabel[record.evidence_tier] || record.evidence_tier)} · ${html(record.review_status)} · ${html(record.ingested_at)}</p>
    <p>${html(record.raw_snippet)}</p>
    <p><a href="${html(record.source_url)}" rel="noreferrer">${html(record.primary_ref)}</a></p>
    <p>${html(record.claim_summary)}</p>
    <button type="button" id="flu-close">关闭</button>`;
}

export function lineChart(timelineDoc) {
  return {
    id: 'timeline',
    kind: 'line',
    title: '出版与接入计数',
    axes: timelineDoc.curve.map((row) => ({ label: row.period })),
    series: [
      { name: '出版文献', values: timelineDoc.curve.map((row) => row.document_count) },
      { name: '接入记录', values: timelineDoc.curve.map((row) => row.ingested_count) },
    ],
  };
}
