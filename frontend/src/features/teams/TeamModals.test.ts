// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import TeamBindModal from './TeamBindModal.vue';
import TeamCandidatePickerModal from './TeamCandidatePickerModal.vue';
import TeamJoinModal from './TeamJoinModal.vue';
import { TeamApiError, type TeamsApi } from '../../api/teams';
import type { CandidateResolveResponse, JoinRequestDTO, TeamDTO } from './contracts';

function pendingResponse<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function resolvedCandidate(accountId: string, email: string): CandidateResolveResponse {
  return { requested_count: 1, unique_count: 1, duplicate_count: 0,
    items: [{ input: accountId, match_status: 'matched', reason_code: null, candidates: [{
      account: { id: accountId, email, archived: false }, category: 'new',
      auth_capability: 'available', has_access_token: true, has_password: true, totp_enabled: true,
      email_status: 'unmarked', other_teams: [], disabled: false, reason_code: null,
    }] }] };
}

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
  id: '9007199254740993',
  revision: 4,
  workspace_id: 'ws-alpha-01',
  name: 'Alpha Studio',
  display_name: 'Alpha 研发组',
  manager_account: { id: '1001', email: 'owner@example.test', archived: true },
  role: 'owner',
  purchased_seats: 10,
  planned_member_limit: 8,
  confirmed_member_count: 5,
  pending_invite_count: 1,
  processing_count: 0,
  last_sync_status: 'success',
  last_synced_at: '2026-11-27T14:00:00Z',
};

