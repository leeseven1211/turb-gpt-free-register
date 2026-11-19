import {bulkId, type BulkRecord} from './contracts';
import {shortErrorLabel} from '../../shared/errorLabels';
import {object,rows,numeric,number,offerName,operationLabel} from './bulkReportPresentation';
export {operationNames,object,rows,numeric,number,duration,scopeText,operationLabel,planName,offerName,railWidth,businessGroups,type BusinessGroup} from './bulkReportPresentation';
const labels:Record<string,string>={pending_submit:'待提交',waiting_account:'等待账号',queued:'排队中',running:'执行中',waiting:'等待外部结果',success:'成功',partial_success:'部分成功',failed:'失败',not_executed:'未执行',not_executable:'材料或状态不满足',unassessed:'等待预检',cancelled:'已取消',preparing:'准备中',ready:'已固定',expired:'已过期',consumed:'已创建',active:'批次执行中',settling:'汇总中',completed:'已完成',ended:'已结束',paused:'已暂停',cancel_requested:'取消中',stop_requested:'停止中',pending:'待执行',confirmed:'已确认'};
export const failureStates=['attention_required','request_unknown','manual_reconcile','unknown','unconfirmed'];
export const badgeClass=(value:unknown)=>'is-'+(failureStates.includes(String(value))?'failed':String(value||'preparing'));
export const label=(value:unknown):string=>labels[failureStates.includes(String(value))?'failed':String(value)]||String(value||'—');
export const operationKey=(value:BulkRecord|null):string=>String(object(value?.operation).key||value?.operation_key||value?.action_key||'');
export function countsOf(value:unknown):Record<string,number> {const result:Record<string,number>={};for(const [key,value_] of Object.entries(object(value))){const target=failureStates.includes(key)?'failed':key;result[target]=(result[target]||0)+(numeric(value_)||0);}return result;}
export const targetId=(row:BulkRecord)=>bulkId(row.canonical_target_id||row.target_id||row.id);
function optionalId(value:unknown):string|null {return value===null||value===undefined||value===''?null:bulkId(value);}
export function resultText(result:BulkRecord):string {
  if(result.refresh_outcome)return ({pending:'等待本轮 AT 刷新',success:'本轮 AT 刷新成功',failed:'本轮 AT 刷新失败',unconfirmed:'本轮 AT 刷新失败',not_executed:'本轮未执行 AT 刷新'} as Record<string,string>)[String(result.refresh_outcome)]||'本轮 AT 刷新失败';
  if(result.query_outcome){if(result.query_outcome==='pending')return '等待本轮查询结果';if(result.query_outcome==='not_executed')return '本轮未执行';const parts=[`查询${label(result.query_outcome)}`];if(result.account_plan_type)parts.push(`套餐 ${result.account_plan_type}`);if(result.confirmed_no_offer)parts.push('本次确认无优惠');else if(result.plus_offer_kind&&result.plus_offer_kind!=='unknown')parts.push(offerName(result.plus_offer_kind));if(result.comparison&&result.comparison!=='not_comparable')parts.push(({unchanged:'优惠未变化',new_offer:'新增优惠',offer_removed:'优惠消失',changed:'优惠变化'} as Record<string,string>)[String(result.comparison)]||'优惠变化');if(Array.isArray(result.countries_requested)&&result.countries_requested.length)parts.push(`国家项成功 ${number(result.country_success_count)} / ${result.countries_requested.length}`);return parts.join(' · ');}
  if(result.confirmation)return result.confirmation==='confirmed'?'已确认 · 变更方式未记录':result.confirmation==='not_executed'?'未执行':result.confirmation==='pending'?'等待本轮设置结果':'设置失败';
  if(result.credential_confirmation)return result.credential_confirmation==='confirmed'?'本轮可用凭证已确认':result.credential_confirmation==='pending'?'等待本轮授权结果':result.existing_asset_preserved?'本轮授权失败 · 已有可用凭证保留':'本轮授权失败 · 未取得有效凭证';
  if(result.required_steps){const names:Record<string,string>={password:'密码',twofa:'2FA',codex:'Codex',access_token:'AT',plan_check:'套餐'},namesFor=(value:unknown)=>Array.isArray(value)?value.map(step=>names[String(step)]||String(step)).join('、'):'';return `已完成 ${namesFor(result.completed_steps)||'暂无'}${namesFor(result.pending_steps)?`；待完成 ${namesFor(result.pending_steps)}`:''}`;}
  return '';
}
export function projectTarget(row:BulkRecord) {
  const projected=object(row.result),result=object(projected.result||row.result_summary||projected),error=object(row.reason||projected.reason||row.error||row.error_info),display=object(row.display_snapshot||row.display),execution=object(row.execution),owned=rows(row.owned_runs)[0]||{};
  const id=targetId(row),accountId=optionalId(row.account_id||display.account_id||display.id||row.entity_id)||id;
  const account=String(display.email||row.email||`账号 #${accountId}`),summary=String(result.summary||result.message||row.result_label||row.summary_text||resultText(result)||'等待本轮结果');
  const reason=String(error.summary||error.cause_summary||error.label||error.message||row.reason_label||row.reason_code||error.code||'');
  const reasonContent=[error.summary||error.cause_summary||error.message||row.error_message||reason,error.display_code||error.code||row.reason_code].filter(Boolean).join('\n');
  const stage=String(row.stage_label||row.current_stage_label||row.stage||'').trim();
  const capabilities=Object.entries(object(result.capabilities)).map(([key,value])=>`${operationLabel(key)}：${label(object(value).state||object(value).status)}`).join('\n');
  const stateKey=row.state||row.outcome||row.status;
  const summaryShort=shortTargetResult(result,stateKey,summary);
  const reasonShort=reason?(shortErrorLabel({...error,code:error.code||row.reason_code})==='执行异常'&&[...reason].length<=10?reason:shortErrorLabel({...error,code:error.code||row.reason_code})):'';
  return {id,accountId,account,summary,summaryShort,reason,reasonShort,reasonContent,stage,capabilities,state:label(stateKey),stateKey,taskId:optionalId(row.task_id||row.owned_task_id||execution.task_id||owned.task_id),runId:optionalId(row.owned_run_id||row.run_id||execution.run_id||owned.run_id),blockerTaskId:optionalId(row.blocker_task_id)};
}
/** Visible list labels use structured outcomes; the dialog retains complete evidence. */
function shortTargetResult(result:BulkRecord,state:unknown,full:string):string {
  if([...full].length<=10)return full;
  if(result.refresh_outcome)return ({success:'AT刷新成功',pending:'等待AT刷新',not_executed:'本轮未执行'} as Record<string,string>)[String(result.refresh_outcome)]||'AT刷新失败';
  if(result.query_outcome)return ({success:result.confirmed_no_offer?'本次无优惠':'套餐已查询',pending:'等待套餐查询',not_executed:'本轮未执行',partial_success:'部分查询失败'} as Record<string,string>)[String(result.query_outcome)]||'套餐查询失败';
  if(result.confirmation)return ({confirmed:'设置已确认',pending:'等待设置结果',not_executed:'本轮未执行'} as Record<string,string>)[String(result.confirmation)]||'设置失败';
  if(result.credential_confirmation)return ({confirmed:'凭证已确认',pending:'等待授权结果'} as Record<string,string>)[String(result.credential_confirmation)]||(result.existing_asset_preserved?'授权失败已保留':'授权失败');
  if(Array.isArray(result.required_steps))return '补全结果见详情';
  const fallback=label(state);return [...fallback].length<=10&&fallback!=='—'?fallback:'结果见详情';
}
