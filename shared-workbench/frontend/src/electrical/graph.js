import { html } from '../format.js';

export function graphModel(annotation) {
  const instances = new Map(annotation.instances.map((item) => [item.id, item]));
  const nodes = (annotation.netlist?.nodes ?? []).map((node) => instances.get(node.id) ?? node);
  const known = nodes.filter((node) => node.bbox_px);
  const extentX = known.map(({bbox_px: [x, , w]}) => x + w / 2);
  const extentY = known.map(({bbox_px: [, y, , h]}) => y + h / 2);
  const left = extentX.length ? Math.min(...extentX) : 0;
  const top = extentY.length ? Math.min(...extentY) : 0;
  const width = Math.max(1, Math.max(...extentX) - left);
  const height = Math.max(1, Math.max(...extentY) - top);
  const positions = new Map(nodes.map((node, i) => {
    if (!node.bbox_px) return [node.id, [10 + 16 * (i % 6), 92]];
    const [x, y, w, h] = node.bbox_px;
    return [node.id, [10 + 80 * (x + w / 2 - left) / width, 9 + 72 * (y + h / 2 - top) / height]];
  }));
  const edges = (annotation.netlist?.edges ?? []).filter(({source, target}) => positions.has(source) && positions.has(target));
  return { nodes, positions, edges };
}

export function renderGraph(parent, annotation, selected, connections) {
  const {nodes, positions, edges} = graphModel(annotation);
  const related = new Set([...connections.upstream, ...connections.downstream]);
  const incoming = new Set([selected, ...connections.upstream]);
  const outgoing = new Set([selected, ...connections.downstream]);
  parent.innerHTML = `<canvas aria-hidden="true"></canvas>${nodes.map((node) => {
    const [x, y] = positions.get(node.id);
    const state = node.id === selected ? 'picked' : related.has(node.id) ? 'related' : '';
    return `<button class="graph-node ${state}" type="button" style="left:${x}%;top:${y}%" data-graph="${html(node.id)}" aria-label="定位 ${html(node.tag || node.class_code)} 拓扑节点" title="${html(node.specs?.spec || node.class_code)}"><span>${html(node.tag || node.class_code)}</span></button>`;
  }).join('')}`;
  const canvas = parent.querySelector('canvas');
  const rect = parent.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const ratio = Math.min(devicePixelRatio, 2);
  canvas.width = Math.round(rect.width * ratio);
  canvas.height = Math.round(rect.height * ratio);
  const ctx = canvas.getContext('2d');
  ctx.scale(ratio, ratio);
  const point = (id) => {
    const [x, y] = positions.get(id);
    return [rect.width * x / 100, rect.height * y / 100];
  };
  for (const edge of edges) {
    const [sx, sy] = point(edge.source), [tx, ty] = point(edge.target);
    const focused = selected && [incoming, outgoing].some((set) => set.has(edge.source) && set.has(edge.target));
    const color = focused ? '#b75537' : ({ control: '#528eac', power: '#7895a7', branch: '#8a79a3', pe: '#599175' })[edge.kind] ?? '#7895a7';
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = focused ? 1.7 : .85;
    ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(tx, ty); ctx.stroke();
    if (focused) {
      const angle = Math.atan2(ty - sy, tx - sx), x = sx + .66 * (tx - sx), y = sy + .66 * (ty - sy);
      ctx.beginPath(); ctx.moveTo(x, y);
      ctx.lineTo(x - 6 * Math.cos(angle - .5), y - 6 * Math.sin(angle - .5));
      ctx.lineTo(x - 6 * Math.cos(angle + .5), y - 6 * Math.sin(angle + .5)); ctx.fill();
    }
  }
}
