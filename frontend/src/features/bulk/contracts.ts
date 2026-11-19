import type {AccountQueryAdapter,AccountQuerySpec} from '../accounts/queryAdapter';

export type BulkId=string;
export type BulkRecord=Record<string,unknown>;
export interface BulkNavigation {
  tab:'bulk';view:'list'|'create'|'detail';batch_id?:BulkId;round_id?:BulkId;result_state?:string;
  cursor?:string;q?:string;reason_code?:string;operation?:string;state?:string;created_from?:string;created_to?:string;
}
export interface BulkPageInfo {has_more:boolean;next_cursor?:string|null;page_size:number}
export interface BulkPageData<T=BulkRecord> {items:T[];page:BulkPageInfo;summary?:BulkRecord;summary_revision?:string|number;[key:string]:unknown}
export interface BulkOperation extends BulkRecord {
  key:string;version:number;label:string;availability?:{enabled?:boolean;available?:boolean;reason?:string};
  effective_settings?:BulkRecord;parameter_schema?:BulkRecord;capabilities?:BulkRecord;config_revision?:string;
}
export interface BulkCatalog extends BulkRecord {operations:BulkOperation[];query_schema:BulkRecord;limits:BulkRecord;config_revision?:string}
export interface BulkApi {request<T=BulkRecord>(path:string,options?:RequestInit):Promise<T>}
export interface BulkIntentRecord {storageKey:string;key:string;signature:string;path:string;body:BulkRecord}
export interface BulkIntentClient {
  submit<T=BulkRecord>(scope:string,path:string,body:BulkRecord):Promise<T>;
  pending():readonly BulkIntentRecord[];
  recover<T=BulkRecord>(record:BulkIntentRecord):Promise<T>;
}
export interface BulkStorage {getItem(key:string):string|null;setItem(key:string,value:string):void;removeItem(key:string):void;key(index:number):string|null;readonly length:number}
export interface BulkDraft extends BulkRecord {
  name:string;operation_key:string;query:AccountQuerySpec;source:BulkRecord|null;parameters:BulkRecord;max_concurrency:number;
}
export interface BulkSliceCallbacks {
  navigate(view:BulkNavigation['view'],extra?:Partial<BulkNavigation>,focusReport?:boolean):void;
  updateNavigation(extra:Partial<BulkNavigation>):void;
  notify(message:string):void;
  formatDateTime(value:unknown):string;
  facetLabel?(group:string,value:string):string;
  openTask(taskId:BulkId,runId?:BulkId|null):void|Promise<unknown>;
  copyBatch?(query:AccountQuerySpec,source:BulkRecord|null,operationKey:string):void;
}
export interface BulkCreateDependencies {
  api:BulkApi;intents:BulkIntentClient;adapter:AccountQueryAdapter;storage:BulkStorage;
  callbacks:BulkSliceCallbacks;now():number;
}
export interface BulkListDependencies {api:BulkApi;callbacks:BulkSliceCallbacks}
export interface BulkDetailDependencies {api:BulkApi;intents:BulkIntentClient;callbacks:BulkSliceCallbacks;now():number}
export interface BulkPageDependencies extends BulkCreateDependencies {
  onNavigation(navigation:BulkNavigation,mode:'push'|'replace'):void;
  isVisible?():boolean;
}
export function bulkId(value:unknown):BulkId {
  if(typeof value!=='string'||!/^[1-9]\d*$/.test(value))throw new Error('任务标识无效');
  return value;
}
export function bulkObject(value:unknown):BulkRecord {
  if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('服务端响应格式无效');
  return value as BulkRecord;
}

function record(value: unknown): BulkRecord {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('批次列表响应格式无效');
  return value as BulkRecord;
}

export function readBulkPage(response: unknown) {
  const data = record(response);
  if (!Array.isArray(data.items)) throw new Error('批次列表响应格式无效');
  const items = data.items.map((value: unknown): BulkRecord & { id: string } => {
    const row = record(value);
    const id = Number.isSafeInteger(row.id) ? String(row.id) : row.id;
    if (typeof id !== 'string' || !/^[1-9]\d*$/.test(id)) throw new Error('批次编号无效');
    return { ...row, id };
  });
  const cursor = data.next_cursor ?? (data.page == null ? null : record(data.page).next_cursor);
  if (cursor != null && typeof cursor !== 'string') throw new Error('批次分页响应格式无效');
  const summary = data.summary == null ? {} : record(data.summary);
  return { items, summary, nextCursor: cursor || null };
}
