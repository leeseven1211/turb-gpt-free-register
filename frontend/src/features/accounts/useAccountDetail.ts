import {computed, shallowReadonly, shallowRef} from 'vue';
import type {AccountDetailReadApi} from '../../api/accountDetail';
import type {AccountPlanDetails} from '../../api/accounts';
import type {AccountViewRow, useAccounts} from './useAccounts';

export type PlanDetailsConsumer = ReturnType<ReturnType<typeof useAccounts>['openPlanDetailsConsumer']>;
export type AccountDetailRecord = AccountViewRow & {roxy_profile_id?: string; roxy_profile_name?: string};
export interface AccountDetailPresentation {
  /** A pure, escaped HTML presenter; never raw server HTML or a legacy DOM writer. */
  renderBody(row: AccountDetailRecord): string;
  sourceLabel(value: unknown): string;
}
export interface AccountDetailCallbacks {
  notify(message: string): void;
  syncModalScrollLock(): void;
}
export interface DetailLifecycle {
  notify(message: string): void;
  opened?(generation: number): void;
  closed?(restoreFocus: boolean, trigger: HTMLElement | null, generation: number): void;
}

interface DetailSession {
  id: string;
  generation: number;
  trigger: HTMLElement | null;
  lease: PlanDetailsConsumer;
  roxyAbort: AbortController;
  account: AccountDetailRecord;
}

function copy<T>(value: T): T { return JSON.parse(JSON.stringify(value)) as T; }
function matchingDetails(value: unknown, id: string): AccountPlanDetails {
  if (!value || typeof value !== 'object' || !('accountId' in value) || String(value.accountId) !== id
    || !('item' in value) || !value.item || typeof value.item !== 'object' || Array.isArray(value.item)
    || ('id' in value.item && value.item.id != null && String(value.item.id) !== id)) {
    throw new Error('账号详情响应不匹配');
  }
  return copy(value.item) as AccountPlanDetails;
}

/** One opening owns its copied public data and its existing list-owner lease. */
export function useAccountDetail(api: AccountDetailReadApi, lifecycle: DetailLifecycle) {
  const account = shallowRef<AccountDetailRecord | null>(null);
  const generation = shallowRef(0);
  const isOpen = computed(() => account.value !== null);
  const accountId = computed(() => account.value ? String(account.value.id) : '');
  let session: DetailSession | null = null;
  const current = (opening: DetailSession) => session === opening && generation.value === opening.generation;
  function publish(opening: DetailSession) { account.value = {...opening.account}; }

  async function read(opening: DetailSession) {
    try {
      const result = await opening.lease.loadPlanDetails(opening.id, opening.lease.openGeneration);
      if (!current(opening)) return;
      Object.assign(opening.account, matchingDetails(result, opening.id));
      publish(opening);
    } catch (cause) {
      const aborted = cause && typeof cause === 'object' && 'name' in cause && cause.name === 'AbortError';
      if (current(opening) && !aborted) lifecycle.notify('优惠详情加载失败，请重新打开详情重试');
      return;
    }
    let profileId = '', profileName = '';
    try {
      const result = await api.roxyProfile(opening.id, opening.roxyAbort.signal);
      profileId = String(result.profile_id || '').trim();
      profileName = String(result.window_name || '').trim();
    } catch { /* Roxy is optional; keep this opening's public profile unrecorded. */ }
    if (!current(opening)) return;
    opening.account.roxy_profile_id = profileId;
    opening.account.roxy_profile_name = profileName;
    publish(opening);
  }

  function close(restoreFocus = true) {
    const previous = session;
    if (!previous) return;
    session = null;
    const closedGeneration = ++generation.value;
    account.value = null;
    previous.roxyAbort.abort();
    previous.lease.release();
    lifecycle.closed?.(restoreFocus, previous.trigger, closedGeneration);
  }

  function open(id: string, row: AccountViewRow, lease: PlanDetailsConsumer, trigger: HTMLElement | null) {
    if (!/^[1-9]\d*$/.test(id) || !row || String(row.id) !== id || !lease
      || typeof lease.loadPlanDetails !== 'function' || typeof lease.release !== 'function') {
      lease?.release?.();
      lifecycle.notify('账号详情暂不可用，请先刷新列表');
      return false;
    }
    const snapshot = copy(row);
    close(false);
    const opening: DetailSession = {
      id, generation: ++generation.value, trigger, lease, roxyAbort: new AbortController(),
      account: {...snapshot, roxy_profile_id: '', roxy_profile_name: ''},
    };
    session = opening;
    publish(opening);
    lifecycle.opened?.(opening.generation);
    void read(opening);
    return true;
  }
  return {account: shallowReadonly(account), generation: shallowReadonly(generation), isOpen, accountId, open, close};
}
