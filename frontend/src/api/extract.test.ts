import {afterEach,describe,expect,it,vi} from 'vitest';
import {createExtractApi,extractParams} from './extract';
import {ApiError} from './client';
const json=(text:string,status=200)=>new Response(text,{status,headers:{'Content-Type':'application/json'}});
afterEach(()=>vi.unstubAllGlobals());
describe('extract HTTP contract',()=>{
 it('decodes numeric task/account/batch bigint before JSON rounds it and keeps exact action paths',async()=>{const fetch=vi.fn().mockResolvedValueOnce(json('{"items":[{"task_id":9007199254740993,"account_id":9007199254740995,"batch_id":9007199254740997}],"total":1,"page":1,"counts":{}}')).mockResolvedValueOnce(json('{"ok":true,"accepted":true,"task_id":9007199254740993,"run_id":9007199254740999}'));vi.stubGlobal('fetch',fetch);const api=createExtractApi();const result=await api.tasks({page:1,size:20,provider:'',mode:'',status:'',query:'',batch:'9007199254740997'});expect(result.items[0]?.task_id).toBe('9007199254740993');expect(result.items[0]?.account_id).toBe('9007199254740995');const receipt=await api.action(result.items[0]!.task_id,'sync_status');expect(fetch.mock.calls[1]?.[0]).toBe('/api/extract-workbench/tasks/9007199254740993/actions');expect(receipt.run_id).toBe('9007199254740999');expect(fetch.mock.calls[0]?.[0]).toContain('batch_id=9007199254740997');});
 it('rejects HTML login redirects, invalid JSON boundaries and business failures',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(new Response('<html>login</html>',{headers:{'Content-Type':'text/html'}})).mockResolvedValueOnce(json('{"ok":false,"error":"missing configuration"}',409)));const api=createExtractApi();await expect(api.config()).rejects.toBeInstanceOf(ApiError);await expect(api.cancel(1)).rejects.toThrow('missing configuration');});
 it('passes provider_id and all filters to CSV without inventing page cursors',async()=>{const fetch=vi.fn().mockResolvedValue(new Response('id,email\n1,synthetic@example.test',{headers:{'Content-Type':'text/csv'}}));vi.stubGlobal('fetch',fetch);await createExtractApi().export({provider:'huanguang',mode:'extract_only',status:'failed',query:'x',batch:'9007199254740993',page:7,size:50});const url=String(fetch.mock.calls[0]?.[0]);expect(url).toContain('provider_id=huanguang');expect(url).toContain('batch_id=9007199254740993');expect(new URL(url,'http://local').searchParams.has('page')).toBe(false);expect(url).not.toContain('cursor');});
 it('reads AT from the explicit account secret endpoint and rejects nonnumeric unsafe task IDs',async()=>{const source=vi.fn(async()=>({ok:true,value:'private-ephemeral'}));const api=createExtractApi({dataSource:source});expect((await api.secret('9007199254740993')).value).toBe('private-ephemeral');expect(source).toHaveBeenCalledWith('/api/accounts/9007199254740993/secret?field=access_token',{});expect(()=>extractParams({provider:'',mode:'',status:'',query:'',batch:String(-1),page:1,size:20})).toThrow();});
});

it('rejects mismatched batch details, invalid candidate counts and empty payment artifacts',async()=>{let value:unknown={item:{batch_id:2}};const api=createExtractApi({dataSource:async()=>value});await expect(api.batch(1)).rejects.toThrow();value={total:1,selected_count:2,items:[]};await expect(api.candidates({query:'',source:'',date_from:'',date_to:'',extract_status:'never',promotion:'eligible'},100)).rejects.toThrow();value={ok:true,entry:{}};await expect(api.paymentEntry(1)).rejects.toThrow();});


describe('extract collection actions',()=>{
 it('submits selected tasks once and polls the accepted sync command before returning results',async()=>{
  const source=vi.fn().mockResolvedValueOnce({ok:true,accepted:true,command_id:'9007199254740997',status:'queued'}).mockResolvedValueOnce({ok:true,command_id:'9007199254740997',status:'partial_success',updated_count:1,skipped_count:1,failed_count:0,items:[{key:'9007199254740993',status:'updated',data:{task_id:'9007199254740993',run_id:'9007199254740999'}},{key:'2',status:'skipped',reason_code:'task_active',reason:'任务仍在执行'}]});
  const result=await createExtractApi({dataSource:source}).actionBulk(['9007199254740993',2],'sync_status');
  expect(source).toHaveBeenCalledTimes(2);expect(source.mock.calls[0]?.[0]).toBe('/api/extract-workbench/tasks/actions-bulk');
  const options=source.mock.calls[0]?.[1] as RequestInit;expect(JSON.parse(String(options.body))).toEqual({task_ids:['9007199254740993','2'],action:'sync_status'});expect(options.headers).toMatchObject({'Idempotency-Key':expect.any(String)});
  expect(source.mock.calls[1]?.[0]).toBe('/api/bulk-mutations/9007199254740997');expect(result.items?.[0]?.data?.run_id).toBe('9007199254740999');expect(result.updated_count).toBe(1);expect(result.accepted).toBe(false);
 });
 it('reads local payment entries in one request with exact selected task IDs',async()=>{
  const source=vi.fn(async(_path:string,_options?:RequestInit)=>({ok:true,items:[{task_id:'9007199254740993',status:'updated',entry:{payment_url:'https://pay.example.test/local'}},{task_id:'2',status:'skipped',reason_code:'payment_entry_missing',reason:'未保存支付入口'}],requested_count:2,unique_count:2,duplicate_count:0}));
  const result=await createExtractApi({dataSource:source}).paymentEntries(['9007199254740993',2]);
  expect(source).toHaveBeenCalledTimes(1);expect(source.mock.calls[0]?.[0]).toBe('/api/extract-workbench/tasks/payment-entries');expect(JSON.parse(String(source.mock.calls[0]?.[1]?.body))).toEqual({task_ids:['9007199254740993','2']});expect(result.items[0]?.entry?.payment_url).toBe('https://pay.example.test/local');
 });
});
