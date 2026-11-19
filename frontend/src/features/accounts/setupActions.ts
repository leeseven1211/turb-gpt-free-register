import {accountBulkUnqueuedReasons} from './useC2aReimport';
import type {AccountActionContext} from './useAccounts';
import type {AccountActionDependencies} from './actions';

export interface AccountTaskOpen {filters?: Record<string, unknown>; taskId?: number; runId?: number | null}
export interface RegistrationRetryEntry {
  account_id?: number; email?: string; task_id?: number; operation_task_id?: number; run_id?: number; job_id?: number;
  reason?: string; error?: string; [key: string]: unknown;
}
export interface RegistrationRetryReceipt {
  started: readonly RegistrationRetryEntry[]; reused: readonly RegistrationRetryEntry[]; skipped: readonly RegistrationRetryEntry[];
  started_count: number; reused_count: number; skipped_count: number;
}
export interface AccountSetupDependencies {
  refresh(context: AccountActionContext): Promise<unknown>;
  pollStatuses(context: AccountActionContext): Promise<unknown>;
  operationWorkers(): number;
  openTasks(options: AccountTaskOpen): void | Promise<unknown>;
  openLog(jobId: number): void | Promise<unknown>;
  trackAcceptedOperations(rows: readonly Record<string, unknown>[], label: string): void | Promise<unknown>;
  /** Render entries as text/escaped values; the action owner supplies authoritative navigation. */
  showRegistrationResult(result: RegistrationRetryReceipt, context: AccountActionContext,
    open: (entries: readonly RegistrationRetryEntry[]) => Promise<void>): void;
}
type AccountAction = 'password' | 'twofa' | 'password_change' | 'twofa_change' | 'complete';
const accountActions: Readonly<Record<AccountAction, {label: string; type: string}>> = {
  password: {label: '补密码', type: 'password_setup'}, twofa: {label: '补 2FA', type: 'twofa_setup'},
  password_change: {label: '修改密码', type: 'password_change'}, twofa_change: {label: '修改 2FA', type: 'twofa_change'},
  complete: {label: '补全账号', type: 'account_completion'},
};
const bulkActions: Readonly<Record<string, AccountAction>> = {
  addPasswordSelectedAccounts: 'password', addTwofaSelectedAccounts: 'twofa', changePasswordSelectedAccounts: 'password_change',
  changeTwofaSelectedAccounts: 'twofa_change', completeSelectedAccounts: 'complete',
};
const supported = new Set(['account-setup', 'setupSelectedAccounts', 'codex-stop', 'codex-reset-retrying', 'codex-retry',
  'stopSelectedCodex', 'retrySelectedCodex', 'uploadSelectedCodexSub2', 'account-registration-retry', 'retryAccountRegistration']);
const own = (source: object, key: string) => Object.prototype.hasOwnProperty.call(source, key);
function parsed(descriptor: string) {
  const index = descriptor.indexOf(':');
  return index < 0 ? {name: descriptor, value: ''} : {name: descriptor.slice(0, index), value: descriptor.slice(index + 1)};
}
function isSupported(descriptor: string): boolean {
  const {name, value} = parsed(descriptor);
  if (name === 'account-action') return own(accountActions, value);
  if (name === 'account-registration-task') return /^[1-9]\d*$/.test(value) && Number.isSafeInteger(Number(value));
  return !descriptor.includes(':') && (supported.has(name) || own(bulkActions, name));
}
function record(value: unknown, envelope = false): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('服务端响应格式无效');
  const result = value as Record<string, unknown>;
  if (envelope && result.ok === false) throw new Error(typeof result.error === 'string' ? result.error : '请求失败');
  return result;
}
function entries(value: unknown): RegistrationRetryEntry[] {
  if (value == null) return [];
  if (!Array.isArray(value)) throw new Error('服务端响应格式无效');
  return value.map(item => record(item));
}
function count(value: unknown): number {
  const result = Number(value || 0);
  if (!Number.isSafeInteger(result) || result < 0) throw new Error('服务端响应格式无效');
  return result;
}
function copy<T>(value: T): T {
  if (Array.isArray(value)) return Object.freeze(value.map(copy)) as T;
  if (value && typeof value === 'object') return Object.freeze(Object.fromEntries(Object.entries(value).map(([key, item]) => [key, copy(item)]))) as T;
  return value;
}
function snapshot(source: AccountActionContext): AccountActionContext {
  if (!Array.isArray(source?.accountIds)) throw new Error('账号动作上下文不可用，请刷新后重试');
  const accountIds = [...new Set(source.accountIds.map(id => {
    if (typeof id !== 'string' || !/^[1-9]\d*$/.test(id) || !Number.isSafeInteger(Number(id))) throw new Error('账号 ID 无效');
    return id;
  }))];
  return copy({accountIds, expectedEmails: source.expectedEmails, querySnapshot: source.querySnapshot, archived: source.archived,
    rowHints: source.rowHints});
}
function retryReceipt(result: Record<string, unknown>): RegistrationRetryReceipt {
  const started = entries(result.started), reused = entries(result.reused), skipped = entries(result.skipped);
  return copy({started, reused, skipped, started_count: count(result.started_count ?? started.length),
    reused_count: count(result.reused_count ?? reused.length), skipped_count: count(result.skipped_count ?? skipped.length)});
}
function retrySummary(result: RegistrationRetryReceipt): string {
  return `注册重跑：已创建 ${result.started_count} 个，进行中 ${result.reused_count} 个，跳过 ${result.skipped_count} 个`;
}
const message = (error: unknown) => error instanceof Error ? error.message : '请求失败，请稍后重试。';
const isRetry = (name: string) => name === 'account-registration-retry' || name === 'retryAccountRegistration';
const isSingle = (name: string) => name.startsWith('account-') || name.startsWith('codex-');

