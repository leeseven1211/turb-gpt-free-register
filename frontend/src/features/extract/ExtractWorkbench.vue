<script setup lang="ts">
import {computed,onMounted,onBeforeUnmount,ref,watch} from 'vue';import type {ExtractDeps,ExtractTask,ExtractLoadOptions,TaskId} from './contracts';import {createExtractWorkbench} from './useExtractWorkbench';import {createExtractBatch} from './useExtractBatch';import {createExtractArtifacts} from './useExtractArtifacts';import {useNativeDialog} from '../../shared/useNativeDialog';import {providerLabel,modeLabel,label,outcome,time,number,sourceSuffix,statusOptions,sourceLabel,modeLabels,promotionLabels,typeLabels,modes,linkTypes,candidateHint,active,safeReplay,paymentUrl,qrSources,paymentStatus,listOutcome,expiryText} from './presentation';import ListPagination from '../../components/ListPagination.vue';import ListCell from '../../components/ListCell.vue';import ListResult from '../../components/ListResult.vue';import ListFilterSummary from '../../components/ListFilterSummary.vue';import ExtractFilters from './ExtractFilters.vue';
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
function historyOutcome(run:any){const status=label(run.status||run.task_status,'状态未记录'),evidence=run.error_info?.summary||run.error_message||run.error||run.message||'';return evidence?`${status} · ${evidence}`:status;}
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
    <h1>提链工作台</h1>
    <div v-if="work.state.summary" class="extract-metrics" aria-label="提链概况">
     <span>今日出链 <strong>{{number(work.state.summary.today_extracted)}}</strong></span>
     <span>待支付 <strong>{{number(work.state.summary.awaiting_payment)}}</strong></span>
     <span>待核对 <strong>{{number(work.state.summary.needs_review)}}</strong></span>
    </div>
   </div>
   <div class="extract-toolbar-actions">
    <button type="button" class="extract-button" @click="refresh">刷新</button>
    <button type="button" class="extract-button" @click="work.exportRows(true)">导出当前筛选</button>
    <button type="button" class="extract-button primary" @click="openCreate">新建批次</button>
   </div>
  </header>
  <div class="extract-list-panel">
  <div class="extract-count-row" data-extract-count-row>
   <div class="extract-count-main"><span class="extract-count">共 {{number(work.state.total)}} 条任务</span><ListFilterSummary :items="filterChips" @remove="changeFilter($event as FilterKey,'')"/></div>
   <div class="extract-count-actions">
    <button v-if="filterChips.length" type="button" class="extract-inline-button" @click="resetFilters">清除筛选</button>
    <ExtractFilters column="batch" :values="filterValues" :providers="filterProviders" :batches="work.state.batches" :batch-busy="work.state.batchLoading" :open="openFilter==='batch'" @update:open="openFilter=$event?'batch':null" @change="changeFilter">
     <p v-if="work.state.batchLoading" class="extract-batch-message" role="status">正在读取批次…</p>
     <div v-if="work.state.auxErrors.batches" class="extract-batch-message" role="alert">
      批次读取失败 <button type="button" class="extract-inline-button" @click="changeBatchPage(work.state.batchPage)">重试</button>
     </div>
     <ListPagination v-if="work.state.batchTotal>20" class="extract-batch-pager" label="提链批次分页" :page="work.state.batchPage" :size="20" :page-sizes="[20]" :total="work.state.batchTotal" :busy="work.state.batchLoading" @update:page="changeBatchPage"/>
    </ExtractFilters>
    <span class="extract-mobile-filter"><ExtractFilters omit-batch :values="filterValues" :providers="filterProviders" :batches="work.state.batches" :counts="work.state.counts" :open="openFilter==='all'" @update:open="openFilter=$event?'all':null" @change="changeFilter"/></span>
    <button v-if="query.batch" type="button" class="extract-inline-button extract-cancel" :title="batchScope" :disabled="Boolean(work.state.cancellingBatch)" @click="work.cancelBatch()">取消当前批次</button>
   </div>
  </div>
  <p v-if="work.state.error" class="notice error" role="alert">{{work.state.error}} <button type="button" class="extract-inline-button" @click="refresh">重试</button></p>
  <p v-if="artifacts.state.error" class="notice error" role="alert">{{artifacts.state.error}}</p>
  <div v-if="selected.size" class="extract-bulk"><strong>已选 {{selected.size}} 项</strong><button type="button" class="extract-button" :disabled="work.state.bulkBusy" @click="work.bulkAction('sync_status')">同步原单</button><button type="button" class="extract-button" @click="work.bulkAction('links')">复制支付链接</button><button type="button" class="extract-button" @click="work.exportRows(false)">导出选中</button><button type="button" class="extract-inline-button" @click="work.bulkAction('clear')">清除选择</button></div>
  <div ref="tableScroll" class="extract-table-wrap" role="region" aria-label="提链任务表格" tabindex="0"><table aria-label="提链任务"><thead><tr><th><input type="checkbox" aria-label="选择本页提链任务" :checked="selectedAll" @change="all(($event.target as HTMLInputElement).checked)"></th>
   <th v-for="key in (['query','provider','mode'] as FilterKey[])" :key="key"><ExtractFilters :column="key" :values="filterValues" :providers="filterProviders" :batches="work.state.batches" :counts="work.state.counts" :open="openFilter===key" @update:open="openFilter=$event?key:null" @change="changeFilter"/></th>
   <th>准备</th><th><ExtractFilters column="status" :values="filterValues" :providers="filterProviders" :batches="work.state.batches" :counts="work.state.counts" :open="openFilter==='status'" @update:open="openFilter=$event?'status':null" @change="changeFilter"/></th><th>支付</th><th>Plus</th><th>更新时间</th><th>操作</th></tr></thead>
   <tbody><tr v-for="task in work.state.items" :key="String(task.task_id)" :class="{'is-selected':selected.has(String(task.task_id))}"><td><input type="checkbox" :aria-label="`选择提链任务 ${task.task_id}`" :checked="selected.has(String(task.task_id))" @change="toggle(String(task.task_id))"></td>
    <td><ListCell :text="task.email||'账号未记录'" :secondary="`#${task.task_id}`"/></td><td><ListCell :text="providerLabel(task.provider_id)" :secondary="task.link_type||undefined"/></td><td><ListCell :text="modeLabel(task.mode)" :secondary="sourceSuffix(task)||undefined"/></td><td><ListCell :text="label(task.preflight_status,'未开始')"/></td>
    <td><ListResult data-extract-result :label="resultSummary(task).label" :tone="resultSummary(task).tone" :title="outcome(task).detail"><template #details><p>{{outcome(task).label}}</p><p>{{outcome(task).detail}}</p><p v-if="task.message">{{task.message}}</p><p v-if="task.error">{{task.error}}</p><p v-if="task.progress?.label">{{task.progress.label}}</p></template></ListResult></td>
    <td><ListCell :text="label(task.payment_phase||task.payment_status,'—')"/></td><td><ListCell :text="label(task.plus_state||task.plus_status,'未核验')"/></td><td><ListCell :text="time(task.updated_at||task.created_at)"/></td><td class="extract-row-actions"><button type="button" class="extract-inline-button" @click="artifacts.openDetail(task.task_id)">详情</button><button type="button" class="extract-button" :disabled="!(task.has_payment_entry||task.has_payment_link||task.has_qr)" @click="paymentEntry(task.task_id)">支付入口</button></td>
   </tr></tbody></table>
   <p v-if="!work.state.items.length" class="empty" role="status">{{work.state.loading?'正在读取任务…':work.state.error?'任务读取失败':filterChips.length?'没有符合筛选条件的任务':'暂无提链任务'}}</p>
  </div>
  <ListPagination class="extract-task-pager" label="提链任务分页" :page="query.page" :size="query.size" :total="work.state.total" :busy="work.state.loading" @update:page="changePage" @update:size="changeSize"/>
  </div>
  <dialog ref="createDialog" class="extract-dialog" aria-labelledby="extract-create-title" @cancel.prevent="closeCreate" @close="closeCreate" @click="backdrop($event,createDialog,closeCreate)">
   <header><h2 id="extract-create-title">新建提链批次</h2><button type="button" @click="closeCreate">关闭</button></header>
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
   <footer><button type="button" :disabled="batch.state.loading||batch.state.creating" @click="batch.preview">刷新匹配数量</button><button type="button" class="primary" :disabled="batch.state.creating||!batch.state.preview?.selected_count" @click="create">创建并运行（{{batch.state.preview?.selected_count||0}}）</button><button type="button" @click="closeCreate">取消</button></footer>
  </dialog>
  <dialog ref="detailDialog" class="extract-dialog" aria-labelledby="extract-detail-title" @cancel.prevent="artifacts.closeDetail" @click="backdrop($event,detailDialog,artifacts.closeDetail)">
   <header><h2 id="extract-detail-title">任务详情</h2><button type="button" @click="artifacts.closeDetail">关闭</button></header>
   <p v-if="artifacts.state.detailLoading" role="status">正在读取任务详情…</p><p v-if="artifacts.state.detailError" class="error" role="alert">{{artifacts.state.detailError}}</p>
   <template v-if="detail">
    <h3>{{detail.email||'账号未记录'}} · #{{detail.task_id}}</h3>
    <div class="extract-detail-actions" role="group" aria-label="任务操作"><button type="button" :disabled="active(detail)" @click="artifacts.taskAction(detail.task_id,'sync_status')">同步状态</button><button type="button" :disabled="!safeReplay(detail)" @click="artifacts.taskAction(detail.task_id,'retry')">重跑</button><button v-if="detail.mode==='auto_payment'&&detail.payment_status!=='paid'" type="button" :disabled="active(detail)" @click="artifacts.taskAction(detail.task_id,'auto_payment')">查询自动支付</button><button type="button" @click="artifacts.copy(detail.task_id,'email')">复制邮箱</button><button v-if="detail.account_id" type="button" @click="artifacts.copy(detail.task_id,'at')">复制 AT</button><button v-if="detail.has_extract_link" type="button" @click="artifacts.showLink(detail.task_id,'extract')">复制提链链接</button><button v-if="detail.has_payment_entry||detail.has_payment_link||detail.has_qr" type="button" @click="paymentEntry(detail.task_id)">读取支付入口</button></div>
    <p>{{providerLabel(detail.provider_id)}} · {{modeLabel(detail.mode)}}{{sourceSuffix(detail)}}</p><p>{{outcome(detail).label}} · {{outcome(detail).detail}}</p>
    <dl class="extract-facts"><div><dt>准备</dt><dd>{{label(detail.preflight_status,'未开始')}}</dd></div><div><dt>提链</dt><dd>{{label(detail.extraction_status)}}</dd></div><div><dt>支付</dt><dd>{{label(detail.payment_status)}}</dd></div><div><dt>本地 Plus 到账核验</dt><dd>{{label(detail.plus_status,'未核验')}}</dd></div></dl>
    <section v-if="detail.stages" aria-label="阶段证据"><h3>执行阶段</h3><div v-for="(stage,key) in detail.stages" :key="key" class="extract-stage"><strong>{{({prepare:'准备',run:'运行',verify:'核验'})[key]||key}}</strong> · {{label(stage?.state||stage?.status)}} <span>{{stage?.step}}</span></div></section>
    <dl v-if="detail.payment_order" class="extract-facts"><div><dt>支付订单</dt><dd>{{detail.payment_order.remote_order_id||'等待平台回执'}}</dd></div><div><dt>支付提交</dt><dd>{{detail.payment_order.submission_state||'响应缺失'}}</dd></div><div><dt>支付状态</dt><dd>{{label(detail.payment_order.payment_state,'支付响应缺失')}}</dd></div></dl>
    <p v-if="detail.reconcile_halt?.halted" class="notice">{{detail.reconcile_halt.label||'已停止自动续查，待核对'}} · {{detail.reconcile_halt.reason}}</p>
    <section class="extract-node-a" data-extract-node-a><h3>节点 A · 出手的东西</h3><p v-if="artifacts.state.nodeA.loading" role="status">读取支付入口中…</p><div v-else-if="artifacts.state.nodeA.error" role="alert"><p>{{artifacts.state.nodeA.error}}</p><button type="button" @click="artifacts.loadNodeA(detail.task_id)">重新读取节点 A</button></div><template v-else-if="artifacts.state.nodeA.entry"><p>金额 {{artifacts.state.nodeA.entry.amount??'平台未返回'}} {{artifacts.state.nodeA.entry.currency||''}} · 有效期 {{artifacts.state.nodeA.entry.expires_at?time(artifacts.state.nodeA.entry.expires_at):'平台未返回'}}</p><div class="extract-detail-actions"><template v-for="key in (['payment_page_url','payment_url'] as const)" :key="key"><template v-if="paymentUrl(artifacts.state.nodeA.entry[key])"><a :href="paymentUrl(artifacts.state.nodeA.entry[key])" target="_blank" rel="noopener noreferrer">打开{{key==='payment_page_url'?'支付页面':'支付入口'}}</a><button type="button" @click="artifacts.copyNodeA(key)">复制{{key==='payment_page_url'?'支付页面':'支付入口'}}</button></template></template><button v-if="artifacts.state.nodeA.entry.qr_data" type="button" @click="artifacts.copyNodeA('qr_data')">复制节点 A 二维码</button></div><img v-if="nodeQrImages.length&&!nodeQrFailed" :src="nodeQrImages[nodeQrIndex]" width="208" height="208" alt="节点 A 支付二维码" referrerpolicy="no-referrer" @error="nodeQrError"><p v-else-if="nodeQrFailed">二维码图片加载失败，可使用支付链接或二维码原文。</p><pre v-if="artifacts.state.nodeA.entry.qr_data">{{artifacts.state.nodeA.entry.qr_data}}</pre></template><p v-else>这一步还没有支付入口</p></section>
    <details v-if="detail.remote_raw"><summary>平台原文</summary><pre>{{detail.remote_raw}}</pre></details>
    <section><h3>执行时间线</h3><ol class="extract-timeline"><li v-for="(event,index) in artifacts.state.detail?.events||[]" :key="index"><strong>{{event.label||event.stage||'事件'}}</strong> · {{label(event.status,'')}} · {{time(event.at||event.created_at||event.time)}}<p v-if="event.message">{{event.message}}</p></li></ol><p v-if="!artifacts.state.detail?.events?.length">暂无阶段事件</p></section>
    <details v-if="artifacts.state.detail?.history?.length" data-extract-history><summary>历史运行 {{artifacts.state.detail.history.length}} 次</summary><article v-for="(run,index) in artifacts.state.detail.history" :key="String(run.run_id||index)"><h4>运行 #{{run.run_id||index+1}}</h4><p data-extract-run-outcome>{{historyOutcome(run)}}</p><pre>{{run}}</pre></article></details>
    <details><summary>完整任务记录</summary><pre>{{detail}}</pre></details>
   </template>
  </dialog>
  <dialog ref="paymentDialog" class="extract-dialog" aria-labelledby="extract-payment-title" @cancel.prevent="artifacts.closePayment" @click="backdrop($event,paymentDialog,artifacts.closePayment)">
   <header><h2 id="extract-payment-title">支付入口</h2><button type="button" @click="artifacts.closePayment">关闭</button></header><p v-if="artifacts.state.payment.loading" role="status">读取中…</p>
   <template v-else><div v-if="artifacts.state.payment.error" class="error" role="alert"><p>{{artifacts.state.payment.error}}</p><button type="button" @click="paymentEntry(artifacts.state.payment.taskId)">重新读取</button></div>
    <template v-if="artifacts.state.payment.entry">
     <dl class="extract-facts"><div><dt>金额</dt><dd>{{artifacts.state.payment.entry.amount??'平台未返回'}} {{artifacts.state.payment.entry.currency||''}}</dd></div><div><dt>平台支付状态</dt><dd>{{paymentStatus(artifacts.state.payment.entry.payment_status)}}</dd></div><div><dt>平台 Plus 核验</dt><dd>{{paymentStatus(artifacts.state.payment.entry.platform_plus_status,true)}}</dd></div><div><dt>有效期至</dt><dd>{{artifacts.state.payment.entry.expires_at?`${time(artifacts.state.payment.entry.expires_at)} · ${expiryText(artifacts.state.payment.entry.expires_at,now)}`:'平台未返回'}}</dd></div></dl>
     <p class="extract-hint">平台 Plus 状态供参考，本地到账以任务中的“Plus 到账核验”为准。</p>
     <section v-for="field in (['payment_page_url','payment_url'] as const)" :key="field"><h3>{{field==='payment_page_url'?'支付页面':'支付入口'}}</h3><template v-if="field==='payment_page_url'?paymentPage:paymentLink"><a :href="field==='payment_page_url'?paymentPage:paymentLink" target="_blank" rel="noopener noreferrer">打开</a><button type="button" @click="artifacts.copyPayment(field)">复制</button><pre>{{field==='payment_page_url'?paymentPage:paymentLink}}</pre></template><p v-else>平台未返回</p></section>
     <section><h3>支付二维码</h3><img v-if="qrImages.length&&!qrFailed" :src="qrImages[qrIndex]" width="208" height="208" alt="平台返回的支付二维码" referrerpolicy="no-referrer" @error="qrError"><p v-else>{{qrFailed?'二维码图片加载失败。':'平台未返回二维码图片。'}}可使用支付链接或复制下方二维码原文。</p></section>
     <section><h3>二维码原文</h3><template v-if="artifacts.state.payment.entry.qr_data"><button type="button" @click="artifacts.copyPayment('qr_data')">复制二维码内容</button><pre>{{artifacts.state.payment.entry.qr_data}}</pre></template><p v-else>平台未返回</p></section>
    </template>
   </template>
  </dialog>
 </section>
