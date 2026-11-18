import {reactive} from 'vue';
import {createExtractApi} from '../../api/extract';
import {sameTaskId,taskId} from '../../api/taskIds';
import type {ExtractDeps,ExtractDetail,ExtractReceipt,ExtractTask,PaymentEntry,TaskId} from './contracts';
import {active,message,paymentUrl,safeReplay} from './presentation';
export function createExtractArtifacts(input:ExtractDeps={},refresh:()=>Promise<unknown>=async()=>{}){
 const api=input.api||createExtractApi(input),state=reactive({detail:null as ExtractDetail|null,detailLoading:false,detailError:'',drawer:false,nodeA:{entry:null as PaymentEntry|null,taskId:null as TaskId|null,loading:false,error:''},payment:{entry:null as PaymentEntry|null,taskId:null as TaskId|null,loading:false,error:'',open:false},receipt:null as ExtractReceipt|null,error:'',busy:new Set<string>()});
 let dead=false,detailSequence=0,paymentSequence=0,nodeSequence=0,detailController:AbortController|undefined,paymentController:AbortController|undefined,nodeController:AbortController|undefined;
 const notify=(text:string)=>input.notify?.(text);
 async function copyText(value:string){if(!value)throw Error('没有可复制内容');await (input.copyText?input.copyText(value):navigator.clipboard.writeText(value));notify('已复制');}
 async function openDetail(id:TaskId){id=taskId(id);const sequence=++detailSequence;detailController?.abort();clearNodeA();detailController=new AbortController();state.drawer=true;state.detail=null;state.detailLoading=true;state.detailError='';
  try{const value=await api.detail(id,detailController.signal);if(!dead&&sequence===detailSequence&&state.drawer){state.detail=value;if(value.item.has_payment_entry||value.item.has_payment_link||value.item.has_qr)void loadNodeA(id);}}
  catch(error){if(!dead&&sequence===detailSequence)state.detailError=message(error);}
  finally{if(sequence===detailSequence)state.detailLoading=false;}
 }
 async function loadNodeA(id:TaskId){
  id=taskId(id);const sequence=++nodeSequence;nodeController?.abort();nodeController=new AbortController();state.nodeA={entry:null,taskId:id,loading:true,error:''};
  try{const value=await api.paymentEntry(id,nodeController.signal);if(!value.entry)throw Error('当前任务没有已保存的支付入口');if(!dead&&state.drawer&&sequence===nodeSequence&&sameTaskId(state.detail?.item.task_id,id))state.nodeA.entry=value.entry;}
  catch(error){if(!dead&&state.drawer&&sequence===nodeSequence)state.nodeA.error=message(error);}
  finally{if(sequence===nodeSequence)state.nodeA.loading=false;}
 }
 async function showPaymentEntry(id:TaskId){id=taskId(id);const sequence=++paymentSequence;paymentController?.abort();paymentController=new AbortController();state.payment={entry:null,taskId:id,loading:true,error:'',open:true};
  try{const value=await api.paymentEntry(id,paymentController.signal);if(!value.entry)throw Error('当前任务没有已保存的支付入口');if(!dead&&sequence===paymentSequence&&state.payment.open)state.payment.entry=value.entry;}
  catch(error){if(!dead&&sequence===paymentSequence)state.payment.error=message(error);}
  finally{if(sequence===paymentSequence)state.payment.loading=false;}
 }
 async function taskAction(id:TaskId,action:string){id=taskId(id);const key=String(id);if(dead||state.busy.has(key))return;state.busy.add(key);state.error='';
  try{if(!['sync_status','retry','manual_payment','auto_payment'].includes(action))throw Error('不支持的任务操作');const task:ExtractTask=sameTaskId(state.detail?.item.task_id,id)?state.detail!.item:(await api.detail(id)).item;
   if(active(task))throw Error('任务正在执行，请等待当前运行结束');if(action!=='sync_status'&&!safeReplay(task))throw Error('远端结果尚未确认，请同步原任务状态，不能重新提交');
   if(action==='auto_payment'&&!(await (input.confirm?input.confirm('确认查询并继续此任务已保存的自动支付原单？'):window.confirm('确认继续此任务的自动支付？'))))return;
   const result=await api.action(id,action);if(result.accepted!==true)throw Error(result.error||'操作未接受');state.receipt=result;notify('任务操作已提交');try{await refresh();}catch{/* A refresh cannot revoke an accepted action. */}
  }catch(error){state.error=message(error);notify(state.error);}finally{state.busy.delete(key);}
 }
 async function showLink(id:TaskId,kind:string){const key=`link:${id}:${kind}`;if(state.busy.has(key))return;state.busy.add(key);state.error='';try{if(!['extract','payment'].includes(kind))throw Error('不支持的链接类型');const result=await api.links(taskId(id),kind),url=paymentUrl(result.url||result.link);if(!url)throw Error('服务端未返回有效链接');if(kind==='extract')await copyText(url);else window.open(url,'_blank','noopener,noreferrer');}catch(error){state.error=message(error);notify(state.error);}finally{state.busy.delete(key);}}
 async function copy(id:TaskId,kind:string){const key=`copy:${id}:${kind}`;if(state.busy.has(key))return;state.busy.add(key);try{if(kind==='at'){const detail=sameTaskId(state.detail?.item.task_id,id)?state.detail!:(await api.detail(id));if(!detail.item.account_id)throw Error('任务未记录账号');const secret=await api.secret(detail.item.account_id);await copyText(secret.value||'');}else if(kind==='email'){const detail=sameTaskId(state.detail?.item.task_id,id)?state.detail!:(await api.detail(id));await copyText(detail.item.email||'');}else throw Error('不支持的复制类型');}catch(error){state.error=message(error);notify(state.error);}finally{state.busy.delete(key);}}
 async function copyPayment(key:'payment_page_url'|'payment_url'|'qr_data'){try{const value=key==='qr_data'?String(state.payment.entry?.qr_data||''):paymentUrl(state.payment.entry?.[key]);await copyText(value);}catch(error){state.payment.error=message(error);}}
 async function copyNodeA(key:'payment_page_url'|'payment_url'|'qr_data'){try{const value=key==='qr_data'?String(state.nodeA.entry?.qr_data||''):paymentUrl(state.nodeA.entry?.[key]);await copyText(value);}catch(error){state.nodeA.error=message(error);}}
 function clearNodeA(){nodeSequence++;nodeController?.abort();state.nodeA={entry:null,taskId:null,loading:false,error:''};}
 function closeDetail(){detailSequence++;detailController?.abort();clearNodeA();state.drawer=false;state.detail=null;state.detailLoading=false;state.detailError='';}
 function closePayment(){paymentSequence++;paymentController?.abort();state.payment={entry:null,taskId:null,loading:false,error:'',open:false};}
 function closeDialogs(){closeDetail();closePayment();}
 function destroy(){dead=true;closeDialogs();}
 return{state,openDetail,loadNodeA,showPaymentEntry,taskAction,showLink,copy,copyPayment,copyNodeA,closeDetail,closePayment,closeDialogs,destroy};
}
