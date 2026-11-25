import {reactive} from 'vue';
import type {EmailApi} from '../../api/email';
import type {EmailIdentity,EmailMountDependencies,EmailRow,InventoryResponse,MutationResult,ParentHistory,Receipt} from './contracts';
import {deletionWarning,identity,keyOf,message,receipt} from './presentation';
import {readScope} from './readScope';
import {BulkMutationPendingError} from '../../api/bulkMutations';
export function useEmailInventory(api:EmailApi,deps:EmailMountDependencies){
 const state=reactive({items:[] as EmailRow[],parents:[] as ParentHistory[],total:0,page:1,size:20,filters:{source:'all',q:'',status:'',used_date:'',usage:''},facets:{} as NonNullable<InventoryResponse['facets']>,selected:new Map<string,EmailIdentity>(),loading:false,error:'',summaryError:'',busy:false,receipt:null as Receipt|null});
 let copyController:AbortController|undefined;
 const scope=readScope(state,async(signal,valid)=>{
  for(let correction=0;correction<2;correction++){
   const result=await api.inventory({page:state.page,size:state.size,...state.filters},signal);if(!valid())return;
   state.total=Math.max(0,Number(result.total)||0);const pages=Math.max(1,Math.ceil(state.total/state.size));
   if(state.page>pages){state.page=pages;if(!correction)continue;throw new Error('列表范围已变化，请刷新后重试');}
   state.items=result.items||[];state.facets=result.facets||{};break;
  }
  try{const result=await api.derivationSummary(signal);if(valid()){state.parents=result.parents||[];state.summaryError='';}}catch(cause){if(valid()&&!(cause instanceof Error&&cause.name==='AbortError'))state.summaryError=`子地址历史读取失败：${message(cause)}`;}
 });
 function updateFilters(patch:Partial<typeof state.filters>){const changed=Object.keys(patch).filter(key=>patch[key as keyof typeof patch]!==state.filters[key as keyof typeof state.filters]);if(!changed.length)return;Object.assign(state.filters,patch);state.page=1;if(changed.some(key=>key!=='q'))state.selected.clear();scope.schedule(changed.every(key=>key==='q')?250:0);}
 function toggle(row:EmailIdentity,checked:boolean){checked?state.selected.set(keyOf(row),identity(row)):state.selected.delete(keyOf(row));}
 function togglePage(checked:boolean){for(const row of state.items)toggle(row,checked);}
 async function sharedRefresh(){try{await deps.onInventoryChanged();}catch(cause){state.receipt=receipt(state.receipt?.label||'已接收',`${state.receipt?.detail||''}\n显示刷新失败：${message(cause)}`,'warning');}void scope.refresh();}
 async function write(run:()=>Promise<void>){if(state.busy)return;state.busy=true;try{await run();}catch(cause){if(cause instanceof Error&&cause.name==='AbortError')return;if(cause instanceof BulkMutationPendingError){state.receipt=receipt('批量命令已受理',cause.message,'warning');deps.notify(cause.message);return;}state.receipt=receipt('操作失败',message(cause),'danger');deps.notify(`操作失败：${message(cause)}`);}finally{state.busy=false;}}
 const bulkOptions=()=>({onAccepted:(result:{command_id?:number|string})=>{state.receipt=receipt('批量命令已受理',`正在执行（命令 ${result.command_id}）`,'warning');}});
 function mutationDetail(result:MutationResult,kind:'delete'|'status'){
  const skipped=result.skipped||[],deleted=Array.isArray(result.deleted)?result.deleted:[];
  const retained=result.lease_retained_count||deleted.filter(row=>row.sync?.lease_retained).length;
  return`${kind==='delete'?'本地已移除':'已更新'} ${kind==='delete'?result.deleted_count||0:result.updated_count||0} 个${retained?`，其中 ${retained} 个已保留原租约`:''}，跳过 ${skipped.length} 个`+skipped.map(row=>`\n${row.email}：${row.reason||'未返回具体原因'}`).join('');
 }
 async function bulkDelete(){
  const items=Array.from(state.selected.values(),identity),source=state.filters.source;if(!items.length||state.busy)return;
  await write(async()=>{if(!await deps.confirm(`确定从本地邮箱池移除选中的 ${items.length} 个邮箱吗？\n\n${deletionWarning}`))return;const result=await api.bulkDelete({items,source},bulkOptions());const requested=new Set(items.map(keyOf)),removed=new Set((Array.isArray(result.deleted)?result.deleted:[]).map(keyOf).filter(key=>requested.has(key)));for(const key of removed)state.selected.delete(key);if(removed.size){state.items=state.items.filter(row=>!removed.has(keyOf(row)));state.total=Math.max(0,state.total-removed.size);}state.receipt=receipt('删除结果',mutationDetail(result,'delete'),result.skipped?.length?'warning':'success');void sharedRefresh();});
 }
 async function bulkStatus(status:string){
  const items=Array.from(state.selected.values(),identity),source=state.filters.source;if(!items.length||state.busy)return;
  const label=({available:'未使用/可用',disabled:'停用',failed:'失败'} as Record<string,string>)[status]||status;
  await write(async()=>{if(!await deps.confirm(`确定把选中的 ${items.length} 个邮箱标记为${label}吗？`))return;const result=await api.bulkStatus({items,status,source,note:`批量标记${label}`},bulkOptions());for(const row of Array.isArray(result.updated)?result.updated:[])if(items.some(item=>keyOf(item)===keyOf(row)))state.selected.delete(keyOf(row));state.receipt=receipt('状态更新',mutationDetail(result,'status'),result.skipped?.length?'warning':'success');await sharedRefresh();});
 }
 async function rowAction(row:EmailRow,action:string){
  const item=identity(row);await write(async()=>{
   if(action==='delete'){
    if(!await deps.confirm(`确定从本地邮箱池移除 ${item.email}？\n\n${deletionWarning}`))return;
    const result=await api.delete(item);if(result.deleted){state.selected.delete(keyOf(item));state.items=state.items.filter(row=>keyOf(row)!==keyOf(item));state.total=Math.max(0,state.total-1);state.receipt=receipt('本地已移除',result.sync?.message||'本地已移除，保留使用历史','success');void sharedRefresh();}
    else state.receipt=receipt('未移除',result.reason||'邮箱未移除','warning');
   }else{
    if(['replaced','pending_sync'].includes(row.status||''))return;
    const notes:Record<string,string>={available:'手动恢复可用',disabled:'手动停用',failed:'手动标记失败'};
    if(!notes[action])return;await api.status({...item,status:action,note:notes[action]});state.receipt=receipt('状态已更新',`${item.email}：${notes[action]}`,'success');await sharedRefresh();
   }
  });
 }
 async function copyRow(row:EmailIdentity){const item=identity(row);await write(async()=>{copyController=new AbortController();const signal=copyController.signal;const result=await api.secret(item,signal);if(signal.aborted)return;if(!result.value)throw new Error('对应内容为空');await deps.clipboard(result.value);deps.notify('已复制');});}
 async function copyPage(){const items=state.items.map(identity);if(!items.length)return;await write(async()=>{copyController=new AbortController();const signal=copyController.signal;const result=await api.secrets(items,signal);if(signal.aborted)return;const text=(result.values||[]).map(row=>row.value).filter(Boolean).join('\n');if(!text)throw new Error('当前页没有可复制内容');await deps.clipboard(text);state.receipt=receipt('已复制当前页',(result.skipped||[]).map(row=>`${row.email}：${row.reason}`).join('\n')||`已复制 ${items.length} 个邮箱素材`,'success');deps.notify('已复制当前页邮箱素材');});}
 return{state,refresh:scope.refresh,setActive(value:boolean){if(!value)copyController?.abort();scope.setActive(value);},dispose(){copyController?.abort();scope.dispose();},updateFilters,toggle,togglePage,bulkDelete,bulkStatus,rowAction,copyRow,copyPage,
  resetFilters(){Object.assign(state.filters,{source:'all',q:'',status:'',used_date:'',usage:''});state.selected.clear();state.page=1;scope.schedule();},
  setPage(value:number){if(!Number.isSafeInteger(value))return;state.page=Math.max(1,Math.min(value,Math.max(1,Math.ceil(state.total/state.size))));scope.schedule();},
  setSize(value:number){if(!Number.isSafeInteger(value)||value<1||value>500)return;state.size=value;state.page=1;scope.schedule();},
  async refreshDerivationSummary(){if(!scope.eligible())return;await scope.refresh();},
 };
}
