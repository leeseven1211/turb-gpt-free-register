import {afterEach, describe, expect, it, vi} from 'vitest';
import {codexApi, emptyCodexFilters} from './codex';

function json(value: unknown, status = 200, headers = {}) {
  return new Response(JSON.stringify(value), {status, headers: {'Content-Type': 'application/json', ...headers}});
}
const attachment = {'Content-Disposition': 'attachment; filename="bundle.json"'};
afterEach(() => vi.unstubAllGlobals());

describe('Codex HTTP contract', () => {
  it('requests one exact page, preserves single-value filters and OAuth IDs, forwards cancellation and complete envelope', async () => {
    const payload = {ok: true, accounts: [{filename: 'one.json'}], total: 27, page: 2, page_size: 20, offset: 20, limit: 20,
      revision: 'rev', facets: {plan: [{value: 'future-plan', count: 27}]}, summary: {total: 50, exported: 30, pending: 20}};
    const fetch = vi.fn().mockResolvedValue(json(payload)); vi.stubGlobal('fetch', fetch);
    const controller = new AbortController();
    const filters = {...emptyCodexFilters(), q: '测试 & ?', plan: 'future-plan', status: 'unexported', oauth_status: 'expired',
      account_id: 'oauth/+id', sub2api_id: '0012', date_from: '2026-11-01', date_to: '2026-11-14', expired_date: '2026-11-15'};
    expect(await codexApi.list({page: 2, size: 20, archived: true, filters}, controller.signal)).toEqual(payload);
    expect(fetch).toHaveBeenCalledExactlyOnceWith('/api/codex?paged=1&page=2&page_size=20&archived=only&q=%E6%B5%8B%E8%AF%95+%26+%3F&plan=future-plan&status=unexported&oauth_status=expired&account_id=oauth%2F%2Bid&sub2api_id=0012&date_from=2026-11-01&date_to=2026-11-14&expired_date=2026-11-15',
      {credentials: 'same-origin', signal: controller.signal});
  });
  it('omits empty filters and explicitly selects nonarchived rows', async () => {
    const fetch = vi.fn().mockResolvedValue(json({accounts: [], total: 0})); vi.stubGlobal('fetch', fetch);
    await codexApi.list({page: 1, size: 50, archived: false, filters: emptyCodexFilters()});
    expect(fetch.mock.calls[0]![0]).toBe('/api/codex?paged=1&page=1&page_size=50&archived=0');
  });
  it.each([
    ['archive', 'archive', ['a.json', true], {filename: 'a.json', archived: true}],
    ['archiveBulk', 'archive-bulk', [['a.json', 'b.json'], false], {filenames: ['a.json', 'b.json'], archived: false}],
    ['delete', 'delete', ['a.json'], {filename: 'a.json'}],
    ['deleteBulk', 'delete-bulk', [['a.json']], {filenames: ['a.json']}],
    ['reset', 'reset-export', ['a.json'], {filename: 'a.json'}],
    ['resetBulk', 'reset-export-bulk', [['a.json']], {filenames:['a.json']}],
    ['refreshToken', 'refresh-token-bulk', [['a.json']], {filenames: ['a.json']}],
    ['reauthorize', 'retry-bulk', [['a.json']], {filenames: ['a.json']}],
    ['uploadSub2', 'upload-sub2-bulk', [['a.json']], {filenames: ['a.json']}],
  ] as const)('uses the existing %s endpoint/body', async (method, path, args, body) => {
    const fetch = vi.fn().mockResolvedValue(json({ok: true})); vi.stubGlobal('fetch', fetch);
    await (codexApi[method] as (...args: unknown[]) => Promise<unknown>)(...args);
    expect(fetch).toHaveBeenCalledExactlyOnceWith(`/api/codex/${path}`, {credentials: 'same-origin', method: 'POST', headers: ['archive-bulk','delete-bulk','reset-export-bulk'].includes(path)?{'Content-Type': 'application/json','Idempotency-Key':expect.any(String)}:{'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  });
  it('bulk mutations resolve only after durable receipts and retain failed filenames',async()=>{
    const fetch=vi.fn().mockResolvedValueOnce(json({ok:true,accepted:true,command_id:'9007199254740993'},202))
      .mockResolvedValueOnce(json({ok:true,command_id:'9007199254740993',status:'partial_success',items:[{key:'a.json',status:'updated'},{key:'b.json',status:'failed',reason:'locked'}]}));
    vi.stubGlobal('fetch',fetch);
    expect(await codexApi.deleteBulk(['a.json','b.json'])).toMatchObject({deleted:['a.json'],deleted_count:1,skipped:[{filename:'b.json',reason:'locked'}]});
    expect(fetch.mock.calls.map(call=>call[0])).toEqual(['/api/codex/delete-bulk','/api/bulk-mutations/9007199254740993']);
  });
  it('retains typed business errors and does not retry a mutation', async () => {
    const fetch = vi.fn().mockResolvedValue(json({ok: false, error: {message: '任务正在运行', code: 'busy'}}, 409)); vi.stubGlobal('fetch', fetch);
    await expect(codexApi.reauthorize(['a.json'])).rejects.toMatchObject({message: '任务正在运行', status: 409, code: 'busy'});
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});

describe('explicit sensitive downloads', () => {
  it('encodes the opaque filename, saves credential JSON and reads RFC5987 disposition', async () => {
    const body = {access_token: 'fixture-only-secret', email: 'test@example.test'};
    const fetch = vi.fn().mockResolvedValue(json(body, 200, {'Content-Disposition': "attachment; filename*=UTF-8''%E5%87%AD%E8%AF%81.json"})); vi.stubGlobal('fetch', fetch);
    const result = await codexApi.download('a /+#.json', true);
    expect(fetch).toHaveBeenCalledExactlyOnceWith('/api/codex/download-from-cpa/a%20%2F%2B%23.json', {credentials: 'same-origin'});
    expect(result.filename).toBe('凭证.json'); expect(await result.blob.text()).toBe(JSON.stringify(body));
    expect(result.acknowledged).toEqual(['a /+#.json']);
    expect(Object.keys(result).sort()).toEqual(['acknowledged', 'blob', 'failed', 'filename']);
  });
  it('local bulk JSON acknowledges only returned successful filenames', async () => {
    const fetch = vi.fn().mockResolvedValue(json({count: 1, credentials: [{filename: 'a.json', data: {access_token: 'fixture'}}], errors: [{filename: 'b.json', error: 'missing'}]}, 200, attachment)); vi.stubGlobal('fetch', fetch);
    const result = await codexApi.downloadBulk(['a.json', 'b.json']);
    expect(fetch.mock.calls[0]).toEqual(['/api/codex/download-bulk', {credentials: 'same-origin', method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{"filenames":["a.json","b.json"]}'}]);
    expect(result).toMatchObject({filename: 'bundle.json', acknowledged: ['a.json'], failed: 1});
  });
  it('downloads a CPA zip without inventing per-file receipts from its outer response', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(new Uint8Array([80, 75, 3, 4]), {headers: {'Content-Type': 'application/zip', 'Content-Disposition': 'attachment; filename="cpa.zip"'}})); vi.stubGlobal('fetch', fetch);
    const result = await codexApi.downloadBulk(['a.json', 'b.json'], true);
    expect(fetch.mock.calls[0]![0]).toBe('/api/codex/download-bulk-from-cpa');
    expect(result.filename).toBe('cpa.zip'); expect(result.blob.size).toBe(4); expect(result.acknowledged).toEqual([]);
  });
  it.each([
    ['login JSON', () => json({ok: false, error: 'login'}, 401), /登录已失效/],
    ['login HTML', () => new Response('<html>login</html>', {headers: {'Content-Type': 'text/html'}}), /非 JSON|非下载|登录/],
    ['business error with 200', () => json({ok: false, error: 'business failed'}), /business failed/],
    ['business error marked as attachment', () => json({error: {message: 'business failed', code: 'unavailable'}}, 200, attachment), /business failed/],
    ['JSON without attachment', () => json({error: 'bad request'}), /bad request|附件/],
    ['empty attachment', () => new Response('', {headers: {'Content-Type': 'application/json', ...attachment}}), /空|无效/],
    ['invalid JSON containing secrets', () => new Response('{"access_token":"never-show-this"', {headers: {'Content-Type': 'application/json', ...attachment}}), /无效/],
    ['non-object JSON attachment', () => json(null, 200, attachment), /无效/],
  ])('rejects %s without saving raw response contents', async (_name, response, expected) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response()));
    const error = await codexApi.download('a.json').catch(e => e);
    expect(error).toBeInstanceOf(Error); expect(error.message).toMatch(expected); expect(error.message).not.toContain('never-show-this');
  });
  it('preserves a 200 all-failed local bulk error-report attachment without acknowledging any credentials', async () => {
    const payload = {count: 0, credentials: [], errors: [{filename: 'a.json', error: 'not found'}]};
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(payload, 200, attachment)));
    const result = await codexApi.downloadBulk(['a.json']);
    expect(result.acknowledged).toEqual([]); expect(result.failed).toBe(1);
    expect(await result.blob.text()).toBe(JSON.stringify(payload));
  });
  it('preserves the first three CPA failure details so users can locate failed files', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ok: false, error: '没有成功从 CPA 下载任何凭证',
      errors: ['a', 'b', 'c', 'd'].map(name => ({filename: `${name}.json`, error: 'CPA 未找到'}))}, 502)));
    await expect(codexApi.downloadBulk(['a.json'], true)).rejects.toMatchObject({status: 502,
      message: '没有成功从 CPA 下载任何凭证；a.json: CPA 未找到；b.json: CPA 未找到；c.json: CPA 未找到'});
  });
});
