import assert from 'node:assert/strict';
import test from 'node:test';
import {
  SCENARIOS, STRATEGIES, comparisonCsv, comparisonMarkdown, createApi, createReplayStore,
  dailyChart, flightsAt, metricValue, receiptCandidates, slotLabel, validateReplay,
} from '../src/sucompute/data.js';

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

test('calls the simulator API with JSON and surfaces service errors', async () => {
  const api = createApi('/sucompute-api/', async (url, options) => {
    assert.equal(url, '/sucompute-api/api/v1/simulate');
    assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), { hours: 24 });
    return Response.json({ detail: '不可用' }, {status: 422});
  });
  await assert.rejects(api('simulate', { hours: 24 }), /不可用/);
});
