/** Team 管理 HTTP 客户端：统一解包 `{ok, request_id, data}`、保持十进制字符串 ID 并管理写操作 Idempotency-Key。 */

import { ApiError } from './client';
import type { AccountQuerySpec } from '../features/accounts/queryAdapter';
import {
  parseTeamJson,
  teamDecimalId,
  type BindingProbeCreateResponse,
  type BindingProbeDTO,
  type CandidateResolveResponse,
  type InvitationActionResponse,
  type InvitationBulkActionResponse,
  type JoinPreviewResponse,
  type JoinPreviewTargetPayload,
  type JoinRequestDTO,
  type JoinSubmitPayload,
  type TeamCandidatesListResponse,
  type TeamCandidatesQuery,
  type TeamCreatePayload,
  type TeamCreateResponse,
  type TeamDecimalId,
  type TeamDetailResponse,
  type TeamInvitationDTO,
  type TeamInvitationsListResponse,
  type TeamInvitationsQuery,
  type TeamListQuery,
  type TeamListResponse,
  type TeamMembersListResponse,
  type TeamMembersQuery,
  type TeamPatchPayload,
  type TeamPatchResponse,
  type TeamSyncActionResponse,
  type TeamSyncBulkResponse,
} from '../features/teams/contracts';

export class TeamApiError extends ApiError {
  field: string | null;
  retryable: boolean;
  details: Readonly<Record<string, unknown>>;
  requestId: string;

  constructor(
    message: string,
    status: number,
    options: {
      code?: string;
      field?: string | null;
      retryable?: boolean;
      details?: Record<string, unknown> | null;
      requestId?: string;
    } = {},
  ) {
    super(message, status, options.code || '');
    this.name = 'TeamApiError';
    this.field = options.field ?? null;
    this.retryable = Boolean(options.retryable);
    this.details = Object.freeze({ ...(options.details || {}) });
    this.requestId = options.requestId || '';
  }
}

interface TeamSuccessEnvelope<T> {
  ok: true;
  request_id?: string;
  data: T;
}

interface TeamErrorEnvelope {
  ok?: false;
  request_id?: string;
  error?:
    | string
    | {
        code?: string;
        message?: string;
        field?: string | null;
        retryable?: boolean;
        details?: Record<string, unknown>;
      };
  message?: string;
  code?: string;
}

function redirectLogin(): never {
  const next = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  window.location.assign(`/login?next=${encodeURIComponent(next)}`);
  throw new TeamApiError('登录已失效，正在跳转登录页', 401, { code: 'unauthorized' });
}

function buildQuery(params: object): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

function generateIdempotencyKey(): string {
  const uuid = globalThis.crypto?.randomUUID?.();
  if (uuid && uuid.length >= 16) return uuid;
  return `team-${Date.now()}-${Math.random().toString(36).slice(2, 12)}-${Math.random().toString(36).slice(2, 10)}`;
}

const TERMINAL_STATUSES = new Set([400, 403, 404, 409, 410, 422, 429]);

async function teamEnvelopeRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  const response = await fetch(path, {
    credentials: 'same-origin',
    ...options,
    headers,
  });

  if (
    response.status === 401 ||
    (response.redirected && new URL(response.url, window.location.origin).pathname === '/login')
  ) {
    redirectLogin();
  }

  const rawText = await response.text();
  let parsed: unknown = null;
  if (rawText) {
    try {
      parsed = parseTeamJson(rawText);
    } catch {
      throw new TeamApiError(
        response.ok ? '服务器返回了无法识别的 Team 数据' : `请求失败（HTTP ${response.status}）`,
        response.status,
      );
    }
  }

  const record = parsed && typeof parsed === 'object' ? (parsed as TeamErrorEnvelope & Partial<TeamSuccessEnvelope<T>>) : null;

  if (!response.ok || !record || record.ok !== true || !('data' in record)) {
    const errObj = record && typeof record.error === 'object' && record.error ? record.error : null;
    const message =
      errObj?.message ||
      (typeof record?.error === 'string' ? record.error : '') ||
      record?.message ||
      `请求失败（HTTP ${response.status}）`;
    const code = errObj?.code || record?.code || '';
    throw new TeamApiError(message, response.status, {
      code,
      field: errObj?.field ?? null,
      retryable: errObj?.retryable ?? response.status >= 500,
      details: errObj?.details ?? null,
      requestId: String(record?.request_id || ''),
    });
  }

  return record.data as T;
}

