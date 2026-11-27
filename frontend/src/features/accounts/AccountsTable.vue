<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,onUpdated,ref,watch,type DeepReadonly} from 'vue';
import {PopoverContent,PopoverPortal,PopoverRoot,PopoverTrigger} from 'reka-ui';
import type {AccountFacets} from '../../api/accounts';
import type {AccountQuerySpec} from './queryAdapter';
import type {AccountViewRow} from './useAccounts';
import ListCell from '../../components/ListCell.vue';
import ColumnResizer from '../../components/ColumnResizer.vue';
import TableState from '../../components/TableState.vue';
import {useColumnWidths} from '../../shared/useColumnWidths';
import AccountFilters from './AccountFilters.vue';
import {accountFilters,type AccountFilterField} from './filterDefinitions';
import {accountColumns,accountColumnWidths,actionFromTarget,type AccountPresentation,type AccountRenderRow} from './presentation';
const props=defineProps<{items:readonly DeepReadonly<AccountViewRow>[];selected:ReadonlySet<string>;query:DeepReadonly<AccountQuerySpec>;facets:DeepReadonly<AccountFacets>;presentation:AccountPresentation;loading:boolean;error:string;invalidSearch:boolean;stale:boolean;visible:boolean;pageSelected:boolean;pageIndeterminate:boolean;openFilter:string|null}>();
const emit=defineEmits<{select:[string,boolean];selectPage:[boolean];action:[string,string,HTMLElement];detail:[string,HTMLElement|null];retry:[];filter:[AccountFilterField,string|readonly string[]];clearFilter:[string];'update:openFilter':[string|null];rendered:[HTMLElement]}>();
// The bridge runs the original 15 -> 16 / layout-v2 migration before mounting.
const {widths,total,resize,resizeWithKeyboard,resetColumns}=useColumnWidths({defaults:accountColumnWidths,storageKey:'gpt_console_table_widths_accounts',totalStorageKey:'gpt_console_table_total_accounts',min:28,max:20000,ratioPrecision:8,totalPrecision:4,
  onPersist(){try{localStorage.setItem('gpt_console_accounts_columns_v2','2');}catch{}},
  onReset(){try{localStorage.removeItem('gpt_console_accounts_columns_v2');}catch{}},
});
const root=ref<HTMLElement>(),openAction=ref<string|null>(null);
function displayHtml(value:string):string {
  if(!props.stale)return value;
  const holder=document.createElement('template');holder.innerHTML=value;
  holder.content.querySelectorAll('button,input,select,textarea').forEach(node=>node.setAttribute('disabled',''));
  holder.content.querySelectorAll('a,[role="button"],[data-copy-id]').forEach(node=>{node.setAttribute('aria-disabled','true');node.setAttribute('tabindex','-1');});
  return holder.innerHTML;
}
const rows=computed(()=>(props.stale&&props.loading?[]:props.items).map(row=>({row,id:String(row.id),cells:Object.fromEntries(accountColumns.filter(column=>column.cell).map(column=>[column.cell!,displayHtml(props.presentation.cell(column.cell!,row))])),menu:props.presentation.menu(row),mobile:props.presentation.mobileSummary(row),tone:props.presentation.rowTone(row)})));
type TeamMembershipItem=NonNullable<AccountViewRow['team_memberships']>[number];
const teamRoleLabels:Record<string,string>={owner:'所有者',admin:'管理员',member:'成员'};
const teamStateLabels:Record<string,string>={invited:'待接受',joining:'入组中'};
function teamMembershipText(m:DeepReadonly<TeamMembershipItem>){
  const name=m.display_name||m.workspace_name||m.workspace_id||`#${m.team_id}`;
  const role=teamRoleLabels[String(m.role||'').toLowerCase()]||'';
  const state=teamStateLabels[String(m.membership_state||'').toLowerCase()]||'';
  const meta=[role,state].filter(Boolean).join('·');
  return meta?`${name} · ${meta}`:name;
}
function teamMembershipTitle(m:DeepReadonly<TeamMembershipItem>){
  const name=m.display_name||m.workspace_name||m.workspace_id||`#${m.team_id}`;
  const role=teamRoleLabels[String(m.role||'').toLowerCase()]||m.role||'待核验';
  const state={joined:'已加入',invited:'待接受',joining:'入组中'}[String(m.membership_state||'').toLowerCase()]||m.membership_state||'未知';
  return `${name} · 角色：${role} · 状态：${state} · Team #${m.team_id}`;
}
const filterFor=(key:string)=>accountFilters.find(column=>column.key===key)!;
function handleRowClick(event:MouseEvent,row:AccountRenderRow){
  if(props.stale||!props.visible){event.preventDefault();event.stopPropagation();return;}
  const target=event.target instanceof Element?event.target:null;
  const detail=target?.closest<HTMLElement>('[data-account-detail-id]');
  if(detail){event.preventDefault();event.stopPropagation();emit('detail',String(row.id),detail);return;}
  const found=actionFromTarget(event.target);
  if(found){event.preventDefault();event.stopPropagation();openAction.value=null;emit('action',found.action,String(row.id),found.trigger);return;}
  if(window.matchMedia('(max-width:860px)').matches&&!target?.closest('button,a,input,label,[role="dialog"]'))emit('detail',String(row.id),null);
}
function closeMenu(){openAction.value=null;}
function onPageScroll(event:Event){
  if(event.target instanceof Element&&event.target.closest('.ac-row-menu'))return;
  closeMenu();
}
watch(()=>props.visible,value=>{if(!value)closeMenu();});
watch(()=>props.stale,value=>{if(value)closeMenu();});
watch(()=>props.items,items=>{if(openAction.value&&!items.some(row=>String(row.id)===openAction.value))closeMenu();});
onMounted(()=>{window.addEventListener('resize',closeMenu);window.addEventListener('scroll',onPageScroll,true);if(root.value)emit('rendered',root.value);});
onUpdated(()=>{if(root.value)emit('rendered',root.value);});
onBeforeUnmount(()=>{window.removeEventListener('resize',closeMenu);window.removeEventListener('scroll',onPageScroll,true);});
defineExpose({resetColumns,closeMenu});
</script>
<template>
  <div ref="root" class="accounts-table-v2-wrap ac-table-scroll" tabindex="0" aria-label="账号列表，可横向滚动" :aria-busy="loading" @scroll="closeMenu">
    <table class="accounts-table-v2 ac-table" :style="{width:`${total}px`}" :data-stale="stale||undefined">
      <caption class="ac-sr-only">账号资产，支持跨页选择</caption>
      <colgroup><col v-for="(width,index) in widths" :key="index" :style="{width:`${width}px`}"></colgroup>
      <thead><tr><th v-for="(column,index) in accountColumns" :key="column.key" scope="col" :class="column.className">
        <input v-if="column.key==='selection'" id="accountsSelectAllV2" type="checkbox" aria-label="全选当前页账号" :checked="pageSelected" :indeterminate="pageIndeterminate" :disabled="stale||!items.length" @change="emit('selectPage',($event.target as HTMLInputElement).checked)">
        <AccountFilters v-else-if="column.filter" :column="filterFor(column.filter)" :query="query" :facets="facets" :label="presentation.facetLabel" :open="visible&&openFilter===column.filter" @update:open="emit('update:openFilter',$event?column.filter:null)" @change="(key,value)=>emit('filter',key,value)" @clear="emit('clearFilter',$event)"/>
        <template v-else>{{ column.label }}</template>
        <ColumnResizer v-if="index" :label="column.label" @start="resize(index,$event)" @nudge="resizeWithKeyboard(index,$event)"/>
      </th></tr></thead>
      <tbody id="accountsBodyV2"><tr v-for="entry in rows" :key="entry.id" :data-account-row="entry.id" :class="{'ac-row-selected':selected.has(entry.id)}" @click="handleRowClick($event,entry.row)">
        <td class="col-check"><input type="checkbox" class="account-row-check" :data-account-id="entry.id" :aria-label="`选择账号 ${entry.row.email||entry.id}`" :checked="selected.has(entry.id)" :disabled="stale" @change="emit('select',entry.id,($event.target as HTMLInputElement).checked)"></td>
        <td class="col-id"><ListCell :text="`#${entry.id}`"/></td>
        <td class="col-email"><button type="button" class="acc-v2-email-link account-cell-line" :disabled="stale" :data-account-detail-id="entry.id" title="查看账号详情"><span class="acc-mobile-dot" :class="`is-${entry.tone}`" aria-hidden="true"></span><span class="acc-v2-email" style="flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis">{{ entry.row.email }}</span><span v-if="entry.row.archived" class="pill status-used" style="flex:none" title="该账号已归档">归档</span></button><div class="acc-v2-sub account-cell-line account-cell-line--sub account-email-meta"><span v-if="!entry.row.team_memberships?.length" class="account-email-name">{{ entry.row.user_name||'-' }}</span><span v-html="presentation.emailInvalidBadge(entry.row)"></span><span v-if="entry.row.team_memberships?.length" class="acc-team-membership-badges"><span v-if="entry.row.team_memberships.length > 1" class="acc-team-pill acc-team-pill--conflict" title="该账号在本地同时关联了多个 Team 工作区">归属冲突</span><span v-for="m in entry.row.team_memberships" :key="String(m.team_id)" class="acc-team-pill" :title="teamMembershipTitle(m)">{{ teamMembershipText(m) }}</span></span></div><div class="acc-mobile-meta">{{ entry.mobile }}</div></td>
        <td class="col-source"><ListCell :text="entry.row.email_source||'-'"/></td>
        <td class="col-registration-driver"><ListCell :text="presentation.registrationDriverLabel(entry.row.registration_driver)"/></td>
        <td v-for="column in accountColumns.filter(column=>column.cell)" :key="column.key" :class="column.className" :data-label="column.label"><div class="ac-legacy-cell" v-html="entry.cells[column.cell!]"></div></td>
        <td class="col-actions"><div class="account-cell-lines acc-v2-actions"><button type="button" class="acc-v2-detail" :disabled="stale" :data-account-detail-id="entry.id">详情</button>
          <PopoverRoot :open="visible&&!stale&&openAction===entry.id" :modal="false" @update:open="openAction=$event?entry.id:null"><PopoverTrigger as-child><button type="button" class="acc-v2-more-btn" :disabled="stale" aria-label="更多账号操作">更多</button></PopoverTrigger><PopoverPortal><PopoverContent class="ac-row-menu accounts-table-v2" :data-account-menu="entry.id" side="bottom" align="end" :side-offset="4" :collision-padding="8" @open-auto-focus.prevent><div class="acc-v2-more-menu ac-menu-content" @click="handleRowClick($event,entry.row)" v-html="entry.menu"></div></PopoverContent></PopoverPortal></PopoverRoot>
        </div></td>
      </tr><TableState v-if="!rows.length" class="ac-empty" :colspan="16" :loading="loading" :error="invalidSearch ? '' : error" loading-title="正在加载账号" loading-text="正在同步账号状态和授权信息" error-title="账号加载失败" :title="invalidSearch ? '搜索条件有误' : '暂无匹配账号'" :text="invalidSearch ? '请按输入框旁的提示修改，或清空高级搜索。' : '可移除部分搜索条件，或切换活跃与归档账号视图。'" retry-label="重试" @retry="emit('retry')"/></tbody>
    </table>
  </div>
</template>
