<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,ref,watch} from 'vue';
import ListPagination from '../../components/ListPagination.vue';
import TableState from '../../components/TableState.vue';
import type {SalesApi,SalesEvent,SalesItem,SalesProduct,SalesShop,SalesSource,SalesReceipt} from '../../api/sales';
import {useSalesList} from './useSalesList';
import './sales.css';

const props=withDefaults(defineProps<{api:SalesApi;initialVisible?:boolean;notify?:(message:string)=>void;executorId?:string;openTask?:(taskId:string,runId?:string)=>void}>(),{initialVisible:true,executorId:'local'});
const notify=props.notify||((message:string)=>{});
const sources=ref<SalesSource[]>([]),shops=ref<SalesShop[]>([]),products=ref<SalesProduct[]>([]);
const metaLoading=ref(false),metaError=ref(''),feedback=ref(''),feedbackTone=ref<'success'|'warning'|'error'>('success'),metaLoaded=ref(false);
const visible=ref(props.initialVisible),listingOpen=ref(false),managementOpen=ref(false),managementTab=ref<'shops'|'sources'>('shops');
const jobsOpen=ref(false),jobs=ref<Awaited<ReturnType<SalesApi['jobs']>>['jobs']>([]),jobsLoading=ref(false),jobsError=ref('');
const eventsOpen=ref(false),events=ref<SalesEvent[]>([]),eventsItem=ref<SalesItem|null>(null),eventsLoading=ref(false),eventsError=ref('');
const batchReceipts=ref<SalesReceipt[]>([]);
const listingShopId=ref<number|null>(null),listingProductId=ref<number|null>(null),listingBusy=ref(false);
const addOpen=ref(false),addSourceId=ref('local'),addAccountIds=ref(''),addBusy=ref(false);
const sourceDraft=ref<Partial<SalesSource>>({id:'',name:'',kind:'remote',base_url:'',auth_env:'',enabled:true});
const shopDraft=ref<Partial<SalesShop>>({name:'',platform:'liandong',base_url:'https://wzyp.cn',token_env:'',enabled:false,owner_id:props.executorId,sync_interval:60});
const editingShopId=ref<number|null>(null),editingSourceId=ref<string|null>(null);
const dialog=ref<HTMLElement|null>(null),restoreFocus=ref<HTMLElement|null>(null);
const statusTabs=[['','全部','all'],['for_sale','待售','for_sale'],['listed','已上架','listed'],['sold','已售出','sold']] as const;
const statusLabel=(value:string)=>({for_sale:'待售',listed:'已上架',sold:'已售出'} as Record<string,string>)[value]||value||'全部';
const syncLabel=(value:string)=>({idle:'待同步',pending:'排队中',running:'同步中',success:'已同步',failed:'同步失败',paused:'已暂停',unknown:'待确认'} as Record<string,string>)[value]||value||'未知';
const statusTone=(value:string)=>value==='sold'?'success':value==='listed'?'active':'neutral';
const fmt=(value:unknown)=>value==null||value===''?'—':String(value);
const shopName=(id:number|null)=>shops.value.find(shop=>shop.id===id)?.name||'未选店铺';
const selectedItems=computed(()=>list.items.value.filter(item=>list.selected.value.has(item.id)));
const ownerWarning=computed(()=>{const shop=shops.value.find(item=>item.id===listingShopId.value);return shop&&shop.owner_id!==props.executorId?`当前执行端为 ${props.executorId}，店铺绑定 ${shop.owner_id}；提交后由后端校验执行端权限。`:'';});
function report(message:string,tone:'success'|'warning'|'error'='success'){feedback.value=message;feedbackTone.value=tone;notify(message);}
const list=useSalesList(props.api,(message)=>report(message,'warning'),items=>{batchReceipts.value=items;});
const selectedCount=computed(()=>list.selected.value.size),pageSelected=computed(()=>list.items.value.length>0&&list.items.value.every(item=>list.selected.value.has(item.id)));
let metaGeneration=0,jobsGeneration=0,eventsGeneration=0;
async function loadMeta(){
  const current=++metaGeneration;metaLoading.value=true;metaError.value='';
  try{const [sourceResult,shopResult]=await Promise.all([props.api.sources(),props.api.shops()]);if(current!==metaGeneration||!visible.value)return;sources.value=sourceResult.sources;shops.value=shopResult.shops;if(!addSourceId.value&&sources.value[0])addSourceId.value=sources.value[0].id;metaLoaded.value=true;}
  catch(cause){if(current===metaGeneration&&visible.value)metaError.value=cause instanceof Error?cause.message:'销售配置加载失败，请重试。';}
  finally{if(current===metaGeneration)metaLoading.value=false;}
}
async function loadProducts(shopId:number|null){products.value=[];listingProductId.value=null;if(shopId==null)return;try{products.value=(await props.api.products(shopId)).products;}catch(cause){report(cause instanceof Error?cause.message:'商品加载失败，请重试。','error');}}
function setVisible(value:boolean){visible.value=value;list.setVisible(value);}
function toggleAll(event:Event){list.togglePage((event.target as HTMLInputElement).checked);}
function toggle(id:number,event:Event){list.toggle(id,(event.target as HTMLInputElement).checked);}
function openListing(){
  if(!selectedCount.value){report('请先选择待售条目。','warning');return;}
  restoreFocus.value=document.activeElement as HTMLElement;listingOpen.value=true;listingShopId.value=shops.value.find(shop=>shop.enabled)?.id||shops.value[0]?.id||null;if(listingShopId.value!=null)void loadProducts(listingShopId.value);void focusDialog();
}
async function submitListing(){
  if(listingShopId.value==null||listingProductId.value==null){report('请选择店铺和商品。','warning');return;}
  listingBusy.value=true;
  try{const result=await props.api.listItems({shop_id:listingShopId.value,product_id:listingProductId.value,item_ids:[...list.selected.value],request_key:globalThis.crypto?.randomUUID?.()||`sales-${Date.now()}`});list.clearSelection();listingOpen.value=false;report(`上架任务已受理：${result.task_id}`);await list.refresh();}
  catch(cause){report(cause instanceof Error?cause.message:'上架任务提交失败，请重试。','error');}
  finally{listingBusy.value=false;}
}
async function submitAdd(){
  const ids=addAccountIds.value.split(/[,\s，]+/).map(value=>Number(value)).filter(value=>Number.isSafeInteger(value)&&value>0);
  if(!addSourceId.value||!ids.length){report('请输入账号 ID，并选择账号来源。','warning');return;}
  addBusy.value=true;
  try{const result=await props.api.addItems({source_id:addSourceId.value,account_ids:[...new Set(ids)]});addOpen.value=false;addAccountIds.value='';report(result.failed_count?`已加入 ${result.success_count} 个，失败 ${result.failed_count} 个`:`已加入 ${result.success_count} 个`,result.failed_count?'warning':'success');await list.refresh();}
  catch(cause){report(cause instanceof Error?cause.message:'加入待售失败，请重试。','error');}
  finally{addBusy.value=false;}
}
async function syncShop(){
  if(list.shopId.value==null){report('请先选择店铺。','warning');return;}
  try{const result=await props.api.syncShop(list.shopId.value,globalThis.crypto?.randomUUID?.()||`sync-${Date.now()}`);report(`同步任务已受理：${result.task_id}`);await loadMeta();await list.refresh();}catch(cause){report(cause instanceof Error?cause.message:'同步任务提交失败，请重试。','error');}
}
async function checkShop(shopId:number){
  try{const result=await props.api.checkShop(shopId);report(`连接成功，已读取 ${result.product_count} 个商品。`);await loadMeta();}catch(cause){report(cause instanceof Error?cause.message:'店铺连接检查失败，请重试。','error');}
}
async function openJobs(){
  restoreFocus.value=document.activeElement as HTMLElement;jobsOpen.value=true;jobs.value=[];jobsError.value='';jobsLoading.value=true;
  const current=++jobsGeneration;
  try{const result=await props.api.jobs();if(current===jobsGeneration)jobs.value=result.jobs;}
  catch(cause){if(current===jobsGeneration)jobsError.value=cause instanceof Error?cause.message:'任务回执加载失败，请重试。';}
  finally{if(current===jobsGeneration)jobsLoading.value=false;}
  void focusDialog();
}
async function openEvents(item:SalesItem){
  restoreFocus.value=document.activeElement as HTMLElement;eventsItem.value=item;eventsOpen.value=true;events.value=[];eventsError.value='';eventsLoading.value=true;
  const current=++eventsGeneration;
  try{const result=await props.api.events(item.id);if(current===eventsGeneration)events.value=result.events;}
  catch(cause){if(current===eventsGeneration)eventsError.value=cause instanceof Error?cause.message:'历史记录加载失败，请重试。';}
  finally{if(current===eventsGeneration)eventsLoading.value=false;}
  void focusDialog();
}
function editShop(shop:SalesShop){editingShopId.value=shop.id;shopDraft.value={...shop};}
function editSource(source:SalesSource){editingSourceId.value=source.id;sourceDraft.value={...source};}
async function saveSource(){
  if(!sourceDraft.value.id||!sourceDraft.value.name){report('请填写来源 ID 和名称。','warning');return;}
  const draft=sourceDraft.value;
  const payload:Partial<SalesSource>={id:editingSourceId.value||draft.id,name:draft.name,kind:draft.kind,base_url:draft.base_url||'',auth_env:draft.auth_env||'',enabled:draft.enabled!==false};
  try{await props.api.saveSource(payload);report('来源已保存。');await loadMeta();editingSourceId.value=null;sourceDraft.value={id:'',name:'',kind:'remote',base_url:'',auth_env:'',enabled:true};}catch(cause){report(cause instanceof Error?cause.message:'来源保存失败，请重试。','error');}
}
async function saveShop(){
  if(!shopDraft.value.name){report('请填写店铺名称。','warning');return;}
  const draft=shopDraft.value;
  const payload:Partial<SalesShop>={id:editingShopId.value||draft.id,name:draft.name,platform:draft.platform||'liandong',base_url:draft.base_url||'https://wzyp.cn',token_env:draft.token_env||'',enabled:draft.enabled===true,owner_id:draft.owner_id||props.executorId,sync_interval:Number(draft.sync_interval??60)};
  try{await props.api.saveShop(payload);report('店铺已保存。');await loadMeta();editingShopId.value=null;shopDraft.value={name:'',platform:'liandong',base_url:'https://wzyp.cn',token_env:'',enabled:false,owner_id:props.executorId,sync_interval:60};}catch(cause){report(cause instanceof Error?cause.message:'店铺保存失败，请重试。','error');}
}
async function focusDialog(){await new Promise(resolve=>requestAnimationFrame(resolve));dialog.value?.querySelector<HTMLElement>('button,input,select')?.focus();}
function closeDialogs(){listingOpen.value=false;managementOpen.value=false;jobsOpen.value=false;eventsOpen.value=false;addOpen.value=false;jobsGeneration++;eventsGeneration++;restoreFocus.value?.focus?.({preventScroll:true});restoreFocus.value=null;}
function onKeydown(event:KeyboardEvent){if(event.key==='Escape'&&(listingOpen.value||managementOpen.value||jobsOpen.value||eventsOpen.value||addOpen.value)){event.preventDefault();closeDialogs();}}
const jobActionLabel=(value:string)=>({sync:'同步店铺',list:'上架商品',sales_sync:'销售同步'} as Record<string,string>)[value]||value||'销售任务';
const jobStatusLabel=(value:string)=>({queued:'排队中',waiting:'等待中',running:'执行中',settling:'收口中',success:'已完成',completed:'已完成',failed:'失败',partial_success:'部分成功',interrupted:'已中断',cancelling:'停止中',cancelled:'已取消',stopped:'已停止',for_sale:'待售',listed:'已上架',sold:'已售出',archived:'已归档'} as Record<string,string>)[value]||value||'待确认';
function jobSummary(value:unknown){
  const summary=(value&&typeof value==='object'&&!Array.isArray(value)?value:{}) as Record<string,unknown>;
  const items=Array.isArray(summary.items)?summary.items as Array<Record<string,unknown>>:[];
  const number=(key:string)=>typeof summary[key]==='number'&&Number.isFinite(summary[key])?Number(summary[key]):null;
  const total=number('total')??items.length;
  const success=number('success_count')??items.filter(item=>['success','completed','listed','sold','archived'].includes(String(item.status||''))).length;
  const failed=number('failed_count')??items.filter(item=>Boolean(item.error_code)||['failed','error'].includes(String(item.status||''))).length;
  const archived=number('archived_count');
  const archiveFailed=number('archive_failed_count');
  const parts=[`共 ${total} 项`,`成功 ${success} 项`,`失败 ${failed} 项`];
  if(archived!=null||archiveFailed!=null)parts.push(`已归档 ${archived??0} 项`,`归档失败 ${archiveFailed??0} 项`);
  return parts.join('，');
}
function jobItems(value:unknown){const job=(value&&typeof value==='object'?value:{}) as Record<string,unknown>;const summary=job.result_summary;if(summary&&typeof summary==='object'&&!Array.isArray(summary)&&Array.isArray((summary as Record<string,unknown>).items))return (summary as Record<string,unknown>).items as Array<Record<string,unknown>>;if(Array.isArray(summary))return summary as Array<Record<string,unknown>>;if(Array.isArray(job.items))return job.items as Array<Record<string,unknown>>;return [];}
function openTask(value:unknown){const job=(value&&typeof value==='object'?value:{}) as Record<string,unknown>;const taskId=String(job.task_id||'');const runId=job.run_id==null?undefined:String(job.run_id);if(taskId||runId)props.openTask?.(taskId,runId);}
watch(()=>list.shopId.value,value=>{if(value!=null)void loadProducts(value);});
watch(()=>list.query.value,()=>{list.clearSelection();list.page.value=1;});
onMounted(()=>{document.addEventListener('keydown',onKeydown);if(visible.value){list.setVisible(true);void loadMeta();}});
watch(visible,value=>{if(value&&!metaLoaded.value)void loadMeta();if(!value){metaGeneration++;jobsGeneration++;eventsGeneration++;}});
onBeforeUnmount(()=>document.removeEventListener('keydown',onKeydown));
defineExpose({setVisible,refresh:()=>Promise.all([list.refresh(),loadMeta()]),addAccounts:(sourceId:string,accountIds:number[])=>{addSourceId.value=sourceId;addAccountIds.value=accountIds.join(',');addOpen.value=true;void focusDialog();},closeDialogs});
</script>
<template>
  <section v-show="visible" class="sales-page" aria-label="贩卖区">
    <div class="ui-list sales-workspace">
      <header class="sales-head">
        <div><h1>贩卖区</h1><p>管理账号销售条目、店铺商品和同步回执</p></div>
        <div class="sales-head-actions"><button type="button" class="ui-button" data-open-add @click="addOpen=true;void focusDialog()">加入待售</button><button type="button" class="ui-button" data-open-management @click="managementOpen=true;managementTab='shops';void focusDialog()">店铺与来源</button><button type="button" class="ui-button" data-open-jobs @click="openJobs">任务回执</button></div>
      </header>

      <div class="sales-tabs" role="tablist" aria-label="销售状态">
        <button v-for="[value,label,key] in statusTabs" :key="key" type="button" role="tab" :data-status="key" :aria-selected="list.status.value===value" :class="{'is-active':list.status.value===value}" @click="list.setStatus(value)">{{label}}<span>{{list.counts.value[key as keyof typeof list.counts.value]}}</span></button>
      </div>
      <div class="ui-list-toolbar sales-toolbar">
        <div class="ui-list-toolbar__main">
          <span class="ui-list-count">{{list.total.value.toLocaleString()}} 条</span>
          <span v-if="selectedCount" class="sales-selection" role="status">已选 {{selectedCount}} 项</span>
          <input v-model="list.query.value" class="sales-search" type="search" placeholder="搜索邮箱、订单号或商品" aria-label="搜索销售条目" @keyup.enter="list.page.value=1;list.refresh()">
          <select v-model="list.sourceId.value" aria-label="账号来源" @change="list.page.value=1;list.clearSelection();list.refresh()"><option value="">全部来源</option><option v-for="source in sources" :key="source.id" :value="source.id">{{source.name}}</option></select>
          <select v-model="list.shopId.value" aria-label="店铺" @change="list.page.value=1;list.clearSelection();list.refresh()"><option :value="null">全部店铺</option><option v-for="shop in shops" :key="shop.id" :value="shop.id">{{shop.name}}</option></select>
        </div>
        <div class="ui-list-toolbar__actions">
          <button type="button" class="ui-button" :disabled="!selectedCount" data-open-listing @click="openListing">选择商品上架</button>
          <button type="button" class="ui-button" :disabled="!selectedCount" data-bulk-status="listed" @click="list.changeStatus('listed')">标记已上架</button>
          <button type="button" class="ui-button" :disabled="!selectedCount" data-bulk-status="sold" @click="list.changeStatus('sold')">标记已售出</button>
          <button type="button" class="ui-button" :disabled="!selectedCount" data-bulk-status="for_sale" @click="list.changeStatus('for_sale')">撤销售出</button>
          <button type="button" class="ui-button" :disabled="list.loading.value" @click="list.refresh">刷新</button>
          <button type="button" class="ui-button" :disabled="list.shopId.value==null" @click="syncShop">立即同步</button>
        </div>
      </div>
      <div v-if="metaError||feedback||batchReceipts.length" class="ui-list-feedback" :class="{'is-error':metaError||feedbackTone==='error'}" role="alert"><p v-if="metaError||feedback">{{metaError||feedback}}</p><ul v-if="batchReceipts.length" class="sales-receipt-list"><li v-for="receipt in batchReceipts" :key="receipt.id">#{{receipt.id}} · {{receipt.status}}<template v-if="receipt.error_code"> · {{receipt.error_code}}</template><template v-if="receipt.message">：{{receipt.message}}</template></li></ul></div>
      <div v-if="list.loading.value" class="sales-loading" aria-live="polite">正在加载销售条目…</div>
      <div class="ui-table-scroll">
        <table class="ui-table ui-table--sticky-end sales-table">
          <thead><tr><th class="ui-col-check"><input type="checkbox" :checked="pageSelected" :indeterminate="selectedCount>0&&!pageSelected" aria-label="选择当前页" @change="toggleAll"></th><th>账号与来源</th><th>销售状态</th><th>店铺 / 商品</th><th>订单与金额</th><th>同步与归档</th><th>操作</th></tr></thead>
          <tbody>
            <TableState v-if="list.loading.value||list.error.value||!list.items.value.length" :colspan="7" :loading="list.loading.value" :error="list.error.value" title="暂无销售条目" text="可从账号列表批量加入待售，或调整筛选条件。" retry-label="重试" @retry="list.refresh"/>
            <tr v-for="item in list.items.value" v-else :key="item.id" :class="{'is-selected':list.selected.value.has(item.id)}">
              <td class="ui-col-check"><input :data-item-check="item.id" type="checkbox" :checked="list.selected.value.has(item.id)" :aria-label="`选择销售条目 ${item.id}`" @change="toggle(item.id,$event)"></td>
              <td><strong>{{item.email}}</strong><small>{{item.source_id}} · 账号 #{{item.account_id}} · {{item.plan||'套餐未记录'}}</small></td>
              <td><span class="ui-badge" :class="`ui-badge--${statusTone(item.status)}`">{{statusLabel(item.status)}}</span><small v-if="item.error_message" class="sales-error">{{item.error_message}}</small></td>
              <td><strong>{{item.shop_name||'未上架'}}</strong><small>{{item.product_name||'尚未选择商品'}}</small></td>
              <td><strong v-if="item.order_ref">{{item.order_ref}}</strong><strong v-else>{{item.price==null?'—':`${item.price} ${item.currency}`}}</strong><small v-if="item.order_amount!=null">{{item.order_amount}} {{item.currency}}</small></td>
              <td><span class="ui-badge" :class="item.sync_status==='failed'?'ui-badge--danger':item.sync_status==='running'?'ui-badge--active':''">{{syncLabel(item.sync_status)}}</span><small v-if="item.archive_pending" class="sales-warning">归档待办</small><small v-if="item.archived" class="sales-muted">来源已归档</small></td>
              <td><button type="button" class="ui-link" @click="openEvents(item)">历史</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <ListPagination :page="list.page.value" :size="list.pageSize.value" :pages="list.pages.value" :total="list.total.value" :busy="list.loading.value" :page-sizes="[20,50,100]" label="销售条目分页" @update:page="list.setPage" @update:size="list.setSize"/>
    </div>
    <div v-if="listingOpen||addOpen||managementOpen||jobsOpen||eventsOpen" ref="dialog" class="sales-modal-backdrop" @click.self="closeDialogs">
      <section v-if="listingOpen" class="sales-dialog" role="dialog" aria-modal="true" aria-labelledby="salesListingTitle"><header><div><h2 id="salesListingTitle">选择店铺商品</h2><p>将 {{selectedCount}} 个销售条目提交为持久上架任务。</p></div><button type="button" class="ui-button" @click="closeDialogs">关闭</button></header>
