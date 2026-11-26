import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {request} from '../../api/client';
import {createAccountActions, type AccountActionDependencies} from './actions';
import type {AccountQueuedDependencies} from './queuedActions';
import type {AccountActionContext, AccountViewRow} from './useAccounts';
import {accountRow, deferred, realAdapter} from './uiTestSupport';

const fetchMock = vi.fn<typeof fetch>();
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {status, headers: {'Content-Type': 'application/json'}});
const receipt = (extra: Record<string, unknown> = {}) => ({ok: true, started_count: 1, started: [{id: 7, email: 'seven@test'}],
  busy_count: 0, busy: [], failed_count: 0, failed: [], skipped_count: 0, skipped: [], ...extra});
function context(ids = ['7', '11'], rows: AccountViewRow[] = []): AccountActionContext {
  return {accountIds: ids, expectedEmails: {'7':'seven@test','11':'eleven@test'}, querySnapshot: realAdapter().normalize(), archived: '0', rowHints: rows};
}
function setup(overrides: Partial<AccountQueuedDependencies> = {}, baseOverrides: Partial<AccountActionDependencies> = {}) {
  const queued: AccountQueuedDependencies = {
    refresh: async () => {}, pollStatuses: async () => {}, refreshSummary: () => {}, reloadTasks: () => {},
    operationWorkers: () => 50, configuredLiveCheckDriver: () => 'protocol', readConfig: async () => [], fallbackConfig: () => [],
    openLiveLog: () => {}, openAccountTaskLog: () => {}, openTasks: () => {}, getRowSnapshot: () => undefined, isOwnerActive: () => true,
    clearScheduled: handle => clearTimeout(handle as ReturnType<typeof setTimeout>), ...overrides,
  };
  const q = {...queued, refresh: vi.fn(queued.refresh), pollStatuses: vi.fn(queued.pollStatuses), refreshSummary: vi.fn(queued.refreshSummary),
    reloadTasks: vi.fn(queued.reloadTasks), readConfig: vi.fn(queued.readConfig), fallbackConfig: vi.fn(queued.fallbackConfig),
    openLiveLog: vi.fn(queued.openLiveLog), openAccountTaskLog: vi.fn(queued.openAccountTaskLog), openTasks: vi.fn(queued.openTasks),
    getRowSnapshot: vi.fn(queued.getRowSnapshot), isOwnerActive: vi.fn(queued.isOwnerActive), clearScheduled: vi.fn(queued.clearScheduled)};
  const restore = vi.fn(), label = vi.fn();
  const defaults: AccountActionDependencies = {request, notify: () => {}, confirm: () => true, clipboard: async () => true,
    downloadBlob() {}, downloadUrl() {}, now: () => new Date(), schedule: (callback, delay) => setTimeout(callback, delay), reloadCodex() {},
    beginBusy: () => restore, canInvoke: () => true, queued: q, ...baseOverrides};
  const deps = {...defaults, notify: vi.fn(defaults.notify), confirm: vi.fn(defaults.confirm), beginBusy: vi.fn(defaults.beginBusy)};
  return {actions: createAccountActions(deps), q, deps, restore, label};
}
function body(index = 0) {return JSON.parse(fetchMock.mock.calls[index]![1]!.body as string);}
function messages(h: ReturnType<typeof setup>) {return h.deps.notify.mock.calls.flat().join(' ');}
beforeEach(() => {vi.useFakeTimers(); vi.stubGlobal('fetch', fetchMock); fetchMock.mockReset(); sessionStorage.clear();});
afterEach(() => {vi.useRealTimers(); vi.unstubAllGlobals(); sessionStorage.clear();});

describe('queued action boundary', () => {
  it('requires opt-in dependencies and preserves already migrated secret support', async () => {
    const noQueued = setup({}, {queued: undefined});
    expect(noQueued.actions.isSupported('plan-check')).toBe(false); expect(noQueued.actions.isSupported('account-totp-copy')).toBe(true);
    const {actions} = setup();
    for (const name of ['plan-check','checkSelectedPlans','account-live-check','checkSelectedLive','account-refresh-token','refreshSelectedToken','deactivation-mail-check','checkSelectedDeactivationMail','extract-link','extractSelectedLinks']) expect(actions.isSupported(name)).toBe(true);
    expect(actions.isSupported('plan-check:7')).toBe(false); expect(actions.isSupported('account-delete')).toBe(false); expect(fetchMock).not.toHaveBeenCalled();
  });
  it('blocks gated actions before config, confirmation or HTTP', async () => {
    const h = setup({}, {canInvoke: () => false}); await h.actions.invoke('refreshSelectedToken', context());
    expect(h.q.readConfig).not.toHaveBeenCalled(); expect(h.deps.confirm).not.toHaveBeenCalled(); expect(fetchMock).not.toHaveBeenCalled();
  });
  it.each(['plan-check','account-live-check','account-refresh-token','deactivation-mail-check','extract-link'])('requires one ID for %s', async name => {
    const h = setup(); await h.actions.invoke(name, context()); expect(fetchMock).not.toHaveBeenCalled(); expect(messages(h)).toContain('一个账号');
  });
  it('invalid IDs and empty selection cannot create tasks', async () => {
    const h = setup(); await h.actions.invoke('checkSelectedPlans', context([])); await h.actions.invoke('checkSelectedPlans', context(['9007199254740993']));
    expect(fetchMock).not.toHaveBeenCalled(); expect(messages(h)).toContain('请先选择账号'); expect(messages(h)).toContain('账号 ID 无效');
  });
});