/**
 * 带会话级幂等恢复的写请求：
 * - 网络异常或 5xx 重试同一意图时复用同一 `Idempotency-Key`
 * - 成功后或收到明确业务终态错误（400/403/404/409/410/422/429）时清理旧键，允许用户调整后重新发起
 */
async function teamMutate<T>(
  intentScope: string,
  method: 'POST' | 'PATCH',
  path: string,
  body?: object,
  signal?: AbortSignal,
): Promise<T> {
  const signature = JSON.stringify({ method, path, body: body ?? null });
  const storageKey = `turb_team_intent:${intentScope}:${signature}`;
  let idempotencyKey = '';
  try {
    idempotencyKey = sessionStorage.getItem(storageKey) || '';
  } catch {
    /* 存储受限时退化为单次内存键 */
  }
  if (!idempotencyKey || idempotencyKey.length < 16) {
    idempotencyKey = generateIdempotencyKey();
    try {
      sessionStorage.setItem(storageKey, idempotencyKey);
    } catch {
      /* 忽略 sessionStorage 写入限制 */
    }
  }
  const clearKey = () => {
    try {
      sessionStorage.removeItem(storageKey);
    } catch {
      /* 忽略 sessionStorage 清理限制 */
    }
  };

  try {
    const headers: Record<string, string> = {
      'Idempotency-Key': idempotencyKey,
    };
    if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
    }
    const data = await teamEnvelopeRequest<T>(path, {
      method,
      headers,
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      signal,
    });
    clearKey();
    return data;
  } catch (error) {
    if (error instanceof TeamApiError && TERMINAL_STATUSES.has(error.status)) {
      clearKey();
    }
    throw error;
  }
}

export interface FrozenTeamSelection {
  selection_id: TeamDecimalId;
  selection_revision: string;
  matched_count: number;
}

export interface TeamsApi {
  list(query: TeamListQuery, signal?: AbortSignal): Promise<TeamListResponse>;
  detail(teamId: TeamDecimalId, signal?: AbortSignal): Promise<TeamDetailResponse>;
  createBindingProbe(
    payload: { manager_account_id: TeamDecimalId; target_workspace_id?: string | null },
    signal?: AbortSignal,
  ): Promise<BindingProbeCreateResponse>;
  getBindingProbe(probeId: TeamDecimalId, signal?: AbortSignal): Promise<BindingProbeDTO>;
  createTeam(payload: TeamCreatePayload, signal?: AbortSignal): Promise<TeamCreateResponse>;
  updateTeam(teamId: TeamDecimalId, payload: TeamPatchPayload, signal?: AbortSignal): Promise<TeamPatchResponse>;
  syncTeam(teamId: TeamDecimalId, signal?: AbortSignal): Promise<TeamSyncActionResponse>;
  syncTeamsBulk(teamIds: readonly TeamDecimalId[], signal?: AbortSignal): Promise<TeamSyncBulkResponse>;
  reverifyTeam(teamId: TeamDecimalId, signal?: AbortSignal): Promise<BindingProbeCreateResponse>;
  listMembers(teamId: TeamDecimalId, query: TeamMembersQuery, signal?: AbortSignal): Promise<TeamMembersListResponse>;
  listInvitations(teamId: TeamDecimalId, query: TeamInvitationsQuery, signal?: AbortSignal): Promise<TeamInvitationsListResponse>;
  getInvitation(teamId: TeamDecimalId, invitationId: TeamDecimalId, signal?: AbortSignal): Promise<TeamInvitationDTO>;
  listCandidates(teamId: TeamDecimalId, query: TeamCandidatesQuery, signal?: AbortSignal): Promise<TeamCandidatesListResponse>;
  resolveCandidates(teamId: TeamDecimalId, values: readonly string[], signal?: AbortSignal): Promise<CandidateResolveResponse>;
  previewJoin(teamId: TeamDecimalId, payload: JoinPreviewTargetPayload, signal?: AbortSignal): Promise<JoinPreviewResponse>;
  submitJoin(teamId: TeamDecimalId, payload: JoinSubmitPayload, signal?: AbortSignal): Promise<JoinRequestDTO>;
  getJoinRequest(
    teamId: TeamDecimalId,
    joinRequestId: TeamDecimalId,
    query?: { page?: number; page_size?: number },
    signal?: AbortSignal,
  ): Promise<JoinRequestDTO>;
  continueInvitation(teamId: TeamDecimalId, invitationId: TeamDecimalId, signal?: AbortSignal): Promise<InvitationActionResponse>;
  retryInvitation(teamId: TeamDecimalId, invitationId: TeamDecimalId, signal?: AbortSignal): Promise<InvitationActionResponse>;
  continueInvitationsBulk(
    teamId: TeamDecimalId,
    invitationIds: readonly TeamDecimalId[],
    signal?: AbortSignal,
  ): Promise<InvitationBulkActionResponse>;
  retryInvitationsBulk(
    teamId: TeamDecimalId,
    invitationIds: readonly TeamDecimalId[],
    signal?: AbortSignal,
  ): Promise<InvitationBulkActionResponse>;
  freezeAccountSelection(query: AccountQuerySpec, signal?: AbortSignal): Promise<FrozenTeamSelection>;
}

