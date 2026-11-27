// @vitest-environment jsdom
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import TeamsPageShell from './TeamsPageShell.vue';
import type { TeamsApi } from '../../api/teams';
import type { TeamDTO, TeamsHostCallbacks } from './contracts';

function polyfillDialog() {
  if (!HTMLDialogElement.prototype.showModal) {
    HTMLDialogElement.prototype.showModal = function showModal() {
      this.setAttribute('open', '');
    };
  }
  if (!HTMLDialogElement.prototype.close) {
    HTMLDialogElement.prototype.close = function close() {
      this.removeAttribute('open');
    };
  }
}

const teamAlpha: TeamDTO = {
  team_id: '9007199254740993',
  revision: 8,
  workspace_id: 'ws-alpha-core',
  workspace_name: 'Alpha Growth Lab',
  display_name: 'Alpha 核心研发组',
  effective_name: 'Alpha 核心研发组',
  plan_type: 'team',
  manager_account: {
    account_id: '1001',
    email: 'owner-alpha@example.test',
    archived: true,
    account_status: 'active',
  },
  manager_role: 'owner',
  can_manage: true,
  seat_policy: 'remaining_purchased_only',
  purchased_seats: 15,
  planned_member_limit: 12,
  confirmed_member_count: 7,
  pending_invite_count: 2,
  processing_count: 1,
  capacity: {
    basis: 'hybrid_min',
    effective_limit: 12,
    occupied_count: 9,
    remaining_before_limit: 3,
    can_accept_new_joins: true,
    blocking_reason_code: null,
  },
  last_sync_status: 'failed',
  last_synced_at: '2026-11-27T14:48:12Z',
  last_sync_task_id: '50101',
  last_sync_run_id: '60101',
  last_sync_error: {
    reason_code: 'team_sync_failed',
    summary: '远端工作区成员同步超时',
    detail: 'HTTP 504',
  },
  created_at: '2026-11-20T08:00:00Z',
  updated_at: '2026-11-27T14:48:12Z',
};

const teamUnsynced: TeamDTO = {
  ...teamAlpha,
  team_id: '9007199254740994',
  workspace_id: 'ws-null-counts',
  workspace_name: 'Null Counts Team',
  display_name: null,
  effective_name: 'Null Counts Team',
  purchased_seats: null,
  planned_member_limit: null,
  confirmed_member_count: null,
  pending_invite_count: null,
  processing_count: 0,
  capacity: {
    basis: 'unknown',
    effective_limit: null,
    occupied_count: null,
    remaining_before_limit: null,
    can_accept_new_joins: false,
    blocking_reason_code: 'team_limit_required',
  },
  last_sync_status: 'never',
  last_synced_at: null,
  last_sync_error: null,
};

