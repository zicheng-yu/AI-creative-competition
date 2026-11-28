const { pres, C, F, N, S, T, R, L, A, chrome, title, stat, hbar, kick } = require('./lib');
const SRC1 = '来源：项目计划书 摘要、表 1；佐证材料 表 2、表 3、表 4';

// ===== 1 cover
{
  const s = pres.addSlide(); s.background = { color: C.bg };
  R(s, 0.5, 0.29, 0.1, 0.1, C.red);
  T(s, '首届江苏省“人工智能+”创新应用大赛   ·   人工智能+工业制造赛道', { x: 0.7, y: 0.2, w: 8, h: 0.28, fontSize: 10.5, bold: true, charSpacing: 1.5 });
  L(s, 0.5, 0.56, 8.1, 0, C.ink, 0.75);
  T(s, '赛题 AI-MFG-Q21 · 电气图纸智能解析与 BOM 自动生成', { x: 0.5, y: 1.25, w: 8, h: 0.35, fontSize: 15, bold: true, color: C.red });
  T(s, [{ text: 'Electronic', options: { color: C.ink } }, { text: 'BOM', options: { color: C.red } }], { x: 0.45, y: 1.7, w: 8.2, h: 1.35, fontFace: N, fontSize: 70, valign: 'middle' });
  T(s, 'Symbols, netlists and BOMs from switchgear drawings', { x: 0.5, y: 3.1, w: 8, h: 0.45, fontFace: S, italic: true, fontSize: 20, color: C.grey });
  T(s, '成套电气图纸的符号、网表与物料清单', { x: 0.5, y: 3.72, w: 8, h: 0.6, fontSize: 30, bold: true });
  L(s, 0.5, 4.75, 8.1, 0, C.rule, 0.75);
  const info = [['团队', '盼盼法式小面包 · 创新组'], ['报名编号', 'REG-2026-000523'], ['命题单位', '中国联合网络通信有限公司镇江市分公司'], ['日期', '2026 年 11 月']];
  info.forEach((r, i) => {
    T(s, r[0], { x: 0.5, y: 4.95 + i * 0.42, w: 1.3, h: 0.34, fontSize: 12, color: C.grey });
    T(s, r[1], { x: 1.8, y: 4.95 + i * 0.42, w: 6.5, h: 0.34, fontSize: 14, bold: true });
  });
  // right crimson block with netlist motif
  R(s, 9.0, 0, 4.333, 7.5, C.red);
  R(s, 9.0, 5.9, 4.333, 1.6, C.ink);
  // motif: busbar + feeders
  const wc = 'FFFFFF';
  R(s, 9.55, 1.15, 0.9, 0.5, null, wc); T(s, '进线', { x: 9.55, y: 1.15, w: 0.9, h: 0.5, fontSize: 12, color: wc, align: 'center', valign: 'middle', bold: true });
  L(s, 10.0, 1.65, 0, 0.75, wc, 1.25);
  R(s, 9.55, 2.4, 3.3, 0.09, wc);
  T(s, '母线', { x: 11.95, y: 2.02, w: 0.9, h: 0.3, fontSize: 11, color: wc, align: 'right' });
  [9.9, 11.0, 12.1].forEach((x, i) => {
    L(s, x + 0.25, 2.49, 0, 0.7, wc, 1.25);
    s.addShape(pres.shapes.OVAL, { x: x + 0.17, y: 2.98, w: 0.16, h: 0.16, fill: { color: wc }, line: { type: 'none' } });
    R(s, x, 3.2, 0.5, 0.5, null, wc); T(s, 'QF', { x, y: 3.2, w: 0.5, h: 0.5, fontSize: 10.5, color: wc, align: 'center', valign: 'middle', fontFace: N });
    L(s, x + 0.25, 3.7, 0, 0.55, wc, 1.25, 'dash');
    T(s, '馈出 ' + (i + 1), { x: x - 0.2, y: 4.3, w: 0.9, h: 0.3, fontSize: 10.5, color: wc, align: 'center' });
  });
  T(s, '图纸  →  符号  →  网表  →  清单', { x: 9.45, y: 4.95, w: 3.6, h: 0.4, fontSize: 15, bold: true, color: wc });
  T(s, [{ text: '一次系统图 · 二次控制图', options: { breakLine: true } }, { text: '矢量 / 单页 PDF / 光栅' }], { x: 9.45, y: 6.15, w: 3.6, h: 0.9, fontSize: 13, color: wc, bold: true });
}

