<script setup lang="ts">
import {computed,onBeforeUnmount,reactive,ref} from 'vue';
import type {EmailApi} from '../../api/email';
import type {EmailMountDependencies,EmailRow,EmailView,LocalImportSource,SourceCard} from './contracts';
import {readScope} from './readScope';
import {useEmailInventory} from './useEmailInventory';
import {useEmailHistory} from './useEmailHistory';
import {useLocalImport} from './useLocalImport';
import {useButlerImport} from './useButlerImport';
import EmailOverview from './EmailOverview.vue';
import EmailInventory from './EmailInventory.vue';
import EmailHistory from './EmailHistory.vue';
import EmailLocalImport from './EmailLocalImport.vue';
import EmailButlerImport from './EmailButlerImport.vue';
import './email.css';
const props=defineProps<{api:EmailApi;deps:EmailMountDependencies;initialView?:EmailView;initialVisible?:boolean}>();
const view=ref<EmailView>(props.initialView||'overview'),visible=ref(props.initialVisible||false),documentVisible=ref(!document.hidden);
const overview=reactive({sources:[] as SourceCard[],expanded:false,loading:false,error:''});
const overviewRead=readScope(overview,async(signal,valid)=>{const result=await props.api.overview(signal);if(valid())overview.sources=result.email?.supply?.sources||result.email?.sources||[];});
const inventory=useEmailInventory(props.api,props.deps),history=useEmailHistory(props.api,props.deps);
const importDeps:EmailMountDependencies={...props.deps,async onInventoryChanged(){void inventory.refresh();void history.refresh();void overviewRead.refresh();await props.deps.onInventoryChanged();}};
const localImport=useLocalImport(props.api,importDeps);
const storage={getItem:(key:string)=>localStorage.getItem(key),setItem:(key:string,value:string)=>localStorage.setItem(key,value),removeItem:(key:string)=>localStorage.removeItem(key)};
const butler=useButlerImport(props.api,importDeps,{storage});
const butlerLabel=computed(()=>butler.state.request?(butler.isRunning.value?`Butler 导入中 · ${butler.state.batch?.imported||0}/${butler.state.batch?.total||0}`:'查看 Butler 导入'):'从 Butler 导入');
function applyVisibility(){const active=visible.value&&documentVisible.value;overviewRead.setActive(active&&view.value==='overview');inventory.setActive(active&&view.value==='list');history.setActive(active&&view.value==='derivations');localImport.setActive(active);butler.setActive(active);}
function closeDialogs(){localImport.close();butler.close();}
function setView(value:EmailView){if(!['overview','list','derivations'].includes(value)||view.value===value)return;view.value=value;closeDialogs();applyVisibility();}
function setVisible(value:boolean){if(visible.value===value)return;visible.value=value;if(!value)closeDialogs();applyVisibility();}
function parent(row:EmailRow){if(!row.id)return;history.scopeParent({source:row.source,id:row.id,email:row.email});props.deps.onNavigate('derivations');}
function source(value:string){inventory.updateFilters({source:value});props.deps.onNavigate('list');}
async function openImport(sourceValue?:LocalImportSource){localImport.open(sourceValue||(['outlook','generic_api','email_butler'].includes(inventory.state.filters.source)?inventory.state.filters.source as LocalImportSource:'outlook'));}
async function openButlerImport(){await butler.open();}
function visibilityChanged(){documentVisible.value=!document.hidden;applyVisibility();}
document.addEventListener('visibilitychange',visibilityChanged);applyVisibility();
onBeforeUnmount(()=>{document.removeEventListener('visibilitychange',visibilityChanged);overviewRead.dispose();inventory.dispose();history.dispose();localImport.dispose();butler.dispose();});
defineExpose({setView,setVisible,refreshOverview:overviewRead.refresh,refreshInventory:inventory.refresh,refreshHistory:history.refresh,refreshDerivationSummary:inventory.refreshDerivationSummary,openImport,openButlerImport,closeDialogs});
</script>
<template>
 <div class="em-page">
  <h1>邮箱资源池</h1>
  <EmailOverview v-show="view==='overview'" :sources="overview.sources" :expanded="overview.expanded" :loading="overview.loading" :error="overview.error" :butler-label="butlerLabel" @refresh="overviewRead.refresh()" @expand="overview.expanded=!overview.expanded" @source="source" @local-import="openImport('email_butler')" @butler-import="openButlerImport"/>
  <EmailInventory v-show="view==='list'" :owner="inventory" :active="visible&&documentVisible&&view==='list'" :butler-label="butlerLabel" @local-import="openImport()" @butler-import="openButlerImport" @parent="parent"/>
  <EmailHistory v-show="view==='derivations'" :owner="history" :active="visible&&documentVisible&&view==='derivations'"/>
  <EmailLocalImport :owner="localImport" :active="visible&&documentVisible"/><EmailButlerImport :owner="butler" :active="visible&&documentVisible"/>
 </div>
</template>
