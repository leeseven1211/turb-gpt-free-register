/** Team 业务事实、执行状态与未知容量的中文展示。 */
import type {
  TeamDTO, TeamInvitationDTO, TeamRole,
} from './contracts';
import { shortErrorLabel } from '../../shared/errorLabels';

export type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'active';

export const TEAM_REASON_LABELS: Readonly<Record<string, string>> = Object.freeze({
  probe_expired: '核验结果已过期', probe_not_found: '核验记录不存在',
  team_workspace_unavailable: '工作区暂不可用', team_workspace_mismatch: '工作区身份不符',
  manager_permission_unconfirmed: '管理权限待核验', team_permission_denied: '母号无管理权限',
  team_already_bound: '工作区已绑定', team_auth_required: '账号登录待完成',
  revision_conflict: '工作区状态已变', team_limit_required: '需先设本地上限',
  team_invite_rate_limited: '发送邀请被限流', team_invite_rejected: '邀请被远端拒绝',
  team_invitation_revoked: '邀请已被撤回', team_invitation_expired: '邀请已过期',
  missing_auth_materials: '缺少认证材料', account_identity_changed: '账号身份已变化',
  account_unavailable: '账号不可用', account_not_found: '账号不存在',
  already_in_another_team: '已归属其他Team', already_member: '已是本组成员',
  team_member_unconfirmed: '成员关系待确认', team_save_failed: '本地保存失败',
  team_execution_lost: '执行租约已失效', team_store_unavailable: '团队存储不可用',
  waiting_account: '等待账号空闲', waiting_child: '等待执行步骤', waiting_sync: '等待完整同步',
  waiting_capacity: '等待可用名额', waiting_remote: '等待远端回执',
  same_team_active: '本组已有活跃执行', no_eligible_targets: '没有可处理目标',
  selection_expired: '固定名单已过期', selection_consumed: '固定名单已使用',
});

export function teamReasonLabel(code?: string | null, error?: { code?: string; message?: string } | null): string {
  const value = String(code || error?.code || '').trim();
  return TEAM_REASON_LABELS[value] || (value ? shortErrorLabel({ code: value, error_code: value }) : error?.message || '状态待核对');
}

export function teamDisplayName(team: Pick<TeamDTO, 'display_name' | 'name' | 'workspace_id'>): string {
  return team.display_name || team.name || team.workspace_id;
}

export function teamEffectiveLimit(team: Pick<TeamDTO, 'purchased_seats' | 'planned_member_limit'>): number | null {
  if (team.purchased_seats !== null) {
    return team.planned_member_limit === null ? team.purchased_seats : Math.min(team.purchased_seats, team.planned_member_limit);
  }
  return team.planned_member_limit;
}

export const TEAM_ROLE_LABELS: Readonly<Record<TeamRole, string>> = Object.freeze({ owner: '所有者', admin: '管理员', member: '成员', unknown: '待核验' });
export function teamRoleLabel(role?: string | null): string { return TEAM_ROLE_LABELS[role as TeamRole] || '待核验'; }
export function teamRoleTone(role?: string | null): BadgeTone { return role === 'owner' ? 'active' : role === 'admin' ? 'success' : role === 'unknown' ? 'warning' : 'neutral'; }

export const TEAM_SYNC_LABELS: Readonly<Record<string, string>> = Object.freeze({ never: '未同步', queued: '排队同步', running: '同步中', success: '已同步', partial_success: '部分同步', failed: '同步失败', interrupted: '同步中断' });
export function teamSyncLabel(status?: string | null): string { return TEAM_SYNC_LABELS[status || 'never'] || '待同步'; }
export function teamSyncTone(status?: string | null): BadgeTone { return status === 'success' ? 'success' : status === 'queued' || status === 'running' ? 'active' : status === 'failed' ? 'danger' : status === 'partial_success' || status === 'interrupted' ? 'warning' : 'neutral'; }

