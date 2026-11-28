import { createHash } from 'node:crypto';
import { mkdir, readFile, rename, rm, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const manifest = JSON.parse(await readFile(new URL('./sucompute-data.json', import.meta.url), 'utf8'));
const output = fileURLToPath(new URL('../public/sucompute-data/', import.meta.url));
const defaultSource = fileURLToPath(new URL('../../../02-sansu-computing-dispatch/frontend_demo_data/', import.meta.url));
const source = process.argv[2] ? resolve(process.argv[2]) : defaultSource;
const checksum = (data) => createHash('sha256').update(data).digest('hex');
const files = Object.entries(manifest.files);
const matches = (data, sha) => data && checksum(data) === sha;
const local = (path) => readFile(path).catch((error) => {
  if (error.code !== 'ENOENT') throw error;
  return null;
});

const assets = await Promise.all(files.map(async ([name, sha]) => {
  const data = await local(join(source, name)) ?? await local(join(output, name));
  if (matches(data, sha)) return [name, data];
  if (process.argv[2]) throw new Error(`样例文件缺失或校验失败：${name}`);
  const response = await fetch(new URL(name, manifest.baseUrl), { signal: AbortSignal.timeout(30_000) });
  if (!response.ok) throw new Error(`读取固定回放 ${name} 失败（HTTP ${response.status}）`);
  const downloaded = Buffer.from(await response.arrayBuffer());
  if (!matches(downloaded, sha)) throw new Error(`回放文件校验失败：${name}`);
  return [name, downloaded];
}));

await mkdir(output, {recursive: true});
for (const [name, bytes] of assets) {
  const temporary = join(output, `.${name}.${process.pid}.tmp`);
  try {
    await writeFile(temporary, bytes);
    await rename(temporary, join(output, name));
  } finally {
    await rm(temporary, {force: true});
  }
}
console.log(`已校验并准备 ${assets.length} 个 SuCompute v2 静态回放文件（${manifest.commit.slice(0, 7)}）。`);
