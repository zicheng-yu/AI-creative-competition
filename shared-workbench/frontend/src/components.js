import { html, labels, percent } from './format.js';

const chartLabels = { line: '趋势', radar: '维度', bar: '消融' };

export function benchmarkPanel(charts, selected) {
  if (!charts.length) {
    return '<div class="panel empty"><h2 id="benchmark">评测数据</h2><p>导入 JSON 或 CSV 后查看策略对比。</p></div>';
  }
  const kindCounts = new Map();
  for (const chart of charts) kindCounts.set(chart.kind, (kindCounts.get(chart.kind) || 0) + 1);
  return `<section class="panel benchmark" aria-labelledby="benchmark">
    <div class="panel-head">
      <div><h2 id="benchmark">${html(selected.title)}</h2><p>离线评测 <span class="panel-divider"></span> ${html(selected.unit || '数值')}</p></div>
      <div class="segmented" aria-label="选择图表">
        ${charts.map((chart) => {
          const label = kindCounts.get(chart.kind) === 1
            ? `${chartLabels[chart.kind]}<span class="sr-only"> ${html(chart.title)}</span>` : html(chart.title);
          return `<button data-chart="${html(chart.id)}" aria-pressed="${chart.id === selected.id}">${label}</button>`;
        }).join('')}
      </div>
    </div>
    <div id="chart" class="chart" role="img" aria-label="${html(selected.title)}。可在下方查看数值表。"></div>
    <details class="chart-table"><summary>查看数值表</summary>
      <div class="table-scroll"><table><thead><tr><th scope="col">策略</th>${selected.axes.map((axis) => `<th scope="col">${html(axis.label)}</th>`).join('')}</tr></thead>
      <tbody>${selected.series.map((series) => `<tr><th scope="row">${html(series.name)}</th>${series.values.map((value) => `<td>${html(value)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>
    </details>
  </section>`;
}

export function findingsPanel(findings, filter) {
  const subset = filter === 'all' ? findings : findings.filter((item) => item.severity === filter);
  const filters = [['all', '全部'], ...Object.entries(labels)];
  return `<section class="panel findings" aria-labelledby="findings">
    <div class="panel-head">
      <div><h2 id="findings">规则与约束</h2><p>按等级定位待复核项</p></div>
      <label class="filter"><span class="sr-only">风险等级</span><select id="severity">${filters.map(([key, title]) =>
        `<option value="${key}" ${key === filter ? 'selected' : ''}>${title}</option>`).join('')}</select></label>
    </div>
    <div class="finding-list">${subset.length ? subset.map((item) => `<article class="finding">
      <div class="finding-title"><span class="severity ${item.severity}">${labels[item.severity]}</span><h3>${html(item.title)}</h3></div>
      <p>${html(item.detail)}</p>
      ${item.recommendation ? `<p class="recommendation">${html(item.recommendation)}</p>` : ''}
      ${item.source_id ? `<button class="text-button" data-source="${html(item.source_id)}">定位来源 <span aria-hidden="true">↗</span></button>` : ''}
    </article>`).join('') : '<p class="empty">该等级暂无记录。</p>'}</div>
  </section>`;
}

export function evidencePanel(sources) {
  return `<section class="panel evidence" aria-labelledby="evidence">
    <div class="panel-head"><div><h2 id="evidence">来源记录</h2><p>查看识别片段与原文</p></div></div>
    <div class="source-list">${sources.length ? sources.map((source) => `<button class="source" data-source="${html(source.source_id)}">
      <span class="source-icon" aria-hidden="true">▤</span><span class="source-copy"><strong>${html(source.title)}</strong><span>${html(source.raw_snippet)}</span></span>
      <span class="source-confidence">${percent(source.confidence)}</span>
    </button>`).join('') : '<p class="empty">暂无来源记录。</p>'}</div>
  </section>`;
}

export function evidenceDetails(source) {
  const start = source.source_text.indexOf(source.raw_snippet);
  const end = start + source.raw_snippet.length;
  let link = '';
  if (source.source_url) {
    const url = new URL(source.source_url);
    if (['http:', 'https:'].includes(url.protocol)) {
      link = `<a class="text-button" href="${html(url.href)}" target="_blank" rel="noopener noreferrer">打开原文件 ↗</a>`;
    }
  }
  return `<header class="drawer-header"><h2 id="source-title">${html(source.title)}</h2><button class="quiet icon-button" data-close aria-label="关闭来源详情">×</button></header>
    <dl class="source-meta"><div><dt>来源编号</dt><dd>${html(source.source_id)}</dd></div><div><dt>版本</dt><dd>${html(source.version)}</dd></div><div><dt>置信度</dt><dd>${percent(source.confidence)}</dd></div></dl>
    <div class="drawer-actions"><button class="quiet" data-highlight>跳到原文片段</button>${link}</div>
    <p class="source-document" aria-label="来源原文">${html(source.source_text.slice(0, start))}<mark id="highlight" tabindex="-1">${html(source.raw_snippet)}</mark>${html(source.source_text.slice(end))}</p>`;
}

const formats = { md: 'Markdown', pdf: 'PDF', csv: 'CSV', xlsx: 'Excel' };

export function reportPanel() {
  return `<section class="panel report" aria-labelledby="report">
    <div class="panel-head"><div><h2 id="report">报告导出</h2><p>下载当前工作区的评测与记录</p></div></div>
    <div class="export-grid">${Object.entries(formats).map(([code, label]) => `<button class="quiet export-button" data-export="${code}"><strong>${label}</strong><span aria-hidden="true">↓</span></button>`).join('')}</div>
    <p id="export-status" class="export-status" role="status"></p>
  </section>`;
}
