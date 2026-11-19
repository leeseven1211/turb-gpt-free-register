import {computed, reactive, ref} from 'vue';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {createConfigActions, type ConfigActionDependencies, type ConfigActions} from './configActions';
import type {ConfigDraftOwner, ConfigValue, SecretDraft} from './contracts';

function ownerFixture() {
  const saved = reactive<Record<string, ConfigValue>>({PROXY_POOL_SOURCE: '1024proxy', PROXY_1024_PROTOCOL: 'http', PROXY_1024_SESSION_MINUTES: 30, PROXY_POOL_DEFAULT_COUNTRY: 'JP'});
  const dirty = reactive<Record<string, ConfigValue>>({});
  const secrets = reactive<Record<string, SecretDraft>>({});
  const listeners = new Set<(event: {keys: string[]}) => void>();
  const saveSubset = vi.fn(async () => ({status: 'saved'}));
  const owner = {
    fields: ref([]), dirtyKeys: computed(() => Object.keys(dirty)),
    field: (key: string) => ({key, value: saved[key], secret: key.endsWith('_KEY'), group: ['GLOBAL_TASK_WORKERS', 'ACCOUNT_PLAN_CHECK_WORKERS'].includes(key) ? '并发控制' : '', type: 'int'}),
    readField: (key: string, source = 'effective') => source === 'saved' ? saved[key] : Object.hasOwn(dirty, key) ? dirty[key] : saved[key],
    isDirty: (key: string) => Object.hasOwn(dirty, key) || (secrets[key]?.mode ?? 'retain') !== 'retain',
    secretDraft: (key: string) => secrets[key] || {mode: 'retain'},
    setField: (key: string, value: ConfigValue) => {dirty[key] = value;}, saveSubset,
    subscribeSaved: (callback: (event: {keys: string[]}) => void) => {listeners.add(callback); return () => listeners.delete(callback);},
  } as unknown as ConfigDraftOwner;
  return {owner, saved, dirty, secrets, saveSubset, savedEvent: (keys: string[]) => listeners.forEach(callback => callback({keys}))};
}
function deferred<T>() {let resolve!: (value: T) => void; const promise = new Promise<T>(done => {resolve = done;}); return {promise, resolve};}
const controllers: ConfigActions[] = [];
function setup(request: ConfigActionDependencies['request'] = vi.fn<NonNullable<ConfigActionDependencies['request']>>(async () => ({ok: true})), dependencies: ConfigActionDependencies = {}) {
  const fixture = ownerFixture(); const actions = createConfigActions(fixture.owner, {request, ...dependencies}); controllers.push(actions);
  return {...fixture, actions};
}
const flush = async () => {for (let i = 0; i < 8; i++) await Promise.resolve();};
afterEach(() => {controllers.splice(0).forEach(controller => controller.dispose()); vi.useRealTimers();});