export const TEAM_MEMBERSHIP_LABELS: Readonly<Record<string, string>> = Object.freeze({ joined: '已加入', left: '已退出', unconfirmed: '待确认' });
export function teamMembershipLabel(state?: string | null): string { return TEAM_MEMBERSHIP_LABELS[state || 'unconfirmed'] || '待确认'; }
export function teamMembershipTone(state?: string | null): BadgeTone { return state === 'joined' ? 'success' : state === 'left' ? 'danger' : 'warning'; }

export const TEAM_INVITATION_LABELS: Readonly<Record<string, string>> = Object.freeze({ not_sent: '未发邀请', pending: '待接受邀请', accepted: '邀请已接受', revoked: '邀请已撤回', expired: '邀请已过期', unconfirmed: '邀请待确认' });
export function teamInvitationStateLabel(state?: string | null): string { return TEAM_INVITATION_LABELS[state || 'unconfirmed'] || '邀请待确认'; }

export const TEAM_EXECUTION_LABELS: Readonly<Record<string, string>> = Object.freeze({ none: '未执行', queued: '排队中', running: '执行中', waiting: '等待中', cancelling: '正在取消', settling: '正在结算', stopping: '正在停止', success: '已完成', partial_success: '部分成功', failed: '执行失败', stopped: '已停止', cancelled: '已取消', interrupted: '执行中断', deactivated: '账号已停用', unsupported: '暂不支持' });
export const TEAM_ACTIVE_EXECUTION_STATUSES = new Set(['queued', 'running', 'waiting', 'cancelling', 'settling', 'stopping']);
export function teamExecutionLabel(status?: string | null): string { return TEAM_EXECUTION_LABELS[status || 'none'] || '状态待核对'; }
export function teamExecutionTone(status?: string | null): BadgeTone { return status === 'success' ? 'success' : TEAM_ACTIVE_EXECUTION_STATUSES.has(status || '') ? 'active' : status === 'failed' || status === 'deactivated' ? 'danger' : status === 'partial_success' || status === 'interrupted' || status === 'unsupported' ? 'warning' : 'neutral'; }

export const TEAM_JOIN_STAGE_LABELS: Readonly<Record<string, string>> = Object.freeze({ queued: '排队等待', manager_verify: '核验母号权限', state_check: '核对业务事实', invite: '发送邀请', member_auth: '认证成员账号', accept: '接受邀请', member_verify: '核验成员关系', persist: '保存认证上下文', complete: '执行结束' });
export function teamJoinStageLabel(stage?: string | null): string { return stage ? TEAM_JOIN_STAGE_LABELS[stage] || stage : '尚无活跃阶段'; }
export const TEAM_PROBE_STAGE_STEPS = Object.freeze([{ key: 'queued', label: '排队等待' }, { key: 'manager_auth', label: '母号认证' }, { key: 'workspace_discovery', label: '发现工作区' }, { key: 'permission_check', label: '核验管理权限' }]);
export const TEAM_CAPACITY_BASIS_LABELS: Readonly<Record<string, string>> = Object.freeze({ purchased_seats: '已购席位', planned_member_limit: '本地计划上限', unavailable: '席位待确认' });
export function teamCapacityBasisLabel(basis?: string | null): string { return TEAM_CAPACITY_BASIS_LABELS[basis || 'unavailable'] || '席位待确认'; }
export function formatNullableCount(value: number | null | undefined, nullText = '待同步', suffix = ''): string { return value === null || value === undefined || !Number.isFinite(value) ? nullText : `${value}${suffix}`; }

