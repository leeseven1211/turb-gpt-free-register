import {reactive} from 'vue';
import {ApiError,isAbort} from '../../api/client';
import type {EmailApi} from '../../api/email';
import type {EmailMountDependencies,LocalImportPayload,LocalImportSource,LocalPreview,Receipt} from './contracts';
import {message,receipt} from './presentation';
export const importFormats:Record<LocalImportSource,{label:string;placeholder:string;hint:string}>={
 outlook:{label:'Outlook 邮箱池',placeholder:'email----password----clientId----refreshToken',hint:'每行一条，支持 ---- 和 ==== 分隔符；多余字段不会写入邮箱池。'},
 generic_api:{label:'通用 API 取码邮箱',placeholder:'email----取码地址----2026-12-01T12:00:00+08:00',hint:'第三字段可填写带时区的 ISO8601 有效期，每行有效期优先于批次值；旧两段格式仍支持。'},
 email_butler:{label:'Butler 已租用邮箱',placeholder:'owned@icloud.com\nowned@outlook.com',hint:'每行一个已在 Butler 长期租用的完整邮箱地址；手动导入仅恢复本人原租约。需要补充新邮箱时使用“从 Butler 导入”。'},
};
export function useLocalImport(api:EmailApi,deps:EmailMountDependencies){
 const state=reactive({open:false,source:'outlook' as LocalImportSource,text:'',expiresAt:'',preview:null as LocalPreview|null,loading:false,busy:false,error:'',receipt:null as Receipt|null});
 let active=false,disposed=false,generation=0,controller:AbortController|undefined,previewFingerprint='';
 function payload():LocalImportPayload{return{source:state.source,text:state.text,...(state.source==='generic_api'&&state.expiresAt.trim()?{expires_at:state.expiresAt.trim()}:{})};}
 function invalidate(){generation++;controller?.abort();controller=undefined;state.loading=false;state.preview=null;previewFingerprint='';}
 function update(patch:Partial<Pick<typeof state,'source'|'text'|'expiresAt'>>){Object.assign(state,patch);invalidate();state.error='';}
 async function preview():Promise<LocalPreview|null>{
  const body=payload(),fingerprint=JSON.stringify(body);invalidate();if(!active||document.hidden||!state.open||disposed)return null;
  if(!body.text.trim()){state.error='请粘贴邮箱资源';return null;}
  const ticket=generation;controller=new AbortController();state.loading=true;state.error='';
  try{const result=await api.localPreview(body,controller.signal);if(ticket!==generation||!active||document.hidden||!state.open||fingerprint!==JSON.stringify(payload()))return null;state.preview=result;previewFingerprint=fingerprint;return result;}
  catch(cause){if(ticket===generation&&!isAbort(cause))state.error=message(cause);return null;}
  finally{if(ticket===generation)state.loading=false;}
 }
 async function submit(){
  if(state.busy||!state.text.trim())return;
  const body=payload(),fingerprint=JSON.stringify(body);state.busy=true;state.error='';
  try{
   const result=state.preview&&previewFingerprint===fingerprint?state.preview:await preview();
   if(!result||fingerprint!==JSON.stringify(payload()))return;
   if(!Number(result.new||0)){state.error='没有可新增的邮箱资源，请修改内容后重新预览。';return;}
   const accepted=await api.localImport(body);
   const detail=`邮箱导入：解析 ${accepted.parsed||0} 行，已接收 ${accepted.accepted_count??accepted.inserted??0}，跳过 ${accepted.skipped||0}；导入处理中 ${accepted.pending_sync_count||0}，无效 ${accepted.invalid||0} 行，忽略多余字段 ${accepted.extra_fields||0} 个`+(accepted.invalid_rows||[]).map(row=>`\n第 ${row.line} 行：${row.reason}`).join('');
   state.receipt=receipt('导入已接收',detail,'success');
   if(JSON.stringify(payload())===fingerprint){state.text='';invalidate();}
   try{await deps.onInventoryChanged();}catch(cause){state.receipt=receipt('导入已接收',`${detail}\n显示刷新失败：${message(cause)}`,'warning');}
   deps.notify('邮箱导入已接收');
  }catch(cause){state.error=message(cause);state.receipt=cause instanceof ApiError&&cause.status>=400&&cause.status<500?receipt('导入被拒绝',`导入被拒绝：${message(cause)}。已保留原素材。`,'danger'):receipt('导入结果未确认',`导入响应未确认：${message(cause)}。已保留原素材，请先核对库存；不会自动重复提交。`,'danger');}
  finally{state.busy=false;}
 }
 return{state,update,preview,submit,
  open(source:LocalImportSource='outlook'){state.open=true;if(importFormats[source]&&state.source!==source)update({source});},
  close(){state.open=false;invalidate();},
  setActive(value:boolean){active=value;if(!value)invalidate();},
  dispose(){disposed=true;invalidate();},
 };
}
