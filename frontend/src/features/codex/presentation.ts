import type {CodexRow} from '../../api/codex';

export interface CodexStatus {
  label: string;
  title: string;
  tone: 'neutral' | 'success' | 'warning' | 'danger';
}

export function credentialStatus(row: CodexRow): CodexStatus {
  const count = Number(row.exported_count || 0);
  const exported = row.exported === true || count > 0;
  const linked = row.sub2api_account_id != null && String(row.sub2api_account_id).trim() !== '';
  if (exported && count <= 0 && linked) {
    return {label: '已关联', title: `Sub2API ID ${row.sub2api_account_id} 已有关联记录，本地下载 0 次`, tone: 'neutral'};
  }
  return exported
    ? {label: '已导出', title: `导出 ${count} 次，最近 ${row.exported_at || '-'}`, tone: 'neutral'}
    : {label: '未导出', title: '没有本地导出或 Sub2API 关联记录', tone: 'success'};
}

export function oauthStatus(row: CodexRow): CodexStatus {
  const status = String(row.oauth_status || 'unknown');
  const httpStatus = Number(row.sub2api_http_status);
  const seconds = row.oauth_seconds_left == null ? NaN : Number(row.oauth_seconds_left);
  const remaining = Number.isFinite(seconds)
    ? `${seconds < 0 ? '已过期' : '剩余'} ${Math.floor(Math.abs(seconds) / 86400)}天${Math.floor(Math.abs(seconds) % 86400 / 3600)}小时`
    : '';
  const title = [
    httpStatus ? `Sub2API HTTP ${httpStatus}` : '',
    row.oauth_expires_at ? `过期：${row.oauth_expires_at}` : '',
    remaining,
    row.oauth_refreshable ? '存在 refresh_token，可尝试自动刷新' : '缺少 refresh_token',
    Number(row.sub2_uploaded_count || 0) > 0 ? '已纳入 sub2 自动同步' : '未记录 sub2 自动同步',
    row.oauth_refresh_error ? `最近刷新失败：${row.oauth_refresh_error}` : '',
    row.sub2_sync_error ? `sub2 同步失败：${row.sub2_sync_error}` : '',
  ].filter(Boolean).join('；');
  const result = (label: string, tone: CodexStatus['tone']): CodexStatus => ({label, title, tone});
  if (status === 'deactivated') return result('账号停用', 'danger');
  if (httpStatus === 401) return result('401 失效', 'danger');
  if (row.oauth_reauth_required) return result('需重授权', 'danger');
  if (status === 'valid') return result('有效', 'success');
  if (status === 'expiring') return result('即将过期', 'warning');
  if (status === 'expired') return result(row.oauth_refreshable ? '已过期' : '已过期·需重授权', 'danger');
  if (status === 'missing') return result('缺少令牌', 'danger');
  return result('未知', 'neutral');
}