// ===== 2 agenda
{
  const s = pres.addSlide(); chrome(s, 2, '00 目录', '');
  title(s, ['从一张已发出的图纸，到可计算网表、物料清单与合规红灯'], '答辩分六部分，每部分落在一项已经测出来的结果上');
  const items = [
    ['01', '核心成绩', '主集 11 张越过两条赛题门槛', '03'],
    ['02', '问题与场景', '成套柜报价与来图初审的难点在网表', '04'],
    ['03', '技术路线', '四层架构 · 三种来图 · 端口追线 · 四类红灯', '05–09'],
    ['04', '交互与清单', '共用器件编号的定位、修订复检与导出', '10–11'],
    ['05', '冻结评测', 'ElectroBench-JS v1.0.0、基线与消融、退化图', '12–14'],
    ['06', '部署与试点', '内网单机部署、三步试点与验收读数', '15–16'],
  ];
  items.forEach((it, i) => {
    const y = 2.0 + i * 0.8;
    T(s, it[0], { x: 0.5, y, w: 0.9, h: 0.62, fontFace: N, fontSize: 30, color: C.red, valign: 'middle' });
    T(s, it[1], { x: 1.5, y: y + 0.02, w: 2.2, h: 0.6, fontSize: 19, bold: true, valign: 'middle' });
    T(s, it[2], { x: 3.75, y: y + 0.02, w: 3.9, h: 0.6, fontSize: 12.5, color: C.grey, valign: 'middle' });
    T(s, 'P' + it[3], { x: 7.45, y: y + 0.02, w: 0.85, h: 0.6, fontSize: 11, color: C.grey, align: 'right', valign: 'middle' });
    L(s, 0.5, y + 0.71, 7.8, 0, C.rule, 0.5);
  });
  // right black panel: what it delivers
  R(s, 8.75, 1.95, 4.083, 4.85, C.ink);
  kick(s, '一次输出四样东西', 9.05, 2.18, 3.5, 'F3A6A9');
  const out = [['符号', '40 类符号的检测框与位号'], ['规格', '邻近标注按距离与读写方向绑定'], ['网表', '端口级节点、边，有向/无向可算'], ['清单', '类别、位号、规格、数量，可筛选导出']];
  out.forEach((o, i) => {
    const y = 2.6 + i * 0.86;
    R(s, 9.05, y + 0.08, 0.08, 0.5, C.red);
    T(s, o[0], { x: 9.3, y, w: 3.3, h: 0.34, fontSize: 16, bold: true, color: C.white });
    T(s, o[1], { x: 9.3, y: y + 0.36, w: 3.4, h: 0.3, fontSize: 11.5, color: 'C8C8C8' });
  });
  T(s, '+ 四类合规红灯落到器件，附条文编号、来源与摘要', { x: 9.05, y: 6.1, w: 3.6, h: 0.55, fontSize: 12, bold: true, color: 'F3A6A9' });
}