describe('任务中心导航契约', () => {
  const bulkCases = [
    ['checkSelectedPlans', 'plan_check'],
    ['checkSelectedLive', 'live_check'],
    ['refreshSelectedToken', 'token_refresh'],
    ['checkSelectedDeactivationMail', 'deactivation_mail'],
    ['extractSelectedLinks', 'extract_link'],
  ] as const;
  it.each(bulkCases)('批量 %s 即使只选一个账号也按类型打开任务列表', async (name, type) => {
    const h = setup(name === 'checkSelectedDeactivationMail' ? {getRowSnapshot: () => ({deactivation_mail_scan_status: 'done'})} : {});
    fetchMock.mockResolvedValue(json(receipt({started_count: 1, started: [{task_id: 101, run_id: 102, email: 'seven@test'}]}), 202));
    await h.actions.invoke(name, context(['7']));
    if (name === 'checkSelectedDeactivationMail') await vi.advanceTimersByTimeAsync(1500);
    expect(h.q.openTasks).toHaveBeenCalledWith({filters: {type, target: ''}});
    expect(h.q.openAccountTaskLog).not.toHaveBeenCalled();
    expect(h.q.openLiveLog).not.toHaveBeenCalled();
  });
  it.each(bulkCases)('批量 %s 全部未入队时不打开任务中心', async name => {
    const h = setup();
    const reason = name === 'checkSelectedDeactivationMail' ? '邮箱不可用' : name === 'extractSelectedLinks' ? '资格不满足' : '';
    fetchMock.mockResolvedValue(json(receipt({
      started_count: 0, started: [], busy_count: 1, skipped_count: 1, skipped: reason ? [{reason}] : [],
    }), 202));
    await h.actions.invoke(name, context(['7']));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(h.q.openTasks).not.toHaveBeenCalled();
    expect(h.q.openAccountTaskLog).not.toHaveBeenCalled();
    expect(h.q.openLiveLog).not.toHaveBeenCalled();
    if (reason) expect(messages(h)).toContain(reason);
  });
  const singleCases = [
    ['plan-check', 'plan_check', {ok: true, started: true, accepted: true}],
    ['account-live-check', 'live_check', receipt({started: [{email: 'seven@test'}]})],
    ['account-refresh-token', 'token_refresh', receipt({started: [{email: 'seven@test'}]})],
    ['deactivation-mail-check', 'deactivation_mail', {ok: true, accepted: true}],
    ['extract-link', 'extract_link', {ok: true, started: true, accepted: true}],
  ] as const;
  it.each(singleCases)('单账号 %s 无任务号时按目标和类型打开任务列表', async (name, type, response) => {
    const h = setup(name === 'deactivation-mail-check' ? {getRowSnapshot: () => ({deactivation_mail_scan_status: 'done'})} : {});
    fetchMock.mockResolvedValue(json(response, 202));
    const input = name === 'extract-link'
      ? context(['7'], [accountRow(7, {email: 'seven@test', current_plan_type: 'free', plus_promo_kind: 'free_trial'})])
      : context(['7']);
    await h.actions.invoke(name, input);
    if (name === 'deactivation-mail-check') await vi.advanceTimersByTimeAsync(1500);
    expect(h.q.openTasks).toHaveBeenCalledWith({filters: {type, target: 'seven@test'}});
    expect(h.q.openAccountTaskLog).not.toHaveBeenCalled();
    expect(h.q.openLiveLog).not.toHaveBeenCalled();
  });
  it('单账号缺少邮箱时使用账号 ID 作为任务中心目标', async () => {
    const h = setup();
    fetchMock.mockResolvedValue(json({ok: true, accepted: true}, 202));
    await h.actions.invoke('deactivation-mail-check', {...context(['7']), expectedEmails: {}, rowHints: []});
    await vi.advanceTimersByTimeAsync(1500);
    expect(h.q.openTasks).toHaveBeenCalledWith({filters: {type: 'deactivation_mail', target: '7'}});
  });
});

