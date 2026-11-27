import geometry from './delta-geometry.json';

const START = [119.4, 32.35];
const LON_SCALE = Math.cos(32.35 * Math.PI / 180);
const LABELS = [
  ['江苏', 119.4, 34.72], ['安徽', 116.65, 31.68], ['浙江', 119.8, 29.40],
  ['山东', 117.73, 35.30], ['黄海', 122.10, 33.50],
];
const LABEL_OFFSETS = {
  南京: [-13, -19], 镇江: [9, 13], 扬州: [-14, -21], 泰州: [10, -18],
  常州: [-21, 17], 无锡: [-16, 22], 苏州: [13, 11], 南通: [12, -14],
  上海: [13, -9], 安徽芜湖: [-15, 13], 浙江: [12, 7], 连云港: [12, -10],
  盐城: [12, 3], 徐州: [-14, -16], 宿迁: [-13, 12], 淮安: [9, 11],
};

function polygons(item) {
  if (item.type === 'Polygon') return [item.coordinates];
  if (item.type === 'MultiPolygon') return item.coordinates;
  return item.geometries?.flatMap(polygons) ?? [];
}

export function loadColor(load, fault) {
  if (fault) return '#f1a17a';
  if (load >= .68) return '#e3d787';
  if (load >= .36) return '#7bc6a9';
  return '#559bbb';
}

function curveBetween(from, to, cross) {
  const [x, y] = from;
  const [xx, yy] = to;
  const lift = Math.min(Math.hypot(xx - x, yy - y) * .22, cross ? 42 : 27);
  return [x, y, (x + xx) / 2, (y + yy) / 2 - lift, xx, yy];
}

