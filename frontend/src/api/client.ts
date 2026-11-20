/** 统一处理 HTTP 状态和现有两种错误响应，不改变服务端业务契约。 */
export class ApiError extends Error {
  constructor(message: string, public status: number, public code = '', public readonly unavailableFeature = '') {
    super(message);
    this.name = 'ApiError';
  }
}

export async function request<T>(path: string, options: RequestInit = {}, decode?: (text: string) => unknown): Promise<T> {
  const response = await fetch(path, {credentials: 'same-origin', ...options});
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    throw new ApiError(response.redirected || response.status === 401
      ? '登录已失效，请重新登录后刷新。' : `服务返回了非 JSON 响应（HTTP ${response.status}）`, response.status);
  }
  const payload: any = decode ? decode(await response.text()) : await response.json();
  if (!response.ok || payload?.ok === false) {
    const error = payload?.error;
    const unavailableFeature = response.status === 503 && payload?.ok === false && typeof payload.feature === 'string'
      ? payload.feature : '';
    throw new ApiError(typeof error === 'string' ? error : error?.message || payload?.message || `请求失败（HTTP ${response.status}）`,
      response.status, error?.code || payload?.error_code || payload?.code || '', unavailableFeature);
  }
  return payload as T;
}

export function isAbort(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError';
}