describe('账号操作回执', () => {
  const uuid = /^[0-9a-f]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
  const requestKey = (index: number) => new Headers(fetchMock.mock.calls[index]![1]?.headers).get('X-Account-Request-Key');

  it.each([
    ['plan-check', ['7']], ['checkSelectedPlans', ['7', '11']],
    ['account-live-check', ['7']], ['checkSelectedLive', ['7', '11']],
    ['account-refresh-token', ['7']], ['refreshSelectedToken', ['7', '11']],
    ['deactivation-mail-check', ['7']], ['checkSelectedDeactivationMail', ['7', '11']],
  ])('%s 每次提交都发送新的回执查询键', async (name, ids) => {
    fetchMock.mockImplementation(async () => json(receipt({started_count: 0}), 202));
    const h = setup({getRowSnapshot: () => ({deactivation_mail_scan_status: 'done'})});
    const first = h.actions.invoke(name, context(ids));
    await vi.advanceTimersByTimeAsync(1500);
    await first;
    const second = h.actions.invoke(name, context(ids));
    await vi.advanceTimersByTimeAsync(1500);
    await second;
    expect(requestKey(0) || '').toMatch(uuid);
    expect(requestKey(1) || '').toMatch(uuid);
    expect(requestKey(0)).not.toBe(requestKey(1));
  });

  it('传输失联保留查询键，重新进入账号页可查询，重新提交使用新键', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('请求超时'))
      .mockResolvedValueOnce(json({ok: true, found: false, items: []}))
      .mockResolvedValueOnce(json(receipt(), 202))
      .mockResolvedValueOnce(json({ok: true, found: true, items: [{task_id: '9007199254740993', run_id: 72}]}));
    const h = setup();
    await h.actions.invoke('checkSelectedLive', context());
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(messages(h)).toContain('受理结果未确认');
    expect(h.restore).toHaveBeenCalledTimes(1);

    const remounted = setup();
    const receipts = remounted.actions.receipts!;
    const previous = receipts.entries.value[0]!;
    expect(previous.key).toBe(requestKey(0));
    await receipts.lookup(previous.key);
    expect(fetchMock.mock.calls[1]![0]).toBe('/api/accounts/operation-receipt');
    expect(fetchMock.mock.calls[1]![1]?.method).toBe('GET');
    expect(requestKey(1)).toBe(previous.key);
    expect(receipts.entries.value[0]?.message).toContain('暂未查到');

    await remounted.actions.invoke('checkSelectedLive', context(['11', '7']));
    expect(fetchMock.mock.calls[2]![1]?.method).toBe('POST');
    expect(requestKey(2)).not.toBe(previous.key);
    await receipts.lookup(previous.key);
    expect(receipts.entries.value[0]?.items).toEqual([{task_id: '9007199254740993', run_id: 72}]);
    expect(receipts.entries.value[0]?.message).toContain('当前查到 1 条任务回执');
    await receipts.open({task_id: '9007199254740993', run_id: 72});
    expect(remounted.q.openAccountTaskLog).toHaveBeenCalledWith('9007199254740993', 72);
    receipts.dismiss(previous.key);
    expect(setup().actions.receipts!.entries.value).toEqual([]);
  });

  it.each([
    [409, {ok: false, error: '计划查询已在执行'}],
    [503, {ok: false, feature: 'plan_check', error: '套餐查询配置不完整'}],
  ])('HTTP %s 明确拒绝时报告服务端原因，清除待查询的回执', async (status, response) => {
    fetchMock.mockResolvedValueOnce(json(response, status));
    const h = setup();
    await h.actions.invoke('plan-check', context(['7']));
    expect(messages(h)).toContain(response.error);
    expect(h.actions.receipts!.entries.value).toEqual([]);
    expect(setup().actions.receipts!.entries.value).toEqual([]);
  });

  it.each([
    [503, {ok: false, accepted: false, error: '套餐查询任务持久化失败'}],
    [504, {ok: false, error: '网关等待超时'}],
  ])('HTTP %s 无法确认入队时保留查询键并显示服务端原因', async (status, response) => {
    fetchMock.mockResolvedValueOnce(json(response, status));
    const h = setup();
    await h.actions.invoke('plan-check', context(['7']));
    expect(messages(h)).toContain('受理结果未确认');
    expect(messages(h)).toContain(response.error);
    expect(h.actions.receipts!.entries.value[0]?.key).toBe(requestKey(0));
    expect(setup().actions.receipts!.entries.value[0]?.key).toBe(requestKey(0));
  });

  it('等待受理超时立即恢复按钮，允许继续发起请求', async () => {
    const delayed = deferred<Response>();
    fetchMock.mockReturnValueOnce(delayed.promise).mockResolvedValueOnce(json(receipt(), 202));
    const h = setup();
    const first = h.actions.invoke('refreshSelectedToken', context());
    await vi.advanceTimersByTimeAsync(10000);
    await first;
    expect(h.restore).toHaveBeenCalledTimes(1);
    expect(messages(h)).toContain('受理结果未确认');
    expect(h.actions.receipts!.entries.value[0]?.key).toBe(requestKey(0));
    await h.actions.invoke('refreshSelectedToken', context());
    expect(requestKey(1)).not.toBe(requestKey(0));
    delayed.resolve(json(receipt(), 202));
  });

  it('收到回执后无需等日志或列表刷新就可继续操作', async () => {
    const log = deferred<void>(), refresh = deferred<void>();
    fetchMock.mockResolvedValue(json(receipt({started: [{task_id: 71, run_id: 72}]}), 202));
    const h = setup({openTasks: () => log.promise, refresh: () => refresh.promise});
    const finished = vi.fn();
    const first = h.actions.invoke('refreshSelectedToken', context()).then(finished);
    await vi.advanceTimersByTimeAsync(0);
    expect(h.q.openTasks).toHaveBeenCalledOnce();
    expect(h.q.refresh).toHaveBeenCalledOnce();
    expect(h.q.refreshSummary).toHaveBeenCalledOnce();
    expect(finished).toHaveBeenCalledOnce();
    expect(h.actions.isPending('refreshSelectedToken', context())).toBe(false);
    log.resolve(); refresh.resolve();
    await first;
  });
});

