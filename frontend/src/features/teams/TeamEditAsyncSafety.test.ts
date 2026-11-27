// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils';
import TeamEditModal from './TeamEditModal.vue';
import { TeamApiError, type TeamsApi } from '../../api/teams';
import type { TeamDTO } from './contracts';

const firstTeam: TeamDTO = {
  id: '9007199254740993', revision: 4, workspace_id: 'workspace-first',
  name: '远端甲组', display_name: '本地甲组', role: 'owner',
  manager_account: { id: '71', email: 'first@example.test', archived: false },
  purchased_seats: 10, planned_member_limit: 8, confirmed_member_count: 2,
  pending_invite_count: 0, processing_count: 0, last_synced_at: null,
  last_sync_status: 'never',
};
const secondTeam: TeamDTO = {
  ...firstTeam, id: '9007199254740995', revision: 9, workspace_id: 'workspace-second',
  name: '远端乙组', display_name: '本地乙组', planned_member_limit: 6,
};
type SaveResponse = Awaited<ReturnType<TeamsApi['updateTeam']>>;

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (cause: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

const mounted = new Set<VueWrapper>();
beforeEach(() => {
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute('open', '');
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute('open');
  });
});
afterEach(() => {
  for (const wrapper of mounted) wrapper.unmount();
  mounted.clear();
  vi.restoreAllMocks();
});

function edit(updateTeam: TeamsApi['updateTeam']) {
  const wrapper = mount(TeamEditModal, {
    attachTo: document.body,
    props: { api: { updateTeam } as TeamsApi, team: firstTeam, open: true, visible: true },
  });
  mounted.add(wrapper);
  return wrapper;
}

function expectNoSaveEvents(wrapper: VueWrapper) {
  for (const event of ['updated', 'notify', 'close', 'conflict']) {
    expect(wrapper.emitted(event), event).toBeUndefined();
  }
}

