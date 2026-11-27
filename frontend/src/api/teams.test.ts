// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { optionalTeamDecimalId, parseTeamJson, teamDecimalId } from '../features/teams/contracts';
import type { AccountQuerySpec } from '../features/accounts/queryAdapter';
import type { components } from './teams-schema';
import { createTeamsApi, TeamApiError } from './teams';

const BIG_ID_A = '9007199254740993';
const BIG_ID_B = '1844674407370955161';
const BIG_ID_C = '9223372036854775807';
const TEAM: components['schemas']['TeamDTO'] = {
  id: BIG_ID_A, workspace_id: 'ws-alpha', name: null, display_name: '测试 Team',
  manager_account: { id: BIG_ID_B, email: null, archived: true }, role: 'owner', purchased_seats: null,
  planned_member_limit: 8, confirmed_member_count: null, pending_invite_count: null, processing_count: null,
  last_synced_at: null, last_sync_status: 'never', revision: 3,
};
const ACTION: components['schemas']['ActionReceipt'] = {
  accepted: true, reused: false, team_id: BIG_ID_A, task_id: BIG_ID_B, run_id: BIG_ID_C, status: 'queued',
};
const CAPACITY: components['schemas']['Capacity'] = {
  basis: 'planned_member_limit', purchased_seats: null, planned_member_limit: 8, effective_limit: 8,
  occupied_count: null, available_count: null, additional_required: 1, can_submit: true, blocking_reason_code: null,
};
const JOIN: components['schemas']['JoinRequestDTO'] = {
  id: BIG_ID_B, team_id: BIG_ID_A, operation: 'join', accepted: true, reused: false, status: 'preparing',
  waiting_reason_code: null, selection_id: null, selection_revision: null, batch_id: BIG_ID_A,
  task_id: BIG_ID_C, run_id: BIG_ID_B, created_at: '2026-11-27T00:00:00Z',
  counts: { requested_count: 1, unique_count: 1, duplicate_count: 0, pending_count: 1,
    accepted_count: 0, reused_count: 0, skipped_count: 0, failed_count: 0 }, capacity: CAPACITY,
  items_url: `/api/teams/${BIG_ID_A}/join-requests/${BIG_ID_B}`,
};
const INVITATION: components['schemas']['InvitationDTO'] = {
  id: BIG_ID_C, team_id: BIG_ID_A, remote_invitation_id: null,
  account: { id: BIG_ID_B, email: 'target@example.test', archived: false }, email_snapshot: 'target@example.test',
  invitation_state: 'pending', membership_state: 'unconfirmed',
  latest_execution: { task_id: BIG_ID_B, run_id: BIG_ID_C, status: 'waiting', stage: 'member_auth',
    waiting_reason_code: 'waiting_account', error_info: null }, updated_at: '2026-11-27T00:00:00Z', last_verified_at: null,
  actions: { continue: { enabled: true, reason_code: null }, retry: { enabled: false, reason_code: 'already_processing' },
    view_task: { enabled: true, reason_code: null } },
};
function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify({ ok: true, request_id: 'req-test', data }), { status, headers: { 'Content-Type': 'application/json' } });
}
function errorResponse(status: number, code: string): Response {
  return new Response(JSON.stringify({ ok: false, request_id: 'req-error', error: { code, message: '测试业务原因' } }), { status });
}
function headerKey(mock: ReturnType<typeof vi.fn>, index: number): string {
  return new Headers((mock.mock.calls[index]![1] as RequestInit).headers).get('Idempotency-Key') || '';
}
function makeAccountQuery(): AccountQuerySpec {
  return { schema_version: 1, entity: 'account', archived: '0', q: 'team-candidate', team_scope: 'all', date_from: '', date_to: '', plan: ['free'],
    filters: { id: '', email: '', source: [], registration_driver: [], token: ['1'], password: ['1'], promotion: [], totp: [],
      risk: [], codex: [], account_status: ['active'], email_status: ['unmarked'] }, order: [{ field: 'id', direction: 'desc' }], limit: 50 };
}
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); sessionStorage.clear(); });

