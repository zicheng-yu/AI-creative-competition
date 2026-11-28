import { html } from '../format.js';
import { ACCOUNTING_NOTE, COMMAND_PRESETS, DAYS, FAULTS, METRICS, SCENARIOS, STRATEGIES, STRATEGY_NAMES, decimal, hourLabel, isCrossRegion, metricValue, presentReceipt, slotLabel } from './data.js';

const strategies = STRATEGIES.map((key) => `<option value="${key}" ${key === 'SuCompute' ? 'selected' : ''}>${STRATEGY_NAMES[key]}</option>`).join('');

export const shell = `<header class="control-header">
  <div class="control-brand"><span class="station-mark" aria-hidden="true"></span><b>苏算绿枢</b><span class="header-divider"></span><a href="./index.html">共用工作台</a></div>
  <div class="header-actions"><span id="source-label" class="source-badge">固定仿真回放</span><button class="s-button ghost" id="theme" type="button" aria-pressed="false">切换深色</button></div>
</header>
<main class="delta-main" id="main" tabindex="-1">
  <section class="dashboard-intro" aria-labelledby="dashboard-title">
    <div><div class="region-name">江苏 1+13 / 长三角协同</div><h1 id="dashboard-title">算网调度沙盘</h1></div>
    <div class="intro-controls"><button class="s-button outline" id="export-csv" type="button">导出对比 CSV</button><button class="s-button outline" id="export-md" type="button">导出评测摘要</button></div>
  </section>
  <div id="boot" class="global-message" role="status">正在读取拓扑和回放索引…</div>
  <div id="dashboard" hidden>
    <section class="scenario-bar" aria-label="仿真设置">
      <div class="scenario-tabs" role="group" aria-label="切换场景">
        ${Object.entries(SCENARIOS).map(([key, label]) => `<button type="button" class="scenario-tab" data-scene="${key}" aria-pressed="${key === 'normal_weekday'}">${label}</button>`).join('')}
      </div>
      <div class="run-actions">
        <label class="sr-only" for="strategy">地图策略</label><select id="strategy" class="dash-select" aria-label="地图策略">${strategies}</select>
        <button class="s-button primary" type="button" id="simulate">运行四策略</button>
      </div>
    </section>
    <p id="operation" class="operation" role="status" aria-live="polite"></p>
    <div class="scene-layout">
      <section class="map-panel" aria-labelledby="map-heading">
        <div class="map-heading"><div><span class="map-caption">16 个仿真节点</span><h2 id="map-heading">长三角算网</h2></div><output id="map-clock">—</output></div>
        <div class="canvas-area"><canvas id="network-map" aria-hidden="true"></canvas><div id="node-targets" class="node-targets" aria-label="城市算力节点"></div>
          <aside class="map-legend" aria-label="地图图例">
            <span><i class="blue"></i>装机低负载</span><span><i class="teal"></i>中负载</span><span><i class="sand"></i>高负载</span><span><i class="amber"></i>故障或异常</span>
          </aside>
          <div class="map-attribution">Natural Earth</div>
        </div>
        <div class="transport">
          <button type="button" id="play" class="s-button transport-button" aria-pressed="false">▶ 播放</button>
          <label class="sr-only" for="hour">回放小时</label><input id="hour" type="range" min="0" max="167" value="14" aria-label="回放小时">
          <label class="sr-only" for="day">回放日期</label><select id="day" class="dash-select" aria-label="回放日期">${DAYS.map((name, i) => `<option value="${i}">${name}</option>`).join('')}</select>
        </div>
      </section>
      <section class="dispatch-panel" aria-labelledby="node-heading">
        <header class="dispatch-header"><div><div id="node-kind" class="region-name">江苏地市节点</div><h2 id="node-heading">南京</h2></div><label class="sr-only" for="node-select">选择城市</label><select class="dash-select" id="node-select" aria-label="选择城市"></select></header>
        <dl id="node-stats" class="node-stats"></dl>
        <div id="node-fault" class="node-fault"></div>
        <div class="route-heading"><h3>本小时调度飞线</h3><span id="route-count"></span></div>
        <div id="routes" class="routes"></div>
        <div class="audit-actions"><button type="button" class="s-button outline" id="open-audit">任务审计样本</button><button id="jump-fault" type="button" class="s-button outline">跳到预置故障</button></div>
      </section>
    </div>
    <section class="metric-section" aria-labelledby="metrics-title">
      <div class="section-bar"><h2 id="metrics-title">当前策略的六维指标</h2><span id="metric-scope"></span></div>
      <div id="kpis" class="kpi-strip"></div>
    </section>
    <section class="comparison-section" aria-labelledby="compare-title">
      <div class="section-bar"><h2 id="compare-title">四策略对比</h2><span id="compare-scope"></span></div>
      <div id="comparison" class="table-frame"></div>
      <div id="delta-chart"></div>
    </section>
    <section class="command-panel" aria-labelledby="command-title">
      <div class="section-bar"><h2 id="command-title">调度 Copilot</h2><span>本地仿真接口</span></div>
      <form id="command-form"><label for="command" class="sr-only">调度指令</label><div class="command-row"><input id="command" maxlength="500" placeholder="例如：碳排权重调至 0.6" autocomplete="off" required><button class="s-button primary" type="submit">执行指令</button></div></form>
      <div class="command-presets">${COMMAND_PRESETS.map((preset) => `<button class="s-button outline" type="button" data-command="${html(preset.text)}">${html(preset.label)}</button>`).join('')}<button id="open-inject" class="s-button outline" type="button">注入自选故障</button><button id="fixed-replay" class="s-button ghost" type="button">恢复固定回放</button></div>
      <div id="command-result" class="command-result" aria-live="polite"></div>
    </section>
  </div>
  <footer class="dashboard-footer">城市、负载及故障数据来自 JS-ComputeSim-313 仿真。底图采用 Natural Earth。</footer>
</main>
<dialog class="audit-drawer" id="audit-dialog" aria-labelledby="audit-title"></dialog>
<dialog class="fault-dialog" id="fault-dialog" aria-labelledby="fault-title">
  <form id="fault-form">
    <div class="drawer-top"><div><span class="region-name">独立仿真实验</span><h2 id="fault-title">注入自选故障</h2></div><button class="s-button ghost drawer-close" data-close="fault" type="button" aria-label="关闭故障设置">×</button></div>
    <label>节点<select id="fault-node" class="dash-select" required></select></label>
    <label>故障类型<select id="fault-kind" class="dash-select"><option value="capacity">容量下降</option><option value="outage">节点宕机</option><option value="pue">PUE 上升</option></select></label>
    <label>影响幅度<span id="fault-unit">容量损失比例，0–1</span><input id="fault-severity" type="number" value="0.3" min="0.01" max="1" step="0.01" required></label>
    <label>持续时长（分钟）<input id="fault-duration" type="number" value="60" min="5" max="480" step="5" required></label>
    <p id="fault-status">在当前仿真时点后的 24 小时区间内执行。</p>
    <button class="s-button primary" type="submit">确认并重算</button>
  </form>
</dialog>`;

