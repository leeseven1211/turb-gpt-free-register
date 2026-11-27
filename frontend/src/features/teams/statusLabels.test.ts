import { describe, expect, it } from 'vitest';
import type { TeamInvitationDTO } from './contracts';
import {
  CANDIDATE_ELIGIBILITY_BADGES, TEAM_ACTIVE_EXECUTION_STATUSES, TEAM_EXECUTION_LABELS,
  TEAM_INVITATION_LABELS, TEAM_JOIN_STAGE_LABELS, TEAM_MEMBERSHIP_LABELS, TEAM_PROBE_STAGE_STEPS,
  TEAM_REASON_LABELS, TEAM_SYNC_LABELS,
  computeCapacityPercentage, formatInvitationBusinessFacts, formatInvitationExecutionFacts,
  formatInvitationResultSummary, formatNullableCount, formatSeatLimitDisplay,
  isTeamActivelyRunning, teamCapacityBasisLabel, teamDisplayName, teamEffectiveLimit,
  teamExecutionLabel, teamExecutionTone, teamMembershipLabel, teamMembershipTone,
  teamReasonLabel, teamRoleLabel, teamRoleTone, teamSyncLabel, teamSyncTone,
  workspaceAvatarHue, workspaceInitials,
} from './statusLabels';

function execution(values: Partial<TeamInvitationDTO['latest_execution']> = {}): TeamInvitationDTO['latest_execution'] {
  return {
    task_id: null, run_id: null, status: 'none', stage: null,
    waiting_reason_code: null, error_info: null, ...values,
  };
}

describe('Team 状态标签使用后端公开枚举', () => {
  it('覆盖全部业务事实、执行状态、阶段、等待原因和候选互斥分类', () => {
    expect(Object.keys(TEAM_SYNC_LABELS)).toEqual([
      'never', 'queued', 'running', 'success', 'partial_success', 'failed', 'interrupted',
    ]);
    expect(Object.keys(TEAM_MEMBERSHIP_LABELS)).toEqual(['joined', 'left', 'unconfirmed']);
    expect(Object.keys(TEAM_INVITATION_LABELS)).toEqual([
      'not_sent', 'pending', 'accepted', 'revoked', 'expired', 'unconfirmed',
    ]);
    expect(Object.keys(TEAM_EXECUTION_LABELS)).toEqual([
      'none', 'queued', 'running', 'waiting', 'cancelling', 'settling', 'stopping',
      'success', 'partial_success', 'failed', 'stopped', 'cancelled', 'interrupted', 'deactivated', 'unsupported',
    ]);
    expect(Object.keys(TEAM_JOIN_STAGE_LABELS)).toEqual([
      'queued', 'manager_verify', 'state_check', 'invite', 'member_auth', 'accept', 'member_verify', 'persist', 'complete',
    ]);
    expect(TEAM_PROBE_STAGE_STEPS.map(step => step.key)).toEqual([
      'queued', 'manager_auth', 'workspace_discovery', 'permission_check',
    ]);
    expect(Object.keys(CANDIDATE_ELIGIBILITY_BADGES)).toEqual([
      'new', 'resume_invite', 'already_member', 'same_team_active', 'another_team', 'missing_auth', 'unavailable',
    ]);
    for (const code of ['waiting_account', 'waiting_child', 'waiting_sync', 'waiting_capacity', 'waiting_remote']) {
      expect(teamReasonLabel(code)).toMatch(/[\u3400-\u9fff]/);
      expect(teamReasonLabel(code)).not.toBe(code);
    }
    expect(Object.isFrozen(TEAM_REASON_LABELS)).toBe(true);
  });

  it('后端业务原因使用统一中文文案，角色与真实终态保持独立', () => {
    expect(teamReasonLabel('team_save_failed')).toBe('本地保存失败');
    expect(teamReasonLabel('already_in_another_team')).toBe('已归属其他Team');
    expect(teamReasonLabel(null, { message: '简短现场说明' })).toBe('简短现场说明');
    expect(teamReasonLabel()).toBe('状态待核对');
    expect(teamRoleLabel('owner')).toBe('所有者');
    expect(teamRoleTone('owner')).toBe('active');
    expect(teamRoleTone('admin')).toBe('success');
    expect(teamMembershipLabel('unconfirmed')).toBe('待确认');
    expect(teamMembershipTone('left')).toBe('danger');
    expect(teamSyncLabel('partial_success')).toBe('部分同步');
    expect(teamSyncTone('partial_success')).toBe('warning');
    expect(teamSyncTone('interrupted')).toBe('warning');
    expect(teamExecutionLabel('partial_success')).toBe('部分成功');
    expect(teamExecutionTone('partial_success')).toBe('warning');
    expect(teamExecutionTone('deactivated')).toBe('danger');
    expect(TEAM_ACTIVE_EXECUTION_STATUSES.has('waiting')).toBe(true);
    expect(TEAM_ACTIVE_EXECUTION_STATUSES.has('partial_success')).toBe(false);
  });
});

