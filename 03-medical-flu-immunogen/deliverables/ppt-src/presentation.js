'use strict';
/* FluVax-Evidence 答辩 PPT — refill of the press_newsletter_presentation family.
   Palette/chrome helpers kept from that template; slides rewritten. */
const path = require('path');
const PptxGenJS = require('pptxgenjs');

const SLIDE_W = 13.3333, SLIDE_H = 7.5;
const CREAM = 'FBF8F5', INK = '151515', RED = 'B3121B', GREY = '6E6A66', GREY_D = '3F3C39';
const SNOW = 'F5F2EF', SILVER = 'CFCAC5', RULEC = 'C6C1BB', PALE = 'F1ECE7';
const HEAD = 'Noto Sans CJK SC', BODY = 'Noto Sans CJK SC', SERIF = 'Liberation Serif';
const L = 1.1023, CW = 11.13; // content left + width

function tx(s, c, o) { s.addText(c, Object.assign({ fontFace: BODY, valign: 'top', margin: 0 }, o)); }
function rule(s, x, y, w, color, width) { s.addShape('line', { x, y, w, h: 0, line: { color: color || RULEC, width: width || 0.5 } }); }
function box(s, x, y, w, h, fill, line) {
  s.addShape('rect', { x, y, w, h, fill: fill === 'none' ? { color: CREAM, transparency: 100 } : { color: fill }, line: line ? { color: line, width: 0.75 } : { type: 'none' } });
}
function frame(s, o) {
  o = o || {};
  const stroke = o.dark ? '3A3A3A' : RULEC, label = o.dark ? SILVER : GREY;
  [0.3642, 0.7699, 12.5744, 12.9801].forEach(x => s.addShape('line', { x, y: 0, w: 0, h: SLIDE_H, line: { color: stroke, width: 0.5 } }));
  rule(s, 0, 0.8268, SLIDE_W, stroke);
  rule(s, 0, 6.7138, SLIDE_W, stroke);
  tx(s, 'FLUVAX-EVIDENCE', { x: L, y: 0.40, w: 2.3, h: 0.28, fontFace: HEAD, bold: true, fontSize: 11, charSpacing: 1.4, color: o.dark ? CREAM : INK });
  if (o.kicker) {
    s.addShape('rect', { x: 3.42, y: 0.548, w: 0.42, h: 0.022, fill: { color: RED }, line: { type: 'none' } });
    tx(s, o.kicker, { x: 3.98, y: 0.40, w: 3.9, h: 0.28, fontSize: 11, charSpacing: 0.8, color: o.dark ? SILVER : GREY });
  }
  tx(s, '人工智能+医疗健康赛道 · AI-HEALTH-Q40', { x: 7.9, y: 0.40, w: 4.33, h: 0.28, fontSize: 10, color: label, align: 'right' });
  tx(s, '盼盼法式小面包', { x: 11.80, y: 3.74, w: 2.0, h: 0.27, rotate: 90, fontSize: 9, color: label, align: 'center' });
  s.slideNumber = { x: 12.50, y: 6.86, w: 0.49, h: 0.29, align: 'right', fontFace: HEAD, bold: true, fontSize: 11, color: label };
}
function headline(s, t, size, y, h, w) {
  tx(s, t, { x: L, y: y || 1.02, w: w || CW, h: h || 0.92, fontSize: size || 30, bold: true, fontFace: HEAD, color: INK, lineSpacingMultiple: 1.12 });
}
function sub(s, t, y, w) { tx(s, t, { x: L, y: y || 1.96, w: w || CW, h: 0.4, fontSize: 13, color: GREY_D, lineSpacingMultiple: 1.3 }); }
function note(s, t) { tx(s, t, { x: L, y: 6.40, w: CW, h: 0.26, fontSize: 9, color: GREY, lineSpacingMultiple: 1.2 }); }
/* big-number stat card */
function card(s, o) {
  const fill = o.fill || INK;
  const dark = fill !== 'none' && fill !== CREAM && fill !== PALE;
  const vc = o.vcolor || (dark ? SNOW : INK);
  const lc = o.lcolor || (dark ? SILVER : GREY_D);
  if (fill === 'none') box(s, o.x, o.y, o.w, o.h, 'none', RULEC); else box(s, o.x, o.y, o.w, o.h, fill);
  const pad = 0.2;
  if (o.kick) tx(s, o.kick, { x: o.x + pad, y: o.y + 0.16, w: o.w - 2 * pad, h: 0.24, fontSize: 10, charSpacing: 0.6, color: dark ? SILVER : GREY });
  const vs = o.vs || 40;
  tx(s, [{ text: o.value, options: { fontSize: vs, bold: true, color: vc, fontFace: HEAD } },
         { text: o.unit ? ' ' + o.unit : '', options: { fontSize: Math.round(vs * 0.34), color: vc, fontFace: BODY } }],
     { x: o.x + pad, y: o.y + (o.kick ? 0.42 : 0.18), w: o.w - 2 * pad, h: vs / 72 * 1.4 });
  if (o.label) {
    const vy = o.y + (o.kick ? 0.42 : 0.18), vh = vs / 72 * 1.35;
    const ly = vy + vh + 0.04, lh = Math.max(0.22, o.y + o.h - ly - 0.06);
    tx(s, o.label, { x: o.x + pad, y: ly, w: o.w - 2 * pad, h: lh, fontSize: o.ls || 10.5, color: lc, lineSpacingMultiple: 1.2 });
  }
}
function cols(n, gap, x, w) { const g = gap === undefined ? 0.19 : gap; const X = x === undefined ? L : x, W = w === undefined ? CW : w; const cw = (W - g * (n - 1)) / n; return { cw, at: i => X + i * (cw + g) }; }
function table(s, rows, o) {
  s.addTable(rows, Object.assign({ fontFace: BODY, fontSize: 10.5, color: GREY_D, border: { pt: 0.5, color: RULEC }, valign: 'middle', autoPage: false }, o));
}
function th(t, extra) { return Object.assign({ text: t, options: Object.assign({ fill: { color: INK }, color: SNOW, bold: true, fontSize: 10.5 }, extra || {}) }); }
function cellRed(t) { return { text: t, options: { fill: { color: RED }, color: SNOW, bold: true } }; }
function stepArrow(s, x, y) { tx(s, '→', { x, y, w: 0.4, h: 0.3, fontSize: 16, color: RED, align: 'center' }); }

