// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils';
import TeamBindModal from './TeamBindModal.vue';
import TeamEditModal from './TeamEditModal.vue';
import { TeamApiError, type TeamsApi } from '../../api/teams';
import type { TeamDTO } from './contracts';

const managerId = '9007199254740993';
const nextManagerId = '9007199254740995';
const team = {
  id: '9007199254740997', revision: 4, workspace_id: 'workspace-fixed',
  name: '远端团队', display_name: '本地团队', role: 'owner',
  manager_account: { id: managerId, email: 'first@example.test', archived: true },
  purchased_seats: null, planned_member_limit: 5, confirmed_member_count: null,
  pending_invite_count: null, processing_count: 0, last_synced_at: null,
  last_sync_status: 'never',
} as unknown as TeamDTO;

function workspace(id = 'workspace-fixed') {
  return {
    workspace_id: id, workspace_type: 'team', name: `团队 ${id}`, role: 'admin',
    can_manage: true, purchased_seats: null,
    capabilities: { read_members: true, read_invitations: true, invite_members: null },
  };
}

function apiFor(accountId = managerId, options: Record<string, unknown> = {}) {
  return {
    list: vi.fn<TeamsApi['list']>(async () => ({
      items: [], total: 0, page: 1, page_size: 100, revision: 'teams:empty',
    })),
    createBindingProbe: vi.fn(async () => ({
      probe_id: '31', status: 'queued', task_id: '41', run_id: '51',
    })),
    getBindingProbe: vi.fn(async () => ({
      id: '31', revision: 7,
      manager_account: {
        id: accountId, email: accountId === managerId ? 'first@example.test' : 'second@example.test',
        archived: false,
      },
      status: 'success', stage: 'complete', task_id: '41', run_id: '51',
      workspaces: [workspace()], suggested_workspace_id: 'workspace-fixed',
      completed_at: '2026-11-27T08:00:00Z', expires_at: '2099-01-01T00:00:00Z',
      error_info: null, ...options,
    })),
    createTeam: vi.fn(async () => ({ team })),
    updateTeam: vi.fn(async () => ({ team })),
  } as unknown as TeamsApi;
}

