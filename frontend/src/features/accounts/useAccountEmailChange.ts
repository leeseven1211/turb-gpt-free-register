import {computed, onScopeDispose, ref, shallowRef} from 'vue';
import type {AccountActionContext} from './useAccounts';

export interface EmailChangeSource {value: string; label: string; enabled: boolean; reason: string}
export interface EmailChangeAccount {id: number; email: string; email_source: string}
export interface AccountEmailChangeDependencies {
  request(path: string, options?: RequestInit): Promise<unknown>;
  notify(message: string): void;
  refreshAccounts(context: AccountActionContext): void | Promise<unknown>;
  openTasks(filters: {target: string; type: 'email_change'}): void | Promise<unknown>;
  syncModalScrollLock(): void;
  fallbackFocus?(): HTMLElement | null;
}
export interface EmailChangeLifecycle {
  opened?(generation: number): void;
  sourcesReady?(generation: number): void;
  closed?(restoreFocus: boolean, trigger: HTMLElement | null, generation: number): void;
}

interface Opening {
  generation: number;
  mode: 'single' | 'bulk';
  account: EmailChangeAccount | null;
  accountIds: readonly string[];
  context: AccountActionContext;
  trigger: HTMLElement | null;
  controller: AbortController;
  submitting: boolean;
}
function copy<T>(value: T): T { return JSON.parse(JSON.stringify(value)) as T; }
function freeze<T>(value: T): T {
  if (value && typeof value === 'object') {Object.values(value).forEach(freeze); Object.freeze(value);}
  return value;
}
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('服务端响应格式无效');
  const data = value as Record<string, unknown>;
  if (data.ok === false) throw new Error(typeof data.error === 'string' ? data.error : '请求失败');
  return data;
}
function message(error: unknown): string {
  return error && typeof error === 'object' && 'message' in error ? String(error.message) : '请求失败，请稍后重试';
}
function idsFrom(context: AccountActionContext): string[] {
  return [...new Set((Array.isArray(context?.accountIds) ? context.accountIds : [])
    .map(Number).filter(id => Number.isSafeInteger(id) && id > 0).map(String))];
}