// ===== 3 results
{
  const s = pres.addSlide(); chrome(s, 3, '01 核心成绩', SRC1);
  title(s, ['主集 11 张：综合解析 ', ['97.88%'], '，严格明细 ', ['96.92%'], '，均过门槛'], '冻结主集 = 一次图 4 张 + 二次图 3 张 + 缺陷图 4 张；矢量通道，报价主路径');
  const cw = 2.92, gap = 0.218;
  const cards = [
    { num: '97.88', unit: '%', label: '综合解析', sub: '赛题门槛 ≥ 93%\n符号 F1·0.40 + 规格语义·0.35 + 无向边 F1·0.25', theme: 'dark' },
    { num: '96.92', unit: '%', label: '严格明细完整率', sub: '赛题门槛 ≥ 95%\n类别、数量、规格语义与真值一致', theme: 'red' },
    { num: '0.07', unit: ' 秒/张', label: '端到端平均耗时', sub: 'P50 0.066 秒 · P95 0.106 秒\n解析 + 追线 + 合规全流程', theme: 'dark' },
    { num: '5/0/0', unit: '', label: '四类红灯 TP / FP / FN', sub: '误报、漏报均为 0\n7 张标准图无红灯误报', theme: 'red' },
  ];
  cards.forEach((c, i) => stat(s, Object.assign({ x: 0.5 + i * (cw + gap), y: 1.92, w: cw, h: 2.35, ns: 40, ss: 10.5 }, c)));
  // threshold bars
  kick(s, '实测 vs 赛题门槛（0–100%）', 0.5, 4.55, 6);
  const bx = 2.2, bw = 4.3;
  [['综合解析', 97.88, 93], ['严格明细', 96.92, 95]].forEach((r, i) => {
    const y = 5.0 + i * 0.85;
    T(s, r[0], { x: 0.5, y: y - 0.02, w: 1.6, h: 0.4, fontSize: 13, bold: true, valign: 'middle' });
    hbar(s, bx, y, bw, 0.36, r[1], 100, i ? C.red : C.ink, r[1].toFixed(2) + '%', { fs: 12.5 });
    const tx = bx + bw * r[2] / 100;
    L(s, tx, y - 0.12, 0, 0.6, C.red, 1.5, 'dash');
    T(s, '门槛 ' + r[2] + '%', { x: tx - 0.6, y: y + 0.42, w: 1.2, h: 0.24, fontSize: 9.5, color: C.red, align: 'center' });
  });
  // timing stack
  kick(s, '0.070 秒拆分（主集均值）', 7.2, 4.55, 5);
  const tx0 = 7.2, tw = 5.633;
  const seg = [['解析', 0.044, C.ink], ['追线', 0.022, C.red], ['合规', 0.004, C.mid]];
  let x = tx0;
  seg.forEach(sg => { const w = tw * sg[1] / 0.070; R(s, x, 5.0, w, 0.36, sg[2]); x += w; });
  T(s, '解析 0.044', { x: tx0, y: 4.78, w: 2, h: 0.22, fontSize: 10, color: C.grey });
  T(s, '追线 0.022', { x: tx0 + tw * 0.044 / 0.07, y: 4.78, w: 1.6, h: 0.22, fontSize: 10, color: C.grey });
  T(s, '合规 0.004', { x: tx0 + tw - 1.2, y: 5.4, w: 1.2, h: 0.22, fontSize: 10, color: C.grey, align: 'right' });
  const rows = [['阶段', '均值', 'P50', 'P95'], ['解析', '0.044', '0.039', '0.077'], ['追线', '0.022', '0.021', '0.027'], ['合规', '0.004', '0.004', '0.006'], ['合计', '0.070', '0.066', '0.106']];
  rows.forEach((r, i) => {
    const y = 5.7 + i * 0.25;
    r.forEach((c, j) => T(s, c, { x: tx0 + j * 1.408, y, w: 1.4, h: 0.24, fontSize: 10.5, bold: i === 0 || i === 4, color: i === 4 ? C.red : (i === 0 ? C.grey : C.ink), align: j ? 'right' : 'left' }));
    if (i === 0) L(s, tx0, y + 0.245, tw, 0, C.rule, 0.5);
  });
}