export function createAccountSetupActions(base: AccountActionDependencies, deps: AccountSetupDependencies) {
  const pending = new Set<string>(), retryPending = new Set<string>();
  const keyFor = (descriptor: string, ids: readonly string[]) => isSingle(parsed(descriptor).name) ? JSON.stringify([descriptor, ...ids]) : descriptor;
  async function openRegistrationTasks(items: readonly RegistrationRetryEntry[], context: AccountActionContext): Promise<void> {
    const item = items.length === 1 ? items[0] : undefined;
    const row = item && context.rowHints.find(value => String(value.id) === String(item.account_id));
    const taskId = item?.task_id || item?.operation_task_id;
    await deps.openTasks({filters: {target: item?.email || row?.email || (item ? context.expectedEmails[String(item.account_id)] : '') || ''},
      taskId: taskId ? Number(taskId) : undefined, runId: item?.run_id ? Number(item.run_id) : null});
    if (!taskId && item?.job_id) await deps.openLog(Number(item.job_id));
  }
  async function pageUpdate(update: () => Promise<unknown>): Promise<void> {
    try {await update();} catch (cause) {base.notify(`请求已处理，但页面更新失败: ${message(cause)}`);}
  }
  async function refreshAndOpen(context: AccountActionContext, options?: AccountTaskOpen): Promise<void> {
    // A successful submission must retain its task link even when the independent list refresh fails.
    await pageUpdate(() => deps.refresh(context));
    if (options) await pageUpdate(async () => deps.openTasks(options));
  }
  async function invoke(descriptor: string, supplied: AccountActionContext, trigger: HTMLElement | null = null): Promise<void> {
    if (!isSupported(descriptor)) throw new Error(`未支持的账号动作：${parsed(descriptor).name}`);
    if (base.canInvoke?.(descriptor, trigger) === false) return;
    const {name, value} = parsed(descriptor);
    const action = name === 'account-action' ? value as AccountAction : own(bulkActions, name) ? bulkActions[name] : undefined;
    const details = action ? accountActions[action] : undefined;
    let key: string | undefined, restore: (() => void) | undefined, retryIds: readonly string[] = [], submissionConfirmed = false;
    let errorPrefix = details ? `${details.label}失败: ` : name.includes('setup') || name === 'setupSelectedAccounts' ? '补齐账号配置失败: '
      : name === 'codex-stop' ? '停止失败: ' : name === 'codex-reset-retrying' ? '重置失败: ' : name === 'codex-retry' ? '触发补跑失败: '
      : name === 'stopSelectedCodex' ? '停止选中补跑失败: ' : name === 'retrySelectedCodex' ? '批量补跑失败: '
      : name === 'uploadSelectedCodexSub2' ? '批量上传 sub2 失败: ' : '注册重跑提交失败: ';
    try {
      const context = snapshot(supplied), ids = context.accountIds.map(Number), id = ids[0];
      if (!ids.length) {base.notify('请先选择账号'); return;}
      if (isSingle(name) && ids.length !== 1) throw new Error('此操作只能选择一个账号');
      const row = context.rowHints.find(item => String(item.id) === String(id));
      const email = context.expectedEmails[String(id)] || row?.email || '';
      const labelEmail = row?.email || email || `账号 #${id}`;
      if (name === 'account-registration-task') {await openRegistrationTasks([{account_id: id, email, job_id: Number(value)}], context); return;}
      if (isRetry(name) && context.accountIds.some(value => retryPending.has(value))) {base.notify('所选账号的注册重跑正在提交，请稍后查看结果'); return;}
      key = keyFor(descriptor, context.accountIds);
      if (pending.has(key)) {key = undefined; return;}
      pending.add(key);
      // Capture the account-level retry guard before an asynchronous confirmation opens a duplicate path.
      if (isRetry(name)) {retryIds = context.accountIds; retryIds.forEach(value => retryPending.add(value));}
      if (action && !isSingle(name) && ['password_change', 'twofa_change'].includes(action) && ids.length > 20) {
        base.notify('修改密码或修改 2FA 单次最多操作 20 个账号'); return;
      }
      let confirmation: string;
      if (name === 'account-setup') confirmation = `补齐账号配置？\n\n${labelEmail}\n\n只执行账号密码、套餐查询和 Authenticator 2FA，不执行 Codex 授权。`;
      else if (name === 'setupSelectedAccounts') confirmation = `确定补齐选中的 ${ids.length} 个账号配置吗？\n\n只执行：账号密码、套餐查询、Authenticator 2FA。\n不会执行 Codex 授权。`;
      else if (details) confirmation = isSingle(name) ? `${details.label}？\n\n${labelEmail}` : `确定${details.label}选中的 ${ids.length} 个账号吗？`;
      else if (name === 'codex-stop') confirmation = `确定停止该账号的 Codex 补跑吗？\n\n${email}\n\n会发送停止信号并将状态标记为“已停止”。`;
      else if (name === 'codex-reset-retrying') confirmation = `确定重置该账号的 Codex「补跑中」状态吗？\n\n${email}\n\n重置后状态会变为“失败”，可再次点击“补跑 Codex”。`;
      else if (name === 'codex-retry') confirmation = `重新跑 Codex 授权？\n\n${email}\n\n按实际验证要求使用邮箱 OTP（自动收）。手机接码仅在开关开启且遇到手机验证时使用；关闭后遇到手机验证会报错退出。\n\n补跑会在后台进行，完成后状态自动更新。`;
      else if (name === 'stopSelectedCodex') confirmation = `确定停止选中的 ${ids.length} 个账号的 Codex 补跑吗？\n\n会向正在补跑的任务发送停止信号，并将状态标记为“已停止”；未在补跑的账号会自动跳过。`;
      else if (name === 'retrySelectedCodex') confirmation = `批量补跑选中的 ${ids.length} 个账号 Codex 授权？\n\n并发线程数：${deps.operationWorkers()}\n\n按实际验证要求使用邮箱 OTP。手机接码仅在开关开启且遇到手机验证时使用；关闭后遇到手机验证会报错退出。\n\n补跑中和已废号账号会自动跳过。`;
      else if (name === 'uploadSelectedCodexSub2') confirmation = `确定上传选中的 ${ids.length} 个账号的 Codex OAuth 凭证到 sub2api 吗？\n\n未完成 Codex OAuth 的账号会自动跳过。`;
      else confirmation = `确定为${ids.length === 1 ? `账号 #${id}` : `选中的 ${ids.length} 个账号`}${ids.length === 1 ? row?.registration_retry?.label || '重跑原注册任务' : '重跑原注册任务'}吗？\n\n复用原注册记录，按当前进度重跑或补齐缺失步骤。正在执行、已完成或没有原任务的账号会显示对应结果。`;
      if (!await base.confirm(confirmation)) return;
      restore = base.beginBusy?.(descriptor, trigger, isRetry(name) ? '提交中…' : name === 'uploadSelectedCodexSub2' ? '提交上传…' : undefined) || undefined;
      const post = async (path: string, body: object) => {
        const result = record(await base.request(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}), true);
        submissionConfirmed = true; return result;
      };
      if (name === 'account-setup' || name === 'setupSelectedAccounts') {
        const single = name === 'account-setup', result = await post(single ? `/api/accounts/${id}/setup` : '/api/accounts/setup-bulk', single ? {} : {account_ids: ids});
        const skipped = entries(result.skipped).length;
        base.notify(single ? String(result.message || '已开始补齐账号配置') : skipped ? `已开始补齐 ${count(result.started_count)} 个，跳过 ${skipped} 个` : `已开始补齐 ${count(result.started_count)} 个账号配置`);
        await refreshAndOpen(context, {filters: {target: single ? labelEmail : '', type: 'account_setup_retry'}});
      } else if (action && details) {
        const single = name === 'account-action', result = await post(single ? `/api/accounts/${id}/action` : '/api/accounts/action-bulk', single ? {action} : {account_ids: ids, action});
        const skipped = entries(result.skipped).length, started = entries(result.started);
        base.notify(single ? String(result.message || `${details.label}已入队`) : skipped ? `已开始 ${count(result.started_count)} 个，跳过 ${skipped} 个` : String(result.message || `${details.label}已入队`));
        const resume = single ? !!result.registration_resume : started.length > 0 && started.every(item => item.registration_resume);
        await refreshAndOpen(context, {filters: single ? {target: labelEmail, type: resume ? 'registration_resume' : details.type} : {type: resume ? 'registration_resume' : details.type}});
      } else if (name.startsWith('codex-')) {
        const endpoint = name === 'codex-stop' ? 'stop' : name === 'codex-reset-retrying' ? 'reset-retrying' : 'retry';
        const result = await post(`/api/codex/${endpoint}`, name === 'codex-reset-retrying' ? {email, status: 'failed'} : {email});
        base.notify(String(result.message || (name === 'codex-stop' ? '已发送停止信号' : name === 'codex-reset-retrying' ? '已重置补跑状态' : '已开始补跑')));
        await refreshAndOpen(context, name === 'codex-retry' ? {filters: {target: email, type: 'codex_retry'}} : undefined);
      } else if (name === 'stopSelectedCodex' || name === 'retrySelectedCodex') {
        const stop = name === 'stopSelectedCodex', result = await post(`/api/codex/${stop ? 'stop' : 'retry'}-bulk`, {account_ids: ids});
        const skipped = entries(result.skipped).length;
        base.notify(stop ? `已停止 ${count(result.stopped_count)} 个${skipped ? `，跳过 ${skipped} 个` : ''}`
          : skipped ? `已开始 ${count(result.started_count)} 个，跳过 ${skipped} 个` : String(result.message || '已开始批量补跑'));
        await refreshAndOpen(context, stop ? undefined : {filters: {target: '', type: 'codex_retry'}});
      } else if (name === 'uploadSelectedCodexSub2') {
        const result = await post('/api/accounts/codex/upload-sub2-bulk', {account_ids: ids}), skipped = count(result.skipped_count??entries(result.skipped).length) + count(result.failed_count??entries(result.failed).length);
        const reasons=skipped?accountBulkUnqueuedReasons(result):'';
        if (result.accepted) {
          base.notify(`手动上传已入队 ${count(result.queued_count??entries(result.queued).length)} 个，未入队 ${skipped} 个，请在任务中心查看结果${reasons}`);
        } else {
          base.notify(`已上传 ${count(result.uploaded_count)} 个${skipped ? `，跳过/失败 ${skipped} 个${reasons}` : ''}`);
          await pageUpdate(() => deps.pollStatuses(context));
        }
      } else if (isRetry(name)) {
        const result = await post(ids.length === 1 ? `/api/accounts/${id}/registration-retry` : '/api/accounts/registration-retry-bulk', ids.length === 1 ? {} : {account_ids: ids});
        const receipt = retryReceipt(result);
        base.notify(retrySummary(receipt));
        deps.showRegistrationResult(receipt, context, items => openRegistrationTasks(items, context));
        if (ids.length === 1) {
          const first = receipt.started[0] || receipt.reused[0];
          if (first) await openRegistrationTasks([first], context);
        }
        await deps.refresh(context);
      }
    } catch (cause) {
      if (submissionConfirmed) errorPrefix = isRetry(name) ? '注册重跑请求已处理，页面更新失败: ' : '请求已处理，但页面更新失败: ';
      base.notify(errorPrefix + message(cause));
    } finally {
      if (key) pending.delete(key);
      retryIds.forEach(value => retryPending.delete(value));
      restore?.();
    }
  }
  return {isSupported, invoke, isPending: (descriptor: string, context: AccountActionContext) => isRetry(parsed(descriptor).name)
    ? context.accountIds.some(id => retryPending.has(id)) : pending.has(keyFor(descriptor, context.accountIds))};
}
