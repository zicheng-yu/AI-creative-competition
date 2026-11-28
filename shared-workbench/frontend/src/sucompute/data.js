export const SCENARIOS = Object.freeze({
  normal_weekday: '常规工作日',
  high_renewable: '绿电大发日',
  peak_shaving: '尖峰保电日',
  fault_stress: '节点故障压测',
});

export const STRATEGIES = ['RR-Local', 'Least-Loaded', 'Cost-First', 'SuCompute'];
export const STRATEGY_NAMES = {
  'RR-Local': '就近轮询', 'Least-Loaded': '最低负载', 'Cost-First': '成本优先', SuCompute: '苏算绿枢',
};

export const METRICS = [
  { key: 'utilization', label: '有效在线利用率', short: '利用率', unit: '%', scale: 100, digits: 2 },
  { key: 'sla', label: 'SLA 履约率', short: 'SLA', unit: '%', scale: 100, digits: 2 },
  { key: 'kwh_per_efh', label: '单位能耗', short: '单位能耗', unit: 'kWh/EF·h', scale: 1, digits: 1, lower: true },
  { key: 'pue', label: '设施能效', short: 'PUE', unit: '', scale: 1, digits: 3, lower: true },
  { key: 'green_share', label: '绿电消纳占比', short: '绿电占比', unit: '%', scale: 100, digits: 2 },
  { key: 'kgco2_per_efh', label: '单位碳排放', short: '碳强度', unit: 'kgCO₂/EF·h', scale: 1, digits: 1, lower: true },
];

export const TREND_KEYS = ['utilization', 'pue', 'kgco2_per_efh'];
export const DAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
export const FAULTS = { outage: '节点宕机', capacity: '容量下降', pue: 'PUE 上升' };

export const COMMAND_PRESETS = [
  { label: '迎峰度夏保电', text: '迎峰度夏保电模式：碳排权重调至 0.6' },
  { label: '南京 30% 算力故障', text: '注入南京节点 30% 算力宕机故障' },
  { label: '优先绿电消纳', text: '优先绿电消纳' },
  { label: '解释调度', text: '解释调度' },
];

export const ACCOUNTING_NOTE = '电费来自调度后端 weather() 的演示分时电价，碳因子是演示参数 GRID=0.55 kgCO₂/kWh。生态环境部、国家统计局公告 2024 年第 33 号公布的 2022 年华东区域因子是 0.5617，本凭证不把 0.55 写成那份公告的数字。凭证是计量 JSON 的 SHA-256，不含中文选中理由。';

const formats = new Map();
export function decimal(value, digits = 1) {
  if (value == null || !Number.isFinite(value)) return '—';
  if (!formats.has(digits)) formats.set(digits, new Intl.NumberFormat('zh-CN', { maximumFractionDigits: digits, minimumFractionDigits: digits }));
  return formats.get(digits).format(value);
}

export function metricValue(metrics, metric) {
  const value = metrics?.[metric.key];
  return value == null ? '—' : decimal(value * metric.scale, metric.digits);
}

export function hourLabel(hour) {
  return `${DAYS[Math.floor(hour / 24)] ?? '仿真日'} ${String(hour % 24).padStart(2, '0')}:00`;
}

