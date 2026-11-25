import {afterEach, describe, expect, it, vi} from 'vitest';
import {DOMWrapper, flushPromises, mount, type VueWrapper} from '@vue/test-utils';
import {nextTick} from 'vue';
import EmailChange from './EmailChange.vue';
import type {AccountEmailChangeDependencies} from './useAccountEmailChange';
import type {AccountActionContext} from './useAccounts';
import {accountRow, deferred, realAdapter} from './uiTestSupport';

const wrappers: VueWrapper[] = [];
afterEach(() => {wrappers.splice(0).forEach(wrapper => wrapper.unmount()); document.body.replaceChildren();});
const sources = {ok: true, sources: [{value: 'outlook', label: 'Outlook', enabled: true, reason: ''},
  {value: 'cloudflare', label: 'Cloudflare', enabled: true, reason: ''},
  {value: 'icloud_hide', label: '<i>iCloud</i>', enabled: false, reason: '未配置'}]};
function context(id = 7, source = 'outlook'): AccountActionContext {
  return {accountIds: [String(id)], expectedEmails: {[id]: `old-${id}@test`},
    rowHints: [accountRow(id, {email: `old-${id}@test`, email_source: source})], querySnapshot: realAdapter().normalize(), archived: '0'};
}
function setup(extra: Partial<AccountEmailChangeDependencies> = {}) {
  const tab = document.createElement('section'); tab.innerHTML = '<div id="accountEmailChangeHost"></div>';
  document.body.append(tab); const trigger = document.createElement('button'); trigger.textContent = '换绑'; tab.prepend(trigger);
  const chosen: AccountEmailChangeDependencies = {request: vi.fn<AccountEmailChangeDependencies['request']>(async () => sources), notify: vi.fn(),
    refreshAccounts: vi.fn(), openTasks: vi.fn(), syncModalScrollLock: vi.fn(), ...extra};
  const deps = {...chosen, syncModalScrollLock: vi.fn(chosen.syncModalScrollLock)};
  const w = mount(EmailChange, {attachTo: tab, props: {deps}}); wrappers.push(w);
  return {w, deps, trigger, body: new DOMWrapper(document.body)};
}

