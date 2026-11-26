import {ApiError,request} from './client';

export type DashboardRequest=(path:string,options?:RequestInit)=>Promise<unknown>;
export type PendingCapabilities=()=>Promise<unknown>|undefined;
export interface DashboardApi {
 dashboard(signal?:AbortSignal):Promise<any>;
 capabilities(signal?:AbortSignal):Promise<any>;
 extractSummary?(signal?:AbortSignal):Promise<any>;
 registrationDaily?(dateFrom?:string,dateTo?:string,signal?:AbortSignal):Promise<any>;
}

async function waitForSharedCapabilities(pending:Promise<unknown>, signal?:AbortSignal):Promise<unknown> {
 if (!signal) return pending;
 signal.throwIfAborted();
 let cancel!:()=>void;
 const cancelled = new Promise<never>((_resolve, reject) => {
  cancel = () => reject(signal.reason);
  signal.addEventListener('abort', cancel, {once:true});
 });
 try {
  return await Promise.race([pending, cancelled]);
 } finally {
  signal.removeEventListener('abort', cancel);
 }
}

export function createDashboardApi(
 send:DashboardRequest=(path,options)=>request(path,options),
 pendingCapabilities?:PendingCapabilities,
):DashboardApi {
 const get=<T>(path:string,signal?:AbortSignal)=>send(path,signal?{signal}:undefined) as Promise<T>;
 return {
  dashboard:(signal)=>get('/api/dashboard',signal),
  extractSummary:(signal)=>get('/api/extract-workbench/summary',signal),
  registrationDaily:(dateFrom,dateTo,signal)=>{
   const params=new URLSearchParams();
   if(dateFrom)params.set('date_from',dateFrom);
   if(dateTo)params.set('date_to',dateTo);
   const suffix=params.toString()?`?${params.toString()}`:'';
   return get(`/api/dashboard/registration-daily${suffix}`,signal);
  },
  async capabilities(signal){
   const pending = pendingCapabilities?.();
   if (!pending) return get('/api/capabilities', signal);
   const result = await waitForSharedCapabilities(pending, signal);
   if (result === null || typeof result !== 'object' || !('ok' in result) || result.ok !== true) {
    throw new ApiError('能力检查返回无效数据', 200);
   }
   return result;
  },
 };
}
