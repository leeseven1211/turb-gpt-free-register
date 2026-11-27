// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import TeamBindModal from './TeamBindModal.vue';
import TeamCandidatePickerModal from './TeamCandidatePickerModal.vue';
import TeamJoinModal from './TeamJoinModal.vue';
import { TeamApiError, type TeamsApi } from '../../api/teams';
import type { TeamDTO } from './contracts';

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

const sampleTeam: TeamDTO = {
  team_id: '9007199254740993',
  revision: 4,
  workspace_id: 'ws-alpha-01',
  workspace_name: 'Alpha Studio',
  display_name: 'Alpha 研发组',
  effective_name: 'Alpha 研发组',
  plan_type: 'team',
  manager_account: {
    account_id: '1001',
    email: 'owner@example.test',
    archived: true,
    account_status: 'active',
  },
  manager_role: 'owner',
  can_manage: true,
  seat_policy: 'remaining_purchased_only',
  purchased_seats: 10,
  planned_member_limit: 8,
  confirmed_member_count: 5,
  pending_invite_count: 1,
  processing_count: 0,
  capacity: {
    basis: 'hybrid_min',
    effective_limit: 8,
    occupied_count: 6,
    remaining_before_limit: 2,
    can_accept_new_joins: true,
    blocking_reason_code: null,
  },
  last_sync_status: 'success',
  last_synced_at: '2026-11-27T14:00:00Z',
  last_sync_task_id: '5001',
  last_sync_run_id: '6001',
  last_sync_error: null,
  created_at: '2026-11-20T08:00:00Z',
  updated_at: '2026-11-27T14:00:00Z',
};

