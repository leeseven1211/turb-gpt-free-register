<script setup lang="ts">
import {computed} from 'vue';
import type {SourceCard} from './contracts';
import {sourceLabels} from './presentation';
const props=defineProps<{sources:SourceCard[];expanded:boolean;loading:boolean;error:string;butlerLabel:string}>();
const emit=defineEmits<{refresh:[];expand:[];source:[string];localImport:[];butlerImport:[]}>();
const truth=(value:unknown)=>value===true||value==='true';
const visible=(row:SourceCard)=>row.kind==='local_pool'||(row.default_visible===undefined?truth(row.enabled)||truth(row.dependency):truth(row.default_visible));
const hiddenCount=computed(()=>props.sources.filter(row=>!visible(row)).length);
const rows=computed(()=>props.expanded?props.sources:props.sources.filter(visible));
const clickable=(row:SourceCard)=>row.kind!=='on_demand'&&!!sourceLabels[row.source]&&row.source!=='all';
function stateLabel(row:SourceCard){return row.kind==='local_pool'?'本地库存':truth(row.enabled)?'已启用':truth(row.dependency)?'收码依赖':truth(row.history_available)||Number(row.total)>0?'历史/已停用':'未启用';}
</script>
<template>
 <section class="em-overview" aria-label="邮箱资源平台" :aria-busy="loading">
  <div class="em-heading"><div><h2>本地邮箱库存</h2><p>仅从本地库存领取邮箱，用完后请从 Butler 或其他来源手动导入。</p></div><button class="em-button" :disabled="loading" @click="emit('refresh')">{{ loading?'刷新中…':'刷新资源' }}</button></div>
  <p v-if="error" class="em-error" role="alert">{{ error }} <button class="em-button" @click="emit('refresh')">重试</button></p>
  <div class="em-source-visibility"><span>{{ hiddenCount?'默认显示已启用服务和当前收码依赖':'当前没有未启用的邮箱服务' }}</span><button v-if="hiddenCount" class="em-button" :aria-expanded="expanded" @click="emit('expand')">{{ expanded?'隐藏未启用':`显示未启用（${hiddenCount}）` }}</button></div>
  <div class="em-source-cards">
   <component :is="clickable(row)?'button':'article'" v-for="row in rows" :key="row.source" :type="clickable(row)?'button':undefined" class="em-source-card" :class="{'is-clickable':clickable(row)}" @click="clickable(row)&&emit('source',row.source)">
    <div class="em-source-title"><strong>{{ row.label||sourceLabels[row.source]||row.source }}</strong><span>{{ stateLabel(row) }}</span></div>
    <strong class="em-source-number">{{ row.kind==='on_demand'?'按需':row.available??0 }}</strong>
    <p>{{ row.kind==='on_demand'?'运行时领取 / 创建':`总数 ${row.total||0} · 已用 ${row.used||0} · 失败 ${row.failed||0} · 停用 ${row.disabled||0}` }}</p>
    <small v-if="row.dependency_reason">{{ row.dependency_reason }}</small>
   </component>
  </div>
  <p v-if="!rows.length" role="status">{{ loading?'正在加载邮箱资源…':'暂无已启用邮箱服务，可显示未启用的服务。' }}</p>
  <section class="em-import-prompt"><div><span>Email Butler</span><h3>手动补充本地库存</h3><p>从 Butler 选择 iCloud HME 母邮箱或子邮箱导入，也可粘贴已有完整地址。注册任务仅领取本地库存。</p></div><div class="em-actions"><button class="em-button em-primary" data-butler-opener @click="emit('butlerImport')">{{ butlerLabel }}</button><button class="em-button" @click="emit('localImport')">粘贴导入</button></div></section>
 </section>
</template>
