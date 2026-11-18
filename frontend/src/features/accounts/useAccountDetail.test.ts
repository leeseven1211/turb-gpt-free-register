import {describe, expect, it, vi} from 'vitest';
import type {AccountPlanDetailsSnapshot, AccountViewRow} from './useAccounts';
import type {AccountRoxyProfileResponse} from '../../api/accountDetail';
import {accountRow, deferred} from './uiTestSupport';
import {useAccountDetail, type PlanDetailsConsumer} from './useAccountDetail';

async function settle() { for (let n = 0; n < 8; n++) await Promise.resolve(); }
function lease(generation = 1) {
  const wait = deferred<AccountPlanDetailsSnapshot>();
  void wait.promise.catch(() => {});
  return {wait, openGeneration: generation, loadPlanDetails: vi.fn(() => wait.promise), release: vi.fn()};
}
function result(id = '7'): AccountPlanDetailsSnapshot {
  return {accountId: id, revision: 'v1', item: {account_promotions: [], promotion_query_snapshot: null, plan_check_country_results: []}};
}
function setup() {
  const roxy: {id: string; signal?: AbortSignal; wait: ReturnType<typeof deferred<AccountRoxyProfileResponse>>}[] = [];
  const api = {roxyProfile: vi.fn((id: string, signal?: AbortSignal) => {
    const wait = deferred<AccountRoxyProfileResponse>(); roxy.push({id, signal, wait}); return wait.promise;
  })};
  const callbacks = {notify: vi.fn(), opened: vi.fn(), closed: vi.fn()};
  return {owner: useAccountDetail(api, callbacks), api, roxy, callbacks};
}