/* ------------------------------------------------------------- slides */

function s01(s) {
  frame(s);
  tx(s, 'FluVax-Evidence', { x: L, y: 1.18, w: CW, h: 1.35, fontSize: 80, bold: true, fontFace: HEAD, color: INK, charSpacing: -1 });
  tx(s, 'Evidence Review of Published Public Records', { x: L + 0.04, y: 2.56, w: 8.6, h: 0.5, fontSize: 25, italic: true, fontFace: SERIF, color: RED });
  s.addShape('rect', { x: L, y: 3.16, w: 1.5, h: 0.045, fill: { color: RED }, line: { type: 'none' } });
  tx(s, '已发表公开记录的证据审阅 · 检索、核验、对照与签批', { x: L, y: 3.32, w: 6.6, h: 0.36, fontSize: 16, bold: true, color: INK });
  tx(s, '交付范围：软件原型 + 公开记录离线评测；不含序列设计、湿实验与疗效结论。', { x: L, y: 3.74, w: 6.6, h: 0.34, fontSize: 11.5, color: GREY_D });

  const n = [
    { tag: '[01]', t: '赛道与赛题', b: '人工智能+医疗健康 · AI-HEALTH-Q40\n流感病毒免疫原辅助设计智能体研发和应用' },
    { tag: '[02]', t: '团队与编号', b: '盼盼法式小面包 · 创新组\n报名编号 REG-2026-000525' },
    { tag: '[03]', t: '命题单位', b: '宿迁市楚润数据集团有限公司\n2026 年 11 月' },
    { tag: '[04]', t: '数据版本', b: 'fluevidence-v1.1 · 24 条公开记录\n标识核验日 2026-11-28' },
  ];
  const c = cols(2, 0.3, L, 6.6);
  n.forEach((it, i) => {
    const x = c.at(i % 2), y = 4.42 + Math.floor(i / 2) * 1.16;
    tx(s, it.tag, { x, y, w: 0.62, h: 0.3, fontSize: 13, bold: true, fontFace: HEAD, color: RED });
    tx(s, it.t, { x: x + 0.66, y, w: c.cw - 0.66, h: 0.28, fontSize: 12, bold: true, color: INK });
    tx(s, it.b, { x: x + 0.66, y: y + 0.32, w: c.cw - 0.66, h: 0.66, fontSize: 10, color: GREY, lineSpacingMultiple: 1.25 });
  });

  const k = [
    { kick: 'RECALL@5', value: '1.00', label: '7 题前 5 条全部含标准答案', fill: INK },
    { kick: 'NDCG@5', value: '0.929', label: '六题 1.00，第 6 题 0.50', fill: RED },
    { kick: '档案对照 / 有效引用', value: '4/4 · 59/59', vs: 26, label: '与金标一致 / 与版本锁一致', fill: 'none' },
  ];
  k.forEach((o, i) => card(s, Object.assign(o, { x: 8.0, y: 2.56 + i * 1.30, w: 4.23, h: 1.22, vs: o.vs || 30, ls: 9.5 })));
  note(s, '来源：03 计划书封面与摘要、§6 表 1；03 佐证摘要、§1。快照 SHA-256 fbf7ca92a9ee…87613847。');
}

function s02(s) {
  frame(s, { kicker: '目录' });
  headline(s, '六段路线，全部落在同一份锁定快照之内', 32);
  sub(s, '问答与档案比较共用同一套版本锁；每一页的数字都来自计划书与佐证材料。');
  const items = ['离线结果：两类任务一次看完', '问题与四层架构', '证据库与三路检索', '两类任务逐题实测', '签批、耗时与评测集', '权重、分工与五项验收'];
  items.forEach((t, i) => {
    const y = 2.52 + i * 0.66;
    tx(s, String(i + 1).padStart(2, '0') + '.', { x: L + 0.06, y, w: 0.85, h: 0.4, fontSize: 19, bold: true, fontFace: HEAD, color: RED });
    tx(s, t, { x: L + 1.0, y: y + 0.03, w: 5.4, h: 0.4, fontSize: 17, color: INK });
    rule(s, L, y + 0.52, 6.45, RULEC, 1);
  });
  box(s, 7.95, 2.42, 4.28, 3.96, INK);
  tx(s, '五项验收读数', { x: 8.2, y: 2.62, w: 3.8, h: 0.3, fontSize: 12, bold: true, color: SNOW, charSpacing: 0.8 });
  const rows = [['Recall@5（7 题）', '1.00'], ['NDCG@5（7 题平均）', '0.929'], ['四份档案与金标一致', '4/4'], ['已采纳语句与版本锁一致', '59/59'], ['签批 采纳 / 标疑', '23 / 1']];
  rows.forEach((r, i) => {
    const y = 3.12 + i * 0.62;
    tx(s, r[0], { x: 8.2, y: y + 0.08, w: 2.5, h: 0.3, fontSize: 10.5, color: SILVER });
    tx(s, r[1], { x: 10.6, y, w: 1.45, h: 0.38, fontSize: 18, bold: true, fontFace: HEAD, color: i === 4 ? RED : SNOW, align: 'right' });
    if (i < 4) rule(s, 8.2, y + 0.5, 3.8, '3A3A3A');
  });
  tx(s, '疗效承诺探针 1 条被拒；快照 24 条原文匹配数 0。', { x: 8.2, y: 5.95, w: 3.8, h: 0.3, fontSize: 9.5, color: SILVER });
  note(s, '来源：03 计划书摘要、§6 表 1、§10；03 佐证 §3。');
}

