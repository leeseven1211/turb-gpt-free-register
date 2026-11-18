import {request} from './client';

export type DashboardRequest=(path:string,options?:RequestInit)=>Promise<unknown>;
export interface DashboardApi {
 dashboard(signal?:AbortSignal):Promise<any>;
 capabilities(signal?:AbortSignal):Promise<any>;
}

export function createDashboardApi(send:DashboardRequest=(path,options)=>request(path,options)):DashboardApi {
 const get=<T>(path:string,signal?:AbortSignal)=>send(path,signal?{signal}:undefined) as Promise<T>;
 return {
  dashboard:(signal)=>get('/api/dashboard',signal),
  capabilities:(signal)=>get('/api/capabilities',signal),
 };
}