function createStubTeamsApi(overrides: Partial<TeamsApi> = {}): TeamsApi {
  const base: TeamsApi = {
    list: vi.fn<TeamsApi['list']>(async () => ({
      items: [sampleTeam], total: 1, page: 1, page_size: 20, revision: 'teams:1',
    })),
    detail: vi.fn<TeamsApi['detail']>(async () => ({
      team: sampleTeam,
      actions: {
        sync: { enabled: true, reason_code: null },
        reverify: { enabled: true, reason_code: null },
        join: { enabled: true, reason_code: null },
      },
      permission_verified_at: '2026-11-27T14:00:00Z',
    })),
    createBindingProbe: vi.fn<TeamsApi['createBindingProbe']>(async () => ({
      probe_id: '8801', status: 'running', task_id: '5100', run_id: '6100',
    })),
    getBindingProbe: vi.fn<TeamsApi['getBindingProbe']>(async () => ({
      id: '8801', revision: 7,
      manager_account: { id: '9007199254740999', email: 'manager@example.test', archived: true },
      status: 'success', stage: 'complete', task_id: '5100', run_id: '6100',
      completed_at: '2026-11-27T14:00:00Z', expires_at: '2099-01-01T00:00:00Z',
      suggested_workspace_id: 'ws-new-01',
      workspaces: [{
        workspace_id: 'ws-new-01', workspace_type: 'team', name: 'New Team Workspace',
        role: 'owner', can_manage: true, purchased_seats: null,
        capabilities: { read_members: true, read_invitations: true, invite_members: null },
      }],
      error_info: null,
    })),
    createTeam: vi.fn<TeamsApi['createTeam']>(async () => ({
      team: sampleTeam,
      sync: { accepted: true, reused: false, team_id: sampleTeam.id,
        task_id: '5200', run_id: '6200', status: 'queued' },
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
    listCandidates: vi.fn<TeamsApi['listCandidates']>(),
    resolveCandidates: vi.fn<TeamsApi['resolveCandidates']>(),
    previewJoin: vi.fn<TeamsApi['previewJoin']>(),
    submitJoin: vi.fn<TeamsApi['submitJoin']>(),
    getJoinRequest: vi.fn<TeamsApi['getJoinRequest']>(),
    continueInvitation: vi.fn<TeamsApi['continueInvitation']>(),
    retryInvitation: vi.fn<TeamsApi['retryInvitation']>(),
    continueInvitationsBulk: vi.fn<TeamsApi['continueInvitationsBulk']>(),
    retryInvitationsBulk: vi.fn<TeamsApi['retryInvitationsBulk']>(),
    freezeAccountSelection: vi.fn<TeamsApi['freezeAccountSelection']>(),
  };
  return { ...base, ...overrides };
}

const joinTeam: TeamDTO = {
  id: '9007199254740993', revision: 4, workspace_id: 'ws-alpha-01', name: 'Alpha Studio', display_name: 'Alpha 研发组',
  manager_account: { id: '1001', email: 'owner@example.test', archived: true }, role: 'owner',
  purchased_seats: 10, planned_member_limit: 8, confirmed_member_count: 5, pending_invite_count: 1,
  processing_count: 0, last_sync_status: 'success', last_synced_at: '2026-11-27T14:00:00Z',
};
function joinPreview(limitSet = true) {
  return { team_id: joinTeam.id, selection_id: null, selection_revision: null, snapshot_revision: '4',
    snapshot_at: '2026-11-27T15:00:00Z', team_last_synced_at: '2026-11-27T14:00:00Z', requires_sync: false,
    counts: { requested_count: 1, unique_count: 1, duplicate_count: 0, unavailable_count: 0,
      another_team_count: 0, already_member_count: 0, same_team_active_count: 0, missing_auth_count: 0,
      resume_invite_count: 0, new_count: 1, eligible_count: 1 },
    capacity: { basis: limitSet ? 'planned_member_limit' as const : 'unavailable' as const,
      purchased_seats: null, planned_member_limit: limitSet ? 12 : null, effective_limit: limitSet ? 12 : null,
      occupied_count: 6, additional_required: 1, available_count: limitSet ? 6 : null,
      can_submit: limitSet, blocking_reason_code: limitSet ? null : 'team_limit_required' as const } };
}
function joinReceipt() {
  return { id: '9501', team_id: joinTeam.id, operation: 'join' as const, accepted: true as const, reused: false,
    status: 'preparing' as const, waiting_reason_code: null, selection_id: null, selection_revision: null,
    batch_id: '5701', task_id: '5901', run_id: '6901', created_at: '2026-11-27T15:00:00Z',
    items_url: `/api/teams/${joinTeam.id}/join-requests/9501`, capacity: joinPreview().capacity,
    counts: { requested_count: 1, unique_count: 1, duplicate_count: 0, pending_count: 1,
      accepted_count: 0, reused_count: 0, skipped_count: 0, failed_count: 0 } };
}
function createJoinApi(overrides: Partial<TeamsApi> = {}): TeamsApi {
  const candidate = { account: { id: '3001', email: 'free-01@example.test', archived: false },
    category: 'new' as const, auth_capability: 'available' as const, has_access_token: true,
    has_password: true, totp_enabled: true, email_status: 'unmarked' as const,
    other_teams: [], disabled: false, reason_code: null };
  return createStubTeamsApi({
    listCandidates: vi.fn(async () => ({ items: [candidate, { ...candidate,
      account: { id: '3002', email: 'other-team@example.test', archived: false }, category: 'another_team' as const,
      other_teams: [{ id: '999', workspace_id: 'other-workspace', name: 'Other Team', display_name: null }],
      disabled: true, reason_code: 'already_in_another_team' }], total: 2, page: 1, page_size: 20, revision: 'candidates:1' })),
    resolveCandidates: vi.fn(async () => ({ requested_count: 2, unique_count: 2, duplicate_count: 0,
      items: [{ input: 'free-01@example.test', match_status: 'matched' as const, candidates: [candidate], reason_code: null },
        { input: 'ghost@example.test', match_status: 'not_found' as const, candidates: [], reason_code: 'account_not_found' }] })),
    previewJoin: vi.fn(async () => joinPreview()), submitJoin: vi.fn(async () => joinReceipt()),
    getJoinRequest: vi.fn(async () => ({ request: joinReceipt(), total: 1, page: 1, page_size: 20, revision: 'request:1',
      items: [{ ordinal: 0, account_id: '3001', invitation_id: null, acceptance_status: 'pending' as const,
        task_id: null, run_id: null, execution_status: 'none' as const, reason_code: null, message: null }] })),
    ...overrides,
  });
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
      { manager_account_id: '9007199254740999' },
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

  it('TeamCandidatePickerModal：真实候选与解析 DTO 勾选并冻结邮箱快照', async () => {
    const api = createJoinApi();
    const wrapper = mount(TeamCandidatePickerModal, { attachTo: document.body,
      props: { open: true, api, team: joinTeam, visible: true } });
    await flushPromises();
    const rows = wrapper.findAll('.tm-candidate-row');
    expect(rows).toHaveLength(2);
    expect(rows[1]!.classes()).toContain('is-disabled');
    expect(rows[1]!.text()).toContain('Other Team');
    await wrapper.findAll('button').find(b => b.text().includes('批量粘贴邮箱或账号 ID'))!.trigger('click');
    await wrapper.find('textarea').setValue('free-01@example.test\nghost@example.test');
    await wrapper.findAll('button').find(b => b.text().includes('解析并勾选'))!.trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('ghost@example.test');
    expect(wrapper.text()).toContain('已选 1 个候选账号');
    await wrapper.findAll('button').find(b => b.text().includes('下一步：本地预览与席位核对'))!.trigger('click');
    expect(wrapper.emitted('confirmCandidates')?.[0]).toEqual([{
      accountIds: ['3001'], expectedEmails: { '3001': 'free-01@example.test' },
    }]);
    wrapper.unmount();
  });
  it('TeamJoinModal：七桶预检补上限，仅提交目标并首次读取分页回执', async () => {
    let limitSet = false;
    const api = createJoinApi({ previewJoin: vi.fn(async () => joinPreview(limitSet)),
      updateTeam: vi.fn(async () => { limitSet = true;
        return { team: { ...joinTeam, revision: 5, purchased_seats: null, planned_member_limit: 12 } }; }) });
    const wrapper = mount(TeamJoinModal, { attachTo: document.body, props: {
      open: true, api, initialTeam: { ...joinTeam, purchased_seats: null, planned_member_limit: null },
      target: { mode: 'explicit', accountIds: ['3001'], expectedEmails: { '3001': 'free-01@example.test' } },
      visible: true, formatDateTime: value => value || '—' } });
    await flushPromises();
    expect(wrapper.text()).toContain('需先设置本地计划人数上限');
    const confirm = () => wrapper.findAll('button').find(b => b.text().includes('确认发起加入'))!;
    expect(confirm().attributes('disabled')).toBeDefined();
    await wrapper.find('input[aria-label="本地计划人数上限"]').setValue('12');
    await wrapper.findAll('button').find(b => b.text().includes('设置本地计划人数上限并重新核算'))!.trigger('click');
    await flushPromises();
    expect(confirm().attributes('disabled')).toBeUndefined();
    await confirm().trigger('click');
    await flushPromises();
    expect(api.submitJoin).toHaveBeenCalledWith(joinTeam.id, {
      account_ids: ['3001'], expected_emails: { '3001': 'free-01@example.test' } });
    expect(api.getJoinRequest).toHaveBeenCalledWith(joinTeam.id, '9501', { page: 1, page_size: 20 }, expect.any(AbortSignal));
    expect(wrapper.text()).toContain('#9501');
    expect(wrapper.text()).toContain('#3001');
    expect(wrapper.text()).toContain('待处理');
    expect(wrapper.text()).not.toContain('预检抽样');
    wrapper.unmount();
  });
  it('TeamJoinModal：同 Team 活跃目标仍可提交，selection_revision 为整数', async () => {
    const preview = joinPreview(); preview.counts.new_count = 0; preview.counts.same_team_active_count = 1;
    const api = createJoinApi({ previewJoin: vi.fn(async () => preview) });
    const wrapper = mount(TeamJoinModal, { attachTo: document.body, props: {
      open: true, api, initialTeam: joinTeam, target: { mode: 'selection', selectionId: '71', selectionRevision: 3 },
      visible: true, formatDateTime: value => value || '—' } });
    await flushPromises();
    expect(api.previewJoin).toHaveBeenCalledWith(joinTeam.id, { selection_id: '71', selection_revision: 3 }, expect.any(AbortSignal));
    const confirm = wrapper.findAll('button').find(b => b.text().includes('确认发起加入'))!;
    expect(confirm.attributes('disabled')).toBeUndefined();
    await confirm.trigger('click'); await flushPromises();
    expect(api.submitJoin).toHaveBeenCalledWith(joinTeam.id, { selection_id: '71', selection_revision: 3 });
    wrapper.unmount();
  });
  it.each([
    [1, true],
    [0, false],
  ] as const)('TeamJoinModal：满员时新增占席 %s 可继续受理，等待提示遵循净新增需求', async (additionalRequired, shouldShowWaiting) => {
    const preview = joinPreview();
    preview.capacity.occupied_count = 2;
    preview.capacity.effective_limit = 2;
    preview.capacity.additional_required = additionalRequired;
    preview.capacity.available_count = 0;
    preview.capacity.can_submit = true;
    if (additionalRequired === 0) {
      preview.counts.new_count = 0;
      preview.counts.same_team_active_count = 1;
    }
    const api = createJoinApi({ previewJoin: vi.fn(async () => preview) });
    const wrapper = mount(TeamJoinModal, { attachTo: document.body, props: {
      open: true, api, initialTeam: joinTeam, target: { mode: 'explicit', accountIds: ['3001'] },
      visible: true, formatDateTime: value => value || '—' } });
    try {
      await flushPromises();
      const confirm = wrapper.findAll('button').find(b => b.text().includes('确认发起加入'))!;
      expect(confirm.attributes('disabled')).toBeUndefined();
      expect(wrapper.text().includes('请求受理后将等待可用席位，不会超额增购')).toBe(shouldShowWaiting);
      await confirm.trigger('click');
      await flushPromises();
      expect(api.submitJoin).toHaveBeenCalledWith(joinTeam.id, { account_ids: ['3001'] });
    } finally {
      wrapper.unmount();
    }
  });
  it('TeamCandidatePickerModal：重复解析已选账号不改写首次邮箱快照', async () => {
    const api = createJoinApi();
    const wrapper = mount(TeamCandidatePickerModal, { attachTo: document.body,
      props: { open: true, api, team: joinTeam, visible: true } });
    await flushPromises();
    await wrapper.findAll('.tm-candidate-row')[0]!.find('input').setValue(true);
    vi.mocked(api.resolveCandidates).mockResolvedValueOnce({ requested_count: 1, unique_count: 1, duplicate_count: 0,
      items: [{ input: '3001', match_status: 'matched', reason_code: null, candidates: [{
        account: { id: '3001', email: 'changed@example.test', archived: false }, category: 'new',
        auth_capability: 'available', has_access_token: true, has_password: true, totp_enabled: true,
        email_status: 'unmarked', other_teams: [], disabled: false, reason_code: null,
      }] }] });
    await wrapper.findAll('button').find(b => b.text().includes('批量粘贴邮箱或账号 ID'))!.trigger('click');
    await wrapper.find('textarea').setValue('3001');
    await wrapper.findAll('button').find(b => b.text().includes('解析并勾选'))!.trigger('click');
    await flushPromises();
    await wrapper.findAll('button').find(b => b.text().includes('下一步：本地预览与席位核对'))!.trigger('click');
    expect(wrapper.emitted('confirmCandidates')?.[0]).toEqual([{
      accountIds: ['3001'], expectedEmails: { '3001': 'free-01@example.test' },
    }]);
    wrapper.unmount();
  });

  it.each(['关闭', '隐藏'] as const)('TeamCandidatePickerModal：解析期间%s再恢复可重新解析，旧响应不能结束新解析', async (transition) => {
    const oldResolve = pendingResponse<CandidateResolveResponse>();
    const newResolve = pendingResponse<CandidateResolveResponse>();
    const api = createJoinApi({ resolveCandidates: vi.fn<TeamsApi['resolveCandidates']>()
      .mockImplementationOnce(() => oldResolve.promise)
      .mockImplementationOnce(() => newResolve.promise) });
    const wrapper = mount(TeamCandidatePickerModal, { attachTo: document.body,
      props: { open: true, api, team: joinTeam, visible: true } });
    try {
      await flushPromises();
      const startResolve = async (input: string) => {
        await wrapper.findAll('button').find(b => b.text().includes('批量粘贴邮箱或账号 ID'))!.trigger('click');
        await wrapper.find('textarea').setValue(input);
        await wrapper.findAll('button').find(b => b.text().includes('解析并勾选'))!.trigger('click');
      };
      await startResolve('3001');
      expect(wrapper.find('textarea').attributes('disabled')).toBeDefined();
      if (transition === '关闭') {
        await wrapper.find('button[aria-label="关闭候选选人器"]').trigger('click');
        await wrapper.setProps({ open: false });
      } else {
        await wrapper.setProps({ visible: false });
      }
      expect(wrapper.find('dialog').attributes('aria-busy')).toBe('false');
      await wrapper.setProps(transition === '关闭' ? { open: true } : { visible: true });
      await flushPromises();
      await startResolve('3003');
      expect(wrapper.find('textarea').attributes('disabled')).toBeDefined();
      oldResolve.resolve(resolvedCandidate('3001', 'old@example.test'));
      await flushPromises();
      expect(wrapper.find('textarea').attributes('disabled')).toBeDefined();
      expect(wrapper.text()).toContain('已选 0 个候选账号');
      newResolve.resolve(resolvedCandidate('3003', 'new@example.test'));
      await flushPromises();
      expect(wrapper.find('textarea').attributes('disabled')).toBeUndefined();
      await wrapper.findAll('button').find(b => b.text().includes('下一步：本地预览与席位核对'))!.trigger('click');
      expect(wrapper.emitted('confirmCandidates')?.[0]).toEqual([{
        accountIds: ['3003'], expectedEmails: { '3003': 'new@example.test' },
      }]);
    } finally {
      wrapper.unmount();
    }
  });

  it('TeamJoinModal：保存上限期间禁切 Team，旧 Team 的迟到保存不能覆盖新目标', async () => {
    const pendingSave = pendingResponse<Awaited<ReturnType<TeamsApi['updateTeam']>>>();
    const otherTeam: TeamDTO = { ...joinTeam, id: '9007199254740994', workspace_id: 'ws-beta',
      name: 'Beta', display_name: 'Beta 研发组' };
    const api = createJoinApi({
      list: vi.fn(async () => ({ items: [joinTeam, otherTeam], total: 2, page: 1, page_size: 50, revision: 'teams:2' })),
      previewJoin: vi.fn<TeamsApi['previewJoin']>(async (teamId) => ({
        ...joinPreview(teamId === otherTeam.id), team_id: teamId,
      })),
      updateTeam: vi.fn(() => pendingSave.promise),
    });
    const wrapper = mount(TeamJoinModal, { attachTo: document.body, props: {
      open: true, api, target: { mode: 'explicit', accountIds: ['3001'] },
      visible: true, formatDateTime: value => value || '—' } });
    try {
      await flushPromises();
      await wrapper.find('select[aria-label="选择目标 Team"]').setValue(joinTeam.id);
      await flushPromises();
      await wrapper.find('input[aria-label="本地计划人数上限"]').setValue('12');
      await wrapper.findAll('button').find(b => b.text().includes('设置本地计划人数上限并重新核算'))!.trigger('click');
      expect(wrapper.find('select[aria-label="选择目标 Team"]').attributes('disabled')).toBeDefined();
      await wrapper.setProps({ initialTeam: otherTeam,
        target: { mode: 'explicit', accountIds: ['3002'], targetTeamId: otherTeam.id } });
      await flushPromises();
      pendingSave.resolve({ team: { ...joinTeam, revision: 5, planned_member_limit: 12 } });
      await flushPromises();
      expect(wrapper.text()).toContain('Beta 研发组');
      expect(wrapper.emitted('teamUpdated')).toBeUndefined();
      expect(api.previewJoin).toHaveBeenLastCalledWith(otherTeam.id, { account_ids: ['3002'] }, expect.any(AbortSignal));
      await wrapper.findAll('button').find(b => b.text().includes('确认发起加入'))!.trigger('click');
      expect(api.submitJoin).toHaveBeenCalledWith(otherTeam.id, { account_ids: ['3002'] });
    } finally {
      wrapper.unmount();
    }
  });

  it.each(['成功', '失败'] as const)('TeamJoinModal：隐藏使旧上限保存失效，迟到%s不干扰恢复后的新保存', async (outcome) => {
    type SaveResponse = Awaited<ReturnType<TeamsApi['updateTeam']>>;
    const oldSave = pendingResponse<SaveResponse>();
    const newSave = pendingResponse<SaveResponse>();
    const api = createJoinApi({ previewJoin: vi.fn(async () => joinPreview(false)),
      updateTeam: vi.fn<TeamsApi['updateTeam']>().mockImplementationOnce(() => oldSave.promise)
        .mockImplementationOnce(() => newSave.promise) });
    const wrapper = mount(TeamJoinModal, { attachTo: document.body, props: {
      open: true, api, initialTeam: joinTeam, target: { mode: 'explicit', accountIds: ['3001'] },
      visible: true, formatDateTime: value => value || '—' } });
    try {
      await flushPromises();
      await wrapper.find('input[aria-label="本地计划人数上限"]').setValue('12');
      const saveButton = () => wrapper.findAll('button').find(b =>
        b.text().includes('设置本地计划人数上限并重新核算') || b.text().includes('保存核算中'))!;
      await saveButton().trigger('click');
      await wrapper.setProps({ visible: false });
      expect(wrapper.find('dialog').attributes('aria-busy')).toBe('false');
      await wrapper.setProps({ visible: true });
      await wrapper.find('input[aria-label="本地计划人数上限"]').setValue('13');
      await saveButton().trigger('click');
      if (outcome === '成功') oldSave.resolve({ team: { ...joinTeam, planned_member_limit: 12 } });
      else oldSave.reject(new Error('旧保存失败'));
      await flushPromises();
      expect(saveButton().text()).toContain('保存核算中');
      expect(saveButton().attributes('disabled')).toBeDefined();
      expect(wrapper.emitted('teamUpdated')).toBeUndefined();
      expect(wrapper.text()).not.toContain('旧保存失败');
      const updatedTeam = { ...joinTeam, revision: 5, planned_member_limit: 13 };
      newSave.resolve({ team: updatedTeam });
      await flushPromises();
      expect(wrapper.emitted('teamUpdated')?.[0]).toEqual([updatedTeam]);
      expect(saveButton().attributes('disabled')).toBeUndefined();
    } finally {
      wrapper.unmount();
    }
  });

  it('TeamJoinModal：保存响应 Team 不匹配时保留当前目标并显示核对错误', async () => {
    const api = createJoinApi({ previewJoin: vi.fn(async () => joinPreview(false)),
      updateTeam: vi.fn(async () => ({ team: { ...joinTeam, id: '9007199254740994' } })) });
    const wrapper = mount(TeamJoinModal, { attachTo: document.body, props: {
      open: true, api, initialTeam: joinTeam, target: { mode: 'explicit', accountIds: ['3001'] },
      visible: true, formatDateTime: value => value || '—' } });
    try {
      await flushPromises();
      await wrapper.find('input[aria-label="本地计划人数上限"]').setValue('12');
      await wrapper.findAll('button').find(b => b.text().includes('设置本地计划人数上限并重新核算'))!.trigger('click');
      await flushPromises();
      expect(wrapper.text()).toContain('保存响应的工作区与当前目标不一致');
      expect(wrapper.emitted('teamUpdated')).toBeUndefined();
      expect(api.previewJoin).toHaveBeenCalledTimes(1);
    } finally {
      wrapper.unmount();
    }
  });

  it('TeamJoinModal：旧目标加入请求受理后上报捕获的 Team，不能覆盖新目标或清除其提交状态', async () => {
    const oldSubmit = pendingResponse<JoinRequestDTO>();
    const newSubmit = pendingResponse<JoinRequestDTO>();
    const otherTeam: TeamDTO = { ...joinTeam, id: '9007199254740994', workspace_id: 'ws-beta',
      name: 'Beta', display_name: 'Beta 研发组' };
    const api = createJoinApi({ submitJoin: vi.fn<TeamsApi['submitJoin']>()
      .mockImplementationOnce(() => oldSubmit.promise).mockImplementationOnce(() => newSubmit.promise) });
    const wrapper = mount(TeamJoinModal, { attachTo: document.body, props: {
      open: true, api, initialTeam: joinTeam, target: { mode: 'explicit', accountIds: ['3001'] },
      visible: true, formatDateTime: value => value || '—' } });
    try {
      await flushPromises();
      await wrapper.findAll('button').find(b => b.text().includes('确认发起加入'))!.trigger('click');
      await wrapper.setProps({ initialTeam: otherTeam, target: { mode: 'explicit', accountIds: ['3002'] } });
      await flushPromises();
      await wrapper.findAll('button').find(b => b.text().includes('确认发起加入'))!.trigger('click');
      oldSubmit.resolve(joinReceipt());
      await flushPromises();
      expect(wrapper.emitted('submitted')?.[0]).toEqual([joinReceipt(), joinTeam.id]);
      expect(wrapper.text()).not.toContain('#9501');
      expect(wrapper.text()).toContain('正在受理');
      expect(api.getJoinRequest).not.toHaveBeenCalled();
    } finally {
      wrapper.unmount();
    }
  });

  it('TeamJoinModal：旧目标加入冲突不重载当前 Team 或清除新提交状态', async () => {
    const oldSubmit = pendingResponse<JoinRequestDTO>();
    const newSubmit = pendingResponse<JoinRequestDTO>();
    const api = createJoinApi({ submitJoin: vi.fn<TeamsApi['submitJoin']>()
      .mockImplementationOnce(() => oldSubmit.promise).mockImplementationOnce(() => newSubmit.promise) });
    const wrapper = mount(TeamJoinModal, { attachTo: document.body, props: {
      open: true, api, initialTeam: joinTeam, target: { mode: 'explicit', accountIds: ['3001'] },
      visible: true, formatDateTime: value => value || '—' } });
    try {
      await flushPromises();
      await wrapper.findAll('button').find(b => b.text().includes('确认发起加入'))!.trigger('click');
      await wrapper.setProps({ target: { mode: 'explicit', accountIds: ['3002'] } });
      await flushPromises();
      await wrapper.findAll('button').find(b => b.text().includes('确认发起加入'))!.trigger('click');
      oldSubmit.reject(new TeamApiError('旧请求版本冲突', 409, { code: 'team_revision_conflict' }));
      await flushPromises();
      expect(wrapper.text()).toContain('正在受理');
      expect(wrapper.text()).not.toContain('旧请求版本冲突');
      expect(wrapper.text()).not.toContain('请二次确认后提交');
      expect(api.detail).not.toHaveBeenCalled();
      expect(api.previewJoin).toHaveBeenCalledTimes(2);
    } finally {
      wrapper.unmount();
    }
  });

  it('TeamJoinModal：同会话隐藏期间受理仍保留回执，恢复可读取且不会主动复活弹窗', async () => {
    const pendingSubmit = pendingResponse<JoinRequestDTO>();
    const api = createJoinApi({ submitJoin: vi.fn(() => pendingSubmit.promise) });
    const wrapper = mount(TeamJoinModal, { attachTo: document.body, props: {
      open: true, api, initialTeam: joinTeam, target: { mode: 'explicit', accountIds: ['3001'] },
      visible: true, formatDateTime: value => value || '—' } });
    try {
      await flushPromises();
      await wrapper.findAll('button').find(b => b.text().includes('确认发起加入'))!.trigger('click');
      await wrapper.setProps({ visible: false });
      pendingSubmit.resolve(joinReceipt());
      await flushPromises();
      expect(wrapper.find('dialog').attributes('open')).toBeUndefined();
      expect(wrapper.emitted('submitted')?.[0]).toEqual([joinReceipt(), joinTeam.id]);
      expect(api.getJoinRequest).not.toHaveBeenCalled();
      await wrapper.setProps({ visible: true });
      await flushPromises();
      expect(wrapper.text()).toContain('#9501');
      expect(api.getJoinRequest).toHaveBeenCalledWith(joinTeam.id, '9501', { page: 1, page_size: 20 }, expect.any(AbortSignal));
    } finally {
      wrapper.unmount();
    }
  });

  it.each([
    ['preparing', '正在准备'],
    ['running', '执行中'],
    ['success', '已完成'],
    ['partial_success', '部分成功'],
    ['failed', '执行失败'],
  ] as const)('TeamJoinModal：回执展示真实 %s 状态和跨页失败总数', async (status, expectedStatus) => {
    const request: JoinRequestDTO = { ...joinReceipt(), status,
      counts: { ...joinReceipt().counts, requested_count: 21, unique_count: 21, accepted_count: 20,
        pending_count: 0, failed_count: 1 } };
    const api = createJoinApi({
      submitJoin: vi.fn(async () => request),
      getJoinRequest: vi.fn(async () => ({ request, items: [], total: 21, page: 1, page_size: 20, revision: 'request:21' })),
    });
    const wrapper = mount(TeamJoinModal, { attachTo: document.body, props: {
      open: true, api, initialTeam: joinTeam, target: { mode: 'explicit', accountIds: ['3001'] },
      visible: true, formatDateTime: value => value || '—' } });
    try {
      await flushPromises();
      await wrapper.findAll('button').find(b => b.text().includes('确认发起加入'))!.trigger('click');
      await flushPromises();
      expect(wrapper.text()).toContain('请求已持久受理，逐项结果见下方');
      expect(wrapper.text()).toContain(expectedStatus);
      const failedStat = wrapper.findAll('.tm-preview-stat').find(item => item.find('span').text() === '受理失败');
      expect(failedStat?.find('strong').text()).toBe('1');
      expect(wrapper.text()).not.toContain('已受理并进入后台执行');
    } finally {
      wrapper.unmount();
    }
  });

  it('TeamJoinModal：按分页读取回执，运行中刷新并在隐藏后停止读取', async () => {
    const request = joinReceipt();
    request.counts.requested_count = 21; request.counts.unique_count = 21; request.counts.pending_count = 21;
    const api = createJoinApi({ submitJoin: vi.fn(async () => request),
      getJoinRequest: vi.fn<TeamsApi['getJoinRequest']>(async (_team, _request, query) => ({ request, total: 21,
        page: query?.page ?? 1, page_size: 20, revision: 'request:21', items: [{
          ordinal: query?.page === 2 ? 20 : 0, account_id: query?.page === 2 ? '3021' : '3001', invitation_id: null,
          acceptance_status: 'pending' as const, task_id: null, run_id: null, execution_status: 'none' as const, reason_code: null, message: null,
        }] })) });
    const wrapper = mount(TeamJoinModal, { attachTo: document.body, props: {
      open: true, api, initialTeam: joinTeam, target: { mode: 'explicit', accountIds: ['3001'] },
      visible: true, formatDateTime: value => value || '—' } });
    await flushPromises();
    await wrapper.findAll('button').find(b => b.text().includes('确认发起加入'))!.trigger('click');
    await flushPromises();
    await wrapper.findAll('button').find(b => b.text() === '下一页')!.trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('#3021');
    expect(api.getJoinRequest).toHaveBeenLastCalledWith(joinTeam.id, '9501', { page: 2, page_size: 20 }, expect.any(AbortSignal));
    const count = vi.mocked(api.getJoinRequest).mock.calls.length;
    await vi.advanceTimersByTimeAsync(3000); await flushPromises();
    expect(api.getJoinRequest).toHaveBeenCalledTimes(count + 1);
    expect(api.getJoinRequest).toHaveBeenLastCalledWith(joinTeam.id, '9501', { page: 2, page_size: 20 }, expect.any(AbortSignal));
    await wrapper.setProps({ visible: false });
    await vi.advanceTimersByTimeAsync(6000); await flushPromises();
    expect(api.getJoinRequest).toHaveBeenCalledTimes(count + 1);
    await wrapper.setProps({ visible: true }); await flushPromises();
    expect(wrapper.text()).toContain('#9501');
    expect(api.getJoinRequest).toHaveBeenCalledTimes(count + 2);
    wrapper.unmount();
  });

});