// ===== 4 pain + scene
{
  const s = pres.addSlide(); chrome(s, 4, '02 问题与场景', '来源：项目计划书 §1 背景与痛点、§10 实施计划；赛题 AI-MFG-Q21');
  title(s, ['难点在网表，不在识字：只认字得不到“母线到馈线”'], '成套柜报价与来图初审，要数清断路器、接触器、互感器和端子，再核对保护与回路');
  const pains = [
    ['01', '画法不统一', '图纸来自不同设计端：符号比例、图层、位号和简写都不统一，同一器件在不同图上写法不同。'],
    ['02', '二次图要追端子', '二次图要沿端子看清自锁、互锁和线圈的供电路径，才能核对控制回路。'],
    ['03', '没有连接就没法核对', '只做文字识别或画框，得不到“母线到馈线”“按钮到线圈”，级差和载流量无从核对。'],
  ];
  pains.forEach((p, i) => {
    const x = 0.5 + i * 2.72;
    L(s, x, 1.95, 2.5, 0, C.red, 2);
    T(s, p[0], { x, y: 2.05, w: 0.8, h: 0.5, fontFace: N, fontSize: 24, color: C.red });
    T(s, p[1], { x, y: 2.6, w: 2.5, h: 0.36, fontSize: 15, bold: true });
    T(s, p[2], { x, y: 3.0, w: 2.5, h: 1.15, fontSize: 11.5, color: C.grey, lineSpacingMultiple: 1.15 });
  });
  // comparison strip
  const y0 = 4.4;
  const row = (y, head, fill, fg, cells, verdict, vfill) => {
    R(s, 0.5, y, 1.55, 1.0, fill); T(s, head, { x: 0.6, y, w: 1.4, h: 1.0, fontSize: 12.5, bold: true, color: fg, valign: 'middle' });
    cells.forEach((c, j) => { const x = 2.15 + j * 1.6; R(s, x, y, 1.5, 1.0, c[1] ? C.pale : null, c[1] ? null : C.rule, c[1] ? null : 'dash'); T(s, c[0], { x: x + 0.08, y, w: 1.34, h: 1.0, fontSize: 11.5, align: 'center', valign: 'middle', color: c[1] ? C.ink : C.mid, bold: !!c[1] }); });
    R(s, 7.0, y, 1.15, 1.0, vfill); T(s, verdict, { x: 7.0, y, w: 1.15, h: 1.0, fontSize: 12, bold: true, color: C.white, align: 'center', valign: 'middle' });
  };
  row(y0, '只做 OCR / 画框', C.pale2, C.ink, [['文字\n位号', 1], ['器件框', 1], ['连接关系\n缺失', 0]], '无法核对\n级差·互锁', C.mid);
  row(y0 + 1.15, 'ElectronicBOM', C.ink, C.white, [['符号 + 位号\n+ 规格', 1], ['端口级\n网表', 1], ['四类规则\n沿网表检查', 1]], '红灯落到\n具体器件', C.red);
  // right: scene panel
  R(s, 8.6, 1.95, 4.233, 4.85, C.ink);
  kick(s, '首期场景 · 扬中、镇江成套开关柜', 8.85, 2.15, 3.9, 'F3A6A9');
  ['GGD', 'MNS', 'GCS', 'KYN28'].forEach((c, i) => {
    const x = 8.85 + (i % 2) * 1.92, y = 2.55 + Math.floor(i / 2) * 0.95;
    R(s, x, y, 1.82, 0.85, i === 3 ? C.red : '2A2A2A');
    T(s, c, { x, y, w: 1.82, h: 0.85, fontFace: N, fontSize: 22, color: C.white, align: 'center', valign: 'middle' });
  });
  T(s, '一次图：统计进线、母线、馈出元件\n二次图：核对启停、正反转、双电源', { x: 8.85, y: 4.5, w: 3.8, h: 0.62, fontSize: 11.5, color: 'D0D0D0', lineSpacingMultiple: 1.15 });
  kick(s, '赛题口径', 8.85, 5.22, 3, 'F3A6A9');
  [['图纸解析准确率', '≥ 93%'], ['物料清单完整率', '≥ 95%'], ['设计规范语义匹配', '支持']].forEach((r, i) => {
    const y = 5.55 + i * 0.4;
    T(s, r[0], { x: 8.85, y, w: 2.6, h: 0.34, fontSize: 12.5, color: C.white, valign: 'middle' });
    T(s, r[1], { x: 11.3, y, w: 1.3, h: 0.34, fontSize: 14, bold: true, color: C.white, align: 'right', valign: 'middle' });
    L(s, 8.85, y + 0.37, 3.75, 0, '444444', 0.5);
  });
}

