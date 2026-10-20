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

function loadFunctions(names, dependencies = {}) {
  const context = {...dependencies};
  vm.createContext(context);
  for (const name of names) {
    const match = new RegExp(`(?:async )?function ${name}\\(`).exec(source);
    assert.ok(match, `缺少 ${name}`);
    const end = source.indexOf('\n}', match.index) + 2;
    vm.runInContext(source.slice(match.index, end), context);
  }
  return context;
}

function operationContext(name, response) {
  const calls = {requests: [], toasts: [], logs: [], accounts: 0, summary: 0};
  const names = ['accountBulkQueueReasons', name].filter(functionName => source.includes(`function ${functionName}(`));
  const context = loadFunctions(names, {
    ACCOUNT_SELECTED: new Set([306]),
    ACCOUNTS: [{id: 306, email: 'old@example.com', account_status: 'deactivated'}],
    getAccountOperationWorkers: () => 3,
    configuredLiveCheckDriver: () => 'protocol',
    confirm: () => true,
    api: async (url, options) => { calls.requests.push({url, options}); return response; },
    showToast: message => calls.toasts.push(message),
    openLiveLog: email => calls.logs.push(email),
    loadAccounts: async () => { calls.accounts += 1; },
    loadSummary: () => { calls.summary += 1; },
    updateAccountSelectionUi: () => {},
    $: () => null,
  });
  return {context, calls};
}

test('仅已停用账号的更多菜单提供已解封恢复入口，并保留正常账号动作保护', () => {
  const context = loadFunctions(['accountIsDeactivated', '_accountsV2MoreMenu'], {
    esc: value => String(value ?? ''),
    _planAction: () => '', _extractLinkAction: () => '', _codexAction: () => '',
  });
  const deactivated = context._accountsV2MoreMenu({id: 306, account_status: 'deactivated'});
  assert.match(deactivated, /data-account-restore="306"[^>]*>已解封，恢复账号<\/button>/);
  assert.doesNotMatch(deactivated, /data-account-action|刷新AT|>查活</);
  const active = context._accountsV2MoreMenu({id: 307, account_status: 'active'});
  assert.doesNotMatch(active, /data-account-restore/);
  assert.match(active, /刷新AT/);
});

test('恢复入口通过账号列表事件委托传递账号和按钮', async () => {
  const button = {dataset: {accountRestore: '306'}};
  const calls = [];
  const context = loadFunctions(['onAccountsBodyClick'], {
    restoreDeactivatedAccount: async (...args) => calls.push(args),
  });
  await context.onAccountsBodyClick({target: {closest: selector => selector === '[data-account-restore]' ? button : null}});
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], 306);
  assert.equal(calls[0][1], button);
});

test('确认解封后只解除本地停用标记，等待期间防止重复提交并刷新账号和摘要', async () => {
  let resolveRequest;
  const calls = {requests: [], confirms: [], toasts: [], accounts: 0, summary: 0};
  const context = loadFunctions(['accountIsDeactivated', 'restoreDeactivatedAccount'], {
    ACCOUNTS: [{id: 306, account_status: 'deactivated'}],
    confirm: message => { calls.confirms.push(message); return true; },
    api: (url, options) => { calls.requests.push({url, options}); return new Promise(resolve => { resolveRequest = resolve; }); },
    showToast: message => calls.toasts.push(message),
    loadAccounts: async () => { calls.accounts += 1; },
    loadSummary: async () => { calls.summary += 1; },
  });
  const button = {disabled: false, textContent: '已解封，恢复账号', isConnected: true};
  const pending = context.restoreDeactivatedAccount(306, button);
  assert.equal(button.disabled, true);
  assert.match(button.textContent, /恢复中/);
  await context.restoreDeactivatedAccount(306, button);
  assert.equal(calls.requests.length, 1);
  assert.equal(calls.confirms.length, 1);
  assert.match(calls.confirms[0], /已确认 OpenAI 恢复访问权限/);
  assert.match(calls.confirms[0], /历史封禁记录保留/);
  assert.match(calls.confirms[0], /AT 和 Codex 凭证需要重新验证/);
  assert.equal(calls.requests[0].url, '/api/accounts/306/restore');
  assert.equal(calls.requests[0].options.method, 'POST');
  assert.deepEqual(JSON.parse(calls.requests[0].options.body), {reason: '已收到 OpenAI 恢复访问通知'});
  resolveRequest({ok: true, message: '已解除本地停用标记，请刷新 AT 重新验证'});
  await pending;
  assert.deepEqual(calls.toasts, ['已解除本地停用标记，请刷新 AT 重新验证']);
  assert.equal(calls.accounts, 1);
  assert.equal(calls.summary, 1);
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, '已解封，恢复账号');
});

