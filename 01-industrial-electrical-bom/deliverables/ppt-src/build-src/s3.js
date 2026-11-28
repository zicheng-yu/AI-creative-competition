const { pres, C, F, N, S, T, R, L, A, chrome, title, stat, hbar, kick } = require('./lib');
const { grid } = require('./s2');

// ===== 13 baseline & ablation
{
  const s = pres.addSlide(); chrome(s, 13, '05 冻结评测 · 基线与消融', '来源：佐证材料 表 5、表 6、§2 分层综合；项目计划书 §4');
  title(s, ['同一口径对照：完整系统综合 ', ['97.88%'], '，OCR 正则符号与连边为 0'], '主集 11 张，连边为无向边 F1；每一行只改一处，其余流水线不变');
  // table with inline bars
  const rows = [['完整系统', 97.88, 95.83, 96.92], ['朴素连线', 89.95, 64.13, 96.92], ['纯光栅', 75.23, 48.02, 90.31], ['OCR 正则', 0, 0, 60.35], ['关闭合规', 97.88, 95.83, 96.92]];
  const x0 = 0.5, colx = [x0, 2.05, 4.0, 5.95], cw = 1.8;
  R(s, x0, 1.95, 7.75, 0.42, C.ink);
  ['方案', '综合解析', '无向边 F1', '严格明细'].forEach((h, j) => T(s, h, { x: colx[j] + 0.1, y: 1.95, w: j ? cw : 1.5, h: 0.42, fontSize: 11.5, bold: true, color: C.white, valign: 'middle' }));
  rows.forEach((r, i) => {
    const y = 2.37 + i * 0.66;
    if (i === 0) R(s, x0, y, 7.75, 0.66, 'F7E3E4');
    T(s, r[0], { x: x0 + 0.1, y, w: 1.5, h: 0.66, fontSize: 13, bold: true, color: i === 0 ? C.red : C.ink, valign: 'middle' });
    [1, 2, 3].forEach(j => {
      const v = r[j];
      T(s, v.toFixed(2) + '%', { x: colx[j] + 0.1, y: y + 0.06, w: cw, h: 0.32, fontFace: N, fontSize: 14, color: i === 0 ? C.red : C.ink });
      hbar(s, colx[j] + 0.1, y + 0.42, cw - 0.2, 0.1, v, 100, i === 0 ? C.red : C.ink, null, { track: C.pale2 });
    });
    L(s, x0, y + 0.66, 7.75, 0, C.rule, 0.5);
  });
  // layered composite strip
  kick(s, '主集分层综合', x0, 5.85, 4);
  [['一次图 4 张', '98.48%'], ['二次图 3 张', '97.31%'], ['缺陷图 4 张', '97.88%']].forEach((r, i) => {
    const x = x0 + i * 2.6;
    R(s, x, 6.15, 2.5, 0.7, C.pale);
    T(s, r[0], { x: x + 0.15, y: 6.15, w: 1.3, h: 0.7, fontSize: 12, bold: true, valign: 'middle' });
    T(s, r[1], { x: x + 1.2, y: 6.15, w: 1.2, h: 0.7, fontFace: N, fontSize: 16, color: C.red, align: 'right', valign: 'middle' });
  });
  // right delta panel
  const rx = 8.6, rw = 4.233;
  R(s, rx, 1.95, rw, 4.9, C.ink);
  kick(s, '完整系统领先（百分点）', rx + 0.25, 2.12, 3.8, 'F3A6A9');
  const d = [['对全光栅', [19.43, 34.93, 40.00]], ['对朴素连线', [7.92, 31.69, 20.00]], ['对关闭合规', [0, 0, 100.00]]];
  const lab = ['综合', '无向边', '红灯召回'];
  d.forEach((g, i) => {
    const y = 2.55 + i * 1.42;
    T(s, g[0], { x: rx + 0.25, y, w: 3, h: 0.3, fontSize: 13, bold: true, color: C.white });
    g[1].forEach((v, j) => {
      const yy = y + 0.36 + j * 0.32;
      T(s, lab[j], { x: rx + 0.25, y: yy - 0.03, w: 0.9, h: 0.28, fontSize: 10, color: 'BDBDBD', valign: 'middle' });
      hbar(s, rx + 1.15, yy, 2.0, 0.22, v, 100, j === 2 ? C.red : C.white, (v === 0 ? '0.00' : '+' + v.toFixed(2)), { notrack: true, tc: C.white, fs: 10.5, font: N });
    });
  });
}