describe('config action credential and result contracts', () => {
  it('Roxy discovery uses saved service and selection saves only two explicit IDs', async () => {
    const request = vi.fn<NonNullable<ConfigActionDependencies['request']>>(async () => ({ok: true, items: [{id: '19', projectId: '23', label: '团队'}]}));
    const {actions, dirty, saveSubset} = setup(request); dirty.OTHER = 'keep';
    await actions.loadRoxyWorkspaces(); await actions.saveRoxySelection('19', '23');
    expect(request).toHaveBeenCalledWith('/api/roxy/workspaces', expect.objectContaining({method: 'GET'}));
    expect(saveSubset).toHaveBeenCalledWith({ROXY_WORKSPACE_ID: '19', ROXY_PROJECT_ID: '23'});
    expect(dirty.OTHER).toBe('keep'); expect(actions.roxyWorkspaces.value[0].id).toBe('19');
  });
  it('proxy submits current provider fields and preserves false and zero', async () => {
    const request = vi.fn<NonNullable<ConfigActionDependencies['request']>>(async () => ({ok: true, lease: {provider: '1024proxy', endpoint: 'proxy:80', exit_ip: '1.2.3.4', region: 'JP'}}));
    const {actions, dirty} = setup(request); dirty.PROXY_1024_API_URL = 'new-url'; dirty.PROXY_1024_VALIDATE = false; dirty.PROXY_1024_SESSION_MINUTES = 0;
    await actions.testProxy();
    expect(JSON.parse(request.mock.calls[0]![1]!.body as string)).toEqual({provider: '1024proxy', api_url: 'new-url', region: 'JP', protocol: 'http', session_minutes: 0, validate: false});
    expect(actions.states.proxy.text).toContain('1.2.3.4');
  });
  it('Butler retains empty-key saved fallback and sends an explicit draft value when set', async () => {
    const request = vi.fn<NonNullable<ConfigActionDependencies['request']>>(async () => ({ok: true, missing_permissions: ['email:read']}));
    const {actions, dirty, secrets} = setup(request); dirty.EMAIL_BUTLER_API_BASE = ' https://butler.test ';
    secrets.EMAIL_BUTLER_API_KEY = {mode: 'clear'}; await actions.testButler();
    expect(JSON.parse(request.mock.calls[0]![1]!.body as string)).toEqual({api_base: 'https://butler.test', api_key: ''});
    secrets.EMAIL_BUTLER_API_KEY = {mode: 'set', value: ' draft '}; await actions.testButler();
    expect(JSON.parse(request.mock.calls[1]![1]!.body as string).api_key).toBe('draft');
    expect(actions.states.butler.text).toContain('权限尚未齐全');
  });
  it('credential payloads preserve the full draft after trimming without display truncation', async () => {
    const request = vi.fn<NonNullable<ConfigActionDependencies['request']>>(async () => ({ok: true, remainingUses: 0, balance: {available_points: 0}}));
    const {actions, secrets} = setup(request);
    const credential = 'key-' + 'x'.repeat(1500);
    for (const [key, action] of [
      ['EMAIL_BUTLER_API_KEY', 'testButler'],
      ['EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY', 'queryHuanguangXxsyun'],
      ['EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY', 'queryXxsyunBalance'],
    ] as const) {
      secrets[key] = {mode: 'set', value: ` ${credential} `};
      await actions[action]();
      expect(JSON.parse(request.mock.calls.at(-1)![1]!.body as string).api_key).toBe(credential);
    }
    expect(JSON.stringify(actions.states)).not.toContain(credential);
  });
  it('both CDK queries refuse dirty saved-only credentials and preserve zero and unknown', async () => {
    const request = vi.fn<NonNullable<ConfigActionDependencies['request']>>(async () => ({ok: true, quota: {required: true, remaining: 0, reserved: null, active: false}}));
    const {actions, dirty} = setup(request); dirty.EXTRACT_LINK_HUANGUANG_CDK = 'draft';
    await actions.queryHuanguangQuota('extraction'); expect(request).not.toHaveBeenCalled();
    delete dirty.EXTRACT_LINK_HUANGUANG_CDK; await actions.queryHuanguangQuota('extraction'); await actions.queryHuanguangQuota('payment');
    expect(request.mock.calls.map(call => call[0])).toEqual(['/api/extract-link/huanguang/cdk-quota/extraction', '/api/extract-link/huanguang/cdk-quota/payment']);
    expect(actions.states.huanguangExtraction.text).toBe('剩余 0 次 · 占用 未知 · 已停用');
  });
  it.each([['huanguangXxsyun', 'EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY', 'queryHuanguangXxsyun'], ['xxsyunBalance', 'EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY', 'queryXxsyunBalance']] as const)('%s preserves retain/set/clear POST three-state', async (_name, key, method) => {
    const request = vi.fn<NonNullable<ConfigActionDependencies['request']>>(async () => ({ok: true, remainingUses: 0, totalUses: null, reservedUses: 0, balance: {available_points: 0, pending_points: null, used_points: 2, cost_points: 1}}));
    const {actions, secrets} = setup(request);
    await actions[method](); secrets[key] = {mode: 'set', value: ' draft '}; await actions[method](); secrets[key] = {mode: 'clear'}; await actions[method]();
    expect(request.mock.calls.map(call => JSON.parse(call[1]!.body as string))).toEqual([{}, {api_key: 'draft'}, {api_key: ''}]);
  });
  it('base drafts block both XXSYUN queries and unknown error text is never displayed', async () => {
    const request = vi.fn<NonNullable<ConfigActionDependencies['request']>>(async () => {throw new Error('password=secret');});
    const {actions, dirty} = setup(request);
    dirty.EXTRACT_LINK_HUANGUANG_API_BASE = 'draft'; dirty.EXTRACT_LINK_PAYMENT_XXSYUN_API_BASE = 'draft';
    await actions.queryHuanguangXxsyun(); await actions.queryXxsyunBalance(); expect(request).not.toHaveBeenCalled();
    delete dirty.EXTRACT_LINK_PAYMENT_XXSYUN_API_BASE; await actions.queryXxsyunBalance();
    expect(actions.states.xxsyunBalance.error).not.toContain('secret'); expect(actions.states.xxsyunBalance.error).toContain('查询积分失败');
  });
  it('dynamic types exclude disabled items and preserve existing owner value', async () => {
    const {actions, dirty} = setup(async () => ({items: [{type: 'A', label: '一'}, {type: 'a'}, {type: 'b', enabled: false}]}));
    dirty.EXTRACT_LINK_TYPE = 'unknown'; await actions.loadExtractTypes();
    expect(actions.extractTypeOptions.value).toEqual([{value: 'a', label: '一'}]); expect(dirty.EXTRACT_LINK_TYPE).toBe('unknown');
  });
  it('concurrency preview only fills untouched policy keys and keeps task types intact', async () => {
    const request = vi.fn(async (path: string) => path.includes('preview') ? {proposed_values: {GLOBAL_TASK_WORKERS: 12, ACCOUNT_PLAN_CHECK_WORKERS: 3, EVIL: 'secret'}} : {types: [{config_key: 'ACCOUNT_PLAN_CHECK_WORKERS', key: 'plan_check', task_types: ['plan_check', 'live_check']}]});
    const navigate = vi.fn(); const {actions, dirty} = setup(request, {onNavigateTasks: navigate}); dirty.GLOBAL_TASK_WORKERS = 9;
    await actions.loadConcurrencyPreview(); expect(actions.applyConcurrencyPreview()).toEqual(['ACCOUNT_PLAN_CHECK_WORKERS']);
    expect(dirty).toEqual({GLOBAL_TASK_WORKERS: 9, ACCOUNT_PLAN_CHECK_WORKERS: 3});
    await actions.refreshConcurrency({details: true}); actions.locateConcurrencyTasks('ACCOUNT_PLAN_CHECK_WORKERS');
    expect(navigate).toHaveBeenCalledWith({types: ['plan_check', 'live_check']});
    expect(request.mock.calls.some(call => call[0].endsWith('?details=1'))).toBe(true);
  });
  it('a saved concurrency policy replaces obsolete migration suggestions before they can be reapplied', async () => {
    let migrated = false;
    const {actions, saved, dirty, savedEvent} = setup(async path => path.includes('preview')
      ? {ok: true, migration_required: !migrated, proposed_values: {GLOBAL_TASK_WORKERS: migrated ? 9 : 3}}
      : {ok: true, migration_required: !migrated, global: {limit: migrated ? 9 : 3}});
    await actions.loadConcurrencyPreview();
    migrated = true; saved.GLOBAL_TASK_WORKERS = 9; savedEvent(['GLOBAL_TASK_WORKERS']);
    expect(actions.applyConcurrencyPreview()).toEqual([]);
    expect(dirty.GLOBAL_TASK_WORKERS).toBeUndefined();
    await actions.refreshConcurrency();
    expect(actions.states.concurrencyPreview.snapshot?.migration_required).toBe(false);
    actions.applyConcurrencyPreview();
    expect(dirty.GLOBAL_TASK_WORKERS).toBe(9);
  });
  it('a preview started before a concurrency save cannot restore obsolete migration suggestions', async () => {
    const old = deferred<unknown>();
    const request = vi.fn<NonNullable<ConfigActionDependencies['request']>>()
      .mockImplementationOnce(() => old.promise)
      .mockResolvedValue({ok: true, migration_required: false, proposed_values: {GLOBAL_TASK_WORKERS: 9}});
    const {actions, dirty, savedEvent} = setup(request);
    const reading = actions.loadConcurrencyPreview(); await flush();
    savedEvent(['GLOBAL_TASK_WORKERS']);
    old.resolve({ok: true, migration_required: true, proposed_values: {GLOBAL_TASK_WORKERS: 3}});
    await reading;
    expect(actions.applyConcurrencyPreview()).toEqual([]);
    expect(dirty.GLOBAL_TASK_WORKERS).toBeUndefined();
    await actions.loadConcurrencyPreview();
    expect(actions.states.concurrencyPreview.snapshot?.migration_required).toBe(false);
  });
});