export function renderMetrics(element, comparison, runs, strategy) {
  element.innerHTML = METRICS.map((metric) => `<article class="kpi">
    <span>${html(metric.label)}</span><div><strong>${metricValue(runs[strategy].kpis, metric)}</strong><small>${html(metric.unit)}</small></div></article>`).join('');
  comparison.innerHTML = `<table class="strategy-table"><thead><tr><th scope="col">策略</th>
    ${METRICS.map((m) => `<th scope="col">${html(m.short)} ${m.unit ? `<small>${html(m.unit)}</small>` : ''}</th>`).join('')}</tr></thead><tbody>${STRATEGIES.map((key) => {
      const values = runs[key].kpis;
      const badge = key === strategy ? ' class="selected-run"' : '';
      return `<tr${badge}><th scope="row"><span class="strategy-dot"></span>${html(STRATEGY_NAMES[key])}</th>${METRICS.map((m) => `<td>${metricValue(values, m)}</td>`).join('')}</tr>`;
    }).join('')}</tbody></table>`;
}

export function renderRoutes(routes, flights, topology, activeId, live) {
  const use = flights.filter(([, src, dst]) => src === activeId || dst === activeId);
  const choices = (use.length ? use : flights).slice(0, 4);
  routes.innerHTML = choices.length ? choices.map(([, from, to, count, example]) => {
    const source = topology.nodes[from], target = topology.nodes[to];
    if (!source || !target) return '';
    return `<div class="route-line"><span class="route-mark ${source.external || target.external ? 'cross' : ''}" aria-hidden="true"></span><span>${html(source.city)} → ${html(target.city)}</span><small>${count} 个调度段</small>${!live ? `<button type="button" data-task="${html(example)}" class="route-link" aria-label="查看任务 ${html(example)}">审计</button>` : ''}</div>`;
  }).join('') : '<p class="micro-empty">这一小时没有跨节点调度记录。</p>';
  return use.length || flights.length;
}

export function kpisInline(data) {
  return `<dl class="inline-kpis">${METRICS.map((metric) => `<div><dt>${html(metric.short)}</dt><dd>${metricValue(data, metric)} ${html(metric.unit)}</dd></div>`).join('')}</dl>`;
}

export function faultSummary(item, topology) {
  if (!item) return '';
  const elapsed = item.elapsed_s == null ? '—' : decimal(item.elapsed_s, 4) + ' 秒';
  const kind = FAULTS[item.kind] || item.kind;
  return `<div class="fault-event"><strong>${html(item.city)} · ${html(kind)}</strong><span>${slotLabel(item.slot, topology.slot_minutes)} · ${item.duration_slots * topology.slot_minutes} 分钟</span><span>仿真编排耗时 ${elapsed} · ${item.trajectories?.length ?? 0} 条处置记录</span>${(item.trajectories ?? []).slice(0, 2).map((trajectory) => `<span>任务 #${html(trajectory.task_id)} · ${html(trajectory.source)} → ${html(trajectory.target || '无可行去向')}${trajectory.sla_met == null ? '' : trajectory.sla_met ? ' · SLA 达成' : ' · SLA 未达成'}</span>`).join('')}</div>`;
}

