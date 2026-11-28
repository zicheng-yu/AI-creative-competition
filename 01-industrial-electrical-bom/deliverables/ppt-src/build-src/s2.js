const { pres, C, F, N, S, T, R, L, A, chrome, title, stat, hbar, kick } = require('./lib');
require('./s1');

// table helper: cols [{w, align}], rows of arrays; opts {x,y,rh,head, hl:[rowIdx], fs}
function grid(s, o) {
  let y = o.y;
  o.rows.forEach((r, i) => {
    const head = i === 0;
    const hl = (o.hl || []).includes(i);
    const rh = o.rh;
    if (head) R(s, o.x, y, o.w, rh, C.ink);
    else if (hl) R(s, o.x, y, o.w, rh, C.red);
    else if (o.zebra && i % 2 === 0) R(s, o.x, y, o.w, rh, 'F3EFEA');
    let x = o.x;
    r.forEach((c, j) => {
      const col = o.cols[j];
      T(s, String(c), { x: x + 0.08, y, w: col.w - 0.16, h: rh, fontSize: head ? (o.hfs || 11) : (o.fs || 11.5), bold: head || hl || col.bold, color: head || hl ? C.white : (col.color || C.ink), align: col.align || 'left', valign: 'middle', fontFace: col.num && !head ? N : F });
      x += col.w;
    });
    if (!head && !hl) L(s, o.x, y + rh, o.w, 0, C.rule, 0.5);
    y += rh;
  });
  return y;
}

// ===== 9 red lights
{
  const s = pres.addSlide(); chrome(s, 9, '03 技术路线 · 四类合规', '来源：项目计划书 §3.4、§9；佐证材料 表 3、表 5、表 6');
  title(s, ['四类红灯沿网表落到器件：', ['5 次真阳性'], '，7 张标准图 0 误报'], '每条告警附条文编号、来源和摘要；黄灯（证据不足或余量偏低）单列，不计入红灯');
  const cols = [{ w: 1.55, bold: true }, { w: 1.85, color: C.grey }, { w: 3.35 }, { w: 0.6, align: 'center', num: true }, { w: 0.6, align: 'center', num: true }, { w: 0.6, align: 'center', num: true }];
  const rows = [
    ['规则', '样图', '沿网表检查什么', 'TP', 'FP', 'FN'],
    ['级差倒挂', 'EBJS-D-SEL-001', '上下级关系比较额定电流', 1, 0, 0],
    ['载流量不足', 'EBJS-D-AMP-002', '导线允许电流 vs 过负荷保护', 1, 0, 0],
    ['电机保护缺配', 'EBJS-D-MOT-003', '短路保护、接触器、过载保护是否齐', 1, 0, 0],
    ['二次互锁缺失', 'EBJS-D-ILK-004', '对侧常闭触点是否在线圈回路（两侧各一）', 2, 0, 0],
    ['合计', '主集 11 张', '4 张缺陷图按真值命中；7 张标准图无误报', 5, 0, 0],
  ];
  grid(s, { x: 0.5, y: 1.95, w: 8.55, rh: 0.66, cols, rows, hl: [5], fs: 11.5 });
  T(s, '黄灯：图纸证据不足或筛查余量偏低时给出，供复核人回到原图确认', { x: 0.5, y: 6.1, w: 8.5, h: 0.5, fontSize: 11, color: C.grey });
  // right: compliance off
  const rx = 9.4, rw = 3.433;
  R(s, rx, 1.95, rw, 4.85, C.ink);
  kick(s, '关闭合规模块前后', rx + 0.25, 2.15, 3, 'F3A6A9');
  const cmp = [['综合解析', 97.88, 97.88, '%'], ['严格明细', 96.92, 96.92, '%'], ['红灯召回', 100, 0, '%']];
  cmp.forEach((r, i) => {
    const y = 2.6 + i * 1.12;
    T(s, r[0], { x: rx + 0.25, y, w: 2, h: 0.3, fontSize: 12.5, bold: true, color: C.white });
    hbar(s, rx + 0.25, y + 0.36, 2.2, 0.22, r[1], 100, C.red, (r[1] === 100 ? '100' : r[1].toFixed(2)) + '%', { track: '2E2E2E', tc: C.white, fs: 10.5 });
    hbar(s, rx + 0.25, y + 0.64, 2.2, 0.22, r[2], 100, 'BDBDBD', (r[2] === 0 ? '0' : r[2].toFixed(2)) + '%', { track: '2E2E2E', tc: 'BDBDBD', fs: 10.5 });
  });
  R(s, rx + 0.25, 5.98, 0.18, 0.14, C.red); T(s, '开启', { x: rx + 0.5, y: 5.92, w: 0.7, h: 0.26, fontSize: 10.5, color: C.white });
  R(s, rx + 1.25, 5.98, 0.18, 0.14, 'BDBDBD'); T(s, '关闭', { x: rx + 1.5, y: 5.92, w: 0.7, h: 0.26, fontSize: 10.5, color: C.white });
  T(s, '解析分数不变、红灯不再发出：网表质量与规则命中各自可复核', { x: rx + 0.25, y: 6.22, w: rw - 0.45, h: 0.5, fontSize: 10.5, color: 'C8C8C8' });
}