describe('async request ownership', () => {
  it('single-flights manual clicks and drops late credential results after editing', async () => {
    const pending = deferred<unknown>(); const request = vi.fn<NonNullable<ConfigActionDependencies['request']>>(() => pending.promise); const {actions, secrets} = setup(request);
    const first = actions.queryXxsyunBalance(); const duplicate = actions.queryXxsyunBalance();
    await flush(); expect(request).toHaveBeenCalledTimes(1);
    secrets.EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY = {mode: 'set', value: 'new'};
    pending.resolve({ok: true, balance: {available_points: 100}}); await Promise.all([first, duplicate]);
    expect(actions.states.xxsyunBalance.text).toBe(''); expect(actions.states.xxsyunBalance.snapshot).toBeNull();
  });
  it('saved-key invalidation waits for prior GET before querying fresh credentials', async () => {
    const old = deferred<unknown>(); const request = vi.fn().mockImplementationOnce(() => old.promise).mockResolvedValue({ok: true, quota: {required: true, remaining: 2, reserved: 0, active: true}});
    const {actions, savedEvent} = setup(request); const first = actions.queryHuanguangQuota('payment'); await flush();
    savedEvent(['EXTRACT_LINK_HUANGUANG_PAYMENT_CDK']); const fresh = actions.queryHuanguangQuota('payment'); await flush();
    expect(request).toHaveBeenCalledTimes(1); old.resolve({ok: true, quota: {required: true, remaining: 99, reserved: 0, active: true}});
    await Promise.all([first, fresh]); expect(request).toHaveBeenCalledTimes(2); expect(actions.states.huanguangPayment.text).toContain('剩余 2');
  });
  it('Sentinel polls only when visible and running; hidden late read never changes snapshot', async () => {
    vi.useFakeTimers(); const pending = deferred<unknown>(); const request = vi.fn().mockResolvedValueOnce({ok: true, running: true}).mockImplementationOnce(() => pending.promise);
    const {actions} = setup(request); actions.setVisible('sentinel', true); await flush();
    await vi.advanceTimersByTimeAsync(1500); expect(request).toHaveBeenCalledTimes(2);
    actions.setVisible('sentinel', false); pending.resolve({ok: true, running: false}); await flush();
    expect(actions.states.sentinel.snapshot?.running).toBe(true);
    await vi.advanceTimersByTimeAsync(6000); expect(request).toHaveBeenCalledTimes(2);
  });
  it('accepted Sentinel and Sub2API receipts remain tracked after hide or dispose and IDs stay exact', async () => {
    for (const method of ['checkSentinel', 'checkSub2Api'] as const) {
      const pending = deferred<unknown>(); const onTaskReceipt = vi.fn(); const request = vi.fn<NonNullable<ConfigActionDependencies['request']>>(() => pending.promise);
      const {actions} = setup(request, {onTaskReceipt}); const operation = actions[method](); await flush(); actions.dispose();
      pending.resolve({ok: true, accepted: true, task_id: '9007199254740993', run_id: '9007199254740995', running: true}); await operation;
      expect(onTaskReceipt).toHaveBeenCalledWith({accepted: true, task_id: '9007199254740993', run_id: '9007199254740995'}, expect.any(String));
      expect(request.mock.calls[0]![1]!.signal).toBeUndefined();
    }
  });
  it('visible concurrency polls every three seconds and leaving document stops requests', async () => {
    vi.useFakeTimers(); const request = vi.fn<NonNullable<ConfigActionDependencies['request']>>(async () => ({ok: true, global: {occupied: 0, limit: 4}})); const {actions} = setup(request);
    actions.setVisible('concurrency', true); await flush(); const initial = request.mock.calls.length;
    await vi.advanceTimersByTimeAsync(3000); expect(request.mock.calls.length).toBeGreaterThan(initial);
    actions.setForeground(false); const hidden = request.mock.calls.length; await vi.advanceTimersByTimeAsync(9000); expect(request.mock.calls.length).toBe(hidden);
  });
});

