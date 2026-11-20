import {request as clientRequest} from './client';
import {parseTaskJson,type TaskId} from './taskIds';

const request = <T>(path:string, options:RequestInit = {}) => clientRequest<T>(path, options, parseTaskJson);

export type RegistrationId = TaskId|string;
export interface RegistrationSource {value:string;label?:string;enabled?:boolean;[key:string]:unknown}
export interface RegistrationMeta {
  sources:RegistrationSource[];registration_drivers:RegistrationSource[];manual_mode?:boolean;
  capabilities?:{
    features?:Record<string,{enabled?:boolean;reason?:string}>;
    email_sources?:Record<string,{enabled?:boolean;reason?:string}>;
  };
}
export interface RegistrationSummary {
  accounts?:number;
  email_supply?:{status?:string;total?:number;available?:number;used?:number;failed?:number;reason?:string;statistics_updated_at?:string;[key:string]:unknown};
  [key:string]:unknown;
}
export interface RegistrationJob {
  id:RegistrationId; batch_id?:RegistrationId|null; parent_job_id?:RegistrationId|null; operation_task_id?:RegistrationId|null; operation_run_id?:RegistrationId|null;
  status?:string;display_status?:string;retryable?:boolean;retry_action?:string;retry_label?:string;email?:string;email_source?:string;registration_driver?:string;
  [key:string]:unknown;
}
export interface RegistrationBatch {batch_id:RegistrationId;items:RegistrationJob[];total?:number;workers?:number;status_counts?:Record<string,number>;[key:string]:unknown}
export interface JobsResponse {items?:RegistrationJob[];total?:number;revision?:string;status_counts?:Record<string,number>;facets?:Record<string,unknown>;progress_batch?:RegistrationBatch|null;progress_batches?:RegistrationBatch[];[key:string]:unknown}
export interface JobProgressResponse {ok:boolean;job?:RegistrationJob}
export interface RegistrationApi {
  metadata(signal?:AbortSignal):Promise<RegistrationMeta>;
  summary(signal?:AbortSignal):Promise<RegistrationSummary>;
  jobs(params:Record<string,string|number>,signal?:AbortSignal):Promise<JobsResponse>;
  progress(id:RegistrationId,signal?:AbortSignal):Promise<JobProgressResponse>;
  create(payload:{count:number;workers:number;email_source:string;debug_enabled:boolean},signal?:AbortSignal):Promise<Record<string,any>>;
  action(path:string,payload?:unknown,signal?:AbortSignal):Promise<Record<string,any>>;
  log(id:RegistrationId,signal?:AbortSignal):Promise<Record<string,any>>;
  debug(id:RegistrationId,signal?:AbortSignal):Promise<Record<string,any>>;
  diagnostics(id:RegistrationId,signal?:AbortSignal):Promise<Record<string,any>>;
  compare(id:RegistrationId,signal?:AbortSignal):Promise<Record<string,any>>;
}
const json=(payload:unknown):RequestInit=>({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload ?? {})});
export function createRegistrationApi():RegistrationApi {
  return {
    metadata:signal=>Promise.all([
      request<RegistrationMeta>('/api/email-sources',{signal}),
      request<Record<string,any>>('/api/capabilities',{signal}),
    ]).then(([value,capabilities])=>({...value,capabilities})),
    summary:signal=>request<RegistrationSummary>('/api/summary',{signal}),
    jobs:(params,signal)=>request<JobsResponse>(`/api/jobs?${new URLSearchParams(Object.entries(params).map(([k,v])=>[k,String(v)]))}`,{signal}),
    progress:(id,signal)=>request<JobProgressResponse>(`/api/jobs/${encodeURIComponent(String(id))}/progress`,{signal}),
    create:(payload,signal)=>request<Record<string,any>>('/api/jobs', {...json(payload),signal}),
    action:(path,payload={},signal)=>request<Record<string,any>>(path,{...json(payload),signal}),
    log:(id,signal)=>request<Record<string,any>>(`/api/jobs/${encodeURIComponent(String(id))}/log`,{signal}),
    debug:(id,signal)=>request<Record<string,any>>(`/api/jobs/${encodeURIComponent(String(id))}/debug?limit=300`,{signal}),
    diagnostics:(id,signal)=>request<Record<string,any>>(`/api/jobs/${encodeURIComponent(String(id))}/diagnostics?limit=100`,{signal}),
    compare:(id,signal)=>request<Record<string,any>>(`/api/jobs/${encodeURIComponent(String(id))}/debug/compare`,{signal}),
  };
}
