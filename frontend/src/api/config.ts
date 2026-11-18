import type {ConfigApi, ConfigField, ConfigFieldErrors, ConfigSaveResponse, ConfigUpdates} from '../features/config/contracts';

export class ConfigApiError extends Error {
  constructor(message: string, public status: number, public code = '', public fields: ConfigFieldErrors = {}) {
    super(message);
    this.name = 'ConfigApiError';
  }
}

const object = (value: unknown): Record<string, unknown> =>
  value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value));

export function sanitizeConfigFields(value: unknown): ConfigField[] {
  if (!Array.isArray(value)) throw new ConfigApiError('配置字段响应格式无效', 0, 'config_schema_invalid');
  const keys = new Set<string>();
  return value.map(item => {
    const field = object(item);
    if (typeof field.key !== 'string' || !field.key || typeof field.type !== 'string' || keys.has(field.key)) {
      throw new ConfigApiError('配置字段响应格式无效', 0, 'config_schema_invalid');
    }
    keys.add(field.key);
    const result = clone({...field, group: String(field.group || '其他'), label: String(field.label || field.key)}) as unknown as ConfigField;
    if (result.secret) {
      result.value = '';
      if ('configured_value' in result) result.configured_value = '';
      if ('published_effective_value' in result) result.published_effective_value = '';
      delete result.default;
    }
    return result;
  });
}

/** Owns the schema cache only. Editable values remain in the page's draft owner. */
export function createConfigApi(fetcher: typeof fetch = fetch): ConfigApi {
  let generation = 0;
  let cache: {fields: ConfigField[]; at: number} | null = null;
  let inflight: {generation: number; promise: Promise<ConfigField[]>} | null = null;

  async function request(path: string, options: RequestInit): Promise<unknown> {
    const response = await fetcher(path, {credentials: 'same-origin', ...options});
    if (!(response.headers.get('content-type') || '').includes('application/json')) {
      throw new ConfigApiError(response.status === 401 || response.redirected
        ? '登录已失效，请重新登录后刷新。' : '配置接口返回了非 JSON 响应', response.status);
    }
    let payload: unknown;
    try {payload = await response.json();} catch {throw new ConfigApiError('配置接口返回了无效 JSON', response.status);}
    const body = object(payload);
    if (!response.ok || body.ok === false) {
      const detail = object(body.error), fields: ConfigFieldErrors = {};
      for (const [key, value] of Object.entries(object(body.fields || detail.fields))) {
        if (typeof value === 'string') fields[key] = value;
      }
      throw new ConfigApiError(
        typeof body.error === 'string' ? body.error : String(detail.message || body.message || `请求失败（HTTP ${response.status}）`),
        response.status, String(detail.code || body.code || body.error_code || ''), fields,
      );
    }
    return payload;
  }
  function invalidate() {generation++; cache = null; inflight = null;}

  return {
    async getSchema(options = {}) {
      if (options.signal?.aborted) throw new DOMException('读取已取消', 'AbortError');
      if (inflight?.generation === generation) return clone(await inflight.promise);
      if (!options.force && cache && Date.now() - cache.at < 30_000) return clone(cache.fields);
      const current = generation;
      const promise = request('/api/config', {signal: options.signal}).then(payload => {
        const fields = sanitizeConfigFields(payload);
        if (generation === current) cache = {fields, at: Date.now()};
        return fields;
      });
      inflight = {generation: current, promise};
      try {return clone(await promise);} finally {if (inflight?.promise === promise) inflight = null;}
    },
    async save(updates: ConfigUpdates) {
      const payload = await request('/api/config', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({updates}),
      });
      if (!payload || typeof payload !== 'object' || Array.isArray(payload)
        || !Array.isArray(object(payload).updated)
        || !(object(payload).updated as unknown[]).every(key => typeof key === 'string')) {
        throw new ConfigApiError('配置保存响应格式无效', 0, 'config_save_response_invalid');
      }
      invalidate();
      return payload as ConfigSaveResponse;
    },
    invalidate,
  };
}
