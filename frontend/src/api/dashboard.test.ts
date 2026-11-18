import {afterEach,describe,expect,it,vi} from 'vitest';
import {createDashboardApi} from './dashboard';

afterEach(()=>vi.unstubAllGlobals());

describe('dashboard API',()=>{
 it('keeps aggregate and capability reads separate and abortable',async()=>{
  const send=vi.fn(async(path:string,options?:RequestInit)=>({path,signal:options?.signal}));
  const api=createDashboardApi(send);
  const controller=new AbortController();
  await expect(api.dashboard(controller.signal)).resolves.toEqual({path:'/api/dashboard',signal:controller.signal});
  await expect(api.capabilities(controller.signal)).resolves.toEqual({path:'/api/capabilities',signal:controller.signal});
  expect(send).toHaveBeenCalledTimes(2);
 });
 it('uses only same-origin GET requests with no mutation payload through the default transport',async()=>{
  const fetch=vi.fn(async()=>new Response('{"ok":true}',{headers:{'Content-Type':'application/json'}}));
  vi.stubGlobal('fetch',fetch);
  const api=createDashboardApi(),controller=new AbortController();
  await api.dashboard(controller.signal);
  await api.capabilities(controller.signal);
  expect(fetch.mock.calls.map(call=>(call as unknown[])[0])).toEqual(['/api/dashboard','/api/capabilities']);
  for(const call of fetch.mock.calls){
   const options=(call as unknown[])[1] as RequestInit;
   expect(options.credentials).toBe('same-origin');
   expect(options.signal).toBe(controller.signal);
   expect(options.method||'GET').toBe('GET');
   expect(options.body).toBeUndefined();
  }
 });
 it('reports a rejected read with the existing HTTP error contract',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>new Response('{"ok":false,"error":{"code":"unavailable","message":"统计暂不可用"}}',{status:503,headers:{'Content-Type':'application/json'}})));
  await expect(createDashboardApi().dashboard()).rejects.toMatchObject({status:503,code:'unavailable',message:'统计暂不可用'});
 });
});
