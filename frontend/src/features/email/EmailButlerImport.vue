<script setup lang="ts">
import {computed,ref} from 'vue';
import ListResult from '../../components/ListResult.vue';
import {short} from './presentation';
import {providers} from './butlerLabels';
import {useNativeDialog} from './useNativeDialog';
import type {useButlerImport} from './useButlerImport';
const props=defineProps<{owner:ReturnType<typeof useButlerImport>;active:boolean}>(),state=props.owner.state;
const dialog=ref<HTMLDialogElement>();useNativeDialog(dialog,()=>state.open,()=>props.active);
const processed=computed(()=>Number(state.batch?.imported||0)+Number(state.batch?.skipped||0)+Number(state.batch?.failed||0)+Number(state.batch?.unknown||0));
const showRecovery=computed(()=>props.active&&!!state.request&&!state.open&&!['completed','succeeded','done','cancelled'].includes(state.batch?.status||''));
</script>
<template>
 <button v-if="showRecovery" class="em-recovery em-button" aria-label="查看 Butler 导入进度" @click="owner.open()">{{ state.batch?`Butler 导入${owner.isRunning.value?'中':'结果'} · 已导入 ${state.batch.imported||0} / ${state.batch.total||0} · 查看进度`:'Butler 导入请求响应缺失 · 查看进度' }}</button>
 <dialog ref="dialog" class="em-dialog" data-email-butler-import aria-labelledby="emailButlerImportTitle" aria-describedby="emailButlerImportDescription" :aria-busy="state.busy||state.polling" @cancel.prevent="owner.close()" @click="($event.target===dialog)&&owner.close()">
  <div class="em-dialog-head"><div><h3 id="emailButlerImportTitle">从 Butler 导入邮箱</h3><p id="emailButlerImportDescription">{{ state.request?'导入进度会自动保存，可随时关闭窗口。':'从 Butler 分配长期租用的邮箱，加入本地库存后使用。' }}</p></div><button class="em-button" aria-label="关闭 Butler 导入窗口" @click="owner.close()">关闭</button></div>
  <div class="em-dialog-body">
   <div v-if="!state.request" class="em-dialog-fields">
    <label class="em-field">邮箱类型<select aria-label="Butler 邮箱类型" :value="state.filters.provider" :disabled="state.storageError||state.busy" @change="owner.changeFilters({provider:($event.target as HTMLSelectElement).value})"><option v-for="item in state.providers" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
    <label class="em-field">导入数量<input aria-label="Butler 导入数量" type="number" min="1" step="1" inputmode="numeric" :value="state.filters.count" :disabled="state.storageError||state.busy" @input="owner.changeFilters({count:Number(($event.target as HTMLInputElement).value)})"></label>
    <p class="em-help">不足时按预览可用数量导入，确认后由 Butler 分配完整地址。</p>
   </div>
   <p v-if="state.error" class="em-error" role="alert">{{ state.error }}</p>
   <p v-if="!state.request" role="status" aria-live="polite">{{ state.previewing?'正在查询当前可用数量…':owner.availability.value }}</p>
   <section v-if="state.request" class="em-preview" aria-label="Butler 导入结果">
    <h4>{{ owner.batchTitle.value }}</h4>
    <template v-if="state.batch"><progress :max="Math.max(Number(state.batch.total||0),1)" :value="Math.min(processed,Number(state.batch.total||0))" aria-label="邮箱导入进度"/><div class="em-stats"><div v-for="item in [['已导入',state.batch.imported],['待处理',state.batch.pending],['租用中',state.batch.submitting],['已跳过',state.batch.skipped],['失败',Number(state.batch.failed||0)+Number(state.batch.unknown||0)]]" :key="String(item[0])"><strong>{{ item[1]||0 }}</strong><span>{{ item[0] }}</span></div></div><p role="status" aria-live="polite">已处理 {{ processed }} / {{ state.batch.total||0 }} 个，本次请求 {{ state.batch.requested||0 }} 个。</p></template>
    <ListResult :label="short(owner.batchTitle.value)" :title="owner.batchDetails.value" :tone="state.batch?.status==='cancelled'?'neutral':state.batch?.failed?'warning':'active'"><template #details>{{ owner.batchDetails.value }}</template></ListResult>
    <p class="em-help em-preserve-lines">{{ state.batch?.status==='cancelled'?'已停止后续导入，原结果与租约保留。':owner.isRunning.value||state.resumePending?'可以关闭窗口，导入会在后台继续。':state.batch?.can_retry?'可继续原批次处理剩余邮箱，已导入的邮箱会保留。':'已保存原导入记录。' }}</p>
    <small v-if="state.request.filters">来源：{{ providers.find(item=>item.value===state.request?.filters?.provider)?.label||state.request.filters.provider }} · 原请求数量 {{ state.request.filters.count }}</small>
    <small v-if="state.batch">批次：{{ state.batch.batch_id }}</small><small v-if="state.request">原请求：{{ state.request.request_id }}</small>
   </section>
  </div>
  <div class="em-dialog-foot">
   <button class="em-button" @click="owner.close()">{{ owner.isRunning.value||state.resumePending?'关闭，后台继续':'关闭' }}</button>
   <button v-if="owner.canCancel.value" class="em-button em-danger" :disabled="state.busy" @click="owner.cancel()">{{ state.busy?'正在终止…':'终止批次' }}</button>
   <button v-if="owner.canReset.value" class="em-button" :disabled="state.busy||state.polling" @click="owner.reset()">新建导入</button>
   <template v-if="!state.request"><button class="em-button" :disabled="state.busy||state.previewing||state.storageError" @click="owner.preview()">刷新可用数量</button><button class="em-button em-primary" :disabled="state.busy||state.previewing||state.storageError||!state.preview?.selected" @click="owner.apply()">{{ state.preview?.selected?`开始导入 ${state.preview.selected} 个`:'开始导入' }}</button></template>
   <button v-else-if="owner.canRetry.value" class="em-button em-primary" @click="owner.retry()">{{ state.batch?'继续原批次':'重试原请求' }}</button>
  </div>
 </dialog>
</template>
