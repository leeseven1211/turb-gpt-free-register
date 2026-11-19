import type {AccountActionContext} from './useAccounts';

export interface LocalAccountMutationDependencies {
  request(path:string,options?:RequestInit):Promise<unknown>;
  notify(message:string):void;
  confirm(message:string):boolean|Promise<boolean>;
  prompt(message:string,initial:string):string|null|Promise<string|null>;
  refresh(context:AccountActionContext):void|Promise<unknown>;
  refreshSummary():void|Promise<unknown>;
  removeAcknowledgedSelection(ids:readonly string[],context:AccountActionContext):void;
  clearSelection(context:AccountActionContext):void;
  selectionChanged?(context:AccountActionContext):void;
  canInvoke?(descriptor:string,trigger:HTMLElement|null):boolean;
  beginBusy?(descriptor:string,trigger:HTMLElement|null,label?:string):(()=>void)|void;
}
const scopeLabel=(scope:string)=>scope==='only'?'已归档账号':scope==='all'?'全部账号':'未归档账号';
const errorMessage=(error:unknown)=>error&&typeof error==='object'&&'message' in error?String(error.message):'请求失败，请稍后重试。';
function split(descriptor:string){const separator=descriptor.indexOf(':');return{name:separator<0?descriptor:descriptor.slice(0,separator),value:separator<0?undefined:descriptor.slice(separator+1)};}
function supported(descriptor:string){const {name,value}=split(descriptor);if(['account-archive','account-email-invalid'].includes(name))return value==='0'||value==='1';if(name==='setAccountsEmailInvalid')return value===undefined||value==='0'||value==='1';return value===undefined&&['account-delete','account-restore','archiveSelectedAccounts','deleteSelectedAccounts','deleteDeactivatedAccounts'].includes(name);}
function object(value:unknown):Record<string,unknown>{if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('服务端响应格式无效');const result=value as Record<string,unknown>;if(result.ok===false)throw new Error(typeof result.error==='string'?result.error:'请求失败');return result;}
function integerCount(value:unknown):number{const count=Number(value);if(value==null||value===''||typeof value==='boolean'||!Number.isSafeInteger(count)||count<0)throw new Error('服务端响应格式无效');return count;}
function idsFrom(context:AccountActionContext):number[]{if(!Array.isArray(context?.accountIds))throw new Error('账号动作上下文不可用，请刷新后重试');return [...new Set(context.accountIds.map(id=>{if(typeof id!=='string'||! /^[1-9]\d*$/.test(id)||!Number.isSafeInteger(Number(id)))throw new Error('账号 ID 无效');return Number(id);} ))];}
function acceptedIds(value:unknown,ids:readonly number[]):string[]{if(!Array.isArray(value))throw new Error('服务端响应格式无效');return [...new Set(value.map(item=>object(item).id).filter(id=>(typeof id==='number'||typeof id==='string')&&ids.includes(Number(id))).map(String))];}