test('取消恢复确认时不请求接口，活跃操作错误直接反馈并恢复按钮', async () => {
  for (const accepted of [false, true]) {
    const calls = {requests: 0, toasts: []};
    const context = loadFunctions(['accountIsDeactivated', 'restoreDeactivatedAccount'], {
      ACCOUNTS: [{id: 306, account_status: 'deactivated'}],
      confirm: () => accepted,
      api: async () => { calls.requests += 1; throw new Error('账号存在活跃操作，请稍后恢复'); },
      showToast: message => calls.toasts.push(message),
      loadAccounts: () => assert.fail('失败或取消时不应刷新账号'),
      loadSummary: () => assert.fail('失败或取消时不应刷新摘要'),
    });
    const button = {disabled: false, textContent: '已解封，恢复账号', isConnected: true};
    await context.restoreDeactivatedAccount(306, button);
    assert.equal(calls.requests, accepted ? 1 : 0);
    assert.equal(calls.toasts.length, accepted ? 1 : 0);
    if (accepted) assert.match(calls.toasts[0], /账号存在活跃操作/);
    assert.equal(button.disabled, false);
    assert.equal(button.textContent, '已解封，恢复账号');
  }
});

test('刷新 AT 未入队时显示跳过原因且不打开账号旧日志', async () => {
  const {context, calls} = operationContext('refreshSelectedToken', {
    ok: true, started: [], started_count: 0, busy_count: 0, failed: [], failed_count: 0,
    skipped: [{id: 306, email: 'old@example.com', reason: '账号已标记为封号'}],
  });
  const button = {disabled: false, textContent: '刷新AT'};
  await context.refreshSelectedToken([306], button);
  assert.deepEqual(calls.logs, []);
  assert.match(calls.toasts[0], /入队 0 个.*跳过 1/);
  assert.match(calls.toasts[0], /账号已标记为封号/);
  assert.equal(calls.accounts, 1);
  assert.equal(calls.summary, 1);
  assert.equal(button.disabled, false);
});

test('刷新 AT 仅打开本次新入队账号日志，并最多展示三条跳过或失败原因', async () => {
  const {context, calls} = operationContext('refreshSelectedToken', {
    ok: true, started: [{id: 307, email: 'new@example.com', status: 'queued'}], started_count: 1, busy_count: 0,
    skipped: [{id: 306, reason: '原因一'}, {id: 308, reason: '原因二'}],
    failed: [{id: 309, error: '入队失败原因三'}, {id: 310, error: '原因四'}], failed_count: 2,
  });
  await context.refreshSelectedToken([306, 307], {disabled: false, textContent: '刷新AT'});
  assert.deepEqual(calls.logs, ['new@example.com']);
  assert.match(calls.toasts[0], /原因一.*原因二.*入队失败原因三/);
  assert.doesNotMatch(calls.toasts[0], /原因四/);
});

test('查活未入队时不打开账号旧日志，且展示跳过原因', async () => {
  const {context, calls} = operationContext('checkSelectedLive', {
    ok: true, started: [], started_count: 0, busy_count: 0, failed: [], failed_count: 0,
    skipped: [{id: 306, reason: '账号已标记为封号'}], live_check_driver: 'protocol',
  });
  await context.checkSelectedLive([306], {disabled: false, textContent: '查活'});
  assert.deepEqual(calls.logs, []);
  assert.match(calls.toasts[0], /账号已标记为封号/);
});

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
