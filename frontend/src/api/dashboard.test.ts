import {describe,expect,it,vi} from 'vitest';
import {createDashboardApi} from './dashboard';

describe('dashboard API',()=>{
 it('keeps aggregate and capability reads separate and abortable',async()=>{
  const send=vi.fn(async(path:string,options?:RequestInit)=>({path,signal:options?.signal}));
  const api=createDashboardApi(send);
  const controller=new AbortController();
  await expect(api.dashboard(controller.signal)).resolves.toEqual({path:'/api/dashboard',signal:controller.signal});
  await expect(api.capabilities(controller.signal)).resolves.toEqual({path:'/api/capabilities',signal:controller.signal});
  expect(send).toHaveBeenCalledTimes(2);
 });
});
