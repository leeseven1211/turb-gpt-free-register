import {afterEach, describe, expect, it, vi} from 'vitest';
import {DOMWrapper, flushPromises, mount} from '@vue/test-utils';
import type {VueWrapper} from '@vue/test-utils';
import {nextTick} from 'vue';
import AccountDetail from './AccountDetail.vue';
import type {AccountPlanDetailsSnapshot} from './useAccounts';
import {accountRow, deferred} from './uiTestSupport';
import type {AccountDetailPresentation} from './useAccountDetail';

const mounted: VueWrapper[] = [];
afterEach(() => { for (const w of mounted.splice(0)) w.unmount(); document.body.replaceChildren(); });
function lease() {
  const wait = deferred<AccountPlanDetailsSnapshot>();
  return {wait, openGeneration: 4, loadPlanDetails: vi.fn(() => wait.promise), release: vi.fn()};
}
function setup() {
  const tab = document.createElement('section'); tab.id = 'accounts-tab';
  const host = document.createElement('div'); host.id = 'accountDetailHost'; tab.append(host); document.body.append(tab);
  const trigger = document.createElement('button'); trigger.textContent = '查看账号详情'; tab.prepend(trigger);
  const callbacks = {notify: vi.fn(), syncModalScrollLock: vi.fn()};
  const presentation: AccountDetailPresentation = {
    sourceLabel: value => value === 'outlook' ? 'Outlook' : '',
    renderBody: row => `<div class="account-detail-section"><div class="account-detail-section-title">账号与注册</div><p>账号 #${row.id}</p></div><div class="account-detail-section">健康与安全</div><div class="account-detail-section">最近认证指纹</div><div class="account-detail-section">套餐与授权</div>`,
  };
  const w = mount(AccountDetail, {attachTo: tab, props: {
    api: {roxyProfile: vi.fn().mockResolvedValue({ok: true, profile_id: '', window_name: ''})}, presentation, callbacks,
  }});
  mounted.push(w);
  return {w, trigger, callbacks, tab, body: new DOMWrapper(document.body)};
}

describe('Vue 账号详情 drawer DOM 和焦点', () => {
  it('保留原 shell/标题/正文，Teleport 位于账号页内，打开后焦点在关闭按钮', async () => {
    const {w, trigger, callbacks, body} = setup(), l = lease();
    expect(body.get('#accountDetailDrawer').classes()).toContain('hidden');
    trigger.focus();
    expect(w.vm.open('7', accountRow(7, {email: '<b>safe</b>@example.test', email_source: 'outlook'}), l, trigger)).toBe(true);
    await nextTick();
    const drawer = body.get('#accountDetailDrawer');
    expect(drawer.attributes()).toMatchObject({role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'accountDetailTitle', 'data-account-id': '7'});
    expect(drawer.classes()).not.toContain('hidden');
    expect(drawer.element.parentElement?.id).toBe('accountDetailHost');
    expect(body.get('#accountDetailTitle').text()).toBe('<b>safe</b>@example.test');
    expect(body.get('#accountDetailTitle').find('b').exists()).toBe(false);
    expect(body.get('#accountDetailSubtitle').text()).toBe('账号 #7 · Outlook');
    expect(body.get('#accountDetailBody').findAll('.account-detail-section')).toHaveLength(4);
    expect(body.get('#accountDetailBackdrop').attributes('aria-hidden')).toBe('false');
    expect(document.activeElement?.id).toBe('btnCloseAccountDetail');
    expect(callbacks.syncModalScrollLock).toHaveBeenCalledTimes(1);
    expect(drawer.findAll('button')).toHaveLength(1);
  });

  it.each(['#btnCloseAccountDetail', '#accountDetailBackdrop'])('点击 %s 关闭、释放、回焦点并在 DOM tick 后更新滚动锁', async selector => {
    const {w, trigger, callbacks, body} = setup(), l = lease();
    w.vm.open('7', accountRow(7), l, trigger); await nextTick();
    callbacks.syncModalScrollLock.mockImplementationOnce(() => {
      expect(body.get('#accountDetailDrawer').classes()).toContain('hidden');
    });
    await body.get(selector).trigger('click');
    expect(l.release).toHaveBeenCalledTimes(1);
    expect(document.activeElement).toBe(trigger);
    expect(body.get('#accountDetailBackdrop').attributes('aria-hidden')).toBe('true');
    expect(body.get('#accountDetailDrawer').attributes('data-account-id')).toBeUndefined();
    expect(body.get('#accountDetailBody').text()).toBe('');
    w.vm.close(); await nextTick(); expect(l.release).toHaveBeenCalledTimes(1);
    expect(callbacks.syncModalScrollLock).toHaveBeenCalledTimes(2);
  });

  it('同 tick 关闭再打开不会让旧焦点恢复夺走新 drawer 焦点', async () => {
    const {w, trigger, body} = setup(), first = lease(), second = lease();
    const focus = vi.spyOn(trigger, 'focus');
    w.vm.open('7', accountRow(7), first, trigger); await nextTick();
    w.vm.close(); w.vm.open('8', accountRow(8), second, null); await nextTick();
    expect(first.release).toHaveBeenCalledTimes(1); expect(focus).not.toHaveBeenCalled();
    expect(document.activeElement?.id).toBe('btnCloseAccountDetail');
    expect(body.get('#accountDetailDrawer').attributes('data-account-id')).toBe('8');
  });

  it('直接切换 opening 不恢复旧 trigger，断开的 trigger 关闭时不聚焦', async () => {
    const {w, trigger} = setup(), first = lease(), second = lease();
    const focus = vi.spyOn(trigger, 'focus');
    w.vm.open('7', accountRow(7), first, trigger); await nextTick();
    w.vm.open('8', accountRow(8), second, trigger); await nextTick();
    expect(focus).not.toHaveBeenCalled(); trigger.remove(); w.vm.close(); await nextTick();
    expect(focus).not.toHaveBeenCalled(); expect(second.release).toHaveBeenCalledTimes(1);
  });

  it('null trigger 使用打开时 activeElement，并保留原 fallback 标题', async () => {
    const {w, trigger, body} = setup(), l = lease(); trigger.focus();
    w.vm.open('7', accountRow(7, {email: '', email_source: ''}), l, null); await nextTick();
    expect(body.get('#accountDetailTitle').text()).toBe('账号 #7');
    expect(body.get('#accountDetailSubtitle').text()).toBe('账号 #7 · 未知来源');
    w.vm.close(); await nextTick(); expect(document.activeElement).toBe(trigger);
  });

  it('卸载移除 Teleport、释放消费者并让壳重新检查滚动锁', async () => {
    const {w, trigger, callbacks, body} = setup(), l = lease();
    w.vm.open('7', accountRow(7), l, trigger); await nextTick();
    w.unmount(); mounted.splice(mounted.indexOf(w), 1); await nextTick();
    expect(l.release).toHaveBeenCalledTimes(1); expect(body.find('#accountDetailDrawer').exists()).toBe(false);
    expect(callbacks.syncModalScrollLock).toHaveBeenCalledTimes(2);
    expect(document.activeElement).toBe(trigger);
    l.wait.resolve({accountId: '7', revision: 'v1', item: {account_promotions: [], promotion_query_snapshot: null, plan_check_country_results: []}});
    await flushPromises(); expect(body.find('#accountDetailDrawer').exists()).toBe(false);
    expect(callbacks.notify).not.toHaveBeenCalled();
  });
});