function createStubApi(): TeamsApi {
  return {
    list: vi.fn<TeamsApi['list']>(async () => ({
      items: [teamAlpha, teamUnsynced],
      total: 2,
      page: 1,
      page_size: 20,
      facets: {},
      summary: { total_teams: 2, syncing_teams: 1, attention_teams: 1 },
    })),
    detail: vi.fn<TeamsApi['detail']>(async (id: string) => ({
      team: id === teamUnsynced.team_id ? teamUnsynced : teamAlpha,
      actions: {
        sync: { enabled: true, reason_code: null, reason: null },
        reverify: { enabled: true, reason_code: null, reason: null },
        join: { enabled: true, reason_code: null, reason: null },
      },
      permission_verified_at: '2026-11-27T14:40:00Z',
    })),
    createBindingProbe: vi.fn<TeamsApi['createBindingProbe']>(),
    getBindingProbe: vi.fn<TeamsApi['getBindingProbe']>(),
    createTeam: vi.fn<TeamsApi['createTeam']>(),
    updateTeam: vi.fn<TeamsApi['updateTeam']>(),
    syncTeam: vi.fn<TeamsApi['syncTeam']>(async teamId => ({
      team_id: teamId,
      status: 'queued',
      task_id: '50200',
      run_id: '60200',
      reused: false,
    })),
    syncTeamsBulk: vi.fn<TeamsApi['syncTeamsBulk']>(async ids => ({
      queued_count: ids.length,
      reused_count: 0,
      skipped_count: 0,
      items: [],
    })),
    reverifyTeam: vi.fn<TeamsApi['reverifyTeam']>(),
    listMembers: vi.fn<TeamsApi['listMembers']>(async () => ({
      items: [
        {
          member_id: '7001',
          team_id: teamAlpha.team_id,
          remote_user_id: 'u1',
          email: 'owner-alpha@example.test',
          display_name: 'Alpha Lead',
          role: 'owner',
          membership_state: 'joined',
          joined_at: '2026-11-20T08:05:00Z',
          last_seen_in_sync_at: '2026-11-27T14:48:12Z',
          local_account: {
            account_id: '1001',
            email: 'owner-alpha@example.test',
            archived: true,
            account_status: 'active',
            current_plan_type: 'team',
          },
          latest_task_id: '50101',
          latest_run_id: '60101',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      facets: {},
    })),
    listInvitations: vi.fn<TeamsApi['listInvitations']>(async () => ({
      items: [
        {
          invitation_id: '8001',
          team_id: teamAlpha.team_id,
          join_request_id: '9101',
          remote_invite_id: 'inv_1',
          email: 'worker-01@example.test',
          invite_role: 'member',
          target_account: {
            account_id: '2011',
            email: 'worker-01@example.test',
            archived: false,
            account_status: 'active',
            has_access_token: true,
            has_account_password: true,
            totp_enabled: false,
            email_invalid: false,
          },
          invitation_state: 'pending',
          membership_state: 'not_joined',
          execution_status: 'failed',
          stage: 'authenticate_target',
          waiting_reason_code: null,
          latest_task_id: '50402',
          latest_run_id: '60402',
          error: {
            reason_code: 'team_invite_mail_timeout',
            summary: '等待邀请邮件超时',
            detail: 'Timeout after 90s',
          },
          actions: { can_continue: true, can_retry: true, can_open_task: true, disabled_reason_code: null },
          invited_at: '2026-11-27T14:20:00Z',
          accepted_at: null,
          updated_at: '2026-11-27T14:22:00Z',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      facets: {},
    })),
    getInvitation: vi.fn<TeamsApi['getInvitation']>(),
    listCandidates: vi.fn<TeamsApi['listCandidates']>(async () => ({ items: [], total: 0, page: 1, page_size: 20, facets: {} })),
    resolveCandidates: vi.fn<TeamsApi['resolveCandidates']>(),
    previewJoin: vi.fn<TeamsApi['previewJoin']>(),
    submitJoin: vi.fn<TeamsApi['submitJoin']>(),
    getJoinRequest: vi.fn<TeamsApi['getJoinRequest']>(),
    continueInvitation: vi.fn<TeamsApi['continueInvitation']>(async (_t, invId) => ({
      invitation_id: invId,
      outcome: 'queued',
      task_id: '50500',
      run_id: '60500',
    })),
    retryInvitation: vi.fn<TeamsApi['retryInvitation']>(async (_t, invId) => ({
      invitation_id: invId,
      outcome: 'queued',
      task_id: '50501',
      run_id: '60501',
    })),
    continueInvitationsBulk: vi.fn<TeamsApi['continueInvitationsBulk']>(),
    retryInvitationsBulk: vi.fn<TeamsApi['retryInvitationsBulk']>(),
    freezeAccountSelection: vi.fn<TeamsApi['freezeAccountSelection']>(),
  };
}

beforeEach(() => {
  polyfillDialog();
  vi.stubGlobal('scrollTo', vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('TeamsPageShell 主列表、详情双页签与状态展示契约', () => {
  it('列表独立展示非相加指标，null 显示为待同步而不伪装成 0，并保持 64 位字符串导航', async () => {
    const api = createStubApi();
    const navEvents: unknown[] = [];
    const callbacks: TeamsHostCallbacks = {
      notify: vi.fn(),
      formatDateTime: v => v || '—',
      openTask: vi.fn(),
      openTasksForTeam: vi.fn(),
      openAccountDetail: vi.fn(),
      openAccountsCandidateMode: vi.fn(),
      onNavigation: (state, mode) => navEvents.push({ state, mode }),
    };

    const wrapper = mount(TeamsPageShell, {
      attachTo: document.body,
      props: { api, callbacks },
    });
    await flushPromises();

    expect(wrapper.text()).toContain('Alpha 核心研发组');
    expect(wrapper.text()).toContain('Null Counts Team');
    expect(wrapper.text()).toContain('待同步');
    expect(wrapper.text()).toContain('需设本地上限');
    expect(wrapper.text()).toContain('已归档');

    // 点击进入详情
    const openBtn = wrapper.findAll('.tm-workspace-name-btn')[0]!;
    await openBtn.trigger('click');
    await flushPromises();

    expect(navEvents.at(-1)).toEqual({
      state: { tab: 'teams', view: 'detail', team_id: '9007199254740993', section: 'members' },
      mode: 'push',
    });

    // 验证同步失败保留旧快照横幅
    expect(wrapper.text()).toContain('最近一次同步失败');
    expect(wrapper.text()).toContain('2026-11-27T14:48:12Z');

    // 验证成员表严格 7 列
    const memberHeaders = wrapper.findAll('section[aria-label="工作区成员列表"] thead th');
    expect(memberHeaders).toHaveLength(7);

    // 切换到邀请页签，验证严格 6 列双事实与继续加入动作
    const invTabBtn = wrapper.findAll('.tm-tab-btn').find(b => b.text().includes('邀请'))!;
    await invTabBtn.trigger('click');
    await flushPromises();

    const invHeaders = wrapper.findAll('div[aria-label="邀请与入组表格，可横向滚动"] thead th');
    expect(invHeaders).toHaveLength(6);
    expect(wrapper.text()).toContain('待接受邀请');
    expect(wrapper.text()).toContain('成员：未入组');
    expect(wrapper.text()).toContain('等待邀请信超时');

    const continueBtn = wrapper.findAll('button').find(b => b.text() === '继续加入')!;
    await continueBtn.trigger('click');
    await flushPromises();
    expect(api.continueInvitation).toHaveBeenCalledWith('9007199254740993', '8001');

    // 返回列表
    await wrapper.find('.tm-back-btn').trigger('click');
    await flushPromises();
    expect(wrapper.vm.navigationState()).toEqual({ tab: 'teams', view: 'list' });
    wrapper.unmount();
  });
});