function s03(s) {
  frame(s, { kicker: '01 离线结果' });
  headline(s, 'Recall@5 1.00，NDCG@5 0.929，档案 4/4，引用 59/59', 29);
  sub(s, '任务一为 7 道封闭题、每题取前 5 条；任务二为 4 份已发表方案档案，逐列与预先写好的金标比对。');
  const c = cols(4);
  const big = [
    { kick: '证据问答 · RECALL@5', value: '1.00', label: '7 题的前 5 条全部含标准答案', fill: INK },
    { kick: '证据问答 · NDCG@5', value: '0.929', label: '六题 1.00；第 6 题目标排第三，为 0.50', fill: RED },
    { kick: '档案对照', value: '4/4', label: '版本、空白项与交叉标识均与金标一致', fill: INK },
    { kick: '有效引用', value: '59/59', label: '已采纳语句与版本锁逐字一致', fill: RED },
  ];
  big.forEach((o, i) => card(s, Object.assign(o, { x: c.at(i), y: 2.46, w: c.cw, h: 1.78, vs: 44 })));
  const c2 = cols(5, 0.17);
  const small = [
    { kick: '问答耗时 · 中位', value: '18.2', unit: 'ms' },
    { kick: '档案比较', value: '16.9', unit: 'ms' },
    { kick: '签批', value: '11.5', unit: 'ms' },
    { kick: '签批 采纳 / 标疑', value: '23 / 1' },
    { kick: '疗效承诺探针', value: '1 拒', vcolor: RED },
  ];
  small.forEach((o, i) => card(s, Object.assign(o, { x: c2.at(i), y: 4.40, w: c2.cw, h: 1.18, fill: 'none', vs: 28 })));
  box(s, L, 5.76, CW, 0.5, INK);
  tx(s, '交付边界：软件原型 + 已发表公开记录的离线评测；不做序列设计、湿实验与疗效结论，公开库接口本次未重查（待核实）。', { x: L + 0.24, y: 5.89, w: CW - 0.48, h: 0.3, fontSize: 11.5, bold: true, color: SNOW });
  note(s, '来源：03 计划书摘要、§3.4、§6 表 1；03 佐证 §2–§3。脚注：人工检索 SOP 在评测记录中为未测，不参与本页分数。');
}

function s04(s) {
  frame(s, { kicker: '02 问题与架构' });
  headline(s, '一次方案比较要同时回答四件事', 32);
  sub(s, '文献、核酸库、结构库与表位库分散；人工抄进表格时版本与标识最先脱落，只给一个综合分数又看不出依据。');
  const qs = ['这句话出自哪一条公开记录？', '这条记录是哪一个数据版本？', '不同来源之间是否互相引用？', '还缺哪一级证据（实验登录 / 监测 / 文献 / 计算预测）？'];
  qs.forEach((t, i) => {
    const y = 2.52 + i * 0.86;
    box(s, L, y, 6.3, 0.68, i === 3 ? PALE : CREAM, RULEC);
    tx(s, String(i + 1).padStart(2, '0'), { x: L + 0.22, y: y + 0.14, w: 0.6, h: 0.4, fontSize: 18, bold: true, fontFace: HEAD, color: RED });
    tx(s, t, { x: L + 0.95, y: y + 0.19, w: 5.2, h: 0.34, fontSize: 14, color: INK });
  });
  box(s, 7.85, 2.52, 4.38, 3.42, INK);
  tx(s, '资料分散在四类公开库', { x: 8.07, y: 2.70, w: 3.9, h: 0.3, fontSize: 12, bold: true, color: SNOW });
  const srcs = ['文献（PMID）', '核酸库元数据', '结构登录（PDB）', '表位库（IEDB）'];
  const c = cols(2, 0.18, 8.07, 3.94);
  srcs.forEach((t, i) => {
    const x = c.at(i % 2), y = 3.12 + Math.floor(i / 2) * 0.62;
    box(s, x, y, c.cw, 0.5, '2A2A2A');
    tx(s, t, { x: x + 0.1, y: y + 0.14, w: c.cw - 0.2, h: 0.3, fontSize: 10.5, color: SNOW, align: 'center' });
  });
  tx(s, '↓', { x: 9.8, y: 4.38, w: 0.5, h: 0.3, fontSize: 16, color: RED, align: 'center' });
  box(s, 8.07, 4.74, 3.94, 0.98, RED);
  tx(s, '人工抄进表格：版本脱落、标识脱落\n只剩一个综合分数，看不出依据', { x: 8.2, y: 4.94, w: 3.7, h: 0.66, fontSize: 11.5, bold: true, color: SNOW, align: 'center', lineSpacingMultiple: 1.25 });
  note(s, '来源：03 计划书 §1；未收录清单（GISAID 序列与计数、Nextstrain 分支频率、深度突变扫描分数、核苷酸与设计构建体、湿实验步骤）见 03 佐证 §1。');
}

