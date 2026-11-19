<script setup lang="ts">
import {computed,nextTick,onMounted,ref,watch} from 'vue';
import type {BulkCreateDependencies,BulkDraft,BulkNavigation} from './contracts';
import {useBulkCreate} from './useBulkCreate';
import {selectedValues,textValue,type AccountFilterField,type AccountFilterKey} from '../accounts/filterDefinitions';
const props=withDefaults(defineProps<{navigation:BulkNavigation;deps:BulkCreateDependencies;seed?:BulkDraft|null;visible?:boolean}>(),{visible:true});
const owner=useBulkCreate(props.deps);
const {draft,loading,creating,recovering,error,errorField,existingBatchId,operations,operation,concurrencyMax,pendingCount,count,scopeLabel,summary,hint,availabilityWarning,chips,needsRefresh}=owner;
const form=ref<HTMLFormElement>(),openFilter=ref('');
const disabled=computed(()=>creating.value||recovering.value);
const columns=owner.accountFilters.filter(column=>!['email','date'].includes(column.key));
const descriptions:Record<string,string>={plan_check:'套餐与优惠',token_refresh:'获取最新访问令牌',password_setup:'补充登录密码',twofa_setup:'启用验证器',codex_retry:'获取授权凭证',account_completion:'完成已配置的项目'};
const paths:Record<string,string>={plan_check:'M4 5h16v14H4z M4 10h16 M8 14h3',token_refresh:'M20 7v5h-5 M4 17v-5h5 M6 8a7 7 0 0 1 12-2l2 2 M4 16l2 2a7 7 0 0 0 12-2',password_setup:'M8 11V7a4 4 0 0 1 8 0v4 M6 11h12v10H6z M12 15v2',twofa_setup:'M12 3l8 4v5c0 5-8 9-8 9s-8-4-8-9V7z M8 12l3 3 5-6',codex_retry:'M8 7l-5 5 5 5 M16 7l5 5-5 5 M14 4l-4 16',account_completion:'M9 5h11 M9 12h11 M9 19h11 M3 5h1 M3 12h1 M3 19h1'};
function value(event:Event){return(event.target as HTMLInputElement).value;}
function toggle(key:AccountFilterKey,entry:string,checked:boolean){const next=new Set(selectedValues(draft.value.query,key));if(checked)next.add(entry);else next.delete(entry);owner.setQueryField(key as AccountFilterField,[...next]);}
function closeFilter(event?:Event){const details=(event?.target as HTMLElement)?.closest('details');openFilter.value='';(details?.querySelector('summary') as HTMLElement|null)?.focus();}
function switchFilter(key:string,event:MouseEvent){
 if(disabled.value)return;
 if(openFilter.value===key){openFilter.value='';return;}
 const trigger=event.currentTarget as HTMLElement;
 const panel=trigger.nextElementSibling as HTMLElement;
 const left=trigger.getBoundingClientRect().left;
 // A filter can wrap to the start of a new row. Align it by its actual
 // position, not by its index among the last few filters.
 const panelWidth=Math.min(250,window.innerWidth-48);
 const contentLeft=Math.max(10,document.querySelector('main')?.getBoundingClientRect().left??0);
 const alignedLeft=Math.max(contentLeft,Math.min(left,document.documentElement.clientWidth-panelWidth-10));
 panel.style.setProperty('--bulk-filter-offset',`${alignedLeft-left}px`);
 openFilter.value=key;
}
function onFocusOut(event:FocusEvent){const details=(event.target as HTMLElement).closest('details');if(details&&!details.contains(event.relatedTarget as Node|null))openFilter.value='';}
watch(()=>props.seed,seed=>{if(seed)owner.applySeed(seed);},{immediate:true});
watch(()=>props.visible,visible=>{owner.setVisible(visible);if(!visible)openFilter.value='';},{immediate:true});
watch(errorField,async field=>{if(field){await nextTick();const input=Array.from(form.value?.querySelectorAll<HTMLInputElement>('[name],[data-query],[data-query-filter]')||[]).find(input=>(input.name||input.dataset.query||input.dataset.queryFilter)===field);input?.focus({preventScroll:true});}});
onMounted(()=>{if(props.visible)void owner.initialize();});
defineExpose({refresh:owner.refresh,recover:owner.recover,restoreSelectionRequest:owner.restoreSelectionRequest,setVisible:owner.setVisible,needsRefresh});
</script>
<template>
 <div v-if="loading&&!operations.length" class="bulk-empty" role="status">正在读取操作和筛选配置…</div>
 <form v-else ref="form" data-bulk-create-form class="bulk-create-form" novalidate :aria-busy="disabled" @submit.prevent="owner.createBatch()" @keydown.esc="closeFilter($event)">
  <div class="bulk-create-main">
   <section class="bulk-card bulk-create-card">
    <div class="bulk-step-head"><span class="bulk-step-no">1</span><div><h3>选择操作</h3><p class="bulk-section-note">本次要对账号做什么</p></div></div>
    <div class="bulk-operation-grid" role="radiogroup" aria-label="批量操作">
     <label v-for="item in operations" :key="item.key" class="bulk-operation" :title="item.availability?.available===false?item.availability.reason||'当前不可用':''">
      <input type="radio" name="operation_key" :value="item.key" :checked="draft.operation_key===item.key" :disabled="disabled" required @change="owner.setOperation(item.key)">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="paths[item.key]||paths.account_completion"/></svg>
      <span><strong>{{ item.label||item.key }}</strong><small>{{ descriptions[item.key]||'批量账号操作' }}</small></span><span class="bulk-operation-check" aria-hidden="true">✓</span>
     </label>
    </div>
   </section>
   <section class="bulk-card bulk-create-card">
    <div class="bulk-step-head"><span class="bulk-step-no">2</span><div><h3>批次设置</h3></div></div>
    <p v-if="availabilityWarning" class="bulk-error bulk-operation-warning" data-bulk-operation-warning>{{ availabilityWarning }}</p>
    <div class="bulk-batch-fields">
     <label class="bulk-field bulk-name-field">批次名称<input name="name" maxlength="120" :value="draft.name" placeholder="留空自动命名" :disabled="disabled" :aria-invalid="errorField==='name'||undefined" :aria-describedby="errorField==='name'?'bulkCreateError':undefined" @input="owner.setDraftField('name',value($event))"></label>
     <label class="bulk-field">本批并发上限<input name="max_concurrency" type="number" min="1" :max="concurrencyMax" step="1" :value="draft.max_concurrency" required :disabled="disabled" :aria-invalid="errorField==='max_concurrency'||undefined" :aria-describedby="errorField==='max_concurrency'?'bulkCreateError':undefined" @input="owner.setDraftField('max_concurrency',value($event))"></label>
    </div>
   </section>
   <section class="bulk-card bulk-create-card" data-bulk-account-scope>
    <div class="bulk-step-head"><span class="bulk-step-no">3</span><div><h3>账号范围</h3><p class="bulk-section-note">与账号列表使用同一套筛选</p></div><button type="button" class="bulk-link" data-bulk-action="clear-filters" :disabled="disabled" @click="owner.clearFilters">清空条件</button></div>
    <div v-if="draft.source" class="bulk-source-banner"><span>{{ draft.source.kind==='ids'?'使用已选账号':`沿用批次 #${draft.source.batch_id} 的账号名单` }}</span><button type="button" class="bulk-link" data-bulk-action="use-query" :disabled="disabled" @click="owner.clearFilters">改为按条件筛选</button></div>
    <div v-show="!draft.source" data-bulk-filters>
     <div class="bulk-query-top">
      <label class="bulk-field bulk-query-search"><span class="bulk-sr-only">邮箱或姓名</span><input data-query="email" type="search" :value="draft.query.filters.email" autocomplete="off" placeholder="搜索邮箱或姓名" :disabled="disabled" @input="owner.setQueryField('email',value($event))"></label>
      <details class="bulk-filter-popover" data-filter-dates :open="openFilter==='date'" @focusout="onFocusOut"><summary @click.prevent="switchFilter('date',$event)">创建日期<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg></summary><div class="bulk-filter-popover-panel"><div class="bulk-filter-popover-heading"><strong>创建日期</strong><button type="button" aria-label="关闭创建日期筛选" @click="closeFilter($event)">完成</button></div><label class="bulk-field">创建日期从<input data-query="date_from" type="date" :value="draft.query.date_from" :disabled="disabled" @input="owner.setQueryField('date_from',value($event))"></label><label class="bulk-field">创建日期至（含当天）<input data-query="date_to" type="date" :value="draft.query.date_to" :disabled="disabled" @input="owner.setQueryField('date_to',value($event))"></label></div></details>
      <details class="bulk-filter-popover" :open="openFilter==='more'" @focusout="onFocusOut"><summary @click.prevent="switchFilter('more',$event)">更多查询<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg></summary><div class="bulk-filter-popover-panel"><div class="bulk-filter-popover-heading"><strong>更多查询</strong><button type="button" aria-label="关闭更多查询筛选" @click="closeFilter($event)">完成</button></div><label class="bulk-field">高级搜索<input data-query="q" type="search" :value="draft.query.q" placeholder="如：协议 jp" autocomplete="off" :disabled="disabled" @input="owner.setQueryField('q',value($event))"></label><label class="bulk-field">归档范围<select data-query="archived" :value="draft.query.archived" :disabled="disabled" @change="owner.setQueryField('archived',value($event))"><option value="0">未归档</option><option value="only">仅归档</option><option value="all">全部</option></select></label></div></details>
     </div>
     <div class="bulk-column-filters" aria-label="账号列筛选">
      <details v-for="column in columns" :key="column.key" class="bulk-filter-popover" :class="{'has-value':column.kind==='text'?!!textValue(draft.query,column.key as AccountFilterField):!!selectedValues(draft.query,column.key).length}" :data-filter-field="column.key" :open="openFilter===column.key" @focusout="onFocusOut">
       <summary @click.prevent="switchFilter(column.key,$event)">{{ column.label }}<span v-if="column.kind==='enum'&&selectedValues(draft.query,column.key).length" data-filter-count>{{ selectedValues(draft.query,column.key).length }}</span><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg></summary>
       <div class="bulk-filter-popover-panel"><div class="bulk-filter-popover-heading"><strong>{{ column.label }}</strong><button type="button" :aria-label="`关闭${column.label}筛选`" @click="closeFilter($event)">完成</button></div>
        <label v-if="column.kind==='text'" class="bulk-field">{{ column.label }}<input :data-query-filter="column.key" :value="textValue(draft.query,column.key as AccountFilterField)" inputmode="numeric" placeholder="输入账号 ID" :disabled="disabled" @input="owner.setQueryField(column.key as AccountFilterField,value($event))"></label>
        <div v-else class="bulk-filter-options"><label v-for="entry in owner.filterOptions(column.key)" :key="entry.value"><input type="checkbox" :data-query-filter="column.key" :value="entry.value" :checked="selectedValues(draft.query,column.key).includes(entry.value)" :disabled="disabled" @change="toggle(column.key,entry.value,($event.target as HTMLInputElement).checked)"><span>{{ entry.label }}</span></label><span v-if="!owner.filterOptions(column.key).length" class="bulk-muted">暂无可用选项</span></div>
       </div>
      </details>
     </div>
     <div class="bulk-query-chips" data-query-chips aria-label="已选账号条件"><button v-for="chip in chips" :key="chip.key" type="button" class="bulk-filter-chip" :data-clear-query="chip.key" :aria-label="chip.removeLabel" :disabled="disabled" @click="owner.clearFilter(chip.key)">{{ chip.label }}<span aria-hidden="true">×</span></button><span v-if="!chips.length" class="bulk-filter-empty">全部未归档账号</span></div>
    </div>
   </section>
  </div>
  <aside class="bulk-card bulk-create-side"><div class="bulk-side-sticky">
   <div class="bulk-side-heading"><div><span class="bulk-side-kicker">执行摘要</span><strong data-bulk-create-summary>{{ summary }}</strong></div></div>
   <div class="bulk-side-big" data-bulk-side-count role="status" aria-live="polite" aria-atomic="true">{{ count==null?(draft.source?'创建时确认':'匹配中'):`${count} 个` }}</div>
   <p class="bulk-side-hint" data-bulk-create-hint>{{ hint }}</p>
   <dl class="bulk-side-meta"><div><dt>操作</dt><dd data-bulk-side-operation>{{ operation?.label||draft.operation_key }}</dd></div><div><dt>范围</dt><dd data-bulk-side-scope>{{ scopeLabel }}</dd></div><div><dt>本批并发</dt><dd data-bulk-side-concurrency>{{ draft.max_concurrency }}</dd></div></dl>
   <p v-if="count!=null&&count>=200" class="bulk-side-warning" data-bulk-side-warning>本批将处理 {{ count }} 个账号。</p>
   <p v-if="error" id="bulkCreateError" class="bulk-error" data-bulk-action-error role="alert">{{ error }}<button v-if="existingBatchId" type="button" class="bulk-link" @click="deps.callbacks.navigate('detail',{batch_id:existingBatchId})">查看批次 #{{ existingBatchId }}</button></p>
   <div v-if="pendingCount" class="bulk-notice" data-bulk-recovery role="status"><span>有 {{ pendingCount }} 个请求未收到回执，草稿已保留。</span><button type="button" class="jobs-tb-btn" :disabled="disabled" @click="owner.recover">{{ recovering?'正在找回…':'找回原请求' }}</button></div>
   <div class="bulk-side-actions"><button type="submit" class="jobs-tb-btn jobs-tb-btn--primary" data-bulk-submit :disabled="disabled||count===0||!operations.length">{{ creating?'正在创建批次…':'创建并执行' }}</button><button type="button" class="jobs-tb-btn" data-bulk-action="create-paused" :disabled="disabled||count===0||!operations.length" @click="owner.createBatch(true)">{{ creating?'正在创建批次…':'创建并暂停' }}</button></div>
   <p class="bulk-side-foot">提交时固定账号范围，暂停后可继续原批次</p><button type="button" class="bulk-side-back" data-bulk-action="list" @click="deps.callbacks.navigate('list')">← 返回批次列表</button>
  </div></aside>
 </form>
</template>
