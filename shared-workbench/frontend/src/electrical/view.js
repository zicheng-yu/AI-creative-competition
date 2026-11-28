import { html } from '../format.js';
import { bomRows, visibleFindings } from './model.js';

export const shell = `<header class="review-header">
 <div class="review-brand"><b>图枢电析</b><a href="./index.html">共用工作台</a></div>
 <div class="review-header-actions"><span id="source-mode">ElectroBench-JS</span><button id="theme" class="soft-button" type="button">切换深色</button></div>
</header>
<main id="main" class="review-main" tabindex="-1">
 <div class="review-intro"><div><div class="section-note">工作图纸与校验记录</div><h1>审图工作台</h1></div>
 <div class="review-tabs" role="group" aria-label="视图"><button type="button" data-view="review" aria-pressed="true">审图</button><button type="button" data-view="eval" aria-pressed="false">离线评测</button></div></div>
 <p id="notice" role="status" aria-live="polite"></p>
 <div id="review-view">
  <section class="review-toolbar" aria-label="图纸工具">
   <div><label for="fixture" class="sr-only">选择样例图纸</label><select id="fixture" class="field" aria-label="选择样例图纸"></select><button id="pick-file" class="primary-button" type="button">上传图纸</button><input id="file" type="file" accept=".dxf,.pdf,.png" hidden></div>
   <span id="input-source">可拖入 DXF、单页 PDF 或 PNG</span>
  </section>
  <div class="canvas-grid">
   <section class="review-card" aria-labelledby="sheet-heading">
    <header class="card-head"><div><span class="section-note">图纸叠加</span><h2 id="sheet-heading">已加载图纸</h2></div><div class="zoom-actions"><button type="button" data-zoom="-1" class="soft-button" aria-label="缩小图纸">−</button><output id="zoom-value">100%</output><button type="button" data-zoom="1" class="soft-button" aria-label="放大图纸">＋</button></div></header>
    <div class="drawing-scroll" id="drawing-scroll"><div class="drawing-stage" id="drawing-stage"></div></div>
    <div id="drawing-footer" class="drawing-footer"></div>
   </section>
   <section class="review-card" aria-labelledby="graph-heading">
    <header class="card-head"><div><span class="section-note">图纸与拓扑联动</span><h2 id="graph-heading">回路拓扑</h2></div><span id="graph-count" class="section-note"></span></header>
    <div class="graph-stage" id="graph"></div><div class="device-detail" id="device-detail"></div>
   </section>
  </div>
  <div class="inspect-grid">
   <section class="review-card" aria-labelledby="bom-heading">
    <header class="card-head"><div><span class="section-note" id="bom-count"></span><h2 id="bom-heading">物料清单</h2></div>
     <div class="export-controls"><button type="button" data-export="xlsx" class="soft-button">Excel</button><button type="button" data-export="csv" class="soft-button">CSV</button><button type="button" data-export="json" class="soft-button">JSON</button></div></header>
    <label class="filter-row"><span class="sr-only">筛选物料</span><input class="field" id="bom-filter" placeholder="筛选位号、型号、规格" aria-label="筛选物料"></label>
    <div class="bom-scroll" id="bom"></div>
   </section>
   <section class="review-card" aria-labelledby="check-heading">
    <header class="card-head"><div><span class="section-note">图纸规则筛查</span><h2 id="check-heading">合规体检</h2></div><button class="soft-button" id="recheck" type="button">重新体检</button></header>
    <div class="check-tools"><p id="check-meta"></p><label class="sr-only" for="severity">告警等级</label><select id="severity" class="field"><option value="all">当前问题</option><option value="error">严重</option><option value="warning">警告</option><option value="pass">已通过</option></select></div>
    <div id="checks" class="checks-list"></div>
   </section>
  </div>
  <section class="review-card command-card" aria-labelledby="command-heading">
   <header class="card-head"><div><span class="section-note">自然语言指令</span><h2 id="command-heading">审图 Copilot</h2></div><button id="voice" class="soft-button" type="button" aria-pressed="false">语音输入</button></header>
   <form id="command-form" class="review-command"><label class="sr-only" for="command">输入审图指令</label><input id="command" class="field" maxlength="180" placeholder="例如：查 QF1 的回路、查级差、把旧型号替换为新型号" required><button class="primary-button" type="submit">执行指令</button></form>
   <p id="command-result" class="command-result" role="status"></p>
  </section>
  <section class="review-card log-card" aria-labelledby="log-heading">
   <header class="card-head"><div><span class="section-note">当前工作副本</span><h2 id="log-heading">操作记录</h2></div><button id="undo" class="soft-button" type="button">撤销最近更改</button></header><div id="log" class="log-list"></div>
  </section>
 </div>
 <section id="eval-view" hidden aria-labelledby="eval-title"><h2 id="eval-title">ElectroBench-JS 离线评测</h2><p class="section-note">固定评测报告 · 主验收集与各输入格式分开统计</p><div id="eval-charts"></div></section>
 <footer class="review-footer">图纸、BOM 和修订均为当前审图工作副本。规则建议需要结合完整工程资料复核。</footer>
</main>
<dialog id="evidence-dialog" aria-labelledby="source-title"></dialog>
<dialog id="fix-dialog" class="fix-dialog" aria-labelledby="fix-title"><div id="fix-content"></div></dialog>`;