// ===== 10 interaction + revision
{
  const s = pres.addSlide(); chrome(s, 10, '04 交互与清单 · 定位与复检', '来源：项目计划书 §3.5、§4、§9；佐证材料 §3');
  title(s, ['点选一处，图纸、网表、告警同时定位；改完即复检，红灯 ', ['1 → 0']], '工程师在原图上确认告警和清单，设计签发仍由工厂完成');
  // shared-id diagram
  kick(s, '同一器件编号贯穿三处', 0.5, 1.95, 5);
  const cx = 2.55, cy = 3.25;
  s.addShape(pres.shapes.OVAL, { x: cx - 0.85, y: cy - 0.55, w: 1.7, h: 1.1, fill: { color: C.red }, line: { type: 'none' } });
  T(s, '器件编号', { x: cx - 0.85, y: cy - 0.55, w: 1.7, h: 1.1, fontSize: 15, bold: true, color: C.white, align: 'center', valign: 'middle' });
  const nodes = [['图纸上的框', 0.5, 2.35], ['网表中的节点', 3.55, 2.35], ['告警列表', 2.02, 4.15]];
  nodes.forEach(n => { R(s, n[1], n[2], 1.55, 0.5, C.ink); T(s, n[0], { x: n[1], y: n[2], w: 1.55, h: 0.5, fontSize: 11.5, bold: true, color: C.white, align: 'center', valign: 'middle' }); });
  L(s, 1.6, 2.85, 0.45, 0.25, C.ink, 1.25); L(s, 3.1, 3.1, 0.45, -0.25, C.ink, 1.25); L(s, cx, 3.8, 0, 0.35, C.ink, 1.25);
  // command examples
  kick(s, '文字指令示例', 0.5, 4.95, 5);
  [['查回路', '查某一断路器所在回路'], ['看级差', '列出级差告警'], ['换型号', '把一批旧型号换成新型号后导出']].forEach((c, i) => {
    const y = 5.3 + i * 0.5;
    R(s, 0.5, y, 1.0, 0.42, i === 0 ? C.red : C.pale2);
    T(s, c[0], { x: 0.5, y, w: 1.0, h: 0.42, fontSize: 11.5, bold: true, color: i === 0 ? C.white : C.ink, align: 'center', valign: 'middle' });
    T(s, '“' + c[1] + '”', { x: 1.62, y, w: 3.6, h: 0.42, fontSize: 12, valign: 'middle' });
  });
  // revision flow right
  const rx = 5.75;
  kick(s, '修订闭环：改规格和查告警是同一次操作的前后两步', rx, 1.95, 7);
  const st = [['预览', '修订先出预览，不直接改图'], ['确认', '写入当前工作副本'], ['复检', '重跑同一组规则']];
  st.forEach((t, i) => {
    const x = rx + i * 2.4;
    R(s, x, 2.35, 2.2, 1.0, i === 2 ? C.ink : C.pale);
    T(s, '0' + (i + 1) + ' ' + t[0], { x: x + 0.15, y: 2.43, w: 1.9, h: 0.38, fontSize: 15, bold: true, color: i === 2 ? C.white : C.ink });
    T(s, t[1], { x: x + 0.15, y: 2.85, w: 1.95, h: 0.4, fontSize: 11, color: i === 2 ? 'C8C8C8' : C.grey });
    if (i < 2) A(s, x + 2.22, 2.85, 0.16, 0, C.red);
  });
  // before/after
  R(s, rx, 3.65, 3.4, 2.15, C.pale);
  T(s, '级差样图 EBJS-D-SEL-001', { x: rx + 0.2, y: 3.75, w: 3.1, h: 0.3, fontSize: 12, bold: true });
  T(s, '1', { x: rx + 0.2, y: 4.1, w: 1.0, h: 1.1, fontFace: N, fontSize: 60, color: C.red, align: 'center', valign: 'middle' });
  A(s, rx + 1.35, 4.65, 0.6, 0, C.ink);
  T(s, '0', { x: rx + 2.1, y: 4.1, w: 1.0, h: 1.1, fontFace: N, fontSize: 60, color: C.ink, align: 'center', valign: 'middle' });
  T(s, '真值 1 条额定电流倒挂 → 改回关系后红灯消失', { x: rx + 0.2, y: 5.25, w: 3.1, h: 0.45, fontSize: 10.5, color: C.grey });
  R(s, rx + 3.6, 3.65, 3.483, 2.15, C.ink);
  T(s, [{ text: '4', options: { fontFace: N, fontSize: 44, color: C.white } }, { text: ' 张缺陷图', options: { fontSize: 15, bold: true, color: C.white } }], { x: rx + 3.8, y: 3.8, w: 3.1, h: 0.85, valign: 'bottom' });
  T(s, '补上正确器件关系后，红灯全部清零——告警跟着网表走', { x: rx + 3.8, y: 4.75, w: 3.1, h: 0.85, fontSize: 12, color: 'D0D0D0' });
  R(s, rx, 6.0, 7.083, 0.8, C.red);
  T(s, [{ text: '14 张', options: { fontFace: N, fontSize: 22, color: C.white } }, { text: '   以“实例 + 网表”为输入重跑，红灯结果与端到端一致', options: { fontSize: 13, bold: true, color: C.white } }], { x: rx + 0.2, y: 6.0, w: 6.8, h: 0.8, valign: 'middle' });
}

