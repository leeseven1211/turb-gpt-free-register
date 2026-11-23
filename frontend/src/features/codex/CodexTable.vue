<script setup lang="ts">
import {computed, ref, watch} from 'vue';
import {PopoverContent, PopoverPortal, PopoverRoot, PopoverTrigger} from 'reka-ui';
import type {CodexFacets, CodexFilters as FilterValues, CodexRow} from '../../api/codex';
import type {CodexAction} from './actions';
import ListCell from '../../components/ListCell.vue';
import ColumnResizer from '../../components/ColumnResizer.vue';
import TableState from '../../components/TableState.vue';
import {useColumnWidths} from '../../shared/useColumnWidths';
import {dateTimeLines} from '../../shared/time';
import CodexFilters from './CodexFilters.vue';
import {codexColumns} from './filterDefinitions';
import {credentialStatus, oauthStatus, planTone} from './presentation';
const props = defineProps<{items: CodexRow[]; selected:Set<string>; filters:FilterValues; facets:CodexFacets; loading:boolean;error:string;busy:boolean;visible:boolean;openFilter:string|null}>();
const emit = defineEmits<{select:[string,boolean];selectPage:[boolean];action:[CodexAction,CodexRow];retry:[];'update:filters':[FilterValues];'update:openFilter':[string|null]}>();
const {widths,total,resize,resizeWithKeyboard,resetColumns} = useColumnWidths({defaults:[48,228,84,108,108,132,132,132,132,228],storageKey:'gpt_console_table_widths_codex',totalStorageKey:'gpt_console_table_total_codex',min:28,max:2000});
const allChecked = computed(() => props.items.length > 0 && props.items.every(row => props.selected.has(row.filename)));
const partial = computed(() => !allChecked.value && props.items.some(row => props.selected.has(row.filename)));
const rows = computed(() => {
  // A credential may join several accounts, including identical display rows.
  // Keep every row; filename remains the shared selection/action identity.
  const occurrences = new Map<string,number>();
  return props.items.map(row => {
    const identity = JSON.stringify([row.filename,row.sub2api_account_id ?? null]);
    const occurrence = occurrences.get(identity) ?? 0;
    occurrences.set(identity,occurrence+1);
    return {row,key:JSON.stringify([identity,occurrence]),credential:credentialStatus(row),oauth:oauthStatus(row)};
  });
});
const openAction = ref<string|null>(null);
watch(() => props.visible, value => { if (!value) openAction.value = null; });
// A refreshed join result has no durable row identity beyond the credential.
watch(() => props.items, () => { openAction.value = null; });
function setActionOpen(key:string,open:boolean) {
  if (open) openAction.value=key;
  else if (openAction.value===key) openAction.value=null;
}
function action(kind:CodexAction,row:CodexRow) { if (props.busy) return; openAction.value=null; emit('action',kind,row); }
function display(value: unknown) { return value == null || value === '' ? '—' : String(value); }
defineExpose({resetColumns});
</script>
<template>
  <div class="ui-table-scroll cx-table-scroll" tabindex="0" aria-label="Codex 凭证列表，可横向滚动" :aria-busy="loading">
    <table class="ui-table ui-table--sticky-end cx-table" :style="{'--ui-table-width':`${total}px`}">
      <caption class="ui-sr-only">Codex 凭证，支持跨页选择</caption>
      <colgroup><col v-for="(width,index) in widths" :key="index" :style="{width:`${width}px`}"></colgroup>
      <thead><tr>
        <th scope="col" class="ui-col-check"><input type="checkbox" aria-label="全选当前页 Codex 凭证" :checked="allChecked" :indeterminate="partial" :disabled="!items.length || busy" @change="emit('selectPage',($event.target as HTMLInputElement).checked)"></th>
        <th v-for="(column,index) in codexColumns" :key="column.key" scope="col">
          <CodexFilters :column="column" :model-value="filters" :facets="facets" :open="visible && openFilter === column.key" @update:model-value="emit('update:filters',$event)" @update:open="emit('update:openFilter',$event ? column.key : null)"/>
          <ColumnResizer :label="column.label" @start="resize(index+1,$event)" @nudge="resizeWithKeyboard(index+1,$event)"/>
        </th>
        <th scope="col">操作</th>
      </tr></thead>
      <tbody>
        <tr v-for="{row,key,credential,oauth} in rows" :key="key" :class="{'is-selected':selected.has(row.filename)}">
          <td class="ui-col-check cx-check" data-label="选择"><input type="checkbox" :aria-label="`选择凭证 ${row.filename}`" :checked="selected.has(row.filename)" :disabled="busy" @change="emit('select',row.filename,($event.target as HTMLInputElement).checked)"></td>
          <td class="cx-identity" data-label="邮箱 / 文件"><ListCell :text="row.email || row.filename" :secondary="row.email ? row.filename : undefined" :title="`${row.email || ''} · 文件：${row.filename}${row.archived ? ' · 已归档' : ''}`"/><div class="cx-mobile-summary" :title="[display(row.plan),credential.title,oauth.title].join('；')">{{ [display(row.plan),credential.label,oauth.label].join(' · ') }}</div></td>
          <td class="cx-extra" data-label="Plan"><ListCell :text="display(row.plan)"><span v-if="row.plan" class="ui-badge cx-badge" :class="`ui-badge--${planTone(row.plan)}`">{{ row.plan }}</span><template v-else>—</template></ListCell></td>
          <td class="cx-extra" data-label="凭证状态"><ListCell :text="credential.label" :title="credential.title" :tone="credential.tone"><span class="ui-badge cx-badge" :class="`ui-badge--${credential.tone}`">{{ credential.label }}</span></ListCell></td>
          <td class="cx-extra" data-label="OAuth 状态"><ListCell :text="oauth.label" :title="oauth.title" :tone="oauth.tone"><span class="ui-badge cx-badge" :class="`ui-badge--${oauth.tone}`">{{ oauth.label }}</span></ListCell></td>
          <td class="cx-extra" data-label="Account ID"><ListCell :text="display(row.account_id)"/></td>
          <td class="cx-extra" data-label="Sub2API ID"><ListCell :text="display(row.sub2api_account_id)"/></td>
          <td class="cx-extra ui-time" data-label="更新时间"><ListCell v-bind="dateTimeLines(row.mtime)" :title="display(row.mtime)"/></td>
          <td class="cx-extra ui-time" data-label="过期时间"><ListCell v-bind="dateTimeLines(row.expired)" :title="display(row.expired)"/></td>
          <td class="cx-actions" data-label="操作"><div class="ui-row-actions cx-row-actions">
            <button type="button" class="ui-link cx-direct-download" :data-codex-download="row.filename" :disabled="busy" @click="action('download',row)">下载凭证</button>
            <PopoverRoot :open="visible && openAction === key" :modal="false" @update:open="setActionOpen(key,$event)">
              <PopoverTrigger as-child><button type="button" class="ui-link" :aria-label="`更多操作 ${row.filename}`" :disabled="busy">更多</button></PopoverTrigger>
              <PopoverPortal><PopoverContent class="cx-row-menu" :aria-label="`${row.email || row.filename} 的凭证详情与操作`" side="bottom" align="end" :side-offset="6" :collision-padding="10" hide-when-detached>
                <div class="cx-menu-actions" role="group" aria-label="凭证操作">
                  <button type="button" :data-codex-download="row.filename" :disabled="busy" @click="action('download',row)">下载凭证</button>
                  <button type="button" :data-codex-reauthorize="row.filename" :disabled="busy" @click="action('reauthorize',row)">重跑授权</button>
                  <button type="button" :data-codex-download-cpa="row.filename" :disabled="busy" @click="action('downloadCpa',row)">从 CPA 下载</button>
                  <button type="button" :data-codex-refresh-token="row.filename" :disabled="busy" @click="action('refreshToken',row)">刷新 OAuth Token</button>
                  <button type="button" :data-codex-upload-sub2="row.filename" :disabled="busy" @click="action('uploadSub2',row)">上传 sub2api</button>
                  <button v-if="Number(row.exported_count || 0) > 0" type="button" :data-codex-reset="row.filename" :disabled="busy" @click="action('reset',row)">重置标记</button>
                  <button type="button" :data-codex-archive="row.filename" :data-archived="row.archived ? '0' : '1'" :disabled="busy" @click="action('archive',row)">{{ row.archived ? '恢复' : '归档' }}</button>
                  <button type="button" class="cx-danger" :data-codex-delete="row.filename" :disabled="busy" @click="action('delete',row)">删除凭证</button>
                </div>
              </PopoverContent></PopoverPortal>
            </PopoverRoot>
          </div></td>
        </tr>
        <TableState v-if="!items.length" :colspan="10" :loading="loading" :error="error" loading-title="正在加载授权凭证" loading-text="正在同步 OAuth 与导出状态" error-title="凭证列表加载失败" title="没有匹配的凭证" text="可调整筛选条件，或清除全部筛选。" retry-label="重新加载" @retry="emit('retry')"/>
      </tbody>
    </table>
  </div>
</template>