// ===== 14 full set & degraded
{
  const s = pres.addSlide(); chrome(s, 14, '05 冻结评测 · 全集与退化', '来源：项目计划书 §6；佐证材料 表 2、§3；退化图综合按单图口径，模糊图为增强且追线阈值 180');
  title(s, ['全集 14 张综合 ', ['93.49%'], '：退化图单独公布，误差能逐类回到原图'], '全集 = 主集 11 张 + 模糊、倾斜、简写 3 张退化图');
  const cw = 2.0;
  stat(s, { x: 0.5, y: 1.95, w: cw, h: 1.5, num: '93.49', unit: '%', label: '全集综合', theme: 'dark', ns: 26, ls: 11.5 });
  stat(s, { x: 2.65, y: 1.95, w: cw, h: 1.5, num: '98.09', unit: '%', label: '全集符号 F1', theme: 'red', ns: 26, ls: 11.5 });
  stat(s, { x: 0.5, y: 3.6, w: cw, h: 1.5, num: '89.90', unit: '%', label: '全集严格明细', theme: 'light', ns: 26, ls: 11.5 });
  stat(s, { x: 2.65, y: 3.6, w: cw, h: 1.5, num: '91.65', unit: '%', label: '全集无向边 F1', theme: 'light', ns: 26, ls: 11.5 });
  // degraded bars
  kick(s, '退化 3 张 · 综合解析', 0.5, 5.3, 4);
  [['倾斜', 82.95], ['简写（别名）', 56.79], ['模糊（增强）', 45.95]].forEach((r, i) => {
    const y = 5.65 + i * 0.4;
    T(s, r[0], { x: 0.5, y, w: 1.3, h: 0.3, fontSize: 11, bold: true, valign: 'middle' });
    hbar(s, 1.8, y + 0.04, 2.2, 0.22, r[1], 100, C.ink, r[1].toFixed(2) + '%', { fs: 10.5 });
  });
  // middle: degraded summary
  const mx = 5.0;
  R(s, mx, 1.95, 3.3, 3.15, C.red);
  T(s, [{ text: '75.84', options: { fontFace: N, fontSize: 40, color: C.white } }, { text: '%', options: { fontSize: 16, bold: true, color: C.white } }], { x: mx + 0.22, y: 2.1, w: 2.9, h: 0.8, valign: 'bottom' });
  T(s, '退化 3 张综合', { x: mx + 0.22, y: 2.95, w: 2.9, h: 0.3, fontSize: 13, bold: true, color: C.white });
  L(s, mx + 0.22, 3.4, 2.86, 0, 'E58A8F', 0.75);
  T(s, [{ text: '59.76', options: { fontFace: N, fontSize: 26, color: C.white } }, { text: '%', options: { fontSize: 12, bold: true, color: C.white } }], { x: mx + 0.22, y: 3.5, w: 2.9, h: 0.6, valign: 'bottom' });
  T(s, '同组原始光栅综合，与退化 3 张同图对照', { x: mx + 0.22, y: 4.15, w: 2.9, h: 0.8, fontSize: 11, color: 'F6D5D6' });
  R(s, mx, 5.3, 3.3, 1.55, C.pale);
  T(s, '简写图：关闭条文归一后', { x: mx + 0.2, y: 5.38, w: 3, h: 0.3, fontSize: 11.5, bold: true });
  [['规格精确', '43.48% → 4.35%'], ['严格明细', '65.22% → 43.48%']].forEach((r, i) => {
    T(s, r[0], { x: mx + 0.2, y: 5.78 + i * 0.45, w: 1.2, h: 0.36, fontSize: 11, color: C.grey, valign: 'middle' });
    T(s, r[1], { x: mx + 1.3, y: 5.78 + i * 0.45, w: 1.85, h: 0.36, fontSize: 12.5, bold: true, color: C.red, align: 'right', valign: 'middle' });
  });
  // right: attribution counts
  const rx = 8.65, rw = 4.183;
  kick(s, '自动归因计数（条）', rx, 1.95, rw);
  const at = [['规格缺文', 17], ['端点缺失', 17], ['多余连线', 13], ['符号漏检', 11], ['疑似断线', 11], ['逻辑分支或端口缺失', 9], ['疑似文字混淆', 3], ['符号误检', 2], ['未匹配端点', 1]];
  at.forEach((r, i) => {
    const y = 2.3 + i * 0.47;
    T(s, r[0], { x: rx, y, w: 1.75, h: 0.36, fontSize: 11, valign: 'middle' });
    hbar(s, rx + 1.8, y + 0.06, 1.95, 0.24, r[1], 17, i < 2 ? C.red : C.ink, String(r[1]), { notrack: true, fs: 11, font: N, lw: 0.4 });
  });
  T(s, '计数用于回到原图复核；符号漏检较多的类别是导线回路', { x: rx, y: 6.55, w: rw, h: 0.35, fontSize: 10.5, color: C.grey });
}

