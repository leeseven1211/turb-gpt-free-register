import { afterEach, describe, expect, it, vi } from 'vitest';
import { createProxyApi } from './proxy';
const page = {
  ok: true,
  items: [{ id: 1, lease_id: 'lease-1' }],
  count: 1,
  total: 25,
  limit: 20,
  offset: 20,
  has_more: true,
};
afterEach(() => vi.unstubAllGlobals());
describe('proxy GET contracts', () => {
  it('sends exact pagination/filter query, same-origin credentials and cancellation', async () => {
    const fetcher = vi.fn().mockResolvedValue(Response.json({ ...page, view: 'history' }));
    vi.stubGlobal('fetch', fetcher);
    const signal = new AbortController().signal;
    const result = await createProxyApi().page(
      'history',
      { page: 2, size: 20, window: '7d', purpose: 'plan-check', state: 'released', search: '  A & 42  ' },
      signal,
    );
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(
      '/api/proxy-traffic/history?limit=20&offset=20&window=7d&purpose=plan-check&state=released&search=A+%26+42',
      { credentials: 'same-origin', signal },
    );
    expect(result).toMatchObject({
      items: [{ id: 1, lease_id: 'lease-1' }],
      count: 1,
      total: 25,
      limit: 20,
      offset: 20,
      has_more: true,
    });
  });
  it('keeps traffic purpose unconstrained and retains exact task identifiers', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response(
          '{"ok":true,"items":[{"id":9007199254740993,"operation_task_id":9007199254740995,"operation_run_id":9007199254740997}],"count":1,"total":1,"limit":20,"offset":0}',
          { headers: { 'content-type': 'application/json' } },
        ),
      );
    vi.stubGlobal('fetch', fetcher);
    const result = await createProxyApi().page('traffic', {
      page: 1,
      size: 20,
      window: 'all',
      purpose: 'plan-check',
      state: 'all',
      search: '',
    });
    expect(fetcher.mock.calls[0]![0]).toBe(
      '/api/proxy-traffic/traffic?limit=20&offset=0&window=all&purpose=all&state=all&search=',
    );
    expect(result.items[0]).toMatchObject({
      id: '9007199254740993',
      operation_task_id: '9007199254740995',
      operation_run_id: '9007199254740997',
    });
  });
  it('preserves ID spelling without interpreting quoted labels or changing metric types', async () => {
    const label = '"id":9007199254740995 and a quoted backslash \\';
    const item = String.raw`{"\u0069d":9007199254740993,"total_bytes":9007199254740993,"lease_id":${JSON.stringify(label)}}`;
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(`{"ok":true,"items":[${item}],"count":1,"total":1,"limit":20,"offset":0}`, {
            headers: { 'content-type': 'application/json' },
          }),
        ),
    );
    const result = await createProxyApi().page('history', {
      page: 1,
      size: 20,
      window: 'all',
      purpose: 'all',
      state: 'all',
      search: '',
    });
    expect(result.items[0]).toEqual({
      id: '9007199254740993',
      total_bytes: Number('9007199254740993'),
      lease_id: label,
    });
  });
  it.each([{ count: 2 }, { total: -1 }, { limit: 0 }, { offset: -1 }, { view: 'current' }, { items: null }])(
    'rejects malformed history pagination %j',
    async (patch) => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ ...page, ...patch })));
      await expect(
        createProxyApi().page('history', {
          page: 2,
          size: 20,
          window: 'all',
          purpose: 'all',
          state: 'all',
          search: '',
        }),
      ).rejects.toThrow();
    },
  );
  it('tolerates malformed optional inventory lists without rendering arbitrary payload fields', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          Response.json({
            ok: true,
            policy: { max_size: 20 },
            counts: { ready: 2 },
            items: 'invalid',
            country_pools: null,
          }),
        ),
    );
    expect(await createProxyApi().pool()).toMatchObject({ items: [], country_pools: [] });
  });
  it('requires global byte metrics but isolates unsupported inventory', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(
          Response.json({
            ok: true,
            total_bytes: 100,
            today_bytes: 5,
            today_request_count: 0,
            today_browser_count: 7,
          }),
        )
        .mockResolvedValueOnce(Response.json({ ok: false, error: 'not supported' }, { status: 404 })),
    );
    const api = createProxyApi();
    expect(await api.summary()).toMatchObject({ today_request_count: 0 });
    expect(await api.pool()).toBeNull();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ ok: true, today_bytes: 1 })));
    await expect(api.summary()).rejects.toThrow('统计');
  });
});