export function slotLabel(slot, slotMinutes = 5) {
  const minutes = slot * slotMinutes;
  return `${DAYS[Math.floor(minutes / 1440)] ?? '仿真日'} ${String(Math.floor(minutes / 60) % 24).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

export function validateReplay(replay) {
  if (!Array.isArray(replay?.hourly) || replay.hourly.length === 0 || !replay.kpis
      || !Array.isArray(replay.flights)
      || !['utilization', 'pue', 'green_share', 'health'].every((key) => replay.nodes?.[key]?.length === replay.hourly.length)) {
    throw new Error('仿真数据格式不符合 SuCompute 回放契约。');
  }
  return replay;
}

export function createReplayStore(root, request = fetch) {
  const cache = new Map();
  const read = (name) => {
    if (!/^[a-z0-9_]+\.json$/.test(name)) throw new Error('回放索引含无效文件名。');
    if (!cache.has(name)) {
      const pending = request(new URL(name, root)).then((response) => {
        if (!response.ok) throw new Error(`读取 ${name} 失败（HTTP ${response.status}）。`);
        return response.json();
      }).catch((error) => {
        cache.delete(name);
        if (error instanceof SyntaxError) throw new Error('回放文件不可读，请先准备演示数据。');
        throw error;
      });
      cache.set(name, pending);
    }
    return cache.get(name);
  };
  return {
    async boot() {
      const [topology, index] = await Promise.all([read('topology.json'), read('scenarios_4x4.json')]);
      if (!Array.isArray(topology.nodes) || index.version !== 2
          || !Object.keys(SCENARIOS).every((key) => index.scenarios?.[key])) {
        throw new Error('需要 SuCompute v2 的拓扑与场景索引。');
      }
      return { topology, index };
    },
    async scene(index, id) {
      const data = await read(index.scenarios[id]);
      if (data.version !== 2 || data.scenario !== id) throw new Error('回放分片与当前场景不一致。');
      return Object.fromEntries(STRATEGIES.map((strategy) => [strategy, validateReplay(data.strategies[strategy])]));
    },
    async faults() { return (await read('fault_failover_trace.json')).events; },
    async receipts() { return (await read('ledger_sample.json')).receipts; },
  };
}

const flightIndex = new WeakMap();
export function flightsAt(replay, hour) {
  if (!flightIndex.has(replay)) {
    const byHour = new Map();
    for (const flight of replay.flights) {
      if (!byHour.has(flight[0])) byHour.set(flight[0], []);
      byHour.get(flight[0]).push(flight);
    }
    for (const flights of byHour.values()) flights.sort((left, right) => right[3] - left[3]);
    flightIndex.set(replay, byHour);
  }
  return flightIndex.get(replay).get(hour) ?? [];
}

export function dailyChart(runs, index, key) {
  const metric = METRICS.find((item) => item.key === key);
  const start = 24 * index;
  const end = Math.min(start + 24, runs.SuCompute.hourly.length);
  const axes = Array.from({length: end - start}, (_, mark) => ({ label: `${String(mark).padStart(2, '0')}:00` }));
  const series = STRATEGIES.map((name) => ({
    name: STRATEGY_NAMES[name],
    values: runs[name].hourly.slice(start, end).map((data) => data[key] == null ? null : Number((data[key] * metric.scale).toFixed(metric.digits))),
  }));
  return { id: key, kind: 'line', title: `${metric.short}日内变化`, unit: metric.unit, tightValueAxis: key === 'pue', axes, series };
}

export function isCrossRegion(receipt) {
  if (typeof receipt?.cross_region === 'boolean') return receipt.cross_region;
  return (receipt?.segments ?? []).some((segment) => segment.latency_ms === 10);
}

export function presentReceipt(receipt, topology) {
  if (Array.isArray(receipt?.candidate_affinity)) {
    const candidates = receipt.candidate_affinity.map((item) => ({
      node: item.node,
      city: topology.nodes[item.node]?.city,
      latency: item.latency_ms,
      resource: item.resource_shadow,
      carbon: item.carbon_shadow,
      pools: topology.pools.map((pool, index) => ({
        pool, score: item.scores?.[index], feasible: Boolean(item.feasible?.[index]),
      })),
    }));
    return { ...receipt, candidates };
  }
  return { ...receipt, candidates: receiptCandidates(receipt, topology) };
}

export function ledgerCsv(receipts, topology) {
  const header = ['任务编号', '场景', '策略', '种子', '来源城市', '目的城市', '是否跨域', '任务类型',
    '算力当量EF·h', '电量kWh', '电费元', '碳排kg', '减排kg', 'SLA达成', '芯片池', '亲和度', '时延ms',
    'PUE', '绿电占比', '动作概率', '资源影子价格', '碳影子价格', '凭证SHA256', '选中理由'];
  const rows = [header];
  for (const receipt of receipts) {
    const view = presentReceipt(receipt, topology);
    const segment = receipt.segments?.[0];
    const node = view.candidates?.find((item) => item.node === segment?.node);
    const pool = node?.pools?.find((item) => item.pool === segment?.pool);
    rows.push([
      receipt.task_id, receipt.scenario, receipt.strategy, receipt.seed,
      topology.nodes[receipt.source]?.city ?? '', topology.nodes[segment?.node]?.city ?? '',
      isCrossRegion(receipt) ? '是' : '否', receipt.task_class,
      receipt.effective_efh, receipt.energy_kwh, receipt.electricity_cny, receipt.co2_kg,
      receipt.avoided_vs_grid_kg, receipt.sla_met ? '达成' : '未达成', segment?.pool ?? '',
      pool?.score ?? '', segment?.latency_ms ?? '', segment?.pue ?? '', segment?.green_share ?? '',
      segment?.probability ?? '', segment?.resource_shadow ?? '', segment?.carbon_shadow ?? '',
      receipt.sha256, receipt.selection_reason ?? '',
    ]);
  }
  return '\uFEFF' + rows.map((row) => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
}

export async function postText(base, path, payload, request = fetch) {
  const host = base.replace(/\/$/, '');
  const response = await request(`${host}/api/v1/${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  const text = await response.text();
  if (!response.ok) throw new Error(text || `接口返回 ${response.status}`);
  return text;
}

export function receiptCandidates(receipt, topology) {
  const affinity = topology.affinity[topology.task_classes.indexOf(receipt.task_class)] ?? [];
  return topology.nodes.map((node) => ({
    node: node.id, city: node.city, latency: topology.latency_ms[receipt.source]?.[node.id],
    resource: receipt.resource_shadow?.[node.id], carbon: receipt.carbon_shadow?.[node.id],
    pools: topology.pools.map((pool, i) => ({
      pool, score: affinity[i], feasible: Boolean(receipt.feasible_bits[node.id] & (1 << i)),
    })),
  }));
}

const csvCell = (val) => '"' + String(val ?? '').replaceAll('"', '""') + '"';

export function comparisonCsv(runs, scenario, mode, seed, day) {
  const header = ['scenario', 'source', 'seed', 'strategy', 'scope', 'hour',
    ...METRICS.map((metric) => metric.key)];
  const rows = [header];
  for (const name of STRATEGIES) {
    const replay = runs[name];
    const row = (slot, scope, data) => [
      scenario, mode, seed, name, scope, slot, ...METRICS.map((metric) => data[metric.key]),
    ];
    rows.push(row('', 'whole_replay', replay.kpis));
    replay.hourly.slice(day * 24, (day + 1) * 24).forEach((metrics, i) => rows.push(row(day * 24 + i, 'hour', metrics)));
  }
  return '\uFEFF' + rows.map((row) => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
}

export function comparisonMarkdown(runs, scenario, mode, seed, weights) {
  const lines = [
    '# 苏算绿枢策略对比', '',
    `场景 ${SCENARIOS[scenario]} · 种子 ${seed} · 仿真 ${runs.SuCompute.hourly.length} 小时`,
    mode === 'live' ? '来源：本机仿真接口即时运行。' : '来源：SuCompute v2 固定仿真回放。', '',
  ];
  if (Object.keys(weights).length) lines.push(`权重 ${JSON.stringify(weights)}`, '');
  lines.push('| 策略 | ' + METRICS.map((m) => [m.label, m.unit].filter(Boolean).join(' ')).join(' | ') + ' |');
  lines.push('| ' + Array(7).fill('---').join(' | ') + ' |');
  for (const name of STRATEGIES) lines.push('| ' + [name, ...METRICS.map((metric) => metricValue(runs[name].kpis, metric))].join(' | ') + ' |');
  return lines.join('\n') + '\n';
}

export function createApi(base, request = fetch) {
  const host = base.replace(/\/$/, '');
  return async (path, payload) => {
    try {
      const response = await request(`${host}/api/v1/${path}`, {
        method: payload ? 'POST' : 'GET',
        ...(payload ? { headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) } : {}),
        signal: AbortSignal.timeout(120_000),
      });
      const result = await response.json().catch(() => null);
      if (response.ok && result) return result;
      const detail = typeof result?.detail === 'string' ? result.detail : `接口返回 ${response.status}`;
      throw new Error(detail);
    } catch (error) {
      if (error instanceof TypeError) throw new Error('未连接本地仿真服务。启动赛道后端后重试。');
      throw error;
    }
  };
}