describe('action boundary regressions', () => {
  it('hiding a Sentinel POST never enables a second submission while it is in flight', async () => {
    const pending = deferred<unknown>(); const request = vi.fn<NonNullable<ConfigActionDependencies['request']>>(() => pending.promise);
    const {actions} = setup(request); const first = actions.checkSentinel(); await flush();
    actions.setForeground(false); const second = actions.checkSentinel();
    pending.resolve({ok: true, accepted: true, task_id: '17', run_id: '18', running: true});
    await Promise.all([first, second]); expect(request).toHaveBeenCalledTimes(1);
  });
  it('queued reads across repeated visibility changes cannot hide an accepted POST from single-flight', async () => {
    const pending = deferred<unknown>(); const onTaskReceipt = vi.fn();
    const request = vi.fn<NonNullable<ConfigActionDependencies['request']>>()
      .mockResolvedValueOnce({ok: true, running: false})
      .mockImplementationOnce(() => pending.promise)
      .mockResolvedValue({ok: true, running: false});
    const {actions} = setup(request, {onTaskReceipt});
    actions.setVisible('sentinel', true); await flush();
    const first = actions.checkSentinel(); await flush();
    actions.setForeground(false); actions.setForeground(true);
    actions.setForeground(false);
    const duplicate = actions.checkSentinel();
    actions.setForeground(true);
    pending.resolve({ok: true, accepted: true, task_id: '17', run_id: '18', running: true});
    await Promise.all([first, duplicate]); await flush();
    expect(request.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
    expect(onTaskReceipt).toHaveBeenCalledTimes(1);
  });
  it('a synchronous transport exception does not leave a completed inflight entry preventing retry', async () => {
    const request = vi.fn<NonNullable<ConfigActionDependencies['request']>>().mockImplementationOnce(() => {throw new Error('secret');}).mockResolvedValue({items: [{type: 'a'}]});
    const {actions} = setup(request); await actions.loadExtractTypes(); await actions.loadExtractTypes();
    expect(request).toHaveBeenCalledTimes(2); expect(actions.extractTypeOptions.value).toEqual([{value: 'a', label: 'a'}]);
  });
  it('invalid array balance is rejected instead of appearing as unknown valid quota', async () => {
    const {actions} = setup(async () => ({ok: true, balance: []})); await actions.queryXxsyunBalance();
    expect(actions.states.xxsyunBalance.error).toContain('响应无效'); expect(actions.states.xxsyunBalance.snapshot).toBeNull();
  });
  it('leaving the config page invalidates manual late results and document visibility cannot restart its polls', async () => {
    vi.useFakeTimers(); const pending = deferred<unknown>(); const request = vi.fn<NonNullable<ConfigActionDependencies['request']>>().mockResolvedValueOnce({running: true}).mockImplementationOnce(() => pending.promise);
    const {actions} = setup(request); actions.setVisible('sentinel', true); await flush(); const query = actions.queryXxsyunBalance(); await flush();
    actions.setPageActive(false); actions.setForeground(false); actions.setForeground(true);
    pending.resolve({ok: true, balance: {available_points: 99}}); await query;
    expect(actions.states.xxsyunBalance.snapshot).toBeNull(); await vi.advanceTimersByTimeAsync(5000); expect(request).toHaveBeenCalledTimes(2);
  });
  it('the real request adapter preserves bigint JSON receipts before JSON number parsing', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{"ok":true,"accepted":true,"task_id":9007199254740993,"run_id":9007199254740995}', {headers: {'Content-Type': 'application/json'}}));
    const fixture = ownerFixture(); const onTaskReceipt = vi.fn(); const actions = createConfigActions(fixture.owner, {onTaskReceipt}); controllers.push(actions);
    await actions.checkSub2Api(); expect(onTaskReceipt).toHaveBeenCalledWith({accepted: true, task_id: '9007199254740993', run_id: '9007199254740995'}, 'Sub2API 异常扫描');
  });
  it('Sub2API completion reports fixed repair reason labels and keeps zero counts', async () => {
    const {actions} = setup(async () => ({ok: true, result: {remote_errors: 0, sync_queued: 0, reasons: {account_busy: 2, private_error_with_secret: 1}}}));
    await actions.checkSub2Api(); expect(actions.states.sub2api.text).toContain('账号忙碌 2'); expect(actions.states.sub2api.text).not.toContain('private_error');
  });
  it('Sub2API check posts only an empty object even while its settings have unsaved changes', async () => {
    const request = vi.fn<NonNullable<ConfigActionDependencies['request']>>(async () => ({ok: true, accepted: true, task_id: 1}));
    const {actions, dirty} = setup(request); dirty.SUB2API_API_KEY = 'private-draft'; dirty.SUB2API_API_BASE = 'new-base'; await actions.checkSub2Api();
    expect(JSON.parse(request.mock.calls[0]![1]!.body as string)).toEqual({}); expect(actions.states.sub2api.text).toContain('已入队');
  });
});


