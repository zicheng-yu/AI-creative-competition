const replacements = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export function html(value = '') {
  return String(value ?? '').replace(/[&<>"']/g, (char) => replacements[char]);
}

export const percent = (value) => value == null ? '—' : `${Math.round(value * 100)}%`;

export const labels = { critical: '严重', warning: '警告', pass: '通过' };
