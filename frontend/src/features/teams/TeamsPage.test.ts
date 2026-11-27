// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils';
import TeamsPageShell from './TeamsPageShell.vue';
import TeamsListView from './TeamsListView.vue';
import TeamDetailView from './TeamDetailView.vue';
import TeamInvitationsTab from './TeamInvitationsTab.vue';
import TeamJoinModal from './TeamJoinModal.vue';
import type { TeamsApi } from '../../api/teams';
import type { components } from '../../api/teams-schema';
import type { TeamsHostCallbacks } from './contracts';

type Team = components['schemas']['TeamDTO'];
type Invitation = components['schemas']['InvitationDTO'];

const teamAlpha: Team = {
  id: '9007199254740993', revision: 8, workspace_id: 'ws-alpha-core',
  name: 'Alpha Growth Lab', display_name: 'Alpha 核心研发组',
  manager_account: { id: '1001', email: 'owner-alpha@example.test', archived: true },
  role: 'owner', purchased_seats: 15, planned_member_limit: 12,
  confirmed_member_count: 7, pending_invite_count: 2, processing_count: 1,
  last_sync_status: 'failed', last_synced_at: '2026-11-27T14:48:12Z',
};
const teamUnsynced: Team = {
  ...teamAlpha, id: '9007199254740994', workspace_id: 'ws-null-counts',
  name: 'Null Counts Team', display_name: null,
  purchased_seats: null, planned_member_limit: null,
  confirmed_member_count: null, pending_invite_count: null, processing_count: null,
  last_sync_status: 'never', last_synced_at: null,
};
const failedInvitation: Invitation = {
  id: '8001', team_id: teamAlpha.id, remote_invitation_id: 'inv_1',
  account: { id: '9007199254740999', email: 'worker-01@example.test', archived: false },
  email_snapshot: 'worker-01@example.test', invitation_state: 'pending',
  membership_state: 'unconfirmed', updated_at: '2026-11-27T14:22:00Z', last_verified_at: null,
  latest_execution: {
    task_id: '9007199254741001', run_id: '9007199254741003',
    status: 'failed', stage: 'member_auth', waiting_reason_code: null,
    error_info: {
      code: 'missing_auth_materials', message: '缺少成员认证材料',
      stage: 'member_auth', retryable: true,
    },
  },
  actions: {
    continue: { enabled: true, reason_code: null },
    retry: { enabled: true, reason_code: null },
    view_task: { enabled: true, reason_code: null },
  },
};

function joinReceipt(operation: 'continue' | 'retry' = 'continue'): components['schemas']['JoinRequestDTO'] {
  return {
    id: '9101', team_id: teamAlpha.id, operation, accepted: true, reused: false,
    status: 'preparing', waiting_reason_code: null, selection_id: null, selection_revision: null,
    batch_id: '9201', task_id: '9301', run_id: '9401', created_at: '2026-11-27T15:00:00Z',
    counts: {
      requested_count: 1, unique_count: 1, duplicate_count: 0, pending_count: 1,
      accepted_count: 0, reused_count: 0, skipped_count: 0, failed_count: 0,
    },
    capacity: {
      basis: 'purchased_seats', purchased_seats: 15, planned_member_limit: 12,
      effective_limit: 12, occupied_count: 9, available_count: 3, additional_required: null,
      can_submit: true, blocking_reason_code: null,
    },
    items_url: `/api/teams/${teamAlpha.id}/join-requests/9101`,
  };
}