// ===== 5 architecture
{
  const s = pres.addSlide(); chrome(s, 5, '03 技术路线 · 架构', '来源：项目计划书 §2 总体方案与架构、图 1；佐证材料 §1');
  title(s, ['四层架构：图纸、网表、告警、清单共用', ['同一器件编号']], '实线为主数据流，虚线框为旁路；三种来图进入同一套绑定、追线和评分');
  const layers = [
    ['交互', C.ink, [['图纸定位', '框、节点、告警'], ['文字查询', '回路与级差'], ['清单导出', '表格 / 结构化文件']], null],
    ['服务', C.ink, [['四类合规规则', '确定性规则'], ['条文编号与摘要', '编号、来源、摘要'], ['修订预览后复检', '确认后重跑']], ['条文资料', '']],
    ['算法', C.red, [['符号与文字', '40 类符号'], ['位号与规格绑定', '距离 + 读写方向'], ['端口追线与网表', '交叉与分支']], null],
    ['数据', C.ink, [['矢量图纸', '图元与文字直读'], ['单页 PDF', '文字 + 矢量原语'], ['光栅图', '离线 OCR + 模板']], ['冻结评测集', '14 张']],
  ];
  layers.forEach((ly, i) => {
    const y = 1.95 + i * 1.2;
    R(s, 0.5, y, 0.95, 0.95, ly[1]);
    T(s, ly[0], { x: 0.5, y, w: 0.95, h: 0.95, fontSize: 17, bold: true, color: C.white, align: 'center', valign: 'middle' });
    ly[2].forEach((c, j) => {
      const x = 1.6 + j * 1.95;
      R(s, x, y, 1.85, 0.95, i === 2 ? 'F7E3E4' : C.pale);
      T(s, c[0], { x: x + 0.12, y: y + 0.14, w: 1.65, h: 0.34, fontSize: 13, bold: true });
      T(s, c[1], { x: x + 0.12, y: y + 0.52, w: 1.65, h: 0.3, fontSize: 10.5, color: C.grey });
    });
    if (ly[3]) { R(s, 7.5, y, 1.25, 0.95, null, C.mid, 'dash'); T(s, ly[3][0] + (ly[3][1] ? '\n' + ly[3][1] : ''), { x: 7.5, y, w: 1.25, h: 0.95, fontSize: 11.5, align: 'center', valign: 'middle', color: C.grey, bold: true }); L(s, 7.45, y + 0.475, 0.05, 0, C.mid, 0.75, 'dash'); }
    if (i < 3) [2.52, 4.47, 6.42].forEach(ax => A(s, ax, y + 1.17, 0, -0.2, C.ink));
  });
  // right: score formula + limits
  const rx = 9.05, rw = 3.783;
  kick(s, '综合解析 = 三项加权', rx, 1.95, rw);
  const segs = [['符号 F1', 0.40, C.ink], ['规格语义', 0.35, C.red], ['无向边 F1', 0.25, C.mid]];
  let x = rx;
  segs.forEach(sg => { const w = rw * sg[1]; R(s, x, 2.3, w, 0.55, sg[2]); T(s, sg[1].toFixed(2), { x, y: 2.3, w, h: 0.55, fontFace: N, fontSize: 16, color: C.white, align: 'center', valign: 'middle' }); T(s, sg[0], { x, y: 2.9, w, h: 0.26, fontSize: 10.5, color: C.grey, align: 'center' }); x += w; });
  T(s, '严格明细：类别、数量和规格语义均与真值一致才算对', { x: rx, y: 3.3, w: rw, h: 0.5, fontSize: 11.5, color: C.ink });
  kick(s, '输入约束', rx, 4.0, rw);
  [['10', ' MB', '单文件上限'], ['1', ' 页', 'PDF 限单页'], ['1600', ' 万像素', '光栅上限']].forEach((r, i) => {
    const y = 4.35 + i * 0.82;
    R(s, rx, y, rw, 0.72, i === 0 ? C.ink : C.pale);
    T(s, [{ text: r[0], options: { fontFace: N, fontSize: 24, color: i === 0 ? C.white : C.red } }, { text: r[1], options: { fontSize: 12, bold: true, color: i === 0 ? C.white : C.ink } }], { x: rx + 0.18, y, w: 2.2, h: 0.72, valign: 'middle' });
    T(s, r[2], { x: rx + 2.2, y, w: rw - 2.35, h: 0.72, fontSize: 12.5, bold: true, color: i === 0 ? C.white : C.ink, align: 'right', valign: 'middle' });
  });
}