describe('真实 Team 窄 DTO 与精确 ID', () => {
  it('64 位 ID 保持字符串，版本和数量保持数字', () => {
    expect(parseTeamJson(`{"id":${BIG_ID_A},"manager_account":{"id":${BIG_ID_B}},"team_id":${BIG_ID_C},"existing_join_request_id":${BIG_ID_B},"account_ids":[${BIG_ID_A}],"revision":3,"selection_revision":2,"count":7}`))
      .toEqual({ id: BIG_ID_A, manager_account: { id: BIG_ID_B }, team_id: BIG_ID_C, existing_join_request_id: BIG_ID_B,
        account_ids: [BIG_ID_A], revision: 3, selection_revision: 2, count: 7 });
    expect(() => parseTeamJson('{"ok":true')).toThrow(SyntaxError);
    expect(() => parseTeamJson('{"ok":true} trailing')).toThrow(SyntaxError);
    expect(teamDecimalId(` ${BIG_ID_A} `)).toBe(BIG_ID_A);
    expect(teamDecimalId(42)).toBe('42');
    expect(teamDecimalId(BIG_ID_C)).toBe(BIG_ID_C);
    for (const value of ['0', '-1', 'abc', '9223372036854775808', '100000000000000000000']) {
      expect(() => teamDecimalId(value)).toThrow('标识格式无效');
    }
    expect(optionalTeamDecimalId(null)).toBeNull();
    expect(optionalTeamDecimalId('0')).toBeNull();
  });
  it('详情保留真实 id、manager_account.id 与未知 null，不编造容量', async () => {
    const detail: components['schemas']['TeamDetail'] = { team: TEAM, actions: { sync: { enabled: true, reason_code: null },
      reverify: { enabled: true, reason_code: null }, join: { enabled: true, reason_code: null } }, permission_verified_at: null };
    const raw = JSON.stringify({ ok: true, data: detail }).replace(`"id":"${BIG_ID_A}"`, `"id":${BIG_ID_A}`).replace(`"id":"${BIG_ID_B}"`, `"id":${BIG_ID_B}`);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(raw)));
    const result = await createTeamsApi().detail(BIG_ID_A);
    expect(result).toEqual(detail);
    expect(result.team).not.toHaveProperty('capacity');
  });
  it('邀请详情解开 invitation 包络并保留执行与动作嵌套字段', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ invitation: INVITATION })));
    expect(await createTeamsApi().getInvitation(BIG_ID_A, BIG_ID_C)).toEqual(INVITATION);
  });
  it('绑定提交使用整数 probe_revision，重新核验使用 ActionReceipt', async () => {
    const mock = vi.fn().mockResolvedValueOnce(jsonResponse(ACTION, 202)).mockResolvedValueOnce(jsonResponse({ team: TEAM, sync: ACTION }, 201));
    vi.stubGlobal('fetch', mock);
    const api = createTeamsApi();
    expect(await api.reverifyTeam(BIG_ID_A)).toEqual(ACTION);
    await api.createTeam({ manager_account_id: BIG_ID_B, workspace_id: 'ws-alpha', probe_id: BIG_ID_A, probe_revision: 2 });
    expect(JSON.parse((mock.mock.calls[1]![1] as RequestInit).body as string)).toEqual({ manager_account_id: BIG_ID_B, workspace_id: 'ws-alpha', probe_id: BIG_ID_A, probe_revision: 2 });
  });
  it('候选布尔筛选发送 true/false 字符串', async () => {
    const data: components['schemas']['CandidateList'] = { items: [], total: 0, page: 2, page_size: 50, revision: 'candidates:7' };
    const mock = vi.fn().mockResolvedValue(jsonResponse(data));
    vi.stubGlobal('fetch', mock);
    expect(await createTeamsApi().listCandidates(BIG_ID_A, { page: 2, page_size: 50, include_facets: '1',
      has_access_token: 'true', has_password: 'false', totp_enabled: 'true', q: '' })).toEqual(data);
    expect(mock.mock.calls[0]![0]).toBe(`/api/teams/${BIG_ID_A}/candidates?page=2&page_size=50&include_facets=1&has_access_token=true&has_password=false&totp_enabled=true`);
  });
  it('Join POST 发送真实目标描述，GET 返回 request/items 分页', async () => {
    const page: components['schemas']['JoinRequestItems'] = { request: JOIN,
      items: [{ ordinal: 1, account_id: BIG_ID_C, invitation_id: null, acceptance_status: 'pending', task_id: null,
        run_id: null, execution_status: 'none', reason_code: null, message: null }], total: 1, page: 1, page_size: 20, revision: 'join:1' };
    const mock = vi.fn().mockResolvedValueOnce(jsonResponse(JOIN, 202)).mockResolvedValueOnce(jsonResponse(page));
    vi.stubGlobal('fetch', mock);
    const api = createTeamsApi();
    const payload = { selection_id: BIG_ID_C, selection_revision: 4 };
    expect(await api.submitJoin(BIG_ID_A, payload)).toEqual(JOIN);
    expect(JSON.parse((mock.mock.calls[0]![1] as RequestInit).body as string)).toEqual(payload);
    expect(await api.getJoinRequest(BIG_ID_A, BIG_ID_B, { page: 1, page_size: 20 })).toEqual(page);
  });
});

