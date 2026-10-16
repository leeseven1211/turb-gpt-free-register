const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/accounts.js'), 'utf8');
function render(name, row) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `缺少 ${name}`);
  const next = source.slice(start + 1).search(/\n(?:async )?function /);
  const context = {esc: value => String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char])), accountIsDeactivated: value => value.account_status === 'deactivated'};
  vm.createContext(context);
  vm.runInContext(source.slice(start, next < 0 ? undefined : start + 1 + next), context);
  return context[name](row);
}

test('封号邮件复查沿用可操作状态样式，扫描中不出现重复入口', () => {
  const html = render('_deactivationMailCell', {id: 7, email_source: 'icloud_hide', deactivation_mail_scan_status: 'success'});
  assert.match(html, /class="account-cell-lines status-action-cell"/);
  assert.match(html, /data-deactivation-mail-check="7"[^>]*>复查<\/button>/);
  assert.doesNotMatch(render('_deactivationMailCell', {id: 7, email_source: 'icloud_hide', deactivation_mail_scan_status: 'running'}), /data-deactivation-mail-check/);
});

test('2FA 只显示复制或补充，并复用现有账号动作入口', () => {
  const enabled = render('_totpCellV2', {id: 7, totp_enabled: true});
  assert.match(enabled, /data-account-totp-copy="7"[^>]*>复制<\/button>/);
  assert.doesNotMatch(enabled, /已启用|data-account-action/);
  const missing = render('_totpCellV2', {id: 8, totp_enabled: false});
  assert.match(missing, /data-account-action="twofa" data-account-id="8"[^>]*>补充<\/button>/);
  assert.doesNotMatch(missing, /未启用|data-account-totp-copy/);
  assert.match(render('_totpCellV2', {id: 8, account_status: 'deactivated'}), /disabled/);
});

test('创建和更新时间各占一行，缺失更新不伪造，完整时间保留在提示中', () => {
  const html = render('_accountTimesCellV2', {created_at: '2026-10-16T09:06:12', updated_at: '2026-10-17T10:11:12'});
  assert.match(html, /创建[\s\S]*10-16 09:06[\s\S]*更新[\s\S]*10-17 10:11/);
  assert.match(html, /2026-10-16 09:06:12/);
  assert.match(html, /2026-10-17 10:11:12/);
  const missing = render('_accountTimesCellV2', {created_at: '2026-10-16T09:06:12'});
  assert.match(missing, /更新<\/span><time[^>]*>-<\/time>/);
});
