import {computed, reactive, watch, type ComputedRef} from 'vue';
import {request as apiRequest} from '../../api/client';
import {optionalTaskId, parseTaskJson, taskId, type TaskId} from '../../api/taskIds';
import type {ConfigDraftOwner, ConfigOption, ConfigSaveOutcome} from './contracts';

export type ConfigActionName = 'extractTypes' | 'roxy' | 'proxy' | 'butler' | 'huanguangExtraction'
  | 'huanguangPayment' | 'huanguangXxsyun' | 'xxsyunBalance' | 'sentinel' | 'sub2api'
  | 'c2a' | 'concurrency' | 'concurrencyPreview' | 'sub2apiGroups';
export type PollingAction = 'sentinel' | 'concurrency';
export interface ConfigActionReceipt {accepted: true; task_id: TaskId; run_id?: TaskId | null}
export interface ConfigActionState {
  loading: boolean;
  posting: boolean;
  text: string;
  error: string;
  snapshot: Record<string, unknown> | null;
  receipt: ConfigActionReceipt | null;
}
export interface RoxyWorkspace {id: string; projectId: string; label: string}
export interface ConfigActionDependencies {
  request?: (path: string, options?: RequestInit) => Promise<unknown>;
  onTaskReceipt?: (receipt: ConfigActionReceipt, label: string) => void;
  onNavigateTasks?: (target: {registration?: boolean; types?: string[]}) => void;
}
export interface ConfigActions {
  states: Record<ConfigActionName, ConfigActionState>;
  extractTypeOptions: ComputedRef<ConfigOption[]>;
  roxyWorkspaces: ComputedRef<RoxyWorkspace[]>;
  sub2apiGroups: ComputedRef<ConfigOption[]>;
  querySub2ApiGroups(): Promise<void>;
  loadExtractTypes(): Promise<void>;
  loadRoxyWorkspaces(): Promise<void>;
  saveRoxySelection(workspaceId: string, projectId: string): Promise<ConfigSaveOutcome | undefined>;
  testProxy(): Promise<void>;
  testButler(): Promise<void>;
  queryHuanguangQuota(kind: 'extraction' | 'payment'): Promise<void>;
  queryHuanguangXxsyun(): Promise<void>;
  queryXxsyunBalance(): Promise<void>;
  refreshSentinel(): Promise<void>;
  checkSentinel(): Promise<void>;
  refreshSub2Api(): Promise<void>;
  checkSub2Api(): Promise<void>;
  refreshC2a(): Promise<void>;
  checkC2a(): Promise<void>;
  refreshConcurrency(options?: {details?: boolean}): Promise<void>;
  loadConcurrencyPreview(): Promise<void>;
  applyConcurrencyPreview(): string[];
  locateConcurrencyTasks(key: string): void;
  setVisible(action: PollingAction, visible: boolean): void;
  setForeground(visible: boolean): void;
  setPageActive(visible: boolean): void;
  dispose(): void;
}