/** 列表和详情没有去重占位并集，余量留待加入预检核算。 */
export function formatSeatLimitDisplay(team: Pick<TeamDTO, 'purchased_seats' | 'planned_member_limit'>): { primary: string; secondary: string; tone: BadgeTone } {
  const limit = teamEffectiveLimit(team);
  return { primary: `已购${team.purchased_seats === null ? '未返回' : ` ${team.purchased_seats} 席`}${team.planned_member_limit === null ? '' : ` · 上限 ${team.planned_member_limit}`}`, secondary: limit === null ? '需设本地上限' : '余量待预检', tone: limit === null ? 'warning' : 'neutral' };
}
export function formatInvitationBusinessFacts(row: Pick<TeamInvitationDTO, 'invitation_state' | 'membership_state'>): { primary: string; secondary: string; tone: BadgeTone } {
  return { primary: teamInvitationStateLabel(row.invitation_state), secondary: `成员：${teamMembershipLabel(row.membership_state)}`, tone: row.membership_state === 'joined' ? 'success' : row.invitation_state === 'pending' ? 'active' : row.invitation_state === 'revoked' || row.invitation_state === 'expired' ? 'danger' : 'neutral' };
}
export function formatInvitationExecutionFacts(row: Pick<TeamInvitationDTO, 'latest_execution'>): { primary: string; secondary: string; tone: BadgeTone } {
  const execution = row.latest_execution;
  return { primary: teamExecutionLabel(execution.status), secondary: [teamJoinStageLabel(execution.stage), execution.waiting_reason_code ? teamReasonLabel(execution.waiting_reason_code) : ''].filter(Boolean).join(' · '), tone: teamExecutionTone(execution.status) };
}
export function formatInvitationResultSummary(row: Pick<TeamInvitationDTO, 'latest_execution' | 'membership_state' | 'invitation_state'>): { label: string; secondary: string; detail: string; tone: BadgeTone } {
  const execution = row.latest_execution;
  const error = execution.error_info;
  if (error) return { label: teamReasonLabel(error.code, error), secondary: error.code, detail: error.message, tone: 'danger' };
  if (execution.waiting_reason_code) return { label: teamReasonLabel(execution.waiting_reason_code), secondary: '等待处理', detail: '', tone: 'warning' };
  if (row.membership_state === 'joined') return { label: '已确认入组', secondary: '', detail: '', tone: 'success' };
  if (TEAM_ACTIVE_EXECUTION_STATUSES.has(execution.status)) return { label: '正在处理加入', secondary: '', detail: '', tone: 'active' };
  return { label: row.invitation_state === 'pending' ? '待接受邀请' : '—', secondary: row.invitation_state === 'pending' ? '可继续加入' : '', detail: '', tone: row.invitation_state === 'pending' ? 'warning' : 'neutral' };
}
export const CANDIDATE_ELIGIBILITY_BADGES: Readonly<Record<string, { label: string; tone: BadgeTone }>> = Object.freeze({ new: { label: '可提交加入', tone: 'success' }, resume_invite: { label: '续接已有邀请', tone: 'active' }, already_member: { label: '已是本组成员', tone: 'neutral' }, same_team_active: { label: '复用活跃执行', tone: 'active' }, another_team: { label: '已属其他Team', tone: 'warning' }, missing_auth: { label: '缺认证材料', tone: 'danger' }, unavailable: { label: '账号不可用', tone: 'danger' } });
export function workspaceAvatarHue(seed: string): number { let hash = 0; for (const char of String(seed || 'team')) hash = ((hash << 5) - hash + char.charCodeAt(0)) | 0; return [226, 202, 168, 258, 190, 240, 152, 28][Math.abs(hash) % 8]!; }
export function workspaceInitials(name: string): string { const text = String(name || '').trim(); if (!text) return 'TM'; const words = text.split(/[\s\-_·]+/).filter(Boolean); return (words.length >= 2 ? Array.from(words[0]!)[0]! + Array.from(words[1]!)[0]! : Array.from(text).slice(0, 2).join('')).toUpperCase(); }
export function isTeamActivelyRunning(team: Pick<TeamDTO, 'last_sync_status' | 'processing_count'> | null | undefined): boolean { return Boolean(team && (team.last_sync_status === 'queued' || team.last_sync_status === 'running' || (team.processing_count ?? 0) > 0)); }
export function computeCapacityPercentage(cap: { effective_limit: number | null; occupied_count: number | null }): number | null { return cap.effective_limit === null || cap.effective_limit <= 0 || cap.occupied_count === null ? null : Math.min(100, Math.max(0, Math.round(cap.occupied_count / cap.effective_limit * 100))); }