function createStubApi(): TeamsApi {
  const receipt = joinReceipt();
  return {
    list: vi.fn(async () => ({
      items: [teamAlpha, teamUnsynced], total: 2, page: 1, page_size: 20,
      revision: 'teams:1', facets: {},
    })),
    detail: vi.fn(async (id: string) => ({
      team: id === teamUnsynced.id ? teamUnsynced : teamAlpha,
      actions: {
        sync: { enabled: true, reason_code: null },
        reverify: { enabled: true, reason_code: null },
        join: { enabled: true, reason_code: null },
      },
      permission_verified_at: '2026-11-27T14:40:00Z',
    })),
    createBindingProbe: vi.fn(), getBindingProbe: vi.fn(), createTeam: vi.fn(), updateTeam: vi.fn(),
    syncTeam: vi.fn(async (id: string) => ({
      accepted: true, reused: false, team_id: id, status: 'queued', task_id: '50200', run_id: '60200',
    })),
    syncTeamsBulk: vi.fn(), reverifyTeam: vi.fn(),
    listMembers: vi.fn(async () => ({
      items: [{
        id: '7001', team_id: teamAlpha.id, remote_user_id: 'u1',
        email: 'owner-alpha@example.test', role: 'owner', membership_state: 'joined',
        joined_at: '2026-11-20T08:05:00Z', last_verified_at: '2026-11-27T14:48:12Z',
        account: teamAlpha.manager_account,
        latest_task: { task_id: '9007199254741005', run_id: '9007199254741007', status: 'success' },
      }], total: 1, page: 1, page_size: 20, revision: 'members:1', facets: {},
    })),
    listInvitations: vi.fn(async () => ({
      items: [failedInvitation], total: 1, page: 1, page_size: 20, revision: 'invitations:1', facets: {},
    })),
    getInvitation: vi.fn(), listCandidates: vi.fn(), resolveCandidates: vi.fn(),
    previewJoin: vi.fn(), submitJoin: vi.fn(),
    getJoinRequest: vi.fn(async () => ({
      request: receipt, items: [{
        ordinal: 0, account_id: '9007199254740999', invitation_id: '8001',
        acceptance_status: 'pending', task_id: null, run_id: null,
        execution_status: 'none', reason_code: null, message: null,
      }], total: 1, page: 1, page_size: 1, revision: 'request:1',
    })),
    continueInvitation: vi.fn(async () => receipt),
    retryInvitation: vi.fn(async () => joinReceipt('retry')),
    continueInvitationsBulk: vi.fn(), retryInvitationsBulk: vi.fn(), freezeAccountSelection: vi.fn(),
  } as unknown as TeamsApi;
}

function callbacks(): TeamsHostCallbacks {
  return {
    notify: vi.fn(), formatDateTime: value => value || '—',
    openTask: vi.fn(), openTasksForTeam: vi.fn(), openAccountDetail: vi.fn(),
    openAccountsCandidateMode: vi.fn(), onNavigation: vi.fn(),
  };
}