describe('plan checks', () => {
  it('single plan POST has no confirmation and polls after an accepted receipt', async () => {
    fetchMock.mockResolvedValue(json({ok:true,started:true,accepted:true,task_id:20,message:'套餐查询已加入后台队列'},202)); const h = setup();
    await h.actions.invoke('plan-check', context(['7'])); expect(fetchMock.mock.calls[0]![0]).toBe('/api/accounts/check-plan'); expect(body()).toEqual({account_id:7});
    expect(h.deps.confirm).not.toHaveBeenCalled(); expect(h.q.pollStatuses).toHaveBeenCalledTimes(1); expect(h.q.refresh).not.toHaveBeenCalled(); expect(h.q.openAccountTaskLog).toHaveBeenCalledWith(20, null); expect(messages(h)).toContain('套餐查询已加入后台队列');
  });
  it('single plan failure polls once; bulk failure preserves its no-poll branch', async () => {
    fetchMock.mockImplementation(async()=>json({ok:false,error:'查询已在执行'},409)); const h = setup(); await h.actions.invoke('plan-check',context(['7']));
    expect(h.q.pollStatuses).toHaveBeenCalledTimes(1); expect(messages(h)).toContain('查询已在执行');
    h.q.pollStatuses.mockClear(); await h.actions.invoke('checkSelectedPlans',context()); expect(h.q.pollStatuses).not.toHaveBeenCalled(); expect(messages(h)).toContain('批量查询失败: 查询已在执行'); expect(fetchMock).toHaveBeenCalledTimes(2);
  });
  it('bulk plan uses all IDs, separate counts and normalized first three reasons', async () => {
    fetchMock.mockResolvedValue(json(receipt({started_count:0,busy_count:2,failed_count:1,skipped:[{reason:' missing\n mailbox '},{error:'already running'},{reason:'x'.repeat(81)}],failed:[{error:'last reason'}]}),202)); const h = setup();
    await h.actions.invoke('checkSelectedPlans',context()); expect(body()).toEqual({account_ids:[7,11]});expect(fetchMock.mock.calls[0]![0]).toBe('/api/accounts/check-plan-bulk');
    expect(messages(h)).toContain('已入队 0 个，查询中跳过 2 个，入队失败 1 个，跳过 3 个；missing mailbox；already running；'+'x'.repeat(80)+'…；另有 1 条原因');expect(h.q.pollStatuses).toHaveBeenCalledTimes(1);
  });
  it('keeps a failed child receipt as a reason rather than rejecting the accepted parent',async()=>{
    fetchMock.mockResolvedValue(json(receipt({started_count:0,started:[],failed_count:1,failed:[{id:7,ok:false,error:'child not queued'}]}),202));
    const h=setup();await h.actions.invoke('checkSelectedPlans',context());
    expect(messages(h)).toContain('入队失败 1 个；child not queued');expect(messages(h)).not.toContain('批量查询失败');expect(h.q.pollStatuses).toHaveBeenCalledTimes(1);expect(h.q.openTasks).not.toHaveBeenCalled();
  });
  it('an accepted plan survives poll failure without duplicate poll or POST', async () => {
    fetchMock.mockResolvedValue(json(receipt(),202));const h=setup({pollStatuses:async()=>{throw new Error('read offline');}});await h.actions.invoke('plan-check',context(['7']));
    expect(fetchMock).toHaveBeenCalledTimes(1);expect(h.q.pollStatuses).toHaveBeenCalledTimes(1);expect(messages(h)).toContain('请求已处理，但页面更新失败: read offline');expect(messages(h)).not.toContain('提交失败');
  });
});