<div class="sales-dialog-body"><label>店铺<select v-model="listingShopId" @change="loadProducts(listingShopId)"><option :value="null">请选择</option><option v-for="shop in shops" :key="shop.id" :value="shop.id">{{shop.name}}</option></select></label><p v-if="ownerWarning" class="sales-notice sales-notice--warning">{{ownerWarning}}</p><label>商品<select v-model="listingProductId"><option :value="null">请选择</option><option v-for="product in products" :key="product.id" :value="product.id" :disabled="product.status==='unavailable'">{{product.name}} · {{product.goods_key}}</option></select></label></div><footer><button type="button" class="ui-button" @click="closeDialogs">取消</button><button type="button" class="ui-button ui-button--primary" data-listing-submit :disabled="listingBusy" @click="submitListing">{{listingBusy?'提交中…':'提交上架'}}</button></footer></section>

      <section v-else-if="addOpen" class="sales-dialog" role="dialog" aria-modal="true" aria-labelledby="salesAddTitle"><header><div><h2 id="salesAddTitle">加入待售</h2><p>只读取所选来源的账号摘要，不显示密码、Token 或完整交付材料。</p></div><button type="button" class="ui-button" @click="closeDialogs">关闭</button></header>
<div class="sales-dialog-body"><label>账号来源<select v-model="addSourceId"><option v-for="source in sources" :key="source.id" :value="source.id">{{source.name}}</option></select></label><label>账号 ID<input v-model="addAccountIds" inputmode="numeric" placeholder="例如 1024,1025"></label></div><footer><button type="button" class="ui-button" @click="closeDialogs">取消</button><button type="button" class="ui-button ui-button--primary" :disabled="addBusy" @click="submitAdd">{{addBusy?'加入中…':'加入待售'}}</button></footer></section>

      <section v-else-if="managementOpen" class="sales-dialog sales-dialog--wide" role="dialog" aria-modal="true" aria-labelledby="salesManagementTitle">