describe('Team 错误与幂等', () => {
  it('完整保留错误字段与精确 details ID', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(`{"ok":false,"request_id":"req-conflict","error":{"code":"team_already_bound","message":"该工作区已绑定","field":"workspace_id","retryable":false,"details":{"existing_team_id":${BIG_ID_A}}}}`, { status: 409 })));
    await expect(createTeamsApi().createTeam({ manager_account_id: BIG_ID_B, workspace_id: 'ws-alpha', probe_id: BIG_ID_C, probe_revision: 2 }))
      .rejects.toMatchObject({ name: 'TeamApiError', status: 409, code: 'team_already_bound', field: 'workspace_id',
        retryable: false, requestId: 'req-conflict', details: { existing_team_id: BIG_ID_A } });
  });
  it('缺少 retryable 时按 HTTP 状态推导，非 JSON 错误保留状态码', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(errorResponse(503, 'service_unavailable')).mockResolvedValueOnce(errorResponse(422, 'parameter_invalid'))
      .mockResolvedValueOnce(new Response('<html>502</html>', { status: 502 })));
    const api = createTeamsApi();
    await expect(api.list({})).rejects.toMatchObject({ status: 503, retryable: true });
    await expect(api.list({})).rejects.toMatchObject({ status: 422, retryable: false });
    await expect(api.list({})).rejects.toMatchObject({ status: 502, message: '请求失败（HTTP 502）' });
  });
  it('网络异常/503复用原键，成功后下一次人工操作使用新键', async () => {
    const mock = vi.fn().mockRejectedValueOnce(new TypeError('Failed to fetch')).mockResolvedValueOnce(errorResponse(503, 'service_unavailable'))
      .mockResolvedValueOnce(jsonResponse(ACTION, 202)).mockResolvedValueOnce(jsonResponse(ACTION, 202));
    vi.stubGlobal('fetch', mock);
    const api = createTeamsApi();
    await expect(api.syncTeam(BIG_ID_A)).rejects.toThrow('Failed to fetch');
    await expect(api.syncTeam(BIG_ID_A)).rejects.toMatchObject({ status: 503 });
    expect(sessionStorage.length).toBe(1);
    await api.syncTeam(BIG_ID_A);
    expect(sessionStorage.length).toBe(0);
    await api.syncTeam(BIG_ID_A);
    expect(headerKey(mock, 0).length).toBeGreaterThanOrEqual(16);
    expect(headerKey(mock, 0)).toBe(headerKey(mock, 1));
    expect(headerKey(mock, 1)).toBe(headerKey(mock, 2));
    expect(headerKey(mock, 3)).not.toBe(headerKey(mock, 0));
  });
  it('显式提供契约允许的 JSON 幂等键时，请求头使用同一个键', async () => {
    const mock = vi.fn().mockResolvedValue(jsonResponse({ team: TEAM }));
    vi.stubGlobal('fetch', mock);
    await createTeamsApi().updateTeam(BIG_ID_A, {
      expected_revision: 3,
      display_name: '新备注',
      idempotency_key: '  explicit-team-key-123456  ',
    });
    expect(headerKey(mock, 0)).toBe('explicit-team-key-123456');
  });
  it.each([409, 422])('HTTP %i 终态错误后清理键，允许用户重新发起', async status => {
    const mock = vi.fn().mockResolvedValueOnce(errorResponse(status, 'parameter_invalid')).mockResolvedValueOnce(jsonResponse({ team: TEAM }));
    vi.stubGlobal('fetch', mock);
    const api = createTeamsApi();
    const payload = { expected_revision: 3, planned_member_limit: 10 };
    await expect(api.updateTeam(BIG_ID_A, payload)).rejects.toBeInstanceOf(TeamApiError);
    expect(sessionStorage.length).toBe(0);
    await api.updateTeam(BIG_ID_A, payload);
    expect(headerKey(mock, 1)).not.toBe(headerKey(mock, 0));
  });
  it('只读预览与解析不发送幂等键、不污染写意图', async () => {
    const preview: components['schemas']['JoinPreviewDTO'] = { team_id: BIG_ID_A, selection_id: null, selection_revision: null,
      snapshot_revision: null, snapshot_at: null, team_last_synced_at: null, requires_sync: true,
      counts: { requested_count: 1, unique_count: 1, duplicate_count: 0, unavailable_count: 0, another_team_count: 0,
        already_member_count: 0, same_team_active_count: 0, missing_auth_count: 0, resume_invite_count: 0, new_count: 1, eligible_count: 1 }, capacity: CAPACITY };
    const resolve: components['schemas']['CandidateResolveResult'] = { requested_count: 1, unique_count: 1, duplicate_count: 0,
      items: [{ input: 'missing@example.test', match_status: 'not_found', candidates: [], reason_code: 'account_not_found' }] };
    const mock = vi.fn().mockResolvedValueOnce(jsonResponse(preview)).mockResolvedValueOnce(jsonResponse(resolve));
    vi.stubGlobal('fetch', mock);
    sessionStorage.setItem('existing', 'keep');
    const api = createTeamsApi();
    expect(await api.previewJoin(BIG_ID_A, { account_ids: [BIG_ID_B] })).toEqual(preview);
    expect(await api.resolveCandidates(BIG_ID_A, ['missing@example.test'])).toEqual(resolve);
    expect(headerKey(mock, 0)).toBe('');
    expect(headerKey(mock, 1)).toBe('');
    expect(sessionStorage.length).toBe(1);
  });
});