/** Local mutation semantics, isolated from the list DOM and mutable legacy selection. */
export function createLocalAccountMutations(deps:LocalAccountMutationDependencies){
  const pending=new Set<string>();
  const keyFor=(descriptor:string,context:AccountActionContext)=>descriptor.startsWith('account-')?JSON.stringify([descriptor,...context.accountIds]):split(descriptor).name;
  async function post(path:string,body:object,timeout=false){
    const controller=timeout?new AbortController():undefined;
    const timer=controller?setTimeout(()=>controller.abort(),30000):undefined;
    try{return object(await deps.request(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),...(controller?{signal:controller.signal}:{})}));}
    finally{if(timer!==undefined)clearTimeout(timer);}
  }
  async function refresh(context:AccountActionContext,summary:boolean,accepted:boolean){
    const results=await Promise.allSettled([Promise.resolve().then(()=>deps.refresh(context)),...(summary?[Promise.resolve().then(()=>deps.refreshSummary())]:[])]);
    const failure=results.find((result):result is PromiseRejectedResult=>result.status==='rejected');
    if(failure)deps.notify(`${accepted?'操作已处理，':''}页面刷新失败: ${errorMessage(failure.reason)}`);
  }
  async function invoke(descriptor:string,context:AccountActionContext,trigger:HTMLElement|null=null):Promise<void>{
    if(!supported(descriptor))throw new Error(`未支持的账号动作：${split(descriptor).name}`);
    if(deps.canInvoke?.(descriptor,trigger)===false)return;
    const {name,value}=split(descriptor),wholeScope=name==='deleteDeactivatedAccounts',emailInvalid=name==='account-email-invalid'||name==='setAccountsEmailInvalid';
    let key:string|undefined,restore:(()=>void)|undefined,attempted=false,accepted=false,refreshSummary=false;
    let prefix=wholeScope?'删除请求失败，请刷新核实：':emailInvalid?'更新邮箱失效标记失败: ':name==='account-restore'?'恢复账号失败: ':name==='deleteSelectedAccounts'?'批量删除失败: ':'删除失败: ';
    try{
      const ids=wholeScope?[]:idsFrom(context),archived=context.archived;
      if(!wholeScope&&!ids.length){deps.notify('请先选择账号');return;}
      if(name.startsWith('account-')&&ids.length!==1)throw new Error('此操作只能选择一个账号');
      key=keyFor(descriptor,context);if(pending.has(key)){key=undefined;return;}pending.add(key);
      const id=ids[0],row=wholeScope?undefined:context.rowHints.find(row=>String(row.id)===String(id));
      const email=wholeScope?'':context.expectedEmails[String(id)]||row?.email||'';
      if(emailInvalid){
        if(ids.length>500){deps.notify('单次最多操作 500 个账号');return;}
        const expectedEmails:Record<string,string>={};
        for(const accountId of ids){const captured=context.expectedEmails[String(accountId)];if(!captured){deps.notify('部分账号缺少邮箱快照，请重新勾选后操作');return;}expectedEmails[String(accountId)]=captured;}
        const invalid=value!=='0';let reason='';
        if(invalid){const input=await deps.prompt(`为 ${ids.length} 个账号标记邮箱失效，请填写原因（最多 300 字）`,'用户确认邮箱失效');if(input===null)return;reason=input.trim()||'用户确认邮箱失效';if(reason.length>300){deps.notify('邮箱失效原因最多 300 字');return;}}
        else if(!await deps.confirm(`确定解除 ${ids.length} 个账号的邮箱失效标记？\n\n仅清除本地标记，邮箱可用性仍需确认。`))return;
        restore=deps.beginBusy?.(descriptor,trigger,'更新中…')||undefined;attempted=true;
        const result=await post('/api/accounts/email-invalid-bulk',{account_ids:ids,invalid,reason,expected_emails:expectedEmails});
        const updated=integerCount(result.updated_count),skipped=Array.isArray(result.skipped)?result.skipped.length:0;
        accepted=true;deps.notify(`${invalid?'已标记邮箱失效':'已清除本地邮箱失效标记'} ${updated} 个${skipped?`，跳过 ${skipped} 个（邮箱可能已变更）`:''}`);
      }else if(wholeScope){
        if(!['0','only','all'].includes(archived))throw new Error('归档范围无效');
        if(!await deps.confirm(`确定删除「${scopeLabel(archived)}」范围内全部已废账号？\n\n不限当前页，不受勾选、搜索或其他筛选影响。仅删除本地账号记录，保留邮箱池和巡检历史。此操作不可撤销。`))return;
        restore=deps.beginBusy?.(descriptor,trigger)||undefined;attempted=true;refreshSummary=true;
        const result=await post('/api/accounts/delete-deactivated',{archived},true),count=integerCount(result.deleted_count);
        accepted=true;deps.clearSelection(context);deps.notify(`已删除 ${count} 个已废账号`);
      }else if(name==='account-restore'){
        if(!['account_status','codex_status','codex_credential_state'].some(field=>String(row?.[field as keyof typeof row]||'').toLowerCase()==='deactivated')){deps.notify('当前账号没有本地停用标记，无需恢复');return;}
        if(!await deps.confirm(`确定恢复账号 #${id}？\n\n已确认 OpenAI 恢复访问权限后，解除本地停用标记；历史封禁记录保留，AT 和 Codex 凭证需要重新验证。`))return;
        restore=deps.beginBusy?.(descriptor,trigger,'恢复中…')||undefined;attempted=true;
        const result=await post(`/api/accounts/${id}/restore`,{reason:'已收到 OpenAI 恢复访问通知'});if(String(result.id)!==String(id))throw new Error('服务端未确认账号恢复结果');
        accepted=true;refreshSummary=true;deps.notify(typeof result.message==='string'&&result.message?result.message:'已解除本地停用标记，请刷新 AT 重新验证');
      }else{
        const archive=name==='account-archive'||name==='archiveSelectedAccounts',bulk=!name.startsWith('account-'),targetArchived=bulk?archived!=='only':value==='1',action=archive?(targetArchived?'归档':'恢复'):'删除';
        prefix=`${bulk?'批量':''}${action}失败: `;
        const note=archive?(targetArchived?(bulk?'归档后默认账号列表不会查询/显示这些账号，可勾选“查看归档”单独查看。':'归档后默认账号列表不会查询/显示它，可勾选“查看归档”单独查看。'):(bulk?'恢复后这些账号会回到默认账号列表。':'恢复后会回到默认账号列表。')):'会从本地账号列表、注册成功邮箱和 token 文件中移除。';
        if(!await deps.confirm(bulk?`确定${action}选中的 ${ids.length} 个账号吗？\n\n${note}`:`确定${action}账号 #${id}？\n\n${email}\n\n${note}`))return;
        restore=deps.beginBusy?.(descriptor,trigger,archive?`${action}中…`:undefined)||undefined;attempted=true;
        const result=await post(bulk?`/api/accounts/${archive?'archive':'delete'}-bulk`:`/api/accounts/${id}/${archive?'archive':'delete'}`,bulk?{account_ids:ids,...(archive?{archived:targetArchived}:{})}:archive?{archived:targetArchived}:{});
        let acknowledged:string[],notice:string;
        if(bulk){acknowledged=acceptedIds(result[archive?'updated':'deleted'],ids);const count=integerCount(result[archive?'updated_count':'deleted_count']),skipped=Array.isArray(result.skipped)?result.skipped.length:0;notice=`已${action} ${count} 个${skipped?`，跳过 ${skipped} 个`:''}`;}
        else{if(result[archive?'updated':'deleted']!==true||(archive||result.id!==undefined)&&String(result.id)!==String(id))throw new Error('服务端未确认账号操作结果');acknowledged=[String(id)];notice=archive?(targetArchived?'账号已归档':'账号已恢复'):'账号已删除';}
        accepted=true;refreshSummary=true;if(acknowledged.length)deps.removeAcknowledgedSelection(acknowledged,context);deps.notify(notice);
      }
    }catch(error){deps.notify(`${accepted?'操作已处理，页面更新失败: ':prefix}${errorMessage(error)}`);}
    finally{
      if(accepted||(wholeScope&&attempted))await refresh(context,refreshSummary||wholeScope,accepted);
      try{if(attempted)deps.selectionChanged?.(context);}finally{try{restore?.();}finally{if(key)pending.delete(key);}}
    }
  }
  return{isSupported:supported,invoke,isPending:(descriptor:string,context:AccountActionContext)=>pending.has(keyFor(descriptor,context))};
}