function createStubTeamsApi(overrides: Partial<TeamsApi> = {}): TeamsApi {
  const base: TeamsApi = {
    list: vi.fn<TeamsApi['list']>(async () => ({
      items: [sampleTeam],
      total: 1,
      page: 1,
      page_size: 20,
      facets: {},
      summary: { total_teams: 1, syncing_teams: 0, attention_teams: 0 },
    })),
    detail: vi.fn<TeamsApi['detail']>(async () => ({
      team: sampleTeam,
      actions: {
        sync: { enabled: true, reason_code: null, reason: null },
        reverify: { enabled: true, reason_code: null, reason: null },
        join: { enabled: true, reason_code: null, reason: null },
      },
      permission_verified_at: '2026-11-27T14:00:00Z',
    })),
    createBindingProbe: vi.fn<TeamsApi['createBindingProbe']>(async () => ({
      probe_id: '8801',
      status: 'running',
      task_id: '5100',
      run_id: '6100',
    })),
    getBindingProbe: vi.fn<TeamsApi['getBindingProbe']>(async () => ({
      probe_id: '8801',
      probe_revision: 'rev_1',
      manager_account_id: '9007199254740999',
      manager_email: 'manager@example.test',
      target_workspace_id: null,
      status: 'success',
      stage: 'completed',
      task_id: '5100',
      run_id: '6100',
      expires_at: '2099-01-01T00:00:00Z',
      suggested_workspace_id: 'ws-new-01',
      workspaces: [
        {
          workspace_id: 'ws-new-01',
          workspace_name: 'New Team Workspace',
          plan_type: 'team',
          is_team_workspace: true,
          role: 'owner',
          can_manage: true,
          purchased_seats: null,
          confirmed_member_count: 2,
          pending_invite_count: 0,
          already_bound_team_id: null,
          selectable: true,
          disabled_reason_code: null,
          disabled_reason: null,
        },
        {
          workspace_id: 'ws-bound-02',
          workspace_name: 'Already Bound',
          plan_type: 'team',
          is_team_workspace: true,
          role: 'admin',
          can_manage: true,
          purchased_seats: 5,
          confirmed_member_count: 3,
          pending_invite_count: 0,
          already_bound_team_id: '9007199254740993',
          selectable: false,
          disabled_reason_code: 'team_already_bound',
          disabled_reason: '该工作区已绑定',
        },
      ],
      error: null,
    })),
    createTeam: vi.fn<TeamsApi['createTeam']>(async () => ({
      team: sampleTeam,
      sync: { status: 'queued', task_id: '5200', run_id: '6200', reused: false },
    })),
    updateTeam: vi.fn<TeamsApi['updateTeam']>(async () => ({
      team: { ...sampleTeam, revision: 5, planned_member_limit: 12 },
    })),
    syncTeam: vi.fn<TeamsApi['syncTeam']>(),
    syncTeamsBulk: vi.fn<TeamsApi['syncTeamsBulk']>(),
    reverifyTeam: vi.fn<TeamsApi['reverifyTeam']>(),
    listMembers: vi.fn<TeamsApi['listMembers']>(),
    listInvitations: vi.fn<TeamsApi['listInvitations']>(),
    getInvitation: vi.fn<TeamsApi['getInvitation']>(),
    listCandidates: vi.fn<TeamsApi['listCandidates']>(async () => ({
      items: [
        {
          account_id: '3001',
          email: 'free-01@example.test',
          user_name: 'Free 01',
          archived: false,
          account_status: 'active',
          current_plan_type: 'free',
          has_access_token: true,
          has_account_password: true,
          totp_enabled: true,
          email_invalid: false,
          email_source: 'cloudflare',
          active_team: null,
          eligibility: { selectable: true, state: 'eligible', reason_code: null, reason: null },
        },
        {
          account_id: '3002',
          email: 'other-team@example.test',
          user_name: 'Other Team',
          archived: false,
          account_status: 'active',
          current_plan_type: 'team',
          has_access_token: true,
          has_account_password: true,
          totp_enabled: true,
          email_invalid: false,
          email_source: 'outlook',
          active_team: {
            team_id: '999',
            effective_name: 'Other Team',
            role: 'member',
            membership_state: 'joined',
          },
          eligibility: {
            selectable: false,
            state: 'another_team',
            reason_code: 'team_already_in_other_team',
            reason: '单账号最多加入一个工作区',
          },
        },
      ],
      total: 2,
      page: 1,
      page_size: 20,
      facets: {},
    })),
    resolveCandidates: vi.fn<TeamsApi['resolveCandidates']>(async () => ({
      matched: [
        {
          account_id: '3001',
          email: 'free-01@example.test',
          user_name: 'Free 01',
          archived: false,
          account_status: 'active',
          current_plan_type: 'free',
          has_access_token: true,
          has_account_password: true,
          totp_enabled: true,
          email_invalid: false,
          email_source: 'cloudflare',
          active_team: null,
          eligibility: { selectable: true, state: 'eligible', reason_code: null, reason: null },
        },
      ],
      not_found: ['ghost@example.test'],
      ambiguous: [],
    })),
    previewJoin: vi.fn<TeamsApi['previewJoin']>(async () => ({
      team_id: sampleTeam.team_id,
      snapshot_revision: 4,
      snapshot_at: '2026-11-27T15:00:00Z',
      team_last_synced_at: '2026-11-27T14:00:00Z',
      requires_sync: false,
      counts: {
        selected_total: 2,
        new_join_count: 1,
        continue_invite_count: 1,
        already_member_skip_count: 0,
        already_processing_skip_count: 0,
        another_team_skip_count: 0,
        missing_auth_skip_count: 0,
        unavailable_skip_count: 0,
        email_mismatch_skip_count: 0,
      },
      capacity: {
        seat_policy: 'remaining_purchased_only',
        basis: 'hybrid_min',
        purchased_seats: 10,
        planned_member_limit: 8,
        effective_limit: 8,
        occupied_count: 6,
        additional_required: 1,
        remaining_after_submit: 1,
        exceeds_limit: false,
        can_submit: true,
        blocking_reason_code: null,
        blocking_reason: null,
      },
      sample_items: [],
    })),
    submitJoin: vi.fn<TeamsApi['submitJoin']>(async () => ({
      join_request_id: '9501',
      team_id: sampleTeam.team_id,
      status: 'accepted',
      summary: { requested_count: 2, queued_count: 2, reused_active_count: 0, skipped_count: 0 },
      items: [
        {
          account_id: '3001',
          email: 'free-01@example.test',
          outcome: 'queued',
          invitation_id: '8101',
          task_id: '5901',
          run_id: '6901',
          reason_code: null,
          reason: null,
        },
      ],
      total_items: 1,
      page: 1,
      page_size: 20,
    })),
    getJoinRequest: vi.fn<TeamsApi['getJoinRequest']>(),
    continueInvitation: vi.fn<TeamsApi['continueInvitation']>(),
    retryInvitation: vi.fn<TeamsApi['retryInvitation']>(),
    continueInvitationsBulk: vi.fn<TeamsApi['continueInvitationsBulk']>(),
    retryInvitationsBulk: vi.fn<TeamsApi['retryInvitationsBulk']>(),
    freezeAccountSelection: vi.fn<TeamsApi['freezeAccountSelection']>(),
  };
  return { ...base, ...overrides };
}

