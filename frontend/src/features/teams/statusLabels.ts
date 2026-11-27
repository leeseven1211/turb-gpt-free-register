/** Team 管理冻结错误短语（<= 10 汉字）、双事实状态映射与席位容量展示规则。 */

import type {
  CandidateEligibilityState,
  TeamCapacityBasis,
  TeamCapacitySummary,
  TeamDTO,
  TeamErrorSummary,
  TeamExecutionStatus,
  TeamInvitationDTO,
  TeamInvitationState,
  TeamJoinStage,
  TeamMembershipState,
  TeamRole,
  TeamSyncStatus,
} from './contracts';
import { shortErrorLabel } from '../../shared/errorLabels';

export type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'active';

/** 契约 8.1 冻结的 27 个 Team reason_code 列表短语（均 <= 10 个汉字）。 */
export const TEAM_REASON_LABELS: Readonly<Record<string, string>> = Object.freeze({
  team_probe_expired: '核验结果已过期',
  team_probe_failed: '工作区核验失败',
  team_workspace_not_found: '未找到目标工作区',
  team_workspace_personal: '个人空间不可绑定',
  team_permission_denied: '母号无管理权限',
  team_already_bound: '工作区已绑定',
  team_manager_auth_failed: '母号登录态失效',
  team_manager_deactivated: '管理母号已停用',
  team_sync_in_progress: '正在同步工作区',
  team_sync_failed: '同步工作区失败',
  team_revision_conflict: '工作区状态已变',
  team_seat_full: '已购席位不足',
  team_limit_reached: '已达本地人数上限',
  team_limit_required: '需先设本地上限',
  team_invite_send_failed: '发送邀请失败',
  team_invite_rate_limited: '发送邀请被限流',
  team_invite_mail_timeout: '等待邀请信超时',
  team_invite_link_invalid: '邀请链接已失效',
  team_invite_revoked: '邀请已被撤回',
  team_invite_expired: '邀请已过期',
  team_target_auth_missing: '目标号缺认证材料',
  team_target_auth_failed: '目标号登录失败',
  team_target_totp_failed: '目标号2FA失败',
  team_target_deactivated: '目标账号已停用',
  team_target_email_invalid: '目标邮箱已失效',
  team_already_in_other_team: '已归属其他Team',
  team_membership_unverified: '加入结果待确认',
});

export function teamReasonLabel(code?: string | null, fallbackError?: TeamErrorSummary | null): string {
  const normalized = String(code || fallbackError?.reason_code || '').trim();
  if (normalized && Object.hasOwn(TEAM_REASON_LABELS, normalized)) {
    return TEAM_REASON_LABELS[normalized]!;
  }
  const summary = String(fallbackError?.summary || '').trim();
  if (summary && Array.from(summary).length <= 10) {
    return summary;
  }
  if (normalized) {
    return shortErrorLabel({ code: normalized, error_code: normalized });
  }
  return '状态待核对';
}

export const TEAM_ROLE_LABELS: Readonly<Record<TeamRole, string>> = Object.freeze({
  owner: '所有者',
  admin: '管理员',
  member: '成员',
  unknown: '待核验',
});

export function teamRoleLabel(role?: string | null): string {
  const key = String(role || 'unknown').toLowerCase() as TeamRole;
  return TEAM_ROLE_LABELS[key] ?? '待核验';
}

export function teamRoleTone(role?: string | null): BadgeTone {
  const key = String(role || 'unknown').toLowerCase();
  if (key === 'owner') return 'active';
  if (key === 'admin') return 'success';
  if (key === 'member') return 'neutral';
  return 'warning';
}

export const TEAM_SYNC_LABELS: Readonly<Record<TeamSyncStatus, string>> = Object.freeze({
  never: '未同步',
  queued: '排队同步',
  running: '同步中',
  success: '已同步',
  failed: '同步失败',
});

export function teamSyncLabel(status?: string | null): string {
  const key = String(status || 'never').toLowerCase() as TeamSyncStatus;
  return TEAM_SYNC_LABELS[key] ?? '待同步';
}

export function teamSyncTone(status?: string | null): BadgeTone {
  const key = String(status || 'never').toLowerCase();
  if (key === 'success') return 'success';
  if (key === 'queued' || key === 'running') return 'active';
  if (key === 'failed') return 'danger';
  return 'neutral';
}

export const TEAM_MEMBERSHIP_LABELS: Readonly<Record<TeamMembershipState, string>> = Object.freeze({
  joined: '已加入',
  not_joined: '未入组',
  removed: '已移除',
  left: '已退出',
  unknown: '待核实',
});

export function teamMembershipLabel(state?: string | null): string {
  const key = String(state || 'unknown').toLowerCase() as TeamMembershipState;
  return TEAM_MEMBERSHIP_LABELS[key] ?? '待核实';
}

export function teamMembershipTone(state?: string | null): BadgeTone {
  const key = String(state || 'unknown').toLowerCase();
  if (key === 'joined') return 'success';
  if (key === 'removed' || key === 'left') return 'danger';
  if (key === 'unknown') return 'warning';
  return 'neutral';
}

