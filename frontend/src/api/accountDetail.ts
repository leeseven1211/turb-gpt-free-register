import {ApiError, request} from './client';

/** Existing GET /api/accounts/<id>/roxy-profile; optional public display data. */
export interface AccountRoxyProfileResponse {
  ok: true;
  profile_id: string | null;
  window_name: string | null;
}
export interface AccountDetailReadApi {
  roxyProfile(accountId: string, signal?: AbortSignal): Promise<AccountRoxyProfileResponse>;
}

export function createAccountDetailApi(): AccountDetailReadApi {
  return {
    async roxyProfile(accountId, signal) {
      if (!/^[1-9]\d*$/.test(accountId)) throw new Error('账号 ID 无效');
      const payload = await request<unknown>(`/api/accounts/${encodeURIComponent(accountId)}/roxy-profile`, {signal});
      if (!payload || typeof payload !== 'object' || Array.isArray(payload)
        || !('ok' in payload) || payload.ok !== true
        || !('profile_id' in payload) || !(payload.profile_id === null || typeof payload.profile_id === 'string')
        || !('window_name' in payload) || !(payload.window_name === null || typeof payload.window_name === 'string')) {
        throw new ApiError('账号详情返回了无效的响应，请重新打开详情重试。', 200, 'account_response_invalid');
      }
      return {ok: true, profile_id: payload.profile_id, window_name: payload.window_name};
    },
  };
}
