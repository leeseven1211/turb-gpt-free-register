// 按模板实际引用顺序读取账号页面脚本，供源码和初始化测试共用。
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'webui/templates/index.html'), 'utf8');
const accountFiles = new Map([
  ['accounts.js', 'js/pages/accounts/page.js'],
  ['account-tasks.js', 'js/pages/operations/page.js'],
  ['account-email-change.js', 'js/pages/accounts/email-change.js'],
  ['account-inspection.js', 'js/pages/accounts/inspection.js'],
]);
const accountNames = new Map(Array.from(accountFiles, ([name, file]) => [file, name]));
const loadedFiles = Array.from(template.matchAll(/filename='([^']+)'/g), match => accountNames.get(match[1]))
  .filter(Boolean);
if (loadedFiles.length !== accountFiles.size || new Set(loadedFiles).size !== accountFiles.size) {
  throw new Error('账号页面脚本加载清单不完整或重复');
}

function readAccountScripts() {
  return loadedFiles.map(name => fs.readFileSync(path.join(root, 'webui/static', accountFiles.get(name)), 'utf8')).join('\n');
}

function readAccountScript(name) {
  if (!loadedFiles.includes(name)) throw new Error(`页面未加载 ${name}`);
  return fs.readFileSync(path.join(root, 'webui/static', accountFiles.get(name)), 'utf8');
}

module.exports = {readAccountScripts, readAccountScript, loadedFiles};