function s05(s) {
  frame(s, { kicker: '02 问题与架构' });
  headline(s, '锁定快照后再检索、核验、对照、签批：问答与档案比较共用同一套版本锁', 26);
  const layers = [
    { tag: '交互', items: ['循证问答', '四份档案对照', '专家签批'] },
    { tag: '服务', items: ['发表与入库时间', '逐字与版本核验', '来源与等级', '疗效语句检查（旁路）'] },
    { tag: '算法', items: ['词频与精确标识', '稠密向量与图', '重排与忠实度', '原文组装'] },
    { tag: '数据', items: ['24 条公开记录', '版本锁', '四份文献档案'] },
  ];
  layers.forEach((Lr, i) => {
    const y = 2.14 + i * 1.03;
    box(s, L, y, 1.05, 0.82, INK);
    tx(s, Lr.tag, { x: L, y: y + 0.26, w: 1.05, h: 0.32, fontSize: 15, bold: true, fontFace: HEAD, color: SNOW, align: 'center' });
    const c = cols(Lr.items.length, 0.16, L + 1.22, CW - 1.22);
    Lr.items.forEach((t, j) => {
      const isBypass = t.indexOf('旁路') >= 0;
      const x = c.at(j);
      if (isBypass) box(s, x, y, c.cw, 0.82, CREAM, RED); else box(s, x, y, c.cw, 0.82, PALE, RULEC);
      tx(s, t, { x: x + 0.08, y: y + 0.26, w: c.cw - 0.16, h: 0.34, fontSize: 12.5, bold: !isBypass, color: isBypass ? RED : INK, align: 'center' });
    });
    if (i < 3) tx(s, '↑', { x: 6.4, y: y + 0.84, w: 0.4, h: 0.2, fontSize: 11, color: GREY, align: 'center' });
  });
  box(s, L, 6.02, CW, 0.3, 'none', RULEC);
  tx(s, '实线为主数据流，疗效语句检查为旁路；边界：做检索、对照与签批，不做序列设计与疗效结论。', { x: L + 0.18, y: 6.08, w: CW - 0.36, h: 0.26, fontSize: 11, bold: true, color: INK });
  note(s, '来源：03 计划书 §2 与图 1；范围脚注 — 03 计划书脚注 1。');
}

function s06(s) {
  frame(s, { kicker: '03 证据库与检索' });
  headline(s, '24 条公开记录分三条来源层级，锁定于 fluevidence-v1.1', 27);
  sub(s, '实验登录 6 条、监测元数据 2 条、文献与审校 16 条、计算预测 0 条；v1.1 = 初版 + 更正通知 + 两条茎部结构登录，标识核验日 2026-11-28。');
  s.addChart('bar', [{ name: '条数', labels: ['实验登录', '监测元数据', '文献与审校', '计算预测'], values: [6, 2, 16, 0] }], {
    x: L, y: 2.42, w: 6.3, h: 3.0, barDir: 'col', barGapWidthPct: 90,
    chartColors: [INK],
    chartArea: { fill: { color: CREAM } }, plotArea: { fill: { color: CREAM } },
    showLegend: false, showValue: true, dataLabelPosition: 'outEnd', dataLabelFontFace: HEAD, dataLabelFontSize: 14, dataLabelColor: INK,
    catAxisLabelFontFace: BODY, catAxisLabelFontSize: 11, catAxisLabelColor: GREY_D, catAxisLineShow: false,
    valAxisHidden: true, valAxisMinVal: 0, valAxisMaxVal: 20, valGridLine: { style: 'none' }, catGridLine: { style: 'none' },
  });
  const c = cols(3, 0.16, L, 6.3);
  [['6', '实验登录 · PDB / IEDB'], ['2', '监测元数据 · 核酸库'], ['16', '文献与审校 · PMID']].forEach((r, i) => {
    card(s, { x: c.at(i), y: 5.46, w: c.cw, h: 0.9, fill: 'none', value: r[0], vs: 22, label: r[1], ls: 9.5 });
  });
  box(s, 7.6, 2.42, 4.63, 3.92, INK);
  tx(s, '公开标识示例（节选自 24 行记录表）', { x: 7.82, y: 2.60, w: 4.2, h: 0.3, fontSize: 11.5, bold: true, color: SNOW });
  const ids = [['PMID:19465683', '参考株方向'], ['PMID:19822741', '糖基化方向'], ['PMID:26303961', '茎部方向'], ['PMID:26912624 / 38819164', '共识文献与更正'], ['PDB:3GBN / 5C0S', '结构登录'], ['IEDB:570 / 226309', '表位'], ['CY121680.1 / AF348176.1', '核酸库元数据'], ['UniProt:P03452', '审校条目']];
  ids.forEach((r, i) => {
    const y = 3.06 + i * 0.37;
    tx(s, r[0], { x: 7.82, y, w: 2.9, h: 0.3, fontSize: 10.5, bold: true, color: SNOW });
    tx(s, r[1], { x: 10.6, y, w: 1.45, h: 0.3, fontSize: 9.5, color: SILVER, align: 'right' });
  });
  tx(s, '记录覆盖 2004–2024 年的关键文献与 2009、2015 年结构登录；每条记录至少有标识、题名、版本与入库时间。', { x: 7.82, y: 5.92, w: 4.2, h: 0.42, fontSize: 9.5, color: SILVER, lineSpacingMultiple: 1.2 });
  note(s, '来源：03 计划书 §2、§8、§9；24 行明细 — 03 佐证表 1（EV-CONS-CARTER 审阅状态为标疑，其余已接受）。');
}

