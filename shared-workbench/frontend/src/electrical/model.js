export function bomRows(annotation) {
  const previous = new Map((annotation.bom ?? []).map((row) => [row.instance_id, row]));
  return annotation.instances.filter((item) => item.bom_anchor === true || previous.has(item.id)).map((item) => {
    const row = previous.get(item.id);
    return {
      instance_id: item.id, tag: item.tag ?? '', class_code: item.class_code,
      name_zh: row?.name_zh ?? item.name_zh ?? item.class_code,
      model: item.specs?.model ?? '', spec: item.specs?.spec ?? '',
      qty: row?.qty ?? 1, unit: row?.unit ?? item.unit ?? '', circuit: item.circuit ?? '',
    };
  });
}

export function connected(annotation, id) {
  const upstream = new Map(), downstream = new Map();
  for (const {source, target} of annotation.netlist?.edges ?? []) {
    if (!upstream.has(target)) upstream.set(target, []);
    if (!downstream.has(source)) downstream.set(source, []);
    upstream.get(target).push(source);
    downstream.get(source).push(target);
  }
  const find = (neighbors) => {
    const seen = new Set([id]), result = [];
    for (const current of seen) {
      for (const next of neighbors.get(current) ?? []) {
        if (seen.has(next)) continue;
        seen.add(next);
        result.push(next);
      }
    }
    return result;
  };
  return { upstream: find(upstream), downstream: find(downstream) };
}

export function visibleFindings(checks, severity) {
  const ranks = { error: 0, warning: 1, pass: 2 };
  return (checks?.findings ?? []).map((finding, i) => ({ ...finding, index: i }))
    .filter((finding) => severity === 'all' ? finding.severity !== 'pass' : finding.severity === severity)
    .sort((a, b) => (ranks[a.severity] ?? 9) - (ranks[b.severity] ?? 9) || a.index - b.index);
}

function replaceSpec(item, newSpec) {
  const specs = { ...item.specs, spec: newSpec };
  for (const [name, pattern] of [
    ['In_A', /\bIn\s*=\s*(\d+(?:\.\d+)?)\s*A\b/i],
    ['Icu_kA', /\bIcu\s*=\s*(\d+(?:\.\d+)?)\s*kA\b/i],
    ['Ie_A', /\bIe\s*=\s*(\d+(?:\.\d+)?)\s*A\b/i],
  ]) {
    const match = newSpec.match(pattern);
    if (match) specs[name] = Number(match[1]);
    else if (item.specs?.spec?.match(pattern)) delete specs[name];
  }
  return specs;
}

export function editBom(annotation, ids, field, raw) {
  if (!['tag', 'model', 'spec'].includes(field)) throw new Error('该字段不可编辑。');
  const value = raw.trim();
  if (value.length > 160 || (field === 'tag' && (!value || value.length > 28))) throw new Error('请填写有效的位号或规格。');
  const wanted = new Set(ids);
  const original = field === 'tag' ? annotation.instances.find((item) => wanted.has(item.id))?.tag : null;
  if (field === 'tag') {
    if (original) for (const item of annotation.instances) if (item.tag === original) wanted.add(item.id);
    if (annotation.instances.some((item) => !wanted.has(item.id) && item.tag?.toUpperCase() === value.toUpperCase())) {
      throw new Error('此位号已用于其他器件。');
    }
  }
  const changes = [];
  const instances = annotation.instances.map((item) => {
    if (!wanted.has(item.id)) return item;
    const before = field === 'tag' ? item.tag : item.specs?.[field];
    if ((before ?? '') === value) return item;
    changes.push({ id: item.id, tag: item.tag, field, before: before ?? '', after: value });
    if (field === 'tag') return { ...item, tag: value };
    return { ...item, specs: field === 'spec' ? replaceSpec(item, value) : { ...item.specs, model: value } };
  });
  const tags = new Map(instances.map((item) => [item.id, item.tag]));
  const graph = annotation.netlist;
  const netlist = { ...graph, nodes: (graph?.nodes ?? []).map((node) => ({ ...node, tag: tags.get(node.id) ?? node.tag })) };
  const patched = { ...annotation, instances, netlist };
  if (original && annotation.control_branches) {
    patched.control_branches = annotation.control_branches.map((branch) => ({
      ...branch,
      coil_tag: branch.coil_tag === original ? value : branch.coil_tag,
      pair_tag: branch.pair_tag === original ? value : branch.pair_tag,
    }));
  }
  return { annotation: { ...patched, bom: bomRows(patched) }, changes };
}

export function decodeCommand(text, annotation) {
  const value = text.trim().replace(/[“”‘’]/g, '"').replace(/[：]/g, ':');
  if (!value) return { kind: 'unknown' };
  const rename = value.match(/^(?:批量\s*)?(?:(?:将|把|替换型号)\s*)?(?:型号\s*)?["']?([A-Za-z\d][A-Za-z\d/_+ .-]{0,58}?)["']?\s*(?:替换为|改为|更新为|换成|→|->)\s*["']?([A-Za-z\d][A-Za-z\d/_+ .-]{0,58}?)["']?$/);
  // Limit writable intents to an explicit old and new model pair.
  if (rename) return { kind: 'replace', from: rename[1].trim(), to: rename[2].trim() };
  const targets = annotation.instances.filter((item) => item.tag
      && new RegExp(`(^|[^A-Z0-9])${escapeRegExp(item.tag)}(?=$|[^A-Z0-9])`, 'i').test(value));
  if (/级差|选择性|保护/.test(value)) return { kind: 'findings', targets };
  if (/回路|拓扑|上游|下游|连接|定位/.test(value) && targets.length) return { kind: 'circuit', targets };
  return { kind: 'unknown' };
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^$${}()|[\]\\]/g, '\\$&');
}

export function diffInstances(before, after) {
  const prior = new Map(before.instances.map((item) => [item.id, item]));
  const updates = [];
  for (const item of after.instances) {
    const old = prior.get(item.id);
    if (!old) {
      updates.push({ id: item.id, tag: item.tag, field: '器件', before: '', after: item.class_code });
      continue;
    }
    for (const field of ['model', 'spec', ...Object.keys(item.specs ?? {}).filter((k) => !['model', 'spec'].includes(k))]) {
      if (JSON.stringify(old.specs?.[field]) !== JSON.stringify(item.specs?.[field])) {
        updates.push({ id: item.id, tag: item.tag, field, before: old.specs?.[field] ?? '', after: item.specs?.[field] ?? '' });
      }
    }
  }
  return updates;
}