// ===== 11 BOM
{
  const s = pres.addSlide(); chrome(s, 11, '04 交互与清单 · 物料清单', '来源：项目计划书 §3.3、§4、§6、§8；佐证材料 表 2');
  title(s, ['每个采购锚点一条明细：严格明细 ', ['96.92%'], '，可筛选、可导出'], '交付物是可筛选、可导出的清单，以及落到器件的条文摘要；报价人员继续用原有表格和签批');
  // field header
  kick(s, '明细字段', 0.5, 1.95, 4);
  const fields = [['类别', '断路器、接触器、互感器、端子…'], ['位号', '与图纸框、网表节点同号'], ['规格', '邻近标注绑定，按规格语义比对'], ['数量', '按类别 + 规格语义 + 单位合并']];
  fields.forEach((f, i) => {
    const x = 0.5 + i * 1.95;
    R(s, x, 2.3, 1.85, 0.5, i === 2 ? C.red : C.ink);
    T(s, f[0], { x, y: 2.3, w: 1.85, h: 0.5, fontSize: 15, bold: true, color: C.white, align: 'center', valign: 'middle' });
    R(s, x, 2.8, 1.85, 0.85, C.pale);
    T(s, f[1], { x: x + 0.12, y: 2.86, w: 1.62, h: 0.75, fontSize: 11, color: C.grey, valign: 'middle' });
  });
  // flow
  kick(s, '从图到报价', 0.5, 3.95, 4);
  const fl = [['采购锚点', '每个器件\n一条明细'], ['汇总', '类别·规格\n·单位·总数'], ['筛选', '位号·器件\n·型号·规格'], ['导出', '表格 /\n结构化文件'], ['交给报价', '原有表格\n与签批']];
  fl.forEach((f, i) => {
    const x = 0.5 + i * 1.56;
    R(s, x, 4.3, 1.38, 1.3, i === 4 ? C.ink : null, i === 4 ? null : C.ink);
    T(s, f[0], { x, y: 4.38, w: 1.38, h: 0.34, fontSize: 13, bold: true, align: 'center', color: i === 4 ? C.white : C.ink });
    T(s, f[1], { x, y: 4.75, w: 1.38, h: 0.75, fontSize: 10.5, align: 'center', color: i === 4 ? 'C8C8C8' : C.grey });
    if (i < 4) A(s, x + 1.4, 4.95, 0.14, 0, C.red);
  });
  T(s, 'GGD 样图：清单可按位号直接筛出断路器、互感器和母线', { x: 0.5, y: 5.85, w: 7.7, h: 0.35, fontSize: 12, bold: true });
  T(s, '采购目录号与物料编码不在图上，第三步试点按企业目录映射，保留按版本回退', { x: 0.5, y: 6.25, w: 7.7, h: 0.35, fontSize: 11, color: C.grey });
  // right cards
  const rx = 8.6, rw = 4.233;
  stat(s, { x: rx, y: 1.95, w: rw, h: 1.5, num: '96.92', unit: '%', label: '严格明细完整率（主集 11 张）', theme: 'red', ns: 40, ls: 12.5 });
  stat(s, { x: rx, y: 3.6, w: rw * 0.485, h: 1.55, num: '96.65', unit: '%', label: '可见字段汇总', theme: 'dark', ns: 26, ls: 11.5 });
  stat(s, { x: rx + rw * 0.515, y: 3.6, w: rw * 0.485, h: 1.55, num: '97.31', unit: '%', label: '二次图 3 张综合', theme: 'dark', ns: 26, ls: 11.5 });
  R(s, rx, 5.3, rw, 1.5, C.pale);
  T(s, [{ text: '13.88', options: { fontFace: N, fontSize: 26, color: C.ink } }, { text: '%', options: { fontSize: 12, bold: true } }], { x: rx + 0.22, y: 5.38, w: 2, h: 0.6, valign: 'bottom' });
  T(s, '含采购目录号的扩展诊断完整率', { x: rx + 0.22, y: 6.02, w: 3.8, h: 0.3, fontSize: 11.5, bold: true });
  T(s, '目录号由企业主数据补充，是下一阶段对接项', { x: rx + 0.22, y: 6.36, w: 3.8, h: 0.3, fontSize: 10.5, color: C.grey });
}

