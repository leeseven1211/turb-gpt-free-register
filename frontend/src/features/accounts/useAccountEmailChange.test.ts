import {effectScope, type EffectScope} from 'vue';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {useAccountEmailChange, type AccountEmailChangeDependencies} from './useAccountEmailChange';
import type {AccountActionContext} from './useAccounts';
import {accountRow, deferred, realAdapter} from './uiTestSupport';

const scopes: EffectScope[] = [];
afterEach(() => scopes.splice(0).forEach(scope => scope.stop()));
async function settle() { for (let i = 0; i < 10; i++) await Promise.resolve(); }
function context(ids = ['7'], source = 'outlook'): AccountActionContext {
  return {accountIds: ids, expectedEmails: Object.fromEntries(ids.map(id => [id, `old-${id}@test`])),
    rowHints: ids.map(id => accountRow(Number(id), {email: `old-${id}@test`, email_source: source})),
    querySnapshot: realAdapter().normalize(), archived: '0'};
}
const sources = {ok: true, sources: [
  {value: 'outlook', label: 'Outlook', enabled: true, reason: ''},
  {value: 'cloudflare', label: 'Cloudflare', enabled: true, reason: ''},
  {value: 'icloud_hide', label: 'iCloud', enabled: false, reason: '尚未配置'},
]};
function setup(overrides: Partial<AccountEmailChangeDependencies> = {}) {
  const chosen: AccountEmailChangeDependencies = {request: vi.fn<AccountEmailChangeDependencies['request']>(async () => sources),
    notify: vi.fn(), refreshAccounts: vi.fn(), openTasks: vi.fn(),
    syncModalScrollLock: vi.fn(), ...overrides};
  const deps = {...chosen, notify: vi.fn(chosen.notify)};
  const lifecycle = {opened: vi.fn(), closed: vi.fn(), sourcesReady: vi.fn()};
  const scope = effectScope(); scopes.push(scope);
  const owner = scope.run(() => useAccountEmailChange(deps, lifecycle))!;
  return {owner, deps, lifecycle, scope};
}