beforeEach(() => {
  polyfillDialog();
  vi.useFakeTimers();
  vi.stubGlobal('scrollTo', vi.fn());
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      new Response(
        '{"ok":true,"items":[{"id":9007199254740999,"email":"manager@example.test","archived":true,"account_status":"active","team_memberships":[]}]}',
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    ),
  );
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('Team 模态框交互契约测试', () => {
  it('TeamBindModal：保留 64 位母号 ID、自动单选 suggested_workspace_id 并处理已绑定工作区跳转', async () => {
    const api = createStubTeamsApi({
      createTeam: vi.fn(async () => {
        throw new TeamApiError('该工作区已在本地绑定', 409, {
          code: 'team_already_bound',
          details: { existing_team_id: '9007199254740993' },
        });
      }),
    });
    const wrapper = mount(TeamBindModal, {
      attachTo: document.body,
      props: { open: true, api, mode: 'bind', visible: true },
    });
    await flushPromises();
    expect(wrapper.text()).toContain('manager@example.test');
    expect(wrapper.text()).toContain('#9007199254740999');

    const probeBtn = wrapper.findAll('button').find(b => b.text().includes('探测并核验工作区'));
    expect(probeBtn).toBeTruthy();
    await probeBtn!.trigger('click');
    await flushPromises();
    expect(api.createBindingProbe).toHaveBeenCalledWith(
      { manager_account_id: '9007199254740999', target_workspace_id: null },
      expect.any(AbortSignal),
    );

    vi.advanceTimersByTime(1600);
    await flushPromises();
    expect(wrapper.text()).toContain('New Team Workspace');
    expect(wrapper.text()).toContain('未返回席位');

    const submitBtn = wrapper.findAll('button').find(b => b.text().includes('确认绑定工作区'));
    expect(submitBtn!.attributes('disabled')).toBeUndefined();
    await submitBtn!.trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('打开已绑定 Team');
    const jumpBtn = wrapper.findAll('button').find(b => b.text().includes('打开已绑定 Team'));
    await jumpBtn!.trigger('click');
    expect(wrapper.emitted('openExistingTeam')?.[0]).toEqual(['9007199254740993']);
    wrapper.unmount();
  });

  it('TeamCandidatePickerModal：单账号单 Team 置灰其他 Team 账号，支持粘贴批量解析并输出快照', async () => {
    const api = createStubTeamsApi();
    const wrapper = mount(TeamCandidatePickerModal, {
      attachTo: document.body,
      props: { open: true, api, team: sampleTeam, visible: true },
    });
    await flushPromises();

    const rows = wrapper.findAll('.tm-candidate-row');
    expect(rows).toHaveLength(2);
    expect(rows[1]!.classes()).toContain('is-disabled');
    expect(rows[1]!.text()).toContain('Other Team');

    const pasteToggle = wrapper.findAll('button').find(b => b.text().includes('批量粘贴邮箱或账号 ID'));
    await pasteToggle!.trigger('click');
    await wrapper.find('textarea').setValue('free-01@example.test\nghost@example.test');
    const resolveBtn = wrapper.findAll('button').find(b => b.text().includes('解析并勾选'));
    await resolveBtn!.trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('ghost@example.test');
    expect(wrapper.text()).toContain('已选 1 个候选账号');

    const nextBtn = wrapper.findAll('button').find(b => b.text().includes('下一步：本地预览与席位核对'));
    await nextBtn!.trigger('click');
    expect(wrapper.emitted('confirmCandidates')?.[0]).toEqual([
      {
        accountIds: ['3001'],
        expectedEmails: { '3001': 'free-01@example.test' },
      },
    ]);
    wrapper.unmount();
  });

  it('TeamJoinModal：team_limit_required 时支持内联补设人数上限重算，提交后切换受理回执视图', async () => {
    let limitSet = false;
    const api = createStubTeamsApi({
      previewJoin: vi.fn<TeamsApi['previewJoin']>(async () => ({
        team_id: sampleTeam.team_id,
        snapshot_revision: limitSet ? 5 : 4,
        snapshot_at: '2026-11-27T15:00:00Z',
        team_last_synced_at: '2026-11-27T14:00:00Z',
        requires_sync: false,
        counts: {
          selected_total: 1,
          new_join_count: 1,
          continue_invite_count: 0,
          already_member_skip_count: 0,
          already_processing_skip_count: 0,
          another_team_skip_count: 0,
          missing_auth_skip_count: 0,
          unavailable_skip_count: 0,
          email_mismatch_skip_count: 0,
        },
        capacity: limitSet
          ? {
              seat_policy: 'remaining_purchased_only',
              basis: 'planned_member_limit',
              purchased_seats: null,
              planned_member_limit: 12,
              effective_limit: 12,
              occupied_count: 6,
              additional_required: 1,
              remaining_after_submit: 5,
              exceeds_limit: false,
              can_submit: true,
              blocking_reason_code: null,
              blocking_reason: null,
            }
          : {
              seat_policy: 'remaining_purchased_only',
              basis: 'unknown',
              purchased_seats: null,
              planned_member_limit: null,
              effective_limit: null,
              occupied_count: 6,
              additional_required: 1,
              remaining_after_submit: null,
              exceeds_limit: false,
              can_submit: false,
              blocking_reason_code: 'team_limit_required',
              blocking_reason: '需先设置本地计划人数上限',
            },
        sample_items: [],
      })),
      updateTeam: vi.fn(async () => {
        limitSet = true;
        return { team: { ...sampleTeam, revision: 5, purchased_seats: null, planned_member_limit: 12 } };
      }),
    });

    const wrapper = mount(TeamJoinModal, {
      attachTo: document.body,
      props: {
        open: true,
        api,
        initialTeam: { ...sampleTeam, purchased_seats: null, planned_member_limit: null },
        target: { mode: 'explicit', accountIds: ['3001'], expectedEmails: { '3001': 'free-01@example.test' } },
        visible: true,
        formatDateTime: v => v || '—',
      },
    });
    await flushPromises();

    expect(wrapper.text()).toContain('需先设置本地计划人数上限');
    const confirmBefore = wrapper.findAll('button').find(b => b.text().includes('确认发起加入'))!;
    expect(confirmBefore.attributes('disabled')).toBeDefined();

    await wrapper.find('input[aria-label="本地计划人数上限"]').setValue('12');
    const setLimitBtn = wrapper.findAll('button').find(b => b.text().includes('设置本地计划人数上限并重新核算'))!;
    await setLimitBtn.trigger('click');
    await flushPromises();

    expect(api.updateTeam).toHaveBeenCalled();
    const confirmAfter = wrapper.findAll('button').find(b => b.text().includes('确认发起加入'))!;
    expect(confirmAfter.attributes('disabled')).toBeUndefined();

    await confirmAfter.trigger('click');
    await flushPromises();

    expect(api.submitJoin).toHaveBeenCalledWith(
      '9007199254740993',
      {
        account_ids: ['3001'],
        expected_emails: { '3001': 'free-01@example.test' },
        expected_team_revision: 5,
      },
    );
    expect(wrapper.text()).toContain('加入请求受理回执');
    expect(wrapper.text()).toContain('#9501');
    wrapper.unmount();
  });
});
