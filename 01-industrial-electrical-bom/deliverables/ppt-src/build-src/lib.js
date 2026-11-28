const pptxgen = require('pptxgenjs');
const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';
pres.author = '盼盼法式小面包';
pres.title = 'ElectronicBOM 答辩';
const C = { bg:'FAF8F5', ink:'111111', red:'B3121B', grey:'666666', mid:'9A9A9A', rule:'D6D0C8', pale:'EFEAE4', pale2:'E4DED6', white:'FFFFFF', soft:'F3C9CB' };
const F = 'Noto Sans CJK SC', N = 'Archivo Black', S = 'Lora';
const TOTAL = 16;
const pad = n => String(n).padStart(2, '0');
function T(s, text, o) { s.addText(text, Object.assign({ fontFace: F, color: C.ink, margin: 0, valign: 'top', fontSize: 12 }, o)); }
function R(s, x, y, w, h, fill, line, dash) { s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: fill ? { color: fill } : { type: 'none' }, line: line ? { color: line, width: 0.75, dashType: dash || 'solid' } : { type: 'none' } }); }
function L(s, x, y, w, h, color, width, dash) { s.addShape(pres.shapes.LINE, { x, y, w, h, line: { color: color || C.ink, width: width || 0.75, dashType: dash || 'solid' } }); }
function A(s, x, y, w, h, color) { s.addShape(pres.shapes.LINE, { x, y, w, h, line: { color: color || C.ink, width: 1.25, endArrowType: 'triangle' } }); }
function chrome(s, n, sec, src) {
  s.background = { color: C.bg };
  R(s, 0.5, 0.29, 0.1, 0.1, C.red);
  T(s, [{ text: 'ELECTRONICBOM', options: { bold: true } }, { text: '   ·   ' + sec, options: { color: C.grey } }], { x: 0.7, y: 0.2, w: 8, h: 0.28, fontSize: 10.5, charSpacing: 1.5 });
  T(s, [{ text: 'AI-MFG-Q21   ', options: { color: C.grey } }, { text: pad(n), options: { bold: true, color: C.red } }, { text: ' / ' + TOTAL, options: { color: C.grey } }], { x: 9.8, y: 0.2, w: 3.03, h: 0.28, fontSize: 10.5, align: 'right', charSpacing: 1 });
  L(s, 0.5, 0.56, 12.333, 0, C.ink, 0.75);
  L(s, 0.5, 7.0, 12.333, 0, C.rule, 0.5);
  if (src) T(s, src, { x: 0.5, y: 7.06, w: 10.3, h: 0.25, fontSize: 9, color: C.mid });
  T(s, '盼盼法式小面包', { x: 10.8, y: 7.06, w: 2.03, h: 0.25, fontSize: 9, color: C.mid, align: 'right' });
}
// runs: array of strings or [text, true] for red
function title(s, runs, sub) {
  const arr = runs.map(r => Array.isArray(r) ? { text: r[0], options: { color: C.red } } : { text: r });
  T(s, arr, { x: 0.5, y: 0.74, w: 12.333, h: 0.62, fontSize: 26, bold: true, valign: 'middle' });
  if (sub) T(s, sub, { x: 0.5, y: 1.38, w: 12.333, h: 0.32, fontSize: 13, color: C.grey });
}
// stat card
function stat(s, o) {
  const th = o.theme || 'dark';
  const fill = th === 'red' ? C.red : th === 'dark' ? C.ink : C.pale;
  const fg = th === 'light' ? C.ink : C.white;
  const acc = th === 'light' ? C.red : C.white;
  const subc = th === 'red' ? 'F6D5D6' : th === 'dark' ? 'C8C8C8' : C.grey;
  const ns = o.ns || 44;
  R(s, o.x, o.y, o.w, o.h, fill);
  const nh = ns / 72 * 1.2;
  T(s, [{ text: o.num, options: { fontFace: N, fontSize: ns, color: acc } }, { text: o.unit || '', options: { fontFace: F, bold: true, fontSize: Math.round(ns * 0.42), color: acc } }], { x: o.x + 0.22, y: o.y + 0.16, w: o.w - 0.44, h: nh, valign: 'bottom' });
  let y = o.y + 0.16 + nh + 0.08;
  if (o.label) { T(s, o.label, { x: o.x + 0.22, y, w: o.w - 0.44, h: 0.32, fontSize: o.ls || 13.5, bold: true, color: fg }); y += 0.36; }
  if (o.sub) T(s, o.sub, { x: o.x + 0.22, y, w: o.w - 0.44, h: o.y + o.h - y - 0.1, fontSize: o.ss || 11, color: subc });
}
// horizontal bar with track
function hbar(s, x, y, w, h, val, max, color, txt, o) {
  o = o || {};
  if (!o.notrack) R(s, x, y, w, h, o.track || C.pale);
  const bw = Math.max(0.02, w * val / max);
  R(s, x, y, bw, h, color);
  if (txt) T(s, txt, { x: x + bw + 0.08, y: y - 0.04, w: o.lw || 1.4, h: h + 0.08, fontSize: o.fs || 11, bold: true, color: o.tc || C.ink, valign: 'middle', fontFace: o.font || F });
}
function kick(s, text, x, y, w, color) { T(s, text, { x, y, w, h: 0.26, fontSize: 10.5, bold: true, color: color || C.red, charSpacing: 1.5 }); }
module.exports = { pres, C, F, N, S, T, R, L, A, chrome, title, stat, hbar, kick, pad, TOTAL };