const NAMES: ConfigActionName[] = ['extractTypes', 'roxy', 'proxy', 'butler', 'huanguangExtraction', 'huanguangPayment', 'huanguangXxsyun', 'xxsyunBalance', 'sentinel', 'sub2api', 'c2a', 'concurrency', 'concurrencyPreview', 'sub2apiGroups'];
const TRACKED_SUBMISSIONS = new Set<ConfigActionName>(['sentinel', 'sub2api', 'c2a', 'proxy']);
const CREDENTIAL_KEYS: Partial<Record<ConfigActionName, string[]>> = {
  roxy: ['ROXY_API_BASE', 'ROXY_API_TOKEN'],
  proxy: ['PROXY_POOL_SOURCE', 'PROXY_POOL_DEFAULT_COUNTRY', 'PROXY_1024_API_URL', 'PROXY_1024_PROTOCOL', 'PROXY_1024_SESSION_MINUTES', 'PROXY_1024_VALIDATE', 'PROXY_711_API_URL', 'PROXY_711_PROTOCOL', 'PROXY_711_SESSION_MINUTES'],
  butler: ['EMAIL_BUTLER_API_BASE', 'EMAIL_BUTLER_API_KEY'],
  huanguangExtraction: ['EXTRACT_LINK_HUANGUANG_CDK', 'EXTRACT_LINK_HUANGUANG_API_BASE'],
  huanguangPayment: ['EXTRACT_LINK_HUANGUANG_PAYMENT_CDK', 'EXTRACT_LINK_HUANGUANG_API_BASE'],
  huanguangXxsyun: ['EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY', 'EXTRACT_LINK_HUANGUANG_API_BASE'],
  xxsyunBalance: ['EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY', 'EXTRACT_LINK_PAYMENT_XXSYUN_API_BASE'],
};
function record(value: unknown): Record<string, unknown> {return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};}
function text(value: unknown, fallback = ''): string {return typeof value === 'string' || typeof value === 'number' ? String(value).slice(0, 1000) : fallback;}
function credential(value: unknown): string {return typeof value === 'string' ? value.trim() : '';}
function list(value: unknown): unknown[] {return Array.isArray(value) ? value : [];}
function nonnegative(value: unknown): boolean {return typeof value === 'number' && Number.isFinite(value) && value >= 0;}
function count(value: unknown): boolean {return Number.isSafeInteger(value) && Number(value) >= 0;}
function invalid(): never {throw {code: 'invalid_response'};}
function post(body: Record<string, unknown>): RequestInit {return {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)};}
function quotaError(error: unknown, points = false, label = 'CDK'): string {
  const code = text(record(error).code || record(error).error_code).toLowerCase();
  const messages: Record<string, string> = {
    key_missing: '未配置 XXSYUN API Key，请填写后重试', api_key_missing: '未配置 XXSYUN API Key，请填写后重试',
    key_invalid: 'XXSYUN API Key 无效或已失效，请更新后重试', api_key_invalid: 'XXSYUN API Key 无效或已失效，请更新后重试',
    unauthorized: 'XXSYUN API Key 无效或已失效，请更新后重试', unauthenticated: 'XXSYUN API Key 无效或已失效，请更新后重试',
    forbidden: '当前 XXSYUN API Key 无权查询积分', cdk_invalid: `${label} 无效或已失效，请更新并保存后重试`,
    cdk_missing: `未配置${label}，请填写并保存后重试`, config_invalid: '查询配置无效，请检查服务地址并保存后重试',
    network_error: '查询遇到网络连接异常，请稍后重试', transport_error: '查询遇到网络连接异常，请稍后重试',
    upstream_http_error: '上游服务暂时无法完成查询，请稍后重试', rate_limited: '查询过于频繁，请稍后重试',
    invalid_response: points ? 'XXSYUN 积分响应无效，请稍后重试' : '上游查询响应无效，请稍后重试', request_timeout: '查询超时，请稍后重试',
    employer_pending: 'XXSYUN 平台账号尚未就绪，请在平台检查账号状态',
    password_change_required: 'XXSYUN 平台要求先修改密码，请在平台处理后重试',
    insufficient_quota: 'XXSYUN 积分不足，请在平台检查积分余额',
  };
  return messages[code] || (points ? '查询积分失败，请检查 XXSYUN 配置或稍后重试' : '查询失败，请稍后重试');
}