describe('查询名单冻结', () => {
  it('发送 source/parameters 并轮询 preparing，ready 后返回整数 revision 和 target_count', async () => {
    vi.useFakeTimers();
    const mock = vi.fn().mockResolvedValueOnce(jsonResponse({ id: BIG_ID_B, state: 'preparing', selection_revision: null, target_count: null }, 202))
      .mockResolvedValueOnce(jsonResponse({ id: BIG_ID_B, state: 'preparing', selection_revision: 1, target_count: 128 }))
      .mockResolvedValueOnce(jsonResponse({ id: BIG_ID_B, state: 'ready', selection_revision: 1, target_count: 128, matched_count: null }));
    vi.stubGlobal('fetch', mock);
    const query = makeAccountQuery();
    const promise = createTeamsApi().freezeAccountSelection(BIG_ID_A, query);
    await vi.runAllTimersAsync();
    expect(await promise).toEqual({ selection_id: BIG_ID_B, selection_revision: 1, matched_count: 128 });
    expect(JSON.parse((mock.mock.calls[0]![1] as RequestInit).body as string)).toEqual({ operation: { key: 'team_join', version: 1 },
      source: { kind: 'query', query }, parameters: { team_id: BIG_ID_A } });
    expect(mock.mock.calls.slice(1).map(call => call[0])).toEqual([`/api/bulk/selections/${BIG_ID_B}`, `/api/bulk/selections/${BIG_ID_B}`]);
    expect(headerKey(mock, 0).length).toBeGreaterThanOrEqual(16);
    expect(headerKey(mock, 1)).toBe('');
  });
  it('ready 缺少 revision 时明确失败，不编造默认值', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ id: BIG_ID_B, state: 'ready', selection_revision: null, target_count: 3 }, 202)));
    await expect(createTeamsApi().freezeAccountSelection(BIG_ID_A, makeAccountQuery())).rejects.toMatchObject({ name: 'TeamApiError', code: 'selection_response_invalid' });
  });
  it('准备失败返回后端分类原因', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ id: BIG_ID_B, state: 'failed', error_code: 'selection_capacity_exceeded' }, 202)));
    await expect(createTeamsApi().freezeAccountSelection(BIG_ID_A, makeAccountQuery())).rejects.toMatchObject({ name: 'TeamApiError', code: 'selection_capacity_exceeded' });
  });
  it('取消轮询后停止继续 GET', async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    const mock = vi.fn().mockResolvedValue(jsonResponse({ id: BIG_ID_B, state: 'preparing', selection_revision: null, target_count: null }, 202));
    vi.stubGlobal('fetch', mock);
    const promise = createTeamsApi().freezeAccountSelection(BIG_ID_A, makeAccountQuery(), controller.signal);
    const rejection = expect(promise).rejects.toMatchObject({ name: 'AbortError' });
    await vi.advanceTimersByTimeAsync(0);
    controller.abort();
    await rejection;
    const count = mock.mock.calls.length;
    await vi.runAllTimersAsync();
    expect(mock).toHaveBeenCalledTimes(count);
  });
});