// ===== 6 channels
{
  const s = pres.addSlide(); chrome(s, 6, '03 技术路线 · 三种来图', '来源：项目计划书 表 1、§3.1；佐证材料 表 2、表 4。同一 11 张主集，三通道分列，不合成平均数');
  title(s, ['三种来图同一条流水线：矢量 ', ['97.88%'], '、', ['0.07 秒/张'], '，作报价主路径'], 'PDF 与光栅保留给扫描件，分数单独公布；明细在三条通道上都在 90% 以上');
  const ch = [['矢量', C.red], ['纯 PDF', C.ink], ['全光栅', C.mid]];
  const data = [['综合解析', [97.88, 77.32, 78.45]], ['无向边 F1', [95.83, 62.14, 60.89]], ['严格明细', [96.92, 92.95, 90.31]], ['可见汇总', [96.65, 92.34, 90.91]]];
  const bx = 1.9, bw = 5.3, bh = 0.2;
  data.forEach((d, i) => {
    const y = 1.98 + i * 0.86;
    T(s, d[0], { x: 0.5, y: y + 0.12, w: 1.35, h: 0.4, fontSize: 13, bold: true });
    d[1].forEach((v, j) => hbar(s, bx, y + j * 0.24, bw, bh, v, 100, ch[j][1], v.toFixed(2) + '%', { fs: 10.5, track: 'F2EEE9' }));
    L(s, 0.5, y + 0.8, 7.6, 0, C.rule, 0.5);
  });
  // channel descriptions w/ legend
  const desc = ['直接读取图元和文字，坐标与图块保持原样', '取页面文字和矢量原语，再从同页渲染图追导线', '离线文字识别，与视觉模板匹配符号'];
  ch.forEach((c, j) => {
    const x = 0.5 + j * 2.6;
    R(s, x, 5.55, 0.22, 0.22, c[1]);
    T(s, c[0], { x: x + 0.32, y: 5.5, w: 2, h: 0.32, fontSize: 13, bold: true });
    T(s, desc[j], { x, y: 5.9, w: 2.4, h: 0.8, fontSize: 11, color: C.grey });
  });
  // right speed panel
  R(s, 8.55, 1.95, 4.283, 4.85, C.ink);
  kick(s, '每张耗时（秒，均值）', 8.8, 2.15, 3.8, 'F3A6A9');
  const sp = [['矢量', 0.070, C.red, 'P50 0.066 · P95 0.106'], ['纯 PDF', 4.812, C.white, 'P50 4.85 · P95 5.09'], ['全光栅', 4.662, 'BDBDBD', 'P50 4.48 · P95 5.27']];
  sp.forEach((r, i) => {
    const y = 2.6 + i * 1.0;
    T(s, r[0], { x: 8.8, y, w: 1.2, h: 0.3, fontSize: 12.5, bold: true, color: C.white });
    T(s, r[3], { x: 10.0, y, w: 2.6, h: 0.3, fontSize: 10, color: 'AFAFAF', align: 'right' });
    hbar(s, 8.8, y + 0.36, 2.9, 0.3, r[1], 5.0, r[2], r[1].toFixed(3), { notrack: true, tc: C.white, fs: 12, font: N, lw: 0.9 });
  });
  T(s, [{ text: '0.070', options: { fontFace: N, fontSize: 40, color: C.white } }, { text: ' 秒', options: { fontSize: 16, bold: true, color: C.white } }], { x: 8.8, y: 5.55, w: 3.8, h: 0.7, valign: 'bottom' });
  T(s, '矢量主集解析 + 追线 + 合规合计', { x: 8.8, y: 6.3, w: 3.8, h: 0.3, fontSize: 11, color: 'C8C8C8' });
}

