import {afterEach, describe, expect, it, vi} from 'vitest';
import {createAccountDetailApi} from './accountDetail';

function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), {status, headers: {'Content-Type': 'application/json'}});
}
afterEach(() => vi.unstubAllGlobals());

describe('账号详情 Roxy 读取边界', () => {
  it('只读取指定 ID 的既有路径并转发取消信号', async () => {
    const fetch = vi.fn().mockResolvedValue(json({ok: true, profile_id: 'p7', window_name: 'window7'}));
    vi.stubGlobal('fetch', fetch);
    const controller = new AbortController();
    expect(await createAccountDetailApi().roxyProfile('7', controller.signal)).toEqual({
      ok: true, profile_id: 'p7', window_name: 'window7',
    });
    expect(fetch).toHaveBeenCalledExactlyOnceWith('/api/accounts/7/roxy-profile', {
      credentials: 'same-origin', signal: controller.signal,
    });
  });

  it('保留空名称和 null，不捏造本次 profile', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ok: true, profile_id: null, window_name: ''})));
    expect(await createAccountDetailApi().roxyProfile('7')).toEqual({ok: true, profile_id: null, window_name: ''});
  });

  it.each(['', '0', '-1', '7/secret', '1.2', '7e1', ' 7'])('无效 ID %j 不发请求', async id => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    await expect(createAccountDetailApi().roxyProfile(id)).rejects.toThrow('账号 ID 无效');
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([null, [], {}, {ok: true}, {ok: true, profile_id: 7, window_name: 'window'},
    {ok: true, profile_id: 'p7', window_name: {}}, {profile_id: 'p7', window_name: 'window'}])(
    '拒绝不完整或类型错误的 envelope %#', async payload => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(payload)));
      await expect(createAccountDetailApi().roxyProfile('7')).rejects.toMatchObject({
        name: 'ApiError', status: 200, code: 'account_response_invalid',
      });
    });

  it('保留 404 业务错误并且不重试', async () => {
    const fetch = vi.fn().mockResolvedValue(json({ok: false, error: '账号不存在'}, 404));
    vi.stubGlobal('fetch', fetch);
    await expect(createAccountDetailApi().roxyProfile('7')).rejects.toMatchObject({status: 404, message: '账号不存在'});
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('沿统一 client 拒绝登录 HTML，取消原样传播', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(new Response('<html>login</html>', {status: 401}));
    vi.stubGlobal('fetch', fetch);
    await expect(createAccountDetailApi().roxyProfile('7')).rejects.toMatchObject({status: 401, message: '登录已失效，请重新登录后刷新。'});
    const aborted = new DOMException('cancelled', 'AbortError');
    fetch.mockRejectedValueOnce(aborted);
    await expect(createAccountDetailApi().roxyProfile('7')).rejects.toBe(aborted);
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
