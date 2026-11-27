import { describe, expect, it } from 'vitest';
import {
  CANDIDATE_ELIGIBILITY_BADGES,
  TEAM_REASON_LABELS,
  computeCapacityPercentage,
  formatInvitationBusinessFacts,
  formatInvitationExecutionFacts,
  formatInvitationResultSummary,
  formatNullableCount,
  formatSeatLimitDisplay,
  isTeamActivelyRunning,
  teamCapacityBasisLabel,
  teamMembershipLabel,
  teamMembershipTone,
  teamReasonLabel,
  teamRoleLabel,
  teamRoleTone,
  teamSyncLabel,
  teamSyncTone,
  workspaceAvatarHue,
  workspaceInitials,
} from './statusLabels';

const EXPECTED_27_REASON_CODES = [
  'team_probe_expired',
  'team_probe_failed',
  'team_workspace_not_found',
  'team_workspace_personal',
  'team_permission_denied',
  'team_already_bound',
  'team_manager_auth_failed',
  'team_manager_deactivated',
  'team_sync_in_progress',
  'team_sync_failed',
  'team_revision_conflict',
  'team_seat_full',
  'team_limit_reached',
  'team_limit_required',
  'team_invite_send_failed',
  'team_invite_rate_limited',
  'team_invite_mail_timeout',
  'team_invite_link_invalid',
  'team_invite_revoked',
  'team_invite_expired',
  'team_target_auth_missing',
  'team_target_auth_failed',
  'team_target_totp_failed',
  'team_target_deactivated',
  'team_target_email_invalid',
  'team_already_in_other_team',
  'team_membership_unverified',
] as const;

describe('TEAM_REASON_LABELS 与 teamReasonLabel', () => {
  it('包含全部 27 个冻结 reason_code，已冻结且每个短语长度均 <= 10', () => {
    expect(Object.isFrozen(TEAM_REASON_LABELS)).toBe(true);
    expect(Object.keys(TEAM_REASON_LABELS)).toHaveLength(27);

    for (const code of EXPECTED_27_REASON_CODES) {
      expect(Object.hasOwn(TEAM_REASON_LABELS, code)).toBe(true);
      const label = TEAM_REASON_LABELS[code]!;
      expect(label.trim().length).toBeGreaterThan(0);
      expect(Array.from(label).length).toBeLessThanOrEqual(10);
    }
  });

  it('teamReasonLabel 优先命中冻结短语，其次消费短 summary，最后兜底', () => {
    expect(teamReasonLabel('team_already_bound')).toBe('工作区已绑定');
    expect(teamReasonLabel(null, { reason_code: 'team_seat_full', summary: '很长的自定义错误说明' })).toBe('已购席位不足');
    expect(teamReasonLabel('custom_unknown_code', { reason_code: 'custom_unknown_code', summary: '简短提示' })).toBe('简短提示');
    expect(
      teamReasonLabel('custom_unknown_code', {
        reason_code: 'custom_unknown_code',
        summary: '超过十个字的详细错误提示说明',
      }),
    ).toBeTruthy();
    expect(teamReasonLabel(null, null)).toBe('状态待核对');
  });
});

describe('formatNullableCount 与 null/0 语义隔离', () => {
  it('严格区分 null/undefined/NaN 与 0，绝不把 null 渲染成 0', () => {
    expect(formatNullableCount(null)).toBe('待同步');
    expect(formatNullableCount(null, '未返回')).toBe('未返回');
    expect(formatNullableCount(undefined, '未返回', ' 席')).toBe('未返回');
    expect(formatNullableCount(Number.NaN, '待同步', ' 席')).toBe('待同步');

    expect(formatNullableCount(0)).toBe('0');
    expect(formatNullableCount(0, '待同步', ' 席')).toBe('0 席');
    expect(formatNullableCount(0, '未返回', ' 席')).toBe('0 席');
    expect(formatNullableCount(12, '待同步', ' 席')).toBe('12 席');

    expect(formatNullableCount(null, '未返回', ' 席')).not.toBe(formatNullableCount(0, '未返回', ' 席'));
  });
});

