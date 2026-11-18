import {createApp} from 'vue';
import DashboardPage from './features/dashboard/DashboardPage.vue';
import {createDashboardApi} from './api/dashboard';
import type {DashboardHandle,DashboardMountDependencies} from './features/dashboard/contracts';
export type {DashboardHandle,DashboardMountDependencies} from './features/dashboard/contracts';
export function mountDashboard(element:HTMLElement,deps:DashboardMountDependencies={}):DashboardHandle{
 const app=createApp(DashboardPage,{api:deps.api||createDashboardApi(),deps});
 const owner=app.mount(element) as InstanceType<typeof DashboardPage>;
 return {setVisible:owner.setVisible,load:owner.load,openCustomizer:owner.openCustomizer,closeCustomizer:owner.closeCustomizer,resetLayout:owner.resetLayout,destroy:()=>app.unmount()};
}
