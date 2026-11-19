import {createApp, defineComponent, h, nextTick, shallowRef} from 'vue';
import BulkPageShell from './features/bulk/BulkPageShell.vue';
import BulkList from './features/bulk/BulkList.vue';
import {createBulkApi} from './api/bulk';
import {createBulkIntent} from './features/bulk/useBulkIntent';
import {createAccountQueryAdapter,type AccountQueryAdapter} from './features/accounts/queryAdapter';
import type {BulkNavigation,BulkSliceCallbacks,BulkStorage} from './features/bulk/contracts';
export {mountBulkReport} from './features/bulk/mountBulkReport';

const pageMounts=new WeakMap<HTMLElement,ReturnType<typeof createBulkMount>>();

/** The existing application shell keeps hash/history; this mount owns all bulk state. */
export function mountBulk(element:HTMLElement,options:{
 query:AccountQueryAdapter;navigation?:BulkNavigation;callbacks:BulkSliceCallbacks;
 onNavigation(navigation:BulkNavigation,mode:'push'|'replace'):void;isVisible():boolean;
}){
 const existing=pageMounts.get(element);
 if(existing)return existing;
 const instance=createBulkMount(element,options);
 pageMounts.set(element,instance);
 return instance;
}
function createBulkMount(element:HTMLElement,options:{
 query:AccountQueryAdapter;navigation?:BulkNavigation;callbacks:BulkSliceCallbacks;
 onNavigation(navigation:BulkNavigation,mode:'push'|'replace'):void;isVisible():boolean;
}){
 const api=createBulkApi();
 // Access storage lazily so disabled persistence does not prevent read-only navigation.
 const storage:BulkStorage={get length(){return window.sessionStorage.length;},key:index=>window.sessionStorage.key(index),
  getItem:key=>window.sessionStorage.getItem(key),setItem:(key,value)=>window.sessionStorage.setItem(key,value),removeItem:key=>window.sessionStorage.removeItem(key)};
 const intents=createBulkIntent(api,storage,()=>globalThis.crypto?.randomUUID?.()||`bulk-${Date.now()}-${Math.random().toString(36).slice(2)}`);
 const app=createApp(BulkPageShell,{initialNavigation:options.navigation,deps:{api,intents,storage,
  adapter:createAccountQueryAdapter(options.query),callbacks:options.callbacks,onNavigation:options.onNavigation,isVisible:options.isVisible,now:Date.now}});
 const instance=app.mount(element) as InstanceType<typeof BulkPageShell>;
 return Object.assign(instance,{request:api.request,intent:intents.submit,destroy(){app.unmount();pageMounts.delete(element);}});
}

/** 保留旧页面桥的只读挂载接口；新页面仅调用 mountBulk。 */
export function mountBulkList(element:HTMLElement,options:{view:BulkNavigation;callbacks:BulkSliceCallbacks}){
 const navigation=shallowRef(options.view),list=shallowRef<InstanceType<typeof BulkList>>();
 const app=createApp(defineComponent({setup:()=>()=>h(BulkList,{ref:list,navigation:navigation.value,deps:{api:createBulkApi(),callbacks:options.callbacks}})}));
 app.mount(element);
 return{
  setView(view:BulkNavigation){navigation.value=view;},
  setVisible(visible:boolean){list.value?.setVisible(visible);if(visible)void nextTick(()=>list.value?.refresh());},
  refresh(poll=false){return list.value?.refresh(poll);},
  destroy(){app.unmount();},
 };
}