// ===== 15 positioning + deployment
{
  const s = pres.addSlide(); chrome(s, 15, '06 部署与试点 · 定位与部署', '来源：项目计划书 §7、§8。效益为试点假设下的预估：人工 120 元/小时，年运维 1.2 万元');
  title(s, ['读已发出的图纸、不替代 ECAD；', ['内网单机'], '即可部署'], '和设计工具分工：它们管建模与归档，ElectronicBOM 管“已发出的图能否直接算清”');
  const cols = [{ w: 1.75, bold: true }, { w: 2.4, color: C.grey }, { w: 2.35 }];
  const rows = [['产品', '公开能力', 'ElectronicBOM 切入点'],
    ['Werk24', '抽取工程图尺寸、标题栏和物料字段', '接已发出的电气图，输出网表'],
    ['EPLAN Electric P8', '在自有工程数据上出导线、端子和报表', '不需在 ECAD 里重新建模'],
    ['CADDi Drawer', '图纸归档与相似检索', '网表、清单、告警共用编号'],
    ['ElectronicBOM', '矢量 / PDF / 光栅进入同一条网表与清单', '告警带回条文编号，报价沿用原表格']];
  grid(s, { x: 0.5, y: 1.95, w: 6.5, rh: 0.86, cols, rows, hl: [4], fs: 11.5 });
  // deployment diagram
  const rx = 7.4, rw = 5.433;
  kick(s, '部署：工厂内网单机', rx, 1.95, rw);
  R(s, rx, 2.28, rw, 1.35, null, C.ink, 'dash');
  const box = [['静态页面', '浏览器访问'], ['同源代理', '单一入口'], ['解析进程', '端口 8066']];
  box.forEach((b, i) => {
    const x = rx + 0.2 + i * 1.78;
    R(s, x, 2.45, 1.45, 1.0, i === 2 ? C.red : C.ink);
    T(s, b[0], { x, y: 2.52, w: 1.45, h: 0.4, fontSize: 13, bold: true, color: C.white, align: 'center' });
    T(s, b[1], { x, y: 2.95, w: 1.45, h: 0.35, fontSize: 10.5, color: i === 2 ? 'F6D5D6' : 'C8C8C8', align: 'center' });
    if (i < 2) A(s, x + 1.47, 2.95, 0.29, 0, C.ink);
  });
  T(s, '报价分列：基础部署 · 目录适配 · 年度运维', { x: rx, y: 3.72, w: rw, h: 0.3, fontSize: 11.5, bold: true });
  // benefit bars
  kick(s, '稳态净收益（万元/年，预估）', rx, 4.15, rw);
  const bn = [['600 张/年', '每张省 10 分钟', 0.0], ['1,200 张/年', '每张省 15 分钟', 2.4], ['2,400 张/年', '每张省 20 分钟', 8.4]];
  bn.forEach((b, i) => {
    const y = 4.5 + i * 0.58;
    T(s, b[0], { x: rx, y, w: 1.25, h: 0.25, fontSize: 11.5, bold: true });
    T(s, b[1], { x: rx, y: y + 0.24, w: 1.4, h: 0.24, fontSize: 9.5, color: C.grey });
    hbar(s, rx + 1.45, y + 0.08, 2.6, 0.3, b[2], 8.4, i === 1 ? C.red : C.ink, b[2].toFixed(1), { fs: 12, font: N });
  });
  R(s, rx, 6.28, rw / 2 - 0.08, 0.6, C.pale);
  T(s, [{ text: '2.5', options: { fontFace: N, fontSize: 18, color: C.red } }, { text: ' 万元  基准一次性实施', options: { fontSize: 11, bold: true } }], { x: rx + 0.15, y: 6.28, w: rw / 2 - 0.3, h: 0.6, valign: 'middle' });
  R(s, rx + rw / 2 + 0.08, 6.28, rw / 2 - 0.08, 0.6, C.pale);
  T(s, [{ text: '12.5', options: { fontFace: N, fontSize: 18, color: C.red } }, { text: ' 个月  静态回收', options: { fontSize: 11, bold: true } }], { x: rx + rw / 2 + 0.23, y: 6.28, w: rw / 2 - 0.3, h: 0.6, valign: 'middle' });
}