const mounted: VueWrapper[] = [];
beforeEach(() => {
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };
});
afterEach(() => {
  for (const wrapper of mounted.splice(0)) wrapper.unmount();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('Team 页面真实 DTO 与导航接缝', () => {
  it('保留未知计数与独立摘要，不从摘要相加推导可用席位，并保持大 ID 导航', async () => {
    const api = createStubApi(), host = callbacks();
    const wrapper = mount(TeamsPageShell, { attachTo: document.body, props: { api, callbacks: host } });
    mounted.push(wrapper);
    await flushPromises();

    expect(wrapper.text()).toContain('Alpha 核心研发组');
    expect(wrapper.text()).toContain('Null Counts Team');
    expect(wrapper.text()).toContain('待同步');
    expect(wrapper.text()).toContain('需设本地上限');
    expect(wrapper.text()).toContain('余量待预检');
    expect(wrapper.text()).not.toContain('可拉剩余 3 席');
    expect(wrapper.text()).toContain('已归档');

    await wrapper.findAll('.tm-workspace-name-btn')[0]!.trigger('click');
    await flushPromises();
    expect(host.onNavigation).toHaveBeenLastCalledWith({
      tab: 'teams', view: 'detail', team_id: teamAlpha.id, section: 'members',
    }, 'push');
    expect(wrapper.text()).toContain('最近一次同步失败');
    expect(wrapper.text()).toContain(teamAlpha.last_synced_at);
    expect(wrapper.findAll('section[aria-label="工作区成员列表"] thead th')).toHaveLength(7);

    await wrapper.findAll('.tm-tab-btn').find(button => button.text().includes('邀请'))!.trigger('click');
    await flushPromises();
    expect(host.onNavigation).toHaveBeenLastCalledWith({
      tab: 'teams', view: 'detail', team_id: teamAlpha.id, section: 'invitations',
    }, 'replace');
    expect(wrapper.findAll('div[aria-label="邀请与入组表格，可横向滚动"] thead th')).toHaveLength(6);
    expect(wrapper.text()).toContain('待接受邀请');
    expect(wrapper.text()).toContain('成员：待确认');
    expect(wrapper.text()).toContain('缺少认证材料');

    await wrapper.findAll('button').find(button => button.text() === '继续加入')!.trigger('click');
    await flushPromises();
    expect(api.continueInvitation).toHaveBeenCalledWith(teamAlpha.id, failedInvitation.id);
    expect(api.getJoinRequest).toHaveBeenCalledWith(teamAlpha.id, '9101', {
      page: 1, page_size: 1,
    }, expect.any(AbortSignal));

    await wrapper.find('.tm-back-btn').trigger('click');
    await flushPromises();
    expect(wrapper.vm.navigationState()).toEqual({ tab: 'teams', view: 'list' });
  });

  it('详情深链与相关任务传递精确 Team ID，成员引用保留独立 Task/Run', async () => {
    const api = createStubApi(), host = callbacks();
    const wrapper = mount(TeamsPageShell, {
      attachTo: document.body,
      props: {
        api, callbacks: host,
        initialNavigation: { tab: 'teams', view: 'detail', team_id: teamAlpha.id, section: 'members' },
      },
    });
    mounted.push(wrapper);
    await flushPromises();
    expect(api.detail).toHaveBeenCalledWith(teamAlpha.id, expect.any(AbortSignal));
    const detail = wrapper.findComponent(TeamDetailView);
    await detail.findAll('button').find(button => button.text() === '查看相关任务')!.trigger('click');
    expect(host.openTasksForTeam).toHaveBeenCalledWith(teamAlpha.id, 'Alpha 核心研发组');
    const members = wrapper.find('section[aria-label="工作区成员列表"]');
    await members.findAll('button').find(button => button.text() === '#1001')!.trigger('click');
    expect(host.openAccountDetail).toHaveBeenCalledWith('1001');
    await members.findAll('button').find(button => button.text().includes('查看任务'))!.trigger('click');
    expect(host.openTask).toHaveBeenCalledWith('9007199254741005', '9007199254741007');
  });

  it('远端已加入但本地保存失败时保留业务事实、具体错误和继续入口', async () => {
    const api = createStubApi(), host = callbacks();
    vi.mocked(api.listInvitations).mockResolvedValue({
      items: [{
        ...failedInvitation, invitation_state: 'accepted', membership_state: 'joined',
        latest_execution: {
          ...failedInvitation.latest_execution, status: 'partial_success', stage: 'persist',
          error_info: { code: 'team_save_failed', message: '工作区认证上下文保存失败', stage: 'persist', retryable: true },
        },
      }], total: 1, page: 1, page_size: 20, revision: 'joined:1',
    });
    const wrapper = mount(TeamInvitationsTab, {
      attachTo: document.body, props: { api, callbacks: host, teamId: teamAlpha.id, visible: true },
    });
    mounted.push(wrapper);
    await flushPromises();
    expect(wrapper.text()).toContain('成员：已加入');
    expect(wrapper.text()).toContain('部分成功');
    expect(wrapper.text()).toContain('本地保存失败');
    const continueButton = wrapper.findAll('button').find(button => button.text() === '继续加入')!;
    expect(continueButton.attributes('disabled')).toBeUndefined();
    await wrapper.findAll('button').find(button => button.text() === '查看任务')!.trigger('click');
    expect(host.openTask).toHaveBeenCalledWith('9007199254741001', '9007199254741003');
  });

  it('活跃列表仅在可见期间轮询，隐藏后停止，返回时重新读取', async () => {
    vi.useFakeTimers();
    const api = createStubApi();
    const wrapper = mount(TeamsListView, {
      attachTo: document.body, props: { api, callbacks: callbacks(), visible: true },
    });
    mounted.push(wrapper);
    await flushPromises();
    const initial = vi.mocked(api.list).mock.calls.length;
    await vi.advanceTimersByTimeAsync(3100);
    await flushPromises();
    expect(vi.mocked(api.list).mock.calls.length).toBeGreaterThan(initial);
    await wrapper.setProps({ visible: false });
    await flushPromises();
    const hidden = vi.mocked(api.list).mock.calls.length;
    await vi.advanceTimersByTimeAsync(9000);
    await flushPromises();
    expect(vi.mocked(api.list)).toHaveBeenCalledTimes(hidden);
    await wrapper.setProps({ visible: true });
    await flushPromises();
    expect(vi.mocked(api.list).mock.calls.length).toBeGreaterThan(hidden);
  });

  it('迟到的其他 Team 受理回执不会覆盖当前 Team 的请求筛选', async () => {
    const api = createStubApi();
    const wrapper = mount(TeamsPageShell, {
      attachTo: document.body,
      props: { api, callbacks: callbacks(),
        initialNavigation: { view: 'detail', team_id: teamUnsynced.id, section: 'invitations' } },
    });
    mounted.push(wrapper);
    await flushPromises();
    const join = wrapper.findComponent(TeamJoinModal);
    const currentReceipt = { ...joinReceipt(), id: '9102', team_id: teamUnsynced.id };
    join.vm.$emit('submitted', currentReceipt, teamUnsynced.id);
    await flushPromises();
    expect(wrapper.findComponent(TeamInvitationsTab).props('joinRequestId')).toBe('9102');
    join.vm.$emit('submitted', joinReceipt(), teamAlpha.id);
    await flushPromises();
    expect(wrapper.findComponent(TeamInvitationsTab).props('joinRequestId')).toBe('9102');
    wrapper.vm.navigate({ view: 'detail', team_id: teamAlpha.id, section: 'invitations' });
    await flushPromises();
    expect(wrapper.findComponent(TeamInvitationsTab).props('joinRequestId')).toBe('9101');
  });
});
