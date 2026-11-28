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

