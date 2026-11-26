<script setup lang="ts">
import {computed, onMounted, ref, watch} from 'vue';
import ListCell from '../../components/ListCell.vue';
import ColumnResizer from '../../components/ColumnResizer.vue';
import TableState from '../../components/TableState.vue';
import {useColumnWidths} from '../../shared/useColumnWidths';
import ListResult from '../../components/ListResult.vue';
import RegistrationFilters from './RegistrationFilters.vue';
import RegistrationBatchPanel from './RegistrationBatchPanel.vue';
import {useNativeDialog} from '../../shared/useNativeDialog';
import {shortErrorLabel} from '../../shared/errorLabels';
import {dateTimeLines, formatDateTime} from '../../shared/time';
import ListFilterSummary from '../../components/ListFilterSummary.vue';
import ListPagination from '../../components/ListPagination.vue';
import type {RegistrationId} from '../../api/registration';
import type {RegistrationDeps} from './contracts';
import {useRegistration} from './useRegistration';
import './registration.css';

const props=defineProps<{deps:RegistrationDeps}>();
const owner=useRegistration(props.deps);
const {state}=owner;
const columnWidths=useColumnWidths({defaults:[38,100,220,156,136,170,104,116,116,148,132],storageKey:'gpt_console_table_widths_jobs',totalStorageKey:'gpt_console_table_total_jobs',min:28,max:2000});
function resetColumns(){columnWidths.resetColumns();props.deps.notify?.('已恢复默认列宽');}
const headers:{label:string;filter?:FilterKey}[]=[{label:'选择'},{label:'ID',filter:'id'},{label:'邮箱',filter:'email'},{label:'邮箱来源',filter:'email_source'},{label:'注册协议'},{label:'代理',filter:'proxy'},{label:'状态',filter:'status'},{label:'开始日期',filter:'date_from'},{label:'截止日期',filter:'date_to'},{label:'错误',filter:'error'},{label:'操作'}];
const logDialog=ref<HTMLDialogElement>();
useNativeDialog(logDialog,()=>state.detail.id!==null,()=>owner.active.value);
const count=ref(1),workers=ref(3),source=ref(''),debug=ref(false),status=ref(''),id=ref(''),email=ref(''),sourceFilter=ref(''),proxy=ref(''),errorFilter=ref(''),dateFrom=ref(''),dateTo=ref(''),page=ref(1),size=ref(20),selected=ref<Set<string>>(new Set()),otpValues=ref<Record<string,string>>({});
const launch= computed(()=>state.view==='launch'), tasks=computed(()=>state.view==='tasks');
const rows=computed(()=>state.jobs);
type FilterKey='id'|'email'|'email_source'|'status'|'proxy'|'error'|'date_from'|'date_to';
const openFilter=ref<FilterKey|'all'|null>(null);
const filterValues=computed(()=>({id:id.value,email:email.value,email_source:sourceFilter.value,status:status.value,proxy:proxy.value,error:errorFilter.value,date_from:dateFrom.value,date_to:dateTo.value}));
const filterLabels:Record<FilterKey,string>={id:'ID',email:'邮箱',email_source:'邮箱来源',status:'状态',proxy:'代理',error:'错误',date_from:'开始日期',date_to:'截止日期'};
const filterChips=computed(()=>Object.entries(filterValues.value).filter(([,value])=>value).map(([key,value])=>({key,label:`${filterLabels[key as FilterKey]}：${key==='status'?statusLabel(value):key==='email_source'?sourceLabel(value):value}`,removeLabel:`清除${filterLabels[key as FilterKey]}筛选`})));
function changeFilter(key:FilterKey,value:string){const fields={id,email,email_source:sourceFilter,status,proxy,error:errorFilter,date_from:dateFrom,date_to:dateTo};fields[key].value=value;openFilter.value=null;queryLoad();}
const errorSummary=(job:any)=>job.error_info?shortErrorLabel(job.error_info):job.error_message?'执行异常':'—';
const activeCount=computed(()=>state.statusCounts.active??['pending','running','stopping'].reduce((total,key)=>total+Number((Object.keys(state.statusCounts).length?state.statusCounts:state.batch?.status_counts||{})[key]||0),0));
const manualMode=computed(()=>Boolean(state.meta?.manual_mode));
const confirmingStart = ref(false);
const filterSourceOptions=computed(()=>{const values=new Map((state.meta?.sources||[]).map(item=>[String(item.value),{value:String(item.value),label:item.label||String(item.value)}]));const facets=state.facets.email_source;for(const item of Array.isArray(facets)?facets:[]){const value=String(typeof item==='object'?item.value:item);if(!values.has(value))values.set(value,{value,label:typeof item==='object'?item.label||value:value});}if(sourceFilter.value&&!values.has(sourceFilter.value))values.set(sourceFilter.value,{value:sourceFilter.value,label:sourceFilter.value});return [...values.values()];});
const sourceOptions=computed(()=>manualMode.value?[{value:'manual',label:'手动配置邮箱'}]:(state.meta?.sources?.filter(item=>item.enabled===true)||[]));
const launchBlock=computed(()=>state.metaError || (state.meta && (
  owner.registrationUnavailable.value || (!sourceOptions.value.length
    ? '没有可用的邮箱来源。请先导入本地邮箱，再重新选择。'
    : '')
)) || '');
const launchHint=computed(()=>launchBlock.value || (
  state.metaError || (!state.meta ? '正在读取邮箱来源…' :
  manualMode.value ? '使用手动配置的邮箱来源。' :
  !source.value ? '请选择本批使用的邮箱来源。' : '')
));
const supply=computed(()=>state.summary?.email_supply||{}), supplyValue=(key:string)=>{const value=supply.value[key];return Number.isInteger(value)&&Number(value)>=0?value:(supply.value.status==='error'?'读取失败':'未知');}, supplyHint=computed(()=>`仅统计本地库存；用完后请手动导入；邮箱由 Email Butler 等邮箱服务准备${supply.value.reason?`；${supply.value.reason}`:''}`);
const inventoryMetrics=computed(()=>[
  {label:'已注册', value:state.summary?.accounts ?? '—'},
  {label:'本地邮箱总数', value:supplyValue('total')},
  {label:'本地可用', value:supplyValue('available')},
  {label:'本地已用', value:supplyValue('used')},
  {label:'本地失败', value:supplyValue('failed')},
]);
const driverLabel=(value:any)=>state.meta?.registration_drivers?.find(item=>String(item.value)===String(value))?.label||({protocol:'本地优化 Protocol（历史）',protocol_oss:'开源 Protocol（历史）',protocol_oss_2:'开源protocol-2',sentinel_rs:'Rust sentinel-rs',roxy:'本地 Roxy',roxy_oss:'开源 Roxy（历史）'} as Record<string,string>)[String(value||'')]||String(value||'未知');
const sourceLabel=(value:any)=>filterSourceOptions.value.find(item=>String(item.value)===String(value))?.label||String(value||'-');
const statusLabel=(value:any)=>({pending:'排队中',queued:'排队中',waiting:'等待中',running:'运行中',stopping:'停止中',success:'成功',failed:'失败',partial_success:'部分成功',cancelled:'已取消',stopped:'已停止',interrupted:'执行中断',request_unknown:'失败',manual_reconcile:'失败',attention_required:'失败',unsupported:'不支持',deactivated:'已停用',debug_paused:'调试暂停',password_confirmation_pending:'失败·密码响应缺失'} as Record<string,string>)[String(value)]||String(value||'等待中');
function statusTone(job:any):'success'|'danger'|'warning'|'active'|'neutral'{
  const raw=String(job?.debug_state==='paused'?'debug_paused':job?.display_status||job?.status||'');
  if(raw==='success')return 'success';
  if(['partial_success','debug_paused','stopping'].includes(raw))return 'warning';
  if(['running','pending','queued','waiting'].includes(raw))return 'active';
  if(['failed','interrupted','request_unknown','manual_reconcile','attention_required','unsupported','deactivated','password_confirmation_pending'].includes(raw))return 'danger';
  return 'neutral';
}
const ask=async(message:string)=>props.deps.confirm?await props.deps.confirm(message):window.confirm(message);
function setVisible(value:boolean){if(!value)openFilter.value=null;owner.setVisible(value);}
function setView(value:'launch'|'tasks'){openFilter.value=null;owner.setView(value);}
function logBackdrop(event:MouseEvent){const dialog=logDialog.value;if(!dialog||event.target!==dialog)return;const box=dialog.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)owner.closeDetail();}
async function start(){
  if (state.creating || confirmingStart.value) return;
  if(launchBlock.value){state.receipt={tone:'warning',message:launchBlock.value};return;}
  const c=Number(count.value),w=Number(workers.value);
  if(!Number.isSafeInteger(c)||c<1){state.receipt={tone:'warning',message:'注册数量必须为有效的正整数'};return;}
  if(!Number.isSafeInteger(w)||w<1){state.receipt={tone:'warning',message:'并发线程数必须为有效的正整数'};return;}
  if(!sourceOptions.value.some(item => item.value === source.value)){state.receipt={tone:'warning',message:'请选择本次注册使用的邮箱来源'};return;}
  const payload = {count:c, workers:w, email_source:source.value, debug_enabled:debug.value};
  confirmingStart.value = true;
  try {
    if (activeCount.value > 0 && !await ask(`当前任务表里已有 ${activeCount.value} 个任务在跑或排队，这次会再加 ${c} 个，确定继续？`)) return;
    const receipt = await owner.create(payload);
    if (Number.isSafeInteger(receipt?.workers) && receipt.workers > 0) workers.value = receipt.workers;
  } catch {} finally {
    confirmingStart.value = false;
  }
}
async function action(kind:'cancelAll'|'stopBatch'|'cancelBatch'|'retryBatch'|'stop'|'delete'|'retry'|'deleteBulk'|'retryBulk',job?:any){
  const ids=Array.from(selected.value);
  try{await owner.executeAction(kind,job,ids,debug.value);if(kind==='deleteBulk'||kind==='retryBulk')selected.value=new Set();}catch{}
}
function resetFilters(){status.value=id.value=email.value=sourceFilter.value=proxy.value=errorFilter.value=dateFrom.value=dateTo.value='';page.value=1;void owner.load(applyFilterParams());}
function queryLoad(){page.value=1;void owner.load(applyFilterParams());}
function toggleAll(event:Event){const checked=(event.target as HTMLInputElement).checked;rows.value.filter(row=>!['running','stopping'].includes(String(row.status))).forEach(row=>checked?selected.value.add(String(row.id)):selected.value.delete(String(row.id)));selected.value=new Set(selected.value);}
function toggle(idValue:RegistrationId,event:Event){const next=new Set(selected.value);(event.target as HTMLInputElement).checked?next.add(String(idValue)):next.delete(String(idValue));selected.value=next;}
function displayProxy(row:any){return [row.proxy_provider,row.proxy_endpoint&&row.proxy_endpoint!=='-'?row.proxy_endpoint:'',row.proxy_region&&row.proxy_region!=='-'?row.proxy_region:''].filter(Boolean).join(' · ')||'-';}
function chooseBatch(value:string){page.value=1;void owner.setBatch(value);}
function applyFilterParams(){return {status:status.value,id:id.value,email:email.value,email_source:sourceFilter.value,proxy:proxy.value,error:errorFilter.value,date_from:dateFrom.value,date_to:dateTo.value,page:page.value,page_size:size.value};}
function submitOtp(job:any){const code=String(otpValues.value[String(job.id)]||'').trim();if(!code){state.receipt={tone:'warning',message:'请先填写邮箱验证码'};return;}void owner.action('/api/manual-otp',{email:job.email,code,job_id:job.id}).then(()=>{otpValues.value={...otpValues.value,[String(job.id)]:''};}).catch(()=>{});}
async function compareDebug(){if(state.detail.id==null)return;try{await owner.compare(state.detail.id);}catch{}}
defineExpose({create:owner.create,runAction:owner.executeAction,setBatch:owner.setBatch,loadSources:()=>owner.ensureMeta(true),load:owner.load,ensureMeta:owner.ensureMeta,setVisible,setView,loadSummary:owner.loadSummary,renderEmailSupply:owner.renderEmailSupply,applySummary:owner.applySummary,action:owner.action,openLog:owner.openLog,closeDetail:owner.closeDetail});
watch(()=>({...state.query}),value=>{page.value=value.page;size.value=value.page_size;id.value=value.id;email.value=value.email;sourceFilter.value=value.email_source;status.value=value.status;proxy.value=value.proxy;errorFilter.value=value.error;dateFrom.value=value.date_from;dateTo.value=value.date_to;},{immediate:true});
watch([manualMode,sourceOptions],()=>{if(manualMode.value)source.value='manual';else if(!sourceOptions.value.some(item=>item.value===source.value))source.value='';},{immediate:true});
onMounted(()=>{void owner.ensureMeta();});
</script>
<template>
  <div class="registration-vue-page" :data-view="state.view">
    <section v-show="launch" class="registration-launch">
      <dl class="registration-summary" aria-label="注册与本地邮箱概览">
        <div v-for="item in inventoryMetrics" :key="item.label">
          <dt>{{ item.label }}</dt>
          <dd>{{ typeof item.value === 'number' ? item.value.toLocaleString('zh-CN') : item.value }}</dd>
        </div>
      </dl>

      <section class="registration-launch-panel" aria-labelledby="registration-launch-title">
        <h2 id="registration-launch-title">新建注册批次</h2>
        <form novalidate @submit.prevent="start">
          <div class="registration-launcher">
            <label>邮箱来源
              <select v-model="source" :disabled="!state.meta||manualMode||!sourceOptions.length"
                :aria-describedby="launchHint ? 'registration-launch-hint registrationEmailSupplyHint' : 'registrationEmailSupplyHint'">
                <option value="">请选择本次邮箱来源</option>
                <option v-for="item in sourceOptions" :key="String(item.value)" :value="String(item.value)">{{ item.label||item.value }}</option>
              </select>
            </label>
            <label>注册数量<input v-model.number="count" min="1" type="number" inputmode="numeric"></label>
            <label>并发线程<input v-model.number="workers" min="1" step="1" type="number" inputmode="numeric"></label>
            <label class="registration-debug"><input v-model="debug" type="checkbox"> 调试模式</label>
            <button type="submit" class="registration-start" :disabled="state.creating||confirmingStart||!source||Boolean(launchBlock)"
              :title="launchBlock||undefined">{{ state.creating ? '提交中…' : '开始注册' }}</button>
          </div>
          <p class="registration-hint registration-hint-bar">
            <span v-if="launchHint" id="registration-launch-hint" class="registration-hint-badge" :class="{'registration-warning':launchBlock}" role="status">{{ launchHint }}</span>
            <button v-if="state.metaError" type="button" class="ui-link" data-registration-source-retry @click="owner.ensureMeta(true)">重试</button>
            <span id="registrationEmailSupplyHint" class="registration-supply-note">{{ supplyHint }}</span>
          </p>
        </form>
      </section>

      <RegistrationBatchPanel v-if="launch" :batch="state.batch" :batches="state.batches" :batch-id="state.batchId"
        :refresh-generation="state.batchRefreshGeneration"
        :active="owner.active.value" :loading="state.loading" :error="state.error" :actions="owner.batchActions.value"
        :mutating="Object.keys(state.pendingActions).length > 0" :status-label="statusLabel" :source-label="sourceLabel"
        :driver-label="driverLabel" :read-progress="owner.readBatchProgress" @select="chooseBatch" @refresh="owner.load()" @batch-action="action($event)"
        @retry="action('retry',$event)" @log="owner.openLog"/>
    </section>
    <section v-show="tasks" class="ui-list registration-tasks">
      <div class="ui-list-toolbar registration-count-row" data-registration-count-row>
        <div class="ui-list-toolbar__main registration-count-main">
          <span class="ui-list-count registration-count">共 {{state.total.toLocaleString()}} 条任务</span>
          <span v-if="selected.size" class="registration-selection" role="status">已选 {{selected.size}} 项</span>
          <ListFilterSummary :items="filterChips" @remove="changeFilter($event as FilterKey,'')"/>
        </div>
        <div class="ui-list-toolbar__actions registration-count-actions">
          <div class="registration-toolbar" role="group" aria-label="注册任务操作"><button type="button" class="ui-button registration-toolbar-bulk" :class="{'is-idle':!selected.size}" @click="action('retryBulk')" :disabled="!selected.size">重试</button><button type="button" class="ui-button ui-button--danger registration-toolbar-bulk" :class="{'is-idle':!selected.size}" @click="action('deleteBulk')" :disabled="!selected.size">删除</button><button type="button" class="ui-button" @click="action('cancelAll')">取消排队</button><button type="button" class="ui-button" @click="queryLoad">刷新</button></div>
          <button type="button" class="ui-link" aria-label="恢复注册任务列宽" @click="resetColumns">恢复列宽</button>
          <span class="registration-mobile-filter"><RegistrationFilters :values="filterValues" :sources="filterSourceOptions" :open="openFilter==='all'" @update:open="openFilter=$event?'all':null" @change="changeFilter"/></span>
          <button v-if="filterChips.length" type="button" class="ui-link" @click="resetFilters">清筛</button>
        </div>
      </div>
      <div v-if="state.error" class="ui-list-feedback is-error registration-list-error" role="alert">{{state.error}} <button type="button" class="ui-link" @click="queryLoad">重试</button></div>
      <div class="ui-table-scroll registration-table-wrap" tabindex="0" aria-label="注册任务列表，可横向滚动"><table class="ui-table ui-table--sticky-end registration-table" :style="{'--ui-table-width':`${columnWidths.total.value}px`}"><colgroup><col v-for="(width,index) in columnWidths.widths.value" :key="index" :style="{width:`${width}px`}"></colgroup><thead><tr><th v-for="(header,index) in headers" :key="header.label" :class="{'ui-col-check':index===0}"><input v-if="index===0" type="checkbox" aria-label="选择本页可操作任务" @change="toggleAll"><RegistrationFilters v-else-if="header.filter" :column="header.filter" :values="filterValues" :sources="filterSourceOptions" :open="openFilter===header.filter" @update:open="openFilter=$event?header.filter:null" @change="changeFilter"/><span v-else>{{header.label}}</span><ColumnResizer v-if="index<headers.length-1" :label="header.label" @start="columnWidths.resize(index,$event)" @nudge="columnWidths.resizeWithKeyboard(index,$event)"/></th></tr></thead>
        <tbody><TableState v-if="state.loading || !rows.length" :colspan="11" :loading="state.loading" loading-title="正在加载任务…" title="暂无匹配任务"/>
        <tr v-for="job in rows" :key="String(job.id)" :class="{'is-selected':selected.has(String(job.id))}"><td class="ui-col-check"><input type="checkbox" :aria-label="`选择任务 ${job.id}`" :checked="selected.has(String(job.id))" :disabled="['running','stopping'].includes(String(job.status))" @change="toggle(job.id,$event)"></td>
         <td><ListCell :text="`#${job.id}`" :secondary="job.parent_job_id?`↳ #${job.parent_job_id}`:undefined"/></td><td class="registration-col-email"><ListCell :text="String(job.email||'—')" :title="job.email?String(job.email):undefined"/></td><td><ListCell :text="sourceLabel(job.email_source)"/></td><td><ListCell :text="driverLabel(job.registration_driver)"/></td>
         <td><ListCell :text="displayProxy(job)" :secondary="String(job.proxy_status||'')"/></td><td><span class="ui-badge registration-status-badge" :class="`ui-badge--${statusTone(job)}`" :title="statusLabel(job.debug_state==='paused'?'debug_paused':job.display_status||job.status)">{{statusLabel(job.debug_state==='paused'?'debug_paused':job.display_status||job.status)}}</span></td><td><ListCell class="ui-time" :text="dateTimeLines(job.started_at).text" :secondary="dateTimeLines(job.started_at).secondary" :title="formatDateTime(job.started_at)"/></td><td><ListCell class="ui-time" :text="dateTimeLines(job.completed_at).text" :secondary="dateTimeLines(job.completed_at).secondary" :title="formatDateTime(job.completed_at)"/></td>
         <td><ListResult v-if="job.error_message||job.error_info" data-registration-result :label="errorSummary(job)" :title="String(job.error_message||errorSummary(job))" tone="danger"><template #details><p>{{job.error_message||errorSummary(job)}}</p><p v-if="job.error_info">{{job.error_info}}</p></template></ListResult><ListCell v-else text="—"/></td>
         <td class="registration-row-actions"><div class="ui-row-actions registration-row-actions-inner"><button type="button" class="ui-link" @click="owner.openLog(job.id)">日志</button><template v-if="job.manual_otp_required&&job.status==='running'"><input v-model="otpValues[String(job.id)]" class="registration-otp-input" placeholder="邮箱验证码"><button type="button" class="ui-button registration-otp-btn" @click="submitOtp(job)">提交验证码</button></template><button v-if="['pending','running','stopping'].includes(String(job.status))" type="button" class="ui-link ui-link--danger" @click="action('stop',job)">停止</button><button v-if="job.retryable" type="button" class="ui-link" @click="action('retry',job)">重试</button><button type="button" class="ui-link ui-link--danger" :disabled="['running','stopping'].includes(String(job.status))" @click="action('delete',job)">删除</button></div></td>
        </tr></tbody></table></div>
      <ListPagination label="注册任务分页" :page="page" :size="size" :total="state.total" :busy="state.loading" @update:page="page=$event;owner.load(applyFilterParams())" @update:size="size=$event;page=1;owner.load(applyFilterParams())"/>
    </section>
    <div v-if="state.receipt" class="registration-receipt" :class="`is-${state.receipt.tone}`" role="status">{{ state.receipt.message }}</div>
    <dialog ref="logDialog" class="registration-dialog registration-log-dialog" aria-labelledby="registration-log-title" @cancel.prevent="owner.closeDetail" @close="owner.closeDetail" @click="logBackdrop">
     <header>
       <div class="registration-dialog-title">
         <h2 id="registration-log-title">任务 #{{state.detail.id}} 日志</h2>
         <template v-if="state.detail.job">
           <span v-if="state.detail.job.email" class="registration-dialog-email" :title="String(state.detail.job.email)">{{state.detail.job.email}}</span>
           <span class="ui-badge registration-status-badge" :class="`ui-badge--${statusTone(state.detail.job)}`">{{statusLabel(state.detail.job.debug_state==='paused'?'debug_paused':state.detail.job.display_status||state.detail.job.status)}}</span>
         </template>
       </div>
       <button type="button" class="ui-button registration-dialog-close" @click="owner.closeDetail">关闭</button>
     </header>
     <div class="registration-dialog-body">
       <p v-if="state.detail.loading" class="registration-dialog-status">加载中…</p>
       <p v-if="state.detail.error" class="registration-dialog-error" role="alert">{{state.detail.error}}</p>
       <pre class="registration-dialog-log">{{state.detail.log||'（暂无日志）'}}</pre>
       <div v-if="state.detail.debug?.enabled" class="registration-dialog-section">
         <strong>网络调试</strong>
         <div class="registration-dialog-actions">
           <button type="button" class="ui-button" :disabled="state.detail.comparing" @click="compareDebug">与同批成功任务对比</button>
           <a class="ui-link" :href="`/api/jobs/${state.detail.id}/debug/har`" download>下载脱敏 HAR</a>
           <button type="button" class="ui-button ui-button--primary" @click="owner.action(`/api/jobs/${state.detail.id}/debug/release`,{action:'finish'})">结束调试并收口</button>
         </div>
         <pre v-if="state.detail.comparison">{{typeof state.detail.comparison === 'object' ? JSON.stringify(state.detail.comparison, null, 2) : state.detail.comparison}}</pre>
         <p v-if="state.detail.compareError" class="registration-dialog-error" role="alert">{{state.detail.compareError}}</p>
       </div>
       <div v-if="state.detail.diagnostics?.captured" class="registration-dialog-section">
         <strong>失败诊断</strong>
         <a v-if="state.detail.diagnostics.screenshot_url" class="ui-link" :href="String(state.detail.diagnostics.screenshot_url)" target="_blank" rel="noopener">打开失败截图</a>
         <details class="registration-dialog-details"><summary>完整诊断证据</summary><pre>{{ typeof state.detail.diagnostics === 'object' ? JSON.stringify(state.detail.diagnostics, null, 2) : state.detail.diagnostics }}</pre></details>
       </div>
     </div>
    </dialog>
  </div>
</template>
