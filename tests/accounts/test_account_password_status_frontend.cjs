const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');

const source = require('../frontend_script_sources.cjs').readAccountScript('accounts.js');
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));

function functionSource(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `应提供 ${name}`);
  const next = source.slice(start + 1).search(/\n(?:async )?function /);
  return source.slice(start, next < 0 ? undefined : start + 1 + next);
}

function view() {
  const context = vm.createContext({
    esc: escape, _liveCheckHttpStatus: () => null,
    _tokenDisplayState: row => ({key: row.has_access_token ? 'normal' : 'missing'}),
    _fmtPlanTime: value => value || '', facetLabel: (_group, value) => value || '',
    _accountPromotionDisplay: () => ({items: []}), _accountCountryPromotionDisplays: () => [],
    _accountPromotionGroups: () => [], _accountDetailFingerprintMarkup: () => '',
  });
  for (const name of ['_passwordCellV2', '_accountPasswordAuthDisplay', '_accountDetailState', '_accountDetailAuthMethod', '_accountDetailMarkup']) {
    vm.runInContext(functionSource(name), context);
  }
  return context;
}

test('详情把本地保存与远端记录分开，密码通过不等于已取得 Token', () => {
  const page = view();
  const html = page._accountDetailMarkup({id: 7, has_account_password: true,
    last_password_auth_status: 'verified', has_access_token: false, live_check_status: 'failed'});
  assert.match(html, /本地已保存/);
  assert.match(html, /最近远端密码结果/);
  assert.match(html, /登录验证通过/);
  assert.match(html, /最近一次有记录的认证结果/);
  assert.match(html, /不代表当前密码或登录态仍有效/);
  assert.match(html, /无 Token/);
  assert.match(html, /查活失败/);
  assert.doesNotMatch(html, /账号密码<\/span>\s*<div[^>]*>.*?<strong>已设置<\/strong>/s);
});

test('远端每一种记录有独立含义，旧数据和未识别值不追认为已通过', () => {
  const page = view();
  for (const [status, label] of [
    ['verified', '登录验证通过'], ['accepted', '创建密码被接受'], ['rejected', '密码被拒绝'],
    ['unknown', '密码验证记录不完整'], ['skipped', '未提交'], [undefined, '未验证'], ['success', '未验证'], ['constructor', '未验证'],
  ]) {
    const html = page._accountDetailMarkup({id: 8, has_account_password: true,
      has_access_token: true, last_auth_method: 'password', last_password_auth_status: status});
    const remoteLabel = html.match(/最近远端密码结果<\/span>[\s\S]*?<strong>([^<]*)<\/strong>/)?.[1];
    assert.equal(remoteLabel, label, String(status));
    if (!['verified', 'accepted'].includes(status)) assert.doesNotMatch(html, /<strong>(登录验证通过|创建密码被接受)<\/strong>/);
  }
});

test('密码列表保留按需复制，提示本地保存且显示最近远端结果', () => {
  const page = view();
  const saved = page._passwordCellV2({id: 9, has_account_password: true, last_password_auth_status: 'verified'});
  assert.match(saved, /data-account-copy-secret="account_password"/);
  assert.match(saved, /本地已保存/);
  assert.match(saved, /最近远端密码结果：登录验证通过/);
  assert.match(saved, />已验证<\/span>/);
  const legacy = page._passwordCellV2({id: 10, has_account_password: true});
  assert.match(legacy, />未验证<\/span>/);
  assert.doesNotMatch(legacy, /登录验证通过/);
  const missing = page._passwordCellV2({id: 11});
  assert.match(missing, /本地未保存/);
  assert.doesNotMatch(missing, /data-account-copy-secret/);
});