describe('换邮 opening 和提交 owner', () => {
  it('按打开快照选择可用来源，保留不可用原因且不修改原context', async () => {
    const {owner} = setup(); const ctx = context(['7'], ' CLOUDFLARE ');
    expect(owner.openSingle(7, ctx, null)).toBe(true); await settle();
    expect(owner.source.value).toBe('cloudflare');
    expect(owner.sources.value).toEqual([
      {value: 'outlook', label: 'Outlook', enabled: true, reason: ''},
      {value: 'cloudflare', label: 'Cloudflare', enabled: true, reason: ''},
      {value: 'icloud_hide', label: 'iCloud', enabled: false, reason: '尚未配置'},
    ]);
    expect(owner.account.value).toEqual({id: 7, email: 'old-7@test', email_source: ' CLOUDFLARE '});
    expect(Object.isFrozen(owner.context.value)).toBe(true);
    expect(Object.isFrozen(owner.context.value?.querySnapshot.filters)).toBe(true);
    ctx.rowHints[0].email = 'new@test'; expect(owner.account.value?.email).toBe('old-7@test');
  });

  it('不可用首选回退到首个可用来源，无可用来源显示原错误', async () => {
    const f = setup(); f.owner.openSingle(7, context(['7'], 'icloud_hide'), null); await settle();
    expect(f.owner.source.value).toBe('outlook');
    const none = setup({request: vi.fn(async () => ({sources: [{value: 'outlook', enabled: false, reason: '禁用'}]}))});
    none.owner.openSingle(7, context(), null); await settle();
    expect(none.owner.sourceDisabled.value).toBe(true); expect(none.owner.source.value).toBe('');
    expect(none.owner.error.value).toBe('没有已配置且可用的新邮箱来源');
  });

  it.each(['resolve', 'reject'] as const)('关闭换窗后旧来源 %s 不改新窗口且旧signal中止', async outcome => {
    const old = deferred<unknown>(), fresh = deferred<unknown>();
    const request = vi.fn<AccountEmailChangeDependencies['request']>().mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);
    const f = setup({request}); f.owner.openSingle(7, context(), null);
    const signal = request.mock.calls[0][1]?.signal;
    f.owner.close(); f.owner.openSingle(8, context(['8'], 'cloudflare'), null);
    expect(signal?.aborted).toBe(true);
    fresh.resolve(sources); await settle();
    if (outcome === 'resolve') old.resolve({sources: [{value: 'outlook', label: '旧', enabled: true}]});
    else old.reject(new Error('old read failed'));
    await settle(); expect(f.owner.source.value).toBe('cloudflare'); expect(f.owner.account.value?.id).toBe(8);
    expect(f.owner.error.value).toBe(''); expect(f.lifecycle.sourcesReady).toHaveBeenCalledTimes(1);
  });

  it('来源读取失败只写当前opening，关闭后不中断任何提交', async () => {
    const request = vi.fn(async () => { throw new Error('offline'); }); const f = setup({request});
    f.owner.openSingle(7, context(), null); await settle();
    expect(f.owner.sourceStatus.value).toBe('failed'); expect(f.owner.error.value).toBe('邮箱来源读取失败：offline');
    expect(f.owner.sourceDisabled.value).toBe(true);
  });

  it('bulk去重正整数、500上限，非法新打开不会覆盖当前窗口', async () => {
    const f = setup(); expect(f.owner.openBulk(context(['7', '7', '8', '0', '-1', 'bad', '1.5']), null)).toBe(true);
    await settle(); expect(f.owner.accountIds.value).toEqual(['7', '8']); expect(f.owner.mode.value).toBe('bulk');
    expect(f.owner.openBulk(context([]), null)).toBe(false);
    expect(f.deps.notify).toHaveBeenCalledWith('请先选择账号');
    expect(f.owner.openBulk(context(Array.from({length: 501}, (_, i) => String(i + 1))), null)).toBe(false);
    expect(f.deps.notify).toHaveBeenCalledWith('单次最多换绑 500 个账号'); expect(f.owner.accountIds.value).toEqual(['7', '8']);
    expect(f.owner.openSingle(9, context(['7']), null)).toBe(false);
    expect(f.deps.notify).toHaveBeenCalledWith('账号详情暂不可用，请先刷新列表');
  });

  it('single提交只发来源并使用打开时账号/邮箱，不受后续context修改影响', async () => {
    const request = vi.fn<AccountEmailChangeDependencies['request']>().mockResolvedValueOnce(sources)
      .mockResolvedValueOnce({ok: true, accepted: true, task_id: 71, run_id: 22, message: '邮箱换绑已入队'});
    const f = setup({request}), ctx = context(); f.owner.openSingle(7, ctx, null); await settle();
    ctx.accountIds = ['99']; ctx.rowHints[0].email = 'different@test';
    await f.owner.submit();
    expect(request.mock.calls[1]).toEqual(['/api/accounts/7/email-change', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{"email_source":"outlook"}',
    }]);
    expect(f.owner.isOpen.value).toBe(false);
    expect(f.deps.openTasks).toHaveBeenCalledWith({filters: {target: 'old-7@test', type: 'email_change'}, taskId: 71, runId: 22});
    expect(f.lifecycle.closed).toHaveBeenCalledWith(false, null, expect.any(Number));
  });

  it('单个换绑缺少当前邮箱时按账号ID筛选任务列表', async () => {
    const request = vi.fn<AccountEmailChangeDependencies['request']>().mockResolvedValueOnce(sources)
      .mockResolvedValueOnce({ok: true, accepted: true});
    const f = setup({request}), ctx = context();
    ctx.rowHints[0]!.email = '';
    f.owner.openSingle(7, ctx, null); await settle(); await f.owner.submit();
    expect(f.deps.openTasks).toHaveBeenCalledExactlyOnceWith({filters: {target: '7', type: 'email_change'}});
  });

  it('bulk提交去重IDs及来源，保留started/skipped受理文案和空target', async () => {
    const request = vi.fn<AccountEmailChangeDependencies['request']>().mockResolvedValueOnce(sources)
      .mockResolvedValueOnce({ok: true, started_count: 1, skipped_count: 1, started: [{task_id: 71}], skipped: [{account_id: 8, error: '已有任务'}]});
    const f = setup({request}); f.owner.openBulk(context(['7', '8', '7']), null); await settle(); await f.owner.submit();
    expect(request.mock.calls[1][0]).toBe('/api/accounts/email-change-bulk');
    expect(JSON.parse(String(request.mock.calls[1][1]?.body))).toEqual({account_ids: [7, 8], email_source: 'outlook'});
    expect(f.deps.notify).toHaveBeenCalledWith('批量换绑已入队 1 个，跳过 1 个；未入队原因：已有任务');
    expect(f.deps.openTasks).toHaveBeenCalledWith({filters: {target: '', type: 'email_change'}});
  });

  it('批量只有一个受理任务时仍只打开任务列表，不进入首条详情', async () => {
    const request = vi.fn<AccountEmailChangeDependencies['request']>().mockResolvedValueOnce(sources)
      .mockResolvedValueOnce({ok: true, started_count: 1, started: [{task_id: 71, run_id: 72}]});
    const openTask = vi.fn();
    const f = setup({request, openTask} as unknown as Partial<AccountEmailChangeDependencies>);
    f.owner.openBulk(context(['7'])); await settle(); await f.owner.submit();
    expect(f.deps.openTasks).toHaveBeenCalledExactlyOnceWith({filters: {target: '', type: 'email_change'}});
    expect(openTask).not.toHaveBeenCalled();
  });

  it('批量未入队没有原因时保持原有数量提示', async () => {
    const request = vi.fn<AccountEmailChangeDependencies['request']>().mockResolvedValueOnce(sources)
      .mockResolvedValueOnce({ok: true, started_count: 1, skipped_count: 1, started: [{task_id: 71}], skipped: [{account_id: 8}]});
    const f = setup({request});
    f.owner.openBulk(context(['7', '8'])); await settle(); await f.owner.submit();
    expect(f.deps.notify).toHaveBeenCalledWith('批量换绑已入队 1 个，跳过 1 个');
  });

  it('批量全部未入队时保留已受理提示但不打开任务列表', async () => {
    const request = vi.fn<AccountEmailChangeDependencies['request']>().mockResolvedValueOnce(sources)
      .mockResolvedValueOnce({ok: true, started_count: 0, started: [], skipped_count: 1, skipped: [{reason: '已有任务'}]});
    const f = setup({request});
    f.owner.openBulk(context(['7'])); await settle(); await f.owner.submit();
    expect(f.deps.openTasks).not.toHaveBeenCalled();
    expect(f.deps.notify).toHaveBeenCalledWith('批量换绑已入队 0 个，跳过 1 个；未入队原因：已有任务');
  });

  it('同opening提交等待期间防重，空/不可用来源不发POST', async () => {
    const response = deferred<unknown>();
    const request = vi.fn<AccountEmailChangeDependencies['request']>().mockResolvedValueOnce(sources).mockReturnValueOnce(response.promise);
    const f = setup({request}); f.owner.openSingle(7, context(), null); await settle();
    for (const value of ['', 'icloud_hide']) { f.owner.source.value = value; await f.owner.submit(); }
    expect(request).toHaveBeenCalledTimes(1); expect(f.owner.error.value).toBe('请选择新邮箱来源');
    f.owner.source.value = 'outlook'; const submitting = f.owner.submit(); await f.owner.submit();
    expect(request).toHaveBeenCalledTimes(2); expect(f.owner.submitting.value).toBe(true);
    response.reject(new Error('HTTP 409')); await submitting;
    expect(f.owner.isOpen.value).toBe(true); expect(f.owner.submitting.value).toBe(false);
    expect(f.owner.error.value).toBe('提交失败：HTTP 409'); expect(f.deps.openTasks).not.toHaveBeenCalled();
  });

  it.each(['success', 'failure'] as const)('旧POST %s不能关闭改写新窗或改变新submit状态', async outcome => {
    const old = deferred<unknown>(), current = deferred<unknown>();
    const request = vi.fn<AccountEmailChangeDependencies['request']>().mockResolvedValueOnce(sources).mockReturnValueOnce(old.promise)
      .mockResolvedValueOnce(sources).mockReturnValueOnce(current.promise);
    const f = setup({request}); f.owner.openSingle(7, context(), null); await settle(); const oldSubmit = f.owner.submit();
    expect(request.mock.calls[1][1]?.signal).toBeUndefined();
    f.owner.close(); f.owner.openSingle(8, context(['8'], 'cloudflare'), null); await settle(); const newSubmit = f.owner.submit();
    if (outcome === 'success') old.resolve({ok: true, accepted: true, task_id: 71}); else old.reject(new Error('old failed'));
    await oldSubmit;
    expect(f.owner.isOpen.value).toBe(true); expect(f.owner.account.value?.id).toBe(8); expect(f.owner.source.value).toBe('cloudflare');
    expect(f.owner.submitting.value).toBe(true); expect(f.owner.error.value).toBe(''); expect(f.deps.openTasks).not.toHaveBeenCalled();
    if (outcome === 'success') {
      expect(f.deps.refreshAccounts).toHaveBeenCalledTimes(1);
    } else expect(f.deps.notify).toHaveBeenCalledWith('换绑邮箱失败: old failed');
    current.resolve({ok: true, accepted: true, task_id: 81}); await newSubmit;
    expect(f.deps.openTasks).toHaveBeenCalledExactlyOnceWith({filters: {target: 'old-8@test', type: 'email_change'}, taskId: 81, runId: null});
  });

  it('受理后refresh故障不把已受理当提交失败，也不重发POST', async () => {
    const request = vi.fn<AccountEmailChangeDependencies['request']>().mockResolvedValueOnce(sources).mockResolvedValueOnce({ok: true, task_id: 71});
    const f = setup({request, refreshAccounts: vi.fn(async () => {throw new Error('refresh failed');})});
    f.owner.openSingle(7, context(), null); await settle(); await f.owner.submit(); await settle();
    expect(request).toHaveBeenCalledTimes(2); expect(f.owner.isOpen.value).toBe(false);
    expect(f.deps.openTasks).toHaveBeenCalledWith({filters: {target: 'old-7@test', type: 'email_change'}, taskId: 71, runId: null});
    expect(f.deps.notify.mock.calls.flat().join(' ')).not.toContain('换绑邮箱失败');
  });

  it('卸载取消来源GET，旧POST成功仍刷新但不导航', async () => {
    const pending = deferred<unknown>(); const request = vi.fn<AccountEmailChangeDependencies['request']>().mockResolvedValueOnce(sources).mockReturnValueOnce(pending.promise);
    const f = setup({request}); f.owner.openSingle(7, context(), null); await settle(); const submitting = f.owner.submit(); f.scope.stop();
    expect(request.mock.calls[0][1]?.signal?.aborted).toBe(true); expect(request.mock.calls[1][1]?.signal).toBeUndefined();
    pending.resolve({ok: true, task_id: 71}); await submitting;
    expect(f.deps.refreshAccounts).toHaveBeenCalledTimes(1);
    expect(f.deps.openTasks).not.toHaveBeenCalled(); expect(f.owner.isOpen.value).toBe(false);
  });
});