describe('live checks', () => {
  it('single and bulk always use the bulk endpoint with configured driver; only bulk shows workers', async () => {
    fetchMock.mockImplementation(async()=>json(receipt({live_check_driver:'effective_driver'}),202)); const h=setup({configuredLiveCheckDriver:()=>null});
    await h.actions.invoke('account-live-check',context(['7']));expect(body()).toEqual({account_ids:[7],driver:null});expect(fetchMock.mock.calls[0]![0]).toBe('/api/accounts/check-live-bulk');
    expect(h.deps.confirm.mock.calls[0]![0]).toBe('确定查活这个账号吗？\n\n只在线验证现有 accessToken，不会发送邮箱验证码，也不会刷新 AT。');
    await h.actions.invoke('checkSelectedLive',context());expect(body(1)).toEqual({account_ids:[7,11],driver:null});expect(h.deps.confirm.mock.calls[1]![0]).toContain('并发线程数：50');
    expect(messages(h)).toContain('配置驱动：默认，实际驱动：effective_driver');expect(h.q.openTasks.mock.calls.map(call => call[0])).toEqual([{filters:{type:'live_check',target:'seven@test'}},{filters:{type:'live_check',target:''}}]);expect(h.q.openLiveLog).not.toHaveBeenCalled();expect(h.q.refresh).toHaveBeenCalledTimes(2);expect(h.q.refreshSummary).toHaveBeenCalledTimes(2);expect(h.q.readConfig).not.toHaveBeenCalled();
  });
  it('uses the click scope after confirmation changes selection and never filters it by current rows',async()=>{
    const input=context();fetchMock.mockResolvedValue(json(receipt(),202));const h=setup({}, {confirm:()=>{input.accountIds=['99'];return true;}});await h.actions.invoke('checkSelectedLive',input);
    expect(body()).toEqual({account_ids:[7,11],driver:'protocol'});expect(h.q.refresh.mock.calls[0]![0].accountIds).toEqual(['7','11']);expect(Object.isFrozen(h.q.refresh.mock.calls[0]![0])).toBe(true);
  });
  it('does not open a skipped email log or issue a refresh when the POST fails',async()=>{
    fetchMock.mockResolvedValueOnce(json(receipt({started:[],started_count:0,skipped:[{email:'skip@test',reason:'已废'}]}),202)).mockResolvedValueOnce(json({ok:false,error:'拒绝查活'},403));const h=setup();
    await h.actions.invoke('checkSelectedLive',context());expect(h.q.openLiveLog).not.toHaveBeenCalled();h.q.refresh.mockClear();await h.actions.invoke('checkSelectedLive',context());expect(h.q.refresh).not.toHaveBeenCalled();expect(messages(h)).toContain('查活失败: 拒绝查活');
  });
  it('acceptance keeps its receipt even if log or refresh navigation fails, without replay',async()=>{
    fetchMock.mockResolvedValue(json(receipt(),202));const h=setup({openTasks:()=>{throw new Error('task center closed');}});await h.actions.invoke('checkSelectedLive',context());expect(fetchMock).toHaveBeenCalledTimes(1);expect(messages(h)).toContain('查活已入队');expect(messages(h)).toContain('请求已处理，但页面更新失败: task center closed');expect(messages(h)).not.toContain('查活失败');
  });
});