export function createTeamsApi(): TeamsApi {
  return {
    list: (query, signal) =>
      teamEnvelopeRequest<TeamListResponse>(`/api/teams${buildQuery(query)}`, { signal }),

    detail: (teamId, signal) =>
      teamEnvelopeRequest<TeamDetailResponse>(`/api/teams/${teamDecimalId(teamId, 'Team ID')}`, { signal }),

    createBindingProbe: (payload, signal) =>
      teamMutate<BindingProbeCreateResponse>(
        'binding_probe',
        'POST',
        '/api/teams/binding-probes',
        {
          manager_account_id: teamDecimalId(payload.manager_account_id, '管理母号 ID'),
          ...(payload.target_workspace_id ? { target_workspace_id: payload.target_workspace_id } : {}),
        },
        signal,
      ),

    getBindingProbe: (probeId, signal) =>
      teamEnvelopeRequest<BindingProbeDTO>(
        `/api/teams/binding-probes/${teamDecimalId(probeId, '核验单 ID')}`,
        { signal },
      ),

    createTeam: (payload, signal) =>
      teamMutate<TeamCreateResponse>(
        `bind:${payload.workspace_id}`,
        'POST',
        '/api/teams',
        {
          ...payload,
          manager_account_id: teamDecimalId(payload.manager_account_id, '管理母号 ID'),
          probe_id: teamDecimalId(payload.probe_id, '核验单 ID'),
        },
        signal,
      ),

    updateTeam: (teamId, payload, signal) => {
      const id = teamDecimalId(teamId, 'Team ID');
      return teamMutate<TeamPatchResponse>(`patch:${id}:${payload.expected_revision}`, 'PATCH', `/api/teams/${id}`, payload, signal);
    },

    syncTeam: (teamId, signal) => {
      const id = teamDecimalId(teamId, 'Team ID');
      return teamMutate<TeamSyncActionResponse>(`sync:${id}`, 'POST', `/api/teams/${id}/sync`, {}, signal);
    },

    syncTeamsBulk: (teamIds, signal) => {
      const normalized = [...new Set(teamIds.map(id => teamDecimalId(id, 'Team ID')))];
      return teamMutate<TeamSyncBulkResponse>('sync_bulk', 'POST', '/api/teams/sync-bulk', { team_ids: normalized }, signal);
    },

    reverifyTeam: (teamId, signal) => {
      const id = teamDecimalId(teamId, 'Team ID');
      return teamMutate<BindingProbeCreateResponse>(`reverify:${id}`, 'POST', `/api/teams/${id}/reverify`, {}, signal);
    },

    listMembers: (teamId, query, signal) =>
      teamEnvelopeRequest<TeamMembersListResponse>(
        `/api/teams/${teamDecimalId(teamId, 'Team ID')}/members${buildQuery(query)}`,
        { signal },
      ),

    listInvitations: (teamId, query, signal) =>
      teamEnvelopeRequest<TeamInvitationsListResponse>(
        `/api/teams/${teamDecimalId(teamId, 'Team ID')}/invitations${buildQuery(query)}`,
        { signal },
      ),

    getInvitation: (teamId, invitationId, signal) =>
      teamEnvelopeRequest<TeamInvitationDTO>(
        `/api/teams/${teamDecimalId(teamId, 'Team ID')}/invitations/${teamDecimalId(invitationId, '邀请记录 ID')}`,
        { signal },
      ),

    listCandidates: (teamId, query, signal) =>
      teamEnvelopeRequest<TeamCandidatesListResponse>(
        `/api/teams/${teamDecimalId(teamId, 'Team ID')}/candidates${buildQuery(query)}`,
        { signal },
      ),

    resolveCandidates: (teamId, values, signal) =>
      teamEnvelopeRequest<CandidateResolveResponse>(
        `/api/teams/${teamDecimalId(teamId, 'Team ID')}/candidates/resolve`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ values: [...values] }),
          signal,
        },
      ),

    previewJoin: (teamId, payload, signal) =>
      teamEnvelopeRequest<JoinPreviewResponse>(
        `/api/teams/${teamDecimalId(teamId, 'Team ID')}/join-preview`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          signal,
        },
      ),

    submitJoin: (teamId, payload, signal) => {
      const id = teamDecimalId(teamId, 'Team ID');
      return teamMutate<JoinRequestDTO>(`join:${id}:${payload.expected_team_revision}`, 'POST', `/api/teams/${id}/join`, payload, signal);
    },

    getJoinRequest: (teamId, joinRequestId, query = {}, signal) =>
      teamEnvelopeRequest<JoinRequestDTO>(
        `/api/teams/${teamDecimalId(teamId, 'Team ID')}/join-requests/${teamDecimalId(joinRequestId, '入组请求 ID')}${buildQuery(query)}`,
        { signal },
      ),

    continueInvitation: (teamId, invitationId, signal) => {
      const tId = teamDecimalId(teamId, 'Team ID');
      const iId = teamDecimalId(invitationId, '邀请记录 ID');
      return teamMutate<InvitationActionResponse>(
        `inv_continue:${tId}:${iId}`,
        'POST',
        `/api/teams/${tId}/invitations/${iId}/continue`,
        {},
        signal,
      );
    },

    retryInvitation: (teamId, invitationId, signal) => {
      const tId = teamDecimalId(teamId, 'Team ID');
      const iId = teamDecimalId(invitationId, '邀请记录 ID');
      return teamMutate<InvitationActionResponse>(
        `inv_retry:${tId}:${iId}`,
        'POST',
        `/api/teams/${tId}/invitations/${iId}/retry`,
        {},
        signal,
      );
    },

    continueInvitationsBulk: (teamId, invitationIds, signal) => {
      const tId = teamDecimalId(teamId, 'Team ID');
      const ids = [...new Set(invitationIds.map(id => teamDecimalId(id, '邀请记录 ID')))];
      return teamMutate<InvitationBulkActionResponse>(
        `inv_continue_bulk:${tId}`,
        'POST',
        `/api/teams/${tId}/invitations/continue-bulk`,
        { invitation_ids: ids },
        signal,
      );
    },

    retryInvitationsBulk: (teamId, invitationIds, signal) => {
      const tId = teamDecimalId(teamId, 'Team ID');
      const ids = [...new Set(invitationIds.map(id => teamDecimalId(id, '邀请记录 ID')))];
      return teamMutate<InvitationBulkActionResponse>(
        `inv_retry_bulk:${tId}`,
        'POST',
        `/api/teams/${tId}/invitations/retry-bulk`,
        { invitation_ids: ids },
        signal,
      );
    },

    freezeAccountSelection: async (query, signal) => {
      const data = await teamMutate<Record<string, unknown>>(
        'freeze_team_join_selection',
        'POST',
        '/api/bulk/selections',
        {
          operation: { key: 'team_join', version: 1 },
          query,
        },
        signal,
      );
      const selectionObj = (data.selection && typeof data.selection === 'object' ? data.selection : data) as Record<string, unknown>;
      return {
        selection_id: teamDecimalId(selectionObj.selection_id ?? selectionObj.id, '快照选择 ID'),
        selection_revision: String(selectionObj.selection_revision ?? selectionObj.revision ?? '1'),
        matched_count: Number(selectionObj.matched_count ?? selectionObj.total ?? 0),
      };
    },
  };
}

export const teamsApi = createTeamsApi();