<header><div><h2 id="salesManagementTitle">店铺与来源</h2><p>这里只保存环境变量名称，不保存或展示真实 Token、授权码和交付资料。</p></div><button type="button" class="ui-button" @click="closeDialogs">关闭</button></header>
<div class="sales-management-tabs"><button type="button" :class="{'is-active':managementTab==='shops'}" @click="managementTab='shops'">店铺</button><button type="button" :class="{'is-active':managementTab==='sources'}" @click="managementTab='sources'">账号来源</button></div><div class="sales-dialog-body sales-management">
<template v-if="managementTab==='shops'">
<div class="sales-config-list">
<article v-for="shop in shops" :key="shop.id">
<strong>{{shop.name}}</strong><span>{{shop.platform}} · {{shop.enabled?'已启用':'未启用'}} · {{shop.token_env||'未配置环境变量'}} · Token {{shop.token_configured?'已配置':'缺失'}}</span><button type="button" class="ui-link" @click="editShop(shop)">编辑</button><button type="button" class="ui-link" @click="checkShop(shop.id)">检查连接</button></article><p v-if="!shops.length" class="sales-empty">还没有店铺配置。</p></div><div class="sales-form-grid"><label>店铺名称<input v-model="shopDraft.name"></label><label>Token 环境变量<input v-model="shopDraft.token_env" placeholder="LIANDONG_TOKEN"></label><label>基础地址<input v-model="shopDraft.base_url"></label><label>执行端<input v-model="shopDraft.owner_id"></label><label>同步周期（秒）<input v-model.number="shopDraft.sync_interval" type="number" min="1" step="1"></label><label class="sales-check"><input v-model="shopDraft.enabled" type="checkbox">启用店铺</label><button type="button" class="ui-button ui-button--primary" @click="saveShop">{{editingShopId?'保存修改':'保存店铺'}}</button><button v-if="editingShopId" type="button" class="ui-link" @click="editingShopId=null;shopDraft={name:'',platform:'liandong',base_url:'https://wzyp.cn',token_env:'',enabled:false,owner_id:props.executorId,sync_interval:60}">新建店铺</button></div></template><template v-else><div class="sales-config-list">
<article v-for="source in sources" :key="source.id">
<strong>{{source.name}}</strong><span>{{source.id}} · {{source.kind==='remote'?'远端':'本地'}} · {{source.enabled?'已启用':'未启用'}} · Auth {{source.auth_configured?'已配置':'缺失'}}</span><button type="button" class="ui-link" @click="editSource(source)">编辑</button></article></div><div class="sales-form-grid"><label>来源 ID<input v-model="sourceDraft.id" placeholder="oracle" :disabled="!!editingSourceId"></label><label>来源名称<input v-model="sourceDraft.name"></label><label>基础地址<input v-model="sourceDraft.base_url"></label><label>Auth 环境变量<input v-model="sourceDraft.auth_env" placeholder="ORACLE_SALES_AUTH"></label><label>来源类型<select v-model="sourceDraft.kind"><option value="local">本地</option><option value="remote">远端</option></select></label><label class="sales-check"><input v-model="sourceDraft.enabled" type="checkbox">启用来源</label><button type="button" class="ui-button ui-button--primary" @click="saveSource">{{editingSourceId?'保存修改':'保存来源'}}</button><button v-if="editingSourceId" type="button" class="ui-link" @click="editingSourceId=null;sourceDraft={id:'',name:'',kind:'remote',base_url:'',auth_env:'',enabled:true}">新建来源</button></div></template></div></section>

      <section v-else-if="jobsOpen" class="sales-dialog sales-dialog--wide" role="dialog" aria-modal="true" aria-labelledby="salesJobsTitle">