describe('token refresh', () => {
  it('freezes IDs before config read and blocks repeated submit throughout the config promise',async()=>{
    const config=deferred<unknown>(),input=context();fetchMock.mockResolvedValue(json(receipt({started:[{task_id:71,run_id:72,email:'seven@test'}]}),202));const h=setup({readConfig:()=>config.promise});const first=h.actions.invoke('refreshSelectedToken',input);input.accountIds=['99'];
    await h.actions.invoke('refreshSelectedToken',context(['99']));expect(h.q.readConfig).toHaveBeenCalledTimes(1);expect(h.actions.isPending('refreshSelectedToken',context())).toBe(true);expect(h.deps.beginBusy).toHaveBeenCalledWith('refreshSelectedToken',null,'读取配置…');expect(fetchMock).not.toHaveBeenCalled();
    config.resolve([{key:'ACCOUNT_AT_REFRESH_DRIVER',value:'browser_roxy'},{key:'ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED',value:true}]);await first;
    expect(body()).toEqual({account_ids:[7,11]});expect(fetchMock.mock.calls[0]![0]).toBe('/api/accounts/refresh-token-bulk');expect(h.deps.confirm.mock.calls[0]![0]).toContain('Roxy 指纹浏览器重新登录');expect(h.deps.confirm.mock.calls[0]![0]).toContain('HAR');expect(h.deps.confirm.mock.calls[0]![0]).toContain('并发线程数：50');expect(h.q.openTasks).toHaveBeenCalledWith({filters:{type:'token_refresh',target:''}});expect(h.q.openAccountTaskLog).not.toHaveBeenCalled();expect(h.q.openLiveLog).not.toHaveBeenCalled();expect(h.restore).toHaveBeenCalledTimes(1);
  });
  it.each([
    ['v1','False','协议刷新（v1）重新登录',false],['v2',false,'协议刷新（v2）重新登录',false],['v3','true','协议刷新（v3）先复用该账号有效的登录会话',true],['unknown',true,'协议刷新（v1）重新登录',true],
  ])('uses protocol %s and debug %s from config for copy only',async(version,debug,expected,hasDebug)=>{
    fetchMock.mockResolvedValue(json(receipt({started:[]}),202));const h=setup({readConfig:async()=>[{key:'ACCOUNT_AT_REFRESH_DRIVER',value:'protocol'},{key:'OPENAI_PROTOCOL_VERSION',value:version},{key:'ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED',value:debug}]});
    await h.actions.invoke('account-refresh-token',context(['7']));const confirmation=h.deps.confirm.mock.calls[0]![0];expect(confirmation).toContain(expected);expect(confirmation).toContain('密码、2FA 或邮箱验证');expect(confirmation.includes('HAR')).toBe(hasDebug);expect(confirmation).not.toContain('并发线程数');expect(body()).toEqual({account_ids:[7]});
  });
  it('names the rust driver and describes session reuse',async()=>{
    fetchMock.mockResolvedValue(json(receipt({started:[]}),202));const h=setup({readConfig:async()=>[{key:'ACCOUNT_AT_REFRESH_DRIVER',value:'rust'}]});
    await h.actions.invoke('account-refresh-token',context(['7']));const confirmation=h.deps.confirm.mock.calls[0]![0];expect(confirmation).toContain('Rust sentinel-rs');expect(confirmation).toContain('先复用该账号有效的登录会话');expect(confirmation).toContain('密码、2FA 或邮箱验证');expect(body()).toEqual({account_ids:[7]});
  });
  it('opens confirmation from already loaded refresh settings without waiting for GET',async()=>{
    fetchMock.mockResolvedValue(json(receipt(),202));const h=setup({fallbackConfig:()=>[{key:'ACCOUNT_AT_REFRESH_DRIVER',value:'browser_roxy'}]});await h.actions.invoke('refreshSelectedToken',context());
    expect(h.q.readConfig).not.toHaveBeenCalled();expect(h.deps.confirm.mock.calls[0]![0]).toContain('Roxy 指纹浏览器');expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it('uses the saved-driver confirmation if config is unavailable',async()=>{
    fetchMock.mockResolvedValue(json(receipt(),202));const h=setup({readConfig:async()=>{throw new Error('config unavailable');}});await h.actions.invoke('refreshSelectedToken',context());
    expect(h.deps.confirm.mock.calls[0]![0]).toContain('已保存的刷新驱动');expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it('default/empty config names the saved driver; cancelling restores controls without POST',async()=>{
    const h=setup({}, {confirm:()=>false});await h.actions.invoke('refreshSelectedToken',context(['7']));expect(h.deps.confirm.mock.calls[0]![0]).toContain('已保存的刷新驱动');expect(fetchMock).not.toHaveBeenCalled();expect(h.restore).toHaveBeenCalledTimes(1);expect(h.actions.isPending('refreshSelectedToken',context())).toBe(false);
  });
  it('单账号优先打开任务详情，缺少任务号时按目标和类型筛选且不打开旧日志',async()=>{
    fetchMock.mockResolvedValueOnce(json(receipt({started:[{task_id:71,email:'seven@test'}]}),202)).mockResolvedValueOnce(json(receipt(),202));const h=setup();await h.actions.invoke('account-refresh-token',context(['7']));expect(h.q.openAccountTaskLog).toHaveBeenCalledWith(71,null);expect(h.q.openTasks).not.toHaveBeenCalled();expect(h.q.openLiveLog).not.toHaveBeenCalled();await h.actions.invoke('account-refresh-token',context(['7']));expect(h.q.openTasks).toHaveBeenCalledWith({filters:{target:'seven@test',type:'token_refresh'}});expect(h.q.openLiveLog).not.toHaveBeenCalled();
  });
});

describe('deactivation mail polling', () => {
  it('single POST has no body/confirmation/AT refresh and polls after 1500ms until visible targets terminate',async()=>{
    fetchMock.mockResolvedValue(json({ok:true,accepted:true},202));const h=setup({getRowSnapshot:()=>({deactivation_mail_scan_status:'done'})});const pending=h.actions.invoke('deactivation-mail-check',context(['7']));await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock.mock.calls[0]).toEqual(['/api/accounts/7/check-deactivation-mail',{credentials:'same-origin',method:'POST',headers:{'X-Account-Request-Key':expect.any(String)}}]);expect(h.q.refresh).toHaveBeenCalledTimes(1);expect(h.deps.confirm).not.toHaveBeenCalled();expect(messages(h)).toContain('不会刷新 AT');await vi.advanceTimersByTimeAsync(1499);expect(h.q.refresh).toHaveBeenCalledTimes(1);await vi.advanceTimersByTimeAsync(1);await pending;expect(h.q.refresh).toHaveBeenCalledTimes(2);expect(h.q.getRowSnapshot).toHaveBeenCalledWith('7');expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it('bulk sends all IDs, refreshes once and skips polling when started_count is zero',async()=>{
    fetchMock.mockResolvedValue(json(receipt({started_count:0,started:[],skipped_count:2}),202));const h=setup();await h.actions.invoke('checkSelectedDeactivationMail',context());await vi.advanceTimersByTimeAsync(0);expect(body()).toEqual({account_ids:[7,11]});expect(fetchMock.mock.calls[0]![0]).toBe('/api/accounts/check-deactivation-mail-bulk');expect(h.q.refresh).toHaveBeenCalledTimes(1);expect(h.q.getRowSnapshot).not.toHaveBeenCalled();expect(h.q.openTasks).not.toHaveBeenCalled();expect(vi.getTimerCount()).toBe(0);expect(messages(h)).toContain('已入队 0 个，跳过 2 个；不会刷新 AT');
  });
  it('an empty visible subset cannot end polling early; it stops after exactly 30 delayed reads',async()=>{
    fetchMock.mockResolvedValue(json(receipt(),202));const h=setup();const pending=h.actions.invoke('checkSelectedDeactivationMail',context());await vi.advanceTimersByTimeAsync(0);await vi.advanceTimersByTimeAsync(45000);await pending;
    expect(h.q.refresh).toHaveBeenCalledTimes(31);expect(h.q.getRowSnapshot).toHaveBeenCalledTimes(60);expect(vi.getTimerCount()).toBe(0);expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it('a visible running target keeps polling until the next visible terminal subset',async()=>{
    fetchMock.mockResolvedValue(json(receipt(),202));let reads=0;const h=setup({getRowSnapshot:id=>id==='7'?{deactivation_mail_scan_status:++reads===1?'running':'done'}:undefined});const pending=h.actions.invoke('checkSelectedDeactivationMail',context());await vi.advanceTimersByTimeAsync(3000);await pending;expect(h.q.refresh).toHaveBeenCalledTimes(3);expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it('连续获受理的不同账号共用一次列表读取，首次读取看到的终态不提前结束新账号轮询', async () => {
    const firstRefresh = deferred<void>();
    fetchMock.mockImplementation(async () => json({ok:true,accepted:true},202));
    let refreshing = true;
    const h = setup({
      refresh: () => {
        if (!refreshing) return Promise.resolve();
        refreshing = false;
        return firstRefresh.promise;
      },
      getRowSnapshot: () => ({deactivation_mail_scan_status:'done'}),
    });
    await h.actions.invoke('deactivation-mail-check', context(['7']));
    await h.actions.invoke('deactivation-mail-check', context(['11']));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(h.q.refresh).toHaveBeenCalledOnce();
    firstRefresh.resolve();
    await vi.advanceTimersByTimeAsync(1500);
    expect(h.q.refresh).toHaveBeenCalledTimes(2);
    expect(h.q.getRowSnapshot.mock.calls.map(([id]) => id)).toEqual(['7', '11']);
    await vi.advanceTimersByTimeAsync(1500);
    expect(h.q.refresh).toHaveBeenCalledTimes(2);
  });
  it.each(['hide','dispose','owner removed'])('%s stops waits and future reads without cancelling an accepted POST',async mode=>{
    fetchMock.mockResolvedValue(json(receipt(),202));let active=true;const h=setup({isOwnerActive:()=>active});const pending=h.actions.invoke('checkSelectedDeactivationMail',context());await vi.advanceTimersByTimeAsync(0);
    if(mode==='hide')h.actions.setVisible(false);else if(mode==='dispose')h.actions.dispose();else active=false;
    await vi.advanceTimersByTimeAsync(1500);await pending;expect(h.q.refresh).toHaveBeenCalledTimes(1);expect(fetchMock).toHaveBeenCalledTimes(1);expect(vi.getTimerCount()).toBe(0);expect(h.restore).toHaveBeenCalledTimes(1);
    h.actions.setVisible(true);await vi.advanceTimersByTimeAsync(45000);expect(h.q.refresh).toHaveBeenCalledTimes(1);expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it('hiding during POST does not abort it or start UI reads after its acceptance',async()=>{
    const response=deferred<Response>();fetchMock.mockReturnValue(response.promise);const h=setup();const pending=h.actions.invoke('checkSelectedDeactivationMail',context());h.actions.setVisible(false);response.resolve(json(receipt(),202));await pending;await vi.advanceTimersByTimeAsync(0);expect(h.q.refresh).not.toHaveBeenCalled();expect(fetchMock.mock.calls[0]![1]!.signal).toBeUndefined();expect(messages(h)).toContain('已入队 1 个');expect(vi.getTimerCount()).toBe(0);
  });
  it('hiding during a refresh prevents stale completion from restarting polling or reading rows',async()=>{
    fetchMock.mockResolvedValue(json(receipt(),202));const refresh=deferred<void>();const h=setup({refresh:()=>refresh.promise});const pending=h.actions.invoke('checkSelectedDeactivationMail',context());await vi.advanceTimersByTimeAsync(0);h.actions.setVisible(false);h.actions.setVisible(true);refresh.resolve();await pending;expect(h.q.refresh).toHaveBeenCalledTimes(1);expect(h.q.getRowSnapshot).not.toHaveBeenCalled();expect(vi.getTimerCount()).toBe(0);
  });
  it('ignores a late read error after hiding without losing the accepted mail receipt',async()=>{
    fetchMock.mockResolvedValue(json(receipt(),202));const refresh=deferred<void>();const h=setup({refresh:()=>refresh.promise});
    const pending=h.actions.invoke('checkSelectedDeactivationMail',context());await vi.advanceTimersByTimeAsync(0);
    h.actions.setVisible(false);refresh.reject(new Error('late read error'));await pending;
    expect(messages(h)).toContain('已入队 1 个');expect(messages(h)).not.toContain('late read error');expect(fetchMock).toHaveBeenCalledTimes(1);expect(vi.getTimerCount()).toBe(0);
  });
  it('accepted mail request with refresh failure reports page update separately and never resubmits',async()=>{
    fetchMock.mockResolvedValue(json(receipt(),202));const h=setup({refresh:async()=>{throw new Error('list offline');}});await h.actions.invoke('checkSelectedDeactivationMail',context());await vi.advanceTimersByTimeAsync(0);expect(messages(h)).toContain('请求已处理，但页面更新失败: list offline');expect(messages(h)).not.toContain('批量扫描失败');expect(fetchMock).toHaveBeenCalledTimes(1);expect(vi.getTimerCount()).toBe(0);
  });
});

describe('extract links', () => {
  it.each([
    {current_plan_type:'plus',plus_promo_kind:'free_trial'}, {current_plan_type:'free',plus_promo_kind:'discount'},
    {current_plan_type:'free',plus_promo_kind:'unknown',plus_trial_eligible:true}, {current_plan_type:'go',plus_promo_kind:'free_trial'},
  ])('does not submit a row without confirmed free Plus trial: %j',async fields=>{
    const h=setup();await h.actions.invoke('extract-link',context(['7'],[accountRow(7,fields)]));expect(fetchMock).not.toHaveBeenCalled();expect(h.deps.confirm).not.toHaveBeenCalled();expect(messages(h)).toContain('仅支持已确认 Plus 免费试用资格');
  });
  it('single uses the original row for eligibility and confirmation, then shows the fallback task receipt',async()=>{
    const row=accountRow(7,{email:'original@test',current_plan_type:'free',plus_promo_kind:'free_trial'});fetchMock.mockResolvedValue(json({ok:true,started:true,accepted:true,task_id:71,fallback_from:'go',link_type:'plus'},202));const h=setup({}, {confirm:()=>{row.email='changed@test';row.plus_promo_kind='discount';return true;}});await h.actions.invoke('extract-link',context(['7'],[row]));
    expect(h.deps.confirm.mock.calls[0]![0]).toBe('确定为该账号提链吗？\n\noriginal@test\n\n提链类型按配置使用，成功会消耗 1 次 CDK。');expect(body()).toEqual({account_id:7});expect(fetchMock.mock.calls[0]![0]).toBe('/api/accounts/extract-link');expect(h.q.openAccountTaskLog).toHaveBeenCalledWith(71,null);expect(messages(h)).toContain('提炼任务已入队 · 任务 #71；GO 已失败，改用 PLUS');expect(h.q.reloadTasks).toHaveBeenCalledTimes(1);expect(h.q.pollStatuses).toHaveBeenCalledTimes(1);
  });
  it('keeps historical free trial derivation but rejects an explicit discount over 100-percent legacy data',async()=>{
    fetchMock.mockResolvedValue(json({ok:true,started:true,accepted:true},202));const h=setup();
    await h.actions.invoke('extract-link',context(['7'],[accountRow(7,{current_plan_type:'free',plus_promo_kind:'',plus_promo_discount_percentage:100})]));expect(fetchMock).toHaveBeenCalledTimes(1);
    await h.actions.invoke('extract-link',context(['7'],[accountRow(7,{current_plan_type:'free',plus_promo_kind:'discount',plus_promo_discount_percentage:100})]));expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it('bulk sends the entire cross-page scope and reports combined skip/busy/failure and fallbacks',async()=>{
    fetchMock.mockResolvedValue(json(receipt({started_count:2,started:[{id:7,fallback_from:'go'},{id:11}],skipped_count:3,busy_count:4,failed_count:5}),202));const h=setup();await h.actions.invoke('extractSelectedLinks',context());expect(body()).toEqual({account_ids:[7,11]});expect(fetchMock.mock.calls[0]![0]).toBe('/api/accounts/extract-link-bulk');expect(h.deps.confirm.mock.calls[0]![0]).toContain('2 个账号');expect(h.deps.confirm.mock.calls[0]![0]).toContain('折扣优惠和历史待复查');expect(h.q.openTasks).toHaveBeenCalledWith({filters:{type:'extract_link',target:''}});expect(messages(h)).toContain('已入队 2 个，跳过/失败 12 个，其中 1 个已自动跳过失败类型');
  });
  it('does not poll or retry rejected extraction; cancellation sends no request',async()=>{
    fetchMock.mockResolvedValue(json({ok:false,error:'CDK 不可用'},400));const h=setup();await h.actions.invoke('extractSelectedLinks',context());expect(h.q.pollStatuses).not.toHaveBeenCalled();expect(h.q.reloadTasks).not.toHaveBeenCalled();expect(messages(h)).toContain('批量提链失败: CDK 不可用');const cancelled=setup({}, {confirm:()=>false});await cancelled.actions.invoke('extractSelectedLinks',context());expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