export const TEAM_INVITATION_LABELS: Readonly<Record<TeamInvitationState, string>> = Object.freeze({
  not_sent: '未发邀请',
  pending: '待接受邀请',
  accepted: '邀请已接受',
  revoked: '邀请已撤回',
  expired: '邀请已过期',
  unknown: '邀请状态未知',
});

export function teamInvitationStateLabel(state?: string | null): string {
  const key = String(state || 'unknown').toLowerCase() as TeamInvitationState;
  return TEAM_INVITATION_LABELS[key] ?? '邀请状态未知';
}

export const TEAM_EXECUTION_LABELS: Readonly<Record<TeamExecutionStatus, string>> = Object.freeze({
  idle: '未执行',
  queued: '排队中',
  running: '执行中',
  waiting_user: '等待人工处理',
  succeeded: '已完成',
  failed: '执行失败',
  cancelled: '已取消',
});

export function teamExecutionLabel(status?: string | null): string {
  const key = String(status || 'idle').toLowerCase() as TeamExecutionStatus;
  return TEAM_EXECUTION_LABELS[key] ?? '未执行';
}

export function teamExecutionTone(status?: string | null): BadgeTone {
  const key = String(status || 'idle').toLowerCase();
  if (key === 'succeeded') return 'success';
  if (key === 'queued' || key === 'running') return 'active';
  if (key === 'waiting_user') return 'warning';
  if (key === 'failed') return 'danger';
  return 'neutral';
}

export const TEAM_JOIN_STAGE_LABELS: Readonly<Record<Exclude<TeamJoinStage, null>, string>> = Object.freeze({
  precheck_capacity: '预检席位与容量',
  send_invite: '母号发送邀请',
  await_invite_mail: '等待接收邀请邮件',
  open_invite_link: '解析并打开邀请链接',
  authenticate_target: '认证目标账号',
  accept_workspace_join: '确认加入工作区',
  verify_membership: '回查工作区成员状态',
});

export function teamJoinStageLabel(stage?: string | null): string {
  if (!stage) return '尚无活跃阶段';
  const key = stage as Exclude<TeamJoinStage, null>;
  return TEAM_JOIN_STAGE_LABELS[key] ?? stage;
}

export const TEAM_PROBE_STAGE_STEPS: ReadonlyArray<{ key: string; label: string }> = Object.freeze([
  { key: 'queued', label: '排队等待' },
  { key: 'authenticate_manager', label: '母号认证' },
  { key: 'discover_workspaces', label: '发现工作区' },
  { key: 'verify_permissions', label: '核验管理权限' },
]);

export const TEAM_CAPACITY_BASIS_LABELS: Readonly<Record<TeamCapacityBasis, string>> = Object.freeze({
  purchased_seats: '已购席位',
  planned_member_limit: '本地计划上限',
  hybrid_min: '已购与本地上限取小',
  unknown: '席位待确认',
});

export function teamCapacityBasisLabel(basis?: string | null): string {
  const key = String(basis || 'unknown') as TeamCapacityBasis;
  return TEAM_CAPACITY_BASIS_LABELS[key] ?? '席位待确认';
}

/** 严禁把 null 渲染为 0；0 表示明确 0 席，null 表示待同步/未返回。 */
export function formatNullableCount(value: number | null | undefined, nullText = '待同步', suffix = ''): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return nullText;
  }
  return `${value}${suffix}`;
}

export function formatSeatLimitDisplay(team: Pick<TeamDTO, 'purchased_seats' | 'planned_member_limit' | 'capacity'>): {
  primary: string;
  secondary: string;
  tone: BadgeTone;
} {
  const purchased = team.purchased_seats;
  const planned = team.planned_member_limit;
  const cap = team.capacity;

  if (cap.blocking_reason_code === 'team_limit_required') {
    return {
      primary: '未返回席位',
      secondary: '需设本地上限',
      tone: 'warning',
    };
  }
  const primaryParts: string[] = [];
  if (purchased !== null && purchased !== undefined) {
    primaryParts.push(`已购 ${purchased} 席`);
  } else {
    primaryParts.push('已购未返回');
  }
  if (planned !== null && planned !== undefined) {
    primaryParts.push(`上限 ${planned}`);
  }
  const remaining = cap.remaining_before_limit;
  const secondary = !cap.can_accept_new_joins && cap.blocking_reason_code
    ? teamReasonLabel(cap.blocking_reason_code)
    : remaining !== null && remaining !== undefined
      ? `可拉剩余 ${remaining} 席`
      : teamCapacityBasisLabel(cap.basis);

  const tone: BadgeTone = !cap.can_accept_new_joins
    ? (cap.blocking_reason_code === 'team_seat_full' || cap.blocking_reason_code === 'team_limit_reached' ? 'danger' : 'warning')
    : remaining !== null && remaining <= 1
      ? 'warning'
      : 'success';

  return {
    primary: primaryParts.join(' · '),
    secondary,
    tone,
  };
}

