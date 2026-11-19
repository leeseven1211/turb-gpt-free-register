import {vi} from 'vitest';
import {createEmailApi} from '../../api/email';
import type {EmailMountDependencies} from './contracts';
export function deferred<T>(){let resolve!:(value:T)=>void,reject!:(cause:unknown)=>void;const promise=new Promise<T>((ok,fail)=>{resolve=ok;reject=fail;});return{promise,resolve,reject};}
export function fixture(){
 const calls:{path:string;options:RequestInit}[]=[];
 const handlers=new Map<string,(options:RequestInit)=>unknown>();
 const send=async<T>(path:string,options:RequestInit={}):Promise<T>=>{
  calls.push({path,options});const handler=handlers.get(path.split('?')[0]!);
  return await(handler?handler(options):path.startsWith('/api/dashboard')?{email:{supply:{sources:[]}}}:path.includes('/summary')?{parents:[]}:path.includes('/allocations')||path.startsWith('/api/outlook?')?{items:[],total:0,facets:{}}:{ok:true}) as T;
 };
 const deps:EmailMountDependencies={notify:vi.fn(),confirm:vi.fn(()=>true),clipboard:vi.fn(async()=>{}),onNavigate:vi.fn(),onInventoryChanged:vi.fn(async()=>{})};
 return{api:createEmailApi(send),deps,calls,handlers};
}