export function renderDrawing(page, selection, located) {
  return `<img id="plate" alt="${html(page.title)}图纸" src="${html(page.preview)}" draggable="false" width="${page.width}" height="${page.height}">
  <div class="overlay" aria-label="器件定位">${page.annotation.instances.filter((item) => item.bbox_px?.length === 4).map((item) => {
    const [x, y, w, h] = item.bbox_px;
    const active = item.id === selection ? 'picked' : located.has(item.id) ? 'located' : '';
    return `<button class="symbol-box ${active}" type="button" data-symbol="${html(item.id)}" aria-label="定位 ${html(item.tag || item.class_code)} 图纸器件" style="left:${100*x/page.width}%;top:${100*y/page.height}%;width:${100*w/page.width}%;height:${100*h/page.height}%"><span>${html(item.tag || item.class_code)}</span></button>`;
  }).join('')}</div>`;
}

export function renderBom(annotation, filter, selected) {
  const input = filter.trim().toUpperCase();
  const rows = bomRows(annotation).filter((row) => !input || [row.tag, row.name_zh, row.model, row.spec, row.circuit].some((value) => value?.toUpperCase().includes(input)));
  const field = (row, key, title) => `<input value="${html(row[key])}" aria-label="${html(row.tag || row.instance_id)} ${title}" maxlength="${key === 'tag' ? 28 : 160}" data-bom-id="${html(row.instance_id)}" data-bom-key="${key}">`;
  return `<table class="bom-table"><thead><tr><th scope="col">位号</th><th scope="col">器件</th><th scope="col">型号</th><th scope="col">规格</th><th scope="col">数量</th><th scope="col">定位</th></tr></thead><tbody>
  ${rows.map((row) => `<tr ${row.instance_id === selected ? 'class="picked-row"' : ''}><td>${field(row,'tag','位号')}</td><td>${html(row.name_zh)}</td><td>${field(row,'model','型号')}</td><td>${field(row,'spec','规格')}</td><td>${row.qty} ${html(row.unit)}</td><td><button type="button" data-symbol="${html(row.instance_id)}" class="text-button">定位</button></td></tr>`).join('')}
  </tbody></table>${rows.length ? '' : '<p class="small-empty">当前筛选没有物料。</p>'}`;
}

export function renderChecks(checks, severity, selected) {
  const labels = { error: '严重', warning: '警告', pass: '通过' };
  const items = visibleFindings(checks, severity);
  return items.length ? items.map((item) => `<article class="check-item ${item.index === selected ? 'picked-check' : ''}">
    <div><span class="check-level ${item.severity}">${labels[item.severity]}</span><strong>${html(item.message)}</strong></div>
    <p>${html((item.tags || []).join(' / '))} ${(item.standard_refs || []).slice(0,2).map((id) => `<button class="text-button" type="button" data-clause="${html(id)}">${html(id)}</button>`).join(' ')}</p>
    <div class="check-actions"><button type="button" data-finding="${item.index}" class="text-button">定位告警</button>${item.fix_suggestion?.operations?.length ? `<button type="button" data-fix="${item.index}" class="text-button">预览修订</button>` : ''}</div>
  </article>`).join('') : '<p class="small-empty">当前筛选没有报告条目。</p>';
}
