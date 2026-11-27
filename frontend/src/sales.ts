import {createApp} from 'vue';
import SalesPage from './features/sales/SalesPage.vue';
import {createSalesApi,type SalesApi} from './api/sales';

export interface SalesMountOptions {
  api?:SalesApi;
  notify?:(message:string)=>void;
  executorId?:string;
  openTask?:(taskId:string,runId?:string)=>void;
  initialVisible?:boolean;
}
export function mountSales(element:HTMLElement,options:SalesMountOptions={}) {
  const app=createApp(SalesPage,{api:options.api||createSalesApi(),notify:options.notify,executorId:options.executorId,openTask:options.openTask,initialVisible:options.initialVisible});
  const instance=app.mount(element) as InstanceType<typeof SalesPage>;
  return {
    setVisible:(value:boolean)=>instance.setVisible(value),
    refresh:()=>instance.refresh(),
    addAccounts:(sourceId:string,accountIds:number[])=>instance.addAccounts(sourceId,accountIds),
    closeDialogs:()=>instance.closeDialogs?.(),
    destroy:()=>app.unmount(),
  };
}