describe('formatSeatLimitDisplay 席位容量展示', () => {
  it('team_limit_required 时提示未返回席位并需设本地上限', () => {
    expect(
      formatSeatLimitDisplay({
        purchased_seats: null,
        planned_member_limit: null,
        capacity: {
          basis: 'unknown',
          effective_limit: null,
          occupied_count: null,
          remaining_before_limit: null,
          can_accept_new_joins: false,
          blocking_reason_code: 'team_limit_required',
        },
      }),
    ).toEqual({
      primary: '未返回席位',
      secondary: '需设本地上限',
      tone: 'warning',
    });
  });

  it('purchased_seats === 0 时清晰显示已购 0 席与危险色调', () => {
    expect(
      formatSeatLimitDisplay({
        purchased_seats: 0,
        planned_member_limit: 5,
        capacity: {
          basis: 'purchased_seats',
          effective_limit: 0,
          occupied_count: 0,
          remaining_before_limit: 0,
          can_accept_new_joins: false,
          blocking_reason_code: 'team_seat_full',
        },
      }),
    ).toEqual({
      primary: '已购 0 席 · 上限 5',
      secondary: '已购席位不足',
      tone: 'danger',
    });

    expect(
      formatSeatLimitDisplay({
        purchased_seats: 0,
        planned_member_limit: null,
        capacity: {
          basis: 'purchased_seats',
          effective_limit: 0,
          occupied_count: 0,
          remaining_before_limit: 0,
          can_accept_new_joins: false,
          blocking_reason_code: 'team_seat_full',
        },
      }),
    ).toEqual({
      primary: '已购 0 席',
      secondary: '已购席位不足',
      tone: 'danger',
    });
  });

  it('正常有剩余席位时显示剩余席位与对应色调（>1 为 success，<=1 为 warning）', () => {
    expect(
      formatSeatLimitDisplay({
        purchased_seats: 10,
        planned_member_limit: 8,
        capacity: {
          basis: 'hybrid_min',
          effective_limit: 8,
          occupied_count: 4,
          remaining_before_limit: 4,
          can_accept_new_joins: true,
          blocking_reason_code: null,
        },
      }),
    ).toEqual({
      primary: '已购 10 席 · 上限 8',
      secondary: '可拉剩余 4 席',
      tone: 'success',
    });

    expect(
      formatSeatLimitDisplay({
        purchased_seats: null,
        planned_member_limit: 5,
        capacity: {
          basis: 'planned_member_limit',
          effective_limit: 5,
          occupied_count: 4,
          remaining_before_limit: 1,
          can_accept_new_joins: true,
          blocking_reason_code: null,
        },
      }),
    ).toEqual({
      primary: '已购未返回 · 上限 5',
      secondary: '可拉剩余 1 席',
      tone: 'warning',
    });
  });

  it('不可加入且非席位/上限阻塞、或剩余席位为 null 时退回容量基准文案', () => {
    expect(
      formatSeatLimitDisplay({
        purchased_seats: 5,
        planned_member_limit: null,
        capacity: {
          basis: 'purchased_seats',
          effective_limit: 5,
          occupied_count: null,
          remaining_before_limit: null,
          can_accept_new_joins: true,
          blocking_reason_code: null,
        },
      }),
    ).toEqual({
      primary: '已购 5 席',
      secondary: '已购席位',
      tone: 'success',
    });

    expect(
      formatSeatLimitDisplay({
        purchased_seats: 5,
        planned_member_limit: 5,
        capacity: {
          basis: 'hybrid_min',
          effective_limit: 5,
          occupied_count: 5,
          remaining_before_limit: 0,
          can_accept_new_joins: false,
          blocking_reason_code: 'team_limit_reached',
        },
      }),
    ).toEqual({
      primary: '已购 5 席 · 上限 5',
      secondary: '已达本地人数上限',
      tone: 'danger',
    });

    expect(
      formatSeatLimitDisplay({
        purchased_seats: 5,
        planned_member_limit: null,
        capacity: {
          basis: 'unknown',
          effective_limit: 5,
          occupied_count: 0,
          remaining_before_limit: null,
          can_accept_new_joins: false,
          blocking_reason_code: 'team_sync_in_progress',
        },
      }),
    ).toEqual({
      primary: '已购 5 席',
      secondary: '正在同步工作区',
      tone: 'warning',
    });
  });
});