/** Owns only action results and I/O lifetimes. Editable values belong to ConfigDraftOwner. */
export function createConfigActions(owner: ConfigDraftOwner, dependencies: ConfigActionDependencies = {}): ConfigActions {
  const request = dependencies.request || ((path: string, options?: RequestInit) => apiRequest(path, options, parseTaskJson));
  const states = reactive(Object.fromEntries(NAMES.map(name => [name, {loading: false, posting: false, text: '', error: '', snapshot: null, receipt: null}])) as Record<ConfigActionName, ConfigActionState>);
  const generations = Object.fromEntries(NAMES.map(name => [name, 0])) as Record<ConfigActionName, number>;
  const inflight = new Map<ConfigActionName, {generation: number; promise: Promise<void>; controller?: AbortController; posting: boolean}>();
  const submissions = new Map<ConfigActionName, Promise<void>>();
  const visible = {sentinel: false, concurrency: false};
  const timers = new Map<PollingAction, ReturnType<typeof setTimeout>>();
  let foreground = true, pageActive = true, disposed = false;
  const stops: (() => void)[] = [];
  const value = (key: string, fallback: unknown = '') => owner.readField(key) ?? fallback;
  function secretValue(key: string): string {
    const draft = owner.secretDraft(key);
    return draft.mode === 'set' ? credential(draft.value) : draft.mode === 'clear' ? '' : credential(value(key));
  }
  function keyPayload(key: string): Record<string, unknown> {
    const draft = owner.secretDraft(key);
    if (draft.mode === 'clear') return {api_key: ''};
    if (draft.mode === 'set') return {api_key: credential(draft.value)};
    return owner.isDirty(key) ? {api_key: credential(value(key))} : {};
  }
  function clearTimer(name: PollingAction) {const timer = timers.get(name); if (timer !== undefined) clearTimeout(timer); timers.delete(name);}
  function invalidate(name: ConfigActionName, keepSnapshot = false) {
    generations[name]++;
    const running = inflight.get(name);
    if (!running?.posting) running?.controller?.abort();
    states[name].loading = false; states[name].posting = false; states[name].error = ''; states[name].text = '';
    if (!keepSnapshot) {states[name].snapshot = null; states[name].receipt = null;}
  }
  for (const [name, keys] of Object.entries(CREDENTIAL_KEYS) as [ConfigActionName, string[]][]) {
    stops.push(watch(() => keys.map(key => [owner.readField(key), owner.isDirty(key), owner.secretDraft(key)]), () => invalidate(name), {deep: true, flush: 'sync'}));
  }
  stops.push(owner.subscribeSaved(event => {
    for (const [name, keys] of Object.entries(CREDENTIAL_KEYS) as [ConfigActionName, string[]][]) {
      if (keys.some(key => event.keys.includes(key))) invalidate(name);
    }
    if(event.keys.some(key=>['SUB2API_API_BASE','SUB2API_API_KEY','SUB2API_API_TIMEOUT'].includes(key)))invalidate('sub2apiGroups');
    if (event.keys.some(key => key.startsWith('C2A_API_') || key.startsWith('C2A_MONITOR_'))) invalidate('c2a');
    if (event.keys.some(key => owner.field(key)?.group === '并发控制')) invalidate('concurrencyPreview');
  }));
  function publishReceipt(raw: Record<string, unknown>, label: string): ConfigActionReceipt | null {
    if (raw.accepted !== true) return null;
    const receipt: ConfigActionReceipt = {accepted: true, task_id: taskId(raw.task_id)};
    if (raw.run_id != null) receipt.run_id = optionalTaskId(raw.run_id);
    // The server has accepted this work even if its originating view has left.
    // Callback failure must never convert acceptance into a retryable POST.
    try {dependencies.onTaskReceipt?.(receipt, label);} catch { /* The local receipt still shows acceptance. */ }
    return receipt;
  }
  function schedule(name: PollingAction) {
    clearTimer(name);
    if (disposed || !foreground || !pageActive || !visible[name] || states[name].loading || states[name].posting) return;
    if (name === 'sentinel' && (!states.sentinel.snapshot?.running || states.sentinel.error)) return;
    timers.set(name, setTimeout(() => {timers.delete(name); void (name === 'sentinel' ? refreshSentinel() : refreshConcurrency());}, name === 'sentinel' ? 1500 : 3000));
  }
  interface RunOptions {
    posting?: boolean; label?: string; error?: (error: unknown) => string;
    apply: (response: Record<string, unknown>, receipt: ConfigActionReceipt | null) => void;
  }
  function run(name: ConfigActionName, path: string, options: RequestInit, behavior: RunOptions): Promise<void> {
    if (disposed) return Promise.resolve();
    // A queued refresh may replace the read generation while an accepted
    // submission is still pending. Track the POST independently of that read.
    const tracksSubmission = behavior.posting && TRACKED_SUBMISSIONS.has(name);
    const submitted = tracksSubmission ? submissions.get(name) : undefined;
    if (submitted) return submitted;
    const previous = inflight.get(name);
    if (previous?.generation === generations[name] || (previous?.posting && tracksSubmission)) return previous.promise;
    const generation = ++generations[name];
    const controller = behavior.posting ? undefined : new AbortController();
    states[name].loading = !behavior.posting; states[name].posting = !!behavior.posting; states[name].error = '';
    if (name === 'sentinel' || name === 'concurrency') clearTimer(name);
    const current = () => !disposed && generations[name] === generation;
    const promise = (async () => {
      try {
        // Keep one request per action even after credential invalidation. This
        // also avoids inheriting an older saved-credential GET via any cache.
        if (previous) await previous.promise;
        if (!current()) return;
        const response = record(await Promise.resolve().then(() => request(path, {...options, ...(controller ? {signal: controller.signal} : {})})));
        if (response.ok === false) throw response;
        const receipt = behavior.label ? publishReceipt(response, behavior.label) : null;
        if (!current()) return;
        states[name].receipt = receipt;
        behavior.apply(response, receipt);
      } catch (error) {
        if (!current()) return;
        states[name].error = behavior.error?.(error) || '请求未完成，请稍后重试。';
        states[name].text = states[name].error;
      } finally {
        if (tracksSubmission) submissions.delete(name);
        if (inflight.get(name)?.generation === generation) inflight.delete(name);
        if (current()) {
          states[name].loading = false; states[name].posting = false;
          if (name === 'sentinel' || name === 'concurrency') schedule(name);
        }
      }
    })();
    inflight.set(name, {generation, promise, controller, posting: !!behavior.posting});
    if (tracksSubmission) submissions.set(name, promise);
    return promise;
  }
  function refuse(name: ConfigActionName, message: string): Promise<void> {
    states[name].text = message; states[name].error = ''; return Promise.resolve();
  }
  function loadExtractTypes() {
    return run('extractTypes', '/api/extract-link/types', {method: 'GET'}, {apply: response => {
      const seen = new Set<string>(); const options: ConfigOption[] = [];
      for (const raw of list(response.items)) {
        const item = record(raw), type = text(item.type).trim().toLowerCase();
        if (!type || seen.has(type) || item.visible === false || item.enabled === false) continue;
        seen.add(type); options.push({value: type, label: text(item.label, type) || type});
      }
      if (!options.length) invalid();
      states.extractTypes.snapshot = {options};
    }, error: () => '提链类型读取失败，保留当前选择。'});
  }
  function loadRoxyWorkspaces() {
    return run('roxy', '/api/roxy/workspaces', {method: 'GET'}, {apply: response => {
      const items = list(response.items).map(raw => {
        const item = record(raw); return {id: text(item.id), projectId: text(item.projectId), label: text(item.label) || `${text(item.name)} (${text(item.id)})`};
      }).filter(item => item.id);
      if (!items.length) invalid();
      states.roxy.snapshot = {items}; states.roxy.text = `已获取 ${items.length} 个团队/项目`;
    }, error: () => '获取团队/项目失败，请检查已保存的 Roxy 连接配置后重试。'});
  }
  async function saveRoxySelection(workspaceId: string, projectId: string) {
    if (disposed || !workspaceId || states.roxy.posting || states.roxy.loading) return;
    states.roxy.posting = true;
    try {
      const outcome = await owner.saveSubset({ROXY_WORKSPACE_ID: workspaceId, ROXY_PROJECT_ID: projectId});
      if (disposed) return outcome;
      states.roxy.text = outcome.status === 'saved' ? 'Roxy 团队/项目已保存。' : outcome.status === 'busy' ? '配置正在保存，请稍后重试。' : '保存未完成，请检查配置反馈。';
      return outcome;
    } catch {if (!disposed) states.roxy.error = '保存未完成，请稍后重试。';}
    finally {if (!disposed) states.roxy.posting = false;}
  }
  function testProxy() {
    const provider = text(value('PROXY_POOL_SOURCE'));
    const prefix = provider === '1024proxy' ? 'PROXY_1024_' : provider === '711proxy' ? 'PROXY_711_' : '';
    if (!prefix) return refuse('proxy', '请选择支持提取测试的代理供应商。');
    return run('proxy', '/api/proxy-provider/test', post({provider, api_url: value(`${prefix}API_URL`), region: value('PROXY_POOL_DEFAULT_COUNTRY', 'JP'), protocol: value(`${prefix}PROTOCOL`, 'http'), session_minutes: value(`${prefix}SESSION_MINUTES`, 30), ...(provider === '1024proxy' ? {validate: value('PROXY_1024_VALIDATE', true)} : {})}), {
      posting: true, label: '代理提取测试', apply: (response, receipt) => {
        if (receipt) {states.proxy.text = `测试已入队 · 任务 #${receipt.task_id}`; return;}
        const lease = record(response.lease);
        const endpoint = text(lease.endpoint, '—').replace(/\/\/[^/]*@/, '//').replace(/^[^/]*@/, '');
        states.proxy.snapshot = {provider: text(lease.provider, provider), endpoint, exit_ip: text(lease.exit_ip, '—'), region: text(lease.region, '—'), expires_at: text(lease.expires_at, '—')};
        states.proxy.text = `测试成功 · ${text(lease.provider, provider)} · ${endpoint} · 出口 ${text(lease.exit_ip, '—')} · ${text(lease.region, '—')} · 有效至 ${text(lease.expires_at, '—')}`;
      }, error: () => '代理提取测试失败，请检查供应商配置后重试。'});
  }
  function testButler() {
    return run('butler', '/api/email-butler/test-connection', post({api_base: credential(value('EMAIL_BUTLER_API_BASE')), api_key: secretValue('EMAIL_BUTLER_API_KEY')}), {posting: true, apply: response => {
      const missing = list(response.missing_permissions).map(item => text(item)).filter(Boolean);
      states.butler.snapshot = {name: text(response.name, 'Email Butler'), consumer: text(response.consumer), service: text(response.service), missing_permissions: missing};
      const policy = [text(response.consumer), text(response.service)].filter(Boolean).join(' / ') || '未绑定策略';
      states.butler.text = missing.length ? `连接成功，权限尚未齐全：${missing.join('、')}。请在 Butler 为原客户端补充权限。` : `连接成功：${text(response.name, 'Email Butler')} · ${policy}`;
    }, error: () => 'Email Butler 连接失败，请检查地址和客户端权限后重试。'});
  }
  function queryHuanguangQuota(kind: 'extraction' | 'payment') {
    const name = kind === 'extraction' ? 'huanguangExtraction' : 'huanguangPayment';
    const key = kind === 'extraction' ? 'EXTRACT_LINK_HUANGUANG_CDK' : 'EXTRACT_LINK_HUANGUANG_PAYMENT_CDK';
    if (owner.isDirty(key) || owner.isDirty('EXTRACT_LINK_HUANGUANG_API_BASE')) return refuse(name, '请先保存此 CDK 或服务地址的更改，再查询剩余次数');
    return run(name, `/api/extract-link/huanguang/cdk-quota/${kind}`, {method: 'GET'}, {apply: response => {
      const quota = record(response.quota);
      if (typeof quota.required !== 'boolean' || !(quota.remaining === null || count(quota.remaining)) || !(quota.reserved === null || count(quota.reserved)) || !(quota.active === null || typeof quota.active === 'boolean')) invalid();
      states[name].snapshot = {required: quota.required, remaining: quota.remaining, reserved: quota.reserved, active: quota.active};
      states[name].text = quota.required ? `剩余 ${quota.remaining ?? '未知'} 次 · 占用 ${quota.reserved ?? '未知'} · ${quota.active === false ? '已停用' : quota.active === true ? '已启用' : '可用状态未知'}` : '平台免计次';
    }, error: error => quotaError(error, false, kind === 'extraction' ? '幻光提链 CDK' : '幻光支付扫码 CDK')});
  }
  function queryHuanguangXxsyun() {
    if (owner.isDirty('EXTRACT_LINK_HUANGUANG_API_BASE')) return refuse('huanguangXxsyun', '请先保存服务地址的更改，再查询剩余次数');
    return run('huanguangXxsyun', '/api/extract-link/huanguang/xxsyun-quota', post(keyPayload('EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY')), {posting: true, apply: response => {
      if (!count(response.remainingUses) || !(response.totalUses == null || count(response.totalUses)) || !(response.reservedUses == null || count(response.reservedUses))) invalid();
      states.huanguangXxsyun.snapshot = {remainingUses: response.remainingUses, totalUses: response.totalUses ?? null, reservedUses: response.reservedUses ?? null};
      states.huanguangXxsyun.text = `剩余 ${response.remainingUses} 次 · 总次数 ${response.totalUses ?? '未知'} · 占用 ${response.reservedUses ?? '未知'}`;
    }, error: error => quotaError(error)});
  }
  function queryXxsyunBalance() {
    if (owner.isDirty('EXTRACT_LINK_PAYMENT_XXSYUN_API_BASE')) return refuse('xxsyunBalance', '请先保存服务地址的更改，再查询积分');
    return run('xxsyunBalance', '/api/extract-link/payments/xxsyun/balance', post(keyPayload('EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY')), {posting: true, apply: response => {
      const balance = record(response.balance), keys = ['available_points', 'pending_points', 'used_points', 'cost_points'];
      if (!response.balance || Array.isArray(response.balance) || !keys.every(key => balance[key] == null || nonnegative(balance[key]))) invalid();
      states.xxsyunBalance.snapshot = Object.fromEntries(keys.map(key => [key, balance[key] ?? null]));
      const points = (item: unknown) => item == null ? '未知' : `${item} 积分`;
      states.xxsyunBalance.text = `可用 ${points(balance.available_points)} · 预占 ${points(balance.pending_points)} · 已用 ${points(balance.used_points)} · 每单 ${points(balance.cost_points)}`;
    }, error: error => quotaError(error, true)});
  }
  function sentinel(check: boolean) {
    if (check && states.sentinel.snapshot?.running) return Promise.resolve();
    return run('sentinel', check ? '/api/maintenance/sentinel/check' : '/api/maintenance/sentinel', check ? post({}) : {method: 'GET'}, {posting: check, label: check ? 'Sentinel 检查' : undefined, apply: (response, receipt) => {
      const previous = states.sentinel.snapshot;
      states.sentinel.snapshot = {...response, candidate: response.candidate || previous?.candidate || null, comparison: !response.candidate && previous?.candidate ? previous.comparison : response.comparison};
      states.sentinel.text = receipt ? `检查已入队 · 任务 #${receipt.task_id}` : response.running ? '正在检查 Sentinel 更新…' : '已读取 Sentinel 检查状态。';
      if (!response.running && (['failed', 'corrupt'].includes(text(response.last_status)) || response.error_code)) {
        states.sentinel.error = response.last_status === 'corrupt' ? '候选资源不可用，请重试。' : '检查失败，请重试。';
      }
    }, error: () => check ? '检查请求未完成，请重试。' : '状态读取失败，请重试。'});
  }
  function refreshSentinel() {return sentinel(false);}
  function checkSentinel() {return sentinel(true);}
  function sub2api(check: boolean) {
    return run('sub2api', check ? '/api/sub2api/automation/check' : '/api/sub2api/automation', check ? post({}) : {method: 'GET'}, {posting: check, label: check ? 'Sub2API 异常扫描' : undefined, apply: (response, receipt) => {
      states.sub2api.snapshot = response;
      if (receipt) {states.sub2api.text = `异常扫描已入队 · 任务 #${receipt.task_id}，最终结果在任务回执中更新。`; return;}
      if (check) {
        const summary = record(response.result);
        const labels: Record<string, string> = {account_busy: '账号忙碌', cooldown: '冷却中', account_archived: '账号已归档', account_deactivated: '账号已停用', automatic_login_material_missing: '自动登录资料不足', unrecognized_remote_error: '远端错误原因未识别', remote_transient_error: '远端网络或限流错误', needs_reconciliation: '上次请求结果待核实', repair_in_progress: '修复进行中'};
        const reasons = Object.entries(record(summary.reasons)).filter(([, value]) => count(value)).map(([code, value]) => `${labels[code] || '其他原因'} ${value}`).join('，');
        states.sub2api.text = `本轮检查 ${summary.remote_errors ?? 0} 条异常记录，已调度同步 ${summary.sync_queued ?? 0}、刷新 ${summary.refresh_queued ?? 0}、重授权 ${summary.reauth_queued ?? 0}。${reasons ? `处理说明：${reasons}。` : ''}`;
      } else {
        const sync = record(response.sync), monitor = record(response.monitor), counts = record(sync.counts);
        const groupIds=list(monitor.group_ids).map(id=>text(id)).filter(Boolean),scope=groupIds.length?`分组 ID ${groupIds.join('、')}`:'全部分组';
        states.sub2api.text = `自动补传${sync.enabled ? '已开启' : '已关闭'}；异常巡检${monitor.enabled ? '已开启' : '已关闭'}；巡检范围：${scope}。待同步 ${counts.pending ?? 0}，排队 ${counts.queued ?? 0}，执行 ${counts.running ?? 0}。`;
      }
    }, error: () => 'Sub2API 状态或巡检请求未完成，请稍后重试。'});
  }
  function querySub2ApiGroups() {
    return run('sub2apiGroups','/api/sub2api/groups',{method:'GET'},{apply:response=>{
      if(response.ok!==true||!Array.isArray(response.groups)||response.groups.some(raw=>{const group=record(raw);return !Number.isSafeInteger(group.id)||Number(group.id)<=0||typeof group.name!=='string';}))throw new Error('分组响应格式无效，请重试');
      const groups=[...new Map(response.groups.map(raw=>{const group=record(raw);return [group.id,group] as const;})).values()];
      states.sub2apiGroups.snapshot={options:groups.map(group=>({value:String(group.id),label:`${group.name}（ID ${group.id}）`}))};
      states.sub2apiGroups.text=`已查询 ${groups.length} 个分组`;
    },error:error=>{const detail=error instanceof Error?error.message:text(record(error).error);return detail==='分组响应格式无效，请重试'?detail:`查询分组失败：${detail||'请检查已保存的连接配置后重试'}`;}});
  }
  function refreshSub2Api() {return sub2api(false);}
  function checkSub2Api() {return sub2api(true);}
  function refreshC2a() {
    return run('c2a', '/api/c2a/automation', {method: 'GET'}, {apply: response => {
      const monitor = record(response.monitor);
      if (typeof monitor.enabled !== 'boolean') invalid();
      states.c2a.snapshot = monitor;
      const enabled = `自动巡检${monitor.enabled ? '已开启' : '已关闭'}`;
      if (monitor.error_code === 'c2a_config_invalid') {
        states.c2a.text = `${enabled}。请检查并保存 C2A 连接配置。`;
        return;
      }
      if (!monitor.state_available) {
        states.c2a.text = `${enabled}。修复状态暂不可用，请稍后重试。`;
        return;
      }
      const stages = record(monitor.repair_stages);
      const stageCount = (key: string) => count(stages[key]) ? stages[key] : 0;
      states.c2a.text = `${enabled}。待提交刷新 ${stageCount('refresh_pending')}，等待刷新 ${stageCount('refresh_wait')}，刷新冷却 ${stageCount('refresh_retry')}，刷新失败已跳过 ${stageCount('refresh_exhausted')}，同步待完成 ${stageCount('sync_wait')}，已结束 ${stageCount('done')}，已取消 ${stageCount('cancelled')}。`;
    }, error: () => '暂时无法读取 C2A 巡检状态，请稍后重试。'});
  }
  function checkC2a() {
    return run('c2a', '/api/c2a/automation/check', post({}), {posting: true, label: 'C2A 异常巡检', apply: (_response, receipt) => {
      if (!receipt) invalid();
      states.c2a.text = `C2A 异常巡检已入队 · 任务 #${receipt.task_id}。扫描结果在任务回执中更新。`;
    }, error: error => record(error).code === 'c2a_config_invalid' || record(error).error_code === 'c2a_config_invalid'
      ? 'C2A 连接配置无效，请检查并保存 API 基址和管理员 Key。'
      : 'C2A 巡检暂时无法入队，请稍后重试。'});
  }
  function loadConcurrencyPreview() {
    return run('concurrencyPreview', '/api/config/concurrency-preview', {method: 'GET'}, {apply: response => {states.concurrencyPreview.snapshot = response;}, error: () => '迁移预览暂不可用，请刷新重试。'});
  }
  async function refreshConcurrency(options: {details?: boolean} = {}) {
    const preview = states.concurrencyPreview.snapshot ? Promise.resolve() : loadConcurrencyPreview();
    await Promise.all([preview, run('concurrency', `/api/operations/concurrency${options.details ? '?details=1' : ''}`, {method: 'GET'}, {apply: response => {
      states.concurrency.snapshot = response;
      const global = record(response.global);
      states.concurrency.text = `当前占用 ${global.occupied ?? 0} / ${global.limit ?? '—'}${global.draining ? '，等待现有任务结束' : ''}；预约 ${global.reserved ?? 0} · 执行 ${global.executing ?? 0} · 清理 ${global.cleaning ?? 0} · 调试保留 ${global.debug_hold ?? 0}；排队 ${response.queued ?? 0} · 远端等待 ${response.remote_waiting ?? '—'}`;
    }, error: () => '状态读取失败，请重试；显示的数据为上次观察结果。'})]);
  }
  function applyConcurrencyPreview(): string[] {
    if (disposed) return [];
    const changed: string[] = [];
    for (const [key, proposed] of Object.entries(record(states.concurrencyPreview.snapshot?.proposed_values))) {
      const field = owner.field(key);
      if (!field || field.group !== '并发控制' || field.type !== 'int' || owner.isDirty(key) || !count(proposed) || Number(proposed) <= 0) continue;
      owner.setField(key, Number(proposed), {force: true}); changed.push(key);
    }
    states.concurrencyPreview.text = '迁移建议已填入草稿；核对全局和各类型上限后点击保存。'; return changed;
  }
  function locateConcurrencyTasks(key: string) {
    if (disposed) return;
    if (key.startsWith('REGISTRATION_')) {dependencies.onNavigateTasks?.({registration: true}); return;}
    const type = list(states.concurrency.snapshot?.types).map(record).find(item => item.config_key === key || item.key === key);
    const types = type ? list(type.task_types).length ? list(type.task_types).map(item => text(item)) : [text(type.key)] : [];
    dependencies.onNavigateTasks?.({types: [...new Set(types.filter(Boolean))]});
  }
  function setVisible(name: PollingAction, enabled: boolean) {
    if (disposed || visible[name] === enabled) return;
    visible[name] = enabled;
    if (!enabled) {clearTimer(name); invalidate(name, true); if (name === 'concurrency') invalidate('concurrencyPreview', true);}
    else if (foreground && pageActive) void (name === 'sentinel' ? refreshSentinel() : refreshConcurrency());
  }
  function setForeground(enabled: boolean) {
    if (disposed || foreground === enabled) return;
    foreground = enabled;
    for (const name of ['sentinel', 'concurrency'] as const) {
      clearTimer(name);
      if (!enabled) {invalidate(name, true); if (name === 'concurrency') invalidate('concurrencyPreview', true);}
      else if (pageActive && visible[name]) void (name === 'sentinel' ? refreshSentinel() : refreshConcurrency());
    }
  }
  function setPageActive(enabled: boolean) {
    if (disposed || pageActive === enabled) return;
    pageActive = enabled;
    clearTimer('sentinel'); clearTimer('concurrency');
    if (!enabled) {
      for (const name of NAMES) invalidate(name, true);
    } else if (foreground) {
      if (visible.sentinel) void refreshSentinel();
      if (visible.concurrency) void refreshConcurrency();
    }
  }
  function dispose() {
    if (disposed) return;
    disposed = true; stops.forEach(stop => stop());
    clearTimer('sentinel'); clearTimer('concurrency');
    for (const name of NAMES) invalidate(name, true);
  }
  return {states, sub2apiGroups:computed(()=>(states.sub2apiGroups.snapshot?.options||[]) as ConfigOption[]), querySub2ApiGroups, extractTypeOptions: computed(() => (states.extractTypes.snapshot?.options || []) as ConfigOption[]), roxyWorkspaces: computed(() => (states.roxy.snapshot?.items || []) as RoxyWorkspace[]),
    loadExtractTypes, loadRoxyWorkspaces, saveRoxySelection, testProxy, testButler, queryHuanguangQuota, queryHuanguangXxsyun, queryXxsyunBalance, refreshSentinel, checkSentinel, refreshSub2Api, checkSub2Api, refreshC2a, checkC2a, refreshConcurrency, loadConcurrencyPreview, applyConcurrencyPreview, locateConcurrencyTasks, setVisible, setForeground, setPageActive, dispose};
}