function s07(s) {
  frame(s, { kicker: '03 证据库与检索' });
  headline(s, '词频、384 维向量与 1–3 跳图三路融合，再由 362 参数重排器排序', 27);
  const ins = ['词频与精确标识', '384 维本地稠密向量', '文档·主题·证据·快照 1–3 跳图'];
  ins.forEach((t, i) => {
    const y = 2.36 + i * 0.86;
    box(s, L, y, 2.95, 0.74, PALE, RULEC);
    tx(s, t, { x: L + 0.12, y: y + 0.14, w: 2.71, h: 0.48, fontSize: 12, bold: true, color: INK, align: 'center', lineSpacingMultiple: 1.2 });
    rule(s, L + 2.95, y + 0.37, 1.57, RULEC, 0.75);
  });
  s.addShape('line', { x: 4.52, y: 2.73, w: 0, h: 1.72, line: { color: RULEC, width: 0.75 } });
  stepArrow(s, 4.42, 3.44);
  box(s, 4.92, 3.05, 1.75, 1.2, INK);
  tx(s, '名次融合', { x: 4.92, y: 3.50, w: 1.75, h: 0.32, fontSize: 13, bold: true, fontFace: HEAD, color: SNOW, align: 'center' });
  stepArrow(s, 6.77, 3.50);
  box(s, 7.25, 3.05, 2.35, 1.2, RED);
  tx(s, '362 参数重排器', { x: 7.35, y: 3.22, w: 2.15, h: 0.32, fontSize: 13.5, bold: true, fontFace: HEAD, color: SNOW, align: 'center' });
  tx(s, '输出相关性概率；问题中的\nPMID / PDB / 表位号优先命中', { x: 7.35, y: 3.60, w: 2.15, h: 0.58, fontSize: 9.5, color: SNOW, align: 'center', lineSpacingMultiple: 1.2 });
  stepArrow(s, 9.70, 3.50);
  box(s, 10.18, 3.05, 2.05, 1.2, 'none', INK);
  tx(s, '前 5 条', { x: 10.18, y: 3.38, w: 2.05, h: 0.34, fontSize: 16, bold: true, fontFace: HEAD, color: INK, align: 'center' });
  tx(s, '交给逐字与版本核验', { x: 10.18, y: 3.80, w: 2.05, h: 0.3, fontSize: 9.5, color: GREY, align: 'center' });
  const c = cols(3, 0.19, L, CW);
  [{ kick: '忠实度判别器', value: '387', unit: '参数', label: '为成对文本给出忠实度概率，作为核验旁边的信号', fill: INK },
   { kick: '重排器参数量', value: '362', unit: '参数', label: '单机 CPU 前向；排序使用相关性概率', fill: 'none' },
   { kick: '精确标识优先', value: 'PMID / PDB / IEDB', vs: 19, label: '问题里写出的编号直接对齐到记录；词频与向量负责没有写编号的问法', fill: 'none' }]
    .forEach((o, i) => card(s, Object.assign(o, { x: c.at(i), y: 5.00, w: c.cw, h: 1.38, vs: o.vs || 30, ls: 9.5 })));
  note(s, '来源：03 计划书 §3.2、§9；训练分工 — 03 佐证 §4：两套权重用不同领域的合成句训练、验证与测试，流感快照不参与训练。');
}

function s08(s) {
  frame(s, { kicker: '03 证据库与检索' });
  headline(s, '过不了原文与版本锁，就不算有效引用', 32);
  sub(s, '候选句子必须与快照中的原文片段逐字一致，并且标识与版本落在当前批准集合之内。');
  box(s, L, 2.46, 4.35, 3.4, INK);
  tx(s, '已采纳语句与版本锁一致', { x: L + 0.26, y: 2.70, w: 3.8, h: 0.3, fontSize: 12, color: SILVER });
  tx(s, '59/59', { x: L + 0.26, y: 3.08, w: 3.9, h: 1.5, fontSize: 96, bold: true, fontFace: HEAD, color: SNOW });
  tx(s, '通过「逐字一致」与「版本在批准集合内」两步的语句，才计为有效引用。', { x: L + 0.26, y: 4.98, w: 3.83, h: 0.72, fontSize: 11, color: SILVER, lineSpacingMultiple: 1.3 });
  const items = [
    { k: '不读原文的草稿提交', v: '3 条 / 采纳 0', l: '超出所选记录 2 条，与原文非逐字 1 条', fill: RED },
    { k: '疗效承诺探针', v: '1 条被拒', l: '把保护效果或临床疗效写成定论的句子由旁路拦住', fill: 'none' },
    { k: '快照 24 条原文与疗效承诺模式匹配', v: '0', l: '评测只使用已发表题名、定义行、表位摘要与条目首行', fill: 'none' },
  ];
  items.forEach((o, i) => card(s, { x: 5.88, y: 2.46 + i * 1.19, w: 6.35, h: 1.1, fill: o.fill, kick: o.k, value: o.v, vs: 21, label: o.l, ls: 9.5 }));
  box(s, L, 6.02, CW, 0.3, PALE, RULEC);
  tx(s, '门禁两步：① 与快照原文片段逐字一致 → ② 标识与版本落在当前批准集合（v1 / v1.1）', { x: L + 0.18, y: 6.08, w: CW - 0.36, h: 0.26, fontSize: 11, bold: true, color: INK });
  note(s, '来源：03 计划书 §3.3、§3.5；03 佐证 §1、§3。');
}

