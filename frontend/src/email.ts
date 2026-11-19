import {createApp} from 'vue';
import EmailPageShell from './features/email/EmailPageShell.vue';
import {createEmailApi} from './api/email';
import type {EmailHandle,EmailMountDependencies} from './features/email/contracts';
export type {EmailHandle,EmailMountDependencies,EmailView,LocalImportSource} from './features/email/contracts';
/** The host owns navigation/history; this mount owns all mailbox state and intents. */
export function mountEmail(element:HTMLElement,deps:EmailMountDependencies):EmailHandle{
 const app=createApp(EmailPageShell,{api:createEmailApi(),deps,initialView:deps.view||'overview',initialVisible:deps.visible||false});
 const owner=app.mount(element) as InstanceType<typeof EmailPageShell>;
 return{setView:owner.setView,setVisible:owner.setVisible,refreshOverview:owner.refreshOverview,refreshInventory:owner.refreshInventory,refreshHistory:owner.refreshHistory,refreshDerivationSummary:owner.refreshDerivationSummary,openImport:owner.openImport,openButlerImport:owner.openButlerImport,closeDialogs:owner.closeDialogs,destroy:()=>app.unmount()};
}
