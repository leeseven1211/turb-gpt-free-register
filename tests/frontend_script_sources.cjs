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

// Extracted-function fixtures need the real explicit action boundary as well as
// the action under test. A browser window and legacy mailbox map belong to the
// fixture environment, while all decision/refresh logic comes from production.
function installAccountActionHelpers(context) {
  const vm = require('node:vm');
  context.window ||= {};
  context.ACCOUNT_SELECTED_EMAILS ||= new Map();
  const source = readAccountScript('accounts.js');
  const names = ['accountActionOwner', 'freezeAccountActionValue', 'captureAccountActionContext',
    'accountActionIds', 'accountActionRow', 'accountActionRefresh', 'accountActionPollStatuses',
    'accountActionSelectionUi', 'accountActionRemoveAcknowledged', 'accountActionClearSelection'];
  for (const name of names) {
    const start = source.indexOf(`function ${name}(`);
    if (start < 0) throw new Error(`缺少账号动作 helper ${name}`);
    const end = source.indexOf('\n}', start) + 2;
    vm.runInContext(source.slice(start, end), context, {filename: `accounts.js:${name}`});
  }
}

module.exports = {readAccountScripts, readAccountScript, loadedFiles, installAccountActionHelpers};