describe('Vue 换邮弹窗保留交互并隔离打开代次', () => {
  it('保留原source-only语义、不可用来源原因与安全转义，来源载入后聚焦', async () => {
    const {w, trigger, body, deps} = setup();
    expect(w.vm.openSingle(7, context(), trigger)).toBe(true); await flushPromises();
    const modal = body.get('#emailChangeModal');
    expect(modal.attributes()).toMatchObject({role: 'dialog', 'aria-modal': 'true', 'aria-hidden': 'false', 'aria-labelledby': 'emailChangeTitle', 'aria-describedby': 'emailChangeNote', 'data-account-id': '7', 'data-account-ids': ''});
    expect(modal.element.parentElement?.id).toBe('accountEmailChangeHost');
    expect(body.get('#emailChangeTitle').text()).toBe('换绑邮箱'); expect(body.get('#emailChangeAccountLabel').text()).toBe('账号 #7 · 当前邮箱 old-7@test');
    const select = body.get<HTMLSelectElement>('#emailChangeSource');
    expect(select.attributes()).toMatchObject({name: 'email_source', required: ''}); expect(select.element.value).toBe('outlook');
    const blocked = select.get('option[value="icloud_hide"]');
    expect(blocked.attributes()).toMatchObject({disabled: '', title: '未配置', 'data-reason': '未配置'});
    expect(blocked.text()).toBe('<i>iCloud</i>（不可用）'); expect(blocked.find('i').exists()).toBe(false);
    expect(body.find('#emailChangeTarget').exists()).toBe(false); expect(body.get('#emailChangeNote').text()).toContain('不会启动浏览器');
    expect(document.activeElement).toBe(select.element); expect(deps.syncModalScrollLock).toHaveBeenCalled();
  });

  it.each(['#btnCloseEmailChange', '#btnCancelEmailChange', '#emailChangeModal'])('通过%s关闭并恢复连接trigger焦点', async selector => {
    const {w, trigger, body, deps} = setup(); w.vm.openSingle(7, context(), trigger); await flushPromises();
    await body.get(selector).trigger('click');
    expect(body.get('#emailChangeModal').classes()).toContain('hidden');
    expect(body.get('#emailChangeModal').attributes('aria-hidden')).toBe('true');
    expect(body.get('#emailChangeModal').attributes('data-account-id')).toBe(''); expect(document.activeElement).toBe(trigger);
    const count = deps.syncModalScrollLock.mock.calls.length; w.vm.close(); await nextTick(); expect(deps.syncModalScrollLock).toHaveBeenCalledTimes(count);
  });

  it('Escape关闭且Tab/ShiftTab在当前可用控件之间循环', async () => {
    const {w, trigger, body} = setup(); w.vm.openSingle(7, context(), trigger); await flushPromises();
    const first = body.get<HTMLButtonElement>('#btnCloseEmailChange').element, last = body.get<HTMLButtonElement>('#btnSubmitEmailChange').element;
    first.focus(); const backwards = new KeyboardEvent('keydown', {key: 'Tab', shiftKey: true, bubbles: true, cancelable: true});
    document.dispatchEvent(backwards); expect(backwards.defaultPrevented).toBe(true); expect(document.activeElement).toBe(last);
    const forwards = new KeyboardEvent('keydown', {key: 'Tab', bubbles: true, cancelable: true}); document.dispatchEvent(forwards);
    expect(document.activeElement).toBe(first);
    const escape = new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}); document.dispatchEvent(escape); await nextTick();
    expect(escape.defaultPrevented).toBe(true); expect(document.activeElement).toBe(trigger);
    expect(body.get('#emailChangeModal').classes()).toContain('hidden');
  });

  it('无来源显示原错误，提交空来源给出validity提示且不POST', async () => {
    const {w, body, deps} = setup({request: vi.fn(async () => ({sources: []}))});
    w.vm.openSingle(7, context()); await flushPromises();
    expect(body.get('#emailChangeSourceError').text()).toBe('没有已配置且可用的新邮箱来源');
    expect(body.get<HTMLSelectElement>('#emailChangeSource').element.disabled).toBe(true);
    await body.get('form').trigger('submit'); await flushPromises();
    expect(body.get('#emailChangeSourceError').text()).toBe('请选择新邮箱来源'); expect(deps.request).toHaveBeenCalledTimes(1);
  });

  it('关闭后旧来源成功或失败不改变新标题/选择，也不抢焦点', async () => {
    const old = deferred<unknown>(); const request = vi.fn<AccountEmailChangeDependencies['request']>().mockReturnValueOnce(old.promise).mockResolvedValueOnce(sources);
    const {w, body, trigger} = setup({request}); w.vm.openSingle(7, context(), trigger); await nextTick();
    w.vm.close(); w.vm.openSingle(8, context(8, 'cloudflare'), trigger); await flushPromises();
    const cancel = body.get<HTMLButtonElement>('#btnCancelEmailChange').element; cancel.focus(); old.resolve({sources: [{value: 'outlook', enabled: true}]}); await flushPromises();
    expect(body.get('#emailChangeAccountLabel').text()).toContain('old-8@test');
    expect(body.get<HTMLSelectElement>('#emailChangeSource').element.value).toBe('cloudflare'); expect(document.activeElement).toBe(cancel);
  });

  it('旧提交成功保留回执却不关闭新窗口、不导航或重置新提交按钮', async () => {
    const old = deferred<unknown>(), current = deferred<unknown>();
    const request = vi.fn<AccountEmailChangeDependencies['request']>().mockResolvedValueOnce(sources).mockReturnValueOnce(old.promise)
      .mockResolvedValueOnce(sources).mockReturnValueOnce(current.promise);
    const {w, body, trigger, deps} = setup({request}); w.vm.openSingle(7, context(), trigger); await flushPromises();
    await body.get('form').trigger('submit'); w.vm.close(); w.vm.openSingle(8, context(8, 'cloudflare'), trigger); await flushPromises();
    await body.get('form').trigger('submit'); const cancel = body.get<HTMLButtonElement>('#btnCancelEmailChange').element; cancel.focus();
    old.resolve({ok: true, task_id: 71}); await flushPromises();
    expect(body.get('#emailChangeModal').classes()).not.toContain('hidden'); expect(body.get('#emailChangeAccountLabel').text()).toContain('old-8@test');
    expect(body.get<HTMLButtonElement>('#btnSubmitEmailChange').element.disabled).toBe(true); expect(body.get('#btnSubmitEmailChange').text()).toBe('提交中…');
    expect(document.activeElement).toBe(cancel); expect(deps.openTasks).not.toHaveBeenCalled();
    current.resolve({ok: true, task_id: 81}); await flushPromises(); expect(deps.openTasks).toHaveBeenCalledExactlyOnceWith({target: 'old-8@test', type: 'email_change'});
  });

  it('当前成功先关闭弹窗，异步滚动锁不抢任务中心的新焦点', async () => {
    const task = document.createElement('button'); document.body.append(task);
    const request = vi.fn<AccountEmailChangeDependencies['request']>().mockResolvedValueOnce(sources).mockResolvedValueOnce({ok: true, task_id: 71});
    const {w, body, trigger} = setup({request, openTasks: () => {task.focus();}});
    w.vm.openSingle(7, context(), trigger); await flushPromises(); await body.get('form').trigger('submit'); await flushPromises();
    expect(body.get('#emailChangeModal').classes()).toContain('hidden'); expect(document.activeElement).toBe(task);
  });

  it('卸载取消来源读且清理键盘监听，连接trigger只恢复一次', async () => {
    const pending = deferred<unknown>(); const request = vi.fn<AccountEmailChangeDependencies['request']>(() => pending.promise);
    const {w, trigger, deps} = setup({request}); const focus = vi.spyOn(trigger, 'focus'); w.vm.openSingle(7, context(), trigger); await nextTick();
    w.unmount(); wrappers.splice(wrappers.indexOf(w), 1); await nextTick();
    expect(request.mock.calls[0][1]?.signal?.aborted).toBe(true); expect(document.getElementById('emailChangeModal')).toBeNull();
    expect(focus).toHaveBeenCalledTimes(1); const calls = deps.syncModalScrollLock.mock.calls.length;
    document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'})); expect(deps.syncModalScrollLock).toHaveBeenCalledTimes(calls);
    pending.resolve(sources); await flushPromises(); expect(focus).toHaveBeenCalledTimes(1);
  });
});
