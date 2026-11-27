/** Team 管理类型直接复用生成的 OpenAPI 契约，未知远端事实保持 null。 */
import type { components, operations } from '../../api/teams-schema';

type Schemas = components['schemas'];
export type TeamDecimalId = Schemas['LocalId'];
export type TeamRole = Schemas['Role'];
export type TeamSyncStatus = Schemas['LastSyncStatus'];
export type TeamCapacityBasis = Schemas['CapacityBasis'];
export type BindingProbeStatus = Schemas['ProbeStatus'];
export type BindingProbeStage = Schemas['ProbeStage'];
export type TeamMembershipState = Schemas['MembershipState'];
export type TeamInvitationState = Schemas['InvitationState'];
export type TeamExecutionStatus = Schemas['ExecutionStatus'];
export type TeamJoinStage = Schemas['JoinStage'] | null;
export type TeamErrorSummary = Schemas['ErrorInfo'];
export type TeamActionAvailability = Schemas['AllowedAction'];
export type TeamManagerAccountSummary = Schemas['AccountRef'];
export type TeamCapacitySummary = Schemas['Capacity'];
export type TeamDTO = Schemas['TeamDTO'];
export type TeamListResponse = Schemas['TeamList'];
export type TeamDetailResponse = Schemas['TeamDetail'];
export type BindingProbeWorkspaceDTO = Schemas['ProbeWorkspace'];
export type BindingWorkspaceDTO = Schemas['ProbeWorkspace'];
export type BindingProbeCreateResponse = Schemas['BindingProbeReceipt'];
export type BindingProbeDTO = Schemas['BindingProbeDTO'];
export type TeamSyncActionResponse = Schemas['ActionReceipt'];
export type TeamCreatePayload = Schemas['TeamCreateRequest'];
export type TeamCreateResponse = Schemas['TeamCreated'];
export type TeamPatchPayload = Schemas['TeamPatchRequest'];
export type TeamPatchResponse = Schemas['TeamUpdated'];
export type TeamSyncBulkItem = Schemas['SyncBulkItem'];
export type TeamSyncBulkResponse = Schemas['SyncBulkReceipt'];
export type TeamMemberDTO = Schemas['MemberDTO'];
export type TeamMembersListResponse = Schemas['MemberList'];
export type TeamInvitationDTO = Schemas['InvitationDTO'];
export type TeamInvitationsListResponse = Schemas['InvitationList'];
export type CandidateEligibilityState = Schemas['CandidateCategory'];
export type TeamCandidateDTO = Schemas['CandidateDTO'];
export type TeamCandidatesListResponse = Schemas['CandidateList'];
export type CandidateResolveResponse = Schemas['CandidateResolveResult'];
export type CandidateResolveAmbiguousItem = Pick<Schemas['CandidateResolveItem'], 'input' | 'candidates'>;
export type JoinPreviewTargetPayload = Schemas['JoinPreviewRequest'];
export type JoinPreviewCounts = Schemas['PreviewCounts'];
export type JoinPreviewCapacity = Schemas['Capacity'];
export type JoinPreviewResponse = Schemas['JoinPreviewDTO'];
export type JoinSubmitPayload = Schemas['JoinRequest'];
export type JoinRequestDTO = Schemas['JoinRequestDTO'];
export type JoinRequestItemDTO = Schemas['JoinItemDTO'];
export type JoinRequestItemsResponse = Schemas['JoinRequestItems'];
export type InvitationActionResponse = Schemas['JoinRequestDTO'];
export type InvitationBulkActionResponse = Schemas['JoinRequestDTO'];

/** 查询字段复用实际 HTTP 参数；默认值由服务端填写，调用方可以省略。 */
export type TeamListQuery = NonNullable<operations['listTeams']['parameters']['query']>;
export type TeamMembersQuery = NonNullable<operations['listTeamMembers']['parameters']['query']>;
export type TeamInvitationsQuery = NonNullable<operations['listTeamInvitations']['parameters']['query']>;
export type TeamCandidatesQuery = NonNullable<operations['listTeamCandidates']['parameters']['query']>;
export type JoinRequestItemsQuery = NonNullable<operations['getTeamJoinRequest']['parameters']['query']>;

/** 供通用筛选控件展示的视图类型，各接口的 facets 仍使用各自生成类型。 */
export interface TeamFacetOption { value: string; label?: string; count: number }
export type TeamFacets = Readonly<Record<string, readonly TeamFacetOption[] | undefined>>;

/** 普通账号接口的已确认成员关系摘要，不附加未确认邀请事实。 */
export type AccountTeamMembershipBadge = Pick<TeamDTO, 'workspace_id' | 'name' | 'display_name' | 'role'> & {
  team_id: TeamDecimalId;
  membership_state: 'joined';
  last_verified_at: Schemas['Timestamp'] | null;
};

