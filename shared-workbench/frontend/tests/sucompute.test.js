import assert from 'node:assert/strict';
import test from 'node:test';
import {
  COMMAND_PRESETS, SCENARIOS, STRATEGIES, comparisonCsv, comparisonMarkdown, createApi, createReplayStore,
  dailyChart, flightsAt, isCrossRegion, ledgerCsv, metricValue, postText, presentReceipt, receiptCandidates,
  slotLabel, validateReplay,
} from '../src/sucompute/data.js';
import { auditBody } from '../src/sucompute/view.js';

const metrics = {
  utilization: .82, sla: .99, kwh_per_efh: 12001, pue: 1.29, green_share: .72, kgco2_per_efh: 4112,
};
function makeReplay() {
  const matrix = Array.from({length: 48}, () => [1, 2]);
  return {
    kpis: metrics,
    hourly: Array.from({length: 48}, (_, hour) => ({ ...metrics, utilization: hour / 100 })),
    flights: [[0, 0, 1, 3, 108], [24, 1, 0, 2, 209], [24, 0, 1, 8, 212]],
    nodes: { utilization: matrix, pue: matrix, green_share: matrix, health: matrix },
  };
}
const allRuns = () => Object.fromEntries(STRATEGIES.map((strategy) => [strategy, makeReplay()]));

test('loads only topology and index, and caches a selected replay shard', async () => {
  const names = [];
  const scenarioIndex = Object.fromEntries(Object.keys(SCENARIOS).map((key) => [key, `scenario_${key}.json`]));
  const assets = {
    'topology.json': { nodes: [{id: 0}] },
    'scenarios_4x4.json': { version: 2, seed: 313, scenarios: scenarioIndex },
    'scenario_normal_weekday.json': { version: 2, scenario: 'normal_weekday', strategies: allRuns() },
  };
  const store = createReplayStore(new URL('https://fixture.invalid/data/'), async (url) => {
    const name = url.pathname.split('/').at(-1);
    names.push(name);
    return Response.json(assets[name]);
  });
  const { index } = await store.boot();
  assert.equal(names.length, 2);
  const [one, two] = await Promise.all([store.scene(index, 'normal_weekday'), store.scene(index, 'normal_weekday')]);
  assert.deepEqual(one, two);
  assert.equal(names.filter((name) => name.startsWith('scenario_normal')).length, 1);
});

test('retries a failed asset and rejects malformed replay matrices', async () => {
  let calls = 0;
  const store = createReplayStore(new URL('https://fixture.invalid/'), async () => {
    calls++;
    if (calls === 1) return new Response('', {status: 503});
    return Response.json({ receipts: [] });
  });
  await assert.rejects(store.receipts(), /503/);
  assert.deepEqual(await store.receipts(), []);
  const replay = makeReplay();
  replay.nodes.health = [];
  assert.throws(() => validateReplay(replay), /格式/);
});

test('uses the selected day for curves and orders hourly flights by count', () => {
  const runs = allRuns();
  const chart = dailyChart(runs, 1, 'utilization');
  assert.equal(chart.axes.length, 24);
  assert.deepEqual(chart.series[0].values.slice(0, 3), [24, 25, 26]);
  assert.deepEqual(flightsAt(runs.SuCompute, 24).map((flight) => flight[3]), [8, 2]);
  assert.deepEqual(flightsAt(runs.SuCompute, 23), []);
  assert.equal(slotLabel(864), '周四 00:00');
});

test('unpacks compact receipt feasibility without recomputing its hash', () => {
  const spec = { id: 0, city: '南京' };
  const topology = {
    nodes: [spec], affinity: [[.25, .8]], task_classes: ['Inference'],
    latency_ms: [[1]], pools: ['CPU', 'GPU'],
  };
  const result = receiptCandidates({ task_class: 'Inference', source: 0, feasible_bits: [2], sha256: 'original' }, topology);
  assert.deepEqual(result[0].pools, [
    { pool: 'CPU', score: .25, feasible: false }, { pool: 'GPU', score: .8, feasible: true },
  ]);
  assert.equal(result[0].latency, 1);
});

test('exports four same-window strategies from the selected source', () => {
  const runs = allRuns();
  const csv = comparisonCsv(runs, 'normal_weekday', 'fixed', 313, 1);
  const lines = csv.trim().split('\r\n');
  assert.equal(lines.length, 1 + 4 * 25);
  assert.match(lines[2], /"RR-Local","hour","24","0\.24"/);
  const md = comparisonMarkdown(runs, 'normal_weekday', 'live', 313, {carbon: .6});
  assert.match(md, /即时运行/);
  assert.match(md, /carbon.*0\.6/);
  assert.match(md, /SuCompute/);
  assert.equal(metricValue({ utilization: 0 }, { key: 'utilization', scale: 100, digits: 2 }), '0.00');
});

test('ledger csv keeps the voucher hash and quotes reasons', () => {
  const topology = {
    nodes: [{ id: 0, city: '南京' }, { id: 1, city: '上海' }],
    pools: ['CPU', 'Ascend'], task_classes: ['Inference'], affinity: [[.32, .98]], latency_ms: [[1, 10]],
  };
  const receipt = {
    task_id: 7, scenario: 'normal_weekday', strategy: 'SuCompute', seed: 313, source: 0, task_class: 'Inference',
    effective_efh: 1.25, energy_kwh: 10, electricity_cny: 6.5, co2_kg: 3.2, avoided_vs_grid_kg: 2.3, sla_met: true,
    sha256: 'ab'.repeat(32), selection_reason: '因为"影子价格", 选中上海',
    segments: [{ node: 1, pool: 'Ascend', latency_ms: 10, pue: 1.21, green_share: .4, probability: .37, resource_shadow: .02, carbon_shadow: .01 }],
    feasible_bits: [0, 2],
  };
  assert.equal(isCrossRegion(receipt), true);
  const csv = ledgerCsv([receipt], topology);
  assert.match(csv, /凭证SHA256/);
  assert.ok(csv.includes('ab'.repeat(32)));
  assert.match(csv, /"因为""影子价格"", 选中上海"/);
  assert.match(csv, /上海/);
  const full = presentReceipt({
    ...receipt, candidate_affinity: [{ node: 1, scores: [.32, .98], feasible: [false, true], latency_ms: 10 }],
  }, topology);
  assert.equal(full.candidates[0].pools[1].score, .98);
  const drawer = auditBody(receipt, topology);
  assert.match(drawer, /算力当量/);
  assert.match(drawer, /碳减排凭证 SHA-256/);
  assert.ok(drawer.includes(receipt.sha256));
  assert.ok(COMMAND_PRESETS.some((item) => item.text === '迎峰度夏保电模式：碳排权重调至 0.6'));
  assert.ok(COMMAND_PRESETS.some((item) => item.text === '注入南京节点 30% 算力宕机故障'));
});

test('posts ledger text without requiring a JSON body', async () => {
  const text = await postText('/sucompute-api/', 'ledger/csv', { hours: 1 }, async (url, options) => {
    assert.equal(url, '/sucompute-api/api/v1/ledger/csv');
    assert.equal(options.method, 'POST');
    return new Response('任务编号\r\n', { status: 200 });
  });
  assert.match(text, /任务编号/);
});

test('calls the simulator API with JSON and surfaces service errors', async () => {
  const api = createApi('/sucompute-api/', async (url, options) => {
    assert.equal(url, '/sucompute-api/api/v1/simulate');
    assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), { hours: 24 });
    return Response.json({ detail: '不可用' }, {status: 422});
  });
  await assert.rejects(api('simulate', { hours: 24 }), /不可用/);
});
