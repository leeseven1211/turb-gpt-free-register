import type {EmailIdentity,EmailRow,HistoryRow,Receipt} from './contracts';
export const sourceLabels:Record<string,string>={all:'全部邮箱池',outlook:'Outlook',generic_api:'通用 API',cloudflare_domain:'域名邮箱',icloud_hide:'iCloud 隐藏邮箱',email_butler:'Butler 本地邮箱'};
export const statusLabels:Record<string,string>={available:'可用',used:'已用',pending_sync:'导入处理中',tombstone:'本地已删除',replaced:'换绑后邮箱',failed:'失败',disabled:'已停用'};
export const usageLabels:Record<string,string>={available:'待领取',pending_sync:'导入处理中',tombstone:'本地已删除',used_unbound:'已领取未绑定',bound:'已绑定账号',replaced:'换绑后邮箱',failed:'失败',disabled:'已停用'};
export const historyLabels:Record<string,string>={available:'历史未领取',disabled:'已停用',reserved:'归属已保留',used:'已绑定账号',replaced:'换绑后地址',retired:'历史停用'};
export const identity=(row:EmailIdentity):EmailIdentity=>({source:row.source,email:row.email});
export const keyOf=(row:EmailIdentity)=>`${row.source}|${row.email}`;
export const message=(cause:unknown)=>cause instanceof Error?cause.message:String(cause);
export function short(value:string,limit=10){const chars=Array.from(value);return chars.length>limit?chars.slice(0,limit-1).join('')+'…':value;}
export function receipt(label:string,detail:string,tone:Receipt['tone']='neutral'):Receipt{return{label:short(label),detail,tone};}
export function credentials(row:EmailRow):{text:string;detail:string}{
 const meta=row.resource_meta||{};
 if(row.source==='outlook'){const fields=[['password','密码'],['client_id','Client ID'],['refresh_token','Refresh Token']] as const;return{text:`${fields.filter(([key])=>meta[key]).length}/3 已配置`,detail:fields.map(([key,label])=>`${label}：${meta[key]?'已配置':'缺少'}`).join('；')};}
 if(row.source==='generic_api')return{text:meta.code_url?'取码地址已配置':'缺少取码地址',detail:'地址仅在按需复制时读取'};
 if(row.source==='icloud_hide')return{text:'Apple 别名',detail:row.remote_active===true?'远程已激活':row.remote_active===false?'远程未激活':'远程状态未知'};
 if(row.source==='email_butler')return{text:'Butler 收码连接',detail:'使用导入时保存的收码设置'};
 return{text:'运行时配置',detail:'由来源服务管理'};
}
export function ownership(row:HistoryRow){return[row.registered_account_id?`账号 #${row.registered_account_id}`:'',row.root_task_id?`任务 #${row.root_task_id}`:''].filter(Boolean).join(' · ')||(['available','disabled'].includes(row.state||'')?'尚未领取':'历史归属');}
export const deletionWarning='保留使用历史；缺少注册完成回执时保留原租约，确认账号未创建后才可退还。已确认注册成功的邮箱不能删除。';
export function reasonSummary(row:EmailRow){
 const labels:Record<string,string>={service_fact_sync_pending:'导入处理中',registration_confirmed:'注册成功保护',registration_result_unverified:'注册结果未确认',local_email_conflict:'邮箱占用冲突',lease_expired:'租约已到期',lease_released:'租约已退还',lease_revoked:'租约已收回',lease_not_found:'原租约缺失',request_unknown:'回执未确认',request_timeout:'请求超时',transport_error:'连接异常'};
 return labels[row.error_code||row.reason_code||row.disabled_reason_code||'']||(row.service_sync_error?'处理异常':row.note?'备注记录':row.disabled_reason?'停用原因':'—');
}
