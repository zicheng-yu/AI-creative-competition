'use strict';
// SuCompute 答辩 PPT — derived from the press_newsletter_presentation family (cream page, hairline chrome, red numerals)
const PptxGenJS = require('pptxgenjs');
const pptx = new PptxGenJS();
pptx.defineLayout({ name: 'W', width: 13.333, height: 7.5 });
pptx.layout = 'W';
pptx.author = '盼盼法式小面包';
pptx.title = 'SuCompute 答辩';

const BG = 'FAF8F5', INK = '111111', RED = 'B3121B', GREY = '6B6B6B', LG = 'D6D2CB', PANEL = 'EFEBE5', DARK = '1C1C1C', MID = '9A9A9A';
const CN = 'Microsoft YaHei', NUM = 'Arial', SERIF = 'Georgia', MONO = 'Courier New';
const TOTAL = 17;
const X0 = 0.5, XW = 12.333;

function t(s, text, o) { s.addText(text, Object.assign({ fontFace: CN, fontSize: 12, color: INK, margin: 0, valign: 'top' }, o)); }
function rect(s, x, y, w, h, fill, line) { s.addShape('rect', { x, y, w, h, fill: { color: fill }, line: line ? { color: line, width: 0.75 } : { type: 'none' } }); }
function box(s, x, y, w, h, line, dash) { s.addShape('rect', { x, y, w, h, fill: { color: 'FFFFFF' }, line: { color: line || LG, width: 0.75, dashType: dash || 'solid' } }); }
function hl(s, x, y, w, color, width, dash) { s.addShape('line', { x, y, w, h: 0, line: { color: color || LG, width: width || 0.5, dashType: dash || 'solid' } }); }
function vl(s, x, y, h, color, width, dash) { s.addShape('line', { x, y, w: 0, h, line: { color: color || LG, width: width || 0.5, dashType: dash || 'solid' } }); }
function arrow(s, x, y, w, h, color, dash) { s.addShape('line', { x, y, w, h, line: { color: color || INK, width: 1.25, endArrowType: 'triangle', dashType: dash || 'solid' } }); }

function base(s, n, kicker, title, sub, source) {
  s.background = { color: BG };
  rect(s, X0, 0.36, 0.06, 0.2, RED);
  t(s, 'SUCOMPUTE  ·  ' + kicker, { x: X0 + 0.14, y: 0.33, w: 7, h: 0.26, fontSize: 10, bold: true, color: INK, charSpacing: 2 });
  t(s, 'AI-JIANGSU-Q36   |   ' + String(n).padStart(2, '0') + ' / ' + TOTAL, { x: 8.83, y: 0.33, w: 4.0, h: 0.26, fontSize: 10, color: GREY, align: 'right', fontFace: NUM });
  hl(s, X0, 0.68, XW, INK, 0.75);
  if (title) t(s, title, { x: X0, y: 0.84, w: XW, h: 0.62, fontSize: 25, bold: true, valign: 'middle' });
  if (sub) t(s, sub, { x: X0, y: 1.5, w: XW, h: 0.34, fontSize: 13, color: GREY, valign: 'middle' });
  hl(s, X0, 6.98, XW, LG, 0.5);
  if (source) t(s, source, { x: X0, y: 7.04, w: 10.25, h: 0.28, fontSize: 8.5, color: MID });
  t(s, '盼盼法式小面包', { x: 10.83, y: 7.04, w: 2.0, h: 0.28, fontSize: 8.5, color: MID, align: 'right' });
}

// big-number card
function stat(s, o) {
  const th = o.theme || 'dark';
  const fill = th === 'dark' ? DARK : th === 'red' ? RED : 'FFFFFF';
  const fg = th === 'light' ? INK : 'FFFFFF';
  const numc = th === 'light' ? RED : 'FFFFFF';
  const sub = th === 'light' ? GREY : (th === 'red' ? 'F6D5D7' : 'C9C9C9');
  if (th === 'light') box(s, o.x, o.y, o.w, o.h); else rect(s, o.x, o.y, o.w, o.h, fill);
  const p = o.pad || 0.22;
  if (o.label) t(s, o.label, { x: o.x + p, y: o.y + 0.16, w: o.w - 2 * p, h: 0.3, fontSize: o.labelSize || 12, bold: true, color: fg });
  t(s, [
    { text: o.num, options: { fontFace: NUM, bold: true, fontSize: o.size || 54, color: numc } },
    { text: o.unit ? ' ' + o.unit : '', options: { fontFace: NUM, bold: true, fontSize: o.unitSize || 20, color: numc } },
  ], { x: o.x + p - 0.04, y: o.y + (o.numY || 0.45), w: o.w - 2 * p + 0.1, h: o.numH || 1.0, valign: 'middle' });
  if (o.note) t(s, o.note, { x: o.x + p, y: o.y + o.h - (o.noteH || 0.62), w: o.w - 2 * p, h: (o.noteH || 0.62) - 0.12, fontSize: o.noteSize || 11, color: sub, valign: 'bottom' });
}

// horizontal flat bars
function hbars(s, o) {
  const { x, y, w, labelW, rowH, max, rows } = o;
  const bw = w - labelW - (o.valW || 1.0);
  rows.forEach((r, i) => {
    const yy = y + i * rowH;
    t(s, r.label, { x, y: yy, w: labelW - 0.12, h: rowH * 0.8, fontSize: o.fs || 11, color: r.hi ? RED : INK, bold: !!r.hi, align: 'right', valign: 'middle' });
    const L = Math.max(0.02, bw * r.v / max);
    rect(s, x + labelW, yy + rowH * 0.12, L, rowH * 0.56, r.color || (r.hi ? RED : '3A3A3A'));
    t(s, r.txt, { x: x + labelW + L + 0.08, y: yy, w: (o.valW || 1.0) + bw - L, h: rowH * 0.8, fontSize: o.fs || 11, fontFace: NUM, bold: true, color: r.hi ? RED : INK, valign: 'middle' });
  });
  if (o.ref) { // reference line
    const rx = x + labelW + bw * o.ref.v / max;
    vl(s, rx, y - 0.1, rows.length * rowH + 0.05, RED, 1, 'dash');
    t(s, o.ref.label, { x: rx - 0.9, y: y + rows.length * rowH - 0.02, w: 1.8, h: 0.24, fontSize: 9.5, color: RED, align: 'center' });
  }
}

// grouped vertical bars
function vbars(s, o) {
  const { x, y, w, h, max, cats, series } = o;
  const baseY = y + h;
  hl(s, x, baseY, w, INK, 0.75);
  const gw = w / cats.length;
  const n = series.length;
  const bw = Math.min(o.bw || 0.42, (gw * 0.78) / n);
  cats.forEach((c, i) => {
    const gx = x + i * gw + (gw - bw * n - 0.04 * (n - 1)) / 2;
    series.forEach((se, j) => {
      const v = se.values[i];
      const bh = h * v / max;
      const bx = gx + j * (bw + 0.04);
      rect(s, bx, baseY - bh, bw, bh, se.colors ? se.colors[i] : se.color);
      t(s, se.fmt ? se.fmt(v) : String(v), { x: bx - 0.25, y: baseY - bh - 0.26, w: bw + 0.5, h: 0.24, fontSize: o.vfs || 10, fontFace: NUM, bold: true, align: 'center', color: (se.colors ? se.colors[i] : se.color) === RED ? RED : INK });
    });
    t(s, c, { x: x + i * gw, y: baseY + 0.05, w: gw, h: 0.3, fontSize: o.cfs || 10.5, align: 'center', color: INK });
  });
}

function legend(s, x, y, items) {
  let xx = x;
  items.forEach(([c, label, w]) => { rect(s, xx, y + 0.06, 0.16, 0.16, c); t(s, label, { x: xx + 0.22, y, w: w || 1.4, h: 0.28, fontSize: 10, color: GREY, valign: 'middle' }); xx += 0.22 + (w || 1.4); });
}

function table(s, rows, o) {
  const fs = o.fs || 10.5;
  const data = rows.map((r, ri) => r.map((c, ci) => {
    const head = ri === 0;
    const hi = o.hiRow === ri;
    const opt = {
      fontFace: (ci > 0 && !head && o.numCols !== false) ? NUM : CN, fontSize: fs, color: head || hi ? 'FFFFFF' : INK,
      bold: head || hi || (ci === 0 && o.boldFirst !== false), align: ci === 0 ? 'left' : (o.align || 'center'), valign: 'middle',
      fill: { color: head ? DARK : hi ? RED : (ri % 2 === 0 ? 'F4F1EC' : 'FFFFFF') }, margin: [0, 0.06, 0, 0.08],
    };
    if (typeof c === 'object') return { text: c.text, options: Object.assign(opt, c.options || {}) };
    return { text: String(c), options: opt };
  }));
  s.addTable(data, { x: o.x, y: o.y, w: o.w, colW: o.colW, rowH: o.rowH || 0.3, border: { type: 'solid', pt: 0.5, color: LG } });
}

/* ================================================================= slides */

