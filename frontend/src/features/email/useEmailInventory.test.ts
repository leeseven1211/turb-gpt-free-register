import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {useEmailInventory} from './useEmailInventory';
import {useEmailHistory} from './useEmailHistory';
import {deferred,fixture} from './testSupport';
import type {InventoryResponse} from './contracts';
const cleanups:(()=>void)[]=[];
beforeEach(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});});
afterEach(()=>{cleanups.splice(0).forEach(fn=>fn());vi.useRealTimers();});
describe('email read scope and frozen actions',()=>{
 it('retains skipped selections after an asynchronously completed status command',async()=>{
  const f=fixture();f.handlers.set('/api/outlook/status-bulk',()=>({ok:true,accepted:true,command_id:'94'}));
  f.handlers.set('/api/bulk-mutations/94',()=>({ok:true,status:'partial_success',items:[{key:'outlook:a@test',status:'updated'},{key:'outlook:b@test',status:'skipped',reason:'protected'}]}));
  const owner=useEmailInventory(f.api,f.deps);cleanups.push(owner.dispose);
  owner.toggle({source:'outlook',email:'a@test'},true);owner.toggle({source:'outlook',email:'b@test'},true);
  await owner.bulkStatus('disabled');
  expect([...owner.state.selected.values()]).toEqual([{source:'outlook',email:'b@test'}]);
  expect(owner.state.receipt?.detail).toContain('protected');
 });
 it('shows accepted status rather than mutation failure if result lookup is unavailable',async()=>{
  const f=fixture();f.handlers.set('/api/outlook/delete-bulk',()=>({ok:true,accepted:true,command_id:'95'}));
  f.handlers.set('/api/bulk-mutations/95',()=>{throw new Error('offline');});
  const owner=useEmailInventory(f.api,f.deps);cleanups.push(owner.dispose);owner.toggle({source:'outlook',email:'a@test'},true);
  await owner.bulkDelete();expect(owner.state.selected.size).toBe(1);
  expect(owner.state.receipt?.tone).toBe('warning');expect(owner.state.receipt?.detail).toContain('95');
  expect(f.deps.notify).not.toHaveBeenCalledWith(expect.stringContaining('操作失败'));
 });
 it('ignores an older response immediately during debounce and aborts hidden reads',async()=>{
  vi.useFakeTimers();const f=fixture(),one=deferred<InventoryResponse>(),two=deferred<InventoryResponse>();let n=0;
  f.handlers.set('/api/outlook',()=>++n===1?one.promise:two.promise);
  const owner=useEmailInventory(f.api,f.deps);cleanups.push(owner.dispose);owner.setActive(true);
  owner.updateFilters({q:'new'});one.resolve({items:[{email:'stale@example.test',source:'outlook'}],total:1});await Promise.resolve();await Promise.resolve();
  expect(owner.state.items).toEqual([]);await vi.advanceTimersByTimeAsync(250);
  const read=f.calls.filter(c=>c.path.startsWith('/api/outlook?')).at(-1)!;owner.setActive(false);
  expect(read.options.signal?.aborted).toBe(true);two.resolve({items:[{email:'hidden@example.test',source:'outlook'}],total:1});await Promise.resolve();await Promise.resolve();
  expect(owner.state.items).toEqual([]);
 });
 it('sends all cross-page identities frozen before confirmation and retains skipped/new selections',async()=>{
  const f=fixture(),confirmation=deferred<boolean>(),write=deferred<unknown>();f.deps.confirm=()=>confirmation.promise;
  f.handlers.set('/api/outlook/delete-bulk',()=>write.promise);
  const owner=useEmailInventory(f.api,f.deps);cleanups.push(owner.dispose);
  owner.toggle({source:'outlook',email:'first@example.test'},true);owner.toggle({source:'email_butler',email:'second@example.test'},true);
  const action=owner.bulkDelete();owner.state.filters.source='generic_api';owner.toggle({source:'generic_api',email:'later@example.test'},true);confirmation.resolve(true);await Promise.resolve();await Promise.resolve();
  const call=f.calls.find(c=>c.path==='/api/outlook/delete-bulk')!;
  expect(JSON.parse(String(call.options.body))).toEqual({items:[{source:'outlook',email:'first@example.test'},{source:'email_butler',email:'second@example.test'}],source:'all'});
  owner.setActive(false);write.resolve({deleted_count:1,deleted:[{source:'outlook',email:'first@example.test',sync:{lease_retained:true}}],skipped:[{source:'email_butler',email:'second@example.test',reason:'注册成功'}]});await action;
  expect(owner.state.selected.size).toBe(2);expect(owner.state.receipt?.detail).toContain('注册成功');expect(owner.state.receipt?.detail).toContain('保留原租约');expect(f.deps.onNavigate).not.toHaveBeenCalled();
 });
 it('freezes current page copying and never sends a secret read for selected other pages',async()=>{
  const f=fixture();f.handlers.set('/api/outlook/secret-bulk',()=>({values:[{value:'one-line'}]}));
  const owner=useEmailInventory(f.api,f.deps);cleanups.push(owner.dispose);owner.state.items=[{source:'outlook',email:'page@example.test'}];owner.toggle({source:'email_butler',email:'selected@example.test'},true);
  await owner.copyPage();expect(JSON.parse(String(f.calls[0]!.options.body)).items).toEqual([{source:'outlook',email:'page@example.test'}]);expect(f.deps.clipboard).toHaveBeenCalledWith('one-line');
 });
 it('history is readonly and preserves selected full addresses across pages',async()=>{
  const f=fixture(),owner=useEmailHistory(f.api,f.deps);cleanups.push(owner.dispose);
  owner.state.items=[{id:1,source:'outlook',email:'child@example.test',state:'reserved'}];owner.togglePage(true);owner.state.items=[{id:2,source:'outlook',email:'other@example.test'}];await owner.copy();
  expect(f.deps.clipboard).toHaveBeenCalledWith('child@example.test');
  owner.scopeParent({source:'outlook',id:9,email:'mother@example.test'});expect(owner.state.filters.parent_id).toBe('9');owner.updateFilters({source:'icloud_hide'});expect(owner.state.filters.parent_id).toBe('');expect(owner.state.selected.size).toBe(0);
  expect(f.calls.every(c=>!c.path.includes('/generate')&&!c.path.includes('/status-bulk'))).toBe(true);
 });
 it('keeps inventory and a distinct summary failure when parent-history reading fails',async()=>{
  const f=fixture();f.handlers.set('/api/outlook',()=>({items:[{email:'kept@example.test',source:'outlook'}],total:1}));f.handlers.set('/api/email-derivation/summary',()=>{throw new Error('summary offline');});
  const owner=useEmailInventory(f.api,f.deps);cleanups.push(owner.dispose);owner.setActive(true);await owner.refresh();
  expect(owner.state.items[0]?.email).toBe('kept@example.test');expect(owner.state.summaryError).toContain('summary offline');expect(owner.state.error).toBe('');
 });
 it('never reports a successful copy when any clipboard operation rejects',async()=>{
  const f=fixture();f.deps.clipboard=async()=>{throw new Error('clipboard denied');};f.handlers.set('/api/outlook/secret',()=>({value:'secret'}));f.handlers.set('/api/outlook/secret-bulk',()=>({values:[{value:'secret'}]}));
  const owner=useEmailInventory(f.api,f.deps),history=useEmailHistory(f.api,f.deps);cleanups.push(owner.dispose,history.dispose);
  const row={source:'outlook',email:'copy@example.test'};owner.state.items=[row];await owner.copyRow(row);expect(owner.state.receipt?.tone).toBe('danger');await owner.copyPage();expect(owner.state.receipt?.tone).toBe('danger');
  history.state.items=[{...row,id:1}];await history.copy();expect(history.state.receipt?.label).toBe('复制失败');expect(f.deps.notify).not.toHaveBeenCalledWith('已复制');expect(f.deps.notify).not.toHaveBeenCalledWith('已复制当前页邮箱素材');
 });
 it('preserves all history query fields, parent source and selected ownership snapshots',async()=>{
  const f=fixture(),owner=useEmailHistory(f.api,f.deps);cleanups.push(owner.dispose);
  owner.scopeParent({source:'outlook',id:9,email:'mother@example.test'});owner.updateFilters({q:'child',parent_q:'mother',state:'reserved',related_q:'17',created_from:'2026-11-01',created_to:'2026-11-16'});owner.setActive(true);await owner.refresh();
  const query=new URL(f.calls.at(-1)!.path,'http://fixture').searchParams;expect(Object.fromEntries(query)).toMatchObject({source:'outlook',parent_id:'9',q:'child',parent_q:'mother',state:'reserved',related_q:'17',created_from:'2026-11-01',created_to:'2026-11-16',page:'1',page_size:'50'});
 });
 it('retains data on read failure and bounds zero-total/out-of-range pagination',async()=>{
  const f=fixture();let fail=false;f.handlers.set('/api/outlook',()=>{if(fail)throw new Error('offline');return{items:[{source:'outlook',email:'keep@example.test'}],total:1};});
  const owner=useEmailInventory(f.api,f.deps);cleanups.push(owner.dispose);owner.setActive(true);await owner.refresh();fail=true;await owner.refresh();expect(owner.state.items).toHaveLength(1);expect(owner.state.error).toContain('offline');
  fail=false;f.handlers.set('/api/outlook',()=>({items:[],total:0}));owner.state.page=9;await owner.refresh();expect(owner.state.page).toBe(1);expect(owner.state.items).toEqual([]);
 });
 it('does not dispatch canceled delete confirmations and preserves per-row backend reasons',async()=>{
  const f=fixture();f.deps.confirm=()=>false;const owner=useEmailInventory(f.api,f.deps);cleanups.push(owner.dispose);const row={source:'outlook',email:'protected@example.test'};owner.toggle(row,true);await owner.bulkDelete();await owner.rowAction(row,'delete');expect(f.calls).toHaveLength(0);
  f.deps.confirm=()=>true;f.handlers.set('/api/outlook/delete',()=>({deleted:false,reason:'邮箱已确认注册成功，不能删除'}));await owner.rowAction(row,'delete');expect(owner.state.receipt?.detail).toContain('已确认注册成功');expect(owner.state.selected.size).toBe(1);
  f.handlers.set('/api/outlook/delete',()=>({deleted:true,sync:{message:'本地已移除，活跃注册已延后退租'}}));await owner.rowAction(row,'delete');expect(owner.state.receipt?.detail).toContain('延后退租');
 });
 it('shows single-delete retained-lease receipts without replacing them with refresh errors',async()=>{
  const f=fixture();f.handlers.set('/api/outlook/delete',()=>({deleted:true,sync:{message:'本地已移除，保留原租约'}}));f.deps.onInventoryChanged=async()=>{throw new Error('display offline');};
  const owner=useEmailInventory(f.api,f.deps);cleanups.push(owner.dispose);await owner.rowAction({source:'email_butler',email:'retained@example.test'},'delete');expect(owner.state.receipt?.detail).toContain('保留原租约');expect(owner.state.receipt?.detail).toContain('显示刷新失败');
 });
 it('preserves history rows on failure and rejects an older query after filters change',async()=>{
  const f=fixture(),old=deferred<{items:never[];total:number}>();let mode='good';f.handlers.set('/api/email-derivation/allocations',()=>{if(mode==='fail')throw new Error('history offline');if(mode==='pending')return old.promise;return{items:[{id:1,source:'outlook',email:'kept-history@example.test'}],total:101};});
  const owner=useEmailHistory(f.api,f.deps);cleanups.push(owner.dispose);owner.setActive(true);await owner.refresh();mode='fail';await owner.refresh();expect(owner.state.items[0]?.email).toBe('kept-history@example.test');expect(owner.state.error).toContain('history offline');
  mode='pending';const reading=owner.refresh();owner.updateFilters({state:'reserved'});mode='good';await owner.refresh();old.resolve({items:[],total:0});await reading;expect(owner.state.items[0]?.email).toBe('kept-history@example.test');
  owner.setPage(2);await owner.refresh();owner.setSize(20);await owner.refresh();const params=new URL(f.calls.at(-1)!.path,'http://fixture').searchParams;expect(params.get('page')).toBe('1');expect(params.get('page_size')).toBe('20');
  f.handlers.set('/api/email-derivation/allocations',()=>({items:[],total:0}));owner.state.page=99;await owner.refresh();expect(owner.state.page).toBe(1);
 });
 it('aborts secret reads when hidden and never copies late secret values',async()=>{
  const f=fixture(),read=deferred<{value:string}>();f.handlers.set('/api/outlook/secret',()=>read.promise);const owner=useEmailInventory(f.api,f.deps);cleanups.push(owner.dispose);owner.setActive(true);const action=owner.copyRow({source:'outlook',email:'late@example.test'});owner.setActive(false);
  expect(f.calls.find(call=>call.path.startsWith('/api/outlook/secret?'))?.options.signal?.aborted).toBe(true);read.resolve({value:'late secret'});await action;expect(f.deps.clipboard).not.toHaveBeenCalled();
 });
});