function s09(s) {
  frame(s, { kicker: '04 两类任务实测' });
  headline(s, '七题前五条全部含标准答案，平均 NDCG@5 为 0.929', 30);
  const rows = [
    [th('题'), th('期望记录'), th('Recall@5'), th('NDCG@5'), th('毫秒')],
    ['Q1', 'EV-REF-GARTEN', '1.00', '1.00', '24.7'],
    ['Q2', 'EV-GLY-WANG', '1.00', '1.00', '18.1'],
    ['Q3', '两条 CARTER 记录', '1.00', '1.00', '18.6'],
    ['Q4', 'EV-PDB-3GBN；EV-PDB-5C0S', '1.00', '1.00', '19.3'],
    ['Q5', 'EV-ACC-CA07', '1.00', '1.00', '14.4'],
    [cellRed('Q6'), cellRed('EV-STEM-HEADLESS'), cellRed('1.00'), cellRed('0.50'), cellRed('16.8')],
    ['Q7', 'EV-IEDB-570；EV-IEDB-226309', '1.00', '1.00', '18.2'],
    [{ text: '平均', options: { bold: true, color: INK } }, { text: '7 题，每题取前 5 条', options: { bold: true, color: INK } },
     { text: '1.00', options: { bold: true, color: INK } }, { text: '0.929', options: { bold: true, color: RED } }, { text: '中位 18.2', options: { bold: true, color: INK } }],
  ];
  table(s, rows, { x: L, y: 2.18, w: 6.6, colW: [0.62, 2.78, 1.1, 1.05, 1.05], rowH: 0.42, fill: { color: CREAM } });
  s.addChart('bar', [{ name: 'NDCG@5', labels: ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7'], values: [1, 1, 1, 1, 1, 0.5, 1] }], {
    x: 7.95, y: 2.18, w: 4.3, h: 2.5, barDir: 'col', barGapWidthPct: 70,
    chartColors: [INK], chartColorsOpacity: 100,
    chartArea: { fill: { color: CREAM } }, plotArea: { fill: { color: CREAM } },
    showLegend: false, showValue: true, dataLabelPosition: 'outEnd', dataLabelFontFace: BODY, dataLabelFontSize: 10, dataLabelColor: GREY_D, dataLabelFormatCode: '0.00',
    catAxisLabelFontFace: BODY, catAxisLabelFontSize: 10, catAxisLabelColor: GREY_D, catAxisLineShow: false,
    valAxisHidden: true, valAxisMinVal: 0, valAxisMaxVal: 1.2, valGridLine: { style: 'none' }, catGridLine: { style: 'none' },
  });
  card(s, { x: 7.95, y: 4.82, w: 4.3, h: 0.92, fill: RED, value: 'Q6 目标记录排在第三位', vs: 15, label: 'Recall@5 仍为 1.00，NDCG@5 为 0.50；单看召回会漏掉排序这件事', ls: 9.5 });
  card(s, { x: 7.95, y: 5.86, w: 4.3, h: 0.5, fill: 'none', value: '14.4 – 24.7 ms', unit: '单题耗时区间，中位 18.2', vs: 17 });
  note(s, '来源：03 佐证表 2、§2；03 计划书 §4、§6。Q6 前五名依次为 EV-ACC-CA07、EV-PDB-3GBM、EV-STEM-HEADLESS、EV-UP-P03452、EV-PDB-3GBN。');
}

function s10(s) {
  frame(s, { kicker: '04 两类任务实测' });
  headline(s, '四份已发表方案，五列对照：版本、空白、等级计数与交叉标识', 28);
  sub(s, '不打综合疗效分；对照表只排已经点名的记录与证据等级，交给专家签批。', 1.92);
  const rows = [
    [th('档案'), th('版本一致'), th('空白数'), th('等级计数（实验登录/监测/文献或审校/计算预测）'), th('注释中的交叉标识'), th('空白明细')],
    ['参考株', '是', '1', '0 / 2 / 5 / 0', '无', '缺实验登录'],
    [cellRed('共识文献'), cellRed('否'), cellRed('5'), '0 / 0 / 3 / 0', { text: 'PMID:26912624 与 PMID:38819164', options: { bold: true, color: RED } }, '版本不一致、缺监测、审阅未关闭'],
    ['头部糖基化', '是', '2', '0 / 0 / 3 / 0', '无', '缺实验登录与监测'],
    [cellRed('保守茎部'), cellRed('否'), cellRed('2'), '6 / 0 / 5 / 0', '无', '版本不一致、缺监测；6 条实验登录来自结构与表位库'],
  ];
  table(s, rows, { x: L, y: 2.40, w: CW, colW: [1.42, 0.95, 0.8, 2.45, 2.5, 3.01], rowH: 0.5, fontSize: 10, fill: { color: CREAM } });
  const c = cols(3, 0.19, L, CW);
  [{ kick: '与金标一致', value: '4/4', label: '空白项、交叉与版本判断均与金标相同', fill: INK },
   { kick: '档案比较耗时', value: '16.9', unit: 'ms', label: '不重新检索全文，直接排出来源、版本、交叉与等级四列', fill: 'none' },
   { kick: '空白项的定义', value: '缺等级 / 版本不一致 / 审阅未关闭', vs: 12, label: '三类情况都计入空白数', fill: 'none' }]
    .forEach((o, i) => card(s, Object.assign(o, { x: c.at(i), y: 5.20, w: c.cw, h: 1.12, vs: o.vs || 22, ls: 9 })));
  note(s, '来源：03 佐证表 3 及随后说明；03 计划书 §3.4、§4。');
}

function s11(s) {
  frame(s, { kicker: '05 签批与性能' });
  headline(s, '专家签批之前，报告一直是草稿', 32);
  sub(s, '每条引文可采纳或标疑，审计留有版本；疗效语句在进入采纳列表之前被单独拦住。');
  const stages = [
    { t: '草稿', b: '检索与核验通过的候选引文\n报告状态：草稿', w: 3.1, fill: PALE, c: INK },
    { t: '采纳 23 / 标疑 1', b: '逐条判定；EV-CONS-CARTER 标疑\n疗效语句探针 1 条被拒', w: 3.85, fill: RED, c: SNOW },
    { t: '专家已签 · 导出', b: '会后只导出已经签批的版本\n签批耗时 11.5 毫秒', w: 3.1, fill: INK, c: SNOW },
  ];
  let x = L;
  stages.forEach((st, i) => {
    box(s, x, 2.46, st.w, 1.5, st.fill, st.fill === PALE ? RULEC : null);
    tx(s, st.t, { x: x + 0.14, y: 2.68, w: st.w - 0.28, h: 0.38, fontSize: 16, bold: true, fontFace: HEAD, color: st.c, align: 'center' });
    tx(s, st.b, { x: x + 0.14, y: 3.14, w: st.w - 0.28, h: 0.66, fontSize: 10.5, color: st.fill === PALE ? GREY_D : SILVER, align: 'center', lineSpacingMultiple: 1.25 });
    x += st.w;
    if (i < 2) { stepArrow(s, x + 0.07, 3.06); x += 0.54; }
  });
  const c = cols(3, 0.19, L, CW);
  [{ kick: '循证问答 · 中位', value: '18.2', unit: 'ms', label: '7 题中位；单题 14.4–24.7 毫秒', fill: INK },
   { kick: '四份档案比较', value: '16.9', unit: 'ms', label: '不重新检索全文，直接排四列', fill: 'none' },
   { kick: '专家签批', value: '11.5', unit: 'ms', label: '演示时间花在读对照表，不花在等待计算', fill: 'none' }]
    .forEach((o, i) => card(s, Object.assign(o, { x: c.at(i), y: 4.14, w: c.cw, h: 1.42, vs: 34, ls: 10 })));
  box(s, L, 5.68, CW, 0.62, INK);
  tx(s, '本地完成，可断网重跑：快照、检索与签批均在本机；仓库运行记录为 Windows 与 Python 3.13；重排器与判别器都在单机 CPU 前向。', { x: L + 0.22, y: 5.86, w: CW - 0.44, h: 0.3, fontSize: 11.5, bold: true, color: SNOW });
  note(s, '来源：03 计划书 §3.5、§7、§8；03 佐证附录（内网部署的账号与留存标为待联调，没有报价）。');
}

function s12(s) {
  frame(s, { kicker: '05 签批与性能' });
  headline(s, '标准答案与档案金标都落在 fluevidence-v1.1 之内', 30);
  sub(s, '方法学夹具单独报告，不混进主结果；评测只使用已发表的题名、定义行、结构库题名、表位摘要与蛋白质条目首行。');
  const panels = [
    { title: '主任务（计入主结果）', fill: INK, rows: [['证据问答', '7 题，前 5 条'], ['Recall@5 / NDCG@5', '1.00 / 0.929'], ['问答耗时中位', '18.2 毫秒'], ['档案对照', '4 份 · 4/4'], ['有效引用', '59/59'], ['签批 采纳 / 标疑', '23 / 1']] },
    { title: '方法学夹具（单独报告）', fill: 'none', rows: [['查询', '4 条'], ['Recall@3 / NDCG@3', '1.00 / 0.875'], ['查询耗时中位', '5.8 毫秒'], ['比较 / 签批', '4.7 / 4.1 毫秒'], ['采纳引文', '2 条'], ['引用 / 拦截无效草稿', '16/16 · 3/3']] },
  ];
  const c = cols(2, 0.24, L, 8.1);
  panels.forEach((p, i) => {
    const x = c.at(i), dark = p.fill === INK;
    if (dark) box(s, x, 2.52, c.cw, 3.8, INK); else box(s, x, 2.52, c.cw, 3.8, CREAM, RULEC);
    tx(s, p.title, { x: x + 0.22, y: 2.72, w: c.cw - 0.44, h: 0.3, fontSize: 13, bold: true, color: dark ? SNOW : INK });
    p.rows.forEach((r, j) => {
      const y = 3.22 + j * 0.5;
      tx(s, r[0], { x: x + 0.22, y: y + 0.05, w: 1.85, h: 0.3, fontSize: 10, color: dark ? SILVER : GREY });
      tx(s, r[1], { x: x + 2.1, y, w: c.cw - 2.32, h: 0.34, fontSize: 13, bold: true, fontFace: HEAD, color: dark ? SNOW : INK, align: 'right' });
      if (j < 5) rule(s, x + 0.22, y + 0.42, c.cw - 0.44, dark ? '3A3A3A' : RULEC);
    });
  });
  box(s, 9.44, 2.52, 2.79, 3.8, PALE, RULEC);
  tx(s, '评测集就是这 24 条锁定记录', { x: 9.66, y: 2.72, w: 2.35, h: 0.3, fontSize: 12, bold: true, color: INK });
  tx(s, '· 问答标准答案与档案金标都在 24 条之内\n\n· 题名不转写成疗效结论\n\n· 夹具 4 题与主任务 7 题使用不同问题集\n\n· 计算预测记录 0 条\n\n· 换快照时七题与四份档案留作回归', { x: 9.66, y: 3.16, w: 2.35, h: 3.0, fontSize: 10, color: GREY_D, lineSpacingMultiple: 1.2 });
  note(s, '来源：03 佐证 §1、§3、§4；03 计划书 §6。脚注：人工检索 SOP 在评测记录中为未测，本页不设人工对照栏。');
}

function s13(s) {
  frame(s, { kicker: '06 权重与验收' });
  headline(s, '四份权重合计 11,748 字节，哈希与对数几率误差均已核对', 28);
  const rows = [
    [th('模型'), th('训练 / 验证 / 测试'), th('选定轮次'), th('验证损失'), th('宏平均 F1  验证 / 测试'), th('NDCG@3  验证 / 测试')],
    ['重排器（362 参数）', '143 / 48 / 48', '第 15 轮', '0.413', '1.00 / 0.43', '1.00 / 0.969'],
    ['判别器（387 参数）', '432 / 144 / 144', '第 220 轮', '0.001', '1.00 / 1.00', '—'],
  ];
  table(s, rows, { x: L, y: 2.22, w: CW, colW: [2.35, 2.0, 1.45, 1.4, 2.0, 1.93], rowH: 0.52, fill: { color: CREAM } });
  const c = cols(4, 0.19, L, CW);
  [{ kick: '四份权重合计', value: '11,748', unit: '字节', label: '重排 3,879 + 可移植 1,898 + 判别 3,973 + 可移植 1,998 字节', fill: INK },
   { kick: '对数几率误差', value: '2.4E-07', vs: 24, label: '重排器留出 48 行；判别器 144 行为 9.5E-07', fill: RED },
   { kick: 'CPU 单样本热运行中位', value: '0.015', unit: 'ms', label: '可移植格式 0.008 毫秒；单机 CPU 前向', fill: 'none' },
   { kick: '训练语料', value: '合成句 · 不含流感快照', vs: 14, label: '两套权重用不同领域合成句训练，快照不参与训练', fill: 'none' }]
    .forEach((o, i) => card(s, Object.assign(o, { x: c.at(i), y: 3.92, w: c.cw, h: 1.5, vs: o.vs || 28, ls: 9.5 })));
  box(s, L, 5.54, CW, 0.78, PALE, RULEC);
  tx(s, '部署与校验', { x: L + 0.22, y: 5.68, w: 2.0, h: 0.3, fontSize: 12, bold: true, color: RED });
  tx(s, '部署按「快照更新 / 检索服务 / 签批留存」三项分列，全部可在本地复跑；权重校验入口 weights/verify_weights.py，评测入口 mbenchmarks.flu_bench。商务报价留待试点核定，内网部署的账号与留存标为待联调。', { x: L + 2.4, y: 5.66, w: 8.5, h: 0.58, fontSize: 10, color: GREY_D, lineSpacingMultiple: 1.2 });
  note(s, '来源：03 佐证 §4 表 4 与随后段落、§5 附录；03 计划书 §7。');
}

function s14(s) {
  frame(s, { kicker: '06 权重与验收' });
  headline(s, '把公开标识、版本与证据等级留在每一条被采纳的句子上', 28);
  sub(s, '相邻工具按通用检索组织答案，或按序列与结构打分组织候选；本系统输出可签批的句子与同一张四方案对照表。');
  const rows = [
    [th('维度'), th('通用文献检索工具'), th('蛋白设计打分平台'), th('FluVax-Evidence', { fill: { color: RED } })],
    ['组织方式', '按关键词与相关度组织答案', '按序列或结构打分组织候选', { text: '按锁定快照的记录与版本组织证据', options: { bold: true, color: INK } }],
    ['标识与版本', '不保证落到每一句上', '以分数为主', { text: '每条被采纳句子都带公开标识与数据版本', options: { bold: true, color: INK } }],
    ['既有方案比较', '按检索结果列举', '按打分排序候选', { text: '四份已发表方案排成同一张五列对照表', options: { bold: true, color: INK } }],
    ['复核与留痕', '由使用者自行记录', '由使用者自行记录', { text: '采纳 / 标疑、草稿态与审计版本', options: { bold: true, color: INK } }],
  ];
  table(s, rows, { x: L, y: 2.46, w: CW, colW: [1.75, 3.1, 3.1, 3.18], rowH: 0.7, fill: { color: CREAM } });
  note(s, '来源：03 计划书 §4 末段、§5。');
}

function s15(s) {
  frame(s, { kicker: '06 权重与验收' });
  headline(s, '换快照时，五项验收一起重跑', 32);
  sub(s, '单看召回会漏掉第 6 题排在第三位这件事，因此召回、排序、档案一致、引用锁与疗效探针五项一起看。');
  const c = cols(5, 0.17);
  [{ n: '01', v: '1.00', l: 'Recall@5（7 题）', fill: INK }, { n: '02', v: '0.929', l: 'NDCG@5（7 题平均）', fill: RED },
   { n: '03', v: '4/4', l: '四份档案与金标一致', fill: INK }, { n: '04', v: '59/59', l: '已采纳语句与版本锁一致', fill: RED },
   { n: '05', v: '1 拒', l: '疗效承诺探针被拒（签批 23 / 1）', fill: 'none' }]
    .forEach((o, i) => card(s, { x: c.at(i), y: 2.52, w: c.cw, h: 1.66, fill: o.fill, kick: o.n, value: o.v, vs: 32, label: o.l, ls: 9.5 }));
  rule(s, L + 0.3, 4.95, CW - 0.6, RULEC, 1);
  const tl = [{ d: '11-30', t: '初赛材料截止', x: L + 0.3 }, { d: '12-01 – 12-03', t: '线上评审', x: L + 4.4 }, { d: '12 月中旬', t: '路演', x: L + 8.6 }];
  tl.forEach(e => {
    s.addShape('ellipse', { x: e.x - 0.07, y: 4.88, w: 0.14, h: 0.14, fill: { color: RED }, line: { type: 'none' } });
    tx(s, e.d, { x: e.x - 0.05, y: 5.12, w: 2.4, h: 0.3, fontSize: 15, bold: true, fontFace: HEAD, color: INK });
    tx(s, e.t, { x: e.x - 0.05, y: 5.44, w: 2.4, h: 0.3, fontSize: 11, color: GREY_D });
  });
  box(s, L, 5.86, CW, 0.46, INK);
  tx(s, 'FluVax-Evidence · 盼盼法式小面包 · 人工智能+医疗健康赛道 AI-HEALTH-Q40 · 报名编号 REG-2026-000525', { x: L + 0.22, y: 5.97, w: CW - 0.44, h: 0.3, fontSize: 11.5, bold: true, color: SNOW });
  note(s, '来源：03 计划书 §10。换一批内部资料时沿用同一条链：入库即写版本与时间，检索仍是词频、向量与图，采纳仍要求逐字对上原文。');
}

const BUILDERS = [s01, s02, s03, s04, s05, s06, s07, s08, s09, s10, s11, s12, s13, s14, s15];

function build() {
  const pptx = new PptxGenJS();
  pptx.defineLayout({ name: 'FLUVAX', width: SLIDE_W, height: SLIDE_H });
  pptx.layout = 'FLUVAX';
  pptx.theme = { headFontFace: HEAD, bodyFontFace: BODY };
  pptx.title = 'FluVax-Evidence 答辩 PPT';
  pptx.author = '盼盼法式小面包';
  pptx.company = '盼盼法式小面包';
  pptx.defineSlideMaster({ title: 'BASE', background: { color: CREAM } });
  BUILDERS.forEach(fn => { const s = pptx.addSlide({ masterName: 'BASE' }); fn(s); });
  return pptx;
}
build().writeFile({ fileName: path.join(__dirname, '人工智能+医疗健康赛道-FluVax-Evidence-盼盼法式小面包-答辩PPT.pptx') })
  .then(f => console.log('wrote ' + f)).catch(e => { console.error(e); process.exit(1); });
