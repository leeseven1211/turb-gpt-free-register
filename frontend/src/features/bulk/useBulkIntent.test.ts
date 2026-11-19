import {expect,it,vi} from 'vitest';
import {createBulkIntent} from './useBulkIntent';
import {BulkApiError} from '../../api/bulk';
import type {BulkApi,BulkStorage} from './contracts';
function memory():BulkStorage{const map=new Map<string,string>();return{getItem:key=>map.get(key)??null,setItem:(key,value)=>{map.set(key,value);},removeItem:key=>{map.delete(key);},key:index=>[...map.keys()][index]??null,get length(){return map.size;}};}
function api(reply:()=>Promise<unknown>){const calls:{path:string;options?:RequestInit}[]=[];const value:BulkApi={async request<T>(path:string,options?:RequestInit){calls.push({path,options});return await reply() as T;}};return{value,calls};}
it('storage denial prevents transmission before any idempotency request is sent',async()=>{
  const store=memory();store.setItem=()=>{throw new Error('blocked');};const network=api(async()=>({id:'1'}));
  await expect(createBulkIntent(network.value,store,()=> 'key-1').submit('create','/batches',{name:'A'})).rejects.toThrow('blocked');expect(network.calls).toHaveLength(0);
});
it('uncertain receipt reuses exact key/path/body and blocks changed content within scope',async()=>{
  const store=memory();let fail=true;const network=api(async()=>{if(fail)throw new Error('network');return{id:'9007199254740993'};});const random=vi.fn(()=> 'key-original');
  const intent=createBulkIntent(network.value,store,random),body={operation:{key:'plan_check',version:1},selection_id:'9007199254740994'};
  await expect(intent.submit('create','/batches',body)).rejects.toThrow('network');
  await expect(intent.submit('create','/batches',{name:'changed'})).rejects.toMatchObject({code:'request_receipt_pending'});expect(network.calls).toHaveLength(1);
  fail=false;const pending=intent.pending()[0]!;await expect(intent.recover(pending)).resolves.toEqual({id:'9007199254740993'});
  expect(network.calls[1]).toEqual(network.calls[0]);expect(random).toHaveBeenCalledOnce();expect(intent.pending()).toHaveLength(0);
});
it('401 and 5xx retain request identity; explicit rejection releases it',async()=>{
  for(const status of [401,500,409]){const store=memory(),network=api(async()=>{throw new BulkApiError('error',status);}),intent=createBulkIntent(network.value,store,()=> 'key');
    await expect(intent.submit('control:1','/batches/1/control',{action:'pause'})).rejects.toMatchObject({status});expect(intent.pending()).toHaveLength(status===409?0:1);}
});
it('duplicate in-flight requests share one POST and accepted receipts survive storage cleanup failure',async()=>{
  let resolve!:(value:unknown)=>void;const network=api(()=>new Promise(done=>{resolve=done;})),store=memory(),intent=createBulkIntent(network.value,store,()=> 'key');
  const first=intent.submit('create','/batches',{name:'A'}),second=intent.submit('create','/batches',{name:'A'});
  expect(network.calls).toHaveLength(1);resolve({id:'1'});await expect(first).resolves.toEqual({id:'1'});await expect(second).resolves.toEqual({id:'1'});
  const accepted=api(async()=>({id:'2'})),blocked=memory();blocked.removeItem=()=>{throw new Error('storage unavailable');};
  await expect(createBulkIntent(accepted.value,blocked,()=> 'key').submit('create','/batches',{name:'B'})).resolves.toEqual({id:'2'});
});
