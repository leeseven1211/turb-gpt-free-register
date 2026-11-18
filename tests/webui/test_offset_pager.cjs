const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const {createRequire} = require('node:module');
const {JSDOM} = createRequire(path.resolve(__dirname, '../../frontend/package.json'))('jsdom');

const common = fs.readFileSync(path.resolve(__dirname, '../../webui/static/js/shared/common.js'), 'utf8');
const pager = common.slice(common.indexOf('// ---------- 分页状态'), common.indexOf('// ---------- 统一列表列宽'));

function view(t, total) {
  const dom = new JSDOM('<div class="jobs-v2-pager" id="pager-accounts-v2"></div>', {runScripts: 'dangerously'});
  t.after(() => dom.window.close());
  const {window} = dom;
  window.eval(`${pager}\nwindow.accounts = PAGERS.accounts;`);
  const reloads = [];
  for (const name of ['refreshJobs', 'loadOutlook', 'loadCodex', 'loadAccountTasks', 'loadEmailDerivationResources']) window[name] = () => {};
  window.loadAccounts = () => reloads.push([window.accounts.page, window.accounts.size]);
  const render = count => { window.ACCOUNTS_TOTAL = count; window._renderPager('accounts', count); };
  render(total);
  return {document: window.document, window, render, reloads};
}

test('后台更新总数时保留正在输入的页码，提交仅加载一次且夹在有效页内', t => {
  const {document, render, reloads} = view(t, 121);
  const input = document.querySelector('input');
  input.focus();
  input.value = '6';
  render(122);
  assert.equal(document.activeElement, input);
  assert.equal(input.value, '6');
  assert.match(document.body.textContent, /共 122 条/);
  render(131);
  assert.equal(document.activeElement, input);
  assert.equal(input.value, '6');
  assert.ok(document.querySelector('[aria-label="第 14 页"]'));
  input.form.requestSubmit();
  assert.deepEqual(reloads, [[6, 10]]);
  render(122);
  const next = document.querySelector('input');
  next.value = '999';
  next.form.requestSubmit();
  assert.deepEqual(reloads, [[6, 10], [13, 10]]);
  render(122);
  assert.match(document.body.textContent, /121–122/);
  assert.equal(document.querySelector('[aria-current="page"]').textContent, '13');
  assert.equal(document.querySelector('[title="下一页"]').disabled, true);
});

test('无效页码和空列表均不会触发翻页，修改每页条数从第一页读取', t => {
  const {document, render, reloads, window} = view(t, 90);
  for (const value of ['', '2.5', '1e2', 'other']) {
    window.pagerJump('accounts', value);
  }
  assert.deepEqual(reloads, []);
  window.pagerGoTo('accounts', 7);
  render(90);
  const size = document.querySelector('select');
  size.value = '30';
  size.dispatchEvent(new window.Event('change'));
  assert.deepEqual(reloads, [[7, 10], [1, 30]]);
  render(0);
  assert.match(document.body.textContent, /共 0 条/);
  assert.equal(document.querySelector('input').disabled, true);
  assert.equal(document.querySelector('[title="下一页"]').disabled, true);
  window.pagerJump('accounts', '3');
  assert.deepEqual(reloads, [[7, 10], [1, 30]]);
});
