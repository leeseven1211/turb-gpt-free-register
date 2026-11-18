<script setup lang="ts">
import {nextTick,onBeforeUnmount,onMounted,ref,watch} from 'vue';
import {CARD_DEFS,useDashboard} from './useDashboard';
import {useNativeDialog} from '../../shared/useNativeDialog';
import type {DashboardMountDependencies,DashboardRegion} from './contracts';
const props=defineProps<{api:any;deps:DashboardMountDependencies}>();
const owner=useDashboard(props.api,props.deps);
const {cards,ids,prefs,customizerOpen,loading,error}=owner;
const customizeButton=ref<HTMLButtonElement>(),customizer=ref<HTMLDialogElement>();
useNativeDialog(customizer,()=>customizerOpen.value,()=>owner.visible.value);
const cardLabel=(id:string)=>CARD_DEFS.find(card=>card.id===id)?.label||id;
const dragged=ref<string|null>(null);
function sourceValue(source:any,key:string){const value=source?.[key];return Number.isInteger(value)&&value>=0?String(value):source?.status==='error'?'读取失败':'未知';}
function planLabel(plan:string){return ({free:'Free',free_trial_eligible:'Free · Plus 免费试用',free_half_price_eligible:'Free · Plus 半价',free_discount_eligible:'Free · Plus 其他折扣',free_promo_unknown:'Free · 优惠待复查',plus:'Plus',pro:'Pro',team:'Team',go:'Go',unknown:'未检测'} as Record<string,string>)[plan]||plan;}
function statusLabel(status:string){return ({success:'成功',partial_success:'部分成功',failed:'失败'} as Record<string,string>)[status]||status;}
const sourceList=(payload:any)=>payload?.sources||[];
const leaseList=(payload:any)=>payload?.leases||[];
const planList=(payload:any)=>payload?.plans||[];
const rowList=(payload:any)=>payload?.rows||[];
function closeCustomizer(){owner.closeCustomizer();}
function backdrop(event:MouseEvent){const dialog=customizer.value;if(!dialog||event.target!==dialog)return;const box=dialog.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)closeCustomizer();}
function closeOnEscape(event:KeyboardEvent){if(event.key!=='Escape')return;finishPointer();if(customizerOpen.value)closeCustomizer();}
onMounted(()=>document.addEventListener('keydown',closeOnEscape));
onBeforeUnmount(()=>document.removeEventListener('keydown',closeOnEscape));
function action(action:any){if(!action)return;if(action[0]==='config')props.deps.onConfig?.('代理与网络');else props.deps.onNavigate?.(action[0]);}
function regionOf(id:string):DashboardRegion{return owner.ids.value.metrics.includes(id)?'metrics':'panels';}
function startDrag(id:string){dragged.value=id;}
function drop(id:string){if(!dragged.value)return;owner.reorder(regionOf(id),dragged.value,id);dragged.value=null;}
function keyMove(id:string,event:KeyboardEvent){if(!['ArrowLeft','ArrowUp','ArrowRight','ArrowDown'].includes(event.key))return;event.preventDefault();owner.move(regionOf(id),id,['ArrowLeft','ArrowUp'].includes(event.key)?'up':'down');const handle=event.currentTarget as HTMLElement;void nextTick(()=>handle.focus({preventScroll:true}));}
let pointerCleanup:((cancelled?:boolean)=>void)|undefined;
function finishPointer(cancelled=true){pointerCleanup?.(cancelled);}
function startPointerDrag(id:string,event:PointerEvent){
 if(event.button!==0||pointerCleanup)return;
 const handle=event.currentTarget as HTMLElement,card=handle.closest<HTMLElement>('[data-dashboard-card]'),grid=card?.parentElement;if(!card||!grid)return;
 const region=regionOf(id),saved=[...owner.prefs.order[region]],startX=event.clientX,startY=event.clientY,rect=card.getBoundingClientRect();let ghost:HTMLElement|undefined,frame:number|undefined,lastX=startX,lastY=startY;
 handle.setPointerCapture?.(event.pointerId);
 const preview=()=>{const target=document.elementFromPoint?.(lastX,lastY)?.closest<HTMLElement>('[data-dashboard-card]');if(!target||target===card||target.parentElement!==grid)return;const box=target.getBoundingClientRect(),source=card.getBoundingClientRect();const columns=getComputedStyle(grid).gridTemplateColumns.trim().split(/\s+/).length;const vertical=columns===1||Math.abs(source.top-box.top)>8||target.dataset.overviewSize==='full';const after=vertical?lastY>=box.top+box.height/2:lastX>=box.left+box.width/2;const positions=new Map(Array.from(grid.children).map(node=>[node,node.getBoundingClientRect()]));owner.reorder(region,id,target.dataset.dashboardCard!,after);void nextTick(()=>{if(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)return;for(const [node,before] of positions){if(node===card)continue;const next=node.getBoundingClientRect(),dx=before.left-next.left,dy=before.top-next.top;if(dx||dy)(node as HTMLElement).animate?.([{transform:`translate(${dx}px,${dy}px)`},{transform:'translate(0,0)'}],{duration:180,easing:'cubic-bezier(.2,.75,.2,1)'});}});};
 const scroll=()=>{frame=undefined;if(!ghost)return;const margin=64,y=lastY,speed=y>=0&&y<margin?-Math.ceil((margin-y)/4):y<=window.innerHeight&&y>window.innerHeight-margin?Math.ceil((y-window.innerHeight+margin)/4):0;if(!speed)return;const before=document.scrollingElement?.scrollTop;window.scrollBy(0,speed);if(document.scrollingElement?.scrollTop===before)return;preview();frame=requestAnimationFrame(scroll);};
 const move=(e:PointerEvent)=>{if(e.pointerId!==event.pointerId)return;lastX=e.clientX;lastY=e.clientY;const dx=lastX-startX,dy=lastY-startY;if(!ghost&&Math.hypot(dx,dy)<5)return;if(!ghost){ghost=card.cloneNode(true) as HTMLElement;ghost.classList.add('overview-drag-ghost');ghost.setAttribute('aria-hidden','true');Object.assign(ghost.style,{left:`${rect.left}px`,top:`${rect.top}px`,width:`${rect.width}px`,height:`${rect.height}px`});document.body.append(ghost);card.classList.add('is-drag-placeholder');}ghost.style.transform=`translate3d(${dx}px,${dy}px,0)`;preview();if(!frame)frame=requestAnimationFrame(scroll);};
 const stop=(e:PointerEvent)=>{if(e.pointerId===event.pointerId)finishPointer(e.type==='pointercancel');};
 pointerCleanup=(cancelled=false)=>{pointerCleanup=undefined;window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',stop);window.removeEventListener('pointercancel',stop);if(frame)cancelAnimationFrame(frame);if(handle.hasPointerCapture?.(event.pointerId))handle.releasePointerCapture(event.pointerId);ghost?.remove();card.classList.remove('is-drag-placeholder');if(cancelled)owner.mutate(p=>{p.order[region]=saved;});};
 window.addEventListener('pointermove',move);window.addEventListener('pointerup',stop);window.addEventListener('pointercancel',stop);event.preventDefault();
}
function startResize(id:string,event:PointerEvent){
 if(event.button!==0||pointerCleanup)return;
 const handle=event.currentTarget as HTMLElement,card=handle.closest<HTMLElement>('[data-dashboard-card]'),grid=card?.parentElement;if(!card||!grid)return;
 const style=getComputedStyle(grid),columns=Math.max(1,style.gridTemplateColumns.trim().split(/\s+/).length),gap=parseFloat(style.columnGap)||0,box=card.getBoundingClientRect(),gridBox=grid.getBoundingClientRect(),columnWidth=(gridBox.width-gap*(columns-1))/columns,region=regionOf(id),originalSize=owner.prefs.sizes[id]||'normal',originalHeight=card.style.minHeight;let size=originalSize,height=owner.prefs.heights[id],changed=false;
 handle.setPointerCapture?.(event.pointerId);card.classList.add('is-resizing');
 const move=(e:PointerEvent)=>{if(e.pointerId!==event.pointerId)return;const dx=e.clientX-event.clientX,dy=e.clientY-event.clientY;if(Math.abs(dx)>4&&columnWidth>0){const span=Math.max(1,Math.min(columns,Math.round((box.width+dx+gap)/(columnWidth+gap))));size=span<=1?'normal':span>=Math.min(columns,region==='metrics'?4:3)&&columns>=3?'full':'wide';card.dataset.overviewSize=size;changed=true;}if(Math.abs(dy)>4){height=Math.max(160,Math.min(800,Math.round(box.height+dy)));card.style.minHeight=`${height}px`;if(region==='panels')card.dataset.overviewDensity=height<220?'minimal':height<300?'compact':'normal';changed=true;}};
 const stop=(e:PointerEvent)=>{if(e.pointerId===event.pointerId)finishPointer(e.type==='pointercancel');};
 pointerCleanup=(cancelled=false)=>{pointerCleanup=undefined;window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',stop);window.removeEventListener('pointercancel',stop);card.classList.remove('is-resizing');if(handle.hasPointerCapture?.(event.pointerId))handle.releasePointerCapture(event.pointerId);if(!cancelled&&changed)owner.mutate(p=>{p.sizes[id]=size;if(height!==undefined)p.heights[id]=height;});else{card.dataset.overviewSize=originalSize;card.style.minHeight=originalHeight;const previous=owner.prefs.heights[id];if(region==='panels')card.dataset.overviewDensity=!previous?'normal':previous<220?'minimal':previous<300?'compact':'normal';}};
 window.addEventListener('pointermove',move);window.addEventListener('pointerup',stop);window.addEventListener('pointercancel',stop);event.preventDefault();
}
watch(owner.visible,value=>{if(!value)finishPointer();});watch(owner.data,()=>finishPointer());onBeforeUnmount(()=>finishPointer());

defineExpose({load:owner.load,setVisible:owner.setVisible,openCustomizer:owner.openCustomizer,closeCustomizer:owner.closeCustomizer,resetLayout:owner.resetLayout});
</script>
<template>
 <div class="dashboard-vue-root" data-dashboard-vue>
  <section class="overview-hero" aria-label="平台状态总览">
   <div><div class="data-panel-kicker">Operations overview</div><h2>整个平台，一屏看清</h2><p>拖动卡片标题旁的把手调整位置，拖动右下角调整大小；显示内容可按需设置。</p></div>
   <div class="overview-hero-actions"><button ref="customizeButton" type="button" class="overview-customize-trigger" data-dashboard-open-customizer :aria-expanded="customizerOpen" @click="owner.openCustomizer">自定义总览</button><button type="button" class="overview-refresh" :disabled="loading" @click="owner.load">刷新数据</button></div>
  </section>
  <div v-if="error" class="list-result list-result--danger" role="alert"><strong>总览加载失败</strong><span>{{error}}</span><button type="button" @click="owner.load">重试</button></div>
  <dialog ref="customizer" class="overview-customizer" role="dialog" aria-modal="true" aria-labelledby="dashboard-customizer-title" :aria-hidden="!customizerOpen" @cancel.prevent="closeCustomizer" @click="backdrop">
   <div class="overview-customizer-head"><div><div class="data-panel-kicker">Customize overview</div><h3 id="dashboard-customizer-title">显示与排序</h3><p>拖动卡片排序，也可以用上移/下移调整。未启用或未配置的功能不会出现在这里。</p></div><button type="button" class="overview-customizer-close" data-dashboard-close-customizer @click="closeCustomizer">关闭</button></div>
   <div class="overview-customizer-list">
    <section v-for="region in ['metrics','panels'] as DashboardRegion[]" :key="region" class="overview-customizer-group">
     <div class="overview-customizer-group-head"><strong>{{region==='metrics'?'指标卡片':'详细卡片'}}</strong><small>{{(ids[region]||[]).length}} 张可用卡片</small></div>
     <div class="overview-customizer-items">
      <div v-for="id in (prefs.order[region]||[])" :key="id" class="overview-customizer-item" draggable="true" :data-dashboard-custom-card="id" @dragstart="startDrag(id)" @dragover.prevent @drop="drop(id)">
       <span class="overview-drag-handle" aria-hidden="true">拖动</span><label><input type="checkbox" :checked="!prefs.hidden.includes(id)" @change="owner.toggle(id,($event.target as HTMLInputElement).checked)"><span>{{cardLabel(id)}}</span></label>
       <div class="overview-customizer-move" role="group" :aria-label="`调整 ${id} 顺序`"><button type="button" @click="owner.move(region,id,'up')">上移</button><button type="button" @click="owner.move(region,id,'down')">下移</button></div>
      </div>
     </div>
    </section>
   </div>
   <div class="overview-customizer-foot"><button type="button" class="overview-reset-layout" data-dashboard-reset-layout @click="owner.resetLayout">恢复默认布局</button></div>
  </dialog>
  <div class="overview-metrics">
   <template v-for="item in cards.filter(item=>item.card.region==='metrics')" :key="item.card.id">
    <article class="overview-metric" :data-dashboard-card="item.card.id" :data-overview-card="item.card.id" :data-overview-size="item.size" :style="{'--metric-color':item.payload.color,minHeight:item.height?`${item.height}px`:undefined}" @dragstart.prevent @dragover.prevent @drop="drop(item.card.id)">
     <div class="overview-metric-top"><span>{{item.card.label}}</span><div class="overview-card-tools"><i class="overview-metric-dot" aria-hidden="true"></i><span class="overview-card-drag" role="button" tabindex="0" :aria-label="`拖动${item.card.label}卡片排序，或使用方向键调整顺序`" @keydown="keyMove(item.card.id,$event)" @pointerdown="startPointerDrag(item.card.id,$event)"><svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="5" cy="3" r="1"/><circle cx="11" cy="3" r="1"/><circle cx="5" cy="8" r="1"/><circle cx="11" cy="8" r="1"/><circle cx="5" cy="13" r="1"/><circle cx="11" cy="13" r="1"/></svg></span></div></div>
     <strong>{{item.payload.value}}</strong><small>{{item.payload.hint}}</small><button type="button" class="overview-resize-handle" data-overview-resize :aria-label="`拖动调整${item.card.label}卡片宽高；方向键可调整`" @pointerdown="startResize(item.card.id,$event)" @keydown.left.prevent="owner.resize(item.card.id,'width',-1)" @keydown.right.prevent="owner.resize(item.card.id,'width',1)" @keydown.up.prevent="owner.resize(item.card.id,'height',-40)" @keydown.down.prevent="owner.resize(item.card.id,'height',40)"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 14l8-8M10 14l4-4"/></svg></button>
    </article>
   </template>
  </div>
  <div class="overview-grid">
   <template v-for="item in cards.filter(item=>item.card.region==='panels')" :key="item.card.id">
    <section class="overview-panel" :data-dashboard-card="item.card.id" :data-overview-card="item.card.id" :data-overview-size="item.size" :data-overview-density="item.density" :style="item.height?{minHeight:`${item.height}px`}:undefined" @dragstart.prevent @dragover.prevent @drop="drop(item.card.id)">
     <div class="overview-panel-head"><div><span>{{item.card.label.split(' · ')[0]}}</span><h3>{{item.card.label.split(' · ').slice(1).join(' · ')}}</h3></div><div class="overview-card-tools"><button v-if="item.payload.action" type="button" @click="action(item.payload.action)">{{item.payload.action[1]}}</button><span class="overview-card-drag" role="button" tabindex="0" :aria-label="`拖动${item.card.label}卡片排序，或使用方向键调整顺序`" @keydown="keyMove(item.card.id,$event)" @pointerdown="startPointerDrag(item.card.id,$event)"><svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="5" cy="3" r="1"/><circle cx="11" cy="3" r="1"/><circle cx="5" cy="8" r="1"/><circle cx="11" cy="8" r="1"/><circle cx="5" cy="13" r="1"/><circle cx="11" cy="13" r="1"/></svg></span></div></div>
     <div v-if="item.payload.kind==='email'" class="overview-source-grid"><article v-for="(source,index) in sourceList(item.payload)" :key="source.source" class="overview-source" :class="{'overview-density-secondary':Number(index)>=2,'overview-density-minimal-extra':Number(index)>=1}"><div class="overview-source-top"><span class="overview-source-name" :title="source.label">{{source.label}}</span><i class="overview-source-state is-on" aria-hidden="true"></i></div><strong>{{sourceValue(source,'available')}}</strong><small>本地总数 {{sourceValue(source,'total')}} · 已用 {{sourceValue(source,'used')}} · 失败 {{sourceValue(source,'failed')}}</small></article><div v-if="sourceList(item.payload).length>2" class="overview-more-summary overview-more-summary--compact overview-more-summary--paired">另有 {{sourceList(item.payload).length-2}} 个来源，进入详情查看</div><div v-if="sourceList(item.payload).length>1" class="overview-more-summary overview-more-summary--minimal">另有 {{sourceList(item.payload).length-1}} 个来源，进入详情查看</div></div>
     <div v-else-if="item.payload.kind==='proxy'"><div class="overview-proxy-grid"><div class="overview-proxy-item"><span>系统代理平台</span><strong>{{item.payload.platform}}</strong></div><div class="overview-proxy-item"><span>活跃出口</span><strong>{{item.payload.active}} 个</strong></div></div><div class="overview-exit-list"><div v-for="(lease,index) in leaseList(item.payload)" :key="index" class="overview-exit-row" :class="{'overview-density-secondary':Number(index)>=1}"><i aria-hidden="true"></i><span>{{lease.endpoint||lease.exit_ip||'活跃出口'}}</span><small>{{lease.region||lease.provider||''}}</small></div><div v-if="!leaseList(item.payload).length" class="muted">当前没有活跃代理出口</div></div><div v-if="item.payload.more" class="overview-more-summary overview-more-summary--compact">{{item.payload.more}}</div></div>
     <div v-else-if="item.payload.kind==='plans'" class="overview-plan-list"><div v-for="([plan,count],index) in planList(item.payload)" :key="plan" class="overview-plan-row" :class="{'overview-density-secondary':Number(index)>=3,'overview-density-minimal-extra':Number(index)>=2}"><span>{{planLabel(plan)}}</span><div class="overview-plan-bar"><i :style="{width:`${Math.max(4,Math.round(Number(count)/Math.max(1,...planList(item.payload).map((p:any)=>Number(p[1])))*100))}%`}"></i></div><strong>{{count}}</strong></div><div v-if="planList(item.payload).length>3" class="overview-more-summary overview-more-summary--compact overview-more-summary--paired">另有 {{planList(item.payload).length-3}} 种套餐，进入详情查看</div><div v-if="planList(item.payload).length>2" class="overview-more-summary overview-more-summary--minimal">另有 {{planList(item.payload).length-2}} 种套餐，进入详情查看</div></div>
     <div v-else-if="item.payload.kind==='today'" class="overview-job-list"><div v-for="([status,label,count],index) in rowList(item.payload)" :key="status" class="overview-job-row" :class="{'overview-density-secondary':status==='partial_success'||(Number(index)>0&&!count)}"><span class="pill" :class="`status-${status}`">{{statusLabel(status)}}</span><div class="overview-job-main"><strong>{{count}} 个任务</strong><small>{{item.payload.today}} · {{label}}</small></div></div><div v-if="rowList(item.payload)[1]?.[2]" class="overview-more-summary overview-more-summary--compact">部分成功 {{rowList(item.payload)[1]?.[2]}}</div></div>
     <div v-else-if="item.payload.kind==='queue' || item.payload.kind==='history' || item.payload.kind==='health' || item.payload.kind==='codex'" class="overview-status-grid"><div v-for="([label,count],index) in rowList(item.payload)" :key="label" class="overview-status-item" :class="{'overview-density-secondary':item.payload.kind==='health'?[1,3].includes(Number(index)):Number(index)>1}"><span>{{label}}</span><strong>{{count}}</strong></div><div v-if="item.payload.kind==='queue' && rowList(item.payload)[2]?.[1]" class="overview-more-summary overview-more-summary--compact">停止中 {{rowList(item.payload)[2]?.[1]}}</div><div v-if="item.payload.kind==='history' && (rowList(item.payload)[2]?.[1] || rowList(item.payload)[3]?.[1])" class="overview-more-summary overview-more-summary--compact">部分成功 {{rowList(item.payload)[2]?.[1]||0}} · 已停止或取消 {{rowList(item.payload)[3]?.[1]||0}}</div><div v-if="item.payload.kind==='health'" class="overview-more-summary overview-more-summary--compact">已用 {{rowList(item.payload)[1]?.[1]||0}} · 停用 {{rowList(item.payload)[3]?.[1]||0}}</div><div v-if="item.payload.kind==='codex'" class="overview-more-summary overview-more-summary--compact">账号 Codex 就绪 {{rowList(item.payload)[2]?.[1]||0}}</div></div>
     <button type="button" class="overview-resize-handle" data-overview-resize :aria-label="`拖动调整${item.card.label}卡片宽高；方向键可调整`" @pointerdown="startResize(item.card.id,$event)" @keydown.left.prevent="owner.resize(item.card.id,'width',-1)" @keydown.right.prevent="owner.resize(item.card.id,'width',1)" @keydown.up.prevent="owner.resize(item.card.id,'height',-40)" @keydown.down.prevent="owner.resize(item.card.id,'height',40)"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 14l8-8M10 14l4-4"/></svg></button>
    </section>
   </template>
  </div>
 </div>
</template>

<style scoped>
.dashboard-vue-root{display:grid;grid-template-columns:minmax(0,1fr);gap:20px;min-width:0;max-width:100%}
.list-result--danger{display:flex;align-items:center;flex-wrap:wrap;gap:8px 12px;padding:12px 16px;border:1px solid var(--ui-color-border);border-radius:8px;color:var(--ui-color-danger)}
.list-result--danger span{flex:1;min-width:0;overflow-wrap:anywhere}
.overview-customizer{margin:0 0 0 auto;border:0;border-left:1px solid var(--ui-color-border);max-width:100vw;max-height:100dvh;height:100dvh;box-sizing:border-box}.overview-customizer:not([open]){display:none}.overview-customizer[open]{display:flex}.overview-customizer::backdrop{background:rgb(16 20 39 / 42%);backdrop-filter:blur(2px)}.overview-customizer-list{min-height:0;overflow:auto}.overview-card-drag{touch-action:none}.overview-resize-handle{touch-action:none}
@media(max-width:560px){.overview-customizer-item button{min-width:40px;min-height:40px}}
</style>

<style>
body.em-native-dialog-lock{position:fixed;left:0;right:0;width:100%;overflow:hidden}
</style>
