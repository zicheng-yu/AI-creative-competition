import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { unzipSync, strFromU8 } from 'fflate';
import { csv, xlsx } from '../src/electrical/export.js';
import { bomRows, connected, decodeCommand, editBom } from '../src/electrical/model.js';

const readFixture = (id) => JSON.parse(readFileSync(new URL(`../public/electrical/${id}.json`, import.meta.url)));
const dol = readFixture('EBJS-S-DOL-001').annotation;
const defect = readFixture('EBJS-D-SEL-001').annotation;

test('propagates a renamed contactor to matching symbols, topology and control references', () => {
  const row = bomRows(dol).find(({tag}) => tag === 'KM1');
  const siblingIds = dol.instances.filter(({tag}) => tag === 'KM1').map(({id}) => id);
  const {annotation, changes} = editBom(dol, [row.instance_id], 'tag', 'KM17');
  assert.deepEqual(changes.map(({id}) => id), siblingIds);
  assert.equal(bomRows(annotation).find(({instance_id}) => instance_id === row.instance_id).tag, 'KM17');
  assert.ok(annotation.netlist.nodes.filter(({id}) => siblingIds.includes(id)).every(({tag}) => tag === 'KM17'));
  assert.equal(annotation.control_branches[0].coil_tag, 'KM17');
  assert.equal(dol.control_branches[0].coil_tag, 'KM1');
});

test('updates explicit ratings in the working copy after a BOM edit', () => {
  const breaker = defect.instances.find(({tag}) => tag === 'QF1');
  const {annotation} = editBom(defect, [breaker.id], 'spec', 'In=200A 3P Icu=50kA');
  assert.equal(annotation.instances.find(({id}) => id === breaker.id).specs.In_A, 200);
  assert.equal(bomRows(annotation).find(({instance_id}) => instance_id === breaker.id).spec, 'In=200A 3P Icu=50kA');
});

test('tracks direction across a cycle without returning the start or duplicate nodes', () => {
  const annotation = {netlist: {edges: [
    {source:'x',target:'a'}, {source:'a',target:'b'}, {source:'b',target:'c'},
    {source:'c',target:'a'}, {source:'a',target:'b'}, {source:'c',target:'d'},
  ]}};
  assert.deepEqual(connected(annotation, 'a'), {upstream:['x','c','b'], downstream:['b','c','d']});
});

test('parses circuit, selectivity and explicit model changes', () => {
  assert.equal(decodeCommand('帮我查 QF2 的回路', defect).targets[0].tag, 'QF2');
  assert.equal(decodeCommand('查 QF1 的级差', defect).kind, 'findings');
  assert.deepEqual(decodeCommand('把 EB-MCCB-250/100 替换为 EB-MCCB-315/315', defect), {
    kind:'replace', from:'EB-MCCB-250/100', to:'EB-MCCB-315/315',
  });
  assert.equal(decodeCommand('帮我随便换一个型号', defect).kind, 'unknown');
});

test('exports editable material data as text and numeric counts', async () => {
  const rows = [{ tag:'QF1', name_zh:'断路器', class_code:'MCCB', model:'=2+2', spec:'A, "B" & C', circuit:'主回路', qty:2, unit:'台' }];
  assert.ok(csv(rows).startsWith('\uFEFF"位号"'));
  assert.ok(csv(rows).includes(`"'=2+2","A, ""B"" & C"`));
  const entries = unzipSync(await xlsx(rows));
  const sheet = strFromU8(entries['xl/worksheets/sheet1.xml']);
  assert.match(sheet, /<c r="D2" t="inlineStr"><is><t xml:space="preserve">=2\+2<\/t>/);
  assert.match(sheet, /A, &quot;B&quot; &amp; C/);
  assert.match(sheet, /<c r="G2"><v>2<\/v><\/c>/);
});