</template>
<style scoped>
@import '../../styles/task-center.css';
/* Keep the toolbar and pager outside the only scrolling region. */
.extract-page {
  display:flex; flex-direction:column; gap:14px; height:100%; min-height:0;
  min-width:0; max-width:100%; color:var(--ui-color-text);
  font:13px/1.45 var(--ui-font-sans);
}
.extract-toolbar,.extract-title,.extract-toolbar-actions,.extract-metrics,
.extract-count-row,.extract-count-main,.extract-count-actions,.extract-bulk {
  display:flex; align-items:center; gap:8px; min-width:0;
}
.extract-toolbar,.extract-count-row { justify-content:space-between; }
.extract-toolbar,.extract-title,.extract-toolbar-actions,.extract-metrics,
.extract-count-actions,.extract-bulk { flex-wrap:wrap; }
.extract-title { gap:8px 18px; }
.extract-title h1 { margin:0; font-size:22px; line-height:1.3; font-weight:700; }
.extract-metrics {
  color:var(--ui-color-text-secondary); font-size:12px; gap:4px 12px;
  font-variant-numeric:tabular-nums;
}
.extract-metrics span { white-space:nowrap; }
.extract-metrics strong { margin-inline-start:3px; color:var(--ui-color-text); font-weight:650; }
.extract-metrics span:last-child strong { color:var(--ui-color-warning); }
.extract-button,.extract-inline-button {
  display:inline-flex; align-items:center; justify-content:center;
  min-height:30px; border:1px solid transparent; border-radius:6px; padding:4px 9px;
  color:var(--ui-color-text); background:transparent; white-space:nowrap; font:inherit; cursor:pointer;
}
.extract-button { border-color:var(--ui-color-border-strong); background:var(--ui-color-surface); }
.extract-button.primary { border-color:var(--ui-color-brand); background:var(--ui-color-brand); color:var(--ui-color-on-brand,#fff); font-weight:650; }
.extract-button:not(.primary):hover:not(:disabled),.extract-inline-button:hover:not(:disabled) {
  color:var(--ui-color-brand); background:var(--ui-color-brand-soft); border-color:var(--ui-color-brand-soft);
}
.extract-button.primary:hover { filter:brightness(.94); }
.extract-button:disabled,.extract-inline-button:disabled { opacity:.48; cursor:default; }
.extract-inline-button { color:var(--ui-color-brand); }
.extract-cancel { color:var(--ui-color-danger); }
.extract-page :is(button,input,select):focus-visible,.extract-table-wrap:focus-visible {
  outline:2px solid var(--ui-color-brand); outline-offset:2px;
}
.extract-list-panel {
  display:flex; flex:1; flex-direction:column; min-width:0; min-height:0;
  border:1px solid var(--ui-color-border); border-radius:12px;
  background:var(--ui-color-surface); box-shadow:0 1px 2px rgb(16 24 40 / 5%); overflow:hidden;
}
.extract-count-row { flex:none; padding:6px 14px; }
.extract-count-main { flex:1; }
.extract-count { flex:none; font-weight:650; white-space:nowrap; font-variant-numeric:tabular-nums; }
.extract-count-main :deep(.list-filter-summary) { flex:1; }
.extract-count-actions { justify-content:flex-end; }
.extract-count-actions :deep(.tc-column-filter-trigger) {
  padding-inline:9px; border:1px solid var(--ui-color-border); border-radius:6px;
}
.extract-count-actions :deep(.tc-column-filter-trigger[data-state=open]) { background:var(--ui-color-brand-soft); }
.extract-mobile-filter { display:none; }
.extract-bulk {
  flex:none; padding:5px 14px; border-top:1px solid var(--ui-color-border);
  background:var(--ui-color-brand-soft);
}
.extract-bulk strong { color:var(--ui-color-brand); }
.extract-table-wrap {
  flex:1; min-height:0; min-width:0; max-width:100%; overflow:auto;
  overscroll-behavior-x:contain; scrollbar-width:thin; border-top:1px solid var(--ui-color-border);
}
.extract-table-wrap:focus-visible { outline-offset:-2px; }
.extract-table-wrap table {
  width:100%; min-width:1050px; table-layout:fixed; border-collapse:separate; border-spacing:0;
}
.extract-table-wrap :is(th,td) {
  padding:5px 11px; border-bottom:1px solid var(--ui-color-border); text-align:left;
  vertical-align:middle; white-space:normal; overflow-wrap:anywhere;
}
.extract-table-wrap th {
  position:sticky; top:0; z-index:1; height:38px; padding-block:2px;
  background:var(--ui-color-surface-subtle); color:var(--ui-color-text-secondary);
  font-size:12px; font-weight:650;
}
.extract-table-wrap :is(th,td):first-child { width:38px; text-align:center; }
.extract-table-wrap th:nth-child(3) { width:12%; }
.extract-table-wrap th:nth-child(4) { width:11.5%; }
.extract-table-wrap th:nth-child(5) { width:6.5%; }
.extract-table-wrap th:nth-child(6) { width:10.5%; }
.extract-table-wrap th:nth-child(7) { width:6.5%; }
.extract-table-wrap th:nth-child(8) { width:8.5%; }
.extract-table-wrap th:nth-child(9) { width:13.5%; }
.extract-table-wrap th:last-child { width:12.5%; }
.extract-table-wrap :is(th,td):last-child { text-align:right; }
.extract-table-wrap :is(th,td):nth-child(9) { font-variant-numeric:tabular-nums; }
.extract-table-wrap tbody tr:hover { background:var(--ui-color-surface-subtle); }
.extract-table-wrap tbody tr.is-selected { background:var(--ui-color-brand-soft); }
.extract-table-wrap input[type=checkbox] {
  display:block; width:15px; height:15px; min-height:0; padding:0; margin:auto;
  accent-color:var(--ui-color-brand); cursor:pointer;
}
.extract-table-wrap :deep(.list-cell-secondary) { margin-top:0; font-size:12px; }
.extract-table-wrap td:nth-child(2) :deep(.list-cell-primary) { font-weight:600; }
.extract-row-actions { white-space:nowrap !important; }
.extract-row-actions button { min-height:28px; margin-inline-start:3px; padding-inline:6px; font-size:12px; }
.extract-task-pager {
  flex:none; border-top:1px solid var(--ui-color-border); padding-block:8px;
  background:var(--ui-color-surface-subtle);
}
.extract-batch-pager { padding:8px 0 0; border-top:1px solid var(--ui-color-border); }
.extract-batch-pager :deep(.list-pagination__size) { display:none; }
.extract-batch-message,.extract-hint { margin:0; color:var(--ui-color-text-secondary); font-size:12px; }
.notice { margin:0; padding:7px 14px; background:var(--ui-color-surface-subtle); }
.error { color:var(--ui-color-danger); }
.empty { padding:28px 14px; text-align:center; color:var(--ui-color-text-secondary); }
@media (max-width:860px), (max-height:560px) {
  .extract-page { height:auto; padding-bottom:12px; }
  .extract-table-wrap { flex:none; max-height:58dvh; min-height:min(205px,42dvh); }
}
@media (max-width:860px) {
  .extract-toolbar { align-items:flex-start; }
  .extract-title { flex-direction:column; align-items:flex-start; }
  .extract-count-row { align-items:flex-start; flex-wrap:wrap; padding-inline:10px; }
  .extract-count-main { flex-basis:100%; }
  .extract-count-actions { margin-inline-start:auto; }
  .extract-mobile-filter { display:inline-flex; }
}
@media (pointer:coarse) {
  .extract-button,.extract-inline-button,.extract-row-actions button { min-height:40px; }
  .extract-count-actions :deep(.tc-column-filter-trigger) { min-height:40px; }
}
.extract-dialog button { min-height:32px; padding:4px 10px; }
.extract-dialog .primary { background:var(--ui-color-brand); color:var(--ui-color-on-brand,#fff); border:0; border-radius:5px; }
.extract-dialog{box-sizing:border-box;width:min(760px,calc(100vw - 24px));max-width:calc(100vw - 24px);max-height:90dvh;overflow:auto;padding:20px;border:1px solid var(--ui-color-border);border-radius:10px;color:var(--ui-color-text);background:var(--ui-color-surface)}.extract-dialog[open]{display:flex;flex-direction:column;gap:12px}.extract-dialog::backdrop{background:#0006}.extract-dialog header,.extract-dialog footer,.extract-detail-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.extract-dialog header{justify-content:space-between}.extract-dialog h2,.extract-dialog h3,.extract-dialog p{margin:0}.extract-dialog pre{max-width:100%;white-space:pre-wrap;overflow-wrap:anywhere}.extract-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.extract-form-grid label{display:flex;flex-direction:column;gap:5px;min-width:0;font-size:13px}.extract-form-grid input,.extract-form-grid select{width:100%;min-width:0;min-height:36px;padding:5px 8px}.extract-facts{display:flex;gap:10px 18px;flex-wrap:wrap}.extract-facts>div{min-width:120px;overflow-wrap:anywhere}.extract-facts dt{font-size:12px;color:var(--ui-color-text-secondary)}.extract-facts dd{margin:4px 0}.extract-timeline{padding-left:20px}.extract-timeline li{margin-bottom:12px;overflow-wrap:anywhere}
@media(max-width:800px) {
  .extract-form-grid { grid-template-columns:minmax(0,1fr); }
  .extract-dialog { padding:14px; }
}
</style>
