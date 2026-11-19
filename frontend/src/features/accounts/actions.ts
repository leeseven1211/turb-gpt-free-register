import type {AccountActionContext} from './useAccounts';
import {createQueuedAccountActions, type AccountQueuedDependencies} from './queuedActions';
import {createAccountSetupActions, type AccountSetupDependencies} from './setupActions';
import {createLocalAccountMutations, type LocalAccountMutationDependencies} from './localMutations';

/** UI/browser capabilities are injected; this owner never reads legacy selection or row secrets. */
export interface AccountActionDependencies {
  queued?: AccountQueuedDependencies;
  setup?: AccountSetupDependencies;
  local?: Omit<LocalAccountMutationDependencies, 'request' | 'notify' | 'confirm' | 'canInvoke' | 'beginBusy'>;
  request(path: string, options?: RequestInit): Promise<unknown>;
  notify(message: string): void;
  confirm(message: string): boolean | Promise<boolean>;
  clipboard(text: string, showFeedback?: boolean): Promise<boolean>;
  downloadBlob(blob: Blob, filename: string): void | Promise<void>;
  downloadUrl(url: string, filename: string): void | Promise<void>;
  now(): Date;
  schedule(callback: () => void, delay: number): unknown;
  reloadCodex(): void | Promise<unknown>;
  /** The integration owns capability/disabled checks without exposing DOM state to the action. */
  canInvoke?(descriptor: string, trigger: HTMLElement | null): boolean;
  /** Returns an idempotent restorer that re-evaluates current UI eligibility, including empty selection. */
  beginBusy?(descriptor: string, trigger: HTMLElement | null, label?: string): (() => void) | void;
}
export interface AccountActionDispatcher {
  setVisible(visible: boolean): void;
  dispose(): void;
  isSupported(descriptor: string): boolean;
  isPending(descriptor: string, context: AccountActionContext): boolean;
  invoke(descriptor: string, context: AccountActionContext, trigger?: HTMLElement | null): Promise<void>;
}
interface BulkCopy {
  field: string;
  empty: string;
  success(count: number): string;
  error: string;
  feedback?: false;
  copyFailed?: string;
}
const bulkCopies: Readonly<Record<string, BulkCopy>> = {
  copySelectedAccountTokens: {field: 'access_token', empty: '选中账号没有可复制 Token', success: n => `已复制 ${n} 个 Token`, error: '复制失败: '},
  copySelectedAccountLines: {field: 'account_credentials_line', empty: '选中账号没有可复制整行', success: n => `已复制 ${n} 行`, error: '复制失败: '},
  copySelectedAccountEmails: {field: 'email', empty: '选中账号没有可复制的邮箱', success: n => `已复制 ${n} 个邮箱`, error: '复制邮箱失败: ', feedback: false, copyFailed: '复制邮箱失败'},
  copySelectedAccountExtractLinks: {field: 'extract_link', empty: '选中账号没有成功提炼地址', success: n => `已复制 ${n} 个提炼地址`, error: '复制提炼地址失败: ', feedback: false, copyFailed: '复制提炼地址失败'},
  copySelectedAccountPasswords: {field: 'account_password_line', empty: '选中账号均未在本地保存密码', success: n => `已复制 ${n} 个账号密码；本地未保存密码的账号已跳过`, error: '复制密码失败: '},
  copySelectedAccountTotpSecrets: {field: 'totp_secret', empty: '选中账号没有已设置的 2FA 密钥', success: n => `已复制 ${n} 个 2FA 密钥；未设置 2FA 的账号已跳过`, error: '复制 2FA 失败: '},
};
const secretLabels: Readonly<Record<string, string>> = {
  copy_line: '账号整行已复制', chatgpt_session: 'ChatGPT session 已复制', account_password: '账号密码已复制', totp_secret: 'TOTP 密钥已复制', access_token: 'Token 已复制',
};
const downloadErrors: Readonly<Record<string, string>> = {
  downloadSelectedAccountTxt: '生成 TXT 失败: ', downloadSelectedAccountSessions: '下载 Session 失败: ', downloadSelectedCpa: '下载 CPA 失败: ',
};
const own = (value: object, key: string) => Object.prototype.hasOwnProperty.call(value, key);
function splitDescriptor(descriptor: string): {name: string; value: string; hasValue: boolean} {
  const separator = descriptor.indexOf(':');
  return separator < 0 ? {name: descriptor, value: '', hasValue: false}
    : {name: descriptor.slice(0, separator), value: descriptor.slice(separator + 1), hasValue: true};
}
function isSupported(descriptor: string): boolean {
  const {name, value, hasValue} = splitDescriptor(descriptor);
  if (name === 'account-copy-secret') return hasValue && own(secretLabels, value);
  return !hasValue && (name === 'account-totp-copy' || own(bulkCopies, name) || own(downloadErrors, name));
}
function responseObject(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('服务端响应格式无效');
  const result = value as Record<string, unknown>;
  if (result.ok === false) throw new Error(typeof result.error === 'string' ? result.error : '请求失败');
  return result;
}
/** Preserve the legacy falsy-value filter; reject malformed truthy values instead of copying objects. */
function secretValue(value: unknown): string {
  if (!value) return '';
  if (typeof value !== 'string') throw new Error('服务端响应格式无效');
  return value;
}
function count(value: unknown): number {
  const number = Number(value || 0);
  if (!Number.isFinite(number) || !Number.isInteger(number) || number < 0) throw new Error('服务端响应格式无效');
  return number;
}
function downloadReference(result: Record<string, unknown>): {url: string; filename: string} {
  if (result.download_url == null || result.download_url === '') throw new Error('服务端未返回下载地址');
  if (typeof result.download_url !== 'string' || (result.filename != null && typeof result.filename !== 'string')) throw new Error('服务端响应格式无效');
  if (!result.download_url.trim()) throw new Error('服务端未返回下载地址');
  return {url: result.download_url, filename: result.filename as string || ''};
}
function accountIds(context: AccountActionContext): readonly number[] {
  if (!Array.isArray(context?.accountIds)) throw new Error('账号动作上下文不可用，请刷新后重试');
  const ids = context.accountIds.map(id => {
    if (typeof id !== 'string' || !/^[1-9]\d*$/.test(id) || !Number.isSafeInteger(Number(id))) throw new Error('账号 ID 无效');
    return Number(id);
  });
  return Object.freeze([...new Set(ids)]);
}
function message(error: unknown): string {return error instanceof Error ? error.message : '请求失败，请稍后重试。';}