describe('邀请页双事实与结果摘要', () => {
  it('formatInvitationBusinessFacts 正确映射 invitation_state 与 membership_state 双事实', () => {
    expect(
      formatInvitationBusinessFacts({ invitation_state: 'accepted', membership_state: 'joined' }),
    ).toEqual({
      primary: '邀请已接受',
      secondary: '成员：已加入',
      tone: 'success',
    });

    expect(
      formatInvitationBusinessFacts({ invitation_state: 'pending', membership_state: 'not_joined' }),
    ).toEqual({
      primary: '待接受邀请',
      secondary: '成员：未入组',
      tone: 'active',
    });

    expect(
      formatInvitationBusinessFacts({ invitation_state: 'revoked', membership_state: 'not_joined' }),
    ).toEqual({
      primary: '邀请已撤回',
      secondary: '成员：未入组',
      tone: 'danger',
    });

    expect(
      formatInvitationBusinessFacts({ invitation_state: 'accepted', membership_state: 'removed' }),
    ).toEqual({
      primary: '邀请已接受',
      secondary: '成员：已移除',
      tone: 'danger',
    });

    expect(
      formatInvitationBusinessFacts({ invitation_state: 'unknown', membership_state: 'unknown' }),
    ).toEqual({
      primary: '邀请状态未知',
      secondary: '成员：待核实',
      tone: 'warning',
    });

    expect(
      formatInvitationBusinessFacts({ invitation_state: 'not_sent', membership_state: 'not_joined' }),
    ).toEqual({
      primary: '未发邀请',
      secondary: '成员：未入组',
      tone: 'neutral',
    });
  });

  it('formatInvitationExecutionFacts 正确映射执行状态、阶段与等待原因', () => {
    expect(
      formatInvitationExecutionFacts({
        execution_status: 'running',
        stage: 'await_invite_mail',
        waiting_reason_code: null,
      }),
    ).toEqual({
      primary: '执行中',
      secondary: '等待接收邀请邮件',
      tone: 'active',
    });

    expect(
      formatInvitationExecutionFacts({
        execution_status: 'waiting_user',
        stage: 'authenticate_target',
        waiting_reason_code: 'team_target_totp_failed',
      }),
    ).toEqual({
      primary: '等待人工处理',
      secondary: '认证目标账号 · 目标号2FA失败',
      tone: 'warning',
    });

    expect(
      formatInvitationExecutionFacts({
        execution_status: 'idle',
        stage: null,
        waiting_reason_code: null,
      }),
    ).toEqual({
      primary: '未执行',
      secondary: '—',
      tone: 'neutral',
    });

    expect(
      formatInvitationExecutionFacts({
        execution_status: 'failed',
        stage: 'verify_membership',
        waiting_reason_code: null,
      }),
    ).toEqual({
      primary: '执行失败',
      secondary: '回查工作区成员状态',
      tone: 'danger',
    });

    expect(
      formatInvitationExecutionFacts({
        execution_status: 'succeeded',
        stage: null,
        waiting_reason_code: null,
      }),
    ).toEqual({
      primary: '已完成',
      secondary: '—',
      tone: 'success',
    });
  });

  it('formatInvitationResultSummary 按优先级生成错误、等待、已入组、执行中、待接受与空态摘要', () => {
    expect(
      formatInvitationResultSummary({
        execution_status: 'failed',
        membership_state: 'not_joined',
        invitation_state: 'pending',
        waiting_reason_code: null,
        error: {
          reason_code: 'team_invite_mail_timeout',
          summary: '120 秒内未收到邀请邮件',
          detail: 'mailbox=foo@example.com',
        },
      }),
    ).toEqual({
      label: '等待邀请信超时',
      secondary: 'team_invite_mail_timeout',
      detail: '120 秒内未收到邀请邮件\nmailbox=foo@example.com',
      tone: 'danger',
    });

    expect(
      formatInvitationResultSummary({
        execution_status: 'waiting_user',
        membership_state: 'not_joined',
        invitation_state: 'pending',
        waiting_reason_code: 'team_target_auth_missing',
        error: {
          reason_code: 'team_target_auth_missing',
          summary: '目标账号缺少访问令牌与密码',
          detail: null,
        },
      }),
    ).toEqual({
      label: '目标号缺认证材料',
      secondary: 'team_target_auth_missing',
      detail: '目标账号缺少访问令牌与密码',
      tone: 'warning',
    });

    expect(
      formatInvitationResultSummary({
        execution_status: 'waiting_user',
        membership_state: 'not_joined',
        invitation_state: 'pending',
        waiting_reason_code: 'team_membership_unverified',
        error: null,
      }),
    ).toEqual({
      label: '加入结果待确认',
      secondary: '等待处理',
      detail: '',
      tone: 'warning',
    });

    expect(
      formatInvitationResultSummary({
        execution_status: 'succeeded',
        membership_state: 'joined',
        invitation_state: 'accepted',
        waiting_reason_code: null,
        error: null,
      }),
    ).toEqual({
      label: '已确认入组',
      secondary: '',
      detail: '',
      tone: 'success',
    });

    expect(
      formatInvitationResultSummary({
        execution_status: 'running',
        membership_state: 'not_joined',
        invitation_state: 'pending',
        waiting_reason_code: null,
        error: null,
      }),
    ).toEqual({
      label: '正在拉人入组',
      secondary: '',
      detail: '',
      tone: 'active',
    });

    expect(
      formatInvitationResultSummary({
        execution_status: 'idle',
        membership_state: 'not_joined',
        invitation_state: 'pending',
        waiting_reason_code: null,
        error: null,
      }),
    ).toEqual({
      label: '待接受邀请',
      secondary: '可继续加入',
      detail: '',
      tone: 'warning',
    });

    expect(
      formatInvitationResultSummary({
        execution_status: 'cancelled',
        membership_state: 'not_joined',
        invitation_state: 'revoked',
        waiting_reason_code: null,
        error: null,
      }),
    ).toEqual({
      label: '—',
      secondary: '',
      detail: '',
      tone: 'neutral',
    });
  });
});

