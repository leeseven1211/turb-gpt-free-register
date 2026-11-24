import {afterEach, expect, it, vi} from 'vitest';
import {tasksApi} from './tasks';
import {BulkMutationPendingError} from './bulkMutations';

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {status, headers: {'Content-Type': 'application/json'}});
it('批量终止只提交一次，按完整命令ID读全部回执，保留失败目标', async () => {
  const send = vi.fn<typeof fetch>()
    .mockResolvedValueOnce(json({ok: true, accepted: true, command_id: '9007199254740993'}))
    .mockResolvedValueOnce(json({ok: true, command_id: '9007199254740993', status: 'partial_success',
      items: [{key: '9007199254740995', status: 'updated', data: {state: 'stopped', message: '已收口'}}], next_offset: 500}))
    .mockResolvedValueOnce(json({ok: true, status: 'partial_success', items: [
      {key: '9007199254740997', status: 'skipped', reason_code: 'run_state_changed', reason: '原执行已变化'},
    ], next_offset: null}));
  vi.stubGlobal('fetch', send);
  const result = await tasksApi.bulk('terminate', ['9007199254740995', '9007199254740997']);
  expect(send.mock.calls.map(call => call[0])).toEqual(['/api/operations/bulk',
    '/api/bulk-mutations/9007199254740993', '/api/bulk-mutations/9007199254740993?offset=500&limit=500']);
  expect(send.mock.calls[0]?.[1]?.body).toBe('{"action":"terminate","task_ids":[9007199254740995,9007199254740997]}');
  expect(send.mock.calls[0]?.[1]?.headers).toMatchObject({'Idempotency-Key': expect.any(String)});
  expect(result.accepted).toEqual([{task_id: '9007199254740995', state: 'stopped', message: '已收口'}]);
  expect(result.skipped).toEqual([{task_id: '9007199254740997', error: '原执行已变化'}]);
  expect([result.accepted_count, result.skipped_count]).toEqual([1, 1]);
});

it('已受理后查询失败保留命令与原错误，不重发终止POST', async () => {
  const send = vi.fn<typeof fetch>()
    .mockResolvedValueOnce(json({ok: true, accepted: true, command_id: '55'}))
    .mockResolvedValueOnce(json({ok: false, error: '查询暂不可用'}, 503));
  vi.stubGlobal('fetch', send);
  await expect(tasksApi.bulk('terminate', [7])).rejects.toBeInstanceOf(BulkMutationPendingError);
  expect(send.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(1);
});
