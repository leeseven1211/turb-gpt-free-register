import type {AccountActionContext, AccountViewRow} from './useAccounts';
import type {AccountActionDependencies} from './actions';
import {accountRequestKeyHeader, createAccountOperationReceipts} from './operationReceipts';
import {openAccountOperationTasks} from './taskNavigation';
import type {AccountTaskOpen} from './taskNavigation';
import type {TaskId} from '../../api/taskIds';

export interface AccountQueuedDependencies {
  refresh(context: AccountActionContext): Promise<unknown>;
  pollStatuses(context: AccountActionContext): Promise<unknown>;
  refreshSummary(): void | Promise<unknown>;
  reloadTasks(): void | Promise<unknown>;
  operationWorkers(): number;
  configuredLiveCheckDriver(): string | null;
  /** Inject the shared GET /api/config cache with its existing 30,000 ms TTL. */
  readConfig(): Promise<unknown>;
  fallbackConfig(): unknown;
  openLiveLog(email: string): void | Promise<unknown>;
  openAccountTaskLog(taskId: TaskId, runId: TaskId | null): void | Promise<unknown>;
  openTasks(options: AccountTaskOpen): void | Promise<unknown>;
  openReceiptTask?(taskId: TaskId, runId: TaskId | null): void | Promise<unknown>;
  getRowSnapshot(id: string): {deactivation_mail_scan_status?: unknown} | undefined;
  isOwnerActive(): boolean;
  clearScheduled(handle: unknown): void;
  updateBusyLabel?(descriptor: string, trigger: HTMLElement | null, label: string): void;
}
type Kind = 'plan' | 'live' | 'token' | 'mail' | 'extract';
interface Action {kind: Kind; single: boolean; error: string}
const actions: Readonly<Record<string, Action>> = {
  'plan-check': {kind: 'plan', single: true, error: ''},
  checkSelectedPlans: {kind: 'plan', single: false, error: '批量查询失败: '},
  'account-live-check': {kind: 'live', single: true, error: '查活失败: '},
  checkSelectedLive: {kind: 'live', single: false, error: '查活失败: '},
  'account-refresh-token': {kind: 'token', single: true, error: '刷新AT失败: '},
  refreshSelectedToken: {kind: 'token', single: false, error: '刷新AT失败: '},
  'deactivation-mail-check': {kind: 'mail', single: true, error: '扫描失败: '},
  checkSelectedDeactivationMail: {kind: 'mail', single: false, error: '批量扫描失败: '},
  'extract-link': {kind: 'extract', single: true, error: '提链失败: '},
  extractSelectedLinks: {kind: 'extract', single: false, error: '批量提链失败: '},
};
const operationTypes: Readonly<Record<Kind, string>> = {
  plan: 'plan_check', live: 'live_check', token: 'token_refresh', mail: 'deactivation_mail', extract: 'extract_link',
};
const receiptLabels = {plan: '查套餐', live: '查活', token: '刷新 AT', mail: '封号邮件扫描'};
const isSupported = (name: string) => Object.prototype.hasOwnProperty.call(actions, name);
const message = (cause: unknown) => cause instanceof Error ? cause.message : '请求失败，请稍后重试。';
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('服务端响应格式无效');
  const result = value as Record<string, unknown>;
  if (result.ok === false) throw new Error(typeof result.error === 'string' ? result.error : '请求失败');
  return result;
}
function rows(value: unknown): Record<string, unknown>[] {
  if (value == null) return [];
  if (!Array.isArray(value)) throw new Error('服务端响应格式无效');
  return value.map(item => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) throw new Error('服务端响应格式无效');
    return item as Record<string, unknown>;
  });
}
function count(value: unknown): number {
  const result = Number(value || 0);
  if (!Number.isSafeInteger(result) || result < 0) throw new Error('服务端响应格式无效');
  return result;
}
function idsOf(context: AccountActionContext): number[] {
  if (!Array.isArray(context?.accountIds)) throw new Error('账号动作上下文不可用，请刷新后重试');
  return [...new Set(context.accountIds.map(id => {
    if (typeof id !== 'string' || !/^[1-9]\d*$/.test(id) || !Number.isSafeInteger(Number(id))) throw new Error('账号 ID 无效');
    return Number(id);
  }))];
}
function frozenCopy<T>(value: T): T {
  if (Array.isArray(value)) return Object.freeze(value.map(frozenCopy)) as T;
  if (value && typeof value === 'object') return Object.freeze(Object.fromEntries(Object.entries(value).map(([key, item]) => [key, frozenCopy(item)]))) as T;
  return value;
}
function contextForReads(context: AccountActionContext, ids: number[]): AccountActionContext {
  // List callbacks need the captured scope; they never need credential or display data.
  return frozenCopy({accountIds: ids.map(String), expectedEmails: {...context.expectedEmails},
    querySnapshot: context.querySnapshot, archived: context.archived, rowHints: []});
}
function queueReasons(result: Record<string, unknown>): string {
  const reasons = [...rows(result.skipped), ...rows(result.failed)].map(item => String(item.reason || item.error || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
  if (!reasons.length) return '';
  const details = reasons.slice(0, 3).map(reason => reason.length > 80 ? `${reason.slice(0, 80)}…` : reason);
  return `；${details.join('；')}${reasons.length > 3 ? `；另有 ${reasons.length - 3} 条原因` : ''}`;
}
function targetFor(context: AccountActionContext, id: number): string {
  const row = context.rowHints.find(item => String(item.id) === String(id));
  const target = String(row?.email || context.expectedEmails[String(id)] || '').trim();
  return target || String(id);
}
function listLength(value: unknown): number {
  return Array.isArray(value) ? value.length : 0;
}
function hasAcceptedTask(result: Record<string, unknown>, single: boolean): boolean {
  const queued = listLength(result.started) + listLength(result.queued) + listLength(result.reused);
  const counted = count(result.started_count) + count(result.queued_count) + count(result.reused_count);
  if (queued > 0 || counted > 0) return true;
  return single && (result.accepted === true || result.started === true);
}
function tokenSettings(raw: unknown): {description: string; debugDescription: string} {
  const fields = Array.isArray(raw) ? raw.filter(item => item && typeof item === 'object') as Record<string, unknown>[] : [];
  const field = (key: string) => fields.find(item => item.key === key);
  const driverField = field('ACCOUNT_AT_REFRESH_DRIVER');
  const driver = String(driverField?.value || 'protocol').trim().toLowerCase() === 'browser_roxy' ? 'browser_roxy' : 'protocol';
  const debug = field('ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED')?.value;
  const debugEnabled = debug === true || String(debug).trim().toLowerCase() === 'true';
  const requestedVersion = String(field('OPENAI_PROTOCOL_VERSION')?.value || 'v1').trim().toLowerCase();
  const version = ['v2', 'v3'].includes(requestedVersion) ? requestedVersion : 'v1';
  const label = driverField ? driver === 'browser_roxy' ? 'Roxy 指纹浏览器' : `协议刷新（${version}）` : '已保存的刷新驱动';
  const description = driver === 'protocol' && version === 'v3'
    ? `使用${label}先复用该账号有效的登录会话；会话失效或尚未保存时，按实际挑战完成密码、2FA 或邮箱验证，核对账号身份并保存最新 accessToken。`
    : `使用${label}重新登录，按实际挑战完成密码、2FA 或邮箱验证，并保存最新 accessToken。`;
  return {description, debugDescription: debugEnabled ? 'Roxy 刷新调试已开启：实际使用 Roxy 时将显示浏览器并全程抓包；失败保留窗口，可从任务日志查看现场并下载 HAR。' : ''};
}
function trialKind(row: AccountViewRow): string {
  const explicit = String(row.plus_promo_kind || '').trim().toLowerCase();
  if (['free_trial', 'discount', 'other_promo', 'none', 'unknown'].includes(explicit)) return explicit;
  const raw: unknown = row.plus_promo_discount_percentage ?? row.plus_trial_discount_percentage;
  const percentage = raw === null || raw === undefined || raw === '' ? NaN : Number(raw);
  const campaign = String(row.plus_promo_campaign_id || row.plus_trial_campaign_id || '').trim().toLowerCase();
  const searchable = [campaign, row.plus_promo_title || row.plus_trial_title, row.plus_promo_promotion_type,
    row.plus_promo_promotion_type_label || row.plus_trial_promotion_type_label].join(' ').toLowerCase();
  if (percentage === 100) return 'free_trial';
  if (Number.isFinite(percentage) && percentage > 0 && percentage < 100) return 'discount';
  if (searchable.includes('pct-off') || searchable.includes('discount') || searchable.includes('% off')) return 'discount';
  if (searchable.includes('free trial') || campaign.includes('-free') || campaign.includes('trial')) return 'free_trial';
  if (searchable.trim()) return 'other_promo';
  if (row.plus_discount_eligible === true) return 'discount';
  return row.plus_promo_eligible === true || row.plus_trial_eligible === true ? 'unknown' : 'none';
}

export function createQueuedAccountActions(base: AccountActionDependencies, deps: AccountQueuedDependencies) {
  const pending = new Set<string>(), waits = new Set<() => void>();
  const receipts = createAccountOperationReceipts(base, deps.openReceiptTask ?? deps.openAccountTaskLog);
  let mailReads: {generation: number; targets: Set<{ids: number[]; attempts: number}>} | undefined;
  let visible = true, disposed = false, readGeneration = 0;
  const keyFor = (name: string, ids: readonly (string | number)[]) => actions[name]?.single ? JSON.stringify([name, ...ids.map(String)]) : name;
  const active = (generation: number) => !disposed && visible && generation === readGeneration && deps.isOwnerActive();
  function stopReads() {++readGeneration; for (const stop of [...waits]) stop();}
  function wait(generation: number): Promise<boolean> {
    if (!active(generation)) return Promise.resolve(false);
    return new Promise(resolve => {
      let handle: unknown;
      const stop = () => {deps.clearScheduled(handle); waits.delete(stop); resolve(false);};
      waits.add(stop);
      handle = base.schedule(() => {waits.delete(stop); resolve(active(generation));}, 1500);
    });
  }
  async function mailResults(ids: number[], context: AccountActionContext, generation: number): Promise<void> {
    const target = {ids, attempts: 0};
    if (mailReads?.generation === generation) {
      if (ids.length) mailReads.targets.add(target);
      return;
    }
    const pendingReads = {generation, targets: new Set(ids.length ? [target] : [])};
    mailReads = pendingReads;
    try {
      await deps.refresh(context);
      while (pendingReads.targets.size && await wait(generation)) {
        // 只处理本次读取开始前已获受理的账号，避免把新增账号的旧状态当成扫描结果。
        const targets = [...pendingReads.targets];
        await deps.refresh(context);
        if (!active(generation)) return;
        for (const target of targets) {
          const visibleRows = target.ids.map(id => deps.getRowSnapshot(String(id))).filter(row => row != null);
          const finished = visibleRows.length > 0 && visibleRows.every(row => !['queued', 'running'].includes(String(row.deactivation_mail_scan_status || '')));
          if (++target.attempts >= 30 || finished) pendingReads.targets.delete(target);
        }
      }
    } finally { if (mailReads === pendingReads) mailReads = undefined; }
  }
  async function updateAfterAccepted(update: () => unknown, current: () => boolean = () => true): Promise<void> {
    try {if (current()) await update();} catch (cause) {if (current()) base.notify(`请求已处理，但页面更新失败: ${message(cause)}`);}
  }
  async function invoke(name: string, supplied: AccountActionContext, trigger: HTMLElement | null = null): Promise<void> {
    if (!isSupported(name)) throw new Error(`未支持的账号动作：${name}`);
    if (disposed || !visible || base.canInvoke?.(name, trigger) === false) return;
    const action = actions[name]!;
    let key: string | undefined, restore: (() => void) | undefined;
    const generation = readGeneration;
    const current = () => active(generation);
    try {
      const ids = idsOf(supplied);
      if (!ids.length) {base.notify('请先选择账号'); return;}
      if (action.single && ids.length !== 1) throw new Error('此操作只能选择一个账号');
      const singleTarget = ids.length === 1 ? targetFor(supplied, ids[0]!) : '';
      key = keyFor(name, ids);
      if (pending.has(key)) {key = undefined; return;}
      pending.add(key);
      const context = contextForReads(supplied, ids);
      const busy = (label: string) => {restore = base.beginBusy?.(name, trigger, label) || undefined;};
      const post = async (path: string, body?: object, requestKey?: string) => {
        const headers: Record<string, string> = {};
        const options: RequestInit = {method: 'POST'};
        if (requestKey) headers[accountRequestKeyHeader] = requestKey;
        if (body !== undefined) {
          headers['Content-Type'] = 'application/json';
          options.body = JSON.stringify(body);
        }
        if (requestKey || body !== undefined) options.headers = headers;
        const result = object(await base.request(path, options));
        if (requestKey && result.ok !== true) throw new Error('服务端响应格式无效');
        return result;
      };
      const submit = (kind: keyof typeof receiptLabels, path: string, body?: object) =>
        receipts.submit(receiptLabels[kind], ids.length, requestKey => post(path, body, requestKey));
      if (action.kind === 'plan') {
        busy('查询中…');
        let result: Record<string, unknown> | undefined;
        try {result = await submit('plan', action.single ? '/api/accounts/check-plan' : '/api/accounts/check-plan-bulk', action.single ? {account_id: ids[0]} : {account_ids: ids});}
        catch (cause) {
          base.notify(action.error + message(cause));
          if (action.single && current()) {
            void deps.pollStatuses(context).catch(readError => {
              if (current()) base.notify(`套餐状态读取失败: ${message(readError)}`);
            });
          }
          return;
        }
        if (!result) return;
        base.notify(action.single ? String(result.message || '套餐查询已加入后台队列')
          : `已入队 ${count(result.started_count)} 个，查询中跳过 ${count(result.busy_count)} 个，入队失败 ${count(result.failed_count)} 个${rows(result.skipped).length ? `，跳过 ${rows(result.skipped).length} 个` : ''}${queueReasons(result)}`);
        if (hasAcceptedTask(result, action.single)) {
          void updateAfterAccepted(() => openAccountOperationTasks(
            {openTasks: deps.openTasks, openTask: deps.openAccountTaskLog},
            {single: action.single, type: operationTypes[action.kind], target: singleTarget || undefined, result},
          ), current);
        }
        void updateAfterAccepted(() => deps.pollStatuses(context), current);
      } else if (action.kind === 'live') {
        const workers = deps.operationWorkers();
        const note = action.single ? '确定查活这个账号吗？\n\n只在线验证现有 accessToken，不会发送邮箱验证码，也不会刷新 AT。'
          : `确定查活选中的 ${ids.length} 个账号吗？\n\n只在线验证现有 accessToken，不会发送邮箱验证码，也不会刷新 AT。\n\n并发线程数：${workers}`;
        if (!await base.confirm(note)) return;
        busy('查活中…');
        const result = await submit('live', '/api/accounts/check-live-bulk', {account_ids: ids, driver: deps.configuredLiveCheckDriver()});
        if (!result) return;
        const skipped = rows(result.skipped).length;
        base.notify(`查活已入队 ${count(result.started_count)} 个，忙碌 ${count(result.busy_count)} 个，失败 ${count(result.failed_count)}${skipped ? `，跳过 ${skipped}` : ''}（配置驱动：${deps.configuredLiveCheckDriver() || '默认'}，实际驱动：${result.live_check_driver || '未知'}）${queueReasons(result)}`);
        if (hasAcceptedTask(result, action.single)) {
          void updateAfterAccepted(() => openAccountOperationTasks(
            {openTasks: deps.openTasks, openTask: deps.openAccountTaskLog},
            {single: action.single, type: operationTypes[action.kind], target: singleTarget || undefined, result},
          ), current);
        }
        void updateAfterAccepted(() => deps.refresh(context), current);
        void updateAfterAccepted(() => deps.refreshSummary(), current);
      } else if (action.kind === 'token') {
        const workers = deps.operationWorkers();
        let config = deps.fallbackConfig();
        const hasRefreshDriver = Array.isArray(config)
          && config.some(field => field?.key === 'ACCOUNT_AT_REFRESH_DRIVER');
        busy(hasRefreshDriver ? '刷新 AT…' : '读取配置…');
        if (!hasRefreshDriver) {
          try {config = await deps.readConfig();} catch {config = deps.fallbackConfig();}
        }
        const settings = tokenSettings(config), scope = ids.length === 1 ? '这个账号' : `选中的 ${ids.length} 个账号`;
        if (!await base.confirm(`确定刷新${scope}的 AT 吗？\n\n${settings.description}${settings.debugDescription ? `\n\n${settings.debugDescription}` : ''}${ids.length > 1 ? `\n\n并发线程数：${workers}` : ''}`)) return;
        deps.updateBusyLabel?.(name, trigger, '刷新中…');
        const result = await submit('token', '/api/accounts/refresh-token-bulk', {account_ids: ids});
        if (!result) return;
        const skipped = rows(result.skipped).length;
        base.notify(`刷新AT已入队 ${count(result.started_count)} 个，忙碌 ${count(result.busy_count)} 个，失败 ${count(result.failed_count)}${skipped ? `，跳过 ${skipped}` : ''}${queueReasons(result)}`);
        if (hasAcceptedTask(result, action.single)) {
          void updateAfterAccepted(() => openAccountOperationTasks(
            {openTasks: deps.openTasks, openTask: deps.openAccountTaskLog},
            {single: action.single, type: operationTypes[action.kind], target: singleTarget || undefined, result},
          ), current);
        }
        void updateAfterAccepted(() => deps.refresh(context), current);
        void updateAfterAccepted(() => deps.refreshSummary(), current);
      } else if (action.kind === 'mail') {
        busy('扫描中…');
        const result = await submit('mail', action.single ? `/api/accounts/${ids[0]}/check-deactivation-mail` : '/api/accounts/check-deactivation-mail-bulk', action.single ? undefined : {account_ids: ids});
        if (!result) return;
        base.notify(action.single ? '封号邮件扫描已入队；不会刷新 AT' : `已入队 ${count(result.started_count)} 个，跳过 ${count(result.skipped_count)} 个；不会刷新 AT${queueReasons(result)}`);
        if (hasAcceptedTask(result, action.single)) {
          void updateAfterAccepted(() => openAccountOperationTasks(
            {openTasks: deps.openTasks, openTask: deps.openAccountTaskLog},
            {single: action.single, type: operationTypes[action.kind], target: singleTarget || undefined, result},
          ), current);
        }
        void updateAfterAccepted(() =>
          mailResults(action.single || count(result.started_count) > 0 ? ids : [], context, generation), current);
      } else if (action.kind === 'extract') {
        if (action.single) {
          const row = supplied.rowHints.find(item => String(item.id) === String(ids[0]));
          if (!row) {base.notify('账号不存在'); return;}
          const plan = String(row.current_plan_type || row.plan_type || '').toLowerCase();
          if (plan !== 'free' || trialKind(row) !== 'free_trial') {base.notify('仅支持已确认 Plus 免费试用资格的 free 账号提链；折扣优惠不支持'); return;}
          if (!await base.confirm(`确定为该账号提链吗？\n\n${row.email || ('#' + ids[0])}\n\n提链类型按配置使用，成功会消耗 1 次 CDK。`)) return;
        } else if (!await base.confirm(`确定为选中的 ${ids.length} 个账号批量提链吗？\n\n仅处理已确认的 Plus 免费试用账号，折扣优惠和历史待复查账号会自动跳过。成功会按账号消耗 CDK 次数。`)) return;
        busy('提链中…');
        const result = await post(action.single ? '/api/accounts/extract-link' : '/api/accounts/extract-link-bulk', action.single ? {account_id: ids[0]} : {account_ids: ids});
        if (action.single) {
          const fallback = result.fallback_from && result.link_type ? `；${String(result.fallback_from).toUpperCase()} 已失败，改用 ${String(result.link_type).toUpperCase()}` : '';
          base.notify(`提炼任务已入队${result.task_id ? ` · 任务 #${result.task_id}` : ''}${fallback}，可在任务中心查看日志`);
        } else {
          const skipped = count(result.skipped_count) + count(result.busy_count) + count(result.failed_count);
          const fallbackCount = rows(result.started).filter(item => item.fallback_from).length;
          base.notify(`已入队 ${count(result.started_count)} 个${skipped ? `，跳过/失败 ${skipped} 个` : ''}${fallbackCount ? `，其中 ${fallbackCount} 个已自动跳过失败类型` : ''}${queueReasons(result)}`);
        }
        if (hasAcceptedTask(result, action.single)) {
          void updateAfterAccepted(() => openAccountOperationTasks(
            {openTasks: deps.openTasks, openTask: deps.openAccountTaskLog},
            {single: action.single, type: operationTypes[action.kind], target: singleTarget || undefined, result},
          ), current);
        }
        await updateAfterAccepted(async () => {await deps.reloadTasks(); await deps.pollStatuses(context);});
      }
    } catch (cause) {base.notify(action.error + message(cause));}
    finally {if (key) pending.delete(key); restore?.();}
  }
  return {isSupported, invoke, receipts: receipts.view, isPending: (name: string, context: AccountActionContext) => pending.has(keyFor(name, context.accountIds)),
    setVisible(value: boolean) {visible = value; if (!value) stopReads();},
    dispose() {disposed = true; stopReads();},
  };
}
