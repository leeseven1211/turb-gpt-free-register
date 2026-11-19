// @vitest-environment jsdom
import {afterEach, describe, expect, it, vi} from 'vitest';
import {request} from './client';
import {operationIntent} from './tasks';
afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear(); });
describe('统一请求和重跑意图', () => {
  it('解析两类错误响应并保留状态码', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ok: false, error: {message: '任务已变化', code: 'changed'}}), {status: 409, headers: {'Content-Type': 'application/json'}})));
    await expect(request('/api/operations')).rejects.toMatchObject({message: '任务已变化', status: 409, code: 'changed'});
  });
  it('网络重试复用幂等键，新的选择可以提交，成功后的再重跑使用新键', async () => {
    const fetch = vi.fn().mockRejectedValueOnce(new TypeError('网络中断')).mockImplementation(async () => new Response('{"ok":true}', {headers: {'Content-Type': 'application/json'}}));
    vi.stubGlobal('fetch', fetch);
    await expect(operationIntent('bulk:retry', '/api/operations/bulk', {task_ids: [1]})).rejects.toThrow('网络中断');
    await operationIntent('bulk:retry', '/api/operations/bulk', {task_ids: [2]});
    await operationIntent('bulk:retry', '/api/operations/bulk', {task_ids: [1]});
    await operationIntent('bulk:retry', '/api/operations/bulk', {task_ids: [1]});
    const key = (index: number) => fetch.mock.calls[index]![1].headers['Idempotency-Key'];
    expect(key(0)).toBe(key(2)); expect(key(0)).not.toBe(key(1)); expect(key(0)).not.toBe(key(3));
  });
});

it('迁移后首次重试接续旧页面未决意图', async () => {
  const url = '/api/operations/91/retry';
  sessionStorage.setItem('turb_operation_intent:retry:91', JSON.stringify({key: 'existing-intent', signature: JSON.stringify({url, body: null})}));
  const fetch = vi.fn().mockResolvedValue(new Response('{"ok":true}', {headers: {'Content-Type': 'application/json'}}));
  vi.stubGlobal('fetch', fetch);
  await operationIntent('retry:91', url);
  expect(fetch.mock.calls[0]![1].headers['Idempotency-Key']).toBe('existing-intent');
  expect(sessionStorage.getItem('turb_operation_intent:retry:91')).toBeNull();
});

it('明确拒绝后结束旧意图，再次提交相同目标生成新幂等键', async () => {
  const fetch = vi.fn().mockImplementationOnce(async () => new Response('{"ok":false,"message":"明确未受理"}', {status: 422, headers: {'Content-Type': 'application/json'}}))
    .mockImplementation(async () => new Response('{"ok":true}', {headers: {'Content-Type': 'application/json'}}));
  vi.stubGlobal('fetch', fetch);
  const body = {action: 'retry', task_ids: [1, 2]};
  await expect(operationIntent('bulk:retry', '/api/operations/bulk', body)).rejects.toMatchObject({status: 422});
  await operationIntent('bulk:retry', '/api/operations/bulk', body);
  expect(fetch.mock.calls[0]![1].headers['Idempotency-Key']).not.toBe(fetch.mock.calls[1]![1].headers['Idempotency-Key']);
});

describe('账号查询顶层错误code兼容', () => {
  it('400搜索语法错误保留顶层code，使账号页可以区分无效查询和网络错误', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ok: false, code: 'account_search_invalid', error: '双引号未闭合，请在完整文字末尾补上 "。',
    }), {status: 400, headers: {'Content-Type': 'application/json'}})));
    await expect(request('/api/accounts?paged=1&q=bad')).rejects.toMatchObject({
      status: 400, code: 'account_search_invalid', message: '双引号未闭合，请在完整文字末尾补上 "。',
    });
  });

  it.each([
    [{ok: false, error: {code: 'nested_code', message: '嵌套消息'}, error_code: 'legacy_code', code: 'top_code'}, 'nested_code', '嵌套消息'],
    [{ok: false, error: '旧消息', error_code: 'legacy_code', code: 'top_code'}, 'legacy_code', '旧消息'],
    [{ok: false, error: '新消息', code: 'top_code'}, 'top_code', '新消息'],
    [{ok: false, error: '无代码'}, '', '无代码'],
  ])('追加顶层兜底不改变两种已有错误code优先级', async (payload, code, message) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(payload),
      {status: 409, headers: {'Content-Type': 'application/json'}})));
    await expect(request('/api/operations')).rejects.toMatchObject({status: 409, code, message});
  });
});
