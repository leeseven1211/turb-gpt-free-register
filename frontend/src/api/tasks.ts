import type {components} from './schema';
import {ApiError, request as clientRequest} from './client';
import {optionalTaskId,parseTaskJson,taskId,type TaskId,type TaskResponse} from './taskIds';
import {bulkMutationRequest,submitBulkMutation,type BulkMutationOptions} from './bulkMutations';
export type {TaskId} from './taskIds';
const request=<T>(path:string,options:RequestInit={})=>clientRequest<T>(path,options,parseTaskJson);

export type OperationTask = TaskResponse<components['schemas']['OperationTask']>;
export type OperationRun = TaskResponse<components['schemas']['OperationRun']>;
export type OperationList = TaskResponse<components['schemas']['OperationList']>;
export type OperationDetail = TaskResponse<components['schemas']['OperationDetail']>;
export type OperationReceipts = components['schemas']['OperationReceipts'];
export interface OperationReceiptReference {task_id: TaskId; run_id: TaskId | null}
export type ProgressResponse = TaskResponse<components['schemas']['ProgressResponse']>;
export type EventsResponse = TaskResponse<components['schemas']['EventsResponse']>;
export type LogsResponse = TaskResponse<components['schemas']['LogsResponse']>;
export type ActionResponse = TaskResponse<components['schemas']['ActionResponse']>;
export type TaskProgress = TaskResponse<components['schemas']['OperationProgress']>;
export type TaskEvent = TaskResponse<components['schemas']['OperationEvent']>;
export type TaskLog = TaskResponse<components['schemas']['OperationLog']>;
export type FacetOption = components['schemas']['FacetOption'];
export type ErrorInfo = components['schemas']['ErrorInfo'];
export type TaskAction = 'retry' | 'cancel' | 'terminate' | 'delete';
export interface TaskFilters {
  task_id: string; type: string; target: string; status: string; target_status: string;
  batch: string; run_count: string; stage: string; created_from: string; created_to: string; result: string;
}
export type TaskQuery = TaskFilters & {page: number; page_size: number; include_facets?: number; include_batches?: number};
export type Facets = NonNullable<OperationList['facets']>;
export function emptyFilters(): TaskFilters {
  return {task_id: '', type: '', target: '', status: '', target_status: '', batch: '', run_count: '',
    stage: '', created_from: '', created_to: '', result: ''};
}
function queryString(query: object): string {
  return new URLSearchParams(Object.entries(query).filter(([, value]) => value !== undefined && value !== '')
    .map(([key, value]) => [key, String(value)])).toString();
}
function receiptQuery(references: readonly OperationReceiptReference[]): string {
  const params = new URLSearchParams();
  for (const reference of references) {
    const task = taskId(reference.task_id), run = optionalTaskId(reference.run_id);
    params.append('ref', run === null ? String(task) : `${task}:${run}`);
  }
  return params.toString();
}