describe('账号详情 opening owner', () => {
  it('复制冻结公开快照并按现有 lease generation 先读计划后读 Roxy', async () => {
    const f = setup(), l = lease(19);
    const fingerprint = Object.freeze({browser: 'chrome', language: 'en'});
    const row = Object.freeze({...accountRow(7), fingerprint_summary: fingerprint});
    expect(f.owner.open('7', row, l, null)).toBe(true);
    expect(f.owner.account.value).toMatchObject({id: 7, roxy_profile_id: '', roxy_profile_name: ''});
    expect(f.owner.account.value).not.toBe(row);
    expect(f.owner.account.value?.fingerprint_summary).not.toBe(fingerprint);
    expect(l.loadPlanDetails).toHaveBeenCalledExactlyOnceWith('7', 19);
    expect(f.api.roxyProfile).not.toHaveBeenCalled();
    const details = result(); l.wait.resolve(details); await settle();
    expect(f.owner.account.value?.account_promotions).toEqual([]);
    expect(f.owner.account.value?.account_promotions).not.toBe(details.item.account_promotions);
    expect(f.roxy).toHaveLength(1); expect(f.roxy[0].id).toBe('7');
    f.roxy[0].wait.resolve({ok: true, profile_id: ' p7 ', window_name: ' window7 '}); await settle();
    expect(f.owner.account.value).toMatchObject({roxy_profile_id: 'p7', roxy_profile_name: 'window7'});
    expect(row).not.toHaveProperty('roxy_profile_id'); expect(row).not.toHaveProperty('account_promotions');
  });

  it('关闭再开同 ID 后旧 plan 成功不能更新新 opening 或发 Roxy', async () => {
    const f = setup(), first = lease(), second = lease(2);
    f.owner.open('7', accountRow(7, {email: 'first@example.test'}), first, null);
    f.owner.close(); f.owner.close();
    expect(first.release).toHaveBeenCalledTimes(1);
    f.owner.open('7', accountRow(7, {email: 'second@example.test'}), second, null);
    first.wait.resolve(result()); await settle();
    expect(f.owner.account.value?.email).toBe('second@example.test');
    expect(f.api.roxyProfile).not.toHaveBeenCalled();
    second.wait.resolve(result()); await settle(); expect(f.roxy).toHaveLength(1);
    expect(second.release).not.toHaveBeenCalled();
  });

  it.each(['resolve', 'reject'] as const)('关闭时取消 Roxy，迟到 %s 不影响同 ID 新 opening', async outcome => {
    const f = setup(), first = lease(), second = lease(2);
    f.owner.open('7', accountRow(7), first, null); first.wait.resolve(result()); await settle();
    f.owner.open('7', accountRow(7), second, null);
    expect(f.roxy[0].signal?.aborted).toBe(true); expect(first.release).toHaveBeenCalledTimes(1);
    second.wait.resolve(result()); await settle();
    f.roxy[1].wait.resolve({ok: true, profile_id: 'new', window_name: 'current'}); await settle();
    if (outcome === 'resolve') f.roxy[0].wait.resolve({ok: true, profile_id: 'old', window_name: 'old'});
    else f.roxy[0].wait.reject(new Error('late'));
    await settle(); expect(f.owner.account.value?.roxy_profile_id).toBe('new');
    expect(f.callbacks.notify).not.toHaveBeenCalled();
  });

  it('current plan 错误保留快照并提示重开，关闭后的错误保持静默', async () => {
    const f = setup(), first = lease();
    f.owner.open('7', accountRow(7), first, null); first.wait.reject(new Error('offline')); await settle();
    expect(f.owner.isOpen.value).toBe(true); expect(f.owner.account.value?.id).toBe(7);
    expect(f.callbacks.notify).toHaveBeenCalledExactlyOnceWith('优惠详情加载失败，请重新打开详情重试');
    expect(f.api.roxyProfile).not.toHaveBeenCalled();
    const second = lease(2); f.owner.open('7', accountRow(7), second, null); f.owner.close();
    second.wait.reject(new Error('late')); await settle();
    expect(f.callbacks.notify).toHaveBeenCalledTimes(1);
  });

  it('AbortError 不提示、不继续读 Roxy', async () => {
    const f = setup(), l = lease(); f.owner.open('7', accountRow(7), l, null);
    l.wait.reject(new DOMException('cancelled', 'AbortError')); await settle();
    expect(f.callbacks.notify).not.toHaveBeenCalled(); expect(f.api.roxyProfile).not.toHaveBeenCalled();
  });

  it.each([{accountId: '8', item: {}}, {accountId: '7', item: []}, {accountId: '7', item: {id: 8}}, null])(
    '错误 account/item %# 不能覆盖本次快照', async payload => {
      const f = setup(), l = lease(); f.owner.open('7', accountRow(7), l, null);
      l.wait.resolve(payload as unknown as AccountPlanDetailsSnapshot); await settle();
      expect(f.owner.account.value?.id).toBe(7); expect(f.api.roxyProfile).not.toHaveBeenCalled();
      expect(f.callbacks.notify).toHaveBeenCalledExactlyOnceWith('优惠详情加载失败，请重新打开详情重试');
    });

  it('Roxy 失败只使本次 profile 保持未记录', async () => {
    const f = setup(), l = lease();
    f.owner.open('7', {...accountRow(7), roxy_profile_id: 'cached'} as AccountViewRow, l, null);
    l.wait.resolve(result()); await settle(); f.roxy[0].wait.reject(new Error('Roxy unavailable')); await settle();
    expect(f.owner.account.value).toMatchObject({roxy_profile_id: '', roxy_profile_name: ''});
    expect(f.owner.isOpen.value).toBe(true); expect(f.callbacks.notify).not.toHaveBeenCalled();
  });

  it('无效输入只释放新 lease，不关闭原 opening', () => {
    const f = setup(), first = lease(), invalid = lease(2);
    f.owner.open('7', accountRow(7), first, null);
    expect(f.owner.open('8', accountRow(9), invalid, null)).toBe(false);
    expect(invalid.release).toHaveBeenCalledTimes(1); expect(first.release).not.toHaveBeenCalled();
    expect(f.owner.accountId.value).toBe('7'); expect(f.owner.isOpen.value).toBe(true);
    expect(f.callbacks.notify).toHaveBeenCalledExactlyOnceWith('账号详情暂不可用，请先刷新列表');
    expect(f.owner.open('7', accountRow(7), null as unknown as PlanDetailsConsumer, null)).toBe(false);
    expect(first.release).not.toHaveBeenCalled();
  });

  it('替换只释放旧 lease且传递不恢复焦点，关闭幂等', () => {
    const f = setup(), first = lease(), second = lease(2), trigger = document.createElement('button');
    f.owner.open('7', accountRow(7), first, trigger);
    f.owner.open('8', accountRow(8), second, null);
    expect(first.release).toHaveBeenCalledTimes(1); expect(second.release).not.toHaveBeenCalled();
    expect(f.callbacks.closed).toHaveBeenCalledWith(false, trigger, expect.any(Number));
    f.owner.close(); f.owner.close();
    expect(second.release).toHaveBeenCalledTimes(1); expect(f.callbacks.closed).toHaveBeenCalledTimes(2);
    expect(f.owner.account.value).toBeNull(); expect(f.owner.isOpen.value).toBe(false);
  });
});
