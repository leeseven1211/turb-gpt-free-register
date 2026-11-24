import {afterEach,describe,expect,it,vi} from 'vitest';
import {BulkMutationPendingError,parseBulkMutationJson,projectBulkMutation,submitBulkMutation} from './bulkMutations';

afterEach(()=>vi.useRealTimers());
describe('durable bulk mutation receipts',()=>{
 it.each(['stopped','deactivated','unsupported','attention_required'])('recognizes durable %s as terminal without polling forever',async status=>{
  vi.useFakeTimers();
  const send=vi.fn().mockResolvedValueOnce({accepted:true,command_id:'103'}).mockResolvedValueOnce({status,items:[],next_offset:null});
  const action=submitBulkMutation(send,'/api/accounts/archive-bulk',{}, {timeoutMs:10}).catch(error=>error);
  await vi.advanceTimersByTimeAsync(10);
  expect(await action).toMatchObject({status,accepted:false,items:[]});
  expect(send).toHaveBeenCalledTimes(2);
 });
 it('collects all final receipt pages before acknowledging selected items',async()=>{
  const send=vi.fn().mockResolvedValueOnce({accepted:true,command_id:'100'})
   .mockResolvedValueOnce({status:'success',items:[{key:'7',status:'updated'}],next_offset:1})
   .mockResolvedValueOnce({status:'success',items:[{key:'11',status:'updated'}],next_offset:null});
  const result=projectBulkMutation(await submitBulkMutation(send,'/api/accounts/delete-bulk',{}),'accounts','delete');
  expect(result.deleted).toEqual([{id:'7'},{id:'11'}]);
  expect(send.mock.calls[2]![0]).toBe('/api/bulk-mutations/100?offset=1&limit=500');
 });
 it('never treats a terminal response without item receipts as completed',async()=>{
  const send=vi.fn().mockResolvedValueOnce({accepted:true,command_id:'101'}).mockResolvedValueOnce({status:'success',updated_count:10});
  await expect(submitBulkMutation(send,'/api/accounts/archive-bulk',{})).rejects.toBeInstanceOf(BulkMutationPendingError);
 });
 it('does not continue pagination if a timed-out read resolves late',async()=>{
  vi.useFakeTimers();let resolve!:(value:unknown)=>void;
  const send=vi.fn().mockResolvedValueOnce({accepted:true,command_id:'102'}).mockImplementation(()=>new Promise(ok=>{resolve=ok;}));
  const action=submitBulkMutation(send,'/api/accounts/archive-bulk',{}, {timeoutMs:10});
  const settled=action.catch(error=>error);await vi.advanceTimersByTimeAsync(10);expect(await settled).toBeInstanceOf(BulkMutationPendingError);
  resolve({status:'success',items:[],next_offset:1});await vi.advanceTimersByTimeAsync(1);
  expect(send).toHaveBeenCalledTimes(2);
 });
 it('waits past accepted and running responses and projects only confirmed successes',async()=>{
  vi.useFakeTimers();
  const send=vi.fn().mockResolvedValueOnce({ok:true,accepted:true,command_id:'9007199254740993',task_id:'9007199254740995',run_id:'9007199254740997'})
   .mockResolvedValueOnce({ok:true,command_id:'9007199254740993',status:'running',items:[{key:'7',status:'updated'}]})
   .mockResolvedValueOnce({ok:true,command_id:'9007199254740993',operation:'account_delete',status:'partial_success',updated_count:1,failed_count:1,items:[{key:'7',status:'updated',data:{id:'7'}},{key:'11',status:'failed',reason:'busy'}]});
  let settled=false;const action=submitBulkMutation(send,'/api/accounts/delete-bulk',{account_ids:[7,11]},{pollIntervalMs:10}).then(result=>{settled=true;return result;});
  await vi.advanceTimersByTimeAsync(0);expect(settled).toBe(false);
  await vi.advanceTimersByTimeAsync(10);
  const result=projectBulkMutation(await action,'accounts','delete');
  expect(result).toMatchObject({deleted:[{id:'7'}],deleted_count:1,skipped:[{id:'11',reason:'busy'}]});
  expect(send.mock.calls.map(call=>call[0])).toEqual(['/api/accounts/delete-bulk','/api/bulk-mutations/9007199254740993','/api/bulk-mutations/9007199254740993']);
 });
 it('bounds waiting, preserves accepted identity, and never resubmits a pending command',async()=>{
  vi.useFakeTimers();const send=vi.fn().mockResolvedValueOnce({accepted:true,command_id:'88'}).mockImplementation(()=>new Promise(()=>{}));
  const action=submitBulkMutation(send,'/api/outlook/delete-bulk',{}, {timeoutMs:20});
  const rejected=expect(action).rejects.toMatchObject({name:'BulkMutationPendingError',commandId:'88',message:expect.stringMatching(/已受理.*88/)});
  await vi.advanceTimersByTimeAsync(20);await rejected;
  expect(send.mock.calls.filter(call=>call[1]?.method==='POST')).toHaveLength(1);
  expect(send.mock.calls[1]![1]?.signal?.aborted).toBe(true);
 });
 it('aborts polling without losing the accepted command reference',async()=>{
  const controller=new AbortController(),send=vi.fn().mockResolvedValueOnce({accepted:true,command_id:'89'}).mockImplementation(()=>new Promise(()=>{}));
  const action=submitBulkMutation(send,'/api/codex/delete-bulk',{}, {signal:controller.signal});
  await Promise.resolve();controller.abort();await expect(action).rejects.toBeInstanceOf(BulkMutationPendingError);
  expect(send).toHaveBeenCalledTimes(2);
 });
 it('keeps query failures actionable as accepted commands instead of suggesting a new POST',async()=>{
  const send=vi.fn().mockResolvedValueOnce({accepted:true,command_id:'90'}).mockRejectedValueOnce(new Error('offline'));
  await expect(submitBulkMutation(send,'/api/codex/delete-bulk',{})).rejects.toMatchObject({commandId:'90',message:expect.stringContaining('已受理')});
 });
 it('allocates each intent a fresh key and accepts an explicit key for the same retry',async()=>{
  const send=vi.fn().mockResolvedValue({ok:true,updated_count:0});
  await submitBulkMutation(send,'/one',{});await submitBulkMutation(send,'/one',{});
  await submitBulkMutation(send,'/one',{}, {idempotencyKey:'same-intent'});await submitBulkMutation(send,'/one',{}, {idempotencyKey:'same-intent'});
  const keys=send.mock.calls.map(call=>(call[1]?.headers as Record<string,string>)['Idempotency-Key']);
  expect(keys[0]).not.toBe(keys[1]);expect(keys.slice(2)).toEqual(['same-intent','same-intent']);
 });
 it('decodes bigint command, task, run, and target identities without rounding',()=>{
  expect(parseBulkMutationJson('{"command_id":9007199254740993,"task_id":9007199254740995,"run_id":9007199254740997,"items":[{"key":9007199254740999,"data":{"id":9007199254741001}}]}'))
   .toMatchObject({command_id:'9007199254740993',task_id:'9007199254740995',run_id:'9007199254740997',items:[{key:'9007199254740999',data:{id:'9007199254741001'}}]});
 });
 it('projects email source identity and failure reasons from terminal receipts',()=>{
  const result=projectBulkMutation({ok:true,status:'failed',items:[{key:'outlook:a@test',status:'updated',data:{source:'outlook',email:'a@test',sync:{lease_retained:true}}},{key:'email_butler:b@test',status:'skipped',reason_code:'protected',reason:'注册成功'}]},'email','delete');
  expect(result).toMatchObject({deleted_count:1,deleted:[{source:'outlook',email:'a@test',sync:{lease_retained:true}}],skipped:[{source:'email_butler',email:'b@test',reason:'注册成功',reason_code:'protected'}]});
 });
});