export interface TeamsNavigationState {
  tab: 'teams';
  view: 'list' | 'detail';
  team_id?: TeamDecimalId;
  section?: 'members' | 'invitations';
}
export interface AccountsJoinRequestPayload {
  mode: 'explicit' | 'selection';
  accountIds?: readonly TeamDecimalId[];
  expectedEmails?: Readonly<Record<string, string>>;
  selectionId?: TeamDecimalId;
  selectionRevision?: number;
  selectedCount?: number;
  targetTeamId?: TeamDecimalId | null;
}
/** 宿主导航只传显示所需上下文，不作为后端 TeamDTO 使用。 */
export interface TeamsHostCallbacks {
  notify(message: string): void;
  formatDateTime(value: string | null | undefined): string;
  openTask(taskId: TeamDecimalId, runId?: TeamDecimalId | null): void;
  openTasksForTeam(teamId: TeamDecimalId, teamName?: string): void;
  openAccountDetail(accountId: TeamDecimalId): void;
  openAccountsCandidateMode(team: { team_id: TeamDecimalId; effective_name: string }): void;
  onNavigation(state: TeamsNavigationState, mode: 'push' | 'replace'): void;
}

const POSITIVE_DECIMAL_RE = /^[1-9]\d*$/;
const MAX_LOCAL_ID = '9223372036854775807';

/** 校验并原样返回正整数十进制字符串，禁止转成 JavaScript Number。 */
export function teamDecimalId(value: unknown, label = '标识'): TeamDecimalId {
  const normalized = typeof value === 'number' && Number.isSafeInteger(value) && value > 0
    ? String(value)
    : typeof value === 'string'
      ? value.trim()
      : '';
  if (
    !POSITIVE_DECIMAL_RE.test(normalized) ||
    normalized.length > MAX_LOCAL_ID.length ||
    (normalized.length === MAX_LOCAL_ID.length && normalized > MAX_LOCAL_ID)
  ) {
    throw new Error(`${label}格式无效`);
  }
  return normalized;
}

export function optionalTeamDecimalId(value: unknown): TeamDecimalId | null {
  if (value === null || value === undefined || value === '' || value === 0 || value === '0') {
    return null;
  }
  return teamDecimalId(value);
}

const TEAM_ID_FIELDS = new Set([
  'id',
  'team_id',
  'existing_team_id',
  'existing_join_request_id',
  'already_bound_team_id',
  'account_id',
  'manager_account_id',
  'probe_id',
  'invitation_id',
  'member_id',
  'join_request_id',
  'selection_id',
  'task_id',
  'run_id',
  'latest_task_id',
  'latest_run_id',
  'last_sync_task_id',
  'last_sync_run_id',
  'batch_id',
]);

const TEAM_ID_ARRAY_FIELDS = new Set([
  'team_ids',
  'account_ids',
  'invitation_ids',
  'task_ids',
  'run_ids',
]);

/** 解析 JSON 时将所有 ID 字段保持为精确十进制字符串，彻底规避 64 位整数精度丢失。 */
export function parseTeamJson(source: string): unknown {
  const replacements: Array<{ start: number; end: number; text: string }> = [];
  let cursor = 0;
  const fail = () => {
    throw new SyntaxError('Team 接口响应 JSON 格式无效');
  };
  const skipSpace = () => {
    while (/[\t\n\r ]/.test(source[cursor] || '\0')) cursor++;
  };
  function readString(): string {
    const start = cursor;
    if (source[cursor++] !== '"') return fail();
    while (cursor < source.length) {
      const ch = source[cursor++];
      if (ch === '\\') {
        cursor++;
        continue;
      }
      if (ch === '"') return JSON.parse(source.slice(start, cursor)) as string;
    }
    return fail();
  }
  function walk(field = '', depth = 0): void {
    if (depth > 256) throw new SyntaxError('Team 接口响应嵌套过深');
    skipSpace();
    const ch = source[cursor];
    if (ch === '{') {
      cursor++;
      skipSpace();
      if (source[cursor] === '}') {
        cursor++;
        return;
      }
      for (;;) {
        skipSpace();
        const key = readString();
        skipSpace();
        if (source[cursor++] !== ':') fail();
        walk(key, depth + 1);
        skipSpace();
        const sep = source[cursor++];
        if (sep === '}') return;
        if (sep !== ',') fail();
      }
    }
    if (ch === '[') {
      cursor++;
      skipSpace();
      if (source[cursor] === ']') {
        cursor++;
        return;
      }
      const itemField = TEAM_ID_ARRAY_FIELDS.has(field) ? 'team_id' : '';
      for (;;) {
        walk(itemField, depth + 1);
        skipSpace();
        const sep = source[cursor++];
        if (sep === ']') return;
        if (sep !== ',') fail();
      }
    }
    if (ch === '"') {
      readString();
      return;
    }
    for (const literal of ['true', 'false', 'null']) {
      if (source.startsWith(literal, cursor)) {
        cursor += literal.length;
        return;
      }
    }
    const match = source.slice(cursor).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);
    if (!match) return fail();
    const token = match[0];
    const start = cursor;
    cursor += token.length;
    if (TEAM_ID_FIELDS.has(field) && /^[1-9]\d*$/.test(token)) {
      replacements.push({ start, end: cursor, text: JSON.stringify(token) });
    }
  }
  walk();
  skipSpace();
  if (cursor !== source.length) fail();
  let output = '';
  let offset = 0;
  for (const item of replacements) {
    output += source.slice(offset, item.start) + item.text;
    offset = item.end;
  }
  return JSON.parse(output + source.slice(offset));
}