/** 网络重试复用同一意图；改变选项代表新意图，不阻断新的批量重跑。 */
export async function operationIntent(scope: string, path: string, body?: object): Promise<ActionResponse> {
  const signature = JSON.stringify({path, body: body || null});
  const storageKey = `turb_operation_intent:${scope}:${signature}`;
  let key: string | null = null;
  let legacyMatched = false;
  const legacyKey = `turb_operation_intent:${scope}`;
  try {
    key = sessionStorage.getItem(storageKey);
    const legacy = JSON.parse(sessionStorage.getItem(legacyKey) || 'null');
    if (legacy?.key && legacy.signature === JSON.stringify({url: path, body: body || null})) {
      key ||= String(legacy.key);
      legacyMatched = true;
    }
  } catch { /* 禁用存储或旧记录无效时仍允许提交。 */ }
  key ||= globalThis.crypto?.randomUUID?.() || `operation-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  try { sessionStorage.setItem(storageKey, key); } catch { /* 幂等键仍随本次请求发送。 */ }
  const clear = () => { try { sessionStorage.removeItem(storageKey); if (legacyMatched) sessionStorage.removeItem(legacyKey); } catch { /* 无本地存储。 */ } };
  try {
    const result = await request<ActionResponse>(path, {method: 'POST', headers: {'Idempotency-Key': key,
      ...(body ? {'Content-Type': 'application/json'} : {})}, ...(body ? {body: operationBody(path,body)} : {})});
    clear();
    return result;
  } catch (error) {
    if (error instanceof ApiError && [400, 403, 404, 409, 410, 422, 429].includes(error.status)) clear();
    throw error;
  }
}

function operationBody(path:string,body:object):string {
  if(path!=='/api/operations/bulk')return JSON.stringify(body);
  const {task_ids:ids,...other}=body as {task_ids:TaskId[]}&Record<string,unknown>;
  if(!Array.isArray(ids))return JSON.stringify(body);
  // The existing endpoint requires JSON integers. Validated decimal tokens can be emitted without Number conversion.
  const prefix=JSON.stringify(other).slice(0,-1);
  return `${prefix}${prefix.length>1?',':''}"task_ids":[${ids.map(id=>String(taskId(id))).join(',')}]}`;
}

async function terminateBulk(taskIds:TaskId[],options:BulkMutationOptions={}):Promise<ActionResponse> {
  const result=await submitBulkMutation((path,init)=>{
    if(init?.method==='POST')return bulkMutationRequest(path,{...init,
      body:operationBody(path,{action:'terminate',task_ids:taskIds})});
    return bulkMutationRequest(path,init);
  },'/api/operations/bulk',{action:'terminate',task_ids:taskIds},options);
  if(!Array.isArray(result.items))return result as ActionResponse;
  const accepted=result.items.filter(item=>item.status==='updated').map(item=>({
    task_id:taskId(item.key),state:String(item.data?.state||'stopped'),message:String(item.data?.message||''),
  }));
  const skipped=result.items.filter(item=>item.status!=='updated').map(item=>({
    task_id:taskId(item.key),error:item.reason||'操作未接受',
  }));
  return {...result,ok:true,accepted,accepted_count:accepted.length,skipped,skipped_count:skipped.length};
}

export const tasksApi = {
  list: (query: TaskQuery, signal?: AbortSignal) => request<OperationList>(`/api/operations?${queryString(query)}`, {signal}),
  detail: (id: TaskId, signal?: AbortSignal) => request<OperationDetail>(`/api/operations/${taskId(id)}?include_events=0`, {signal}),
  receipts: (references: readonly OperationReceiptReference[], signal?: AbortSignal) =>
    request<OperationReceipts>(`/api/operations/receipts?${receiptQuery(references)}`, {signal}),
  progress: (id: TaskId, runId: TaskId, signal?: AbortSignal) => request<ProgressResponse>(`/api/operations/${taskId(id)}/runs/${taskId(runId)}/progress`, {signal}),
  events: (id: TaskId, runId: TaskId, query: {after_id?: TaskId; limit?: number} = {}, signal?: AbortSignal) =>
    request<EventsResponse>(`/api/operations/${taskId(id)}/runs/${taskId(runId)}/events?${queryString({limit: 500, ...query})}`, {signal}),
  logs: (id: TaskId, runId: TaskId, query: {cursor?: number; limit?: number} = {}, signal?: AbortSignal) =>
    request<LogsResponse>(`/api/operations/${taskId(id)}/runs/${taskId(runId)}/logs?${queryString({limit: 500, ...query})}`, {signal}),
  action: (id: TaskId, action: TaskAction) => action === 'retry'
    ? operationIntent(`retry:${taskId(id)}`, `/api/operations/${taskId(id)}/retry`)
    : request<ActionResponse>(`/api/operations/${taskId(id)}/${action}`, {method: 'POST'}),
  bulk: (action: TaskAction, taskIds: TaskId[], options?:BulkMutationOptions) => action === 'terminate'
    ? terminateBulk(taskIds,options)
    : action === 'retry'
    ? operationIntent('bulk:retry', '/api/operations/bulk', {action, task_ids: taskIds})
    : request<ActionResponse>('/api/operations/bulk', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: operationBody('/api/operations/bulk',{action, task_ids: taskIds})}),
};
