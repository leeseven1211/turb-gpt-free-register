<script setup lang="ts">
import {computed,onMounted,onBeforeUnmount,ref,watch} from 'vue';import type {ExtractDeps,ExtractTask,ExtractLoadOptions,TaskId} from './contracts';import {createExtractWorkbench} from './useExtractWorkbench';import {createExtractBatch} from './useExtractBatch';import {createExtractArtifacts} from './useExtractArtifacts';import {useNativeDialog} from '../../shared/useNativeDialog';import {providerLabel,modeLabel,label,outcome,time,number,sourceSuffix,statusOptions,sourceLabel,modeLabels,promotionLabels,typeLabels,modes,linkTypes,candidateHint,active,safeReplay,paymentUrl,qrSources,paymentStatus,listOutcome,expiryText} from './presentation';import ListPagination from '../../components/ListPagination.vue';import ListCell from '../../components/ListCell.vue';
import TableState from '../../components/TableState.vue';import ListResult from '../../components/ListResult.vue';import ListFilterSummary from '../../components/ListFilterSummary.vue';import ExtractFilters from './ExtractFilters.vue';
const props=defineProps<{deps?:ExtractDeps}>();const deps=props.deps||{};const work=createExtractWorkbench(deps);const batch=createExtractBatch(deps,()=>work.load({force:true}));const artifacts=createExtractArtifacts(deps,()=>work.load({force:true}));const visible=ref(deps.visible!==false);const showCreate=ref(false);const createDialog=ref<HTMLDialogElement>();const detailDialog=ref<HTMLDialogElement>();const paymentDialog=ref<HTMLDialogElement>();const query=work.state.query;const selected=computed(()=>work.state.selected as Set<string>);const pages=computed(()=>Math.max(1,Math.ceil(work.state.total/query.size)));const providers=computed(()=>work.state.config?.providers||batch.state.config?.providers||[]);const tableScroll=ref<HTMLElement>();let scrollGeneration=0;const selectedAll=computed(()=>work.state.items.length>0&&work.state.items.every((x:ExtractTask)=>selected.value.has(String(x.task_id))));
useNativeDialog(createDialog,()=>showCreate.value,()=>visible.value);useNativeDialog(detailDialog,()=>Boolean(artifacts.state.drawer),()=>visible.value);useNativeDialog(paymentDialog,()=>Boolean(artifacts.state.payment.open),()=>visible.value);
type FilterKey='query'|'provider'|'mode'|'status'|'batch';
const openFilter=ref<FilterKey|'all'|null>(null);
const filterValues=computed(()=>({query:query.query,provider:query.provider,mode:query.mode,status:query.status,batch:query.batch}));
const filterLabels:Record<FilterKey,string>={query:'账号',provider:'平台',mode:'模式',status:'提链状态',batch:'批次'};
const filterChips=computed(()=>Object.entries(filterValues.value).filter(([,value])=>value).map(([key,value])=>({key,label:`${filterLabels[key as FilterKey]}：${key==='provider'?providers.value.find((p:any)=>p.id===value)?.label||providerLabel(value):key==='mode'?modeLabel(value):key==='status'?statusOptions.find(item=>item[0]===value)?.[1]||value:key==='batch'?work.state.batchDetail?.title||`#${value}`:value}`,removeLabel:`清除${filterLabels[key as FilterKey]}筛选`})));
function changeFilter(key:FilterKey,value:string){openFilter.value=null;if(key==='batch'){void switchBatch(value);return;}query[key]=value;query.page=1;void load();}
function resetFilters(){Object.assign(query,{query:'',provider:'',mode:'',status:'',page:1});void switchBatch('');}
function changePage(value:number){query.page=value;void load();}
function changeSize(value:number){query.page=1;query.size=value;void load();}
const batchScope=computed(()=>work.state.batchDetail?.title||`批次 #${query.batch}`);
function changeBatchPage(value:number){void work.loadBatchPage(value);}
const filterProviders=computed(()=>[...providers.value,...(work.state.config?.unavailable_providers||[]).filter((provider:any)=>!providers.value.some((item:any)=>item.id===provider.id)).map((provider:any)=>({...provider,label:`${provider.label||providerLabel(provider.id)}（已停用）`}))]);
const currentProvider=computed(()=>providers.value.find((p:any)=>p.id===batch.state.provider));
const detail=computed(()=>artifacts.state.detail?.item as ExtractTask|undefined);
const paymentPage=computed(()=>paymentUrl(artifacts.state.payment.entry?.payment_page_url));
const paymentLink=computed(()=>paymentUrl(artifacts.state.payment.entry?.payment_url));
const nodeQrIndex=ref(0),nodeQrFailed=ref(false);const nodeQrImages=computed(()=>qrSources(artifacts.state.nodeA.entry||{}));watch(()=>artifacts.state.nodeA.entry,()=>{nodeQrIndex.value=0;nodeQrFailed.value=false;});function nodeQrError(){if(nodeQrIndex.value+1<nodeQrImages.value.length)nodeQrIndex.value++;else nodeQrFailed.value=true;}
const qrIndex=ref(0),qrFailed=ref(false),now=ref(Date.now());let expiryTimer:ReturnType<typeof setInterval>|undefined;
watch(()=>artifacts.state.payment.open,opened=>{if(expiryTimer)clearInterval(expiryTimer);expiryTimer=undefined;if(opened){now.value=Date.now();expiryTimer=setInterval(()=>{now.value=Date.now();},1000);}});
onBeforeUnmount(()=>{if(expiryTimer)clearInterval(expiryTimer);});
const qrImages=computed(()=>qrSources(artifacts.state.payment.entry||{}));
function qrError(){if(qrIndex.value+1<qrImages.value.length)qrIndex.value++;else qrFailed.value=true;}
async function paymentEntry(id:any){qrIndex.value=0;qrFailed.value=false;await artifacts.showPaymentEntry(id);}
const resultSummary=listOutcome;
type Tone='neutral'|'success'|'warning'|'danger'|'active';
function providerColor(id?:string){return ({legacy:'#64748b',huanguang:'#7c5cf0',anguang:'#0e9aa7',lumen:'#377dff',lumen_flow:'#377dff'} as Record<string,string>)[id||'']||'#98a2b3';}
function preflightTone(status?:string):Tone{return ({passed:'success',success:'success',failed:'danger',running:'active',queued:'active',waiting:'active'} as Record<string,Tone>)[status||'']||'neutral';}
function paymentTone(status?:string):Tone{return ({paid:'success',succeeded:'success',success:'success',awaiting_payment:'warning',pending:'warning',unpaid:'warning',pending_payment:'warning',processing:'active',running:'active',failed:'danger',expired:'danger',cancelled:'danger',canceled:'danger'} as Record<string,Tone>)[status||'']||'neutral';}
function plusTone(status?:string):Tone{return ({confirmed:'success',plus:'success',not_confirmed:'danger',checking:'active',unavailable:'warning'} as Record<string,Tone>)[status||'']||'neutral';}
function historyOutcome(run:any){const status=label(run.status||run.task_status,'状态未记录'),evidence=run.error_info?.summary||run.error_message||run.error||run.message||'';return evidence?`${status} · ${evidence}`:status;}
function timeLines(value:unknown){const formatted=time(value);const split=/^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})$/.exec(formatted);return split?{text:split[1]!,secondary:split[2]!,full:formatted}:{text:formatted,full:formatted};}
function providerChanged(){batch.setProvider(batch.state.provider);}
function resetScroll(){if(tableScroll.value){tableScroll.value.scrollTop=0;tableScroll.value.scrollLeft=0;}}
async function load(options:ExtractLoadOptions={}){const generation=options.quiet?scrollGeneration:++scrollGeneration;await work.load(options);if(!options.quiet&&generation===scrollGeneration&&visible.value&&!work.state.error)resetScroll();}
async function switchBatch(id:TaskId|''){const generation=++scrollGeneration;await work.switchBatch(id);if(generation===scrollGeneration&&visible.value&&!work.state.error)resetScroll();}
function backdrop(event:MouseEvent,dialog:HTMLDialogElement|undefined,close:()=>void){if(event.target!==dialog||!dialog)return;const box=dialog.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)close();}
function closeCreate(){showCreate.value=false;batch.close();}
function closeDialogs(){closeCreate();artifacts.closeDialogs();}
function setVisible(v:boolean){visible.value=v;work.setVisible(v);if(!v){openFilter.value=null;closeCreate();artifacts.closeDialogs();}}function toggle(id:string){selected.value.has(id)?selected.value.delete(id):selected.value.add(id)}function all(v:boolean){work.state.items.forEach((x:ExtractTask)=>v?selected.value.add(String(x.task_id)):selected.value.delete(String(x.task_id)))}async function openCreate(){showCreate.value=true;await batch.open(work.state.config||undefined);await batch.preview()}async function create(){const receipt=await batch.submit();if(receipt?.batch_id){closeCreate();await switchBatch(receipt.batch_id)}}async function refresh(){await load({force:true})}onMounted(()=>work.load());onBeforeUnmount(()=>{work.destroy();batch.destroy();artifacts.destroy()});defineExpose({load,setVisible,openCreate,switchBatch,openDetail:artifacts.openDetail,showPaymentEntry:paymentEntry,taskAction:artifacts.taskAction,showLink:artifacts.showLink,copy:artifacts.copy,copyPayment:artifacts.copyPayment,bulkAction:work.bulkAction,cancelBatch:work.cancelBatch,exportRows:work.exportRows,closeDialogs});
</script>
<template>
 <section class="extract-page" :aria-busy="work.state.loading">
  <header class="extract-toolbar">
   <div class="extract-title">
    <h1 class="ui-sr-only">提链工作台</h1>
    <div v-if="work.state.summary" class="extract-metrics" aria-label="提链概况">
     <span>今日出链 <strong>{{number(work.state.summary.today_extracted)}}</strong></span>
     <span>待支付 <strong>{{number(work.state.summary.awaiting_payment)}}</strong></span>
    </div>
   </div>
   <div class="extract-toolbar-actions">
    <button type="button" class="ui-button" @click="refresh">刷新</button>
    <button type="button" class="ui-button" @click="work.exportRows(true)">导出当前筛选</button>
    <button type="button" class="ui-button ui-button--primary" @click="openCreate">新建批次</button>
   </div>
  </header>
  <div class="ui-list extract-list-panel">
  <div class="ui-list-toolbar extract-count-row" data-extract-count-row>
   <div class="ui-list-toolbar__main extract-count-main"><span class="ui-list-count extract-count">共 {{number(work.state.total)}} 条任务</span><div v-if="selected.size" class="extract-bulk-actions" role="group" aria-label="选中提链任务批量操作"><strong class="ui-list-bulkbar__count">已选 {{selected.size}} 项</strong><button type="button" class="ui-button" :disabled="work.state.bulkBusy" @click="work.bulkAction('sync_status')">同步原单</button><button type="button" class="ui-button" @click="work.bulkAction('links')">复制支付链接</button><button type="button" class="ui-button" @click="work.exportRows(false)">导出选中</button><button type="button" class="ui-link" @click="work.bulkAction('clear')">清除选择</button></div><ListFilterSummary :items="filterChips" @remove="changeFilter($event as FilterKey,'')"/></div>
   <div class="ui-list-toolbar__actions extract-count-actions">
    <button v-if="filterChips.length" type="button" class="ui-link" @click="resetFilters">清除筛选</button>
    <ExtractFilters column="batch" :values="filterValues" :providers="filterProviders" :batches="work.state.batches" :batch-busy="work.state.batchLoading" :open="openFilter==='batch'" @update:open="openFilter=$event?'batch':null" @change="changeFilter">
     <p v-if="work.state.batchLoading" class="extract-batch-message" role="status">正在读取批次…</p>
     <div v-if="work.state.auxErrors.batches" class="extract-batch-message" role="alert">
      批次读取失败 <button type="button" class="ui-link" @click="changeBatchPage(work.state.batchPage)">重试</button>
     </div>
     <ListPagination v-if="work.state.batchTotal>20" class="extract-batch-pager" label="提链批次分页" :page="work.state.batchPage" :size="20" :page-sizes="[20]" :total="work.state.batchTotal" :busy="work.state.batchLoading" @update:page="changeBatchPage"/>
    </ExtractFilters>
    <span class="extract-mobile-filter"><ExtractFilters omit-batch :values="filterValues" :providers="filterProviders" :batches="work.state.batches" :counts="work.state.counts" :open="openFilter==='all'" @update:open="openFilter=$event?'all':null" @change="changeFilter"/></span>
    <button v-if="query.batch" type="button" class="ui-link ui-link--danger extract-cancel" :title="batchScope" :disabled="Boolean(work.state.cancellingBatch)" @click="work.cancelBatch()">取消当前批次</button>
   </div>
  </div>
  <p v-if="work.state.error" class="ui-list-feedback is-error" role="alert">{{work.state.error}} <button type="button" class="ui-link" @click="refresh">重试</button></p>
  <p v-if="artifacts.state.error" class="ui-list-feedback is-error" role="alert">{{artifacts.state.error}}</p>
  <div ref="tableScroll" class="ui-table-scroll extract-table-wrap" role="region" aria-label="提链任务表格" tabindex="0"><table class="ui-table ui-table--sticky-end extract-table" aria-label="提链任务"><colgroup><col class="extract-col-check"><col class="extract-col-email"><col class="extract-col-provider"><col class="extract-col-mode"><col class="extract-col-preflight"><col class="extract-col-status"><col class="extract-col-payment"><col class="extract-col-plus"><col class="extract-col-time"><col class="extract-col-actions"></colgroup><thead><tr><th class="ui-col-check"><input type="checkbox" aria-label="选择本页提链任务" :checked="selectedAll" @change="all(($event.target as HTMLInputElement).checked)"></th>
   <th v-for="key in (['query','provider','mode'] as FilterKey[])" :key="key"><ExtractFilters :column="key" :values="filterValues" :providers="filterProviders" :batches="work.state.batches" :counts="work.state.counts" :open="openFilter===key" @update:open="openFilter=$event?key:null" @change="changeFilter"/></th>
   <th>准备</th><th><ExtractFilters column="status" :values="filterValues" :providers="filterProviders" :batches="work.state.batches" :counts="work.state.counts" :open="openFilter==='status'" @update:open="openFilter=$event?'status':null" @change="changeFilter"/></th><th>支付</th><th>Plus</th><th>更新时间</th><th>操作</th></tr></thead>
   <tbody><tr v-for="task in work.state.items" :key="String(task.task_id)" :class="{'is-selected':selected.has(String(task.task_id))}"><td class="ui-col-check"><input type="checkbox" :aria-label="`选择提链任务 ${task.task_id}`" :checked="selected.has(String(task.task_id))" @change="toggle(String(task.task_id))"></td>
    <td><ListCell :text="task.email||'账号未记录'" :secondary="`#${task.task_id}`"/></td><td><ListCell :text="providerLabel(task.provider_id)" :secondary="task.link_type||undefined" :title="`${providerLabel(task.provider_id)}${task.link_type ? ' · ' + task.link_type : ''}`"><span class="extract-tone"><i :style="{background:providerColor(task.provider_id)}" aria-hidden="true"></i><span class="extract-tone-label">{{ providerLabel(task.provider_id) }}</span></span></ListCell></td><td><ListCell :text="modeLabel(task.mode)" :secondary="sourceSuffix(task)||undefined"/></td><td><ListCell :text="label(task.preflight_status,'未开始')" :tone="preflightTone(task.preflight_status)"/></td>
    <td><ListResult data-extract-result :label="resultSummary(task).label" :tone="resultSummary(task).tone" :title="outcome(task).detail"><template #details><p>{{outcome(task).label}}</p><p>{{outcome(task).detail}}</p><p v-if="task.message">{{task.message}}</p><p v-if="task.error">{{task.error}}</p><p v-if="task.progress?.label">{{task.progress.label}}</p></template></ListResult></td>
    <td><ListCell :text="label(task.payment_phase||task.payment_status,'—')" :tone="paymentTone(task.payment_phase||task.payment_status)"/></td><td><ListCell :text="label(task.plus_state||task.plus_status,'未核验')" :tone="plusTone(task.plus_state||task.plus_status)"/></td><td><ListCell class="ui-time extract-time-cell" :text="timeLines(task.updated_at||task.created_at).text" :secondary="timeLines(task.updated_at||task.created_at).secondary" :title="timeLines(task.updated_at||task.created_at).full"/></td><td><div class="ui-row-actions extract-row-actions"><button type="button" class="ui-link" @click="artifacts.openDetail(task.task_id)">详情</button><button type="button" class="ui-link" :disabled="!(task.has_payment_entry||task.has_payment_link||task.has_qr)" @click="paymentEntry(task.task_id)">支付入口</button></div></td>
   </tr><TableState v-if="!work.state.items.length" :colspan="10" :loading="work.state.loading" :error="work.state.error?' ':''" loading-title="正在读取任务…" error-title="任务读取失败" :title="filterChips.length?'没有符合筛选条件的任务':'暂无提链任务'"/></tbody></table>
  </div>
  <ListPagination class="extract-task-pager" label="提链任务分页" :page="query.page" :size="query.size" :total="work.state.total" :busy="work.state.loading" @update:page="changePage" @update:size="changeSize"/>
  </div>
  <dialog ref="createDialog" class="extract-dialog" aria-labelledby="extract-create-title" @cancel.prevent="closeCreate" @close="closeCreate" @click="backdrop($event,createDialog,closeCreate)">
   <header><h2 id="extract-create-title">新建提链批次</h2><button type="button" class="ui-button" @click="closeCreate">关闭</button></header>
   <div class="extract-dialog-body">
    <div class="extract-form-grid">
     <label>批次名称<input v-model="batch.state.title"></label><label>账号搜索<input v-model="batch.state.filters.query" @input="batch.invalidate"></label>
     <label>来源<select v-model="batch.state.filters.source" @change="batch.invalidate"><option value="">全部来源</option><option v-for="(text,key) in (deps.accountSources||{})" :key="key" :value="key">{{text}}</option></select></label>
     <label>注册日期从<input v-model="batch.state.filters.date_from" type="date" @change="batch.invalidate"></label><label>注册日期至<input v-model="batch.state.filters.date_to" type="date" @change="batch.invalidate"></label>
     <label>提链状态<select v-model="batch.state.filters.extract_status" @change="batch.invalidate"><option value="not_succeeded">未成功提链</option><option value="all">全部可用账号</option><option value="failed">失败</option><option value="never">从未提链</option><option value="success">已成功提链</option></select></label>
     <label>套餐优惠<select v-model="batch.state.filters.promotion" @change="batch.invalidate"><option v-for="(text,key) in promotionLabels" :key="key" :value="key">{{text}}</option></select></label>
     <label>本批运行数量<input v-model.number="batch.state.limit" type="number" min="1" max="5000" step="1" @input="batch.invalidate"></label>
     <label>平台<select v-model="batch.state.provider" @change="providerChanged"><option v-for="provider in providers" :key="provider.id" :value="provider.id">{{provider.label||providerLabel(provider.id)}}</option><option v-for="provider in batch.state.config?.unavailable_providers||[]" :key="provider.id" :value="provider.id" disabled>{{provider.label||providerLabel(provider.id)}}（{{provider.unavailable_reason||'已停用'}}）</option></select></label>
     <label>模式<select v-model="batch.state.mode"><option v-for="mode in modes(currentProvider)" :key="mode" :value="mode">{{modeLabel(mode)}}</option></select></label>
     <label>链接类型<select v-model="batch.state.type"><option v-for="type in linkTypes(currentProvider)" :key="type" :value="type">{{typeLabels[type]||type}}</option></select></label>
     <label>并发<input v-model.number="batch.state.workers" type="number" min="1" :max="batch.workersMax()" step="1"></label>
    </div>
    <p class="extract-hint">{{candidateHint(batch.state.filters.promotion)}}</p><p role="status">{{batch.state.feedback}}</p><p v-if="batch.state.error" class="error" role="alert">{{batch.state.error}}</p>
   </div>
   <footer><button type="button" class="ui-button" :disabled="batch.state.loading||batch.state.creating" @click="batch.preview">刷新匹配数量</button><button type="button" class="ui-button ui-button--primary primary" :disabled="batch.state.creating||!batch.state.preview?.selected_count" @click="create">创建并运行（{{batch.state.preview?.selected_count||0}}）</button><button type="button" class="ui-button" @click="closeCreate">取消</button></footer>
  </dialog>
  <dialog ref="detailDialog" class="extract-dialog" aria-labelledby="extract-detail-title" @cancel.prevent="artifacts.closeDetail" @click="backdrop($event,detailDialog,artifacts.closeDetail)">
   <header><h2 id="extract-detail-title">任务详情</h2><button type="button" class="ui-button" @click="artifacts.closeDetail">关闭</button></header>
   <div class="extract-dialog-body">
    <p v-if="artifacts.state.detailLoading" role="status">正在读取任务详情…</p><p v-if="artifacts.state.detailError" class="error" role="alert">{{artifacts.state.detailError}}</p>
    <template v-if="detail">
     <h3>{{detail.email||'账号未记录'}} · #{{detail.task_id}}</h3>
     <div class="extract-detail-actions" role="group" aria-label="任务操作"><button type="button" class="ui-button" :disabled="active(detail)" @click="artifacts.taskAction(detail.task_id,'sync_status')">同步状态</button><button type="button" class="ui-button" :disabled="!safeReplay(detail)" @click="artifacts.taskAction(detail.task_id,'retry')">重跑</button><button v-if="detail.mode==='auto_payment'&&detail.payment_status!=='paid'" type="button" class="ui-button" :disabled="active(detail)" @click="artifacts.taskAction(detail.task_id,'auto_payment')">查询自动支付</button><button type="button" class="ui-button" @click="artifacts.copy(detail.task_id,'email')">复制邮箱</button><button v-if="detail.account_id" type="button" class="ui-button" @click="artifacts.copy(detail.task_id,'at')">复制 AT</button><button v-if="detail.has_extract_link" type="button" class="ui-button" @click="artifacts.showLink(detail.task_id,'extract')">复制提链链接</button><button v-if="detail.has_payment_entry||detail.has_payment_link||detail.has_qr" type="button" class="ui-button ui-button--primary" @click="paymentEntry(detail.task_id)">读取支付入口</button></div>
     <p>{{providerLabel(detail.provider_id)}} · {{modeLabel(detail.mode)}}{{sourceSuffix(detail)}}</p><p>{{outcome(detail).label}} · {{outcome(detail).detail}}</p>
     <dl class="extract-facts"><div><dt>准备</dt><dd>{{label(detail.preflight_status,'未开始')}}</dd></div><div><dt>提链</dt><dd>{{label(detail.extraction_status)}}</dd></div><div><dt>支付</dt><dd>{{label(detail.payment_status)}}</dd></div><div><dt>本地 Plus 到账核验</dt><dd>{{label(detail.plus_status,'未核验')}}</dd></div></dl>
     <section v-if="detail.stages" aria-label="阶段证据"><h3>执行阶段</h3><div v-for="(stage,key) in detail.stages" :key="key" class="extract-stage"><strong>{{({prepare:'准备',run:'运行',verify:'核验'})[key]||key}}</strong> · {{label(stage?.state||stage?.status)}} <span>{{stage?.step}}</span></div></section>
     <dl v-if="detail.payment_order" class="extract-facts"><div><dt>支付订单</dt><dd>{{detail.payment_order.remote_order_id||'等待平台回执'}}</dd></div><div><dt>支付提交</dt><dd>{{detail.payment_order.submission_state||'响应缺失'}}</dd></div><div><dt>支付状态</dt><dd>{{label(detail.payment_order.payment_state,'支付响应缺失')}}</dd></div></dl>
     <p v-if="detail.reconcile_halt?.halted" class="notice">{{detail.reconcile_halt.label||'已停止自动续查'}} · {{detail.reconcile_halt.reason}}</p>
     <section class="extract-node-a" data-extract-node-a><h3>节点 A · 出手的东西 <small style="font-weight:500;font-size:12px;color:var(--ui-color-text-secondary);margin-left:6px">支付入口与二维码凭据</small></h3><p v-if="artifacts.state.nodeA.loading" role="status">读取支付入口中…</p><div v-else-if="artifacts.state.nodeA.error" role="alert"><p>{{artifacts.state.nodeA.error}}</p><button type="button" class="ui-button" @click="artifacts.loadNodeA(detail.task_id)">重新读取节点 A</button></div><template v-else-if="artifacts.state.nodeA.entry"><p>金额 {{artifacts.state.nodeA.entry.amount??'平台未返回'}} {{artifacts.state.nodeA.entry.currency||''}} · 有效期 {{artifacts.state.nodeA.entry.expires_at?time(artifacts.state.nodeA.entry.expires_at):'平台未返回'}}</p><div class="extract-detail-actions"><template v-for="key in (['payment_page_url','payment_url'] as const)" :key="key"><template v-if="paymentUrl(artifacts.state.nodeA.entry[key])"><a :href="paymentUrl(artifacts.state.nodeA.entry[key])" target="_blank" rel="noopener noreferrer">打开{{key==='payment_page_url'?'支付页面':'支付入口'}}</a><button type="button" class="ui-button" @click="artifacts.copyNodeA(key)">复制{{key==='payment_page_url'?'支付页面':'支付入口'}}</button></template></template><button v-if="artifacts.state.nodeA.entry.qr_data" type="button" class="ui-button" @click="artifacts.copyNodeA('qr_data')">复制节点 A 二维码</button></div><img v-if="nodeQrImages.length&&!nodeQrFailed" :src="nodeQrImages[nodeQrIndex]" width="208" height="208" alt="节点 A 支付二维码" referrerpolicy="no-referrer" @error="nodeQrError"><p v-else-if="nodeQrFailed">二维码图片加载失败，可使用支付链接或二维码原文。</p><pre v-if="artifacts.state.nodeA.entry.qr_data">{{artifacts.state.nodeA.entry.qr_data}}</pre></template><p v-else>这一步还没有支付入口</p></section>
     <details v-if="detail.remote_raw"><summary>平台原文</summary><pre>{{detail.remote_raw}}</pre></details>
     <section><h3>执行时间线</h3><ol class="extract-timeline"><li v-for="(event,index) in artifacts.state.detail?.events||[]" :key="index"><strong>{{event.label||event.stage||'事件'}}</strong> · {{label(event.status,'')}} · {{time(event.at||event.created_at||event.time)}}<p v-if="event.message">{{event.message}}</p></li></ol><p v-if="!artifacts.state.detail?.events?.length">暂无阶段事件</p></section>
     <details v-if="artifacts.state.detail?.history?.length" data-extract-history><summary>历史运行 {{artifacts.state.detail.history.length}} 次</summary><article v-for="(run,index) in artifacts.state.detail.history" :key="String(run.run_id||index)"><h4>运行 #{{run.run_id||index+1}}</h4><p data-extract-run-outcome>{{historyOutcome(run)}}</p><pre>{{run}}</pre></article></details>
     <details><summary>完整任务记录</summary><pre>{{detail}}</pre></details>
    </template>
   </div>
   <footer><button type="button" class="ui-button" @click="artifacts.closeDetail">关闭</button></footer>
  </dialog>
  <dialog ref="paymentDialog" class="extract-dialog" aria-labelledby="extract-payment-title" @cancel.prevent="artifacts.closePayment" @click="backdrop($event,paymentDialog,artifacts.closePayment)">
   <header><h2 id="extract-payment-title">支付入口</h2><button type="button" class="ui-button" @click="artifacts.closePayment">关闭</button></header>
   <div class="extract-dialog-body">
    <p v-if="artifacts.state.payment.loading" role="status">读取中…</p>
    <template v-else><div v-if="artifacts.state.payment.error" class="error" role="alert"><p>{{artifacts.state.payment.error}}</p><button type="button" class="ui-button" @click="paymentEntry(artifacts.state.payment.taskId)">重新读取</button></div>
     <template v-if="artifacts.state.payment.entry">
      <dl class="extract-facts"><div><dt>金额</dt><dd>{{artifacts.state.payment.entry.amount??'平台未返回'}} {{artifacts.state.payment.entry.currency||''}}</dd></div><div><dt>平台支付状态</dt><dd>{{paymentStatus(artifacts.state.payment.entry.payment_status)}}</dd></div><div><dt>平台 Plus 核验</dt><dd>{{paymentStatus(artifacts.state.payment.entry.platform_plus_status,true)}}</dd></div><div><dt>有效期至</dt><dd>{{artifacts.state.payment.entry.expires_at?`${time(artifacts.state.payment.entry.expires_at)} · ${expiryText(artifacts.state.payment.entry.expires_at,now)}`:'平台未返回'}}</dd></div></dl>
      <p class="extract-hint">平台 Plus 状态供参考，本地到账以任务中的“Plus 到账核验”为准。</p>
      <section v-for="field in (['payment_page_url','payment_url'] as const)" :key="field"><h3>{{field==='payment_page_url'?'支付页面':'支付入口'}}</h3><template v-if="field==='payment_page_url'?paymentPage:paymentLink"><div class="extract-detail-actions"><a :href="field==='payment_page_url'?paymentPage:paymentLink" target="_blank" rel="noopener noreferrer">打开</a><button type="button" class="ui-button" @click="artifacts.copyPayment(field)">复制</button></div><pre>{{field==='payment_page_url'?paymentPage:paymentLink}}</pre></template><p v-else>平台未返回</p></section>
      <section><h3>支付二维码</h3><img v-if="qrImages.length&&!qrFailed" :src="qrImages[qrIndex]" width="208" height="208" alt="平台返回的支付二维码" referrerpolicy="no-referrer" @error="qrError"><p v-else>{{qrFailed?'二维码图片加载失败。':'平台未返回二维码图片。'}}可使用支付链接或复制下方二维码原文。</p></section>
      <section><h3>二维码原文</h3><template v-if="artifacts.state.payment.entry.qr_data"><button type="button" class="ui-button" @click="artifacts.copyPayment('qr_data')">复制二维码内容</button><pre>{{artifacts.state.payment.entry.qr_data}}</pre></template><p v-else>平台未返回</p></section>
     </template>
    </template>
   </div>
   <footer><button type="button" class="ui-button" @click="artifacts.closePayment">关闭</button></footer>
  </dialog>
 </section>
</template>
<style scoped>
@import '../../styles/task-center.css';
/* 列表外观来自共享 list.css；这里只保留本页布局、概况数字与列宽。 */
.extract-page {
  display:flex; flex-direction:column; gap:14px; height:100%; min-height:0;
  min-width:0; max-width:100%; color:var(--ui-color-text);
  font:13px/1.45 var(--ui-font-sans);
}
.extract-page :deep(.ui-link:disabled),
.extract-page .ui-link:disabled {
  background:transparent;
  border-color:transparent;
  color:var(--ui-color-text-subtle);
  box-shadow:none;
  opacity:0.6;
}
.extract-toolbar,.extract-title,.extract-toolbar-actions,.extract-metrics {
  display:flex; align-items:center; flex-wrap:wrap; gap:8px; min-width:0;
}
.extract-toolbar { justify-content:space-between; }
.extract-toolbar-actions .ui-button { min-height:32px; height:32px; padding:0 12px; }
.extract-title { gap:8px 18px; }
.extract-metrics { color:var(--ui-color-text-secondary); font-size:12.5px; gap:8px 10px; font-variant-numeric:tabular-nums; }
.extract-metrics span {
  display:inline-flex; align-items:center; gap:7px; height:32px; padding:0 12px;
  border:1px solid var(--ui-color-border); border-radius:var(--ui-radius-pill,999px);
  background:var(--ui-color-surface); box-shadow:0 1px 2px rgba(16,24,40,.04);
  white-space:nowrap; font-weight:550;
}
.extract-metrics span::before {
  content:''; width:7px; height:7px; border-radius:50%; flex:none;
  background:var(--ui-color-success); box-shadow:0 0 0 3px rgba(31,157,117,.14);
}
.extract-metrics span:last-child::before {
  background:var(--ui-color-warning); box-shadow:0 0 0 3px rgba(201,130,22,.16);
}
.extract-metrics strong { margin-inline-start:2px; color:var(--ui-color-text); font-size:14.5px; font-weight:720; font-stretch:105%; }
.extract-metrics span:last-child strong { color:var(--ui-color-warning); }
.extract-list-panel { flex:1; min-height:0; box-shadow:var(--ui-shadow-sm); }
.extract-count-main :deep(.list-filter-summary) { flex:1; }
.extract-count-actions { flex-shrink:0; }
.extract-count-actions :deep(button[aria-label="筛选批次"]),
.extract-count-actions :deep(.tc-column-filter-trigger) {
  display:inline-flex; align-items:center; gap:4px; height:32px; min-height:32px;
  padding:0 12px; margin-left:0; white-space:nowrap; flex-shrink:0;
  border:1px solid var(--ui-color-border); border-radius:6px;
  background:var(--ui-color-surface);
}
.extract-count-actions :deep(.tc-column-filter-label) { white-space:nowrap; flex-shrink:0; }
.extract-count-actions :deep(.tc-column-filter-trigger[data-state=open]) { background:var(--ui-color-brand-soft); }
.extract-mobile-filter { display:none; }
.extract-table { min-width:1220px; }
.extract-table :is(th, td) { padding-inline:10px; }
.extract-table :is(th, td).ui-col-check { padding-inline:10px 0; }
.extract-col-check { width:38px; }
.extract-col-email { width:19%; }
.extract-col-provider { width:17.5%; }
.extract-col-mode { width:15%; }
.extract-col-preflight { width:84px; }
.extract-col-status { width:96px; }
.extract-col-payment { width:76px; }
.extract-col-plus { width:11.5%; }
.extract-col-time { width:13.5%; }
.extract-col-actions { width:106px; }
.extract-time-cell :deep(.list-cell-primary),
.extract-time-cell :deep(.list-cell-secondary) {
  font-family:var(--ui-font-mono); font-size:11.5px; font-variant-numeric:tabular-nums; white-space:nowrap;
}
.extract-time-cell :deep(.list-cell-secondary) { margin-top:2px; }
.extract-table td :deep(.list-cell-primary) { overflow:hidden; text-overflow:ellipsis; }
.extract-table td:nth-child(2) :deep(.list-cell-primary) { font-weight:600; }
.extract-row-actions { flex-wrap:nowrap; gap:2px 8px; }
.extract-bulk-actions { display:flex; align-items:center; flex-wrap:wrap; gap:6px; min-width:0; margin-left:2px; padding-left:10px; border-left:1px solid var(--ui-color-border); }
.extract-bulk-actions .ui-button { min-height:28px; padding:3px 9px; font-size:12px; }
.extract-tone { display:flex; align-items:center; gap:6px; min-width:0; max-width:100%; }
.extract-tone i { width:6px; height:6px; border-radius:2px; flex:none; }
.extract-tone-label { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.extract-task-pager { flex:none; border-top:1px solid var(--ui-color-border); }
.extract-batch-pager { padding:8px 0 0; border-top:1px solid var(--ui-color-border); }
.extract-batch-pager :deep(.list-pagination__size) { display:none; }
.extract-batch-message,.extract-hint { margin:0; color:var(--ui-color-text-secondary); font-size:12px; }
.ui-list-feedback { margin-bottom:10px; }
@media (max-width:860px), (max-height:560px) {
  .extract-page { height:auto; padding-bottom:12px; }
  .extract-table-wrap { flex:none; max-height:58dvh; min-height:min(205px,42dvh); }
}
@media (max-width:860px) {
  .extract-toolbar { align-items:flex-start; }
  .extract-title { flex-direction:column; align-items:flex-start; }
  .extract-mobile-filter { display:inline-flex; }
  .extract-bulk-actions { flex-basis:100%; margin-left:0; padding-left:0; border-left:0; }
}
@media (pointer:coarse) {
  .extract-row-actions button,.extract-count-actions :deep(.tc-column-filter-trigger) { min-height:40px; }
}
.extract-dialog button { min-height:32px; padding:4px 12px; }
.extract-dialog .primary { background:var(--ui-color-brand); color:var(--ui-color-on-brand,#fff); border:0; border-radius:var(--ui-radius-md); }
.extract-dialog{box-sizing:border-box;width:min(780px,calc(100vw - 24px));max-width:calc(100vw - 24px);max-height:90dvh;overflow:auto;padding:0;border:1px solid var(--ui-color-border);border-radius:var(--ui-radius-lg);color:var(--ui-color-text);background:var(--ui-color-surface);box-shadow:var(--ui-shadow-md)}
.extract-dialog[open]{display:flex;flex-direction:column}
.extract-dialog::backdrop{background:#0b122866}
.extract-dialog > header,.extract-dialog > footer{position:sticky;z-index:4;display:flex;align-items:center;gap:8px;flex-wrap:wrap;background:var(--ui-color-surface)}
.extract-dialog > header{top:0;justify-content:space-between;padding:14px 20px;border-bottom:1px solid var(--ui-color-border)}
.extract-dialog > footer{bottom:0;justify-content:flex-end;padding:12px 20px;border-top:1px solid var(--ui-color-border)}
.extract-dialog-body{display:flex;flex-direction:column;gap:14px;padding:18px 20px;min-width:0}
.extract-detail-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.extract-detail-actions a{color:var(--ui-color-brand);font-size:12.5px;font-weight:600;text-decoration:none}
.extract-detail-actions a:hover{text-decoration:underline}
.extract-dialog h2,.extract-dialog h3,.extract-dialog p{margin:0}
.extract-dialog h2{font-size:16px;font-weight:700}
.extract-dialog h3{font-size:14px;font-weight:700;margin-bottom:6px}
.extract-dialog details{border:1px solid var(--ui-color-border);border-radius:var(--ui-radius-md);padding:10px 12px;background:var(--ui-color-surface-subtle)}
.extract-dialog details > summary{cursor:pointer;font-weight:600;font-size:12.5px;color:var(--ui-color-text-secondary)}
.extract-dialog pre{max-width:100%;max-height:260px;overflow:auto;margin:8px 0 0;padding:11px 13px;border:1px solid var(--ui-color-border);border-radius:var(--ui-radius-md);background:#f6f8fa;color:#1e293b;font-family:var(--ui-font-mono);font-size:12px;line-height:1.55;white-space:pre-wrap;overflow-wrap:anywhere}
.extract-node-a{padding:14px;border:1px solid var(--ui-color-border);border-radius:var(--ui-radius-md);background:var(--ui-color-surface-subtle);display:flex;flex-direction:column;gap:8px}
.extract-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.extract-form-grid label{display:flex;flex-direction:column;gap:5px;min-width:0;font-size:12.5px;color:var(--ui-color-text-secondary)}
.extract-form-grid input,.extract-form-grid select{width:100%;min-width:0;min-height:34px;padding:5px 9px;border:1px solid var(--ui-color-border-strong);border-radius:var(--ui-radius-sm);background:var(--ui-color-surface);color:var(--ui-color-text);font:inherit}
.extract-facts{display:flex;gap:10px 18px;flex-wrap:wrap;margin:0;padding:12px 14px;border:1px solid var(--ui-color-border);border-radius:var(--ui-radius-md);background:var(--ui-color-surface-subtle)}
.extract-facts>div{min-width:120px;overflow-wrap:anywhere}
.extract-facts dt{font-size:12px;color:var(--ui-color-text-secondary)}
.extract-facts dd{margin:4px 0 0;font-weight:600}
.extract-timeline{margin:0;padding-left:20px}
.extract-timeline li{margin-bottom:10px;overflow-wrap:anywhere}
@media(max-width:800px) {
  .extract-form-grid { grid-template-columns:minmax(0,1fr); }
  .extract-dialog > header,.extract-dialog > footer{padding:12px 14px}
  .extract-dialog-body{padding:14px}
}
</style>