// 1 cover
(function () {
  const s = pptx.addSlide();
  s.background = { color: BG };
  rect(s, X0, 0.5, 0.06, 0.2, RED);
  t(s, '首届江苏省“人工智能+”创新应用大赛  ·  “三苏”创新应用赛道', { x: X0 + 0.16, y: 0.47, w: 7.6, h: 0.28, fontSize: 11, bold: true, charSpacing: 1 });
  hl(s, X0, 0.88, 7.7, INK, 0.75);
  t(s, '赛题 AI-JIANGSU-Q36  异构算力智能调度与能效优化', { x: X0, y: 1.12, w: 7.6, h: 0.32, fontSize: 13, color: GREY });
  t(s, 'SuCompute', { x: X0 - 0.06, y: 1.6, w: 7.7, h: 1.5, fontSize: 96, bold: true, fontFace: NUM, color: INK, valign: 'middle' });
  rect(s, X0, 3.2, 1.2, 0.09, RED);
  t(s, 'Heterogeneous compute, orchestrated for efficiency', { x: X0, y: 3.45, w: 7.6, h: 0.42, fontSize: 18, italic: true, fontFace: SERIF, color: GREY_or() });
  t(s, '异构算力的任务编排与能效', { x: X0, y: 3.95, w: 7.6, h: 0.62, fontSize: 32, bold: true });
  const info = [['团队', '盼盼法式小面包'], ['组别', '创新组  ·  报名编号 REG-2026-000524'], ['命题单位', '江苏省数据集团有限公司'], ['日期', '2026 年 11 月']];
  info.forEach((r, i) => {
    const yy = 5.0 + i * 0.42;
    hl(s, X0, yy, 7.2, LG, 0.5);
    t(s, r[0], { x: X0, y: yy + 0.07, w: 1.2, h: 0.3, fontSize: 11, color: RED, bold: true });
    t(s, r[1], { x: X0 + 1.3, y: yy + 0.07, w: 5.9, h: 0.3, fontSize: 12.5, bold: i === 0 });
  });
  hl(s, X0, 6.68, 7.2, LG, 0.5);
  // agenda panel
  rect(s, 8.55, 0, 4.783, 7.5, DARK);
  t(s, 'CONTENTS', { x: 9.05, y: 0.62, w: 3.8, h: 0.3, fontSize: 11, bold: true, color: 'C9C9C9', charSpacing: 4, fontFace: NUM });
  t(s, '目录', { x: 9.05, y: 0.95, w: 3.8, h: 0.55, fontSize: 26, bold: true, color: 'FFFFFF' });
  const ag = [['01', '主结果', '一个合成周、三条主结果', 'P2'], ['02', '背景与痛点', '省平台 1+13 与四件难事', 'P3'], ['03', '技术路线', '预报 · 整数规划 · 可行域打分 · 凭证', 'P4–9'], ['04', '仿真评测', '四场景 × 六策略 × 六维指标', 'P10–13'], ['05', '落地部署', '旁路边车与分工', 'P14–15'], ['06', '效益与路线', '电费推算与影子运行', 'P16–17']];
  ag.forEach((a, i) => {
    const yy = 1.85 + i * 0.78;
    t(s, a[0], { x: 9.05, y: yy, w: 0.8, h: 0.5, fontSize: 26, bold: true, color: 'E0313B', fontFace: NUM });
    t(s, a[1], { x: 9.95, y: yy + 0.02, w: 2.2, h: 0.32, fontSize: 15, bold: true, color: 'FFFFFF' });
    t(s, a[3], { x: 11.9, y: yy + 0.05, w: 0.95, h: 0.28, fontSize: 10, color: 'A8A8A8', align: 'right', fontFace: NUM });
    t(s, a[2], { x: 9.95, y: yy + 0.36, w: 2.9, h: 0.26, fontSize: 10, color: 'B5B5B5' });
    hl(s, 9.05, yy + 0.7, 3.8, '444444', 0.5);
  });
  rect(s, 8.55, 6.68, 4.783, 0.82, RED);
  t(s, '种子 313  ·  四场景各 168 小时  ·  6 策略 × 6 维指标', { x: 9.05, y: 6.86, w: 4.0, h: 0.44, fontSize: 11.5, bold: true, color: 'FFFFFF', valign: 'middle' });
})();
function GREY_or() { return '4A4A4A'; }

// 2 main results
(function () {
  const s = pptx.addSlide();
  base(s, 2, '01 主结果', '同一合成周三条主结果：利用率 80.01%，服务等级 99.83%，能耗降 21.23%',
    '种子 313 · 常规工作日 / 绿电大发 / 尖峰保电 / 故障压测 各 168 小时等权 · 对照轮询就近、最短队列、成本优先三条经典基线',
    '来源：计划书 摘要、表 1；佐证材料 表 1、表 2。有效在线利用率的分母含 15 分钟保活；服务等级分母为到达任务数，拒单计入违约。');
  const W3 = 3.95, G = 0.24, Y = 2.05;
  stat(s, { x: X0, y: Y, w: W3, h: 2.55, theme: 'dark', label: '有效在线利用率', num: '80.01', unit: '%', size: 66, unitSize: 26, numY: 0.55, numH: 1.15, note: '轮询就近 62.72% → 相对提升 +27.57%\n高于脚本下限「有效在线利用率 ≥ 78%」' });
  stat(s, { x: X0 + W3 + G, y: Y, w: W3, h: 2.55, theme: 'red', label: '服务等级（SLA）', num: '99.83', unit: '%', size: 66, unitSize: 26, numY: 0.55, numH: 1.15, note: '轮询就近 95.72% → +4.12 个百分点\n高峰时段（09–11、17–19 时）99.80%' });
  stat(s, { x: X0 + 2 * (W3 + G), y: Y, w: W3, h: 2.55, theme: 'dark', label: '单位能耗 vs 轮询就近', num: '−21.23', unit: '%', size: 66, unitSize: 26, numY: 0.55, numH: 1.15, note: '13,945.7 vs 17,705.0 kWh/EF·h\n高于脚本下限「降低 12%～18%」' });
  const Y2 = 4.82, H2 = 1.95;
  const sec = [
    ['加权 PUE', '1.296', '', '轮询就近 1.376，绝对值降低 0.080', 1.296, 1.376, 1.5, '1.296', '1.376'],
    ['绿电占比', '35.95', '%', '轮询就近 25.26%，相对提升 +42.31%', 35.95, 25.26, 40, '35.95%', '25.26%'],
    ['碳强度', '4,911.9', 'kgCO₂/EF·h', '轮询就近 7,277.5，相对降低 32.51%', 4911.9, 7277.5, 8000, '4,911.9', '7,277.5'],
  ];
  sec.forEach((c, i) => {
    const x = X0 + i * (W3 + G);
    box(s, x, Y2, W3, H2);
    t(s, c[0], { x: x + 0.22, y: Y2 + 0.14, w: 2, h: 0.28, fontSize: 12, bold: true });
    t(s, [{ text: c[1], options: { fontFace: NUM, bold: true, fontSize: 34, color: RED } }, { text: c[2] ? ' ' + c[2] : '', options: { fontFace: NUM, bold: true, fontSize: 13, color: RED } }], { x: x + 0.2, y: Y2 + 0.42, w: 3.6, h: 0.6, valign: 'middle' });
    // mini compare bars
    const bw = W3 - 0.44 - 1.75;
    [['SuCompute', c[4], RED, c[7]], ['轮询就近', c[5], '8C8C8C', c[8]]].forEach((b, j) => {
      const yy = Y2 + 1.1 + j * 0.3;
      t(s, b[0], { x: x + 0.22, y: yy, w: 0.95, h: 0.24, fontSize: 9.5, color: GREY, valign: 'middle', fontFace: j === 0 ? NUM : CN });
      rect(s, x + 1.2, yy + 0.04, bw * b[1] / c[6], 0.16, b[2]);
      t(s, b[3], { x: x + 1.25 + bw * b[1] / c[6], y: yy, w: 0.9, h: 0.24, fontSize: 9.5, fontFace: NUM, bold: true, valign: 'middle' });
    });
    t(s, c[3], { x: x + 0.22, y: Y2 + 1.66, w: W3 - 0.44, h: 0.24, fontSize: 10, color: GREY });
  });
})();

