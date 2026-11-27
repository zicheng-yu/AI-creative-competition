import { BarChart, LineChart, RadarChart } from 'echarts/charts';
import { GridComponent, LegendComponent, RadarComponent, TooltipComponent } from 'echarts/components';
import { init, use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';

use([BarChart, LineChart, RadarChart, GridComponent, LegendComponent, RadarComponent, TooltipComponent, CanvasRenderer]);

export function mountChart(element, chart, dark) {
  const surface = init(element);
  const tone = dark ? '#c5d4de' : '#435967';
  const grid = dark ? '#334858' : '#d9e3ea';
  const colors = dark ? ['#66bfd3', '#ed9b72', '#a4bd8b', '#b6a3e3'] : ['#226e91', '#b65431', '#467962', '#6953a7'];
  const legend = { bottom: 4, textStyle: { color: tone }, itemWidth: 15, itemHeight: 7 };
  const base = {
    color: colors, legend, textStyle: { color: tone },
    animation: !matchMedia('(prefers-reduced-motion: reduce)').matches,
    tooltip: { renderMode: 'richText', confine: true },
  };
  if (chart.kind === 'radar') {
    surface.setOption({
      ...base,
      radar: {
        center: ['50%', '48%'], radius: '58%',
        indicator: chart.axes.map((axis) => ({ name: axis.label, max: axis.maximum })),
        axisName: { color: tone }, axisLine: { lineStyle: { color: grid } },
        splitLine: { lineStyle: { color: grid } }, splitArea: { show: false },
      },
      series: [{
        type: 'radar', symbolSize: 6,
        data: chart.series.map(({ name, values }) => ({ name, value: values, areaStyle: { opacity: 0.13 } })),
      }],
    });
  } else {
    const xs = chart.axes.map((axis) => axis.label);
    surface.setOption({
      ...base,
      grid: { top: 24, left: 50, right: 28, bottom: 60 },
      tooltip: { ...base.tooltip, trigger: 'axis' },
      xAxis: {
        type: 'category', data: xs, boundaryGap: chart.kind === 'bar',
        axisLabel: { color: tone, hideOverlap: true }, axisLine: { lineStyle: { color: grid } },
      },
      yAxis: { type: 'value', axisLabel: { color: tone }, splitLine: { lineStyle: { color: grid, type: 'dashed' } } },
      series: chart.series.map(({ name, values }) => ({
        type: chart.kind, name, data: values, symbolSize: 7,
        lineStyle: { width: 3 },
        barMaxWidth: 45,
      })),
    });
  }
  const observer = new ResizeObserver(() => surface.resize());
  observer.observe(element);
  return () => {
    observer.disconnect();
    surface.dispose();
  };
}