// ===== 12 benchmark
{
  const s = pres.addSlide(); chrome(s, 12, '05 冻结评测 · 数据集', '来源：佐证材料 §1 表 1、表 7、摘要、附录');
  title(s, ['ElectroBench-JS v1.0.0：', ['14 张'], '冻结图、', ['345 个'], '符号实例、40/40 类'], '每张图的矢量、PDF、光栅和标注同源；模糊与倾斜只有光栅和标注');
  const rows = [['编号', '子集', '内容', '缺陷真值'],
    ['EBJS-P-GGD-001', '一次', 'GGD', 0], ['EBJS-P-MNS-002', '一次', 'MNS', 0], ['EBJS-P-GCS-003', '一次', 'GCS', 0], ['EBJS-P-KYN-004', '一次', 'KYN28', 0],
    ['EBJS-S-DOL-001', '二次', '启停自锁', 0], ['EBJS-S-FREV-002', '二次', '正反转', 0], ['EBJS-S-ATS-003', '二次', '双电源', 0],
    ['EBJS-D-SEL-001', '缺陷', '级差倒挂', 1], ['EBJS-D-AMP-002', '缺陷', '载流量', 1], ['EBJS-D-MOT-003', '缺陷', '电机保护', 1], ['EBJS-D-ILK-004', '缺陷', '互锁', 2],
    ['EBJS-G-BLUR-001', '退化', '模糊', 0], ['EBJS-G-SKEW-002', '退化', '倾斜', 0], ['EBJS-G-ALIAS-003', '退化', '简写', 0]];
  const cols = [{ w: 2.3 }, { w: 0.9, color: C.grey }, { w: 1.6, bold: true }, { w: 1.1, align: 'center', num: true }];
  const x0 = 0.5, rh = 0.325;
  // subset color tags
  rows.forEach((r, i) => { if (i > 0 && r[1] === '缺陷') R(s, x0, 1.95 + i * rh, 5.9, rh, 'F7E3E4'); });
  grid(s, { x: x0, y: 1.95, w: 5.9, rh, cols, rows, fs: 10.5, hfs: 10.5 });
  // right stats
  const rx = 6.85, cw = 2.9;
  stat(s, { x: rx, y: 1.95, w: cw, h: 1.3, num: '14', unit: ' 张', label: '冻结图（主集 11）', theme: 'dark', ns: 32, ls: 12 });
  stat(s, { x: rx + cw + 0.183, y: 1.95, w: cw, h: 1.3, num: '345', unit: ' 个', label: '符号实例', theme: 'red', ns: 32, ls: 12 });
  stat(s, { x: rx, y: 3.4, w: cw, h: 1.3, num: '40/40', unit: ' 类', label: '符号类别全覆盖', theme: 'light', ns: 32, ls: 12 });
  stat(s, { x: rx + cw + 0.183, y: 3.4, w: cw, h: 1.3, num: '262', unit: '', label: '随机种子', theme: 'light', ns: 32, ls: 12 });
  // composition bar
  kick(s, '分层构成 · 缺陷真值合计 5 条', rx, 4.95, 6);
  const comp = [['一次', 4, C.ink], ['二次', 3, '444444'], ['缺陷', 4, C.red], ['退化', 3, C.mid]];
  const tw = 5.983; let x = rx;
  comp.forEach(c => { const w = tw * c[1] / 14; R(s, x, 5.3, w, 0.5, c[2]); T(s, c[0] + ' ' + c[1], { x, y: 5.3, w, h: 0.5, fontSize: 12, bold: true, color: C.white, align: 'center', valign: 'middle' }); x += w; });
  L(s, rx, 5.92, tw * 11 / 14, 0, C.ink, 1); T(s, '主集 11 张', { x: rx, y: 5.96, w: tw * 11 / 14, h: 0.26, fontSize: 10.5, bold: true, align: 'center' });
  L(s, rx, 5.92 + 0.35, tw, 0, C.mid, 1); T(s, '全集 14 张', { x: rx, y: 6.3, w: tw, h: 0.26, fontSize: 10.5, color: C.grey, align: 'center' });
  T(s, 'CC BY 4.0 · 规范与生成器 v1.0.0 · 评测提交 dc21c96902e6', { x: rx, y: 6.62, w: tw, h: 0.3, fontSize: 9.5, color: C.grey });
}
module.exports = { pres, grid };
