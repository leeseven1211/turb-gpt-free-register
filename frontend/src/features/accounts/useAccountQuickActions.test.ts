import {effectScope} from 'vue';
import {describe,expect,it,vi} from 'vitest';
import {ACCOUNT_ACTION_USAGE_KEY,ACCOUNT_QUICK_ACTION_DEFAULTS,rankAccountQuickActions,useAccountQuickActions,type AccountQuickActionRuntime} from './useAccountQuickActions';
const ids=[...ACCOUNT_QUICK_ACTION_DEFAULTS,'copy','delete','batch'];
function fixture(initial:string|null=null){
  let saved=initial,blocked=false,listener:((event:{key:string|null})=>void)|undefined;const frames=new Map<number,()=>void>();let sequence=0;
  const runtime:AccountQuickActionRuntime={storage:{getItem:vi.fn(()=>saved),setItem:vi.fn((_key,value)=>{saved=value;})},requestFrame:fn=>{frames.set(++sequence,fn);return sequence;},cancelFrame:handle=>{frames.delete(handle);},addStorageListener:fn=>{listener=fn;return()=>{listener=undefined;};}};
  const scope=effectScope(),view=scope.run(()=>useAccountQuickActions(ids,runtime,()=>blocked))!;
  const flush=()=>{const pending=[...frames.values()];frames.clear();pending.forEach(fn=>fn());};
  return{view,runtime,scope,flush,setBlocked:(value:boolean)=>{blocked=value;},setSaved:(value:string)=>{saved=value;},external:(key:string|null)=>listener?.({key}),saved:()=>saved,frames};
}
describe('account usage ranking',()=>{
  it('ranks positive safe counts before stable default and source-order ties',()=>{expect(rankAccountQuickActions(ids,{copy:4,delete:4})).toEqual(['copy','delete',...ACCOUNT_QUICK_ACTION_DEFAULTS.slice(0,3)]);});
  it.each(['broken','[]','null','{"copy":-1,"delete":1.2,"batch":9007199254740992}'])('rejects invalid persisted counts %s',saved=>{const f=fixture(saved);f.view.refresh();expect(f.view.quickIds.value).toEqual(ACCOUNT_QUICK_ACTION_DEFAULTS);f.scope.stop();});
  it('counts one valid use, preserves saturation and supports storage errors in memory',()=>{
    const f=fixture('{"copy":9007199254740991}');f.view.refresh();f.view.record('copy');f.flush();expect(JSON.parse(f.saved()!).copy).toBe(Number.MAX_SAFE_INTEGER);
    vi.mocked(f.runtime.storage.getItem).mockImplementation(()=>{throw new Error('denied');});vi.mocked(f.runtime.storage.setItem).mockImplementation(()=>{throw new Error('denied');});
    f.view.record('batch');f.view.record('missing');f.flush();expect(f.view.counts.value.batch).toBe(1);expect(f.view.quickIds.value).toContain('batch');f.scope.stop();
  });
  it('defers ordering while blocked and consumes only matching storage events',()=>{
    const f=fixture();f.view.refresh();f.setBlocked(true);f.view.record('delete');f.flush();expect(f.view.quickIds.value).toEqual(ACCOUNT_QUICK_ACTION_DEFAULTS);
    f.setBlocked(false);f.view.schedule();f.flush();expect(f.view.quickIds.value[0]).toBe('delete');
    f.setSaved('{"batch":10}');f.external('other');f.flush();expect(f.view.quickIds.value[0]).toBe('delete');f.external(ACCOUNT_ACTION_USAGE_KEY);f.flush();expect(f.view.quickIds.value[0]).toBe('batch');f.scope.stop();
  });
  it('coalesces pending frames and removes storage/frame work at disposal',()=>{const f=fixture();f.view.schedule();f.view.schedule();expect(f.frames.size).toBe(1);f.scope.stop();expect(f.frames.size).toBe(0);f.external(ACCOUNT_ACTION_USAGE_KEY);expect(f.frames.size).toBe(0);});
});
