const fields = [
  ['tag', '位号'], ['name_zh', '器件'], ['class_code', '类别'], ['model', '型号'],
  ['spec', '规格'], ['circuit', '回路'], ['qty', '数量'], ['unit', '单位'],
];

function cell(value) {
  let data = String(value ?? '');
  if (typeof value === 'string' && (/^[\t\n\r]/.test(data) || /^[=+@-]/.test(data.trimStart()))) data = "'" + data;
  return '"' + data.replaceAll('"', '""') + '"';
}
const matrix = (rows) => [fields.map(([, title]) => title), ...rows.map((row) => fields.map(([field]) => row[field]))];

export function csv(rows) {
  return '\uFEFF' + matrix(rows).map((row) => row.map(cell).join(',')).join('\r\n') + '\r\n';
}

function xml(value) {
  return String(value ?? '').replace(/[<>&"']/g, (text) => ({
    '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;',
  })[text]);
}
export async function xlsx(rows) {
  const { zipSync, strToU8 } = await import('fflate');
  const declaration = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
  const sheet = matrix(rows).map((row, y) => {
    const cells = row.map((value, x) => {
      const ref = String.fromCharCode(65 + x) + (y + 1);
      if (typeof value === 'number' && Number.isFinite(value)) return `<c r="${ref}"><v>${value}</v></c>`;
      return `<c r="${ref}" t="inlineStr"><is><t xml:space="preserve">${xml(value)}</t></is></c>`;
    }).join('');
    return `<row r="${y + 1}">${cells}</row>`;
  }).join('');
  const main = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main';
  const rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships';
  const pkg = 'http://schemas.openxmlformats.org/package/2006';
  const docs = {
    '[Content_Types].xml': `<Types xmlns="${pkg}/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>`,
    '_rels/.rels': `<Relationships xmlns="${pkg}/relationships"><Relationship Id="rId1" Type="${rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>`,
    'xl/workbook.xml': `<workbook xmlns="${main}" xmlns:r="${rel}"><sheets><sheet name="BOM" sheetId="1" r:id="rId1"/></sheets></workbook>`,
    'xl/_rels/workbook.xml.rels': `<Relationships xmlns="${pkg}/relationships"><Relationship Id="rId1" Type="${rel}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>`,
    'xl/worksheets/sheet1.xml': `<worksheet xmlns="${main}"><cols><col min="1" max="3" width="16" customWidth="1"/><col min="4" max="5" width="26" customWidth="1"/><col min="6" max="8" width="12" customWidth="1"/></cols><sheetData>${sheet}</sheetData><autoFilter ref="A1:H${rows.length + 1}"/></worksheet>`,
  };
  return zipSync(Object.fromEntries(Object.entries(docs).map(([name, content]) => [name, strToU8(declaration + content)])));
}

export function download(body, name, type) {
  const anchor = document.createElement('a');
  const url = URL.createObjectURL(new Blob([body], {type}));
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