describe('Team 未知数量与明确零值', () => {
  it('未知计数显示待同步，零值保持零', () => {
    expect(formatNullableCount(null)).toBe('待同步');
    expect(formatNullableCount(undefined, '未返回')).toBe('未返回');
    expect(formatNullableCount(Number.NaN)).toBe('待同步');
    expect(formatNullableCount(0, '未返回', ' 席')).toBe('0 席');
    expect(formatNullableCount(12, '待同步', ' 人')).toBe('12 人');
  });

  it('已购为零不回退到本地上限，有效上限采用两者较小值', () => {
    expect(teamEffectiveLimit({ purchased_seats: 0, planned_member_limit: 5 })).toBe(0);
    expect(teamEffectiveLimit({ purchased_seats: null, planned_member_limit: 5 })).toBe(5);
    expect(teamEffectiveLimit({ purchased_seats: 10, planned_member_limit: 8 })).toBe(8);
    expect(teamEffectiveLimit({ purchased_seats: 8, planned_member_limit: null })).toBe(8);
    expect(teamEffectiveLimit({ purchased_seats: null, planned_member_limit: null })).toBeNull();
    expect(formatSeatLimitDisplay({ purchased_seats: 0, planned_member_limit: 5 })).toEqual({
      primary: '已购 0 席 · 上限 5', secondary: '余量待预检', tone: 'neutral',
    });
    expect(formatSeatLimitDisplay({ purchased_seats: null, planned_member_limit: null })).toEqual({
      primary: '已购未返回', secondary: '需设本地上限', tone: 'warning',
    });
    expect(formatSeatLimitDisplay({ purchased_seats: 10, planned_member_limit: 8 }).secondary).toBe('余量待预检');
    expect(teamCapacityBasisLabel('unavailable')).toBe('席位待确认');
  });

  it('Team 名称按本地备注、远端名称、workspace ID回退', () => {
    expect(teamDisplayName({ display_name: '本地备注', name: '远端名称', workspace_id: 'ws-1' })).toBe('本地备注');
    expect(teamDisplayName({ display_name: null, name: '远端名称', workspace_id: 'ws-1' })).toBe('远端名称');
    expect(teamDisplayName({ display_name: null, name: null, workspace_id: 'ws-1' })).toBe('ws-1');
  });
});

describe('邀请业务事实与执行结果分别展示', () => {
  it('pending与unconfirmed分别保留，joined不因执行失败回退', () => {
    expect(formatInvitationBusinessFacts({ invitation_state: 'pending', membership_state: 'unconfirmed' })).toEqual({
      primary: '待接受邀请', secondary: '成员：待确认', tone: 'active',
    });
    expect(formatInvitationBusinessFacts({ invitation_state: 'accepted', membership_state: 'joined' })).toEqual({
      primary: '邀请已接受', secondary: '成员：已加入', tone: 'success',
    });
    expect(formatInvitationBusinessFacts({ invitation_state: 'revoked', membership_state: 'left' })).toEqual({
      primary: '邀请已撤回', secondary: '成员：已退出', tone: 'danger',
    });
  });

  it('读取嵌套latest_execution，等待原因不混为失败', () => {
    expect(formatInvitationExecutionFacts({ latest_execution: execution({
      status: 'waiting', stage: 'member_auth', waiting_reason_code: 'waiting_account',
    }) })).toEqual({ primary: '等待中', secondary: '认证成员账号 · 等待账号空闲', tone: 'active' });
    expect(formatInvitationResultSummary({
      membership_state: 'unconfirmed', invitation_state: 'pending',
      latest_execution: execution({ status: 'waiting', waiting_reason_code: 'waiting_capacity' }),
    })).toEqual({ label: '等待可用名额', secondary: '等待处理', detail: '', tone: 'warning' });
  });

  it('joined与本地保存失败同时展示，保留具体错误证据', () => {
    expect(formatInvitationResultSummary({
      membership_state: 'joined', invitation_state: 'accepted',
      latest_execution: execution({ status: 'partial_success', stage: 'persist', error_info: {
        code: 'team_save_failed', message: '加密上下文未完成本地保存', stage: 'persist', retryable: true,
      } }),
    })).toEqual({ label: '本地保存失败', secondary: 'team_save_failed', detail: '加密上下文未完成本地保存', tone: 'danger' });
    expect(formatInvitationResultSummary({
      membership_state: 'joined', invitation_state: 'accepted', latest_execution: execution({ status: 'success' }),
    }).label).toBe('已确认入组');
    expect(formatInvitationResultSummary({
      membership_state: 'unconfirmed', invitation_state: 'pending', latest_execution: execution(),
    })).toEqual({ label: '待接受邀请', secondary: '可继续加入', detail: '', tone: 'warning' });
  });
});

describe('显示辅助与活跃投影', () => {
  it('只有正在同步或处理目标才持续轮询，null处理数不伪造活跃', () => {
    expect(isTeamActivelyRunning(null)).toBe(false);
    expect(isTeamActivelyRunning({ last_sync_status: 'queued', processing_count: null })).toBe(true);
    expect(isTeamActivelyRunning({ last_sync_status: 'success', processing_count: 2 })).toBe(true);
    expect(isTeamActivelyRunning({ last_sync_status: 'partial_success', processing_count: 0 })).toBe(false);
    expect(isTeamActivelyRunning({ last_sync_status: 'interrupted', processing_count: null })).toBe(false);
  });

  it('头像稳定，只有已知非零上限与并集占用可显示比例', () => {
    expect(workspaceAvatarHue('ws-1')).toBe(workspaceAvatarHue('ws-1'));
    expect(workspaceInitials('Alpha Team')).toBe('AT');
    expect(workspaceInitials('中文团队')).toBe('中文');
    expect(workspaceInitials('')).toBe('TM');
    expect(computeCapacityPercentage({ effective_limit: null, occupied_count: 3 })).toBeNull();
    expect(computeCapacityPercentage({ effective_limit: 0, occupied_count: 0 })).toBeNull();
    expect(computeCapacityPercentage({ effective_limit: 10, occupied_count: null })).toBeNull();
    expect(computeCapacityPercentage({ effective_limit: 10, occupied_count: 3 })).toBe(30);
    expect(computeCapacityPercentage({ effective_limit: 5, occupied_count: 8 })).toBe(100);
  });
});