// ===== 16 pilot + timeline
{
  const s = pres.addSlide(); chrome(s, 16, '06 部署与试点 · 路线', '来源：项目计划书 §7、§10 实施计划');
  title(s, ['三步试点，验收就看冻结集上', ['已有读数'], '的四项指标'], '新柜型先进评测集，矢量通道达到主集量级后再放进报价');
  const steps = [['01', '稳住主集这一档', 'GGD 与 KYN28 脱敏图，用人工清单核对严格明细和红灯；记录上传、修改、导出时间'], ['02', '三通道分列', '单机按图源打开矢量、PDF、光栅；矢量作报价主路径，PDF 与光栅作扫描件对照'], ['03', '对接目录号', '审批后把目录号和物料编码映射进现有采购表，保留按版本回退；身份与留存由工厂信息部门定']];
  L(s, 0.5, 2.05, 12.333, 0, C.ink, 1.5);
  steps.forEach((st, i) => {
    const x = 0.5 + i * 4.2;
    s.addShape(pres.shapes.OVAL, { x: x, y: 1.9, w: 0.3, h: 0.3, fill: { color: C.red }, line: { type: 'none' } });
    T(s, st[0], { x, y: 2.2, w: 0.8, h: 0.55, fontFace: N, fontSize: 24, color: C.red, valign: 'middle' });
    T(s, st[1], { x: x + 0.8, y: 2.2, w: 3.1, h: 0.55, fontSize: 16, bold: true, valign: 'middle' });
    T(s, st[2], { x, y: 2.8, w: 3.9, h: 0.8, fontSize: 11.5, color: C.grey });
  });
  // acceptance table
  kick(s, '验收四项', 0.5, 3.72, 4);
  const cols = [{ w: 1.7, bold: true }, { w: 1.8, align: 'right', num: true }, { w: 1.4, align: 'right', color: C.grey }, { w: 3.3, color: C.grey }];
  const rows = [['指标', '冻结集读数', '门槛', '试点看什么'],
    ['综合解析', '97.88%', '≥ 93%', '本厂图是否保持在这一档'],
    ['严格明细', '96.92%', '≥ 95%', '与人工清单逐条比对'],
    ['四类红灯', '5 TP · 0 FP', '—', '只在已知缺陷上亮'],
    ['矢量耗时', '0.07 秒/张', '—', '离线解析与人工确认分开记']];
  grid(s, { x: 0.5, y: 4.02, w: 8.2, rh: 0.55, cols, rows, fs: 12 });
  // milestones black panel
  const rx = 9.1, rw = 3.733;
  R(s, rx, 3.7, rw, 3.12, C.ink);
  kick(s, '赛程节点 · 2026', rx + 0.25, 3.85, 3, 'F3A6A9');
  [['11.30', '初赛材料截止'], ['12.1–3', '线上评审'], ['12 月中旬', '路演']].forEach((m, i) => {
    const y = 4.25 + i * 0.72;
    R(s, rx + 0.25, y + 0.12, 0.08, 0.4, i === 2 ? C.red : C.white);
    T(s, m[0], { x: rx + 0.45, y, w: 1.75, h: 0.62, fontFace: N, fontSize: 17, color: C.white, valign: 'middle' });
    T(s, m[1], { x: rx + 2.05, y, w: 1.5, h: 0.62, fontSize: 12.5, bold: true, color: 'D0D0D0', valign: 'middle', align: 'right' });
  });
  T(s, [{ text: 'Electronic', options: { color: C.white } }, { text: 'BOM', options: { color: 'F3A6A9' } }], { x: rx + 0.25, y: 6.37, w: 3.3, h: 0.38, fontFace: N, fontSize: 16, valign: 'middle' });
}

const out = '/workspace/slides/electronicbom-FFhyCQ/人工智能+工业制造赛道-ElectronicBOM-盼盼法式小面包.pptx';
pres.writeFile({ fileName: out }).then(() => console.log('wrote', out));
