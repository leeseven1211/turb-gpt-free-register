import {onScopeDispose,readonly,shallowRef} from 'vue';
export const ACCOUNT_ACTION_USAGE_KEY='turb_account_action_usage_v1';
export const ACCOUNT_QUICK_ACTION_DEFAULTS=Object.freeze(['btnCheckSelectedLiveV2','btnCheckSelectedPlansV2','btnRefreshSelectedTokenV2','btnExtractSelectedLinksV2','btnAddTwofaSelectedAccountsV2']);
export interface AccountQuickActionRuntime {
  storage:Pick<Storage,'getItem'|'setItem'>;
  requestFrame(callback:()=>void):number;
  cancelFrame(handle:number):void;
  addStorageListener(listener:(event:{key:string|null})=>void):()=>void;
}
export function rankAccountQuickActions(ids:readonly string[],counts:Readonly<Record<string,number>>):string[]{
  const order=[...ACCOUNT_QUICK_ACTION_DEFAULTS,...ids.filter(id=>!ACCOUNT_QUICK_ACTION_DEFAULTS.includes(id))];
  return [...ids].sort((left,right)=>(counts[right]||0)-(counts[left]||0)||order.indexOf(left)-order.indexOf(right)).slice(0,5);
}
/** Keeps persisted usage and order independent of browser globals and button rendering. */
export function useAccountQuickActions(ids:readonly string[],runtime:AccountQuickActionRuntime,blocked:()=>boolean){
  const counts=shallowRef<Record<string,number>>({}),quickIds=shallowRef(rankAccountQuickActions(ids,{}));
  let frame:number|undefined,disposed=false;
  function readCounts():Record<string,number>{
    let saved:unknown=counts.value;
    try{const raw=runtime.storage.getItem(ACCOUNT_ACTION_USAGE_KEY);if(raw!==null)saved=JSON.parse(raw);}catch{/* Retain the in-memory counts if storage is unavailable. */}
    return Object.fromEntries(ids.map(id=>{const value=saved&&typeof saved==='object'&&!Array.isArray(saved)?(saved as Record<string,unknown>)[id]:0;return[id,Number.isSafeInteger(value)&&Number(value)>0?Number(value):0];}));
  }
  function refresh(){
    if(disposed||blocked())return;
    counts.value=readCounts();const ranked=rankAccountQuickActions(ids,counts.value);
    if(ranked.join(',')!==quickIds.value.join(','))quickIds.value=ranked;
  }
  function schedule(){
    if(disposed||frame!==undefined)return;
    frame=runtime.requestFrame(()=>{frame=undefined;refresh();});
  }
  function record(id:string){
    if(disposed||!ids.includes(id))return;
    const values=readCounts();values[id]=Math.min(Number.MAX_SAFE_INTEGER,values[id]+1);counts.value=values;
    try{runtime.storage.setItem(ACCOUNT_ACTION_USAGE_KEY,JSON.stringify(values));}catch{/* In-memory ranking remains usable when writes are blocked. */}
    schedule();
  }
  const removeStorage=runtime.addStorageListener(event=>{if(event.key===ACCOUNT_ACTION_USAGE_KEY)schedule();});
  onScopeDispose(()=>{disposed=true;if(frame!==undefined)runtime.cancelFrame(frame);frame=undefined;removeStorage();});
  return{counts:readonly(counts),quickIds:readonly(quickIds),refresh,schedule,record};
}
