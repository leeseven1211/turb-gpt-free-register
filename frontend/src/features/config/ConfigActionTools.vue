<script setup lang="ts">
import {computed, onBeforeUnmount, watch} from 'vue';
import type {ConfigDraftOwner} from './contracts';
import type {ConfigActions, PollingAction} from './configActions';
import {formatDateTime} from '../../shared/time';
const props = withDefaults(defineProps<{owner: ConfigDraftOwner; actions: ConfigActions; tool: 'roxy'|'proxy'|'butler'|'sentinel'|'sub2api'|'concurrency'; active?: boolean}>(), {active: true});
const state = computed(() => props.actions.states[props.tool]);
const busy = computed(() => state.value.loading || state.value.posting);
const record = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
const display = (value: unknown, fallback = '—') => typeof value === 'string' || typeof value === 'number' ? String(value) : fallback;
const objects = (value: unknown): Record<string, unknown>[] => Array.isArray(value) ? value.map(record) : [];
const workspaceSelection = computed(() => `${props.owner.readField('ROXY_WORKSPACE_ID') || ''}::${props.owner.readField('ROXY_PROJECT_ID') || ''}`);
function selectWorkspace(event: Event) {
  const selected = props.actions.roxyWorkspaces.value.find(item => `${item.id}::${item.projectId}` === (event.target as HTMLSelectElement).value);
  if (!selected) return;
  props.owner.setField('ROXY_WORKSPACE_ID', selected.id);
  props.owner.setField('ROXY_PROJECT_ID', selected.projectId);
}
function saveWorkspace() {return props.actions.saveRoxySelection(String(props.owner.readField('ROXY_WORKSPACE_ID') || ''), String(props.owner.readField('ROXY_PROJECT_ID') || ''));}
const selectedWorkspace = computed(() => props.actions.roxyWorkspaces.value.some(item => `${item.id}::${item.projectId}` === workspaceSelection.value));
const roxyBlockedField = computed(() => props.tool === 'roxy' ? ['ROXY_WORKSPACE_ID', 'ROXY_PROJECT_ID'].map(key => props.owner.field(key)).find(field => field?.readonly || field?.editable === false) : undefined);
const unavailable = computed(() => roxyBlockedField.value ? roxyBlockedField.value.reason || '当前部署不可编辑 Roxy 团队与项目。' : '');
let observing: PollingAction | undefined;
watch(() => [props.tool, props.active] as const, ([tool, active]) => {
  if (observing) props.actions.setVisible(observing, false);
  observing = tool === 'sentinel' || tool === 'concurrency' ? tool : undefined;
  if (observing) props.actions.setVisible(observing, active);
}, {immediate: true});
onBeforeUnmount(() => {if (observing) props.actions.setVisible(observing, false);});
const candidate = computed(() => record(state.value.snapshot?.candidate));
const builtin = computed(() => record(state.value.snapshot?.builtin));
const comparison = computed(() => ({not_checked: '尚未检查', same: '同当前一致', version_changed: '发现新版本', content_changed: '同版本内容变化', unknown: '暂无法比较'}[display(state.value.snapshot?.comparison)] || '暂无法比较'));
const staticStatus = (value: unknown) => value === 'static_markers_present' ? '通过（未运行验证）' : value === 'needs_adaptation' ? '需要适配' : '尚未检查';
const checkedAt = computed(() => {const seconds = Number(state.value.snapshot?.last_checked_at); return seconds > 0 && Number.isFinite(seconds) ? new Date(seconds * 1000).toLocaleString('zh-CN', {hour12: false}) : '尚未检查';});
const concurrencyTypes = computed(() => objects(state.value.snapshot?.types));
const details = computed(() => ['providers', 'batches', 'remote_orders'].flatMap(key => objects(state.value.snapshot?.[key]).map(item => ({label: display(item.label || item.key || item.id || item.batch_id, '当前'), occupied: item.occupied ?? item.active ?? 0, limit: item.limit ?? '—'}))));
const preview = computed(() => props.actions.states.concurrencyPreview);
const waitReason = (value: unknown) => {
  const item = record(value);
  const code = display(item.code || item.reason || value);
  const count = item.occupied != null && item.limit != null ? `（${item.occupied}/${item.limit}）` : '';
  const labels: Record<string, string> = {
    global_capacity: '等待全局空位', type_capacity: '等待本类空位', batch_capacity: '等待当前批次空位',
    provider_capacity: '等待平台空位', account_busy: '账号正由其他任务使用', email_busy: '邮箱资源忙碌',
    runtime_not_ready: '执行服务尚未就绪', concurrency_policy_migration_required: '等待配置并发迁移策略',
    remote_order_capacity: '等待远端订单名额', not_due: '等待下次平台查询', fairness_turn: '等待公平调度轮次',
    executor_capacity: '等待执行承载空位', resource_capacity: '等待业务资源空位',
    scheduler_store_unavailable: '调度存储暂不可用', permit_owner_lost: '执行许可归属已变化',
    execution_active: '上一执行仍在退出或清理',
  };
  return labels[code] ? labels[code] + count : `调度等待原因未登记（${code || '缺少原因代码'}）`;
};
</script>
<template>
  <div class="config-tool-panel-v2 config-action-tools" :data-config-tool="tool" :aria-busy="busy">
    <template v-if="tool === 'roxy'">
      <strong>团队 / 项目选择</strong>
      <p class="hint">获取已保存连接中的团队与项目，选择后单独保存。</p>
      <div class="config-tool-controls">
        <label>团队 / 项目<select aria-label="团队 / 项目" :value="workspaceSelection" :disabled="busy || !!unavailable" @change="selectWorkspace"><option :value="workspaceSelection" v-if="!selectedWorkspace">当前团队：{{ owner.readField('ROXY_WORKSPACE_ID') || '未设置' }}</option><option v-for="item in actions.roxyWorkspaces.value" :key="`${item.id}::${item.projectId}`" :value="`${item.id}::${item.projectId}`">{{ item.label }}</option></select></label>
        <button type="button" class="btn" data-config-action="load-roxy" :disabled="busy || !!unavailable" @click="actions.loadRoxyWorkspaces()">{{ state.loading ? '正在获取…' : '获取团队' }}</button>
        <button type="button" class="btn primary" data-config-action="save-roxy" :disabled="busy || !selectedWorkspace || !!unavailable" @click="saveWorkspace">{{ state.posting ? '正在保存…' : '保存选择' }}</button>
      </div>
      <p v-if="unavailable" role="status">{{ unavailable }}</p>
    </template>
    <template v-else-if="tool === 'proxy'">
      <strong>代理供应商本地联调</strong><p class="hint">会实际提取并检测 1 个 IP，可能产生少量流量或配额消耗。API 请求会绕过系统代理。</p>
      <button type="button" class="btn" data-config-action="test-proxy" :disabled="busy" @click="actions.testProxy()">{{ busy ? '正在测试…' : '提取并测试 1 个 IP' }}</button>
    </template>
    <template v-else-if="tool === 'butler'">
      <strong>Email Butler 连接与权限</strong><button type="button" class="btn" data-config-action="test-butler" :disabled="busy" @click="actions.testButler()">{{ busy ? '正在检测…' : '测试连接与权限' }}</button>
    </template>
    <template v-else-if="tool === 'sentinel'">
      <strong>Sentinel 检查</strong><p class="hint">手动获取候选资源；不自动切换现用版本。</p>
      <div class="config-tool-controls"><button type="button" class="btn" data-config-action="check-sentinel" :disabled="busy || !!state.snapshot?.running" @click="actions.checkSentinel()">{{ state.posting || state.snapshot?.running ? '检查中…' : '检查 Sentinel 更新' }}</button><button type="button" class="btn" :disabled="busy" @click="actions.refreshSentinel()">刷新状态</button></div>
      <dl class="config-tool-facts"><dt>当前内置版本</dt><dd>{{ display(builtin.version, '读取后显示') }}</dd><dt>发现版本</dt><dd>{{ display(candidate.version, '尚未发现') }}</dd><dt>上次检查时间</dt><dd>{{ checkedAt }}</dd><dt>版本比较</dt><dd>{{ comparison }}</dd><dt>generic 静态检查</dt><dd>{{ staticStatus(candidate.generic_status) }}</dd><dt>Proto2 静态检查</dt><dd>{{ staticStatus(candidate.proto2_status) }}</dd></dl>
    </template>
    <template v-else-if="tool === 'sub2api'">
      <strong>同步与异常巡检</strong><p class="hint">使用已保存配置检查远端异常账号，修复进度可在任务中心查看。</p>
      <div class="config-tool-controls"><button type="button" class="btn" :disabled="busy" @click="actions.refreshSub2Api()">查看状态</button><button type="button" class="btn" data-config-action="check-sub2api" :disabled="busy" @click="actions.checkSub2Api()">立即巡检</button></div>
    </template>
    <template v-else-if="tool === 'concurrency'">
      <strong>并发运行状态</strong>
      <div class="config-tool-controls"><button type="button" class="btn" :disabled="busy" @click="actions.refreshConcurrency()">刷新状态</button><button type="button" class="btn" :disabled="busy" @click="actions.refreshConcurrency({details: true})">查看附加限制</button></div>
      <p v-if="state.snapshot" class="hint">部署范围 {{ display(record(state.snapshot.scope).label || state.snapshot.scope, '当前部署') }} · 策略版本 {{ display(state.snapshot.policy_revision) }} · 观察时间 {{ formatDateTime(state.snapshot.observed_at) }}</p>
      <p class="config-section-v2-subhelp">各类型上限是上限，不预留配额，合计可以超过全局。内部同步刷新 AT、查套餐与后处理归属巡检、提链或注册父任务，复用父任务许可；独立子任务按实际动作重新排队。</p>
      <div v-if="preview.snapshot?.migration_required || state.snapshot?.migration_required" class="config-migration-preview"><p>新策略需要完整保存。历史账号池上限：{{ display(preview.snapshot?.legacy_account_workers, '未记录') }}</p><p v-for="(note, index) in (Array.isArray(preview.snapshot?.notes) ? preview.snapshot.notes : [])" :key="index">{{ display(note, '') }}</p><button type="button" class="btn" :disabled="!preview.snapshot" @click="actions.applyConcurrencyPreview()">填入迁移建议</button><button v-if="preview.error" type="button" class="btn" :disabled="preview.loading" @click="actions.loadConcurrencyPreview()">重试迁移预览</button></div>
      <ul v-if="concurrencyTypes.length" class="config-concurrency-types"><li v-for="item in concurrencyTypes" :key="display(item.key)"><div><strong>{{ display(item.label || item.key) }}</strong><span>占用 {{ item.occupied ?? 0 }} / {{ item.limit ?? '—' }} · 排队 {{ item.queued ?? 0 }}{{ item.draining ? ' · 等待现有任务结束' : '' }}</span><small v-if="Number(owner.readField(display(item.config_key))) > Number(record(state.snapshot?.global).limit)">当前实际最多受全局 {{ record(state.snapshot?.global).limit }} 限制；保存后的类型值仍会保留。</small><small v-if="Array.isArray(item.blocked_by) && item.blocked_by.length">{{ item.blocked_by.map(waitReason).join('；') }}</small></div><button type="button" class="btn" @click="actions.locateConcurrencyTasks(display(item.config_key || item.key))">定位任务</button></li></ul>
      <ul v-if="details.length"><li v-for="(item, index) in details" :key="index">{{ item.label }}：{{ item.occupied }} / {{ item.limit }}</li></ul>
      <details class="config-concurrency-details-v2"><summary>业务附加限制与计量说明</summary><p class="hint">注册批次并发填写正整数，提链批次与平台保留 1–50；它们与全局、类型限制同时生效。XXSYUN 未结束订单名额在远端等待时仍占用，本地查询间隔不占执行槽。调试保留、停止清理和已预约执行仍计入占用。</p><p class="hint">账号补全等待独立子任务时不重复占全局槽；HME 合并扫描按一个扫描 Run 计数；邮箱导入按实际远端交接调用计数。Sub2API 远端账号并发属性在服务集成中维护。</p></details>
      <p v-if="preview.text || preview.error" role="status">{{ preview.error || preview.text }}</p>
    </template>
    <p class="config-action-status" :class="{'config-action-error': state.error}" role="status" aria-live="polite">{{ state.error || state.text || (busy ? '正在请求…' : '尚未查询') }}</p>
  </div>
