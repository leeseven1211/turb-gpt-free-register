import {readonly, shallowRef} from 'vue';
import {ApiError} from '../../api/client';
import {optionalTaskId, taskId, type TaskId} from '../../api/taskIds';
import type {AccountActionDependencies} from './actions';

export const accountRequestKeyHeader = 'X-Account-Request-Key';
const storageKey = 'turb_account_operation_receipts';
const requestKeyPattern = /^(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})$/;
const waitMs = 10000;

interface RequestReference {key: string; label: string; count: number; submittedAt: number}
interface TaskReference {task_id: TaskId; run_id: TaskId | null}
interface ReceiptEntry extends RequestReference {items: TaskReference[]; message: string; loading: boolean}

function readStored(): RequestReference[] {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(storageKey) || '[]');
    if (!Array.isArray(value)) return [];
    return value.filter((item): item is RequestReference => item && typeof item === 'object'
      && typeof item.key === 'string' && requestKeyPattern.test(item.key)
      && typeof item.label === 'string' && Number.isSafeInteger(item.count) && item.count > 0
      && Number.isSafeInteger(item.submittedAt) && item.submittedAt > 0);
  } catch { return []; }
}

function writeStored(entries: RequestReference[]): void {
  try { sessionStorage.setItem(storageKey, JSON.stringify(entries)); }
  catch { /* 禁用会话存储时仍可在当前页面查询回执。 */ }
}

function receiptEntry(reference: RequestReference): ReceiptEntry {
  return {...reference, items: [], message: '受理结果未确认，可能已入队。', loading: false};
}

export function createAccountOperationReceipts(
  base: Pick<AccountActionDependencies, 'request' | 'now' | 'notify'>,
  showTask: (task: TaskId, run: TaskId | null) => void | Promise<unknown>,
) {
  const entries = shallowRef(readStored().map(receiptEntry));
  const update = (key: string, changes: Partial<ReceiptEntry>) => {
    entries.value = entries.value.map(entry => entry.key === key ? {...entry, ...changes} : entry);
  };
  function dismiss(key: string): void {
    entries.value = entries.value.filter(entry => entry.key !== key);
    writeStored(readStored().filter(item => item.key !== key));
  }
  async function submit(
    label: string,
    count: number,
    send: (key: string) => Promise<Record<string, unknown>>,
  ): Promise<Record<string, unknown> | undefined> {
    const key = crypto.randomUUID?.() ?? Array.from(crypto.getRandomValues(new Uint8Array(16)),
      byte => byte.toString(16).padStart(2, '0')).join('');
    const reference = {key, label, count, submittedAt: base.now().getTime()};
    writeStored([reference, ...readStored()]);
    // 页面仅限制等待回执的时间，原请求继续由服务端处理。
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const deadline = new Promise<never>((_resolve, reject) => {
        timer = setTimeout(() => reject(new Error('等待受理超时')), waitMs);
      });
      const result = await Promise.race([send(key), deadline]);
      dismiss(key);
      return result;
    } catch (cause) {
      if (cause instanceof ApiError && (cause.unavailableFeature
        || (cause.status >= 400 && cause.status < 500 && cause.status !== 408))) {
        dismiss(key);
        throw cause;
      }
      entries.value = [receiptEntry(reference), ...entries.value];
      const detail = cause instanceof ApiError ? `。${cause.message}` : '';
      base.notify(`${label}受理结果未确认，可在账号页查询回执${detail}`);
      return undefined;
    } finally { clearTimeout(timer); }
  }
  async function lookup(key: string): Promise<void> {
    const entry = entries.value.find(item => item.key === key);
    if (!entry || entry.loading) return;
    update(key, {loading: true});
    try {
      const result = await base.request('/api/accounts/operation-receipt', {
        method: 'GET', cache: 'no-store', headers: {[accountRequestKeyHeader]: key},
      }) as {ok?: boolean; found?: boolean; items?: Record<string, unknown>[]};
      if (result?.ok !== true || typeof result.found !== 'boolean' || !Array.isArray(result.items)
        || result.found !== (result.items.length > 0)) throw new Error('回执格式无效');
      const items = result.items.map(item => ({task_id: taskId(item.task_id), run_id: optionalTaskId(item.run_id)}));
      update(key, {items, message: items.length
        ? `当前查到 ${items.length} 条任务回执`
        : '暂未查到任务回执，原请求可能仍在处理中。'});
    } catch (cause) {
      update(key, {message: `回执查询失败：${cause instanceof Error ? cause.message : '请稍后再查'}`});
    } finally { update(key, {loading: false}); }
  }
  async function open(item: TaskReference): Promise<void> {
    try { await showTask(item.task_id, item.run_id); }
    catch (cause) { base.notify(`打开任务失败：${cause instanceof Error ? cause.message : '请稍后重试'}`); }
  }
  return {submit, view: {entries: readonly(entries), lookup, open, dismiss}};
}

export type AccountOperationReceiptsView = ReturnType<typeof createAccountOperationReceipts>['view'];
