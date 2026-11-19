<script setup lang="ts">
import {nextTick,onBeforeUnmount,ref,watch} from 'vue';
import type {AccountActionContext} from './useAccounts';
import {inspectionFailureLabel,inspectionScopeLabel,inspectionStatusLabel,useAccountInspection,type AccountInspectionDependencies,type InspectionDialog,type InspectionRow} from './useAccountInspection';
const props=defineProps<{deps:AccountInspectionDependencies}>();
const view=useAccountInspection(props.deps);
const {startOpen,historyOpen,failuresOpen,archived,workers,starting,startError,historyPage,failurePage,failureId,historyRows,failureRows,historyTotal,failureTotal,historyReady,failureReady,failureError,historyLabel,failureLabel}=view;
const start=ref<HTMLDialogElement>(),history=ref<HTMLDialogElement>(),failures=ref<HTMLDialogElement>();
const historyContent=ref<HTMLElement>(),failureContent=ref<HTMLElement>();
const triggers=new Map<InspectionDialog,HTMLElement|null>();
const handledCloseEvents:Record<InspectionDialog,number>={start:0,history:0,failures:0};
const dialogs={start,history,failures};
const opened={start:startOpen,history:historyOpen,failures:failuresOpen};
let disposed=false;
function remember(kind:InspectionDialog,trigger?:HTMLElement|null){if(!opened[kind].value)triggers.set(kind,trigger??(document.activeElement instanceof HTMLElement?document.activeElement:null));}
function openStart(context:AccountActionContext,trigger?:HTMLElement|null){remember('start',trigger);view.openStart(context);void syncDialog('start');}
function openHistory(trigger?:HTMLElement|null){remember('history',trigger);view.openHistory();void syncDialog('history');}
function openFailures(id:number,trigger?:HTMLElement|null){remember('failures',trigger);view.openFailures(id);void syncDialog('failures');}
function finishClose(kind:InspectionDialog){
  view.close(kind);
  const trigger=triggers.get(kind);triggers.delete(kind);
  if(disposed)return;
  const fallback=history.value?.open?history.value.querySelector<HTMLElement>('button:not([disabled])'):props.deps.fallbackFocus?.();
  (trigger?.isConnected?trigger:fallback)?.focus({preventScroll:true});
}
function closed(kind:InspectionDialog){if(handledCloseEvents[kind]){--handledCloseEvents[kind];return;}if(dialogs[kind].value?.open)return;finishClose(kind);}
function closeNative(kind:InspectionDialog){const dialog=dialogs[kind].value;if(!dialog?.open)return;++handledCloseEvents[kind];dialog.close();finishClose(kind);}
function close(kind?:InspectionDialog){view.close(kind);for(const name of ['failures','history','start'] as const){if(!kind||kind===name)closeNative(name);}}
async function syncDialog(kind:InspectionDialog){await nextTick();const dialog=dialogs[kind].value,value=opened[kind].value;if(!dialog||disposed)return;if(value&&!dialog.open){if(!triggers.has(kind))triggers.set(kind,document.activeElement instanceof HTMLElement?document.activeElement:null);dialog.showModal();}else if(!value&&dialog.open)closeNative(kind);}
for(const kind of ['start','history','failures'] as const){
  watch(opened[kind],()=>syncDialog(kind),{flush:'post'});
}
// Vue keeps the scroll containers alive on same-view refreshes; only page/ID changes reset offsets.
watch(historyPage,()=>{if(historyContent.value){historyContent.value.scrollTop=0;const scroll=historyContent.value.querySelector<HTMLElement>('[data-inspection-scroll]');if(scroll)scroll.scrollLeft=0;}});
watch([failurePage,failureId],()=>{if(failureContent.value){failureContent.value.scrollTop=0;const scroll=failureContent.value.querySelector<HTMLElement>('[data-inspection-scroll]');if(scroll)scroll.scrollLeft=0;}});
function task(row:InspectionRow){close('history');void props.deps.openTask(Number(row.task_id));}
function failureCount(row:InspectionRow){return Number(row.live_failed_count||0)+Number(row.deactivated_skipped_count||0);}
onBeforeUnmount(()=>{disposed=true;for(const dialog of Object.values(dialogs)){if(dialog.value?.open)dialog.value.close();}triggers.clear();});
defineExpose({openStart,openHistory,openFailures,close,refreshHistory:view.refreshHistory,refreshFailures:view.refreshFailures,changeHistoryPage:view.changeHistoryPage,changeFailuresPage:view.changeFailuresPage,stop:view.stop});
</script>
<template>
  <dialog ref="start" class="proxy-traffic-detail-dialog ac-inspection" id="accountInspectionStart" aria-labelledby="accountInspectionStartTitle" :data-archived="archived" @close="closed('start')">
    <div class="modal-header"><h2 id="accountInspectionStartTitle">启动账号巡检</h2><button type="button" class="jobs-tb-btn" aria-label="关闭启动巡检" @click="close('start')">关闭</button></div>
    <form @submit.prevent="view.submit">
      <p id="accountInspectionScope">本次范围：{{ inspectionScopeLabel(archived) }}</p>
      <p>该归档范围内全部账号，不限当前页，不受勾选、搜索或其他筛选条件影响。</p>
      <p>已废账号跳过；AT 本地有效则结束；失效时自动刷新，再复用登录会话查套餐。</p>
      <label for="accountInspectionWorkers">并发账号数</label>
      <input id="accountInspectionWorkers" v-model="workers" type="number" min="1" max="16" step="1" required>
      <p>支持 1–16；实际并发同时受共享账号操作预算限制。</p>
      <p id="accountInspectionStartError" role="status">{{ startError }}</p>
      <button type="submit" class="jobs-tb-btn jobs-tb-btn--primary" id="btnConfirmAccountInspection" :disabled="starting">开始巡检</button>
    </form>
  </dialog>
  <dialog ref="history" class="proxy-traffic-detail-dialog ac-inspection" id="accountInspectionHistory" aria-labelledby="accountInspectionHistoryTitle" @close="closed('history')">
    <div class="modal-header"><h2 id="accountInspectionHistoryTitle">账号巡检历史</h2><button type="button" class="jobs-tb-btn" @click="view.refreshHistory">刷新</button><button type="button" class="jobs-tb-btn" @click="close('history')">关闭</button></div>
    <p>每 5 秒刷新。进度包含跳过；完成表示本轮处理结束，查活和套餐结果分别统计。</p>
    <div ref="historyContent" id="accountInspectionHistoryContent" aria-live="polite">
      <div v-if="historyRows.length" data-inspection-scroll tabindex="0" role="region" aria-label="可左右滚动查看巡检记录"><table class="data-table"><thead><tr><th v-for="label in ['任务','范围','状态 / 时间','并发','进度','AT失效','查活 成功/失败','套餐 成功/失败','操作']" :key="label" scope="col">{{ label }}</th></tr></thead><tbody>
        <tr v-for="(row,index) in historyRows" :key="String(row.id??index)">
          <td><button type="button" class="jobs-tb-btn" :data-inspection-task="Number(row.id)" @click="task(row)">#{{ Number(row.id) }}</button></td>
          <td>{{ inspectionScopeLabel(String(row.archived)) }}</td><td>{{ inspectionStatusLabel(row.status) }}<div class="sub-cell">{{ deps.formatDateTime(row.created_at) }}</div></td><td>{{ Number(row.workers) }}</td>
          <td>{{ Number(row.checked_count)+Number(row.skipped_count) }} / {{ Number(row.total_count) }}<div class="sub-cell">跳过 {{ Number(row.skipped_count) }}（已废 {{ Number(row.deactivated_skipped_count) }}）</div></td><td>{{ Number(row.invalid_count) }}</td>
          <td>{{ Number(row.live_success_count) }} / {{ Number(row.live_failed_count) }}<div v-if="failureCount(row)"><button type="button" class="jobs-tb-btn" @click="openFailures(Number(row.id),$event.currentTarget as HTMLElement)">失败详情 {{ failureCount(row) }}</button></div></td>
          <td>{{ Number(row.plan_success_count) }} / {{ Number(row.plan_failed_count) }}</td><td><button v-if="row.status==='running'" type="button" class="jobs-tb-btn" @click="view.stop(Number(row.id))">停止</button></td>
        </tr>
      </tbody></table></div>
      <p v-else>{{ historyReady?'暂无巡检记录。':'正在读取巡检历史…' }}</p>
    </div>
    <div class="jobs-v2-pager"><button type="button" class="jobs-tb-btn" id="accountInspectionPrev" :disabled="historyPage<=1" @click="view.changeHistoryPage(-1)">上一页</button><span id="accountInspectionPageLabel">{{ historyLabel }}</span><button type="button" class="jobs-tb-btn" id="accountInspectionNext" :disabled="historyPage*20>=historyTotal" @click="view.changeHistoryPage(1)">下一页</button></div>
  </dialog>
  <dialog ref="failures" class="proxy-traffic-detail-dialog ac-inspection" id="accountInspectionFailures" aria-labelledby="accountInspectionFailuresTitle" @close="closed('failures')">
    <div class="modal-header"><h2 id="accountInspectionFailuresTitle">{{ failureId?`巡检 #${failureId} · 失败详情`:'巡检失败详情' }}</h2><button type="button" class="jobs-tb-btn" @click="view.refreshFailures">刷新</button><button type="button" class="jobs-tb-btn" @click="close('failures')">关闭</button></div>
    <p>保留本轮原始执行快照，后续重跑或删除账号不会改写；含已废跳过，套餐单独失败不计为查活失败。</p>
    <div ref="failureContent" id="accountInspectionFailuresContent" aria-live="polite">
      <p v-if="failureError">{{ failureError }}</p>
      <div v-else-if="failureRows.length" data-inspection-scroll tabindex="0" role="region" aria-label="可左右滚动查看巡检记录"><table class="data-table"><thead><tr><th v-for="label in ['账号','邮箱','类型','时间','原因']" :key="label" scope="col">{{ label }}</th></tr></thead><tbody><tr v-for="(row,index) in failureRows" :key="String(row.account_id??index)"><td>#{{ Number(row.account_id) }}</td><td>{{ row.email }}</td><td>{{ inspectionFailureLabel(row.status) }}</td><td>{{ deps.formatDateTime(row.failed_at) }}</td><td class="inspection-error-reason">{{ row.error }}</td></tr></tbody></table></div>
      <p v-else>{{ failureReady?'本轮暂无查活失败或已废跳过。':'正在读取本次失败记录…' }}</p>
    </div>
    <div class="jobs-v2-pager"><button type="button" class="jobs-tb-btn" id="accountInspectionFailuresPrev" :disabled="!failureReady||failurePage<=1" @click="view.changeFailuresPage(-1)">上一页</button><span id="accountInspectionFailuresPageLabel">{{ failureLabel }}</span><button type="button" class="jobs-tb-btn" id="accountInspectionFailuresNext" :disabled="!failureReady||failurePage*20>=failureTotal" @click="view.changeFailuresPage(1)">下一页</button></div>
  </dialog>
</template>
<style scoped>
.ac-inspection{padding:20px;max-height:88dvh;overflow:auto}
#accountInspectionHistory,#accountInspectionFailures{width:min(1180px,calc(100vw - 28px))}
.modal-header{display:flex;align-items:center;gap:10px}.modal-header h2{flex:1;font-size:18px;margin:0}
p{color:var(--ui-color-text-secondary);line-height:1.65;font-size:13px}
#accountInspectionWorkers{display:block;margin:8px 0;width:100%;padding:9px}
#accountInspectionStartError{color:var(--ui-color-danger)}
#accountInspectionHistoryContent,#accountInspectionFailuresContent{overflow:auto}
[data-inspection-scroll]{overflow-x:auto}[data-inspection-scroll] table{width:100%;min-width:800px;border-collapse:collapse;font-size:13px}
th,td{padding:10px;text-align:left;border-bottom:1px solid var(--ui-color-border)}td{vertical-align:top}
.inspection-error-reason{min-width:240px;max-width:460px;white-space:pre-wrap;overflow-wrap:anywhere}
#accountInspectionFailures td:nth-child(2){max-width:230px;overflow-wrap:anywhere}button{min-height:34px}
@media(max-width:640px){.ac-inspection{padding:14px}}
</style>
