/** Team 管理前后端共享接口契约与十进制字符串 ID 边界。 */

export type TeamDecimalId = string;

export type TeamRole = 'owner' | 'admin' | 'member' | 'unknown';
export type TeamSyncStatus = 'never' | 'queued' | 'running' | 'success' | 'failed';
export type TeamCapacityBasis = 'purchased_seats' | 'planned_member_limit' | 'hybrid_min' | 'unknown';

export type BindingProbeStatus = 'queued' | 'running' | 'success' | 'failed' | 'expired';
export type BindingProbeStage = 'queued' | 'authenticate_manager' | 'discover_workspaces' | 'verify_permissions' | 'completed';

export type TeamMembershipState = 'joined' | 'not_joined' | 'removed' | 'left' | 'unknown';
export type TeamInvitationState = 'not_sent' | 'pending' | 'accepted' | 'revoked' | 'expired' | 'unknown';
export type TeamExecutionStatus = 'idle' | 'queued' | 'running' | 'waiting_user' | 'succeeded' | 'failed' | 'cancelled';
export type TeamJoinStage =
  | 'precheck_capacity'
  | 'send_invite'
  | 'await_invite_mail'
  | 'open_invite_link'
  | 'authenticate_target'
  | 'accept_workspace_join'
  | 'verify_membership'
  | null;

export interface TeamErrorSummary {
  reason_code: string;
  summary: string;
  detail?: string | null;
}

export interface TeamActionAvailability {
  enabled: boolean;
  reason_code: string | null;
  reason: string | null;
}

export interface TeamManagerAccountSummary {
  account_id: TeamDecimalId | null;
  email: string;
  archived: boolean;
  account_status: string;
}

export interface TeamCapacitySummary {
  basis: TeamCapacityBasis;
  effective_limit: number | null;
  occupied_count: number | null;
  remaining_before_limit: number | null;
  can_accept_new_joins: boolean;
  blocking_reason_code: string | null;
}

export interface TeamDTO {
  team_id: TeamDecimalId;
  revision: number;
  workspace_id: string;
  workspace_name: string;
  display_name: string | null;
  effective_name: string;
  plan_type: string;
  manager_account: TeamManagerAccountSummary;
  manager_role: TeamRole;
  can_manage: boolean | null;
  seat_policy: 'remaining_purchased_only';
  purchased_seats: number | null;
  planned_member_limit: number | null;
  confirmed_member_count: number | null;
  pending_invite_count: number | null;
  processing_count: number;
  capacity: TeamCapacitySummary;
  last_sync_status: TeamSyncStatus;
  last_synced_at: string | null;
  last_sync_task_id: TeamDecimalId | null;
  last_sync_run_id: TeamDecimalId | null;
  last_sync_error: TeamErrorSummary | null;
  created_at: string;
  updated_at: string;
}

export interface TeamFacetOption {
  value: string;
  label?: string;
  count: number;
}

export type TeamFacets = Readonly<Record<string, readonly TeamFacetOption[] | undefined>>;

export interface TeamListSummary {
  total_teams: number;
  syncing_teams: number;
  attention_teams: number;
}

export interface TeamListResponse {
  items: TeamDTO[];
  total: number;
  page: number;
  page_size: number;
  facets: TeamFacets;
  summary: TeamListSummary;
}

export interface TeamDetailResponse {
  team: TeamDTO;
  actions: {
    sync: TeamActionAvailability;
    reverify: TeamActionAvailability;
    join: TeamActionAvailability;
  };
  permission_verified_at: string | null;
}

export interface BindingProbeWorkspaceDTO {
  workspace_id: string;
  workspace_name: string;
  plan_type: string;
  is_team_workspace: boolean;
  role: TeamRole;
  can_manage: boolean;
  purchased_seats: number | null;
  confirmed_member_count: number | null;
  pending_invite_count: number | null;
  already_bound_team_id: TeamDecimalId | null;
  selectable: boolean;
  disabled_reason_code: string | null;
  disabled_reason: string | null;
}

