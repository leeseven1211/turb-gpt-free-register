import {createApp,effectScope,h,ref,watch} from 'vue';
import ConfigPage from './features/config/ConfigPage.vue';
import {createConfigApi} from './api/config';
import {createConfigDraft} from './features/config/useConfigDraft';
import type {ConfigActionReceipt} from './features/config/configActions';
import {useConfigActions} from './features/config/useConfigActions';
import type {ConfigField} from './features/config/contracts';

export function mountConfig(element:HTMLElement,options:{
 visible?:boolean;onSaved?():void;onSavedFields(fields:readonly ConfigField[]):void;
 onTaskReceipt(receipt:ConfigActionReceipt,label:string):void;
 onNavigateTasks(filters:{registration?:boolean;types?:string[]}):void;
}){
 const owner=createConfigDraft({api:createConfigApi()});
 const actionScope=effectScope();
 const actions=actionScope.run(()=>useConfigActions(owner,{onTaskReceipt:options.onTaskReceipt,onNavigateTasks:options.onNavigateTasks}))!;
 const active=ref(options.visible!==false);
 let page:InstanceType<typeof ConfigPage>|null=null;
 const stop=watch(owner.fields,fields=>options.onSavedFields(fields),{immediate:true});
 const stopSaved=owner.subscribeSaved(()=>options.onSaved?.());
 const app=createApp({render:()=>h(ConfigPage,{owner,actions,active:active.value,ref:(value:unknown)=>{page=value as InstanceType<typeof ConfigPage>;}})});
 app.mount(element);
 return {
  load:()=>owner.initialize(),refresh:()=>owner.refresh({force:true}),
  open:(name:string)=>page?.open(name),
  setVisible:(visible:boolean)=>{active.value=visible;actions.setPageActive(visible);},
  destroy:()=>{stop();stopSaved();app.unmount();actionScope.stop();owner.dispose();},
 };
}
