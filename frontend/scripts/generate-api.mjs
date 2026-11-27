import { readFile, writeFile, mkdir } from 'node:fs/promises';
import openapiTS, { astToString } from 'openapi-typescript';

for (const [contract, output] of [
  ['task-center', 'schema'],
  ['codex', 'codex-schema'],
  ['accounts', 'accounts-schema'],
  ['bulk-mutations', 'bulk-mutations-schema'],
  ['teams', 'teams-schema'],
]) {
  const source = new URL(`../../contracts/${contract}.openapi.json`, import.meta.url);
  const destination = new URL(`../src/api/${output}.d.ts`, import.meta.url);
  const generated = `// 由 contracts/${contract}.openapi.json 生成，请运行 npm run generate:api。\n`
    + astToString(await openapiTS(source));
  if (process.argv.includes('--check')) {
    if (await readFile(destination, 'utf8').catch(() => '') !== generated) {
      throw new Error(`${contract} API 类型已过期，请运行 npm run generate:api 并一同提交。`);
    }
  } else {
    await mkdir(new URL('../src/api/', import.meta.url), { recursive: true });
    await writeFile(destination, generated);
  }
}