export interface BindingProbeCreateResponse {
  probe_id: TeamDecimalId;
  status: BindingProbeStatus;
  task_id: TeamDecimalId | null;
  run_id: TeamDecimalId | null;
}

export interface BindingProbeDTO {
  probe_id: TeamDecimalId;
  probe_revision: string;
  manager_account_id: TeamDecimalId;
  manager_email: string;
  target_workspace_id: string | null;
  status: BindingProbeStatus;
  stage: BindingProbeStage;
  task_id: TeamDecimalId | null;
  run_id: TeamDecimalId | null;
  expires_at: string | null;
  suggested_workspace_id: string | null;
  workspaces: BindingProbeWorkspaceDTO[];
  error: TeamErrorSummary | null;
}

export interface TeamSyncActionResponse {
  team_id: TeamDecimalId;
  status: 'queued' | 'running';
  task_id: TeamDecimalId | null;
  run_id: TeamDecimalId | null;
  reused: boolean;
}

export interface TeamCreatePayload {
  manager_account_id: TeamDecimalId;
  workspace_id: string;
  probe_id: TeamDecimalId;
  probe_revision: string;
  display_name?: string | null;
  planned_member_limit?: number | null;
}

export interface TeamCreateResponse {
  team: TeamDTO;
  sync: Omit<TeamSyncActionResponse, 'team_id'>;
}

export interface TeamPatchPayload {
  expected_revision: number;
  display_name?: string | null;
  planned_member_limit?: number | null;
  manager_account_id?: TeamDecimalId;
  probe_id?: TeamDecimalId;
  probe_revision?: string;
}

export interface TeamPatchResponse {
  team: TeamDTO;
}

export interface TeamSyncBulkItem {
  team_id: TeamDecimalId;
  outcome: 'queued' | 'reused' | 'skipped';
  task_id: TeamDecimalId | null;
  run_id: TeamDecimalId | null;
  reason_code: string | null;
  reason: string | null;
}

export interface TeamSyncBulkResponse {
  queued_count: number;
  reused_count: number;
  skipped_count: number;
  items: TeamSyncBulkItem[];
}

export interface TeamMemberLocalAccount {
  account_id: TeamDecimalId;
  email: string;
  archived: boolean;
  account_status: string;
  current_plan_type?: string | null;
}

export interface TeamMemberDTO {
  member_id: TeamDecimalId;
  team_id: TeamDecimalId;
  remote_user_id: string | null;
  email: string;
  display_name: string | null;
  role: TeamRole;
  membership_state: TeamMembershipState;
  joined_at: string | null;
  last_seen_in_sync_at: string | null;
  local_account: TeamMemberLocalAccount | null;
  latest_task_id: TeamDecimalId | null;
  latest_run_id: TeamDecimalId | null;
}

export interface TeamMembersListResponse {
  items: TeamMemberDTO[];
  total: number;
  page: number;
  page_size: number;
  facets: TeamFacets;
}

export interface TeamInvitationTargetAccount {
  account_id: TeamDecimalId | null;
  email: string;
  archived: boolean;
  account_status: string;
  has_access_token: boolean;
  has_account_password: boolean;
  totp_enabled: boolean;
  email_invalid: boolean;
}

export interface TeamInvitationDTO {
  invitation_id: TeamDecimalId;
  team_id: TeamDecimalId;
  join_request_id: TeamDecimalId | null;
  remote_invite_id: string | null;
  email: string;
  invite_role: 'member' | 'admin';
  target_account: TeamInvitationTargetAccount;
  invitation_state: TeamInvitationState;
  membership_state: TeamMembershipState;
  execution_status: TeamExecutionStatus;
  stage: TeamJoinStage;
  waiting_reason_code: string | null;
  latest_task_id: TeamDecimalId | null;
  latest_run_id: TeamDecimalId | null;
  error: TeamErrorSummary | null;
  actions: {
    can_continue: boolean;
    can_retry: boolean;
    can_open_task: boolean;
    disabled_reason_code: string | null;
  };
  invited_at: string | null;
  accepted_at: string | null;
  updated_at: string;
}