// ===== 7 netlist
{
  const s = pres.addSlide(); chrome(s, 7, '03 技术路线 · 网表', '来源：项目计划书 §3.2、§4、§6；佐证材料 表 2');
  title(s, ['位号、规格、端口落在同一器件：GGD 样图 ', ['24 个符号、23 条边']], '一条流水线同时交出检测框、规格和可计算网表，评分也按这三项加权');
  const steps = [['01', '符号与文字', '识别 40 类符号的检测框与邻近文字'], ['02', '位号与规格绑定', '按距离和读写方向绑定；无 TMY/LMY 标注的母排规格留空，计入遗漏'], ['03', '端口追线', '从器件端口出发，处理交叉和分支，输出节点、边和端口']];
  steps.forEach((st, i) => {
    const x = 0.5 + i * 2.66;
    R(s, x, 1.95, 2.46, 1.55, i === 2 ? C.red : C.pale);
    const fg = i === 2 ? C.white : C.ink;
    T(s, st[0], { x: x + 0.18, y: 2.05, w: 0.8, h: 0.42, fontFace: N, fontSize: 20, color: i === 2 ? C.white : C.red });
    T(s, st[1], { x: x + 0.18, y: 2.5, w: 2.25, h: 0.32, fontSize: 14, bold: true, color: fg });
    T(s, st[2], { x: x + 0.18, y: 2.84, w: 2.16, h: 0.62, fontSize: 10.5, color: i === 2 ? 'F6D5D6' : C.grey });
    if (i < 2) A(s, x + 2.48, 2.72, 0.16, 0, C.ink);
  });
  // schematic 1: primary
  const py = 3.85;
  kick(s, '一次图 → 进线 · 母线 · 馈出', 0.5, py, 4);
  R(s, 0.5, py + 0.4, 3.9, 2.45, null, C.rule);
  R(s, 0.75, py + 0.6, 0.85, 0.42, C.ink); T(s, '进线', { x: 0.75, y: py + 0.6, w: 0.85, h: 0.42, fontSize: 11.5, bold: true, color: C.white, align: 'center', valign: 'middle' });
  L(s, 1.175, py + 1.02, 0, 0.45, C.ink, 1.5);
  R(s, 0.75, py + 1.47, 3.4, 0.08, C.red); T(s, '母线', { x: 3.3, y: py + 1.15, w: 0.85, h: 0.28, fontSize: 10.5, color: C.red, align: 'right', bold: true });
  [0.95, 2.05, 3.15].forEach((x, i) => {
    L(s, x + 0.3, py + 1.55, 0, 0.35, C.ink, 1.5);
    R(s, x, py + 1.9, 0.6, 0.42, C.pale2); T(s, '馈出', { x, y: py + 1.9, w: 0.6, h: 0.42, fontSize: 10.5, align: 'center', valign: 'middle' });
    s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: py + 1.5, w: 0.1, h: 0.1, fill: { color: C.ink }, line: { type: 'none' } });
  });
  T(s, '节点 = 器件端口　边 = 导线连接', { x: 0.75, y: py + 2.42, w: 3.5, h: 0.3, fontSize: 10, color: C.grey });
  // schematic 2: secondary
  const sx = 4.6;
  kick(s, '二次图 → 按钮 · 触点 · 线圈 · 指示', sx, py, 4);
  R(s, sx, py + 0.4, 3.65, 2.45, null, C.rule);
  ['按钮', '触点', '线圈', '指示'].forEach((t, i) => {
    const x = sx + 0.2 + i * 0.85;
    R(s, x, py + 1.2, 0.65, 0.5, i === 2 ? C.red : C.pale2);
    T(s, t, { x, y: py + 1.2, w: 0.65, h: 0.5, fontSize: 11, bold: true, align: 'center', valign: 'middle', color: i === 2 ? C.white : C.ink });
    if (i < 3) L(s, x + 0.65, py + 1.45, 0.2, 0, C.ink, 1.5);
  });
  L(s, sx + 0.2, py + 0.85, 3.2, 0, C.ink, 1, 'dash'); T(s, '控制电源', { x: sx + 0.2, y: py + 0.55, w: 1.5, h: 0.26, fontSize: 10, color: C.grey });
  T(s, '自锁、互锁、线圈供电路径都在网表里可查', { x: sx + 0.2, y: py + 1.95, w: 3.3, h: 0.5, fontSize: 10.5, color: C.grey });
  // right stat stack
  const rx = 8.55, rw = 4.283;
  stat(s, { x: rx, y: 1.95, w: rw * 0.48, h: 1.55, num: '24', unit: ' 个', label: 'GGD 符号实例', theme: 'dark', ns: 34, ls: 12 });
  stat(s, { x: rx + rw * 0.52, y: 1.95, w: rw * 0.48, h: 1.55, num: '23', unit: ' 条', label: 'GGD 网表边', theme: 'red', ns: 34, ls: 12 });
  const rows = [['主集符号 F1', '100%'], ['主集无向边 F1', '95.83%'], ['主集有向边 F1', '90.66%'], ['可见字段汇总完整率', '96.65%'], ['一次图 4 张综合', '98.48%']];
  rows.forEach((r, i) => {
    const y = 3.8 + i * 0.6;
    T(s, r[0], { x: rx, y, w: 2.6, h: 0.5, fontSize: 12.5, valign: 'middle' });
    T(s, r[1], { x: rx + 2.3, y, w: rw - 2.3, h: 0.5, fontFace: N, fontSize: 20, color: i === 0 ? C.red : C.ink, align: 'right', valign: 'middle' });
    L(s, rx, y + 0.55, rw, 0, C.rule, 0.5);
  });
}