<header><div><h2 id="salesJobsTitle">任务回执</h2><p>销售同步与上架任务按逐项结果展示，未知结果仍可重试。</p></div><button type="button" class="ui-button" :disabled="jobsLoading" @click="openJobs">刷新回执</button><button type="button" class="ui-button" @click="closeDialogs">关闭</button></header>
<div class="sales-dialog-body sales-jobs">
<p v-if="jobsLoading" class="sales-empty">正在读取任务回执…</p><p v-else-if="jobsError" class="sales-notice sales-notice--warning" role="alert">{{jobsError}} <button type="button" class="ui-link" @click="openJobs">重试</button></p><p v-else-if="!jobs.length" class="sales-empty">暂无销售任务。</p><article v-for="job in jobs" :key="String(job.id)"><strong>{{jobActionLabel(job.action)}} · {{jobStatusLabel(job.status)}}</strong><span>任务 {{job.task_id||job.id}}<template v-if="job.error_code"> · {{job.error_code}}</template></span><small v-if="job.error_message">{{job.error_message}}</small><pre v-if="job.result_summary">{{jobSummary(job.result_summary)}}</pre><ul v-if="jobItems(job).length"><li v-for="(result,index) in jobItems(job)" :key="`${String(job.id)}-${index}`">#{{result.id??'—'}} · {{jobStatusLabel(String(result.status||''))}} · {{result.error_code||'完成'}}<template v-if="result.message">：{{result.message}}</template></li></ul><button v-if="job.task_id||job.run_id" type="button" class="ui-link" @click="openTask(job)">查看任务详情</button></article></div></section>
      <section v-else class="sales-dialog sales-dialog--wide" role="dialog" aria-modal="true" aria-labelledby="salesEventsTitle"><header><div><h2 id="salesEventsTitle">条目历史</h2><p>{{eventsItem?.email}} · 销售条目 #{{eventsItem?.id}}</p></div><button type="button" class="ui-button" @click="closeDialogs">关闭</button></header>
<div class="sales-dialog-body sales-events"><p v-if="eventsLoading" class="sales-empty">正在读取条目历史…</p><p v-else-if="eventsError" class="sales-notice sales-notice--warning" role="alert">{{eventsError}} <button type="button" class="ui-link" @click="eventsItem&&openEvents(eventsItem)">重试</button></p><p v-else-if="!events.length" class="sales-empty">暂无变更记录。</p><article v-for="event in events" :key="event.id"><strong>{{event.event}}</strong><time>{{event.created_at}}</time><pre>{{JSON.stringify(event.changes,null,2)}}</pre></article></div></section>
    </div>
  </section>
</template>
