import {describe, expect, it, vi} from 'vitest';
import {ConfigApiError, createConfigApi} from './config';

const response = (payload: unknown, status = 200) => new Response(JSON.stringify(payload), {
  status, headers: {'content-type': 'application/json'},
});
const field = {key: 'ZERO', type: 'int', group: '系统', label: '零值', value: 0};

describe('configuration API contracts', () => {
  it('reads an array schema once per cached generation and preserves zero', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(response([field]));
    const api = createConfigApi(fetcher);
    const [first, second] = await Promise.all([api.getSchema(), api.getSchema()]);
    expect(first).toEqual([field]); expect(second).toEqual([field]);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect((await api.getSchema())[0]?.value).toBe(0);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('keeps field validation errors and posts the existing updates envelope', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(response({
      ok: false, error: '配置无效', fields: {ZERO: '必须为正整数'},
    }, 400));
    const api = createConfigApi(fetcher);
    await expect(api.save({ZERO: 0})).rejects.toMatchObject({
      name: 'ConfigApiError', status: 400, fields: {ZERO: '必须为正整数'},
    });
    expect(JSON.parse(fetcher.mock.calls[0]![1]!.body as string)).toEqual({updates: {ZERO: 0}});
  });

  it('rejects a malformed schema envelope instead of erasing loaded fields', async () => {
    const api = createConfigApi(vi.fn<typeof fetch>().mockResolvedValue(response({fields: [field]})));
    await expect(api.getSchema()).rejects.toBeInstanceOf(ConfigApiError);
  });

  it('does not let a pre-save schema response overwrite the invalidated cache', async () => {
    let resolve!: (response: Response) => void;
    const fetcher = vi.fn<typeof fetch>()
      .mockImplementationOnce(() => new Promise(done => { resolve = done; }))
      .mockResolvedValueOnce(response({...field, updated: ['ZERO']}))
      .mockResolvedValueOnce(response([{...field, value: 8}]));
    const api = createConfigApi(fetcher);
    const old = api.getSchema();
    await api.save({ZERO: 8});
    resolve(response([{...field, value: 1}]));
    await old;
    expect((await api.getSchema())[0]?.value).toBe(8);
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it('redacts malformed server secret values before exposing metadata', async () => {
    const api = createConfigApi(vi.fn<typeof fetch>().mockResolvedValue(response([{
      ...field, key: 'KEY', type: 'str', secret: true, configured: true,
      value: 'must-not-surface', configured_value: 'secret', default: 'secret',
    }])));
    const schema = await api.getSchema();
    expect(schema[0]?.value).toBe('');
    expect(schema[0]?.configured_value).toBe('');
    expect(schema[0]?.default).toBeUndefined();
  });

  it('rejects login html without parsing it as a save response', async () => {
    const api = createConfigApi(vi.fn<typeof fetch>().mockResolvedValue(new Response('<html/>', {
      status: 401, headers: {'content-type': 'text/html'},
    })));
    await expect(api.save({ZERO: 8})).rejects.toMatchObject({status: 401});
  });

  it('does not treat a successful HTTP status with no save receipt as committed', async () => {
    const api = createConfigApi(vi.fn<typeof fetch>().mockResolvedValue(response({})));
    await expect(api.save({ZERO: 8})).rejects.toMatchObject({code: 'config_save_response_invalid'});
  });

  it('does not let consumers mutate the cached schema', async () => {
    const api = createConfigApi(vi.fn<typeof fetch>().mockResolvedValue(response([field])));
    const first = await api.getSchema(); first[0]!.value = 800;
    expect((await api.getSchema())[0]!.value).toBe(0);
  });
});