describe('Team 编辑保存的弹窗会话归属', () => {
  it.each(['关闭', '关闭后重新打开', '切换 Team', '卸载'] as const)('%s后旧成功回包不触发保存事件', async mode => {
    const pending = deferred<SaveResponse>();
    const wrapper = edit(vi.fn<TeamsApi['updateTeam']>(() => pending.promise));
    await wrapper.get('form').trigger('submit');
    if (mode === '切换 Team') await wrapper.setProps({ team: secondTeam });
    else if (mode === '卸载') {
      wrapper.unmount();
      mounted.delete(wrapper);
    } else {
      await wrapper.setProps({ open: false });
      if (mode === '关闭后重新打开') await wrapper.setProps({ open: true });
    }
    pending.resolve({ team: { ...firstTeam, revision: 5 } });
    await flushPromises();
    expectNoSaveEvents(wrapper);
    if (mode === '切换 Team' || mode === '关闭后重新打开') {
      expect(wrapper.get<HTMLButtonElement>('button[type="submit"]').element.disabled).toBe(false);
    }
  });

  it.each([
    { mode: '切换 Team', cause: new Error('甲组保存失败') },
    { mode: '重新打开', cause: new TeamApiError('甲组修订已变更', 409, { code: 'team_revision_conflict' }) },
  ])('$mode 后旧失败不污染新表单或触发冲突', async ({ mode, cause }) => {
    const pending = deferred<SaveResponse>();
    const wrapper = edit(vi.fn<TeamsApi['updateTeam']>(() => pending.promise));
    await wrapper.get('form').trigger('submit');
    if (mode === '切换 Team') await wrapper.setProps({ team: secondTeam });
    else {
      await wrapper.setProps({ open: false });
      await wrapper.setProps({ open: true });
    }
    pending.reject(cause);
    await flushPromises();
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expectNoSaveEvents(wrapper);
    expect(wrapper.get<HTMLButtonElement>('button[type="submit"]').element.disabled).toBe(false);
  });

  it.each(['成功', '失败'] as const)('旧请求%s不能清除乙组新请求的 busy', async oldResult => {
    const old = deferred<SaveResponse>(), current = deferred<SaveResponse>();
    const updateTeam = vi.fn<TeamsApi['updateTeam']>()
      .mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
    const wrapper = edit(updateTeam);
    await wrapper.get('form').trigger('submit');
    await wrapper.setProps({ team: secondTeam });
    await wrapper.get('form').trigger('submit');
    expect(updateTeam).toHaveBeenCalledTimes(2);
    expect(updateTeam).toHaveBeenLastCalledWith('9007199254740995', {
      expected_revision: 9, display_name: '本地乙组', planned_member_limit: 6,
    });
    if (oldResult === '成功') old.resolve({ team: { ...firstTeam, revision: 5 } });
    else old.reject(new TeamApiError('甲组修订已变更', 409, { code: 'team_revision_conflict' }));
    await flushPromises();
    expectNoSaveEvents(wrapper);
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(wrapper.get<HTMLButtonElement>('button[type="submit"]').element.disabled).toBe(true);
    expect(wrapper.get('dialog').attributes('aria-busy')).toBe('true');
    const savedTeam = { ...secondTeam, revision: 10 };
    current.resolve({ team: savedTeam });
    await flushPromises();
    expect(wrapper.emitted('updated')).toEqual([[savedTeam]]);
    expect(wrapper.emitted('notify')).toHaveLength(1);
    expect(wrapper.emitted('close')).toHaveLength(1);
    expect(wrapper.emitted('conflict')).toBeUndefined();
    expect(wrapper.get<HTMLButtonElement>('button[type="submit"]').element.disabled).toBe(false);
  });

  it('仅隐藏页面保持原保存会话，成功不重新打开原生弹窗', async () => {
    const pending = deferred<SaveResponse>();
    const wrapper = edit(vi.fn<TeamsApi['updateTeam']>(() => pending.promise));
    await flushPromises();
    await wrapper.get('form').trigger('submit');
    await wrapper.setProps({ visible: false });
    expect(wrapper.get<HTMLDialogElement>('dialog').element.open).toBe(false);
    const showCount = vi.mocked(HTMLDialogElement.prototype.showModal).mock.calls.length;
    const savedTeam = { ...firstTeam, revision: 5 };
    pending.resolve({ team: savedTeam });
    await flushPromises();
    expect(wrapper.emitted('updated')).toEqual([[savedTeam]]);
    expect(wrapper.emitted('close')).toHaveLength(1);
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalledTimes(showCount);
    expect(wrapper.get<HTMLDialogElement>('dialog').element.open).toBe(false);
  });

  it('隐藏期间保存失败，恢复可见后保留同一会话的错误提示', async () => {
    const pending = deferred<SaveResponse>();
    const wrapper = edit(vi.fn<TeamsApi['updateTeam']>(() => pending.promise));
    await wrapper.get('form').trigger('submit');
    await wrapper.setProps({ visible: false });
    pending.reject(new Error('隐藏期间保存失败'));
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain('隐藏期间保存失败');
    expect(wrapper.get<HTMLDialogElement>('dialog').element.open).toBe(false);
    await wrapper.setProps({ visible: true });
    expect(wrapper.get('[role="alert"]').text()).toContain('隐藏期间保存失败');
    expectNoSaveEvents(wrapper);
    expect(wrapper.get<HTMLButtonElement>('button[type="submit"]').element.disabled).toBe(false);
  });

  it('同 Team 修订刷新保持原保存归属及请求发起时的参数', async () => {
    const pending = deferred<SaveResponse>();
    const updateTeam = vi.fn<TeamsApi['updateTeam']>(() => pending.promise);
    const wrapper = edit(updateTeam);
    await wrapper.get('form').trigger('submit');
    await wrapper.setProps({ team: { ...firstTeam, revision: 5, display_name: '刷新后的备注' } });
    const savedTeam = { ...firstTeam, revision: 6 };
    pending.resolve({ team: savedTeam });
    await flushPromises();
    expect(updateTeam).toHaveBeenCalledWith('9007199254740993', {
      expected_revision: 4, display_name: '本地甲组', planned_member_limit: 8,
    });
    expect(wrapper.emitted('updated')).toEqual([[savedTeam]]);
    expect(wrapper.emitted('close')).toHaveLength(1);
  });

  it('当前会话版本冲突正常反馈并恢复保存按钮', async () => {
    const pending = deferred<SaveResponse>();
    const wrapper = edit(vi.fn<TeamsApi['updateTeam']>(() => pending.promise));
    await wrapper.get('form').trigger('submit');
    pending.reject(new TeamApiError('修订已变更', 409, { code: 'team_revision_conflict' }));
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain('版本冲突');
    expect(wrapper.emitted('conflict')).toHaveLength(1);
    expect(wrapper.emitted('updated')).toBeUndefined();
    expect(wrapper.emitted('close')).toBeUndefined();
    expect(wrapper.get<HTMLButtonElement>('button[type="submit"]').element.disabled).toBe(false);
  });
});
