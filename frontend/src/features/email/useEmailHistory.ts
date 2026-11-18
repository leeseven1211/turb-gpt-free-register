import {reactive} from 'vue';
import type {EmailApi} from '../../api/email';
import type {EmailMountDependencies,HistoryRow,Receipt} from './contracts';
import {message,receipt} from './presentation';
import {readScope} from './readScope';
const empty=()=>({source:'all',parent_id:'',q:'',parent_q:'',state:'',related_q:'',created_from:'',created_to:''});
export function useEmailHistory(api:EmailApi,deps:EmailMountDependencies){
 const state=reactive({items:[] as HistoryRow[],total:0,page:1,size:50,filters:empty(),parentEmail:'',selected:new Map<string,HistoryRow>(),loading:false,error:'',receipt:null as Receipt|null});
 const scope=readScope(state,async(signal,valid)=>{for(let correction=0;correction<2;correction++){const result=await api.history({page:state.page,size:state.size,...state.filters},signal);if(!valid())return;state.total=Math.max(0,Number(result.total)||0);const pages=Math.max(1,Math.ceil(state.total/state.size));if(state.page>pages){state.page=pages;if(!correction)continue;throw new Error('列表范围已变化，请刷新后重试');}state.items=result.items||[];for(const row of state.items)if(state.selected.has(String(row.id)))state.selected.set(String(row.id),{...row});return;}});
 function updateFilters(patch:Partial<typeof state.filters>){if(Object.entries(patch).every(([key,value])=>value===state.filters[key as keyof typeof state.filters]))return;if(patch.source!==undefined&&patch.source!==state.filters.source){state.filters.parent_id='';state.parentEmail='';}Object.assign(state.filters,patch);state.page=1;state.selected.clear();scope.schedule(Object.keys(patch).every(key=>['q','parent_q','related_q'].includes(key))?250:0);}
 function toggle(row:HistoryRow,checked:boolean){checked?state.selected.set(String(row.id),{...row}):state.selected.delete(String(row.id));}
 return{state,refresh:scope.refresh,setActive:scope.setActive,dispose:scope.dispose,updateFilters,toggle,togglePage(checked:boolean){for(const row of state.items)toggle(row,checked);},
  resetFilters(){Object.assign(state.filters,empty());state.parentEmail='';state.selected.clear();state.page=1;scope.schedule();},
  scopeParent(row:{source:string;id:number|string;email:string}){Object.assign(state.filters,empty(),{source:row.source,parent_id:String(row.id)});state.parentEmail=row.email;state.selected.clear();state.page=1;scope.schedule();},
  clearParent(){state.filters.parent_id='';state.parentEmail='';state.selected.clear();state.page=1;scope.schedule();},
  setPage(value:number){if(!Number.isSafeInteger(value))return;state.page=Math.max(1,Math.min(value,Math.max(1,Math.ceil(state.total/state.size))));scope.schedule();},
  setSize(value:number){if(!Number.isSafeInteger(value)||value<1||value>100)return;state.size=value;state.page=1;scope.schedule();},
  async copy(){const rows=state.selected.size?Array.from(state.selected.values()):state.items;if(!rows.length){deps.notify('当前没有可复制的子邮箱');return;}try{await deps.clipboard(rows.map(row=>row.email).filter(Boolean).join('\n'));state.receipt=receipt('已复制',`已复制 ${rows.length} 条历史子邮箱`,'success');}catch(cause){state.receipt=receipt('复制失败',message(cause),'danger');}},
 };
}
