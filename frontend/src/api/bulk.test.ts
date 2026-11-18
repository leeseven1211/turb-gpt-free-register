import {expect,it,vi} from 'vitest';
import {BulkApiError,createBulkApi} from './bulk';

it('bulk unwraps its response while preserving decimal bigint IDs and the caller request',async()=>{
  const fetcher=vi.fn(async()=>Response.json({ok:true,request_id:'r1',data:{id:'9007199254740993',run_id:'9223372036854775807'}}));
  const data=await createBulkApi(fetcher).request('/batches');
  expect(data).toEqual({id:'9007199254740993',run_id:'9223372036854775807'});
  expect(fetcher).toHaveBeenCalledWith('/api/bulk/batches',{credentials:'same-origin'});
});
it('bulk preserves domain error fields, original request ID and auth errors',async()=>{
  const fetcher=vi.fn(async()=>Response.json({ok:false,request_id:'r2',error:{code:'selection_consumed',message:'已创建',details:{existing_batch_id:'9007199254740993'},field:'selection_id',fields:{name:'过长'},retryable:false}},{status:409}));
  await expect(createBulkApi(fetcher).request('/batches')).rejects.toMatchObject({name:'BulkApiError',status:409,code:'selection_consumed',message:'已创建',details:{existing_batch_id:'9007199254740993'},field:'selection_id',fields:{name:'过长'},requestId:'r2',retryable:false});
  await expect(createBulkApi(async()=>Response.json({error:'重新登录'},{status:401})).request('/catalog')).rejects.toMatchObject({status:401,message:'重新登录'});
});
it('bulk fails non-JSON and invalid success envelopes without losing abort identity',async()=>{
  await expect(createBulkApi(async()=>new Response('<html>login</html>',{status:200})).request('/catalog')).rejects.toBeInstanceOf(BulkApiError);
  const abort=new DOMException('aborted','AbortError');
  await expect(createBulkApi(async()=>{throw abort;}).request('/catalog')).rejects.toBe(abort);
});
it('malformed bulk success is rejected before downstream state can treat it as accepted',async()=>{
 for(const value of [{ok:true}, {ok:true,data:null}, {ok:true,data:'accepted'}, {ok:true,data:[]}]){
  await expect(createBulkApi(async()=>Response.json(value)).request('/batches')).rejects.toBeInstanceOf(BulkApiError);
 }
 await expect(createBulkApi(async()=>new Response('{"ok":true,"data":{}}',{headers:{'content-type':'text/html'}})).request('/catalog')).rejects.toBeInstanceOf(BulkApiError);
});