// 3 background & pain points
(function () {
  const s = pptx.addSlide();
  base(s, 3, '02 背景与痛点', '省平台已是“1+13”格局，调度台上仍有四件事要同时处理', null,
    '来源：赛题 AI-JIANGSU-Q36 原文（313 座、271.8 EFlops、1+13、沪浙皖互联）；计划书 §1；对应模块见计划书 §3、§9。');
  // left: structure
  const LX = X0, LW = 5.3, Y = 1.75;
  t(s, '江苏省一体化算力监测调度平台', { x: LX, y: Y, w: LW, h: 0.3, fontSize: 12.5, bold: true });
  rect(s, LX, Y + 0.4, 3.9, 0.48, RED);
  t(s, '省级调度核心', { x: LX, y: Y + 0.4, w: 3.9, h: 0.48, fontSize: 14, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle' });
  const cities = ['南京', '无锡', '徐州', '常州', '苏州', '南通', '连云港', '淮安', '盐城', '扬州', '镇江', '泰州', '宿迁'];
  const cw = 0.72, ch = 0.4, gx = 0.075;
  cities.forEach((c, i) => {
    const col = i % 5, row = Math.floor(i / 5);
    const x = LX + col * (cw + gx), y = Y + 1.08 + row * (ch + 0.08);
    rect(s, x, y, cw, ch, DARK);
    t(s, c, { x, y, w: cw, h: ch, fontSize: 10.5, color: 'FFFFFF', align: 'center', valign: 'middle', bold: true });
  });
  vl(s, LX + 1.95, Y + 0.88, 0.2, RED, 1);
  t(s, '13 个市级节点 · 地市子门户', { x: LX + 2.45, y: Y + 2.05, w: 1.75, h: 0.42, fontSize: 9.5, color: GREY, valign: 'middle' });
  // external
  const ex = LX + 4.25;
  t(s, '长三角互联', { x: ex, y: Y + 0.45, w: 1.05, h: 0.3, fontSize: 9.5, color: RED, bold: true, align: 'center' });
  ['上海', '浙江', '安徽'].forEach((c, i) => {
    const y = Y + 0.85 + i * 0.55;
    s.addShape('rect', { x: ex, y, w: 1.05, h: 0.42, fill: { color: 'FFFFFF' }, line: { color: RED, width: 1, dashType: 'dash' } });
    t(s, c, { x: ex, y, w: 1.05, h: 0.42, fontSize: 11, bold: true, color: RED, align: 'center', valign: 'middle' });
  });
  arrow(s, LX + 3.92, Y + 0.64, 0.3, 0, RED, 'dash');
  // stats
  const sy = Y + 2.75;
  stat(s, { x: LX, y: sy, w: 2.55, h: 1.95, theme: 'dark', label: '纳管在用数据中心', num: '313', unit: '座', size: 50, unitSize: 18, numY: 0.45, numH: 0.85, note: '赛题原文口径', noteH: 0.45 });
  stat(s, { x: LX + 2.75, y: sy, w: 2.55, h: 1.95, theme: 'red', label: '总算力规模', num: '271.8', unit: 'EFlops', size: 40, unitSize: 13, numY: 0.45, numH: 0.85, note: '作为中国算力网江苏分平台，与国家平台数据贯通', noteH: 0.55, noteSize: 9.5 });
  // right: 4 pains
  const RX = 6.15, RW = 6.68, cw2 = (RW - 0.2) / 2, chh = 2.42;
  const pains = [
    ['异构口径不一', '通算、智算、超算并存，国产与进口芯片混合，任务与资源匹配主要靠人工经验。', '6 类芯片池统一进入打分：等效效率、是否国产、池占用作为特征；国产有效份额设 30% 下限'],
    ['训推错配', '训练、微调、推理特征差异大，闲时空转与高峰排队同时存在。', '24 期整数规划把可推迟的训练、微调挪到绿电或低价时段；推理受时延圈约束'],
    ['绿电未进决策', 'PUE、电量、绿电与算力产出缺少统一在线度量，难以在调度层落地。', '目标函数同含电费与碳；PUE 超出、绿电比例进入打分；凭证逐任务记电量与碳'],
    ['跨域 SLA 与故障', '长三角多主体的计费、SLA 保障与故障切换缺少可复算的决策支撑。', '故障编排最长 0.0629 秒；四句中文指令在同一输入上重算；凭证带校验和'],
  ];
  pains.forEach((p, i) => {
    const x = RX + (i % 2) * (cw2 + 0.2), y = Y + Math.floor(i / 2) * (chh + 0.2);
    box(s, x, y, cw2, chh);
    t(s, '0' + (i + 1), { x: x + 0.2, y: y + 0.14, w: 0.6, h: 0.45, fontSize: 24, bold: true, color: RED, fontFace: NUM });
    t(s, p[0], { x: x + 0.85, y: y + 0.18, w: cw2 - 1.0, h: 0.38, fontSize: 15, bold: true, valign: 'middle' });
    t(s, p[1], { x: x + 0.2, y: y + 0.66, w: cw2 - 0.4, h: 0.68, fontSize: 11, color: GREY });
    rect(s, x + 0.2, y + 1.38, cw2 - 0.4, 0.9, PANEL);
    t(s, [{ text: 'SuCompute  ', options: { fontFace: NUM, bold: true, color: RED, fontSize: 10.5 } }, { text: p[2], options: { fontSize: 10.5 } }], { x: x + 0.3, y: y + 1.43, w: cw2 - 0.6, h: 0.8, valign: 'middle' });
  });
})();

// 4 architecture
(function () {
  const s = pptx.addSlide();
  base(s, 4, '03 技术路线', '可断网复跑的四层策略引擎，外加本地边车', null,
    '来源：计划书 §2 图 1、§3、§9。实线为五分钟主链；虚线框为旁路（小时级仿真单独成表）。');
  const Y = 1.75, LW = 1.0, AX = X0, AW = 8.45, rowH = 1.12, g = 0.12;
  const layers = [
    ['交互', [['十三市回放', '加沪浙皖'], ['中文指令', '四句固定操作'], ['边车建议', '与凭证'], ['调度说明', '模板生成']], false],
    ['服务', [['滚动配额', '每小时滚动 24 期'], ['可行域打分', '每 5 分钟槽位'], ['任务凭证', '电量 · 碳 · 校验和']], false],
    ['算法', [['24 小时预报', '1,706 参数'], ['24 期整数规划', '对偶 + 整数求解'], ['约束策略网络', '1,466 参数']], true],
    ['数据', [['16 节点', '6 类芯片池 · 5 类任务'], ['合成周', '种子 313'], ['电价与绿电', '分时 · 分省'], ['小时级仿真', '单独成表', 'dash']], false],
  ];
  layers.forEach((L, i) => {
    const y = Y + i * (rowH + g);
    rect(s, AX, y, LW, rowH, i === 2 ? RED : DARK);
    t(s, L[0], { x: AX, y, w: LW, h: rowH, fontSize: 17, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle' });
    const n = L[1].length, bx0 = AX + LW + 0.15, bw = (AW - LW - 0.15 - 0.12 * (n - 1)) / n;
    L[1].forEach((b, j) => {
      const x = bx0 + j * (bw + 0.12);
      if (b[2] === 'dash') s.addShape('rect', { x, y, w: bw, h: rowH, fill: { color: BG }, line: { color: MID, width: 1, dashType: 'dash' } });
      else box(s, x, y, bw, rowH, L[2] ? RED : LG);
      t(s, b[0], { x: x + 0.1, y: y + 0.2, w: bw - 0.2, h: 0.38, fontSize: 14, bold: true, align: 'center', color: L[2] ? RED : INK });
      t(s, b[1], { x: x + 0.1, y: y + 0.6, w: bw - 0.2, h: 0.32, fontSize: 11, color: GREY, align: 'center', fontFace: /\d/.test(b[1]) ? CN : CN });
    });
  });
  // right pipeline
  const PX = 9.2, PW = 3.63;
  rect(s, PX, Y, PW, 4.84, DARK);
  t(s, '一个调度周期', { x: PX + 0.25, y: Y + 0.18, w: PW - 0.5, h: 0.35, fontSize: 14, bold: true, color: 'FFFFFF' });
  hl(s, PX + 0.25, Y + 0.6, PW - 0.5, '555555', 0.5);
  const steps = [
    ['预报', '16 节点未来 24 小时的到达与绿电比例'],
    ['配额', '整数规划在电费、碳、网络、利用率、拒单间取配额'],
    ['打分', '只在容量、时延、份额都允许的节点上取最高分'],
    ['编排', '提交平台现有队列；故障时按剩余容量改派'],
    ['凭证', '有效算力时、分摊电量、碳排、校验和同记一条'],
  ];
  steps.forEach((st, i) => {
    const y = Y + 0.75 + i * 0.8;
    t(s, String(i + 1), { x: PX + 0.25, y, w: 0.4, h: 0.4, fontSize: 22, bold: true, color: 'E0313B', fontFace: NUM });
    t(s, st[0], { x: PX + 0.7, y: y + 0.02, w: 2.6, h: 0.28, fontSize: 12.5, bold: true, color: 'FFFFFF' });
    t(s, st[1], { x: PX + 0.7, y: y + 0.31, w: PW - 0.95, h: 0.44, fontSize: 9.5, color: 'C9C9C9' });
  });
})();

// 5 two sandboxes
(function () {
  const s = pptx.addSlide();
  base(s, 5, '03 技术路线', '两套沙盘各自比策略：五分钟引擎出主结果，小时级仿真单独成表', null,
    '来源：计划书 §2；佐证材料 §1、§4 表 5、§6 表 8。两套功率系数不同，百分比只在各自表内比较。');
  const Y = 1.72;
  const rows = [
    ['参数', '五分钟引擎（主结果）', '小时级仿真（旁路）'],
    ['步长', '5 分钟', '1 小时'],
    ['功率系数', '峰值 10,000 kW/EF · 空闲 0.32 · 保活 15 min', '1,000 kW/EFlops'],
    ['碳因子', '0.55 kgCO₂/kWh（演示值）', '分省年平均：苏 0.5978 · 沪 0.5849 · 浙 0.5153 · 皖 0.6782'],
    ['全网算力', '335.8 EFlops（含沪 26 · 浙 20 · 芜湖 18）', '271.8 EFlops 按 13 市生产总值分配，三枢纽各 12'],
    ['对比策略', '轮询就近 · 最短队列 · 成本优先 · SuCompute + 两项消融', '随机放置 · 最短队列'],
    ['设计时延', '城域 1 ms · 省内 5 ms · 长三角 10 ms', '—'],
    ['预报接口', '24 小时预报器（1,706 参数）', '等于生成器给出的剩余到达'],
    ['绿电与电费', '绿电抵扣碳排，电费仍按用电量计', '同左'],
  ];
  table(s, rows, { x: X0, y: Y, w: 7.55, colW: [1.15, 3.2, 3.2], rowH: 0.555, fs: 10.5, numCols: false, align: 'left' });
  // capacity stacked bar
  const CX = 8.4, CW = 4.43;
  t(s, '五分钟引擎装机设定（EFlops）', { x: CX, y: Y, w: CW, h: 0.3, fontSize: 12.5, bold: true });
  const parts = [['江苏 13 市', 271.8, DARK], ['上海', 26, RED], ['浙江', 20, 'D9585F'], ['芜湖', 18, 'E9A0A4']];
  let xx = CX; const total = 335.8;
  parts.forEach(p => {
    const w = CW * p[1] / total;
    rect(s, xx, Y + 0.42, w, 0.5, p[2]);
    xx += w;
  });
  t(s, '271.8', { x: CX + 0.1, y: Y + 0.42, w: 1.5, h: 0.5, fontSize: 14, bold: true, color: 'FFFFFF', fontFace: NUM, valign: 'middle' });
  t(s, '江苏 13 市 271.8 · 上海 26 · 浙江 20 · 芜湖 18 = 335.8', { x: CX, y: Y + 0.98, w: CW, h: 0.26, fontSize: 10, color: GREY });
  // hourly completion chart
  t(s, '小时级仿真：送达比例（完成比）', { x: CX, y: Y + 1.42, w: CW, h: 0.3, fontSize: 12.5, bold: true });
  legend(s, CX, Y + 1.74, [[MID, '随机放置', 1.2], [DARK, '最短队列', 1.2]]);
  vbars(s, { x: CX, y: Y + 2.35, w: CW, h: 2.2, max: 1.0, cats: ['常规工作日', '绿电大发', '尖峰保电', '节点故障'], bw: 0.38, vfs: 9.5,
    series: [{ color: MID, values: [0.8109, 0.8109, 0.6874, 0.8049], fmt: v => v.toFixed(2) }, { color: DARK, values: [0.9404, 0.9404, 0.8043, 0.9337], fmt: v => v.toFixed(2) }] });
  t(s, '小时级只比随机放置与最短队列，不看电价和绿电', { x: CX, y: Y + 4.92, w: CW, h: 0.26, fontSize: 9.5, color: GREY });
})();

// 6 forecast
(function () {
  const s = pptx.addSlide();
  base(s, 6, '03 技术路线 · 预报', '先看见未来 24 小时：验证集到达误差 2.09 作业/小时，绿电比例误差 0.020', null,
    '来源：计划书 §3.1；佐证材料 §5、表 7。训练种子 41–43，验证种子 72，评测周种子 313 不在误差表中。');
  const Y = 1.8;
  // timeline
  const TX = X0, TW = 8.0;
  t(s, '输入 → 模型 → 输出（16 节点 × 到达 / 绿电比例）', { x: TX, y: Y, w: TW, h: 0.3, fontSize: 12.5, bold: true });
  const ty = Y + 0.55;
  rect(s, TX, ty, 2.4, 0.55, 'CFCAC2');
  t(s, '可见历史 48 h', { x: TX, y: ty, w: 2.4, h: 0.55, fontSize: 11, bold: true, align: 'center', valign: 'middle' });
  rect(s, TX + 1.2, ty + 0.62, 1.2, 0.08, DARK);
  t(s, '其中最近 24 h 作输入', { x: TX, y: ty + 0.74, w: 2.4, h: 0.26, fontSize: 9.5, color: GREY, align: 'right' });
  vl(s, TX + 2.5, ty - 0.15, 1.2, RED, 1.25, 'dash');
  t(s, '切点', { x: TX + 2.2, y: ty + 1.07, w: 0.6, h: 0.24, fontSize: 9.5, color: RED, align: 'center' });
  rect(s, TX + 2.65, ty - 0.08, 2.9, 0.71, DARK);
  t(s, [{ text: '季节残差时间卷积', options: { bold: true, fontSize: 12, color: 'FFFFFF', breakLine: true } }, { text: '3 层 1D 卷积 · 核宽 5 / 3（扩张 2）/ 1', options: { fontSize: 9.5, color: 'D0D0D0' } }], { x: TX + 2.75, y: ty - 0.06, w: 2.75, h: 0.67, align: 'center', valign: 'middle' });
  arrow(s, TX + 5.58, ty + 0.28, 0.32, 0, INK);
  rect(s, TX + 5.95, ty, 2.05, 0.55, RED);
  t(s, '预报未来 24 h', { x: TX + 5.95, y: ty, w: 2.05, h: 0.55, fontSize: 11, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle' });
  t(s, '输出形状 (24, 16, 2)', { x: TX + 5.95, y: ty + 0.62, w: 2.05, h: 0.26, fontSize: 9.5, color: GREY, align: 'center', fontFace: CN });
  // facts row
  const fy = Y + 2.05;
  const facts = [['1,706', '参数'], ['24 / 48 h', '残差接在滞后均值上'], ['18', '训练轮次'], ['41–43 / 72', '训练 / 验证种子']];
  facts.forEach((f, i) => {
    const x = TX + i * 2.03;
    hl(s, x, fy, 1.85, INK, 0.75);
    t(s, f[0], { x, y: fy + 0.08, w: 1.9, h: 0.45, fontSize: 22, bold: true, fontFace: NUM, color: i === 0 ? RED : INK });
    t(s, f[1], { x, y: fy + 0.55, w: 1.9, h: 0.26, fontSize: 10, color: GREY });
  });
  // table 7
  const rows = [['划分', '变量', '平均绝对误差', '百分比误差', '非零样本'],
    ['训练', '到达（作业/小时）', '2.042', '43.71%', '137,010'], ['训练', '绿电比例', '0.0198', '12.43%', '152,064'],
    ['验证', '到达（作业/小时）', '2.086', '43.96%', '45,179'], ['验证', '绿电比例', '0.0204', '12.54%', '50,688']];
  table(s, rows, { x: TX, y: Y + 3.08, w: TW, colW: [1.0, 2.2, 1.6, 1.6, 1.6], rowH: 0.36, fs: 10.5 });
  // right cards
  const RX = 8.95, RW = 3.88;
  stat(s, { x: RX, y: Y, w: RW, h: 2.42, theme: 'dark', label: '验证集 · 到达 MAE', num: '2.09', unit: '作业/小时', size: 60, unitSize: 15, numY: 0.5, numH: 1.0, note: '精细值 2.086；非零样本 45,179' });
  stat(s, { x: RX, y: Y + 2.62, w: RW, h: 2.42, theme: 'red', label: '验证集 · 绿电比例 MAE', num: '0.020', unit: '', size: 60, numY: 0.5, numH: 1.0, note: '精细值 0.0204；非零样本 50,688' });
})();

// 7 MILP
(function () {
  const s = pptx.addSlide();
  base(s, 7, '03 技术路线 · 滚动配额', '整数规划每小时滚动 24 期：国产有效份额下限 30%，实测 52.19%', null,
    '来源：计划书 §3.2、§9；佐证材料 表 1（国产份额为四场景等权实际份额）。');
  const Y = 1.8, LX = X0, LW = 6.3;
  t(s, '同一目标函数里的五项', { x: LX, y: Y, w: LW, h: 0.3, fontSize: 12.5, bold: true });
  const terms = ['电费', '碳排', '网络开销', '利用率', '拒单'];
  t(s, 'min', { x: LX, y: Y + 0.45, w: 0.6, h: 0.7, fontSize: 20, italic: true, fontFace: SERIF, valign: 'middle' });
  terms.forEach((tm, i) => {
    const x = LX + 0.65 + i * 1.13;
    rect(s, x, Y + 0.45, 1.0, 0.7, i < 2 ? RED : DARK);
    t(s, tm, { x, y: Y + 0.45, w: 1.0, h: 0.7, fontSize: 12.5, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle' });
    if (i < 4) t(s, '+', { x: x + 1.0, y: Y + 0.45, w: 0.13, h: 0.7, fontSize: 14, bold: true, align: 'center', valign: 'middle' });
  });
  // solve steps
  const sy = Y + 1.5;
  t(s, '求解与约束', { x: LX, y: sy, w: LW, h: 0.3, fontSize: 12.5, bold: true });
  const st = [
    ['01', '先松弛，后取整', '取线性松弛的对偶信息（影子价格），再解整数规划'],
    ['02', '训练、微调可后移', '批量预训练与微调把开工推迟到绿电或低价时段'],
    ['03', '推理守时延圈', '江苏城市之间设计时延 5 ms，跨到沪浙皖 10 ms'],
    ['04', '国产份额兜底', '国产芯片上的有效工作量不低于 30%'],
  ];
  st.forEach((r, i) => {
    const y = sy + 0.4 + i * 0.68;
    hl(s, LX, y, LW, LG, 0.5);
    t(s, r[0], { x: LX, y: y + 0.1, w: 0.6, h: 0.45, fontSize: 20, bold: true, color: RED, fontFace: NUM });
    t(s, r[1], { x: LX + 0.65, y: y + 0.1, w: 1.9, h: 0.45, fontSize: 12.5, bold: true, valign: 'middle' });
    t(s, r[2], { x: LX + 2.6, y: y + 0.1, w: LW - 2.6, h: 0.45, fontSize: 11, color: GREY, valign: 'middle' });
  });
  hl(s, LX, sy + 0.4 + 4 * 0.68, LW, LG, 0.5);
  // right chart
  const RX = 7.25, RW = 5.58;
  rect(s, RX, Y, RW, 5.0, 'FFFFFF', LG);
  t(s, '国产芯片有效份额（四场景等权）', { x: RX + 0.25, y: Y + 0.18, w: RW - 0.5, h: 0.3, fontSize: 12.5, bold: true });
  t(s, '六条策略均高于 30% 下限；SuCompute 52.19%，不是压在门槛上的结果', { x: RX + 0.25, y: Y + 0.5, w: RW - 0.5, h: 0.28, fontSize: 10, color: GREY });
  hbars(s, { x: RX + 0.15, y: Y + 1.05, w: RW - 0.3, labelW: 1.25, rowH: 0.56, max: 60, valW: 0.75, fs: 11, ref: { v: 30, label: '下限 30%' },
    rows: [['轮询就近', 56.30], ['最短队列', 54.79], ['成本优先', 56.93], ['SuCompute', 52.19, 1], ['仅整数规划', 52.20], ['仅约束策略', 51.83]].map(r => ({ label: r[0], v: r[1], txt: r[1].toFixed(2) + '%', hi: !!r[2], color: r[2] ? RED : '8C8C8C' })) });
})();

// 8 policy scorer
(function () {
  const s = pptx.addSlide();
  base(s, 8, '03 技术路线 · 可行域打分', '当前槽位只在可行节点上打分：1,466 参数打分器取最高分', null,
    '来源：计划书 §3.3、§9；佐证材料 §5（两层双曲正切打分器，输入 15 维，部署前加偏置和可行性掩码）。');
  const Y = 1.8;
  // stat row
  const cards = [['1,466', '', '策略网络参数', 'dark'], ['15', '维', '输入特征', 'light'], ['0.5', '%', '采样违约率目标', 'red'], ['160', '次', '训练日志更新', 'light']];
  cards.forEach((c, i) => stat(s, { x: X0 + i * 3.14, y: Y, w: 2.95, h: 1.55, theme: c[3], label: c[2], num: c[0], unit: c[1], size: 44, unitSize: 16, numY: 0.5, numH: 0.9 }));
  // flow
  const fy = Y + 1.85;
  t(s, '打分流程', { x: X0, y: fy, w: 4, h: 0.3, fontSize: 12.5, bold: true });
  const flow = [['候选节点', '16 节点 · 6 类芯片池', DARK], ['可行性掩码', '容量 · 时延 · 份额不允许的置为不可选', RED], ['两层 tanh 打分', '15 维特征 + 偏置', DARK], ['取最高分', '提交编排并写凭证', RED]];
  const fw = 2.72;
  flow.forEach((f, i) => {
    const x = X0 + i * (fw + 0.48);
    rect(s, x, fy + 0.4, fw, 1.25, f[2]);
    t(s, f[0], { x: x + 0.1, y: fy + 0.52, w: fw - 0.2, h: 0.4, fontSize: 15, bold: true, color: 'FFFFFF', align: 'center' });
    t(s, f[1], { x: x + 0.1, y: fy + 0.98, w: fw - 0.2, h: 0.55, fontSize: 11, color: 'E6E6E6', align: 'center' });
    if (i < 3) arrow(s, x + fw + 0.06, fy + 1.02, 0.36, 0, INK);
  });
  // features grid
  const gy = fy + 1.85;
  t(s, '打分特征（计划书 §9 列出的 11 类）', { x: X0, y: gy, w: 6, h: 0.3, fontSize: 12.5, bold: true });
  const feats = ['等效效率', '电价', '绿电比例', 'PUE 超出', '池占用', '时延比', '是否跨域', '是否国产', '配额', '服务等级风险', '等待时间'];
  const fw2 = 1.06;
  feats.forEach((f, i) => {
    const x = X0 + i * (fw2 + 0.067);
    box(s, x, gy + 0.38, fw2, 0.6, i < 4 ? RED : LG);
    t(s, f, { x, y: gy + 0.38, w: fw2, h: 0.6, fontSize: 10.5, bold: true, align: 'center', valign: 'middle', color: i < 4 ? RED : INK });
  });
  t(s, '红框：电价、绿电与 PUE 直接进入每一次节点选择；只保留打分、不做移峰时，推迟计数为 0（见第 10 页消融）', { x: X0, y: gy + 1.06, w: XW, h: 0.26, fontSize: 10.5, color: GREY });
})();

// 9 commands + voucher
(function () {
  const s = pptx.addSlide();
  base(s, 9, '03 技术路线 · 指令与凭证', '四句中文指令在同一输入上重算，每笔任务把电量、碳和校验和写进一张凭证', null,
    '来源：计划书 §3.4、§3.5、§4；佐证材料 §6。凭证电费为演示电价下的值；电量随 10,000 kW/EF 设定线性放大，用于策略对照。');
  const Y = 1.8, LX = X0, LW = 6.75;
  const rows = [['中文指令', '引擎怎么做'],
    ['把碳排权重调到 0.6', '迎峰度夏场景下改权重，同一输入重算一周，与改前对比'],
    ['注入南京 30% 算力损失', '带百分数＝容量损失：南京按剩余 70% 容量重新分配'],
    ['（不带百分数的停机）', '整节点离线：从候选节点中去掉该节点'],
    ['优先消纳绿电', '提高绿电偏好后重算配额与打分'],
    ['解释当前调度', '模板读取亲和度、影子价格、PUE、绿电比例、动作概率生成说明']];
  table(s, rows, { x: LX, y: Y, w: LW, colW: [2.35, 4.4], rowH: 0.56, fs: 11, numCols: false, align: 'left' });
  // diagram split
  const dy = Y + 3.6;
  t(s, '故障注入两种口径', { x: LX, y: dy, w: 4, h: 0.28, fontSize: 12.5, bold: true });
  const bw = 3.25;
  [['南京 30%', 0.7, '容量损失 → 保留 70%，重分配'], ['南京 离线', 0, '整节点离线 → 退出候选']].forEach((b, i) => {
    const x = LX + i * (bw + 0.25);
    t(s, b[0], { x, y: dy + 0.36, w: bw, h: 0.26, fontSize: 11, bold: true, color: RED });
    rect(s, x, dy + 0.66, bw, 0.32, 'E4E0D9');
    if (b[1] > 0) rect(s, x, dy + 0.66, bw * b[1], 0.32, DARK);
    t(s, b[1] > 0 ? '剩余 70%' : '0%', { x: x + 0.08, y: dy + 0.66, w: 1.5, h: 0.32, fontSize: 10, bold: true, color: b[1] > 0 ? 'FFFFFF' : RED, valign: 'middle', fontFace: CN });
    t(s, b[2], { x, y: dy + 1.02, w: bw, h: 0.26, fontSize: 10, color: GREY });
  });
  // voucher
  const VX = 7.55, VW = 5.28;
  rect(s, VX, Y, VW, 5.0, DARK);
  rect(s, VX, Y, VW, 0.08, RED);
  t(s, '任务凭证 · 样例', { x: VX + 0.3, y: Y + 0.22, w: 3, h: 0.32, fontSize: 14, bold: true, color: 'FFFFFF' });
  t(s, '常规工作日 · SuCompute · 任务 1', { x: VX + 0.3, y: Y + 0.56, w: VW - 0.6, h: 0.26, fontSize: 10, color: 'B5B5B5' });
  t(s, '高性能计算：南京 → 盐城 DCU 池，槽 0–14', { x: VX + 0.3, y: Y + 0.9, w: VW - 0.6, h: 0.3, fontSize: 12, bold: true, color: 'FFFFFF' });
  const kv = [['有效算力', '1.984', 'EF·h'], ['分摊电量', '27,600', 'kWh'], ['电费（演示电价）', '10,212', '元'], ['碳排', '293.0', 'kg'], ['相对全购电减排', '14,887', 'kg'], ['绿电份额', '98.07', '%'], ['PUE', '1.157', ''], ['动作概率', '0.975', '']];
  kv.forEach((k, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = VX + 0.3 + col * 2.4, y = Y + 1.35 + row * 0.72;
    hl(s, x, y, 2.2, '4A4A4A', 0.5);
    t(s, k[0], { x, y: y + 0.05, w: 2.2, h: 0.22, fontSize: 9.5, color: 'B5B5B5' });
    t(s, [{ text: k[1], options: { fontFace: NUM, bold: true, fontSize: 18, color: i === 4 ? 'FF5A62' : 'FFFFFF' } }, { text: k[2] ? ' ' + k[2] : '', options: { fontFace: NUM, fontSize: 10, color: 'D0D0D0' } }], { x, y: y + 0.27, w: 2.3, h: 0.38, valign: 'middle' });
  });
  t(s, 'SHA-256 校验和', { x: VX + 0.3, y: Y + 4.28, w: 3, h: 0.22, fontSize: 9.5, color: 'B5B5B5' });
  t(s, 'e699c16ae9430f01cab21b2efbe628acc9a1f5f9…', { x: VX + 0.3, y: Y + 4.5, w: VW - 0.6, h: 0.3, fontSize: 10.5, fontFace: MONO, color: 'FFFFFF' });
})();

// 10 four scenarios
(function () {
  const s = pptx.addSlide();
  base(s, 10, '04 仿真评测 · 四场景', '四场景各跑 168 小时：高峰服务等级保持在 99.76%–99.83%', null,
    '来源：计划书 §4；佐证材料 §3、表 4。推迟 ≥ 2h：预训练和微调首次开工推迟不少于 24 个五分钟槽的作业数。全装机口径含未通电容量，与有效在线利用率不同。');
  const Y = 1.75, CX = X0, CW = 6.2;
  t(s, '推迟 ≥ 2h 的批任务：每场景 3,299–3,508 个', { x: CX, y: Y, w: 4.5, h: 0.3, fontSize: 12.5, bold: true });
  legend(s, CX + 3.3, Y + 0.32, [[RED, 'SuCompute', 1.3], ['8C8C8C', '仅整数规划', 1.4]]);
  const cats = ['常规工作日', '绿电大发', '尖峰保电', '故障压测'];
  vbars(s, { x: CX, y: Y + 0.65, w: CW, h: 1.55, max: 3700, cats, bw: 0.55, vfs: 9.5,
    series: [{ color: RED, values: [3305, 3485, 3508, 3299], fmt: v => v.toLocaleString('en-US') }, { color: '8C8C8C', values: [3060, 3144, 3327, 3051], fmt: v => v.toLocaleString('en-US') }] });
  t(s, '滚动重排次数（策略网络分担后更少）', { x: CX, y: Y + 2.75, w: 5, h: 0.3, fontSize: 12.5, bold: true });
  vbars(s, { x: CX, y: Y + 3.4, w: CW, h: 1.3, max: 2700, cats, bw: 0.55, vfs: 9.5,
    series: [{ color: RED, values: [1354, 1152, 1470, 1402], fmt: v => v.toLocaleString('en-US') }, { color: '8C8C8C', values: [2334, 1967, 2467, 2475], fmt: v => v.toLocaleString('en-US') }] });
  // table
  const TX = 7.0, TW = 5.83;
  const R = [['场景', '策略', '推迟≥2h', '重排', '高峰', '全装机']];
  const d = [['常规工作日', [3305, 1354, '99.83%', '32.38%'], [3060, 2334, '99.83%', '32.33%'], [0, 0, '99.78%', '32.36%']],
    ['绿电大发', [3485, 1152, '99.76%', '32.34%'], [3144, 1967, '99.78%', '32.33%'], [0, 0, '99.73%', '32.34%']],
    ['尖峰保电', [3508, 1470, '99.82%', '34.27%'], [3327, 2467, '99.84%', '34.22%'], [0, 0, '99.78%', '34.20%']],
    ['故障压测', [3299, 1402, '99.80%', '32.34%'], [3051, 2475, '99.80%', '32.31%'], [0, 0, '99.74%', '32.35%']]];
  const names = ['SuCompute', '仅整数规划', '仅约束策略'];
  d.forEach(sc => [1, 2, 3].forEach(k => {
    const v = sc[k];
    const sty = k === 1 ? { color: RED, bold: true } : {};
    R.push([k === 1 ? sc[0] : '', { text: names[k - 1], options: Object.assign({ fontFace: k === 1 ? NUM : CN, align: 'left' }, sty) },
      { text: v[0].toLocaleString('en-US'), options: sty }, { text: v[1].toLocaleString('en-US'), options: sty }, { text: v[2], options: sty }, { text: v[3], options: sty }]);
  }));
  table(s, R, { x: TX, y: Y, w: TW, colW: [1.05, 1.18, 0.95, 0.75, 0.95, 0.95], rowH: 0.3, fs: 10 });
  rect(s, TX, Y + 4.05, TW, 0.88, PANEL);
  t(s, [{ text: '分工清楚：', options: { bold: true, color: RED } }, { text: '整数规划把训练、微调挪到合适的小时；策略网络负责时隙内选点。只保留策略网络时推迟与重排为 0，高峰仍有 99.73%–99.78%。' }], { x: TX + 0.15, y: Y + 4.1, w: TW - 0.3, h: 0.78, fontSize: 10.5, valign: 'middle' });
})();

// 11 six strategies table
(function () {
  const s = pptx.addSlide();
  base(s, 11, '04 仿真评测 · 六策略', '六策略 × 六维：SuCompute 在利用率、服务等级、能耗上同时领先', null,
    '来源：佐证材料 表 1（四场景等权均值）；计划书 表 1。碳强度单位 kgCO₂/EF·h；高峰为每日 09–11 与 17–19 时到达的任务；国产份额下限 30%。');
  const Y = 1.75;
  const rows = [['策略', '利用率', '服务等级', 'kWh/EF·h', 'PUE', '绿电', '碳强度', '高峰', '国产份额'],
    ['轮询就近', '62.72%', '95.72%', '17,705.0', '1.3760', '25.26%', '7,277.5', '92.64%', '56.30%'],
    ['最短队列', '60.92%', '98.13%', '18,181.2', '1.3497', '25.98%', '7,401.3', '97.04%', '54.79%'],
    ['成本优先', '68.98%', '94.97%', '16,271.5', '1.3093', '27.26%', '6,509.9', '93.69%', '56.93%'],
    [{ text: 'SuCompute', options: { fontFace: NUM } }, '80.01%', '99.83%', '13,945.7', '1.2957', '35.95%', '4,911.9', '99.80%', '52.19%'],
    ['仅整数规划', '74.10%', '99.83%', '14,298.4', '1.3177', '35.57%', '5,066.2', '99.81%', '52.20%'],
    ['仅约束策略', '80.14%', '99.81%', '13,954.4', '1.2965', '35.71%', '4,933.7', '99.76%', '51.83%']];
  table(s, rows, { x: X0, y: Y, w: XW, colW: [1.75, 1.32, 1.32, 1.32, 1.12, 1.12, 1.32, 1.12, 1.96], rowH: 0.38, fs: 11.5, hiRow: 4 });
  t(s, '消融', { x: X0 - 0.0, y: Y + 2.68, w: 1, h: 0.0, fontSize: 1 });
  // three bar charts
  const cy = Y + 2.95, cw = 3.9, g = 0.32;
  const charts = [
    ['有效在线利用率（%）', [62.72, 60.92, 68.98, 80.01], 100, v => v.toFixed(2)],
    ['服务等级（%）', [95.72, 98.13, 94.97, 99.83], 100, v => v.toFixed(2)],
    ['单位能耗（kWh/EF·h）', [17705.0, 18181.2, 16271.5, 13945.7], 20000, v => v.toLocaleString('en-US', { minimumFractionDigits: 1 })],
  ];
  charts.forEach((c, i) => {
    const x = X0 + i * (cw + g);
    t(s, c[0], { x, y: cy, w: cw, h: 0.28, fontSize: 12, bold: true });
    hbars(s, { x, y: cy + 0.36, w: cw, labelW: 1.05, rowH: 0.4, max: c[2], valW: 0.85, fs: 10,
      rows: ['轮询就近', '最短队列', '成本优先', 'SuCompute'].map((n, j) => ({ label: n, v: c[1][j], txt: c[3](c[1][j]), hi: j === 3, color: j === 3 ? RED : '8C8C8C' })) });
  });
})();

// 12 relative + floors
(function () {
  const s = pptx.addSlide();
  base(s, 12, '04 仿真评测 · 相对提升', '相对轮询就近，脚本设定的 8 项下限在本合成周全部达到', null,
    '来源：计划书 §6；佐证材料 表 2、表 3。利用率、能耗、绿电、碳强度为相对变化；服务等级为百分点；PUE 为绝对差。');
  const Y = 1.75;
  const cards = [['+27.57', '%', '利用率', 'dark'], ['+4.12', 'pp', '服务等级', 'red'], ['−21.23', '%', '单位能耗', 'dark'], ['+42.31', '%', '绿电占比', 'light'], ['−32.51', '%', '碳强度', 'light'], ['−0.080', '', '加权 PUE', 'light']];
  const cw = 1.95, ch = 1.32;
  cards.forEach((c, i) => {
    const x = X0 + (i % 3) * (cw + 0.12), y = Y + Math.floor(i / 3) * (ch + 0.12);
    stat(s, { x, y, w: cw, h: ch, theme: c[3], label: c[2], num: c[0], unit: c[1], size: 28, unitSize: 13, numY: 0.48, numH: 0.6, pad: 0.16, labelSize: 11 });
  });
  // vs other baselines table
  const ty = Y + 2 * (ch + 0.12) + 0.2;
  t(s, '对其他对照的相对变化', { x: X0, y: ty, w: 4, h: 0.28, fontSize: 12, bold: true });
  table(s, [['对照', '利用率', 'SLA', '能耗', '绿电', '碳强度'],
    ['最短队列', '+31.33%', '+1.70', '−23.30%', '+38.36%', '−33.63%'],
    ['成本优先', '+15.99%', '+4.87', '−14.29%', '+31.90%', '−24.55%'],
    ['仅整数规划', '+7.97%', '+0.01', '−2.47%', '+1.08%', '−3.05%']], { x: X0, y: ty + 0.34, w: 6.09, colW: [1.2, 1.0, 0.75, 1.0, 1.0, 1.14], rowH: 0.31, fs: 10 });
  // floor checklist with bullet bars
  const RX = 6.95, RW = 5.88;
  t(s, '脚本下限 vs 本次值（作用域：本合成周，种子 313）', { x: RX, y: Y, w: RW, h: 0.28, fontSize: 12, bold: true });
  const fl = [['利用率提升', '+15%～22%', '27.57%', 22, 27.57, 35], ['各场景服务等级', '≥ 99.2%', '99.80%', 99.2, 99.80, 100, 98.5], ['单位能耗降低', '12%～18%', '21.23%', 18, 21.23, 30], ['有效在线利用率', '≥ 78%', '80.01%', 78, 80.01, 85, 70], ['绿电相对提升', '18%～25%', '42.31%', 25, 42.31, 50], ['碳强度降低', '15%～22%', '32.51%', 22, 32.51, 40], ['加权 PUE 降低', '≥ 0.06', '0.0803', 0.06, 0.0803, 0.1], ['最长故障编排', '≤ 3 秒', '0.0629 秒', 3, 0.0629, 3.5]];
  const rh = 0.555, lw = 1.6, bw = 2.4;
  fl.forEach((f, i) => {
    const y = Y + 0.42 + i * rh;
    hl(s, RX, y, RW, LG, 0.5);
    t(s, f[0], { x: RX, y: y + 0.06, w: lw, h: 0.24, fontSize: 10.5, bold: true });
    t(s, '下限 ' + f[1], { x: RX, y: y + 0.3, w: lw, h: 0.22, fontSize: 9.5, color: GREY });
    const lo = f[6] || 0, span = f[5] - lo;
    const bx = RX + lw + 0.05;
    rect(s, bx, y + 0.2, bw, 0.2, 'E4E0D9');
    const vx = bw * (Math.max(f[4], lo) - lo) / span;
    rect(s, bx, y + 0.2, Math.max(vx, 0.03), 0.2, RED);
    const fx = bx + bw * (f[3] - lo) / span;
    vl(s, fx, y + 0.12, 0.36, INK, 1.5);
    t(s, f[2], { x: bx + bw + 0.12, y: y + 0.12, w: 1.15, h: 0.36, fontSize: 12, bold: true, fontFace: NUM, color: RED, valign: 'middle' });
    rect(s, RX + RW - 0.62, y + 0.17, 0.62, 0.28, DARK);
    t(s, '达到', { x: RX + RW - 0.62, y: y + 0.17, w: 0.62, h: 0.28, fontSize: 10, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle' });
  });
  hl(s, RX, Y + 0.42 + 8 * rh, RW, LG, 0.5);
  t(s, '黑色竖线＝下限（区间取上沿）；红条＝本次值。故障编排一行越短越好。', { x: RX, y: Y + 0.48 + 8 * rh, w: RW, h: 0.24, fontSize: 9.5, color: GREY });
})();

// 13 wall clock + weights
(function () {
  const s = pptx.addSlide();
  base(s, 13, '04 仿真评测 · 墙钟与权重', '滚动规划最长 0.0957 秒，故障编排最长 0.0629 秒，五份权重校验通过', null,
    '来源：计划书 §10；佐证材料 摘要、§3、§5、表 6、§7。环境：Python 3.12.3，torch 2.7.0+cpu，scipy 1.15.2，4 vCPU。墙钟随机器变化。');
  const Y = 1.75;
  stat(s, { x: X0, y: Y, w: 3.2, h: 2.2, theme: 'dark', label: '滚动规划最长', num: '0.0957', unit: '秒', size: 46, unitSize: 16, numY: 0.5, numH: 0.9, note: '全体策略最大值（故障场景 · 仅整数规划）', noteSize: 10 });
  stat(s, { x: X0 + 3.4, y: Y, w: 3.2, h: 2.2, theme: 'red', label: '故障编排最长', num: '0.0629', unit: '秒', size: 46, unitSize: 16, numY: 0.5, numH: 0.9, note: 'SuCompute；求解最长 0.0681 秒，求解 168 次', noteSize: 10 });
  // vs 3s bar
  const by = Y + 2.5;
  t(s, '与脚本上限 3 秒同尺比较', { x: X0, y: by, w: 6.6, h: 0.28, fontSize: 12, bold: true });
  hbars(s, { x: X0, y: by + 0.4, w: 6.6, labelW: 1.5, rowH: 0.43, max: 3.0, valW: 0.8, fs: 10.5,
    rows: [{ label: '脚本上限', v: 3.0, txt: '3 秒', color: 'CFCAC2' }, { label: '滚动规划', v: 0.0957, txt: '0.0957 秒', color: DARK }, { label: '求解最长', v: 0.0681, txt: '0.0681 秒', color: DARK }, { label: '故障编排', v: 0.0629, txt: '0.0629 秒', hi: true }] });
  t(s, '复现：verify_weights.py · run_baselines.py · run_benchmark.py（--seed 313）', { x: X0, y: by + 2.25, w: 6.6, h: 0.26, fontSize: 9, fontFace: MONO, color: GREY });
  // weights table
  const RX = 7.4, RW = 5.43;
  t(s, '权重包：五份文件', { x: RX, y: Y, w: RW, h: 0.28, fontSize: 12, bold: true });
  table(s, [['文件', '字节', 'SHA-256 前 16 位'], ['策略权重', '9,669', 'fc11e917392a9140'], ['预报权重', '9,621', '4153bc439493ff61'], ['策略可移植格式', '5,437', '2f7b6d8032225469'], ['预报误差', '707', '5ccb04478642254c'], ['策略训练日志', '8,539', '6d3543ee4dd1219e'], [{ text: '合计', options: { bold: true } }, { text: '38,987', options: { bold: true } }, '5 / 5 哈希通过']],
    { x: RX, y: Y + 0.36, w: RW, colW: [1.75, 1.0, 2.68], rowH: 0.36, fs: 10.5 });
  rect(s, RX, Y + 3.05, RW, 1.95, DARK);
  t(s, 'Verified 5 hashes, 38987 bytes', { x: RX + 0.25, y: Y + 3.2, w: RW - 0.5, h: 0.32, fontSize: 12, fontFace: MONO, bold: true, color: 'FFFFFF' });
  const kv = [['3.81×10⁻⁶', '策略对数几率最大误差'], ['(24, 16, 2)', '预报输出形状'], ['1,706 + 1,466', '预报 + 策略参数']];
  kv.forEach((k, i) => {
    const x = RX + 0.25 + i * 1.72;
    t(s, k[0], { x, y: Y + 3.75, w: 1.7, h: 0.45, fontSize: 15, bold: true, fontFace: NUM, color: i === 0 ? 'FF5A62' : 'FFFFFF' });
    t(s, k[1], { x, y: Y + 4.25, w: 1.6, h: 0.5, fontSize: 9.5, color: 'B5B5B5' });
  });
})();

// 14 sidecar deployment
(function () {
  const s = pptx.addSlide();
  base(s, 14, '05 落地部署', '边车站在省平台旁边：读指标、写建议，下发与计量仍走现有队列', null,
    '来源：计划书 §3.5、§8、§10；佐证材料 §6。省平台字段名在联调时替换，建议单内容保持不变。');
  const Y = 1.75, H = 3.3;
  rect(s, X0, Y, 3.3, H, DARK);
  t(s, '省一体化算力平台（现有）', { x: X0 + 0.2, y: Y + 0.18, w: 3.0, h: 0.32, fontSize: 13, bold: true, color: 'FFFFFF' });
  ['省级调度核心', '13 个地市子门户', '长三角算力互联接口', '现有下发队列与计量'].forEach((p, i) => {
    rect(s, X0 + 0.2, Y + 0.7 + i * 0.64, 2.9, 0.5, '333333');
    t(s, p, { x: X0 + 0.35, y: Y + 0.7 + i * 0.64, w: 2.7, h: 0.5, fontSize: 11.5, color: 'FFFFFF', valign: 'middle' });
  });
  const SX = 6.25, SW = 2.85;
  s.addShape('rect', { x: SX, y: Y, w: SW, h: H, fill: { color: 'FFFFFF' }, line: { color: RED, width: 1.5, dashType: 'dash' } });
  t(s, 'SuCompute 边车', { x: SX + 0.2, y: Y + 0.15, w: SW - 0.4, h: 0.35, fontSize: 14, bold: true, color: RED });
  t(s, '按种子重放 1–168 小时 · 可断网', { x: SX + 0.2, y: Y + 0.52, w: SW - 0.4, h: 0.26, fontSize: 9.5, color: GREY });
  ['24 小时预报', '24 期整数规划', '可行域打分', '凭证与调度说明'].forEach((p, i) => {
    rect(s, SX + 0.2, Y + 0.95 + i * 0.56, SW - 0.4, 0.46, i % 2 ? PANEL : 'F6E3E4');
    t(s, p, { x: SX + 0.32, y: Y + 0.95 + i * 0.56, w: SW - 0.6, h: 0.46, fontSize: 11.5, bold: true, valign: 'middle' });
  });
  const AX = X0 + 3.35, AW = SX - AX - 0.05;
  t(s, '只读订阅', { x: AX, y: Y + 0.45, w: AW, h: 0.26, fontSize: 10.5, bold: true, align: 'center' });
  t(s, '负荷 · 电价 · 绿电 · 节点健康', { x: AX, y: Y + 0.72, w: AW, h: 0.26, fontSize: 9.5, color: GREY, align: 'center' });
  arrow(s, AX + 0.05, Y + 1.08, AW - 0.1, 0, INK);
  arrow(s, SX - 0.05, Y + 2.3, -(AW - 0.1), 0, RED, 'dash');
  t(s, '建议单', { x: AX, y: Y + 2.42, w: AW, h: 0.26, fontSize: 10.5, bold: true, color: RED, align: 'center' });
  t(s, '目的节点 · 时延圈 · 电费估算 · 校验和', { x: AX, y: Y + 2.69, w: AW, h: 0.26, fontSize: 9.5, color: RED, align: 'center' });
  const OX = 9.4, OW = 3.43;
  rect(s, OX, Y, OW, H, PANEL);
  t(s, '一条建议里同时看到', { x: OX + 0.2, y: Y + 0.18, w: OW - 0.4, h: 0.3, fontSize: 12.5, bold: true });
  [['目的节点', '可行域内最高分节点'], ['设计时延圈', '城域 1 / 省内 5 / 长三角 10 ms'], ['电费估算', '演示电价，绿电只改碳不改电费'], ['校验和', '去掉展示字段后的 SHA-256']].forEach((r, i) => {
    const y = Y + 0.65 + i * 0.66;
    rect(s, OX + 0.2, y + 0.06, 0.06, 0.46, RED);
    t(s, r[0], { x: OX + 0.36, y, w: OW - 0.5, h: 0.28, fontSize: 11.5, bold: true });
    t(s, r[1], { x: OX + 0.36, y: y + 0.29, w: OW - 0.5, h: 0.26, fontSize: 10, color: GREY });
  });
  const sy = Y + 3.6;
  t(s, '四阶段接入：先并列建议，再进工单，最后谈闭环', { x: X0, y: sy, w: 8, h: 0.3, fontSize: 12.5, bold: true });
  const st = [['阶段 0', '合成周跑通建议单', '合成周、权重、静态回放和本机边车已在仓库，评测可断网重跑', RED, '已完成'], ['阶段 1', '只读影子建议', '接平台已有只读时序；建议与现行策略并列，不写生产队列', DARK, '下一步'], ['阶段 2', '值班确认进工单', '由值班员确认后进入现有工单与队列', DARK, ''], ['阶段 3', '闭环与回退开关', '生产日志对照完成后，再安排闭环和回退开关', DARK, '']];
  const sw = (XW - 0.36) / 4;
  st.forEach((p, i) => {
    const x = X0 + i * (sw + 0.12);
    rect(s, x, sy + 0.42, sw, 0.12, p[3]);
    t(s, [{ text: p[0] + '  ', options: { bold: true, color: p[3] === RED ? RED : INK, fontSize: 12.5 } }, { text: p[1], options: { bold: true, fontSize: 12.5 } }], { x, y: sy + 0.66, w: sw, h: 0.3 });
    t(s, p[2], { x, y: sy + 1.02, w: sw - 0.1, h: 0.55, fontSize: 10.5, color: GREY });
    if (p[4]) { rect(s, x + sw - 0.72, sy + 0.68, 0.72, 0.26, p[3]); t(s, p[4], { x: x + sw - 0.72, y: sy + 0.68, w: 0.72, h: 0.26, fontSize: 9, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle' }); }
  });
})();

// 15 positioning
(function () {
  const s = pptx.addSlide();
  base(s, 15, '05 落地部署 · 分工', '把时延圈、电价、碳、绿电和故障放进同一条可复跑的边车', null,
    '来源：计划书 §4 末段、§5。仅列各方案公开的面向与分工，不作优劣评价。');
  const Y = 1.75;
  table(s, [['方案', '主要面向', '与 SuCompute 的关系'],
    ['Run:ai', 'GPU 配额管理', '集群内配额；边车不替换集群侧队列'],
    ['Cast AI', '多云成本优化', '云账单视角；边车面向省级节点电价与碳'],
    ['灵骏 / 昇腾 / 无问芯穹', '各自绑定云或芯片栈', '边车跨厂商，6 类芯片池同一打分'],
    ['国家超算互联网', '全国算力门户', '门户层；边车服务省级调度台'],
    [{ text: 'SuCompute', options: { fontFace: NUM } }, '省级多厂商节点', '可复算的建议单 + 任务凭证']],
    { x: X0, y: Y, w: 7.3, colW: [2.1, 1.9, 3.3], rowH: 0.6, fs: 11.5, hiRow: 5, numCols: false, align: 'left' });
  // right: five factors converge
  const RX = 8.2, RW = 4.63;
  t(s, '同一条策略同时使用五个因素', { x: RX, y: Y, w: RW, h: 0.3, fontSize: 12.5, bold: true });
  const f = [['时延圈', '1 / 5 / 10 ms'], ['分时电价', '谷 · 平 · 峰 · 尖'], ['碳因子', '分省 / 演示值'], ['绿电', '24 h 预报'], ['故障', '容量损失 / 离线']];
  f.forEach((x, i) => {
    const y = Y + 0.45 + i * 0.6;
    rect(s, RX, y, 2.0, 0.48, i % 2 ? DARK : RED);
    t(s, x[0], { x: RX + 0.12, y, w: 1.0, h: 0.48, fontSize: 12, bold: true, color: 'FFFFFF', valign: 'middle' });
    t(s, x[1], { x: RX + 0.95, y, w: 1.0, h: 0.48, fontSize: 8.5, color: 'E6E6E6', valign: 'middle', align: 'right' });
    arrow(s, RX + 2.05, y + 0.24, 0.6, (Y + 1.65 - (y + 0.24)) * 0.0 + 0, INK);
  });
  vl(s, RX + 2.65, Y + 0.69, 2.4, INK, 1.25);
  rect(s, RX + 2.85, Y + 1.15, 1.78, 1.48, DARK);
  t(s, [{ text: '一条可复跑策略', options: { bold: true, fontSize: 12.5, color: 'FFFFFF', breakLine: true } }, { text: '同输入重放\n结果可复算', options: { fontSize: 9.5, color: 'C9C9C9' } }], { x: RX + 2.95, y: Y + 1.2, w: 1.6, h: 1.38, align: 'center', valign: 'middle' });
  arrow(s, RX + 2.66, Y + 1.89, 0.17, 0, INK);
  // innovations row
  const iy = Y + 3.9;
  const inn = [['分层求解', '整数规划负责未来一天的配额，策略网络负责当前槽位的可行打分，消融表把两者拆开'], ['凭证绑定', '电量、碳和校验和绑在每条任务上，抽查即可核对'], ['电费口径', '绿电只改变碳、不改变电费，演示电价不写成账单']];
  const iw = (XW - 0.4) / 3;
  inn.forEach((p, i) => {
    const x = X0 + i * (iw + 0.2);
    hl(s, x, iy, iw, INK, 1);
    t(s, '0' + (i + 1), { x, y: iy + 0.1, w: 0.6, h: 0.42, fontSize: 22, bold: true, color: RED, fontFace: NUM });
    t(s, p[0], { x: x + 0.62, y: iy + 0.14, w: iw - 0.7, h: 0.34, fontSize: 13, bold: true, valign: 'middle' });
    t(s, p[1], { x, y: iy + 0.62, w: iw, h: 0.6, fontSize: 11.5, color: GREY });
  });
})();

// 16 benefit
(function () {
  const s = pptx.addSlide();
  base(s, 16, '06 效益与路线', '单位能耗降 21.23%，按三档年用电推算年电费少 665–10,637 万元', null,
    '预估：降幅来自本合成周（13,945.7 vs 17,705.0 kWh/EF·h）；电费只按能耗一项、平段 0.6263 元/kWh 估算，到户电价待核实。来源：计划书 §7；佐证材料 §6 表 8。');
  const Y = 1.75;
  // left measured
  rect(s, X0, Y, 3.6, 5.0, DARK);
  t(s, '实测 · 单位能耗', { x: X0 + 0.25, y: Y + 0.18, w: 3.1, h: 0.3, fontSize: 12, bold: true, color: 'FFFFFF' });
  t(s, [{ text: '−21.23', options: { fontFace: NUM, bold: true, fontSize: 52, color: 'FFFFFF' } }, { text: ' %', options: { fontFace: NUM, bold: true, fontSize: 20, color: 'FFFFFF' } }], { x: X0 + 0.22, y: Y + 0.55, w: 3.3, h: 0.95, valign: 'middle' });
  const maxv = 18000, bh = 2.3, by = Y + 4.35;
  [['轮询就近', 17705.0, '8C8C8C', '17,705.0'], ['SuCompute', 13945.7, RED, '13,945.7']].forEach((b, i) => {
    const h = bh * b[1] / maxv, x = X0 + 0.5 + i * 1.45;
    rect(s, x, by - h, 1.0, h, b[2]);
    t(s, b[3], { x: x - 0.25, y: by - h - 0.3, w: 1.5, h: 0.26, fontSize: 11, bold: true, fontFace: NUM, color: 'FFFFFF', align: 'center' });
    t(s, b[0], { x: x - 0.25, y: by + 0.06, w: 1.5, h: 0.26, fontSize: 10, color: 'C9C9C9', align: 'center', fontFace: i ? NUM : CN });
  });
  hl(s, X0 + 0.3, by, 3.0, '777777', 0.75);
  t(s, 'kWh/EF·h', { x: X0 + 0.25, y: by + 0.36, w: 3.1, h: 0.24, fontSize: 9.5, color: 'B5B5B5', fontFace: NUM });
  // middle tiers
  const MX = 4.4, MW = 4.6;
  t(s, '年电费变化（万元，预估）', { x: MX, y: Y, w: MW, h: 0.3, fontSize: 12.5, bold: true });
  t(s, '年电费变化 ＝ 年用电 × 21.23% × 0.6263 元/kWh', { x: MX, y: Y + 0.34, w: MW, h: 0.26, fontSize: 10, color: GREY });
  vbars(s, { x: MX, y: Y + 1.05, w: MW, h: 3.2, max: 11500, cats: ['0.5 亿 kWh', '2.0 亿 kWh', '8.0 亿 kWh'], bw: 0.95, vfs: 13,
    series: [{ colors: ['8C8C8C', DARK, RED], values: [665, 2659, 10637], fmt: v => v.toLocaleString('en-US') }] });
  t(s, '年用电规模（假设三档）', { x: MX, y: Y + 4.68, w: MW, h: 0.26, fontSize: 9.5, color: GREY, align: 'center' });
  // right tariff
  const RX = 9.45, RW = 3.38;
  t(s, '110 kV 两部制分时电价（2025-08）', { x: RX, y: Y, w: RW, h: 0.3, fontSize: 11.5, bold: true });
  t(s, '元/kWh；测算取平段', { x: RX, y: Y + 0.34, w: RW, h: 0.26, fontSize: 10, color: GREY });
  vbars(s, { x: RX, y: Y + 1.05, w: RW, h: 2.3, max: 1.25, cats: ['谷', '平', '峰', '尖'], bw: 0.55, vfs: 10.5,
    series: [{ colors: ['C9C4BC', RED, '8C8C8C', DARK], values: [0.3485, 0.6263, 0.9682, 1.1221], fmt: v => v.toFixed(4) }] });
  rect(s, RX, Y + 3.85, RW, 1.15, PANEL);
  t(s, '测算只取平段。训练、微调本身就被规划到绿电或低价时段，谷段 0.3485 元/kWh。', { x: RX + 0.15, y: Y + 3.92, w: RW - 0.3, h: 1.0, fontSize: 10, valign: 'middle' });
})();

// 17 next steps
(function () {
  const s = pptx.addSlide();
  base(s, 17, '06 效益与路线', '下一步：一周影子运行，建议与现行策略并列，不改生产队列', null,
    '来源：计划书 §7、§10；赛题初赛日程。影子周沿用种子 313 与四个场景；小时级仿真继续单独列表。');
  const Y = 1.75;
  t(s, '影子周安排', { x: X0, y: Y, w: 4, h: 0.3, fontSize: 12.5, bold: true });
  const days = [['D1–D2', '常规工作日 + 绿电大发', '对照轮询就近 62.72% / 95.72%，看是否仍在 80% / 99.8% 一带', 2], ['D3', '尖峰保电 + 故障压测', '核对高峰服务等级；故障编排是否仍低于 1 秒', 1], ['D4', '导出凭证', '抽一条核对电量、碳与校验和三项', 1], ['周末', '只提交建议单', '不改生产队列；字段名联调时替换', 2]];
  const unit = XW / 6;
  let xx = X0;
  days.forEach((d, i) => {
    const w = unit * d[3] - 0.08;
    rect(s, xx, Y + 0.42, w, 0.5, i === 3 ? RED : DARK);
    t(s, d[0], { x: xx + 0.12, y: Y + 0.42, w: w - 0.2, h: 0.5, fontSize: 14, bold: true, color: 'FFFFFF', valign: 'middle', fontFace: /D/.test(d[0]) ? NUM : CN });
    t(s, d[1], { x: xx, y: Y + 1.02, w, h: 0.3, fontSize: 11.5, bold: true });
    t(s, d[2], { x: xx, y: Y + 1.34, w: w - 0.08, h: 0.66, fontSize: 10, color: GREY });
    xx += w + 0.08;
  });
  // acceptance table
  const ty = Y + 2.25;
  t(s, '影子周验收：四项读数 + 凭证抽查', { x: X0, y: ty, w: 7, h: 0.3, fontSize: 12.5, bold: true });
  table(s, [['验收项', '门槛', '合成周实测'],
    ['有效在线利用率', '高于轮询就近 62.72%', '80.01%'],
    ['服务等级', '高于 99%', '99.83%'],
    ['单位能耗降幅', '相对 17,705.0 kWh/EF·h 保持在 21% 一带', '21.23%'],
    ['故障编排', '远低于 3 秒', '0.0629 秒'],
    ['凭证抽查', '电量、碳、校验和三项同时在', '样例凭证三项齐全']],
    { x: X0, y: ty + 0.38, w: 7.6, colW: [1.8, 3.8, 2.0], rowH: 0.4, fs: 11, numCols: false });
  // contest timeline + closing
  const RX = 8.5, RW = 4.33;
  rect(s, RX, ty, RW, 2.78, DARK);
  t(s, '赛程', { x: RX + 0.25, y: ty + 0.15, w: 2, h: 0.3, fontSize: 12.5, bold: true, color: 'FFFFFF' });
  [['11.30', '初赛材料截止'], ['12.1–12.3', '线上评审'], ['12 月中旬', '路演']].forEach((r, i) => {
    const y = ty + 0.52 + i * 0.58;
    t(s, r[0], { x: RX + 0.25, y, w: 1.75, h: 0.45, fontSize: 18, bold: true, color: i === 0 ? 'FF5A62' : 'FFFFFF', fontFace: /\d/.test(r[0][0]) && i < 2 ? NUM : CN, valign: 'middle' });
    t(s, r[1], { x: RX + 2.05, y, w: 2.1, h: 0.45, fontSize: 12, color: 'D0D0D0', valign: 'middle' });
    hl(s, RX + 0.25, y + 0.5, RW - 0.5, '444444', 0.5);
  });
  rect(s, RX, ty + 2.28, RW, 0.5, RED);
  t(s, [{ text: 'SuCompute', options: { fontFace: NUM, bold: true } }, { text: '  ·  盼盼法式小面包  ·  谢谢', options: { bold: true } }], { x: RX + 0.25, y: ty + 2.28, w: RW - 0.5, h: 0.5, fontSize: 13, color: 'FFFFFF', valign: 'middle' });
})();

pptx.writeFile({ fileName: __dirname + '/../preview.pptx' }).then(f => console.log('wrote', f));
