import {createApp} from 'vue';
import RegistrationPage from './features/registration/RegistrationPage.vue';
import type {RegistrationDeps,RegistrationHandle,RegistrationView} from './features/registration/contracts';
import {createRegistrationApi} from './api/registration';
export type {RegistrationDeps,RegistrationHandle,RegistrationView} from './features/registration/contracts';
export function mountRegistration(element:HTMLElement,deps:RegistrationDeps={}):RegistrationHandle{
  const app=createApp(RegistrationPage,{deps:{...deps,api:deps.api||createRegistrationApi()}});
  const page=app.mount(element) as InstanceType<typeof RegistrationPage>;
  return {load:page.load,ensureMeta:page.ensureMeta,loadSources:page.loadSources,setBatch:page.setBatch,create:page.create,runAction:page.runAction,setVisible:page.setVisible,setView:page.setView,loadSummary:page.loadSummary,renderEmailSupply:page.renderEmailSupply,applySummary:page.applySummary,action:page.action,openLog:page.openLog,closeDetail:page.closeDetail,destroy:()=>app.unmount()};
}
