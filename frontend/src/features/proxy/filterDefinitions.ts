import type {ProxyRecordView,ProxySummary} from './contracts';
import {status} from './presentation';
export type FilterKey='search'|'state'|'purpose'|'window';
export const filterLabels:Record<FilterKey,string>={search:'搜索',state:'状态',purpose:'用途',window:'时间'};
export const windows=[{value:'all',label:'全部时间'},{value:'1h',label:'最近 1 小时'},{value:'24h',label:'最近 24 小时'},{value:'7d',label:'最近 7 天'}];
export const currentStates=['pending','leased','shared_pending','shared_leased','pool_leased'];
export function options(key:FilterKey,view:ProxyRecordView,summary:ProxySummary|null,value:string){
 if(key==='window')return windows;
 const raw=key==='purpose'?summary?.purposes??[]:view==='traffic'?['available']:(summary?.lease_states??[]).filter(item=>view==='current'?currentStates.includes(item):!currentStates.includes(item));
 const values=[...new Set(raw.filter(item=>typeof item==='string'&&item!=='all'))];if(value&&value!=='all'&&!values.includes(value))values.push(value);
 return[{value:'all',label:key==='state'?'全部状态':'全部用途'},...values.map(item=>({value:item,label:key==='state'?status(item).label:item}))];
}
export function chips(filters:{search:string;window:string;purpose:string},states:Record<ProxyRecordView,string>){
 const values:{key:string;label:string;title:string;removeLabel:string}[]=[];
 const add=(key:string,label:string,value:string)=>values.push({key,label:`${label}：${value}`,title:`${label}：${value}`,removeLabel:`清除${label}筛选`});
 if(filters.search)add('search','搜索',filters.search);if(filters.window!=='all')add('window','时间',windows.find(item=>item.value===filters.window)?.label||filters.window);if(filters.purpose!=='all')add('purpose','用途',filters.purpose);
 for(const view of ['current','history','traffic'] as const)if(states[view]!=='all')add('state:'+view,{current:'当前状态',history:'历史状态',traffic:'采集状态'}[view],status(states[view]).label);
 return values;
}
