// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  optionalTeamDecimalId,
  parseTeamJson,
  teamDecimalId,
  type TeamDetailResponse,
} from '../features/teams/contracts';
import type { AccountQuerySpec } from '../features/accounts/queryAdapter';
import { createTeamsApi, TeamApiError } from './teams';

const BIG_ID_A = '9007199254740993'; // Number.MAX_SAFE_INTEGER + 2（Number 解析会丢精为 9007199254740992）
const BIG_ID_B = '1844674407370955161';
const BIG_ID_C = '9223372036854775807';

function jsonResponse(rawBody: string, status = 200): Response {
  return new Response(rawBody, {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function makeAccountQuery(): AccountQuerySpec {
  return {
    schema_version: 1,
    entity: 'account',
    archived: '0',
    q: 'team-candidate',
    date_from: '',
    date_to: '',
    plan: ['free'],
    filters: {
      id: '',
      email: '',
      source: [],
      registration_driver: [],
      token: ['1'],
      password: ['1'],
      promotion: [],
      totp: [],
      risk: [],
      codex: [],
      account_status: ['active'],
      email_status: ['unmarked'],
    },
    order: [{ field: 'id', direction: 'desc' }],
    limit: 50,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe('parseTeamJson 与十进制 ID 边界', () => {
  it('将 JSON 数字形式与字符串形式的 64 位超大整数 ID 均精确保持为十进制字符串', () => {
    const raw = `{
      "ok": true,
      "request_id": "req-64bit",
      "data": {
        "team_id": ${BIG_ID_A},
        "existing_team_id": "${BIG_ID_B}",
        "already_bound_team_id": ${BIG_ID_C},
        "account_id": ${BIG_ID_B},
        "manager_account_id": ${BIG_ID_A},
        "probe_id": ${BIG_ID_C},
        "invitation_id": ${BIG_ID_A},
        "member_id": ${BIG_ID_B},
        "join_request_id": ${BIG_ID_C},
        "selection_id": ${BIG_ID_A},
        "task_id": ${BIG_ID_B},
        "run_id": ${BIG_ID_C},
        "latest_task_id": ${BIG_ID_A},
        "latest_run_id": ${BIG_ID_B},
        "last_sync_task_id": ${BIG_ID_C},
        "last_sync_run_id": ${BIG_ID_A},
        "batch_id": ${BIG_ID_B},
        "team_ids": [${BIG_ID_A}, "${BIG_ID_B}"],
        "account_ids": [${BIG_ID_B}, ${BIG_ID_C}],
        "invitation_ids": [${BIG_ID_C}],
        "task_ids": [${BIG_ID_A}],
        "run_ids": [${BIG_ID_B}],
        "revision": 7,
        "purchased_seats": 12,
        "note": "含文本数字 9007199254740993 不被二次转义"
      }
    }`;

    const parsed = parseTeamJson(raw) as { data: Record<string, unknown> };
    const data = parsed.data;

    expect(data.team_id).toBe(BIG_ID_A);
    expect(data.existing_team_id).toBe(BIG_ID_B);
    expect(data.already_bound_team_id).toBe(BIG_ID_C);
    expect(data.account_id).toBe(BIG_ID_B);
    expect(data.manager_account_id).toBe(BIG_ID_A);
    expect(data.probe_id).toBe(BIG_ID_C);
    expect(data.invitation_id).toBe(BIG_ID_A);
    expect(data.member_id).toBe(BIG_ID_B);
    expect(data.join_request_id).toBe(BIG_ID_C);
    expect(data.selection_id).toBe(BIG_ID_A);
    expect(data.task_id).toBe(BIG_ID_B);
    expect(data.run_id).toBe(BIG_ID_C);
    expect(data.latest_task_id).toBe(BIG_ID_A);
    expect(data.latest_run_id).toBe(BIG_ID_B);
    expect(data.last_sync_task_id).toBe(BIG_ID_C);
    expect(data.last_sync_run_id).toBe(BIG_ID_A);
    expect(data.batch_id).toBe(BIG_ID_B);

    expect(data.team_ids).toEqual([BIG_ID_A, BIG_ID_B]);
    expect(data.account_ids).toEqual([BIG_ID_B, BIG_ID_C]);
    expect(data.invitation_ids).toEqual([BIG_ID_C]);
    expect(data.task_ids).toEqual([BIG_ID_A]);
    expect(data.run_ids).toEqual([BIG_ID_B]);

    // 非 ID 数值字段保持 number，字符串内容不被破坏
    expect(data.revision).toBe(7);
    expect(data.purchased_seats).toBe(12);
    expect(data.note).toBe('含文本数字 9007199254740993 不被二次转义');
  });

  it('非法 JSON 或尾部多余字符抛出 SyntaxError', () => {
    expect(() => parseTeamJson('{"ok":true')).toThrow(SyntaxError);
    expect(() => parseTeamJson('{"ok":true} trailing')).toThrow(SyntaxError);
  });

  it('teamDecimalId 与 optionalTeamDecimalId 校验正整数十进制字符串', () => {
    expect(teamDecimalId(`  ${BIG_ID_A}  `)).toBe(BIG_ID_A);
    expect(teamDecimalId(42)).toBe('42');
    expect(() => teamDecimalId('0')).toThrow('标识格式无效');
    expect(() => teamDecimalId('-1')).toThrow('标识格式无效');
    expect(() => teamDecimalId('abc', 'Team ID')).toThrow('Team ID格式无效');

    expect(optionalTeamDecimalId(null)).toBeNull();
    expect(optionalTeamDecimalId(undefined)).toBeNull();
    expect(optionalTeamDecimalId('')).toBeNull();
    expect(optionalTeamDecimalId(0)).toBeNull();
    expect(optionalTeamDecimalId('0')).toBeNull();
    expect(optionalTeamDecimalId(BIG_ID_B)).toBe(BIG_ID_B);
  });
});

describe('createTeamsApi 信封解包、64 位 ID 与错误处理', () => {
  it('解包 { ok: true, request_id, data } 并在接口返回未加引号的 64 位整数 ID 时保持精度', async () => {
    const rawDetail = `{
      "ok": true,
      "request_id": "req-detail-1",
      "data": {
        "team": {
          "team_id": ${BIG_ID_A},
          "revision": 3,
          "workspace_id": "ws-alpha",
          "workspace_name": "Alpha",
          "display_name": null,
          "effective_name": "Alpha",
          "plan_type": "team",
          "manager_account": {
            "account_id": ${BIG_ID_B},
            "email": "mgr@example.com",
            "archived": false,
            "account_status": "active"
          },
          "manager_role": "owner",
          "can_manage": true,
          "seat_policy": "remaining_purchased_only",
          "purchased_seats": 10,
          "planned_member_limit": 8,
          "confirmed_member_count": 2,
          "pending_invite_count": 1,
          "processing_count": 0,
          "capacity": {
            "basis": "hybrid_min",
            "effective_limit": 8,
            "occupied_count": 3,
            "remaining_before_limit": 5,
            "can_accept_new_joins": true,
            "blocking_reason_code": null
          },
          "last_sync_status": "success",
          "last_synced_at": "2026-11-27T00:00:00Z",
          "last_sync_task_id": ${BIG_ID_C},
          "last_sync_run_id": "${BIG_ID_A}",
          "last_sync_error": null,
          "created_at": "2026-11-26T00:00:00Z",
          "updated_at": "2026-11-27T00:00:00Z"
        },
        "actions": {
          "sync": { "enabled": true, "reason_code": null, "reason": null },
          "reverify": { "enabled": true, "reason_code": null, "reason": null },
          "join": { "enabled": true, "reason_code": null, "reason": null }
        },
        "permission_verified_at": "2026-11-27T00:00:00Z"
      }
    }`;

    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(rawDetail, 200));
    vi.stubGlobal('fetch', fetchMock);

    const api = createTeamsApi();
    const detail: TeamDetailResponse = await api.detail(BIG_ID_A);

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/teams/${BIG_ID_A}`,
      expect.objectContaining({ credentials: 'same-origin' }),
    );
    expect(detail.team.team_id).toBe(BIG_ID_A);
    expect(detail.team.manager_account.account_id).toBe(BIG_ID_B);
    expect(detail.team.last_sync_task_id).toBe(BIG_ID_C);
    expect(detail.team.last_sync_run_id).toBe(BIG_ID_A);
    expect(detail.team.revision).toBe(3);
  });

  it('当返回字符串 ID 与数字 ID 混用的列表/请求数据时均不丢失精度', async () => {
    const rawSubmit = `{
      "ok": true,
      "request_id": "req-join-1",
      "data": {
        "join_request_id": ${BIG_ID_B},
        "team_id": "${BIG_ID_A}",
        "status": "accepted",
        "summary": {
          "requested_count": 2,
          "queued_count": 2,
          "reused_active_count": 0,
          "skipped_count": 0
        },
        "items": [
          {
            "account_id": ${BIG_ID_A},
            "email": "a@example.com",
            "outcome": "queued",
            "invitation_id": ${BIG_ID_C},
            "task_id": ${BIG_ID_B},
            "run_id": "${BIG_ID_C}",
            "reason_code": null,
            "reason": null
          }
        ],
        "total_items": 1,
        "page": 1,
        "page_size": 20
      }
    }`;

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(rawSubmit, 200)));
    const api = createTeamsApi();
    const result = await api.submitJoin(BIG_ID_A, {
      account_ids: [BIG_ID_A],
      expected_team_revision: 5,
    });

    expect(result.join_request_id).toBe(BIG_ID_B);
    expect(result.team_id).toBe(BIG_ID_A);
    expect(result.items[0]!.account_id).toBe(BIG_ID_A);
    expect(result.items[0]!.invitation_id).toBe(BIG_ID_C);
    expect(result.items[0]!.task_id).toBe(BIG_ID_B);
    expect(result.items[0]!.run_id).toBe(BIG_ID_C);
  });

  it('对 { ok: false, request_id, error } 抛出 TeamApiError 并完整保留 code、field、retryable 与 64 位 details', async () => {
    const rawConflict = `{
      "ok": false,
      "request_id": "req-conflict-409",
      "error": {
        "code": "team_already_bound",
        "message": "该工作区已绑定到其他 Team",
        "field": "workspace_id",
        "retryable": false,
        "details": {
          "existing_team_id": ${BIG_ID_A},
          "workspace_id": "ws-bound"
        }
      }
    }`;

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(rawConflict, 409)));
    const api = createTeamsApi();

    let caught: unknown;
    try {
      await api.createTeam({
        manager_account_id: BIG_ID_B,
        workspace_id: 'ws-bound',
        probe_id: BIG_ID_C,
        probe_revision: 'rev-1',
      });
    } catch (error) {
      caught = error;
    }

    expect(caught).toBeInstanceOf(TeamApiError);
    const err = caught as TeamApiError;
    expect(err.status).toBe(409);
    expect(err.code).toBe('team_already_bound');
    expect(err.message).toBe('该工作区已绑定到其他 Team');
    expect(err.field).toBe('workspace_id');
    expect(err.retryable).toBe(false);
    expect(err.requestId).toBe('req-conflict-409');
    expect(err.details).toEqual({
      existing_team_id: BIG_ID_A,
      workspace_id: 'ws-bound',
    });
    expect(Object.isFrozen(err.details)).toBe(true);
  });

  it('在缺少显式 retryable 时，5xx 默认 retryable=true、422 默认 retryable=false', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          JSON.stringify({
            ok: false,
            request_id: 'req-503',
            error: { code: 'upstream_timeout', message: '服务暂不可用' },
          }),
          503,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          JSON.stringify({
            ok: false,
            request_id: 'req-422',
            error: { code: 'team_limit_required', message: '需设本地上限', field: 'planned_member_limit' },
          }),
          422,
        ),
      );
    vi.stubGlobal('fetch', fetchMock);
    const api = createTeamsApi();

    await expect(api.list({ page: 1, page_size: 20 })).rejects.toMatchObject({
      name: 'TeamApiError',
      status: 503,
      code: 'upstream_timeout',
      retryable: true,
      requestId: 'req-503',
    });

    await expect(
      api.updateTeam(BIG_ID_A, { expected_revision: 1, planned_member_limit: null }),
    ).rejects.toMatchObject({
      name: 'TeamApiError',
      status: 422,
      code: 'team_limit_required',
      field: 'planned_member_limit',
      retryable: false,
      requestId: 'req-422',
    });
  });

  it('返回非 JSON 响应体时抛出带状态码的 TeamApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>502</html>', { status: 502 })));
    const api = createTeamsApi();

    await expect(api.list({ page: 1, page_size: 20 })).rejects.toMatchObject({
      name: 'TeamApiError',
      status: 502,
      message: '请求失败（HTTP 502）',
    });
  });

  it('过滤空 query 参数并正确构造列表查询路径', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          JSON.stringify({
            ok: true,
            request_id: 'req-list',
            data: {
              items: [],
              total: 0,
              page: 2,
              page_size: 50,
              facets: {},
              summary: { total_teams: 0, syncing_teams: 0, attention_teams: 0 },
            },
          }),
        ),
      ),
    );
    const api = createTeamsApi();
    await api.list({
      page: 2,
      page_size: 50,
      include_facets: 1,
      q: 'alpha',
      role: '',
      last_sync_status: undefined,
    });

    const fetchMock = vi.mocked(fetch);
    expect(fetchMock.mock.calls[0]![0]).toBe(
      '/api/teams?page=2&page_size=50&include_facets=1&q=alpha',
    );
  });
});

describe('写请求 Idempotency-Key 与只读 POST 隔离', () => {
  const headerKey = (fetchMock: ReturnType<typeof vi.fn>, callIndex: number): string => {
    const init = fetchMock.mock.calls[callIndex]![1] as RequestInit;
    return new Headers(init.headers).get('Idempotency-Key') || '';
  };

  it('网络异常与 503 重试同一意图时复用同一 Idempotency-Key，成功后清理并在下次生成新键', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(
        jsonResponse(
          JSON.stringify({
            ok: false,
            request_id: 'req-503',
            error: { code: 'service_unavailable', message: '服务忙', retryable: true },
          }),
          503,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          JSON.stringify({
            ok: true,
            request_id: 'req-ok-1',
            data: { team_id: BIG_ID_A, status: 'queued', task_id: BIG_ID_B, run_id: BIG_ID_C, reused: false },
          }),
          200,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          JSON.stringify({
            ok: true,
            request_id: 'req-ok-2',
            data: { team_id: BIG_ID_A, status: 'queued', task_id: BIG_ID_B, run_id: BIG_ID_C, reused: false },
          }),
          200,
        ),
      );

    vi.stubGlobal('fetch', fetchMock);
    const api = createTeamsApi();

    // 第 1 次网络异常：保留键
    await expect(api.syncTeam(BIG_ID_A)).rejects.toThrow('Failed to fetch');
    expect(sessionStorage.length).toBe(1);

    // 第 2 次 503：复用同一个键，且不清理
    await expect(api.syncTeam(BIG_ID_A)).rejects.toMatchObject({ status: 503 });
    expect(sessionStorage.length).toBe(1);

    // 第 3 次成功：复用同一个键，并清理旧键
    const res1 = await api.syncTeam(BIG_ID_A);
    expect(res1.team_id).toBe(BIG_ID_A);
    expect(sessionStorage.length).toBe(0);

    // 第 4 次再次发起同路径同载荷写请求：生成新键
    await api.syncTeam(BIG_ID_A);
    expect(sessionStorage.length).toBe(0);

    const k0 = headerKey(fetchMock, 0);
    const k1 = headerKey(fetchMock, 1);
    const k2 = headerKey(fetchMock, 2);
    const k3 = headerKey(fetchMock, 3);

    expect(k0.length).toBeGreaterThanOrEqual(16);
    expect(k0).toBe(k1);
    expect(k1).toBe(k2);
    expect(k3).not.toBe(k0);
  });

  it.each([
    [409, 'team_revision_conflict'],
    [422, 'team_limit_required'],
  ])('收到 %i 业务终态错误后清理旧键，再次发起同一请求生成新 Idempotency-Key', async (status, code) => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          JSON.stringify({
            ok: false,
            request_id: `req-${status}`,
            error: { code, message: '终态拒绝', retryable: false },
          }),
          status,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          JSON.stringify({
            ok: true,
            request_id: 'req-retry-ok',
            data: {
              team: { team_id: BIG_ID_A, revision: 2 },
            },
          }),
          200,
        ),
      );

    vi.stubGlobal('fetch', fetchMock);
    const api = createTeamsApi();
    const payload = { expected_revision: 1, planned_member_limit: 10 };

    await expect(api.updateTeam(BIG_ID_A, payload)).rejects.toMatchObject({
      name: 'TeamApiError',
      status,
      code,
    });
    expect(sessionStorage.length).toBe(0);

    await api.updateTeam(BIG_ID_A, payload);
    const firstKey = headerKey(fetchMock, 0);
    const secondKey = headerKey(fetchMock, 1);
    expect(firstKey).not.toBe(secondKey);
  });

  it('只读 POST /join-preview 与 POST /candidates/resolve 不发送 Idempotency-Key 且不污染写意图存储', async () => {
    const previewData = {
      team_id: BIG_ID_A,
      snapshot_revision: 4,
      snapshot_at: '2026-11-27T00:00:00Z',
      team_last_synced_at: '2026-11-27T00:00:00Z',
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
      capacity: {
        seat_policy: 'remaining_purchased_only',
        basis: 'purchased_seats',
        purchased_seats: 10,
        planned_member_limit: null,
        effective_limit: 10,
        occupied_count: 2,
        additional_required: 1,
        remaining_after_submit: 7,
        exceeds_limit: false,
        can_submit: true,
        blocking_reason_code: null,
        blocking_reason: null,
      },
      sample_items: [],
    };
    const resolveData = {
      matched: [],
      not_found: ['missing@example.com'],
      ambiguous: [],
    };

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(JSON.stringify({ ok: true, request_id: 'req-prev', data: previewData })))
      .mockResolvedValueOnce(jsonResponse(JSON.stringify({ ok: true, request_id: 'req-res', data: resolveData })));

    vi.stubGlobal('fetch', fetchMock);
    sessionStorage.setItem('turb_team_intent:existing', 'keep-this-key');

    const api = createTeamsApi();
    await api.previewJoin(BIG_ID_A, { account_ids: [BIG_ID_B] });
    await api.resolveCandidates(BIG_ID_A, ['missing@example.com']);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    for (const [url, init] of fetchMock.mock.calls) {
      const headers = new Headers((init as RequestInit).headers);
      expect(headers.has('Idempotency-Key')).toBe(false);
      expect((init as RequestInit).method).toBe('POST');
      expect(String(url)).toMatch(/\/(join-preview|candidates\/resolve)$/);
    }

    expect(sessionStorage.length).toBe(1);
    expect(sessionStorage.getItem('turb_team_intent:existing')).toBe('keep-this-key');
  });
});

describe('freezeAccountSelection 批量选择快照', () => {
  it('发送 operation: { key: "team_join", version: 1 } 并正确解析 64 位 selection_id 与 selection_revision', async () => {
    const rawSelection = `{
      "ok": true,
      "request_id": "req-sel-1",
      "data": {
        "selection_id": ${BIG_ID_A},
        "selection_revision": "rev-42",
        "matched_count": 128
      }
    }`;

    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(rawSelection, 200));
    vi.stubGlobal('fetch', fetchMock);

    const api = createTeamsApi();
    const query = makeAccountQuery();
    const frozen = await api.freezeAccountSelection(query);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe('/api/bulk/selections');
    expect((init as RequestInit).method).toBe('POST');
    const headers = new Headers((init as RequestInit).headers);
    expect(headers.get('Idempotency-Key')).toBeTruthy();
    expect(headers.get('Content-Type')).toBe('application/json');
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      operation: { key: 'team_join', version: 1 },
      query,
    });

    expect(frozen).toEqual({
      selection_id: BIG_ID_A,
      selection_revision: 'rev-42',
      matched_count: 128,
    });
  });

  it('兼容嵌套 selection 对象（id / revision / total）并返回精确十进制 selection_id', async () => {
    const rawNested = `{
      "ok": true,
      "request_id": "req-sel-2",
      "data": {
        "selection": {
          "id": ${BIG_ID_B},
          "revision": 9,
          "total": 35
        }
      }
    }`;

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(rawNested, 200)));
    const api = createTeamsApi();
    const frozen = await api.freezeAccountSelection(makeAccountQuery());

    expect(frozen).toEqual({
      selection_id: BIG_ID_B,
      selection_revision: '9',
      matched_count: 35,
    });
  });
});