export function createDeltaMap(canvas, layer, topology, onSelect) {
  const context = canvas.getContext('2d');
  const nodes = new Map(topology.nodes.map((node) => [node.id, node]));
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');
  const controls = new Map();
  let width = 1, height = 1, frame = 0, current;

  for (const node of topology.nodes) {
    const button = document.createElement('button');
    button.className = 'node-hit';
    button.type = 'button';
    button.setAttribute('aria-label', `查看${node.city}节点`);
    button.addEventListener('click', () => onSelect(node.id));
    layer.append(button);
    controls.set(node.id, button);
  }

  function project(lon, lat) {
    const scale = Math.min(width / 6.8, height / 5.72);
    return [width * .5 + (lon - START[0]) * scale * LON_SCALE, height * .48 - (lat - START[1]) * scale];
  }

  const background = document.createElement('canvas');
  function renderBase() {
    background.width = canvas.width;
    background.height = canvas.height;
    const ctx = background.getContext('2d');
    ctx.scale(canvas.width / width, canvas.height / height);
    const gradient = ctx.createLinearGradient(0, 0, width, height);
    gradient.addColorStop(0, '#102636');
    gradient.addColorStop(1, '#0d3240');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);
    ctx.lineWidth = 1;
    ctx.strokeStyle = '#97cbcf16';
    for (let lon = 115; lon <= 124; lon++) {
      const x = project(lon, 0)[0];
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let lat = 27; lat <= 37; lat++) {
      const y = project(0, lat)[1];
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
    for (const region of geometry.features) {
      ctx.fillStyle = region.properties.core ? '#244653' : '#193441';
      ctx.strokeStyle = region.properties.core ? '#5b8993' : '#355763';
      ctx.lineWidth = region.properties.core ? 1.15 : .8;
      for (const polygon of polygons(region.geometry)) {
        ctx.beginPath();
        for (const ring of polygon) {
          ring.forEach(([lon, lat], i) => {
            const [x, y] = project(lon, lat);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          ctx.closePath();
        }
        ctx.fill('evenodd');
        ctx.stroke();
      }
    }
    ctx.textAlign = 'center';
    ctx.font = '11px PingFang SC, sans-serif';
    ctx.fillStyle = '#85a5ac';
    for (const [text, lon, lat] of LABELS) {
      if (width < 430 && text !== '黄海') continue;
      ctx.fillText(text, ...project(lon, lat));
    }
  }

  function size() {
    const size = canvas.getBoundingClientRect();
    if (!size.width || !size.height) return;
    width = size.width;
    height = size.height;
    const ratio = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    for (const node of nodes.values()) {
      const [x, y] = project(node.lon, node.lat);
      const button = controls.get(node.id);
      button.style.left = `${x}px`;
      button.style.top = `${y}px`;
    }
    renderBase();
    animate(performance.now());
  }

  function animate(now) {
    cancelAnimationFrame(frame);
    if (width <= 1 || !height) return;
    context.setTransform(canvas.width / width, 0, 0, canvas.height / height, 0, 0);
    context.clearRect(0, 0, width, height);
    context.drawImage(background, 0, 0, width, height);
    if (!current) return;
    const { nodes: values, selected, flights, alarm, playing } = current;
    const motion = playing && !reduce.matches;
    const position = (id) => {
      const node = nodes.get(id);
      return node ? project(node.lon, node.lat) : null;
    };
    for (const [index, flight] of flights.slice(0, 12).entries()) {
      const [, origin, target, count] = flight;
      const from = position(origin), to = position(target);
      if (!from || !to || origin === target) continue;
      const cross = nodes.get(origin).external || nodes.get(target).external;
      const selectedFlight = origin === selected || target === selected;
      const [x, y, m, n, xx, yy] = curveBetween(from, to, cross);
      const tint = cross ? '233,164,116' : '115,214,207';
      context.beginPath();
      context.lineWidth = Math.min(2.4, 1 + Math.sqrt(count) * .22);
      context.strokeStyle = `rgba(${tint},${selectedFlight ? .78 : .34})`;
      context.moveTo(x, y);
      context.quadraticCurveTo(m, n, xx, yy);
      context.stroke();
      const t = motion ? (now / 1420 + index * .109) % 1 : .72;
      const a = 1 - t;
      context.beginPath();
      context.fillStyle = `rgba(${tint},${selectedFlight ? .95 : .66})`;
      context.arc(a * a * x + 2 * a * t * m + t * t * xx, a * a * y + 2 * a * t * n + t * t * yy, selectedFlight ? 2.55 : 1.65, 0, Math.PI * 2);
      context.fill();
    }
    const capital = topology.nodes.find((node) => node.city === '南京');
    if (capital && width >= 450) {
      const [x, y] = position(capital.id);
      const dx = x - 51, dy = y - 36;
      context.lineWidth = .9;
      context.strokeStyle = '#b0d6d1';
      context.setLineDash([3, 3]);
      context.beginPath();
      context.moveTo(dx, dy);
      context.lineTo(x, y);
      context.stroke();
      context.setLineDash([]);
      context.strokeRect(dx - 3.5, dy - 3.5, 7, 7);
      context.textAlign = 'right';
      context.font = '11px PingFang SC, sans-serif';
      context.fillStyle = '#c2dcd9';
      context.fillText('省级调度核心', dx - 8, dy + 4);
    }
    for (const node of nodes.values()) {
      const [x, y] = position(node.id);
      const load = values.utilization?.[node.id] ?? 0;
      const fault = values.health?.[node.id] < .999 || alarm === node.id;
      const fill = loadColor(load, fault);
      const radius = node.id === selected ? 5.3 : 4.15;
      if (fault || node.id === selected) {
        context.beginPath();
        context.lineWidth = 1.1;
        context.strokeStyle = `${fill}99`;
        context.arc(x, y, fault && motion ? radius + 5 + (now % 1100) / 270 : radius + 5, 0, Math.PI * 2);
        context.stroke();
      }
      context.beginPath();
      context.lineWidth = 1.2;
      context.fillStyle = fill;
      context.strokeStyle = '#102532';
      if (node.external) {
        context.rect(x - radius, y - radius, radius * 2, radius * 2);
      } else {
        context.arc(x, y, radius, 0, Math.PI * 2);
      }
      context.fill();
      context.stroke();
      const drawn = width > 455 || [0, 1, 8, 10, 11, 13, 14, 15].includes(node.id) || node.id === selected;
      if (!drawn) continue;
      const [dx, dy] = LABEL_OFFSETS[node.city] ?? [8, -8];
      context.textAlign = dx < 0 ? 'right' : 'left';
      context.font = `${node.id === selected ? 700 : 500} ${width < 430 ? 10 : 11}px PingFang SC, sans-serif`;
      context.lineWidth = 3;
      context.strokeStyle = '#122a38';
      context.strokeText(node.city, x + dx, y + dy);
      context.fillStyle = fault ? '#ffd2ba' : '#e2eff0';
      context.fillText(node.city, x + dx, y + dy);
    }
    if (motion) frame = requestAnimationFrame(animate);
  }

  const observer = new ResizeObserver(size);
  observer.observe(canvas);
  return {
    update(input) {
      current = input;
      for (const [id, control] of controls) control.setAttribute('aria-pressed', String(id === input.selected));
      animate(performance.now());
    },
    stop() {
      cancelAnimationFrame(frame);
      observer.disconnect();
    },
  };
}
