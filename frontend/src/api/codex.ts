import type {components} from './codex-schema';
import {ApiError, request} from './client';
import {bulkMutationRequest,projectBulkMutation,submitBulkMutation,type BulkMutationOptions} from './bulkMutations';

export type CodexRow = components['schemas']['CodexRow'];
export type CodexFacets = components['schemas']['CodexFacets'];
export type CodexListResponse = components['schemas']['CodexListResponse'];
export type CodexTaskReference = components['schemas']['CodexTaskReference'];
export type CodexActionResponse = components['schemas']['CodexActionResponse'];
export interface CodexFilters {
  q: string; plan: string; status: string; oauth_status: string; account_id: string;
  sub2api_id: string; date_from: string; date_to: string; expired_date: string;
}
export interface CodexCallbacks {
  notify(message: string): void;
  confirm(message: string): boolean | Promise<boolean>;
  openTasks(type?: string): void;
  operationWorkers(): number;
}
export interface CodexListQuery {page: number; size: number; archived: boolean; filters: CodexFilters}
export interface CodexDownload {blob: Blob; filename: string; acknowledged: string[]; failed: number}
export function emptyCodexFilters(): CodexFilters {
  return {q: '', plan: '', status: '', oauth_status: '', account_id: '', sub2api_id: '', date_from: '', date_to: '', expired_date: ''};
}
function post(path: string, body: object): Promise<CodexActionResponse> {
  return request(`/api/codex/${path}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
}
async function bulkPost(path:string,body:object,options?:BulkMutationOptions):Promise<CodexActionResponse>{
  return projectBulkMutation(await submitBulkMutation(bulkMutationRequest,`/api/codex/${path}`,body,options),'codex',path==='delete-bulk'?'delete':'update') as CodexActionResponse;
}
function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
function downloadName(disposition: string, fallback: string): string {
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(disposition)?.[1];
  const regular = /filename=(?:"([^"]+)"|([^;]+))/i.exec(disposition);
  let filename = regular?.[1] || regular?.[2]?.trim() || fallback;
  if (encoded) {try { filename = decodeURIComponent(encoded.trim()); } catch { /* 保留普通文件名。 */ }}
  return filename.replace(/[\\/\x00-\x1f\x7f]/g, '_') || fallback;
}
function downloadError(payload: Record<string, unknown>, status: number): ApiError {
  const error = payload.error;
  // 仅展示协议定义的错误消息；不得把凭证体或 JSON 解析异常写入通知。
  const message = typeof error === 'string' ? error : record(error).message;
  const details = Array.isArray(payload.errors) ? payload.errors.slice(0, 3).map(item => {
    const detail = record(item);
    return typeof detail.filename === 'string' && typeof detail.error === 'string' ? `${detail.filename}: ${detail.error}` : '';
  }).filter(Boolean) : [];
  return new ApiError((typeof message === 'string' ? message : `下载失败（HTTP ${status}）`) + (details.length ? `；${details.join('；')}` : ''), status,
    typeof record(error).code === 'string' ? String(record(error).code) : typeof payload.error_code === 'string' ? payload.error_code : '');
}
async function download(path: string, fallback: string, requested: string[], kind: 'single' | 'bulk' | 'zip', body?: object): Promise<CodexDownload> {
  const response = await fetch(path, {credentials: 'same-origin', ...(body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {})});
  if (response.status === 401 || response.redirected) throw new ApiError('登录已失效，请重新登录后刷新。', response.status);
  const type = (response.headers.get('Content-Type') || '').toLowerCase();
  const disposition = response.headers.get('Content-Disposition') || '';
  const blob = await response.blob();
  if (!blob.size) throw new ApiError('下载返回空文件。', response.status);
  let payload: Record<string, unknown> = {};
  if (type.includes('application/json')) {
    try {
      const parsed: unknown = JSON.parse(await blob.text());
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('invalid');
      payload = record(parsed);
    }
    catch {throw new ApiError('下载返回无效 JSON。', response.status);}
    if (!response.ok || payload.ok === false || payload.error) throw downloadError(payload, response.status);
  } else if (!response.ok) {
    throw new ApiError(`下载失败（HTTP ${response.status}）`, response.status);
  }
  if (!/attachment/i.test(disposition)) throw new ApiError('服务返回了非下载附件，请刷新后重试。', response.status);
  if (kind === 'zip' ? !type.includes('application/zip') : !type.includes('application/json')) {
    throw new ApiError('服务返回了非下载内容，请刷新后重试。', response.status);
  }
  let acknowledged = kind === 'single' ? requested : [];
  let failed = 0;
  if (kind === 'bulk') {
    if (!Array.isArray(payload.credentials) || typeof payload.count !== 'number') throw new ApiError('下载返回无效的批量凭证附件。', response.status);
    acknowledged = Array.isArray(payload.credentials) ? payload.credentials.map(item => record(item).filename)
      .filter((name): name is string => typeof name === 'string' && requested.includes(name)) : [];
    failed = Array.isArray(payload.errors) ? payload.errors.length : 0;
  }
  // ZIP 中逐文件回执位于 manifest.json；外层响应不能证明每个选中项都已成功。
  return {blob, filename: downloadName(disposition, fallback), acknowledged, failed};
}

export const codexApi = {
  list(query: CodexListQuery, signal?: AbortSignal): Promise<CodexListResponse> {
    const params = new URLSearchParams({paged: '1', page: String(query.page), page_size: String(query.size), archived: query.archived ? 'only' : '0'});
    for (const [key, value] of Object.entries(query.filters)) if (value !== '') params.set(key, value);
    return request(`/api/codex?${params}`, {signal});
  },
  archive: (filename: string, archived: boolean) => post('archive', {filename, archived}),
  archiveBulk: (filenames: string[], archived: boolean,options?:BulkMutationOptions) => bulkPost('archive-bulk', {filenames, archived},options),
  delete: (filename: string) => post('delete', {filename}),
  deleteBulk: (filenames: string[],options?:BulkMutationOptions) => bulkPost('delete-bulk', {filenames},options),
  reset: (filename: string) => post('reset-export', {filename}),
  resetBulk: (filenames:string[],options?:BulkMutationOptions)=>bulkPost('reset-export-bulk',{filenames},options),
  refreshToken: (filenames: string[]) => post('refresh-token-bulk', {filenames}),
  reauthorize: (filenames: string[]) => post('retry-bulk', {filenames}),
  uploadSub2: (filenames: string[]) => post('upload-sub2-bulk', {filenames}),
  download: (filename: string, cpa = false) => download(`/api/codex/${cpa ? 'download-from-cpa' : 'download'}/${encodeURIComponent(filename)}`,
    cpa ? filename.replace(/-cpa-callback\.json$/i, '-free.json') : filename, [filename], 'single'),
  downloadBulk: (filenames: string[], cpa = false) => download(`/api/codex/${cpa ? 'download-bulk-from-cpa' : 'download-bulk'}`,
    cpa ? 'codex-cpa-bulk.zip' : 'codex-bulk.json', filenames, cpa ? 'zip' : 'bulk', {filenames}),
};
