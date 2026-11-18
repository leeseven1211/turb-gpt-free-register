import {createApp} from 'vue';
import BulkPageShell from './features/bulk/BulkPageShell.vue';
import {createBulkApi} from './api/bulk';
import {createBulkIntent} from './features/bulk/useBulkIntent';
import {createAccountQueryAdapter,type AccountQueryAdapter} from './features/accounts/queryAdapter';
import type {BulkNavigation,BulkSliceCallbacks,BulkStorage} from './features/bulk/contracts';

/** The existing application shell keeps hash/history; this mount owns all bulk state. */
export function mountBulk(element:HTMLElement,options:{
 query:AccountQueryAdapter;navigation?:BulkNavigation;callbacks:BulkSliceCallbacks;
 onNavigation(navigation:BulkNavigation,mode:'push'|'replace'):void;isVisible():boolean;
}){
 const api=createBulkApi();
 // Access storage lazily so disabled persistence does not prevent read-only navigation.
 const storage:BulkStorage={get length(){return window.sessionStorage.length;},key:index=>window.sessionStorage.key(index),
  getItem:key=>window.sessionStorage.getItem(key),setItem:(key,value)=>window.sessionStorage.setItem(key,value),removeItem:key=>window.sessionStorage.removeItem(key)};
 const intents=createBulkIntent(api,storage,()=>globalThis.crypto?.randomUUID?.()||`bulk-${Date.now()}-${Math.random().toString(36).slice(2)}`);
 const instance=createApp(BulkPageShell,{initialNavigation:options.navigation,deps:{api,intents,storage,
  adapter:createAccountQueryAdapter(options.query),callbacks:options.callbacks,onNavigation:options.onNavigation,isVisible:options.isVisible,now:Date.now}}).mount(element) as InstanceType<typeof BulkPageShell>;
 return Object.assign(instance,{request:api.request,intent:intents.submit});
}