export interface TeamInvitationsListResponse {
  items: TeamInvitationDTO[];
  total: number;
  page: number;
  page_size: number;
  facets: TeamFacets;
}

export interface AccountTeamMembershipBadge {
  team_id: TeamDecimalId;
  workspace_id: string;
  workspace_name: string;
  display_name: string | null;
  role: TeamRole;
  membership_state: 'joined' | 'invited' | 'joining';
}

export type CandidateEligibilityState =
  | 'eligible'
  | 'continue_existing_invite'
  | 'already_member'
  | 'already_processing'
  | 'another_team'
  | 'missing_auth'
  | 'unavailable';

export interface TeamCandidateDTO {
  account_id: TeamDecimalId;
  email: string;
  user_name: string | null;
  archived: boolean;
  account_status: string;
  current_plan_type: string | null;
  has_access_token: boolean;
  has_account_password: boolean;
  totp_enabled: boolean;
  email_invalid: boolean;
  email_source: string | null;
  active_team: {
    team_id: TeamDecimalId;
    effective_name: string;
    role: TeamRole;
    membership_state: string;
  } | null;
  eligibility: {
    selectable: boolean;
    state: CandidateEligibilityState;
    reason_code: string | null;
    reason: string | null;
  };
}

export interface TeamCandidatesListResponse {
  items: TeamCandidateDTO[];
  total: number;
  page: number;
  page_size: number;
  facets: TeamFacets;
}

export interface CandidateResolveAmbiguousItem {
  input: string;
  candidates: Array<{
    account_id: TeamDecimalId;
    email: string;
    archived: boolean;
    eligibility: TeamCandidateDTO['eligibility'];
  }>;
}

export interface CandidateResolveResponse {
  matched: TeamCandidateDTO[];
  not_found: string[];
  ambiguous: CandidateResolveAmbiguousItem[];
}

export type JoinPreviewTargetPayload =
  | { account_ids: TeamDecimalId[]; expected_emails?: Readonly<Record<string, string>> }
  | { selection_id: TeamDecimalId; selection_revision: string };

export interface JoinPreviewCounts {
  selected_total: number;
  new_join_count: number;
  continue_invite_count: number;
  already_member_skip_count: number;
  already_processing_skip_count: number;
  another_team_skip_count: number;
  missing_auth_skip_count: number;
  unavailable_skip_count: number;
  email_mismatch_skip_count: number;
}

export interface JoinPreviewCapacity {
  seat_policy: 'remaining_purchased_only';
  basis: TeamCapacityBasis;
  purchased_seats: number | null;
  planned_member_limit: number | null;
  effective_limit: number | null;
  occupied_count: number | null;
  additional_required: number;
  remaining_after_submit: number | null;
  exceeds_limit: boolean;
  can_submit: boolean;
  blocking_reason_code: string | null;
  blocking_reason: string | null;
}

export interface JoinPreviewSampleItem {
  account_id: TeamDecimalId;
  email: string;
  outcome:
    | 'will_join'
    | 'will_continue_invite'
    | 'skip_already_member'
    | 'skip_already_processing'
    | 'skip_another_team'
    | 'skip_missing_auth'
    | 'skip_unavailable'
    | 'skip_email_mismatch';
  reason_code: string | null;
  reason: string | null;
}

export interface JoinPreviewResponse {
  team_id: TeamDecimalId;
  snapshot_revision: number;
  snapshot_at: string;
  team_last_synced_at: string | null;
  requires_sync: boolean;
  counts: JoinPreviewCounts;
  capacity: JoinPreviewCapacity;
  sample_items: JoinPreviewSampleItem[];
}

