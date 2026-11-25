import {request} from './client';
import {parseTaskJson} from './taskIds';
import {parseBulkMutationJson,projectBulkMutation,submitBulkMutation,type BulkMutationOptions} from './bulkMutations';
import type {BatchResponse,ButlerFilters,ButlerPreview,ButlerRequest,EmailIdentity,HistoryQuery,HistoryRow,InventoryQuery,InventoryResponse,LocalImportPayload,LocalImportResult,LocalPreview,MutationResult,ParentHistory,SourceCard} from '../features/email/contracts';
export type EmailRequest=(path:string,options?:RequestInit)=>Promise<unknown>;
export function createEmailApi(send:EmailRequest=(path,options)=>request(path,options,path.startsWith('/api/bulk-mutations/')||path==='/api/outlook/status-bulk'||path==='/api/outlook/delete-bulk'?parseBulkMutationJson:parseTaskJson)){
 const get=<T>(path:string,signal?:AbortSignal)=>send(path,{signal}) as Promise<T>;
 const post=<T>(path:string,body:unknown,signal?:AbortSignal)=>send(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),...(signal?{signal}:{})}) as Promise<T>;
 return {
  overview:(signal?:AbortSignal)=>get<{email?:{supply?:{sources?:SourceCard[]};sources?:SourceCard[]}}>('/api/dashboard',signal),
  inventory:(query:InventoryQuery,signal?:AbortSignal)=>{const {size,...values}=query;return get<InventoryResponse>(`/api/outlook?${new URLSearchParams({paged:'1',page:String(values.page),page_size:String(size),source:values.source,q:values.q,status:values.status,used_date:values.used_date,usage:String(values.usage||'')})}`,signal);},
  derivationSummary:(signal?:AbortSignal)=>get<{parents?:ParentHistory[]}>('/api/email-derivation/summary?source=all',signal),
  history:(query:HistoryQuery,signal?:AbortSignal)=>{const {size,page,...filters}=query;const params=new URLSearchParams({page:String(page),page_size:String(size)});for(const [key,value]of Object.entries(filters))if(value)params.set(key,value);return get<{items:HistoryRow[];total:number}>(`/api/email-derivation/allocations?${params}`,signal);},
  secret:(item:EmailIdentity,signal?:AbortSignal)=>get<{value?:string}>(`/api/outlook/secret?${new URLSearchParams({...item,field:'copy_line'})}`,signal),
  secrets:(items:EmailIdentity[],signal?:AbortSignal)=>post<{values?:{value?:string}[];skipped?:MutationResult['skipped']}>('/api/outlook/secret-bulk',{items,field:'copy_line'},signal),
  status:(body:EmailIdentity&{status:string;note:string})=>post<MutationResult>('/api/outlook/status',body),
  bulkStatus:async(body:{items:EmailIdentity[];status:string;source:string;note:string},options?:BulkMutationOptions)=>projectBulkMutation(await submitBulkMutation(send,'/api/outlook/status-bulk',body,options),'email','update') as MutationResult,
  delete:(item:EmailIdentity)=>post<MutationResult>('/api/outlook/delete',item),
  bulkDelete:async(body:{items:EmailIdentity[];source:string},options?:BulkMutationOptions)=>projectBulkMutation(await submitBulkMutation(send,'/api/outlook/delete-bulk',body,options),'email','delete') as MutationResult,
  localPreview:(body:LocalImportPayload,signal?:AbortSignal)=>post<LocalPreview>('/api/outlook/import-preview',body,signal),
  localImport:(body:LocalImportPayload)=>post<LocalImportResult>('/api/outlook/import',body),
  options:(signal?:AbortSignal)=>get<{providers?:{value:string;label:string}[]}>('/api/email-butler/import-options',signal),
  butlerPreview:(body:ButlerFilters,signal?:AbortSignal)=>post<ButlerPreview>('/api/email-butler/import-preview',body,signal),
  createBatch:(body:Pick<ButlerRequest,'request_id'|'preview_token'>)=>post<BatchResponse>('/api/email-butler/imports',body),
  batch:(id:string,signal?:AbortSignal)=>get<BatchResponse>(`/api/email-butler/imports/${encodeURIComponent(id)}`,signal),
  retryBatch:(id:string,body:Pick<ButlerRequest,'request_id'|'preview_token'>)=>post<BatchResponse>(`/api/email-butler/imports/${encodeURIComponent(id)}/retry`,body),
  cancelBatch:(id:string)=>send(`/api/email-butler/imports/${encodeURIComponent(id)}/cancel`,{method:'POST'}) as Promise<BatchResponse>,
 };
}
export type EmailApi=ReturnType<typeof createEmailApi>;