// ===== 8 tracing vs naive
{
  const s = pres.addSlide(); chrome(s, 8, '03 技术路线 · 追线消融', '来源：项目计划书 §5 创新点、§6；佐证材料 表 5、表 6');
  title(s, ['完整追线比“就近连端口”：无向边 F1 高 ', ['31.69 个百分点']], '同一 11 张主集、同一评分口径，只换连线方法');
  R(s, 0.5, 1.95, 4.1, 4.85, C.red);
  T(s, '无向边 F1 提升', { x: 0.75, y: 2.15, w: 3.6, h: 0.35, fontSize: 14, bold: true, color: C.white });
  T(s, '+31.69', { x: 0.7, y: 2.6, w: 3.8, h: 1.2, fontFace: N, fontSize: 64, color: C.white, valign: 'middle' });
  T(s, '个百分点 · 64.13% → 95.83%', { x: 0.75, y: 3.85, w: 3.6, h: 0.35, fontSize: 14, bold: true, color: C.white });
  L(s, 0.75, 4.45, 3.6, 0, 'E58A8F', 0.75);
  [['+7.92', '综合解析 个百分点'], ['+20.00', '红灯召回 个百分点']].forEach((r, i) => {
    const y = 4.65 + i * 1.0;
    T(s, r[0], { x: 0.75, y, w: 1.9, h: 0.7, fontFace: N, fontSize: 28, color: C.white, valign: 'middle' });
    T(s, r[1], { x: 2.65, y, w: 1.85, h: 0.7, fontSize: 12, bold: true, color: 'F6D5D6', valign: 'middle' });
  });
  // methods
  const mx = 4.95;
  [['朴素连线', '就近连端口：把导线端点接到最近的器件端口', C.mid], ['完整追线', '从器件端口出发沿导线追踪，处理交叉和分支', C.red]].forEach((m, i) => {
    const x = mx + i * 3.98;
    R(s, x, 1.95, 3.85, 0.95, C.pale);
    R(s, x, 1.95, 0.08, 0.95, m[2]);
    T(s, m[0], { x: x + 0.25, y: 2.03, w: 3.4, h: 0.32, fontSize: 14, bold: true, color: i ? C.red : C.ink });
    T(s, m[1], { x: x + 0.25, y: 2.38, w: 3.5, h: 0.45, fontSize: 11, color: C.grey });
  });
  // paired bars
  kick(s, '主集 11 张对照（0–100%）', mx, 3.15, 6);
  const pb = [['无向边 F1', 64.13, 95.83], ['综合解析', 89.95, 97.88], ['严格明细', 96.92, 96.92]];
  pb.forEach((r, i) => {
    const y = 3.6 + i * 1.02;
    T(s, r[0], { x: mx, y: y + 0.1, w: 1.4, h: 0.4, fontSize: 13, bold: true });
    hbar(s, mx + 1.5, y, 5.1, 0.3, r[1], 100, C.mid, '朴素 ' + r[1].toFixed(2) + '%', { fs: 10.5 });
    hbar(s, mx + 1.5, y + 0.36, 5.1, 0.3, r[2], 100, C.red, '完整 ' + r[2].toFixed(2) + '%', { fs: 10.5 });
  });
  T(s, '严格明细持平，提升落在连接关系上——而网表正是级差、载流量、互锁检查的输入', { x: mx, y: 6.62, w: 7.9, h: 0.3, fontSize: 11, color: C.grey });
}
module.exports = pres;
