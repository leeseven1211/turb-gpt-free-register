<script setup lang="ts">
import {computed,nextTick,ref,watch} from 'vue';
import {AlertDialogRoot,AlertDialogPortal,AlertDialogOverlay,AlertDialogContent,AlertDialogTitle,AlertDialogDescription,AlertDialogCancel} from 'reka-ui';
import type {BulkDetailDependencies,BulkNavigation} from './contracts';
import {object,label,number,operationKey,operationLabel,badgeClass,badgeTone} from './bulkDetailPresentation';
import {useBulkDetail} from './useBulkDetail';
import CursorPagination from '../../components/CursorPagination.vue';
import ListFilterSummary from '../../components/ListFilterSummary.vue';
import BulkReportView from './BulkReportView.vue';
import BulkTargets from './BulkTargets.vue';
import BulkBusinessStats from './BulkBusinessStats.vue';
const props=withDefaults(defineProps<{navigation:BulkNavigation;deps:BulkDetailDependencies;visible?:boolean}>(),{visible:undefined});
const state=useBulkDetail(()=>props.navigation,props.deps,props.visible??props.navigation.view==='detail');
const {navigation,detail,targets,report,reportOpen,rounds,roundsCursor,selected,pendingRound,loading,targetsLoading,reportLoading,roundsLoading,writing,error,targetError,reportError,actionError,confirmation,counts,ended,paused,hasReport,hasPrevious,nextCursor}=state;
const batchName=computed(()=>detail.value?.name||detail.value?.title||'批次详情');
const targetTable=ref<InstanceType<typeof BulkTargets>|null>(null),reportRegion=ref<HTMLElement|null>(null),retryChoice=ref('failed');
const completedCount=computed(()=>['success','partial_success','failed','not_executed','cancelled'].reduce((n,key)=>n+(counts.value[key]||0),0));
const activeCount=computed(()=>['pending_submit','waiting_account','queued','running','waiting'].reduce((n,key)=>n+(counts.value[key]||0),0));
const selectedRound=computed(()=>rounds.value.find(round=>round.id===navigation.value.round_id));
const canCopyQuery=computed(()=>Boolean(object(detail.value?.selection_summary).query||detail.value?.query_spec||object(detail.value?.selection).query_spec));
const filters=['running','queued','success','failed','partial_success','pending_submit','waiting_account','waiting','not_executed','cancelled'];
const filterChips=computed(()=>navigation.value.result_state?[{key:'result_state',label:`结果状态：${label(navigation.value.result_state)}`,title:`结果状态：${label(navigation.value.result_state)}`,removeLabel:'清除结果状态筛选'}]:[]);
const retryOptions=[['failed','失败'],['partial_success','部分成功'],['not_executed','未执行'],['cancelled','已取消'],['unsuccessful','全部未成功']];
const controlActions=[['pause','暂停批次','pause'],['resume','继续批次','resume'],['cancel_not_started','取消排队账号','cancel'],['request_stop','停止正在执行','stop']];
let confirmationTrigger:HTMLElement|null=null;
function rememberTrigger(event:Event){confirmationTrigger=event.currentTarget as HTMLElement;}
async function retry(checked:boolean,event:Event){rememberTrigger(event);await state.retry(checked,retryChoice.value);}
async function control(action:string,event:Event){rememberTrigger(event);await state.control(action);}
function restoreFocus(event:Event) {event.preventDefault();const trigger=confirmationTrigger;confirmationTrigger=null;void nextTick(()=>{if(trigger?.isConnected&&!trigger.hasAttribute('disabled')&&!trigger.closest('[hidden],[inert]')){let node:HTMLElement|null=trigger;while(node){if(getComputedStyle(node).display==='none'||getComputedStyle(node).visibility==='hidden')return;node=node.parentElement;}trigger.focus({preventScroll:true});}});}
async function showReport(){
  const pending=state.openReport();
  await nextTick();
  if(reportRegion.value){reportRegion.value.focus({preventScroll:true});reportRegion.value.scrollIntoView?.({block:'start'});}
  await pending;
}
function setVisible(visible:boolean){state.setVisible(visible);if(!visible){targetTable.value?.close();confirmationTrigger=null;}}
watch(()=>props.visible,value=>{if(value!==undefined)setVisible(value);},{flush:'sync'});
watch(()=>[navigation.value.batch_id,navigation.value.round_id,navigation.value.result_state,navigation.value.view],()=>{targetTable.value?.close();confirmationTrigger=null;});
defineExpose({batchName,refresh:state.refresh,showReport,setVisible,needsRefresh:state.needsPolling});
</script>
<template>
  <div class="bulk-detail-owner" :aria-busy="loading">
    <p v-if="error" class="bulk-error" role="alert">{{error}} <button type="button" class="bulk-link" @click="state.refresh(true)">重试读取批次</button></p>
    <section v-if="detail" class="bulk-card bulk-overview">
      <div class="bulk-detail-toolbar">
        <div class="bulk-detail-meta">
          <span class="ui-badge bulk-badge" :class="`ui-badge--${badgeTone(paused?'paused':object(detail.control).state||detail.control_state||detail.state)}`">{{label(paused?'paused':object(detail.control).state||detail.control_state||detail.state)}}</span>
          <span>{{operationLabel(operationKey(detail))}}</span>
          <span>创建于 {{deps.callbacks.formatDateTime(detail.created_at)}}</span>
          <details class="bulk-settings bulk-detail-settings">
            <summary>范围与设置</summary>
            <dl>
              <dt>名单生成</dt><dd>{{deps.callbacks.formatDateTime(object(detail.selection_summary).selection_at||detail.selection_at)}}</dd>
              <dt>配置版本</dt><dd>{{object(detail.effective_settings).config_revision||detail.config_revision||'—'}}</dd>
              <dt>结果更新</dt><dd>{{deps.callbacks.formatDateTime(detail.projected_at)}}</dd>
            </dl>
          </details>
          <span v-if="object(detail.projection).state && object(detail.projection).state!=='current'" class="bulk-projection-note">汇总同步中</span>
        </div>
        <div class="bulk-actions">
          <label class="bulk-round-picker">
            <span class="bulk-sr-only">结果视图</span>
            <select :value="navigation.round_id||'current'" aria-label="结果视图" @change="state.setRound(($event.target as HTMLSelectElement).value)">
              <option value="current">当前结果</option>
              <option v-for="round in rounds" :key="String(round.id)" :value="String(round.id)">{{Number(round.round_no)===1?'首轮':'重跑 '+(Number(round.round_no)-1)}} · {{label(round.state)}} · {{round.target_count==null?'准备中':number(round.target_count)+' 个'}}</option>
              <option v-if="navigation.round_id&&!selectedRound" :value="navigation.round_id">所选轮次 #{{navigation.round_id}}</option>
            </select>
          </label>
          <button type="button" class="jobs-tb-btn" data-bulk-action="more-rounds" :disabled="!roundsCursor||roundsLoading" @click="state.moreRounds">更多轮次</button>
          <button v-if="hasReport" type="button" class="jobs-tb-btn" data-bulk-action="view-report" @click="showReport">查看报告</button>
          <button type="button" class="jobs-tb-btn" data-bulk-action="copy-targets" @click="state.copyBatch(true)">同一名单再次执行</button>
          <button type="button" class="jobs-tb-btn" data-bulk-action="copy-query" :disabled="!canCopyQuery" @click="state.copyBatch(false)">复制条件新建</button>
        </div>
      </div>
      <div class="bulk-control-strip">
        <div class="bulk-control-copy">
          <p class="bulk-view-note">
            <strong>已结束 {{number(completedCount)}} / {{number(detail.target_count)}} 个</strong>
            <span v-if="hasReport && reportOpen && !ended && !paused">{{number(activeCount)}} 个进行中</span>
            <span v-if="selectedRound?.completion_reason==='cancelled_before_freeze'">本轮在名单生成前取消，当前结果未改变。</span>
            <span v-else-if="navigation.round_id">仅展示该轮名单及执行结果。</span>
            <span v-else>每个账号保留最近一轮结果</span>
          </p>
          <p v-if="paused && !ended" class="bulk-view-note">未开始的账号等待继续，已开始的账号继续收尾。</p>
        </div>
        <div class="bulk-actions" role="group" aria-label="运行控制">
          <button v-for="[action,title,selector] in controlActions" :key="action" type="button" class="jobs-tb-btn" :class="{'jobs-tb-btn--danger':['cancel','stop'].includes(selector!)}" :data-bulk-action="selector" :disabled="state.controlDisabled(action!)" @click="control(action!,$event)">{{title}}</button>
        </div>
      </div>
      <template v-if="!hasReport || !reportOpen"><div class="bulk-summary-grid"><div class="bulk-summary-item"><span>账号总数</span><strong>{{number(detail.target_count)}}</strong></div><div class="bulk-summary-item"><span>进行中</span><strong>{{activeCount}}</strong></div><div class="bulk-summary-item is-success"><span>成功</span><strong>{{counts.success||0}}</strong></div><div class="bulk-summary-item is-warning"><span>未成功</span><strong>{{state.retryCount('unsuccessful')}}</strong></div></div><BulkBusinessStats :metrics="detail.business_summary||detail.metrics"/></template>
    </section>
    <section v-if="hasReport && reportOpen" ref="reportRegion" data-bulk-plan-report class="bulk-report-target" tabindex="-1" role="region" aria-label="批次报告" :aria-busy="reportLoading">
      <BulkReportView :operation-key="operationKey(detail)" :report="report" :error="reportError?'读取报告失败：'+reportError:''" :format-date-time="deps.callbacks.formatDateTime" :on-retry="()=>state.refreshReport(true)" :loading="reportLoading"/>
    </section>
    <section class="bulk-card bulk-results-card"><div class="bulk-results-heading"><h3>账号明细 <span>{{selected.size?'已选 '+selected.size+' 个（可跨页）':''}}</span><button type="button" class="bulk-link" :disabled="!selected.size" @click="state.clearSelection">清空选择</button></h3><div class="bulk-retry-toolbar"><select v-model="retryChoice" aria-label="重跑范围"><option v-for="[value,title] in retryOptions" :key="value" :value="value">{{title}}</option></select><button type="button" class="jobs-tb-btn jobs-tb-btn--primary" data-bulk-action="retry" :disabled="writing||!!confirmation||!state.retryCount(retryChoice)" @click="retry(false,$event)">重跑{{retryOptions.find(option=>option[0]===retryChoice)?.[1]}} ({{state.retryCount(retryChoice)}})</button><button type="button" class="jobs-tb-btn" data-bulk-action="retry-selected" :disabled="writing||!!confirmation||!selected.size" @click="retry(true,$event)">重跑勾选{{selected.size?' ('+selected.size+')':''}}</button></div></div>
      <p v-if="actionError" class="bulk-error" role="alert">{{actionError}}</p><p v-if="pendingRound" class="bulk-notice" role="status">重跑已受理，正在准备新轮次 #{{pendingRound}}。</p>
      <div class="bulk-target-count-row" data-bulk-target-count-row><span class="bulk-target-count" role="status">共 {{number(detail?.target_count)}} 个账号 · 当前页 {{targets?.items.length||0}} 个</span><ListFilterSummary :items="filterChips" @remove="state.setFilter('')"/></div>
      <BulkTargets ref="targetTable" :scope="[navigation.batch_id,navigation.round_id,navigation.result_state,navigation.cursor].join(':')" :items="targets?.items||[]" :selected="selected" :loading="targetsLoading||loading&&!detail" :error="targetError" :result-state="navigation.result_state||''" :result-counts="counts" :result-total="detail?.target_count" :result-states="filters" :open-task="deps.callbacks.openTask" @filter="state.setFilter" @toggle="state.toggleTarget" @select-page="state.selectPage" @retry="state.loadTargets"/>
      <CursorPagination :has-previous="hasPrevious" :next-cursor="nextCursor" :item-count="targets?.items.length||0" :has-cursor="!!navigation.cursor" :busy="targetsLoading" label="账号明细分页" @next="state.next" @previous="state.previous" @first="state.first"/>
    </section>
    <AlertDialogRoot :open="!!confirmation" @update:open="open=>{if(!open)state.cancelConfirmation()}"><AlertDialogPortal><AlertDialogOverlay class="bulk-vue-overlay"/><AlertDialogContent class="bulk-vue-dialog" @escape-key-down="event=>{event.preventDefault();state.cancelConfirmation()}" @close-auto-focus="restoreFocus"><AlertDialogTitle>{{confirmation?.title}}</AlertDialogTitle><AlertDialogDescription>{{confirmation?.description}}</AlertDialogDescription><p>范围：{{confirmation?.scopeLabel}} · 预计账号：{{confirmation?.count}} 个</p><div class="bulk-vue-dialog-actions"><AlertDialogCancel class="jobs-tb-btn" data-confirm-cancel @click="state.cancelConfirmation">返回</AlertDialogCancel><button type="button" class="jobs-tb-btn jobs-tb-btn--danger" data-confirm-submit @click="state.confirm">{{confirmation?.label}}</button></div></AlertDialogContent></AlertDialogPortal></AlertDialogRoot>
  </div>
</template>
<style scoped>
.bulk-detail-toolbar{padding:12px;border:1px solid var(--ui-color-border);border-radius:var(--ui-radius-md);background:var(--ui-color-surface-subtle)}
.bulk-control-strip{margin-top:12px;padding:12px;border:1px solid var(--ui-color-border);border-radius:var(--ui-radius-md)}
.bulk-results-heading{border-bottom:1px solid var(--ui-color-border)}
.bulk-detail-owner{min-width:0}.bulk-target-count-row{display:flex;align-items:center;gap:10px;min-width:0;padding:8px 16px}.bulk-target-count{flex:none;font-size:12px;color:var(--ui-color-text-secondary)}.bulk-target-count-row :deep(.list-filter-summary){flex:1}.bulk-results-heading h3{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.bulk-results-heading h3>span{font-size:12px;font-weight:400}.bulk-report-target:focus{outline:2px solid var(--ui-color-brand);outline-offset:4px}@media(max-width:680px){.bulk-target-count-row{padding:8px 10px;gap:6px}.bulk-target-count{max-width:55%;overflow-wrap:anywhere}.bulk-results-heading{flex-wrap:wrap}}
</style>