</template>
<style scoped>
.config-action-tools{display:flex;flex-direction:column;gap:10px;min-width:0}.config-tool-controls{display:flex;align-items:end;gap:8px;flex-wrap:wrap}.config-tool-controls label{display:flex;flex-direction:column;gap:5px;min-width:0}.config-tool-controls select{max-width:100%;min-height:34px}.config-action-tools button{align-self:flex-start;min-height:32px}.config-action-tools p{margin:0;overflow-wrap:anywhere}.config-action-error{color:var(--red)}.config-tool-facts{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:6px 16px;margin:0}.config-tool-facts dd{margin:0;overflow-wrap:anywhere}.config-concurrency-types{padding:0;list-style:none;margin:0}.config-concurrency-types li{display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-bottom:1px solid var(--border)}.config-concurrency-types li>div{display:flex;flex-direction:column;gap:4px;min-width:0}.config-migration-preview{padding:10px;border:1px solid var(--border);border-radius:8px}.config-action-status{min-height:1.5em}@media(max-width:600px){.config-tool-controls>label{width:100%}.config-tool-controls select{width:100%}.config-tool-facts{grid-template-columns:1fr;gap:3px}.config-tool-facts dd{margin-bottom:5px}.config-concurrency-types li{flex-wrap:wrap}}
</style>