const auditHeader = `<header class="drawer-top"><div><span class="region-name">跨域计量</span><h2 id="audit-title">任务轨迹与碳足迹</h2></div><button class="s-button ghost drawer-close" data-close="audit" type="button" aria-label="关闭任务审计">×</button></header>`;

export function paragraphs(text) {
  return String(text || '').split(/\n+/).filter(Boolean).map((line) => `<p>${html(line)}</p>`).join('');
}

export function auditShell(list, current, body) {
  const choices = list.map((id) => `<option value="${id}" ${id === current ? 'selected' : ''}>任务 #${id}</option>`).join('');
  return `${auditHeader}<div class="audit-toolbar"><button type="button" class="s-button outline" data-ledger="csv">导出账本 CSV</button><button type="button" class="s-button outline" data-ledger="api">加载本窗口完整账本</button></div>${choices ? `<label class="audit-picker" for="audit-task">任务凭证<select class="dash-select" id="audit-task">${choices}</select></label>` : ''}<div id="audit-body">${body}</div>`;
}

export function auditBody(receipt, topology) {
  const view = presentReceipt(receipt, topology);
  const first = receipt.segments?.[0];
  const destination = first && topology.nodes[first.node];
  const candidates = view.candidates;
  const chosen = destination && candidates.find((item) => item.node === destination.id)?.pools.find((item) => item.pool === first.pool);
  return `<section class="receipt-section">
    <h3>任务 #${receipt.task_id} <small>${html(receipt.task_class)}</small>${isCrossRegion(receipt) ? ' <small>跨域</small>' : ''}</h3>
    <p>${html(topology.nodes[receipt.source]?.city)} → ${html(destination?.city || '未派单')} · ${html(first?.pool ?? '无芯片池')}</p>
    <dl class="inline-kpis"><div><dt>算力当量</dt><dd>${decimal(receipt.effective_efh, 3)} EF·h</dd></div><div><dt>电费结算</dt><dd>¥ ${decimal(receipt.electricity_cny, 2)}</dd></div><div><dt>碳排放</dt><dd>${decimal(receipt.co2_kg)} kgCO₂</dd></div><div><dt>相对全网供电减排</dt><dd>${decimal(receipt.avoided_vs_grid_kg)} kgCO₂</dd></div><div><dt>SLA</dt><dd>${receipt.sla_met ? '达成' : '未达成'}</dd></div></dl>
  </section>
  ${receipt.selection_reason ? `<section class="receipt-section"><h3>选中理由</h3>${paragraphs(receipt.selection_reason)}</section>` : ''}
  <section class="receipt-section">
    <h3>选中记录</h3>
    ${first ? `<p>首次派至 ${html(destination?.city)} 的 ${html(first.pool)} 池，亲和度 ${decimal(chosen?.score, 2)}，网络时延 ${decimal(first.latency_ms, 1)} ms，时延预算 ${decimal(receipt.latency_limit_ms, 1)} ms。</p>
    ${first.probability != null ? `<p>Safe-RL 选中动作概率 ${decimal(first.probability * 100, 2)}%。</p>` : '<p>该策略没有 Safe-RL 动作概率。</p>'}
    ${first.pue != null ? `<p>实时 PUE ${decimal(first.pue, 3)}，绿电占比 ${decimal(first.green_share * 100, 2)}%。</p>` : ''}
    ${first.resource_shadow != null ? `<p>资源影子价格 ${decimal(first.resource_shadow, 4)}，碳影子价格 ${decimal(first.carbon_shadow, 4)}。</p>` : '<p>该策略没有 MILP 影子价格。</p>'}` : '<p>账本没有可展示的执行分段。</p>'}
  </section>
  <section class="receipt-section"><h3>执行轨迹</h3><ol class="segments">
    ${(receipt.segments ?? []).map((segment) => `<li><strong>${html(topology.nodes[segment.node]?.city)} · ${html(segment.pool)}</strong><span>${slotLabel(segment.start_slot, topology.slot_minutes)} → ${slotLabel(segment.end_slot, topology.slot_minutes)}</span></li>`).join('')}
  </ol></section>
  <details class="receipt-section"><summary>查看 16 节点候选亲和度</summary><div class="table-scroll"><table><thead><tr><th>节点</th><th>时延</th>${topology.pools.map((pool) => `<th>${html(pool)}</th>`).join('')}</tr></thead><tbody>
    ${candidates.map((node) => `<tr><th scope="row">${html(node.city)}</th><td>${decimal(node.latency, 1)} ms</td>${node.pools.map((pool) => `<td title="${pool.feasible ? '可行' : '不可行'}" class="${pool.feasible ? 'is-feasible' : 'is-blocked'}">${decimal(pool.score, 2)}${pool.feasible ? ' ✓' : ' ×'}</td>`).join('')}</tr>`).join('')}
    </tbody></table></div></details>
  <section class="receipt-section"><h3>碳减排凭证 SHA-256</h3><code class="receipt-hash">${html(receipt.sha256)}</code><p class="accounting-note">${html(ACCOUNTING_NOTE)}</p></section>`;
}