describe('Sub2API monitor group compatibility', () => {
  it('queries saved connection only, validates positive IDs and deduplicates groups', async () => {
    const request = vi.fn<NonNullable<ConfigActionDependencies['request']>>(async () => ({ok:true, groups:[{id:16,name:'Plus'},{id:16,name:'duplicate'},{id:17,name:'Free'}]}));
    const {actions,dirty} = setup(request);dirty.SUB2API_API_BASE='draft-base';dirty.SUB2API_API_KEY='draft-key';
    await actions.querySub2ApiGroups();
    expect(request).toHaveBeenCalledWith('/api/sub2api/groups',expect.objectContaining({method:'GET'}));
    expect(request.mock.calls[0]?.[1]).not.toHaveProperty('body');
    expect(actions.sub2apiGroups.value).toEqual([{value:'16',label:'duplicate（ID 16）'},{value:'17',label:'Free（ID 17）'}]);
    expect(actions.states.sub2apiGroups.text).toBe('已查询 2 个分组');
    expect(JSON.stringify(actions.states)).not.toContain('draft-key');
  });
  it('keeps previous group choices after invalid responses and drops stale saved-connection reads', async () => {
    const pending = deferred<unknown>();let round=0;
    const {actions,savedEvent} = setup(async()=>++round===1?{ok:true,groups:[{id:16,name:'Plus'}]}:round===2?{ok:true,groups:[{id:0,name:'bad'}]}:pending.promise);
    await actions.querySub2ApiGroups();await actions.querySub2ApiGroups();
    expect(actions.sub2apiGroups.value.map(item=>item.value)).toEqual(['16']);
    expect(actions.states.sub2apiGroups.error).toContain('分组响应格式无效');
    const reading=actions.querySub2ApiGroups();await flush();savedEvent(['SUB2API_API_KEY']);
    pending.resolve({ok:true,groups:[{id:99,name:'stale'}]});await reading;
    expect(actions.sub2apiGroups.value).toEqual([]);
  });
});
