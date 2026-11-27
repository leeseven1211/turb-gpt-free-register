import {computed,ref,shallowRef} from 'vue';
import type {SalesApi,SalesItem,SalesListParams,SalesStatus,SalesReceipt} from '../../api/sales';

export function useSalesList(api:SalesApi,notify:(message:string)=>void=()=>{},onBatchResult:(items:SalesReceipt[])=>void=()=>{}) {
  const items=shallowRef<SalesItem[]>([]), total=ref(0), page=ref(1), pageSize=ref(20);
  const status=ref(''),shopId=ref<number|null>(null),sourceId=ref(''),query=ref('');
  const counts=ref({all:0,for_sale:0,listed:0,sold:0});
  const selected=ref<Set<number>>(new Set()),loading=ref(false),error=ref(''),visible=ref(false);
  const pages=computed(()=>Math.max(1,Math.ceil(total.value/pageSize.value)));
  let generation=0;
  function clearSelection(){selected.value=new Set();}
  async function refresh() {
    if(!visible.value)return;
    const current=++generation; loading.value=true; error.value='';
    try {
      const params:SalesListParams={page:page.value,page_size:pageSize.value,status:status.value,shop_id:shopId.value,source_id:sourceId.value,q:query.value};
      const result=await api.list(params);
      if(current!==generation)return;
      items.value=result.items;total.value=result.total;counts.value=result.counts;
    } catch(cause) {
      if(current!==generation)return;
      error.value=cause instanceof Error?cause.message:'销售列表加载失败，请稍后重试。';
    } finally {if(current===generation)loading.value=false;}
  }
  function setStatus(value:string){if(status.value===value)return;status.value=value;page.value=1;clearSelection();void refresh();}
  function toggle(id:number,value?:boolean){const next=new Set(selected.value);if(value===undefined?next.has(id):!value)next.delete(id);else next.add(id);selected.value=next;}
  function togglePage(value:boolean){const next=new Set(selected.value);items.value.forEach(item=>value?next.add(item.id):next.delete(item.id));selected.value=next;}
  async function changeStatus(next:SalesStatus) {
    const ids=[...selected.value];if(!ids.length){notify('请先选择销售条目');return;}
    try {
      const result=await api.changeStatus({item_ids:ids,status:next});
      const failed=new Set(result.items.filter(item=>item.status==='failed'||item.error_code).map(item=>item.id));
      selected.value=new Set(ids.filter(id=>failed.has(id)));
      onBatchResult(result.items);
      presentBatch(result,notify);
      await refresh();
    }
    catch(cause){notify(cause instanceof Error?cause.message:'批量修改状态失败，请稍后重试。');}
  }
  function presentBatch(result:{success_count:number;failed_count:number;items:{id:number;status:string;error_code?:string;message?:string}[]},report=notify){
    const failed=result.items.filter(item=>item.status==='failed'||item.error_code).map(item=>`#${item.id} ${item.error_code||'failed'}${item.message?`：${item.message}`:''}`);
    if(result.failed_count)report(`已完成 ${result.success_count} 项，失败 ${result.failed_count} 项${failed.length?`：${failed.join('；')}`:''}`);
    else report(`已更新 ${result.success_count} 项`);
  }
  function setPage(value:number){const next=Math.min(pages.value,Math.max(1,value));if(next===page.value)return;page.value=next;void refresh();}
  function setSize(value:number){if(value===pageSize.value)return;pageSize.value=value;page.value=1;void refresh();}
  function setVisible(value:boolean){
    visible.value=value;
    if(!value){generation++;loading.value=false;return;}
    void refresh();
  }
  return {items,total,page,pageSize,status,shopId,sourceId,query,counts,pages,selected,loading,error,visible,
    refresh,setVisible,setStatus,toggle,togglePage,clearSelection,changeStatus,setPage,setSize};
}