/** 邀请页双事实展示：第 2 列业务事实（invitation_state + membership_state），第 3 列执行与阶段。 */
export function formatInvitationBusinessFacts(row: Pick<TeamInvitationDTO, 'invitation_state' | 'membership_state'>): {
  primary: string;
  secondary: string;
  tone: BadgeTone;
} {
  const primary = teamInvitationStateLabel(row.invitation_state);
  const secondary = `成员：${teamMembershipLabel(row.membership_state)}`;
  let tone: BadgeTone = 'neutral';
  if (row.membership_state === 'joined') tone = 'success';
  else if (row.invitation_state === 'pending') tone = 'active';
  else if (row.invitation_state === 'revoked' || row.invitation_state === 'expired' || row.membership_state === 'removed') tone = 'danger';
  else if (row.invitation_state === 'unknown') tone = 'warning';
  return { primary, secondary, tone };
}

export function formatInvitationExecutionFacts(
  row: Pick<TeamInvitationDTO, 'execution_status' | 'stage' | 'waiting_reason_code'>,
): {
  primary: string;
  secondary: string;
  tone: BadgeTone;
} {
  const primary = teamExecutionLabel(row.execution_status);
  const waitingLabel = row.waiting_reason_code ? teamReasonLabel(row.waiting_reason_code) : '';
  const stageLabel = row.stage ? teamJoinStageLabel(row.stage) : '';
  const secondary = [stageLabel, waitingLabel].filter(Boolean).join(' · ') || '—';
  return {
    primary,
    secondary,
    tone: teamExecutionTone(row.execution_status),
  };
}

export function formatInvitationResultSummary(row: Pick<TeamInvitationDTO, 'execution_status' | 'membership_state' | 'invitation_state' | 'waiting_reason_code' | 'error'>): {
  label: string;
  secondary: string;
  detail: string;
  tone: BadgeTone;
} {
  if (row.error?.reason_code || row.error?.summary) {
    const label = teamReasonLabel(row.error.reason_code, row.error);
    const detail = [row.error.summary, row.error.detail].filter(Boolean).join('\n');
    return {
      label,
      secondary: row.error.reason_code || '',
      detail,
      tone: row.execution_status === 'waiting_user' ? 'warning' : 'danger',
    };
  }
  if (row.waiting_reason_code) {
    const label = teamReasonLabel(row.waiting_reason_code);
    return { label, secondary: '等待处理', detail: '', tone: 'warning' };
  }
  if (row.membership_state === 'joined') {
    return { label: '已确认入组', secondary: '', detail: '', tone: 'success' };
  }
  if (row.execution_status === 'queued' || row.execution_status === 'running') {
    return { label: '正在拉人入组', secondary: '', detail: '', tone: 'active' };
  }
  if (row.invitation_state === 'pending') {
    return { label: '待接受邀请', secondary: '可继续加入', detail: '', tone: 'warning' };
  }
  return { label: '—', secondary: '', detail: '', tone: 'neutral' };
}

export const CANDIDATE_ELIGIBILITY_BADGES: Readonly<Record<CandidateEligibilityState, { label: string; tone: BadgeTone }>> = Object.freeze({
  eligible: { label: '可直接加入', tone: 'success' },
  continue_existing_invite: { label: '续接已有邀请', tone: 'active' },
  already_member: { label: '已是本组成员', tone: 'neutral' },
  already_processing: { label: '入组执行中', tone: 'active' },
  another_team: { label: '已属其他Team', tone: 'warning' },
  missing_auth: { label: '缺认证材料', tone: 'danger' },
  unavailable: { label: '账号不可用', tone: 'danger' },
});

/** 根据 workspace_id 生成稳定柔和的头像色相，提升多工作区辨识度。 */
export function workspaceAvatarHue(seed: string): number {
  let hash = 0;
  const text = String(seed || 'team');
  for (let i = 0; i < text.length; i++) {
    hash = ((hash << 5) - hash + text.charCodeAt(i)) | 0;
  }
  const palette = [226, 202, 168, 258, 190, 240, 152, 28];
  return palette[Math.abs(hash) % palette.length]!;
}

export function workspaceInitials(name: string): string {
  const cleaned = String(name || '').trim();
  if (!cleaned) return 'TM';
  const words = cleaned.split(/[\s\-_·]+/).filter(Boolean);
  if (words.length >= 2) {
    return (Array.from(words[0]!)[0]! + Array.from(words[1]!)[0]!).toUpperCase();
  }
  return Array.from(cleaned).slice(0, 2).join('').toUpperCase();
}

export function isTeamActivelyRunning(team: Pick<TeamDTO, 'last_sync_status' | 'processing_count'> | null | undefined): boolean {
  if (!team) return false;
  return team.last_sync_status === 'queued' || team.last_sync_status === 'running' || team.processing_count > 0;
}

export function computeCapacityPercentage(cap: Pick<TeamCapacitySummary, 'effective_limit' | 'occupied_count'>): number | null {
  if (cap.effective_limit === null || cap.effective_limit <= 0 || cap.occupied_count === null) {
    return null;
  }
  return Math.min(100, Math.max(0, Math.round((cap.occupied_count / cap.effective_limit) * 100)));
}