export type JoinSubmitPayload = JoinPreviewTargetPayload & {
  expected_team_revision: number;
};

export interface JoinRequestItemDTO {
  account_id: TeamDecimalId;
  email: string;
  outcome: 'queued' | 'reused_active' | 'skipped';
  invitation_id: TeamDecimalId | null;
  task_id: TeamDecimalId | null;
  run_id: TeamDecimalId | null;
  reason_code: string | null;
  reason: string | null;
}

export interface JoinRequestDTO {
  join_request_id: TeamDecimalId;
  team_id: TeamDecimalId;
  status: 'accepted' | 'completed';
  summary: {
    requested_count: number;
    queued_count: number;
    reused_active_count: number;
    skipped_count: number;
  };
  items: JoinRequestItemDTO[];
  total_items: number;
  page: number;
  page_size: number;
}

export interface InvitationActionResponse {
  invitation_id: TeamDecimalId;
  outcome: 'queued' | 'reused_active';
  task_id: TeamDecimalId | null;
  run_id: TeamDecimalId | null;
}

export interface InvitationBulkActionItem {
  invitation_id: TeamDecimalId;
  outcome: 'queued' | 'reused_active' | 'skipped';
  task_id: TeamDecimalId | null;
  run_id: TeamDecimalId | null;
  reason_code: string | null;
  reason: string | null;
}

export interface InvitationBulkActionResponse {
  queued_count: number;
  reused_active_count: number;
  skipped_count: number;
  items: InvitationBulkActionItem[];
}

export interface TeamListQuery {
  page: number;
  page_size: number;
  include_facets?: 0 | 1;
  q?: string;
  manager_account_id?: string;
  role?: string;
  last_sync_status?: string;
}

export interface TeamMembersQuery {
  page: number;
  page_size: number;
  include_facets?: 0 | 1;
  q?: string;
  role?: string;
  membership_state?: string;
  linked?: 'all' | 'linked' | 'unlinked';
}

export interface TeamInvitationsQuery {
  page: number;
  page_size: number;
  include_facets?: 0 | 1;
  q?: string;
  invitation_state?: string;
  membership_state?: string;
  execution_status?: string;
  stage?: string;
  join_request_id?: string;
}

export interface TeamCandidatesQuery {
  page: number;
  page_size: number;
  q?: string;
  scope?: 'unassigned' | 'all';
  archived?: '0' | 'only' | 'all';
  has_access_token?: '0' | '1';
  has_password?: '0' | '1';
  totp_enabled?: '0' | '1';
  email_status?: 'unmarked' | 'invalid';
}

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
  selectionRevision?: string;
  selectedCount?: number;
  targetTeamId?: TeamDecimalId | null;
}

export interface TeamsHostCallbacks {
  notify(message: string): void;
  formatDateTime(value: string | null | undefined): string;
  openTask(taskId: TeamDecimalId, runId?: TeamDecimalId | null): void;
  openTasksForTeam(teamId: TeamDecimalId, teamName?: string): void;
  openAccountDetail(accountId: TeamDecimalId): void;
  openAccountsCandidateMode(team: Pick<TeamDTO, 'team_id' | 'effective_name'>): void;
  onNavigation(state: TeamsNavigationState, mode: 'push' | 'replace'): void;
}

const POSITIVE_DECIMAL_RE = /^[1-9]\d*$/;

/** 校验并原样返回正整数十进制字符串，禁止转成 JavaScript Number。 */
export function teamDecimalId(value: unknown, label = '标识'): TeamDecimalId {
  const normalized = typeof value === 'number' && Number.isSafeInteger(value) && value > 0
    ? String(value)
    : typeof value === 'string'
      ? value.trim()
      : '';
  if (!POSITIVE_DECIMAL_RE.test(normalized)) {
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
