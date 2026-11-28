import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
  applyReview, badge, canSign, emptyReview, filterRecords, radarChart, reviewMarkdown, sameSnapshot, signReview,
} from '../src/fluvax/model.js';
import { page } from '../src/fluvax/view.js';

const statement = { statement_id: 'S1', evidence_id: 'EV-REF-GARTEN', primary_ref: 'PMID:19465683', dataset_version: 'fluevidence-v1', text: 'Antigenic title.', evidence_tier: 'T3_PEER_REVIEWED_LIT' };

test('badges cite the evidence id, public ref, and dataset version', () => {
  assert.equal(badge(statement), '[EV-REF-GARTEN | PMID:19465683 | fluevidence-v1]');
});

test('signoff stays a draft until every statement has a disposition', () => {
  let review = emptyReview([statement]);
  assert.equal(review.watermark, 'AI 辅助草稿');
  assert.equal(canSign(review), false);
  review = applyReview(review, 'S1', 'accept');
  assert.equal(canSign(review), true);
  assert.match(reviewMarkdown(review, '边界', 'fluevidence-v1.1'), /签批前不导出/);
  review = signReview(review);
  assert.equal(review.watermark, '专家已签批');
  assert.match(reviewMarkdown(review, '边界声明', 'fluevidence-v1.1'), /边界声明/);
  assert.match(reviewMarkdown(review, '边界声明', 'fluevidence-v1.1'), /PMID:19465683/);
  assert.throws(() => applyReview(review, 'S1', 'reject'), /已签批/);
});

test('filters records and builds a five-axis evidence radar', () => {
  const records = [
    { evidence_id: 'A', primary_ref: 'PMID:1', title: 'stem', evidence_tier: 'T3_PEER_REVIEWED_LIT', source_type: 'PUBMED_LITERATURE' },
    { evidence_id: 'B', primary_ref: 'PDB:3GBN', title: 'structure', evidence_tier: 'T1_WET_LAB_ASSAY', source_type: 'PDB_STRUCTURE' },
  ];
  assert.equal(filterRecords(records, { text: '3gbn' }).length, 1);
  const chart = radarChart([{
    label: '茎部',
    evidence_dimensions: { source_coverage: .2, version_consistency: 0, citation_conflict_clearance: 1, tier_breadth: .5, open_review_clearance: .5 },
  }]);
  assert.equal(chart.kind, 'radar');
  assert.equal(chart.axes.length, 5);
  assert.deepEqual(chart.series[0].values, [.2, 0, 1, .5, .5]);
});

test('offline demo carries the boundary, version, and no upload path', () => {
  const doc = JSON.parse(readFileSync(new URL('../public/fluvax/workbench.json', import.meta.url), 'utf8'));
  assert.equal(doc.records.length, 24);
  assert.equal(doc.dataset_version, 'fluevidence-v1.1');
  assert.equal(doc.manual_sop_baseline, '未测');
  assert.match(doc.boundary, /不以实验有效性或临床效果作为承诺/);
  assert.equal(sameSnapshot({ snapshot_id: doc.snapshot_id }, doc), true);
  assert.equal(sameSnapshot({ snapshot_id: 'other' }, doc), false);
  const html = page(doc, {
    view: 'compare', tier: 'all', source: 'all', text: '', question: 0, visible: doc.records.slice(0, 1),
    mode: '离线演示数据', review: emptyReview(doc.questions[0].statements),
  });
  assert.match(html, /数据版本 fluevidence-v1\.1/);
  assert.match(html, /证据工作台/);
  assert.doesNotMatch(html, /type="file"/);
  assert.doesNotMatch(readFileSync(new URL('../src/fluvax/main.js', import.meta.url), 'utf8'), /type="file"|upload/i);
});