/** Each opening has independent UI state; accepted POST receipts outlive that UI. */
export function useAccountEmailChange(deps: AccountEmailChangeDependencies, lifecycle: EmailChangeLifecycle = {}) {
  const isOpen = ref(false), generation = ref(0), mode = ref<'single' | 'bulk'>('single');
  const account = shallowRef<EmailChangeAccount | null>(null), context = shallowRef<AccountActionContext | null>(null);
  const accountIds = shallowRef<readonly string[]>([]), sources = shallowRef<readonly EmailChangeSource[]>([]);
  const source = ref(''), sourceStatus = ref<'idle' | 'loading' | 'ready' | 'failed'>('idle'), error = ref(''), submitting = ref(false);
  const sourceDisabled = computed(() => sourceStatus.value !== 'ready' || !sources.value.some(item => item.enabled));
  let opening: Opening | null = null, disposed = false;
  const current = (session: Opening) => !disposed && opening === session && generation.value === session.generation && isOpen.value;
  function close({restoreFocus = true}: {restoreFocus?: boolean} = {}) {
    const previous = opening;
    if (!previous) return;
    opening = null;
    ++generation.value;
    previous.controller.abort();
    isOpen.value = false; account.value = null; context.value = null; accountIds.value = [];
    sources.value = []; source.value = ''; sourceStatus.value = 'idle'; error.value = ''; submitting.value = false;
    lifecycle.closed?.(restoreFocus, previous.trigger, generation.value);
  }
  async function loadSources(session: Opening, preferred: string) {
    try {
      const data = record(await deps.request('/api/email-sources', {signal: session.controller.signal}));
      if (!current(session)) return;
      sources.value = freeze((Array.isArray(data.sources) ? data.sources : []).map(raw => {
        const item = record(raw);
        return {value: String(item.value || ''), label: String(item.label || item.value || ''), enabled: Boolean(item.enabled), reason: String(item.reason || '')};
      }));
      const enabled = sources.value.filter(item => item.enabled);
      source.value = (enabled.find(item => item.value === preferred) || enabled[0])?.value || '';
      sourceStatus.value = 'ready';
      error.value = enabled.length ? '' : '没有已配置且可用的新邮箱来源';
    } catch (cause) {
      if (!current(session)) return;
      sourceStatus.value = 'failed'; sources.value = []; source.value = '';
      error.value = `邮箱来源读取失败：${message(cause)}`;
    }
    if (current(session)) lifecycle.sourcesReady?.(session.generation);
  }
  function begin(kind: 'single' | 'bulk', ids: string[], snapshot: EmailChangeAccount | null, supplied: AccountActionContext, trigger: HTMLElement | null) {
    if (disposed) return false;
    const captured = freeze(copy({...supplied, accountIds: ids}));
    close({restoreFocus: false});
    const session: Opening = {generation: ++generation.value, mode: kind, account: snapshot, accountIds: freeze([...ids]),
      context: captured, trigger, controller: new AbortController(), submitting: false};
    opening = session;
    mode.value = kind; account.value = snapshot; accountIds.value = session.accountIds; context.value = captured;
    isOpen.value = true; sourceStatus.value = 'loading'; source.value = ''; error.value = ''; sources.value = []; submitting.value = false;
    lifecycle.opened?.(session.generation);
    void loadSources(session, String(snapshot?.email_source || '').trim().toLowerCase());
    return true;
  }
  function openSingle(id: string | number, supplied: AccountActionContext, trigger: HTMLElement | null = null) {
    const numeric = Number(id), key = String(numeric);
    const row = supplied?.rowHints?.find(item => String(item.id) === key);
    if (!Number.isSafeInteger(numeric) || numeric <= 0 || !idsFrom(supplied).includes(key) || !row) {
      deps.notify('账号详情暂不可用，请先刷新列表'); return false;
    }
    return begin('single', [key], freeze({id: numeric, email: String(row.email || ''), email_source: String(row.email_source || '')}), supplied, trigger);
  }
  function openBulk(supplied: AccountActionContext, trigger: HTMLElement | null = null) {
    const ids = idsFrom(supplied);
    if (!ids.length) {deps.notify('请先选择账号'); return false;}
    if (ids.length > 500) {deps.notify('单次最多换绑 500 个账号'); return false;}
    return begin('bulk', ids, null, supplied, trigger);
  }
  function followup(callback: () => void | Promise<unknown>, prefix: string) {
    try {void Promise.resolve(callback()).catch(cause => deps.notify(prefix + message(cause)));}
    catch (cause) {deps.notify(prefix + message(cause));}
  }
  async function submit() {
    const session = opening;
    if (!session || !current(session) || session.submitting) return;
    const selectedSource = source.value;
    if (sourceStatus.value !== 'ready' || !selectedSource || !sources.value.some(item => item.value === selectedSource && item.enabled)) {
      error.value = '请选择新邮箱来源'; return;
    }
    error.value = ''; submitting.value = true; session.submitting = true;
    let result: Record<string, unknown>;
    try {
      result = record(await deps.request(session.mode === 'bulk' ? '/api/accounts/email-change-bulk' : `/api/accounts/${session.account!.id}/email-change`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(session.mode === 'bulk' ? {account_ids: session.accountIds.map(Number), email_source: selectedSource} : {email_source: selectedSource}),
      }));
    } catch (cause) {
      if (current(session)) error.value = `提交失败：${message(cause)}`;
      deps.notify('换绑邮箱失败: ' + message(cause));
      return;
    } finally {
      session.submitting = false;
      if (current(session)) submitting.value = false;
    }
    const wasCurrent = current(session);
    if (session.mode === 'bulk') {
      const started = Number(result.started_count || 0), skipped = Number(result.skipped_count || 0);
      deps.notify(`批量换绑已入队 ${started} 个${skipped ? `，跳过 ${skipped} 个` : ''}`);
    } else deps.notify(String(result.message || `邮箱换绑已入队 · 任务 #${result.task_id || '-'}`));
    if (wasCurrent) close({restoreFocus: false});
    followup(() => deps.refreshAccounts(session.context), '换绑已受理，刷新账号失败：');
    // A newer opening, even for the same account, keeps its form and focus.
    if (wasCurrent && !disposed && !opening) {
      followup(() => deps.openTasks({target: session.mode === 'bulk' ? '' : session.account!.email || `#${session.account!.id}`, type: 'email_change'}), '换绑已受理，打开任务失败：');
    }
  }
  onScopeDispose(() => {disposed = true; close();});
  return {isOpen, generation, mode, account, context, accountIds, sources, source, sourceStatus, sourceDisabled, error, submitting,
    openSingle, openBulk, close, submit};
}
