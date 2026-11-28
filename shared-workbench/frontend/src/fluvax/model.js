export const VIEWS = [
  ['snapshot', '快照与版本'],
  ['timeline', '引用时间线'],
  ['qa', '循证问答'],
  ['compare', '五维比较'],
  ['review', '签批与评测'],
];

export const DIMENSION_KEYS = [
  ['source_coverage', '来源覆盖'],
  ['version_consistency', '版本一致'],
  ['citation_conflict_clearance', '引用无交叉冲突'],
  ['tier_breadth', '等级覆盖'],
  ['open_review_clearance', '未决事项少'],
];

export function badge(statement) {
  return `[${statement.evidence_id} | ${statement.primary_ref} | ${statement.dataset_version}]`;
}

export function sameSnapshot(health, document) {
  return Boolean(health?.snapshot_id && health.snapshot_id === document?.snapshot_id);
}

export function filterRecords(records, { tier = 'all', source = 'all', text = '' } = {}) {
  const query = text.trim().toLowerCase();
  return records.filter((row) => (tier === 'all' || row.evidence_tier === tier)
    && (source === 'all' || row.source_type === source)
    && (!query || `${row.evidence_id} ${row.primary_ref} ${row.title}`.toLowerCase().includes(query)));
}

export function radarChart(dossiers) {
  return {
    id: 'dimensions',
    kind: 'radar',
    title: '证据治理五维',
    axes: DIMENSION_KEYS.map(([, label]) => ({ label, maximum: 1 })),
    series: dossiers.map((row) => ({
      name: row.label,
      values: DIMENSION_KEYS.map(([key]) => row.evidence_dimensions[key]),
    })),
  };
}

export function emptyReview(statements) {
  return { signed: false, watermark: 'AI 辅助草稿', dispositions: {}, notes: {}, statements };
}

export function applyReview(review, statementId, action, note = '') {
  if (!review.statements.some((row) => row.statement_id === statementId)) throw new Error('未知语句');
  if (review.signed) throw new Error('已签批');
  return {
    ...review,
    dispositions: { ...review.dispositions, [statementId]: action },
    notes: { ...review.notes, [statementId]: note },
  };
}

export function canSign(review) {
  return review.statements.length > 0 && review.statements.every((row) =>
    ['accept', 'flag_doubt', 'reject'].includes(review.dispositions[row.statement_id]));
}

export function signReview(review) {
  if (!canSign(review)) throw new Error('签批前需要逐条处置');
  return { ...review, signed: true, watermark: '专家已签批' };
}

export function reviewMarkdown(review, boundary, version) {
  const lines = ['# 专家复核', '', boundary, '', `数据版本 ${version}`, '', `状态 ${review.watermark}`, ''];
  if (!review.signed) {
    lines.push('签批前不导出未采纳引文。');
    return lines.join('\n');
  }
  const rows = review.statements.filter((row) => review.dispositions[row.statement_id] === 'accept');
  if (!rows.length) lines.push('没有已采纳引文。');
  for (const row of rows) lines.push(`- ${row.text} — ${badge(row)}`);
  return `${lines.join('\n')}\n`;
}