const mounted: VueWrapper[] = [];
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true, status: 200, redirected: false,
    text: async () => JSON.stringify({ items: [
      { id: managerId, email: 'first@example.test', archived: true, team_memberships: [] },
      { id: nextManagerId, email: 'second@example.test', archived: false, team_memberships: [] },
    ] }),
  })));
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };
});
afterEach(() => {
  for (const wrapper of mounted.splice(0)) wrapper.unmount();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function bind(api: TeamsApi, mode: 'bind' | 'change_manager' = 'bind') {
  const wrapper = mount(TeamBindModal, {
    attachTo: document.body,
    props: { api, mode, team: mode === 'change_manager' ? team : undefined, open: true, visible: true },
  });
  mounted.push(wrapper);
  return wrapper;
}

function submitButton(wrapper: VueWrapper, text = '确认绑定工作区') {
  return wrapper.findAll('button').find(button => button.text().includes(text))!;
}

async function probeAccount(wrapper: VueWrapper, index = 0) {
  await flushPromises();
  await wrapper.findAll('.tm-candidate-row')[index]!.find('button').trigger('click');
  await flushPromises();
}

describe('绑定与编辑弹窗使用真实后端契约', () => {
  it('按 workspace_type 与管理证据单选，并提交整数探测修订', async () => {
    const api = apiFor();
    const wrapper = bind(api);
    await probeAccount(wrapper);
    expect(wrapper.text()).toContain('团队 workspace-fixed');
    expect(submitButton(wrapper).attributes('disabled')).toBeUndefined();
    await submitButton(wrapper).trigger('click');
    await flushPromises();
    expect(api.createTeam).toHaveBeenCalledWith({
      manager_account_id: managerId, workspace_id: 'workspace-fixed',
      probe_id: '31', probe_revision: 7, display_name: null, planned_member_limit: null,
    });
  });

  it('切换所选母号立即作废旧账号的探测结果', async () => {
    const api = apiFor();
    const wrapper = bind(api);
    await probeAccount(wrapper);
    expect(wrapper.text()).toContain('团队 workspace-fixed');
    await wrapper.findAll('.tm-candidate-row')[1]!.trigger('click');
    expect(wrapper.text()).not.toContain('团队 workspace-fixed');
    expect(submitButton(wrapper).attributes('disabled')).toBeDefined();
    await submitButton(wrapper).trigger('click');
    expect(api.createTeam).not.toHaveBeenCalled();
  });

  it('更换母号只允许原工作区，忽略其他工作区建议', async () => {
    const api = apiFor(nextManagerId, {
      workspaces: [workspace('workspace-other'), workspace()],
      suggested_workspace_id: 'workspace-other',
    });
    const wrapper = bind(api, 'change_manager');
    await probeAccount(wrapper, 1);
    const choices = wrapper.findAll('.tm-workspace-option');
    expect(choices[0]!.attributes('aria-disabled')).toBe('true');
    expect(choices[1]!.attributes('aria-checked')).toBe('true');
    const confirm = submitButton(wrapper, '确认更换母号');
    expect(confirm.attributes('disabled')).toBeUndefined();
    await confirm.trigger('click');
    await flushPromises();
    expect(api.updateTeam).toHaveBeenCalledWith('9007199254740997', {
      expected_revision: 4, manager_account_id: nextManagerId,
      probe_id: '31', probe_revision: 7,
    });
  });

  it('编辑使用 Team id 与 name，保留修订校验', async () => {
    const api = apiFor();
    const wrapper = mount(TeamEditModal, {
      attachTo: document.body, props: { api, team, open: true, visible: true },
    });
    mounted.push(wrapper);
    expect(wrapper.text()).toContain('远端团队');
    await wrapper.find('form').trigger('submit');
    await flushPromises();
    expect(api.updateTeam).toHaveBeenCalledWith('9007199254740997', {
      expected_revision: 4, display_name: '本地团队', planned_member_limit: 5,
    });
  });
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (cause: unknown) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}
function boundReceipt(): Awaited<ReturnType<TeamsApi['createTeam']>> {
  return { team, sync: { accepted: true, reused: false, team_id: team.id,
    task_id: '61', run_id: '71', status: 'queued' } };
}

describe('绑定弹窗异步回包归属', () => {
  it.each(['成功', '失败'] as const)('重新打开后旧绑定%s不影响新提交', async result => {
    const old = deferred<Awaited<ReturnType<TeamsApi['createTeam']>>>();
    const current = deferred<Awaited<ReturnType<TeamsApi['createTeam']>>>();
    const api = apiFor();
    vi.mocked(api.createTeam).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
    const wrapper = bind(api);
    await probeAccount(wrapper);
    await submitButton(wrapper).trigger('click');
    await wrapper.setProps({ open: false });
    await wrapper.setProps({ open: true });
    await probeAccount(wrapper);
    expect(wrapper.get('.tm-dialog__foot .tm-btn--primary').attributes('disabled')).toBeUndefined();
    await submitButton(wrapper).trigger('click');
    expect(api.createTeam).toHaveBeenCalledTimes(2);
    if (result === '成功') old.resolve(boundReceipt());
    else old.reject(new TeamApiError('旧探测已过期', 410, { code: 'team_probe_expired' }));
    await flushPromises();
    expect(wrapper.emitted('bound')).toBeUndefined();
    expect(wrapper.emitted('notify')).toBeUndefined();
    expect(wrapper.emitted('close')).toBeUndefined();
    expect(wrapper.text()).not.toContain('旧探测已过期');
    expect(wrapper.text()).not.toContain('核验结果已过期');
    expect(wrapper.get('.tm-dialog__foot .tm-btn--primary').attributes('disabled')).toBeDefined();
    expect(wrapper.find('dialog').attributes('aria-busy')).toBe('true');
    current.resolve(boundReceipt());
    await flushPromises();
    expect(wrapper.emitted('bound')).toEqual([[team]]);
    expect(wrapper.emitted('close')).toHaveLength(1);
  });

  it('保持打开时更换 Team 作废旧母号更新回包和旧探测结果', async () => {
    const old = deferred<Awaited<ReturnType<TeamsApi['updateTeam']>>>();
    const nextTeam: TeamDTO = { ...team, id: '9007199254741001', workspace_id: 'workspace-next', name: '新目标团队', display_name: '新目标团队' };
    const api = apiFor(nextManagerId);
    vi.mocked(api.updateTeam).mockReturnValueOnce(old.promise);
    const wrapper = bind(api, 'change_manager');
    await probeAccount(wrapper, 1);
    await submitButton(wrapper, '确认更换母号').trigger('click');
    await wrapper.setProps({ team: nextTeam });
    expect(wrapper.text()).toContain('新目标团队');
    expect(wrapper.findAll('.tm-workspace-option')).toHaveLength(0);
    old.resolve({ team });
    await flushPromises();
    expect(wrapper.emitted('managerUpdated')).toBeUndefined();
    expect(wrapper.emitted('close')).toBeUndefined();
    expect(wrapper.emitted('notify')).toBeUndefined();
    expect(wrapper.get('.tm-dialog__foot .tm-btn--primary').attributes('disabled')).toBeDefined();
  });

  it('保持打开时由绑定切为换母号会清除旧模式的探测', async () => {
    const api = apiFor();
    const wrapper = bind(api);
    await probeAccount(wrapper);
    expect(wrapper.findAll('.tm-workspace-option')).toHaveLength(1);
    await wrapper.setProps({ mode: 'change_manager', team });
    expect(wrapper.findAll('.tm-workspace-option')).toHaveLength(0);
    expect(wrapper.get('.tm-dialog__foot .tm-btn--primary').attributes('disabled')).toBeDefined();
  });

  it('更换 Team 后已中止的探测即使返回也不覆盖新目标', async () => {
    const old = deferred<Awaited<ReturnType<TeamsApi['getBindingProbe']>>>();
    const api = apiFor(nextManagerId);
    const oldProbe = await api.getBindingProbe('31');
    vi.mocked(api.getBindingProbe).mockReturnValueOnce(old.promise);
    const wrapper = bind(api, 'change_manager');
    await probeAccount(wrapper, 1);
    await wrapper.setProps({ team: { ...team, id: '9007199254741001', workspace_id: 'workspace-next' } });
    const signal = vi.mocked(api.getBindingProbe).mock.calls[1]?.[1];
    expect(signal?.aborted).toBe(true);
    old.resolve(oldProbe);
    await flushPromises();
    expect(wrapper.findAll('.tm-workspace-option')).toHaveLength(0);
    expect(wrapper.find('dialog').attributes('aria-busy')).toBe('false');
  });

  it('仅临时隐藏时保留同一会话的失败结果，回包不重新打开弹窗', async () => {
    const pending = deferred<Awaited<ReturnType<TeamsApi['createTeam']>>>();
    const api = apiFor();
    vi.mocked(api.createTeam).mockReturnValueOnce(pending.promise);
    const wrapper = bind(api);
    await probeAccount(wrapper);
    await submitButton(wrapper).trigger('click');
    await wrapper.setProps({ visible: false });
    pending.reject(new Error('绑定证据已改变'));
    await flushPromises();
    expect(wrapper.find('dialog').attributes('open')).toBeUndefined();
    expect(wrapper.emitted('close')).toBeUndefined();
    await wrapper.setProps({ visible: true });
    expect(wrapper.text()).toContain('绑定证据已改变');
  });

  it('卸载后绑定成功不再派发导航或通知事件', async () => {
    const pending = deferred<Awaited<ReturnType<TeamsApi['createTeam']>>>();
    const api = apiFor();
    vi.mocked(api.createTeam).mockReturnValueOnce(pending.promise);
    const wrapper = bind(api);
    await probeAccount(wrapper);
    await submitButton(wrapper).trigger('click');
    wrapper.unmount();
    pending.resolve(boundReceipt());
    await flushPromises();
    expect(wrapper.emitted('bound')).toBeUndefined();
    expect(wrapper.emitted('notify')).toBeUndefined();
    expect(wrapper.emitted('close')).toBeUndefined();
  });
});

type TeamPage = Awaited<ReturnType<TeamsApi['list']>>;
function managerTeamPage(items: TeamDTO[], page = 1, total = items.length): TeamPage {
  return { items, total, page, page_size: 100, revision: `teams:${page}` };
}

describe('绑定弹窗区分本地管理母号与已确认成员', () => {
  it('首次同步前空成员关系仍显示母号关联，搜索与临时隐藏复用已完成索引', async () => {
    const api = apiFor();
    vi.mocked(api.list).mockResolvedValue(managerTeamPage([{ ...team, display_name: '尚未同步的 Team3' }]));
    const wrapper = bind(api);
    await flushPromises();
    const row = wrapper.findAll('.tm-candidate-row')[0]!;
    expect(row.text()).toContain('本地管理母号：');
    expect(row.text()).toContain('尚未同步的 Team3');
    expect(row.text()).not.toContain('已关联 Team：');
    expect(row.text()).not.toContain('已入组');
    expect(api.list).toHaveBeenCalledWith({ page: 1, page_size: 100, include_facets: '0' }, expect.any(AbortSignal));
    const search = wrapper.get('input[aria-label="搜索管理母号"]');
    await search.setValue('first');
    await search.trigger('keydown', { key: 'Enter' });
    await flushPromises();
    await wrapper.setProps({ visible: false });
    await wrapper.setProps({ visible: true });
    await flushPromises();
    expect(api.list).toHaveBeenCalledTimes(1);
    expect(wrapper.findAll('.tm-candidate-row')[0]!.text()).toContain('尚未同步的 Team3');
  });

  it('遍历真实分页，在后页找到母号关联', async () => {
    const api = apiFor();
    const unrelated = Array.from({ length: 100 }, (_, index): TeamDTO => ({
      ...team, id: String(1000 + index), manager_account: { id: '999', email: null, archived: false },
    }));
    vi.mocked(api.list).mockResolvedValueOnce(managerTeamPage(unrelated, 1, 101))
      .mockResolvedValueOnce(managerTeamPage([{ ...team, display_name: '第二页母号 Team' }], 2, 101));
    const wrapper = bind(api);
    await flushPromises();
    expect(api.list).toHaveBeenCalledTimes(2);
    expect(api.list).toHaveBeenLastCalledWith({ page: 2, page_size: 100, include_facets: '0' }, expect.any(AbortSignal));
    expect(wrapper.findAll('.tm-candidate-row')[0]!.text()).toContain('本地管理母号：');
    expect(wrapper.findAll('.tm-candidate-row')[0]!.text()).toContain('第二页母号 Team');
  });

  it.each(['成功', '失败'] as const)('旧会话关联读取%s不覆盖新会话索引或清除读取状态', async result => {
    const old = deferred<TeamPage>(), current = deferred<TeamPage>();
    const api = apiFor();
    vi.mocked(api.list).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
    const wrapper = bind(api);
    await flushPromises();
    await wrapper.setProps({ open: false });
    await wrapper.setProps({ open: true });
    await flushPromises();
    expect(api.list).toHaveBeenCalledTimes(2);
    expect(vi.mocked(api.list).mock.calls[0]?.[1]?.aborted).toBe(true);
    if (result === '成功') old.resolve(managerTeamPage([{ ...team, display_name: '旧会话关联' }]));
    else old.reject(new Error('旧会话关联读取失败'));
    await flushPromises();
    expect(wrapper.text()).not.toContain('旧会话关联');
    expect(wrapper.text()).toContain('正在读取本地管理母号关联');
    current.resolve(managerTeamPage([{ ...team, display_name: '当前会话关联' }]));
    await flushPromises();
    expect(wrapper.findAll('.tm-candidate-row')[0]!.text()).toContain('当前会话关联');
    expect(wrapper.text()).not.toContain('正在读取本地管理母号关联');
  });

  it('隐藏时中止未完成读取，返回后重读且忽略旧回包', async () => {
    const old = deferred<TeamPage>(), current = deferred<TeamPage>();
    const api = apiFor();
    vi.mocked(api.list).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
    const wrapper = bind(api);
    await flushPromises();
    await wrapper.setProps({ visible: false });
    expect(vi.mocked(api.list).mock.calls[0]?.[1]?.aborted).toBe(true);
    await wrapper.setProps({ visible: true });
    expect(api.list).toHaveBeenCalledTimes(2);
    old.resolve(managerTeamPage([{ ...team, display_name: '隐藏前关联' }]));
    await flushPromises();
    expect(wrapper.text()).not.toContain('隐藏前关联');
    expect(wrapper.text()).toContain('正在读取本地管理母号关联');
    current.resolve(managerTeamPage([{ ...team, display_name: '恢复后关联' }]));
    await flushPromises();
    expect(wrapper.text()).toContain('恢复后关联');
  });

  it('后页读取失败独立报错，不把部分结果当完整关联且不阻断探测绑定', async () => {
    const api = apiFor();
    const partial = Array.from({ length: 100 }, (_, index): TeamDTO => ({ ...team, id: String(1000 + index) }));
    vi.mocked(api.list).mockResolvedValueOnce(managerTeamPage(partial, 1, 101)).mockRejectedValueOnce(new Error('关联后页暂不可读'));
    const wrapper = bind(api);
    await flushPromises();
    expect(wrapper.text()).toContain('读取本地管理母号关联失败');
    expect(wrapper.text()).toContain('关联后页暂不可读');
    expect(wrapper.findAll('.tm-candidate-row')[0]!.text()).not.toContain('本地管理母号：');
    await probeAccount(wrapper);
    expect(submitButton(wrapper).attributes('disabled')).toBeUndefined();
    await submitButton(wrapper).trigger('click');
    await flushPromises();
    expect(wrapper.emitted('bound')).toEqual([[team]]);
  });

  it.each(['更换目标', '卸载'] as const)('%s会中止独立的管理母号关联读取', async action => {
    const pending = deferred<TeamPage>();
    const api = apiFor();
    vi.mocked(api.list).mockReturnValueOnce(pending.promise);
    const wrapper = bind(api);
    await flushPromises();
    const signal = vi.mocked(api.list).mock.calls[0]?.[1];
    if (action === '更换目标') await wrapper.setProps({ mode: 'change_manager', team });
    else wrapper.unmount();
    expect(signal?.aborted).toBe(true);
    pending.resolve(managerTeamPage([]));
    await flushPromises();
  });
});
