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

test('封号邮件列统一显示复查按钮并按扫描状态禁用', () => {
  const unscanned = render('_deactivationMailCell', {id: 1, email_source: 'icloud_hide'});
  assert.match(unscanned, /class="account-cell-lines status-action-cell"/);
  assert.match(unscanned, /data-deactivation-mail-check="1"[^>]*>复查<\/button>/);
  assert.doesNotMatch(unscanned, /class="pill/);

  const success = render('_deactivationMailCell', {
    id: 2,
    email_source: 'icloud_hide',
    deactivation_mail_scan_status: 'success',
    deactivation_mail_checked_at: '2026-10-16 10:11:12',
  });
  assert.match(success, /data-deactivation-mail-check="2"[^>]*>复查<\/button>/);
  assert.match(success, /title="扫描时间: 2026-10-16 10:11:12"/);
  assert.doesNotMatch(success, /未发现|class="pill/);

  const failed = render('_deactivationMailCell', {
    id: 3,
    email_source: 'icloud_hide',
    deactivation_mail_scan_status: 'failed',
    deactivation_mail_error: '邮箱暂不可读',
  });
  assert.match(failed, /data-deactivation-mail-check="3"[^>]*>复查<\/button>/);
  assert.match(failed, /title="邮箱暂不可读"/);
  assert.doesNotMatch(failed, /扫描失败|class="pill/);

  const detected = render('_deactivationMailCell', {
    id: 4,
    email_source: 'icloud_hide',
    deactivation_mail_detected: true,
    deactivation_mail_scan_status: 'success',
    deactivation_mail_received_at: '2026-10-16 10:11:12',
    deactivation_mail_sender: 'no-reply@example.com',
    deactivation_mail_subject: '账号通知',
  });
  assert.match(detected, /class="pill status-failed"[^>]*>封号<\/span>/);
  assert.doesNotMatch(detected, /data-deactivation-mail-check|复查/);
  assert.match(detected, /收件: 2026-10-16 10:11:12；发件人: no-reply@example.com；账号通知/);

  for (const [id, status, label] of [[5, 'queued', '排队中'], [6, 'running', '扫描中']]) {
    const html = render('_deactivationMailCell', {id, email_source: 'icloud_hide', deactivation_mail_scan_status: status});
    assert.match(html, new RegExp(`data-deactivation-mail-check="${id}"[^>]*disabled[^>]*>复查<\\/button>`));
    assert.match(html, new RegExp(`title="${label}；正在扫描邮箱，不会刷新 AT"`));
    assert.doesNotMatch(html, /class="pill/);
  }

  const unsupported = render('_deactivationMailCell', {
    id: 7,
    email_source: 'other',
    deactivation_mail_scan_status: 'unsupported',
    deactivation_mail_error: '当前邮箱来源不支持',
  });
  assert.match(unsupported, /data-deactivation-mail-check="7"[^>]*disabled[^>]*>复查<\/button>/);
  assert.match(unsupported, /title="当前邮箱来源不支持"/);
  assert.doesNotMatch(unsupported, /不支持<\/span>|class="pill/);
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