describe('其他状态标签与容量辅助函数', () => {
  it('角色、同步、成员、容量基准与候选资格映射完整且稳定', () => {
    expect(teamRoleLabel('owner')).toBe('所有者');
    expect(teamRoleTone('owner')).toBe('active');
    expect(teamRoleTone('admin')).toBe('success');
    expect(teamRoleTone('member')).toBe('neutral');
    expect(teamRoleTone('unknown')).toBe('warning');

    expect(teamSyncLabel('success')).toBe('已同步');
    expect(teamSyncTone('running')).toBe('active');
    expect(teamSyncTone('failed')).toBe('danger');
    expect(teamSyncTone('never')).toBe('neutral');

    expect(teamMembershipLabel('left')).toBe('已退出');
    expect(teamMembershipTone('joined')).toBe('success');
    expect(teamMembershipTone('removed')).toBe('danger');

    expect(teamCapacityBasisLabel('hybrid_min')).toBe('已购与本地上限取小');
    expect(Object.keys(CANDIDATE_ELIGIBILITY_BADGES)).toHaveLength(7);
  });

  it('workspaceAvatarHue、workspaceInitials、isTeamActivelyRunning 与 computeCapacityPercentage 边界正确', () => {
    expect(workspaceAvatarHue('ws-1')).toBe(workspaceAvatarHue('ws-1'));
    expect(workspaceInitials('Alpha Team')).toBe('AT');
    expect(workspaceInitials('中文团队')).toBe('中文');
    expect(workspaceInitials('')).toBe('TM');

    expect(isTeamActivelyRunning(null)).toBe(false);
    expect(isTeamActivelyRunning({ last_sync_status: 'queued', processing_count: 0 })).toBe(true);
    expect(isTeamActivelyRunning({ last_sync_status: 'success', processing_count: 2 })).toBe(true);
    expect(isTeamActivelyRunning({ last_sync_status: 'success', processing_count: 0 })).toBe(false);

    expect(computeCapacityPercentage({ effective_limit: null, occupied_count: 3 })).toBeNull();
    expect(computeCapacityPercentage({ effective_limit: 0, occupied_count: 0 })).toBeNull();
    expect(computeCapacityPercentage({ effective_limit: 10, occupied_count: null })).toBeNull();
    expect(computeCapacityPercentage({ effective_limit: 10, occupied_count: 3 })).toBe(30);
    expect(computeCapacityPercentage({ effective_limit: 5, occupied_count: 8 })).toBe(100);
  });
});
