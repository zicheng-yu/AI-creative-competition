import Papa from 'papaparse';

function checkChart(chart) {
  const chartId = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
  if (!chart || typeof chart.id !== 'string' || !chartId.test(chart.id) || chart.id.length > 64
      || typeof chart.title !== 'string' || !chart.title.trim() || chart.title.length > 120
      || typeof chart.unit !== 'string' || chart.unit.length > 32
      || !['line', 'radar', 'bar'].includes(chart.kind)
      || !Array.isArray(chart.axes) || !chart.axes.length || chart.axes.length > 100
      || !Array.isArray(chart.series) || !chart.series.length || chart.series.length > 8) {
    throw new Error('图表缺少编号、标题、类型、坐标或数据系列。');
  }
  const axes = new Set();
  for (const axis of chart.axes) {
    if (!axis || typeof axis.label !== 'string' || !axis.label.trim() || axis.label.length > 80
        || axes.has(axis.label) || (axis.maximum != null && (!Number.isFinite(axis.maximum) || axis.maximum <= 0))) {
      throw new Error(`图表「${chart.title}」的坐标标签或上限有误。`);
    }
    axes.add(axis.label);
  }
  const seriesNames = new Set();
  for (const series of chart.series) {
    if (!series || typeof series.name !== 'string' || !series.name.trim() || series.name.length > 80
        || seriesNames.has(series.name)
        || !Array.isArray(series.values) || series.values.length !== axes.size
        || series.values.some((value) => !Number.isFinite(value))) {
      throw new Error(`图表「${chart.title}」的数据系列和坐标不匹配。`);
    }
    seriesNames.add(series.name);
  }
  if (chart.kind === 'radar' && (chart.axes.length < 3 || chart.axes.some((axis) => axis.maximum == null)
      || chart.series.some((series) => series.values.some((value, index) => value < 0 || value > chart.axes[index].maximum)))) {
    throw new Error(`雷达图「${chart.title}」需要至少三个坐标，数值须在各坐标范围内。`);
  }
}

function csvCharts(text) {
  const parsed = Papa.parse(text, { header: true, skipEmptyLines: 'greedy', transformHeader: (key) => key.trim() });
  const cols = ['chart_id', 'kind', 'title', 'unit', 'category', 'series', 'value'];
  if (parsed.errors.length || !cols.every((col) => parsed.meta.fields?.includes(col))) {
    throw new Error('CSV 表头或行格式有误，请使用契约中的示例。');
  }
  const groups = new Map();
  for (const row of parsed.data) {
    if (!row.value.trim()) throw new Error('CSV 中的数值不能为空。');
    const { chart_id: id, kind, title, unit, category, series, value, maximum } = row;
    if (!groups.has(id)) groups.set(id, { kind, title, unit, axes: new Map(), series: new Map() });
    const group = groups.get(id);
    if (group.kind !== kind || group.title !== title || group.unit !== unit) throw new Error('同一图表的类型、标题和单位应一致。');
    const bound = maximum?.trim() ? Number(maximum) : null;
    if (group.axes.has(category) && group.axes.get(category) !== bound) throw new Error('同一坐标的上限应一致。');
    group.axes.set(category, bound);
    if (!group.series.has(series)) group.series.set(series, new Map());
    const values = group.series.get(series);
    if (values.has(category)) throw new Error('CSV 中存在重复的数据点。');
    values.set(category, Number(value));
  }
  return Array.from(groups, ([id, group]) => ({
    id, kind: group.kind, title: group.title, unit: group.unit,
    axes: Array.from(group.axes, ([label, maximum]) => ({ label, maximum })),
    series: Array.from(group.series, ([name, values]) => ({
      name, values: Array.from(group.axes.keys(), (label) => values.get(label)),
    })),
  }));
}

export async function readCharts(file) {
  const text = (await file.text()).replace(/^\uFEFF/, '');
  let charts;
  try {
    if (/\.csv$/i.test(file.name)) charts = csvCharts(text);
    else {
      const parsed = JSON.parse(text);
      charts = Array.isArray(parsed) ? parsed : parsed?.charts;
    }
  } catch (error) {
    if (error instanceof SyntaxError) throw new Error('JSON 语法有误，请检查文件格式。');
    throw error;
  }
  if (!Array.isArray(charts) || !charts.length || charts.length > 30) throw new Error('文件应包含 1 到 30 张图表。');
  const ids = new Set();
  for (const chart of charts) {
    checkChart(chart);
    if (ids.has(chart.id)) throw new Error(`图表编号「${chart.id}」重复。`);
    ids.add(chart.id);
  }
  return charts.map(({ id, kind, title, unit, axes, series }) => ({
    id, kind, title, unit,
    axes: axes.map(({ label, maximum }) => ({ label, maximum })),
    series: series.map(({ name, values }) => ({ name, values })),
  }));
}