export function createAccountActions(deps: AccountActionDependencies): AccountActionDispatcher {
  const queued = deps.queued ? createQueuedAccountActions(deps, deps.queued) : undefined;
  const setup = deps.setup ? createAccountSetupActions(deps, deps.setup) : undefined;
  const local = deps.local ? createLocalAccountMutations({...deps.local, request: deps.request, notify: deps.notify, confirm: deps.confirm, canInvoke: deps.canInvoke, beginBusy: deps.beginBusy}) : undefined;
  const pending = new Set<string>();
  const keyFor = (descriptor: string, ids: readonly (string | number)[]) => descriptor.startsWith('account-') ? JSON.stringify([descriptor, ...ids.map(String)]) : descriptor;
  const post = async (path: string, body: object) => responseObject(await deps.request(path, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
  }));
  async function secrets(ids: readonly number[], field: string): Promise<string[]> {
    const result = await post('/api/accounts/secret-bulk', {account_ids: ids, field});
    if (!Array.isArray(result.values)) throw new Error('服务端响应格式无效');
    return result.values.map(item => secretValue(responseObject(item).value)).filter(Boolean);
  }
  async function invoke(descriptor: string, context: AccountActionContext, trigger: HTMLElement | null = null): Promise<void> {
    if (queued?.isSupported(descriptor)) return queued.invoke(descriptor, context, trigger);
    if (setup?.isSupported(descriptor)) return setup.invoke(descriptor, context, trigger);
    if (local?.isSupported(descriptor)) return local.invoke(descriptor, context, trigger);
    // Root uses isSupported to route not-yet-migrated actions. There is deliberately no legacy fallback here.
    if (!isSupported(descriptor)) throw new Error(`未支持的账号动作：${splitDescriptor(descriptor).name}`);
    if (deps.canInvoke?.(descriptor, trigger) === false) return;
    const {name, value} = splitDescriptor(descriptor), copy = own(bulkCopies, name) ? bulkCopies[name]! : undefined;
    const errorPrefix = copy?.error ?? downloadErrors[name] ?? (name === 'account-totp-copy' ? '复制验证码失败: ' : '复制失败: ');
    let key: string | undefined, restore: (() => void) | undefined, deferredRelease = false;
    const release = () => {if (key) pending.delete(key); const callback = restore; restore = undefined; callback?.();};
    try {
      // Snapshot before confirmation, API, clipboard or download awaits. No other context field is needed.
      const ids = accountIds(context);
      if (!ids.length) {deps.notify('请先选择账号'); return;}
      if (name.startsWith('account-') && ids.length !== 1) throw new Error('此操作只能选择一个账号');
      key = keyFor(descriptor, ids);
      if (pending.has(key)) {key = undefined; return;}
      pending.add(key);
      if (name === 'downloadSelectedCpa' && !await deps.confirm(`确定从 CPA 下载选中的 ${ids.length} 个账号的 CPA/Codex JSON 吗？\n\n会按账号邮箱匹配 CPA auth-files，成功的文件会打包成 ZIP，缺失文件会写入 manifest 错误清单。`)) return;
      const label = name === 'account-totp-copy' ? '查询中…' : name === 'downloadSelectedAccountSessions' ? '打包中…' : name === 'downloadSelectedCpa' ? '下载中…' : undefined;
      restore = deps.beginBusy?.(descriptor, trigger, label) || undefined;
      deferredRelease = name === 'downloadSelectedCpa';
      if (copy) {
        const values = await secrets(ids, copy.field);
        if (!values.length) {deps.notify(copy.empty); return;}
        const copied = copy.feedback === false ? await deps.clipboard(values.join('\n'), false) : await deps.clipboard(values.join('\n'));
        deps.notify(copy.copyFailed && !copied ? copy.copyFailed : copy.success(values.length));
      } else if (name === 'account-copy-secret') {
        const result = responseObject(await deps.request(`/api/accounts/${ids[0]}/secret?field=${encodeURIComponent(value)}`));
        const text = secretValue(result.value);
        if (!text) {deps.notify('可复制内容为空'); return;}
        await deps.clipboard(text); deps.notify(secretLabels[value]!);
      } else if (name === 'account-totp-copy') {
        const result = responseObject(await deps.request(`/api/accounts/${ids[0]}/totp-code`));
        const code = secretValue(result.code);
        if (!code) throw new Error('验证码为空');
        const remaining = count(result.remaining_seconds), copied = await deps.clipboard(code, false);
        deps.notify(copied ? `验证码已复制，剩余 ${remaining} 秒` : '验证码已查询，但复制失败');
      } else if (name === 'downloadSelectedAccountTxt') {
        const lines = await secrets(ids, 'copy_line');
        if (!lines.length) {deps.notify('选中账号没有可下载整行'); return;}
        const now = deps.now(), pad = (n: number) => String(n).padStart(2, '0');
        const filename = `accounts-selected-${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}.txt`;
        await deps.downloadBlob(new Blob(['\ufeff' + lines.join('\n') + '\n'], {type: 'text/plain;charset=utf-8'}), filename);
        deps.notify(`已下载 ${lines.length} 个账号 TXT`);
      } else if (name === 'downloadSelectedAccountSessions') {
        const result = await post('/api/accounts/download-session-bulk', {account_ids: ids, prepare: true});
        const {url, filename} = downloadReference(result), added = count(result.added_count), skipped = count(result.skipped_count);
        await deps.downloadUrl(url, filename);
        deps.notify(added === 0 ? `没有可下载的 Session，已生成结果清单，跳过 ${skipped} 个；开始下载，分类原因见 ZIP 内 manifest.json；Session 缺失或无效的账号请先刷新 AT，读取失败的账号请重试`
          : `已打包 ${added} 个账号 Session，跳过 ${skipped} 个；开始下载，结果见 ZIP 内 manifest.json`);
      } else if (name === 'downloadSelectedCpa') {
        const result = await post('/api/accounts/download-cpa-bulk', {account_ids: ids, prepare: true});
        const {url, filename} = downloadReference(result), failed = count(result.error_count);
        await deps.downloadUrl(url, filename);
        deps.notify(`已生成 ZIP，开始下载${failed ? `（${failed} 个失败见 manifest）` : ''}`);
        deps.schedule(() => {
          void Promise.resolve().then(() => deps.reloadCodex()).catch(error => deps.notify(`下载已开始，但 Codex 列表刷新失败: ${message(error)}`));
        }, 1200);
      }
    } catch (error) {deps.notify(errorPrefix + message(error));}
    finally {if (deferredRelease) deps.schedule(release, 1200); else release();}
  }
  return {isSupported: descriptor => isSupported(descriptor) || queued?.isSupported(descriptor) === true || setup?.isSupported(descriptor) === true || local?.isSupported(descriptor) === true, invoke,
    isPending: (descriptor, context) => pending.has(keyFor(descriptor, context.accountIds)) || queued?.isPending(descriptor, context) === true || setup?.isPending(descriptor, context) === true || local?.isPending(descriptor, context) === true,
    setVisible: visible => queued?.setVisible(visible), dispose: () => queued?.dispose()};
}
