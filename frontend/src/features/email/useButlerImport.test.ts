import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {useButlerImport,BUTLER_IMPORT_STORAGE_KEY} from './useButlerImport';
import {ApiError} from '../../api/client';
import {deferred,fixture} from './testSupport';
const cleanups:(()=>void)[]=[];
beforeEach(()=>{localStorage.clear();Object.defineProperty(document,'hidden',{configurable:true,value:false});});
afterEach(()=>{cleanups.splice(0).forEach(fn=>fn());vi.useRealTimers();localStorage.clear();});
describe('Butler original intent and lifecycle',()=>{
 it('persists before sending and retries the same original request after unknown response',async()=>{
  const f=fixture();f.handlers.set('/api/email-butler/import-preview',()=>({preview_token:'token',available:300,selected:201}));
  const post=vi.fn(()=>{expect(JSON.parse(localStorage.getItem(BUTLER_IMPORT_STORAGE_KEY)!)).toMatchObject({request_id:'fixed',preview_token:'token'});throw new Error('断开');});f.handlers.set('/api/email-butler/imports',post);
  const owner=useButlerImport(f.api,f.deps,{storage:localStorage,uuid:()=> 'fixed'});cleanups.push(owner.dispose);owner.setActive(true);owner.state.filters.count=201;await owner.open();await owner.apply();
  expect(owner.state.request?.request_id).toBe('fixed');owner.close();await owner.open();await owner.retry();
  expect(post).toHaveBeenCalledTimes(2);expect(f.calls.filter(c=>c.path==='/api/email-butler/imports').map(c=>JSON.parse(String(c.options.body)))).toEqual([{request_id:'fixed',preview_token:'token'},{request_id:'fixed',preview_token:'token'}]);
 });
 it('refuses a new claim when storage is unavailable',async()=>{
  const f=fixture(),storage={getItem:()=>null,setItem:()=>{throw new Error('blocked');},removeItem:()=>{}};
  f.handlers.set('/api/email-butler/import-preview',()=>({preview_token:'token',selected:1}));
  const owner=useButlerImport(f.api,f.deps,{storage,uuid:()=> 'fixed'});cleanups.push(owner.dispose);owner.setActive(true);await owner.open();await owner.apply();
  expect(f.calls.some(c=>c.path==='/api/email-butler/imports')).toBe(false);expect(owner.state.error).toContain('保存');
 });
 it('restores only by GET, stops hidden polling and never revives cancellation from a late read',async()=>{
  vi.useFakeTimers();localStorage.setItem(BUTLER_IMPORT_STORAGE_KEY,JSON.stringify({request_id:'original',preview_token:'token',batch_id:'batch',batch_status:'running',filters:{provider:'auto',count:10}}));
  const f=fixture(),read=deferred<unknown>();f.handlers.set('/api/email-butler/imports/batch',()=>read.promise);f.handlers.set('/api/email-butler/imports/batch/cancel',()=>({batch:{batch_id:'batch',status:'cancelled',can_retry:false,can_cancel:false,imported:1,total:10}}));
  const owner=useButlerImport(f.api,f.deps,{storage:localStorage});cleanups.push(owner.dispose);owner.setActive(true);await owner.cancel();read.resolve({batch:{batch_id:'batch',status:'running',can_retry:true,total:10}});await Promise.resolve();await Promise.resolve();
  expect(owner.state.batch?.status).toBe('cancelled');owner.setActive(false);const count=f.calls.length;await vi.advanceTimersByTimeAsync(10000);expect(f.calls).toHaveLength(count);expect(f.calls.some(c=>c.path==='/api/email-butler/imports')).toBe(false);
 });
 it('handles public partial success with internal unknown evidence and safe reset guards',async()=>{
  localStorage.setItem(BUTLER_IMPORT_STORAGE_KEY,JSON.stringify({request_id:'original',preview_token:'token',batch_id:'batch',batch_status:'running'}));
  const f=fixture();f.handlers.set('/api/email-butler/imports/batch',()=>({batch:{batch_id:'batch',status:'partial_success',internal_status:'partial',internal_unknown_count:2,imported:1,failed:2,unknown:0,total:3,can_retry:true}}));
  const owner=useButlerImport(f.api,f.deps,{storage:localStorage});cleanups.push(owner.dispose);owner.setActive(true);await owner.poll();
  expect(owner.canReset.value).toBe(false);expect(owner.batchTitle.value).toContain('部分');expect(owner.batchDetails.value).toContain('2');expect(owner.batchDetails.value).toContain('原请求');expect(f.deps.onNavigate).not.toHaveBeenCalled();
 });
 it('invalidates an old preview as soon as the filters change',async()=>{
  const f=fixture(),old=deferred<unknown>();f.handlers.set('/api/email-butler/import-preview',()=>old.promise);
  const owner=useButlerImport(f.api,f.deps,{storage:localStorage});cleanups.push(owner.dispose);owner.setActive(true);const opening=owner.open();await Promise.resolve();await Promise.resolve();owner.changeFilters({count:10000});old.resolve({preview_token:'old',selected:10});await opening;await owner.apply();
  expect(owner.state.preview).toBeNull();expect(f.calls.some(c=>c.path==='/api/email-butler/imports')).toBe(false);
 });
 it('opens with a readonly quantity preview and whitelists only valid positive diagnostics',async()=>{
  const f=fixture();f.handlers.set('/api/email-butler/import-preview',()=>({preview_token:'preview',selected:0,available:0,resource_total:57,availability_buckets:{history_blocked:57,cooldown:-1,source_unavailable:1.5,active_same_service:0,other_service_exclusive:2,private_key:999},private_text:'never display'}));
  const owner=useButlerImport(f.api,f.deps,{storage:localStorage});cleanups.push(owner.dispose);owner.setActive(true);await owner.open();
  expect(f.calls.map(c=>c.path)).toEqual(['/api/email-butler/import-options','/api/email-butler/import-preview']);expect(owner.availability.value).toContain('历史占用限制 57 个');expect(owner.availability.value).toContain('其他服务占用 2 个');expect(owner.availability.value).not.toContain('-1');expect(owner.availability.value).not.toContain('1.5');expect(owner.availability.value).not.toContain('999');expect(owner.availability.value).toContain('未租用”不等于');expect(owner.state.error).toContain('当前没有可用于 OpenAI');
 });
 it('accepts the old preview shape without inventing diagnostic counts and preserves all five providers',async()=>{
  const f=fixture();f.handlers.set('/api/email-butler/import-preview',()=>({preview_token:'preview',selected:1,available:1}));
  const owner=useButlerImport(f.api,f.deps,{storage:localStorage});cleanups.push(owner.dispose);owner.setActive(true);await owner.open();
  expect(owner.state.providers.map(row=>row.value)).toEqual(['icloud_hme','outlook_graph','cloudflare','mailcom','auto']);expect(owner.availability.value).toContain('当前可用 1 个');expect(owner.availability.value).not.toContain('历史占用限制');expect(owner.availability.value).not.toContain('当前查询范围');
 });
 it('validates provider and positive safe integer count without remote preview calls',async()=>{
  const f=fixture(),owner=useButlerImport(f.api,f.deps,{storage:localStorage});cleanups.push(owner.dispose);owner.setActive(true);owner.state.open=true;
  for(const count of [0,-1,1.5,NaN,Infinity,Number.MAX_SAFE_INTEGER+1]){owner.changeFilters({count});await owner.preview();expect(owner.state.error).toContain('整数');}
  owner.changeFilters({provider:'unsupported',count:1});await owner.preview();expect(owner.state.error).toContain('来源');expect(f.calls).toHaveLength(0);
 });
 it('submits 10000 with only provider/count, never adds retired filters or a new request on duplicate clicks',async()=>{
  const f=fixture(),write=deferred<unknown>();f.handlers.set('/api/email-butler/import-preview',()=>({preview_token:'preview',selected:10000,available:10000}));f.handlers.set('/api/email-butler/imports',()=>write.promise);
  const owner=useButlerImport(f.api,f.deps,{storage:localStorage,uuid:()=> 'original'});cleanups.push(owner.dispose);owner.setActive(true);owner.state.filters={provider:'auto',count:10000};await owner.open();
  const submit=owner.apply();await owner.apply();await owner.retry();expect(f.calls.filter(c=>c.path==='/api/email-butler/imports')).toHaveLength(1);expect(JSON.parse(String(f.calls.find(c=>c.path==='/api/email-butler/import-preview')!.options.body))).toEqual({provider:'auto',count:10000});
  write.resolve({batch:{batch_id:'batch',status:'running',total:10000,imported:0,can_retry:true}});await submit;owner.close();expect(owner.state.batch?.batch_id).toBe('batch');
 });
 it('persists a same-revision retry marker through reload and polls original batch until it changes',async()=>{
  vi.useFakeTimers();localStorage.setItem(BUTLER_IMPORT_STORAGE_KEY,JSON.stringify({request_id:'original',preview_token:'preview',batch_id:'batch',batch_status:'partial',filters:{provider:'auto',count:3}}));
  const f=fixture(),partial={batch_id:'batch',status:'partial',total:3,imported:1,pending:2,can_retry:true,updated_at:'first'};let reads=0;
  f.handlers.set('/api/email-butler/imports/batch',()=>({batch:++reads<3?partial:{...partial,status:'running',updated_at:'next'}}));f.handlers.set('/api/email-butler/imports/batch/retry',()=>({batch:partial}));
  const owner=useButlerImport(f.api,f.deps,{storage:localStorage});cleanups.push(owner.dispose);owner.setActive(true);await owner.poll();await owner.retry();expect(owner.state.resumePending).toBeTruthy();expect(JSON.parse(localStorage.getItem(BUTLER_IMPORT_STORAGE_KEY)!).resume_revision).toBeTruthy();owner.dispose();
  const restored=useButlerImport(f.api,f.deps,{storage:localStorage});cleanups.push(restored.dispose);restored.setActive(true);await restored.poll();expect(restored.state.resumePending).toBeTruthy();await vi.advanceTimersByTimeAsync(2000);expect(restored.state.batch?.status).toBe('running');expect(restored.state.resumePending).toBeNull();expect(f.calls.filter(c=>c.path==='/api/email-butler/imports')).toHaveLength(0);
 });
 it('throttles inventory refresh while polling continues and flushes final imported count',async()=>{
  vi.useFakeTimers();localStorage.setItem(BUTLER_IMPORT_STORAGE_KEY,JSON.stringify({request_id:'original',preview_token:'preview',batch_id:'batch',batch_status:'running'}));
  const f=fixture(),slow=deferred<void>();let imported=1,finished=false;f.deps.onInventoryChanged=vi.fn(()=>slow.promise);f.handlers.set('/api/email-butler/imports/batch',()=>({batch:{batch_id:'batch',status:finished?'completed':'running',imported,total:5,can_retry:!finished}}));
  const owner=useButlerImport(f.api,f.deps,{storage:localStorage});cleanups.push(owner.dispose);owner.setActive(true);await owner.poll();expect(f.deps.onInventoryChanged).toHaveBeenCalledTimes(1);
  imported=2;await vi.advanceTimersByTimeAsync(2000);expect(owner.state.batch?.imported).toBe(2);expect(f.deps.onInventoryChanged).toHaveBeenCalledTimes(1);
  slow.resolve();await Promise.resolve();await Promise.resolve();await vi.advanceTimersByTimeAsync(2000);expect(f.deps.onInventoryChanged).toHaveBeenCalledTimes(1);
  imported=5;finished=true;await vi.advanceTimersByTimeAsync(2000);await Promise.resolve();expect(owner.state.batch?.status).toBe('completed');expect(f.deps.onInventoryChanged).toHaveBeenCalledTimes(2);
 });
 it('retains an accepted completed result when inventory refresh fails and does not claim again',async()=>{
  localStorage.setItem(BUTLER_IMPORT_STORAGE_KEY,JSON.stringify({request_id:'original',preview_token:'preview',batch_id:'batch',batch_status:'completed'}));
  const f=fixture();f.deps.onInventoryChanged=async()=>{throw new Error('display offline');};f.handlers.set('/api/email-butler/imports/batch',()=>({batch:{batch_id:'batch',status:'completed',imported:2,total:2,can_retry:false}}));
  const owner=useButlerImport(f.api,f.deps,{storage:localStorage});cleanups.push(owner.dispose);owner.setActive(true);await owner.poll();await Promise.resolve();await Promise.resolve();
  expect(owner.state.batch?.status).toBe('completed');expect(owner.state.error).toContain('显示未完全刷新');expect(owner.canReset.value).toBe(true);expect(f.calls.some(c=>c.path==='/api/email-butler/imports')).toBe(false);
 });
 it('clears only definitely uncreated invalid previews and preserves conflicting original requests',async()=>{
  const f=fixture();f.handlers.set('/api/email-butler/import-preview',()=>({preview_token:'preview',selected:1}));f.handlers.set('/api/email-butler/imports',()=>{throw new ApiError('预览已过期',400,'import_preview_expired');});
  const owner=useButlerImport(f.api,f.deps,{storage:localStorage,uuid:()=> 'original'});cleanups.push(owner.dispose);owner.setActive(true);await owner.open();await owner.apply();expect(owner.state.request).toBeNull();expect(localStorage.getItem(BUTLER_IMPORT_STORAGE_KEY)).toBeNull();
  await owner.preview();f.handlers.set('/api/email-butler/imports',()=>{throw new ApiError('原请求冲突',409,'import_request_conflict');});await owner.apply();expect(owner.state.request?.request_id).toBe('original');expect(owner.state.error).toContain('原请求冲突');
 });
 it('preserves explicit rejection reason and original identity for create and cancel failures',async()=>{
  localStorage.setItem(BUTLER_IMPORT_STORAGE_KEY,JSON.stringify({request_id:'original',preview_token:'preview'}));
  const f=fixture();f.handlers.set('/api/email-butler/imports',()=>{throw new ApiError('当前 Key 缺少授权',403,'permission_denied');});
  const owner=useButlerImport(f.api,f.deps,{storage:localStorage});cleanups.push(owner.dispose);owner.setActive(true);await owner.retry();expect(owner.state.error).toContain('当前 Key 缺少授权');expect(owner.state.request?.request_id).toBe('original');
  owner.state.batch={batch_id:'batch',status:'partial',can_retry:true,can_cancel:true};f.handlers.set('/api/email-butler/imports/batch/cancel',()=>{throw new ApiError('不能终止原租约',403,'permission_denied');});await owner.cancel();expect(owner.state.error).toContain('不能终止原租约');expect(owner.state.batch.status).toBe('partial');expect(owner.canRetry.value).toBe(true);
 });
 it('prevents duplicate cancellation and ignores the previous poll after cancellation/reset',async()=>{
  localStorage.setItem(BUTLER_IMPORT_STORAGE_KEY,JSON.stringify({request_id:'original',preview_token:'preview',batch_id:'batch',batch_status:'running'}));
  const f=fixture(),read=deferred<unknown>(),cancel=deferred<unknown>();f.handlers.set('/api/email-butler/imports/batch',()=>read.promise);f.handlers.set('/api/email-butler/imports/batch/cancel',()=>cancel.promise);f.handlers.set('/api/email-butler/import-preview',()=>({preview_token:'new-preview',selected:1}));
  const owner=useButlerImport(f.api,f.deps,{storage:localStorage});cleanups.push(owner.dispose);owner.setActive(true);owner.state.open=true;const cancelling=owner.cancel();await owner.cancel();expect(f.calls.filter(c=>c.path.endsWith('/cancel'))).toHaveLength(1);
  cancel.resolve({batch:{batch_id:'batch',status:'cancelled',can_cancel:false,can_retry:false}});await cancelling;await owner.reset();read.resolve({batch:{batch_id:'batch',status:'running'}});await Promise.resolve();await Promise.resolve();expect(owner.state.batch).toBeNull();expect(owner.state.request).toBeNull();expect(owner.state.preview?.preview_token).toBe('new-preview');
 });
 it('honors cross-tab cancellation and stored terminal cancellation against older reads',async()=>{
  localStorage.setItem(BUTLER_IMPORT_STORAGE_KEY,JSON.stringify({request_id:'original',preview_token:'preview',batch_id:'batch',batch_status:'running'}));const f=fixture(),read=deferred<unknown>();f.handlers.set('/api/email-butler/imports/batch',()=>read.promise);
  const owner=useButlerImport(f.api,f.deps,{storage:localStorage});cleanups.push(owner.dispose);owner.setActive(true);const saved=JSON.stringify({request_id:'original',preview_token:'preview',batch_id:'batch',batch_status:'cancelled'});localStorage.setItem(BUTLER_IMPORT_STORAGE_KEY,saved);window.dispatchEvent(new StorageEvent('storage',{key:BUTLER_IMPORT_STORAGE_KEY,newValue:saved}));read.resolve({batch:{batch_id:'batch',status:'running',can_retry:true}});await Promise.resolve();await Promise.resolve();expect(owner.state.batch?.status).toBe('cancelled');expect(owner.canRetry.value).toBe(false);
 });
 it('disallows replacing original unknown results but allows fresh import after known terminal failure',async()=>{
  const f=fixture(),owner=useButlerImport(f.api,f.deps,{storage:localStorage});cleanups.push(owner.dispose);
  owner.state.batch={batch_id:'batch',status:'failed',can_retry:false,unknown:1};expect(owner.canReset.value).toBe(false);
  owner.state.batch={batch_id:'batch',status:'failed',can_retry:false,unknown:0};expect(owner.canReset.value).toBe(true);
 });
 it('debounces only the final filters and never resurrects a preview after closing',async()=>{
  vi.useFakeTimers();const f=fixture();f.handlers.set('/api/email-butler/import-preview',()=>({preview_token:'preview',available:5,selected:5}));
  const owner=useButlerImport(f.api,f.deps,{storage:localStorage});cleanups.push(owner.dispose);owner.setActive(true);await owner.open();f.calls.length=0;owner.changeFilters({count:2});owner.changeFilters({provider:'cloudflare',count:5});expect(owner.state.preview).toBeNull();await vi.advanceTimersByTimeAsync(400);
  expect(f.calls).toHaveLength(1);expect(JSON.parse(String(f.calls[0]!.options.body))).toEqual({provider:'cloudflare',count:5});
  owner.changeFilters({count:6});owner.close();await vi.advanceTimersByTimeAsync(400);expect(f.calls).toHaveLength(1);
 });
 it('closes running work without cancel and reopens the same batch for a partial retry',async()=>{
  localStorage.setItem(BUTLER_IMPORT_STORAGE_KEY,JSON.stringify({request_id:'original',preview_token:'preview',batch_id:'batch',batch_status:'running'}));
  const f=fixture();let status='running';f.handlers.set('/api/email-butler/imports/batch',()=>({batch:{batch_id:'batch',status,can_retry:true,imported:1,total:2}}));f.handlers.set('/api/email-butler/imports/batch/retry',()=>({batch:{batch_id:'batch',status:'running',can_retry:true,imported:1,total:2}}));
  const owner=useButlerImport(f.api,f.deps,{storage:localStorage});cleanups.push(owner.dispose);owner.setActive(true);await owner.poll();owner.close();expect(f.calls.some(call=>call.path.endsWith('/cancel'))).toBe(false);status='partial';await owner.open();expect(owner.canRetry.value).toBe(true);await owner.retry();
  const call=f.calls.find(call=>call.path.endsWith('/retry'))!;expect(call.path).toContain('/imports/batch/retry');expect(JSON.parse(String(call.options.body))).toEqual({request_id:'original',preview_token:'preview'});
 });
 it('retains known completed storage state when the restoring GET fails',async()=>{
  localStorage.setItem(BUTLER_IMPORT_STORAGE_KEY,JSON.stringify({request_id:'original',preview_token:'preview',batch_id:'batch',batch_status:'completed'}));
  const f=fixture();f.handlers.set('/api/email-butler/imports/batch',()=>{throw new Error('read offline');});const owner=useButlerImport(f.api,f.deps,{storage:localStorage});cleanups.push(owner.dispose);owner.setActive(true);await owner.poll();
  expect(owner.state.batch?.status).toBe('completed');expect(owner.batchTitle.value).toBe('导入完成');expect(owner.state.error).toContain('读取原批次');expect(owner.canRetry.value).toBe(false);expect(f.calls.every(call=>call.options.method!=='POST')).toBe(true);
 });
});
