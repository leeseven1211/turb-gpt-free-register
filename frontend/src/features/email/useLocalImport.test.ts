import {beforeEach,describe,expect,it} from 'vitest';
import {useLocalImport} from './useLocalImport';
import {ApiError} from '../../api/client';
import {deferred,fixture} from './testSupport';
beforeEach(()=>Object.defineProperty(document,'hidden',{configurable:true,value:false}));
describe('local import preview and receipt',()=>{
 it('submits the exact matching generic expiry payload and retains accepted receipt after hiding',async()=>{
  const f=fixture(),write=deferred<unknown>();f.handlers.set('/api/outlook/import-preview',()=>({new:1,valid:1,total_lines:1}));f.handlers.set('/api/outlook/import',()=>write.promise);
  const owner=useLocalImport(f.api,f.deps);owner.setActive(true);owner.open('generic_api');owner.update({text:'raw====url',expiresAt:'2026-12-01T12:00:00+08:00'});await owner.preview();const submit=owner.submit();owner.setActive(false);write.resolve({inserted:1,parsed:1,accepted_count:1,pending_sync_count:1});await submit;
  const bodies=f.calls.filter(c=>c.path.includes('/outlook/import')).map(c=>JSON.parse(String(c.options.body)));expect(bodies).toEqual([{source:'generic_api',text:'raw====url',expires_at:'2026-12-01T12:00:00+08:00'},{source:'generic_api',text:'raw====url',expires_at:'2026-12-01T12:00:00+08:00'}]);expect(owner.state.receipt?.detail).toContain('已接收 1');expect(owner.state.receipt?.detail).toContain('处理中 1');expect(f.deps.onNavigate).not.toHaveBeenCalled();owner.dispose();
 });
 it('cannot submit an old preview after source/draft changes and does not leak expiry',async()=>{
  const f=fixture(),old=deferred<unknown>();f.handlers.set('/api/outlook/import-preview',()=>old.promise);
  const owner=useLocalImport(f.api,f.deps);owner.setActive(true);owner.open('generic_api');owner.update({text:'old----url',expiresAt:'2026-12-01T12:00:00Z'});const read=owner.preview();owner.update({source:'email_butler',text:'owned@example.test'});old.resolve({new:1});await read;expect(owner.state.preview).toBeNull();
  f.handlers.set('/api/outlook/import-preview',()=>({new:1}));f.handlers.set('/api/outlook/import',()=>({inserted:1}));await owner.submit();
  expect(JSON.parse(String(f.calls.at(-1)!.options.body))).toEqual({source:'email_butler',text:'owned@example.test'});owner.dispose();
 });
 it('separates accepted write from refresh failure and never auto replays a dropped response',async()=>{
  const f=fixture();f.handlers.set('/api/outlook/import-preview',()=>({new:1}));f.handlers.set('/api/outlook/import',()=>{throw new Error('响应丢失');});
  const owner=useLocalImport(f.api,f.deps);owner.setActive(true);owner.open('outlook');owner.update({text:'email----password----client----refresh'});await owner.submit();owner.setActive(false);owner.setActive(true);expect(f.calls.filter(c=>c.path==='/api/outlook/import')).toHaveLength(1);expect(owner.state.receipt?.detail).toContain('响应丢失');expect(owner.state.text).toContain('password');owner.dispose();
 });
 it('keeps all original resource formats and uses only local preview/import endpoints',async()=>{
  for(const [source,text]of [['outlook','user@example.test====password====client====refresh'],['generic_api','user@example.test----https://fixture.test/code'],['email_butler','owned+original@icloud.com']] as const){
   const f=fixture();f.handlers.set('/api/outlook/import-preview',()=>({new:1}));f.handlers.set('/api/outlook/import',()=>({inserted:1}));const owner=useLocalImport(f.api,f.deps);owner.setActive(true);owner.open(source);owner.update({text});await owner.submit();
   expect(f.calls.map(call=>call.path)).toEqual(['/api/outlook/import-preview','/api/outlook/import']);expect(f.calls.map(call=>JSON.parse(String(call.options.body)))).toEqual([{source,text},{source,text}]);owner.dispose();
  }
 });
 it('retains accepted import and open result when shared refresh fails, and blocks empty previews',async()=>{
  const f=fixture();let fresh=0;f.handlers.set('/api/outlook/import-preview',()=>({new:fresh}));f.handlers.set('/api/outlook/import',()=>({accepted_count:1,inserted:1,parsed:1}));f.deps.onInventoryChanged=async()=>{throw new Error('display failed');};
  const owner=useLocalImport(f.api,f.deps);owner.setActive(true);owner.open('outlook');owner.update({text:'fixture----password----client----refresh'});await owner.submit();expect(f.calls.some(call=>call.path==='/api/outlook/import')).toBe(false);
  fresh=1;owner.update({text:'fixture----password----client----refresh'});await owner.submit();expect(owner.state.open).toBe(true);expect(owner.state.receipt?.detail).toContain('已接收 1');expect(owner.state.receipt?.detail).toContain('显示刷新失败');expect(owner.state.text).toBe('');owner.dispose();
 });
 it('keeps authoritative local import rejection distinct from an unacknowledged response',async()=>{
  const f=fixture();f.handlers.set('/api/outlook/import-preview',()=>({new:1}));f.handlers.set('/api/outlook/import',()=>{throw new ApiError('当前来源不允许导入',403,'permission_denied');});
  const owner=useLocalImport(f.api,f.deps);owner.setActive(true);owner.open('outlook');owner.update({text:'original----password----client----refresh'});await owner.submit();
  expect(owner.state.receipt?.label).toBe('导入被拒绝');expect(owner.state.receipt?.detail).toContain('当前来源不允许导入');expect(owner.state.receipt?.detail).not.toContain('响应未确认');expect(owner.state.text).toContain('original');owner.setActive(false);owner.setActive(true);expect(f.calls.filter(call=>call.path==='/api/outlook/import')).toHaveLength(1);owner.dispose();
 });
});
