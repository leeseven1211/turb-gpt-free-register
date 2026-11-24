import {request} from './client';
import {parseTaskJson} from './taskIds';

export type BulkMutationRequest=(path:string,options?:RequestInit)=>Promise<unknown>;
export interface BulkMutationItem {key:unknown;status:string;reason_code?:string|null;reason?:string;data?:Record<string,unknown>|null}
export interface BulkMutationReceipt {
 [key:string]:unknown;
 ok?:boolean;accepted?:boolean;command_id?:number|string;status?:string;operation?:string;
 items?:BulkMutationItem[];next_offset?:number|null;
}
export interface BulkMutationOptions {
 signal?:AbortSignal;idempotencyKey?:string;timeoutMs?:number;pollIntervalMs?:number;
 onAccepted?(receipt:BulkMutationReceipt):void;
}
export class BulkMutationPendingError extends Error {
 constructor(public readonly commandId:string,public readonly receipt:BulkMutationReceipt){
  super(`批量命令已受理，仍在执行或等待结果确认（命令 ${commandId}）。请在任务中心查看进度，勿重复提交。`);
  this.name='BulkMutationPendingError';
 }
}
function object(value:unknown):BulkMutationReceipt {
 if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('批量命令响应格式无效');
 const result=value as BulkMutationReceipt;if(result.ok===false)throw new Error('批量命令查询失败');return result;
}
function exactId(value:unknown):string {
 if(typeof value==='string'&&/^[1-9]\d*$/.test(value))return value;
 if(typeof value==='number'&&Number.isSafeInteger(value)&&value>0)return String(value);
 throw new Error('批量命令标识无效');
}
/** Preserve bigint keys as well as the task decoder's known ID fields, including data.id. */
export function parseBulkMutationJson(source:string):unknown {
 const replacements:{start:number;end:number;text:string}[]=[];
 for(const match of source.matchAll(/"(?:\\.|[^"\\])*"/g)){
  const field=JSON.parse(match[0]) as string;
  if(!['key','id','command_id'].includes(field))continue;
  const start=match.index+match[0].length,number=/^\s*:\s*(\d+)(?=\s*[,}])/.exec(source.slice(start));
  if(number&&!Number.isSafeInteger(Number(number[1]))){
   const offset=start+number[0].lastIndexOf(number[1]!);
   replacements.push({start:offset,end:offset+number[1]!.length,text:JSON.stringify(number[1])});
  }
 }
 let result='',start=0;for(const replacement of replacements){result+=source.slice(start,replacement.start)+replacement.text;start=replacement.end;}
 return parseTaskJson(result+source.slice(start));
}
export const bulkMutationRequest:BulkMutationRequest=(path,options)=>request(path,options,parseBulkMutationJson);
const terminal=new Set(['success','partial_success','failed','stopped','cancelled','interrupted','deactivated','unsupported','attention_required','terminated']);

/** Submit exactly once. After acceptance only GETs are allowed; timeout/abort retains the command reference. */
export async function submitBulkMutation(send:BulkMutationRequest,path:string,body:unknown,options:BulkMutationOptions={}):Promise<BulkMutationReceipt> {
 const key=options.idempotencyKey||crypto.randomUUID();
 const headers={'Content-Type':'application/json','Idempotency-Key':key,...(path.startsWith('/api/accounts/')?{'X-Account-Request-Key':key}:{})};
 const initial=object(await send(path,{method:'POST',headers,body:JSON.stringify(body),...(options.signal?{signal:options.signal}:{})}));
 if(initial.accepted!==true&&initial.reused!==true)return initial;
 if(initial.command_id==null)throw new Error('服务端未返回可查询的批量命令标识，请刷新核实操作结果');
 const commandId=exactId(initial.command_id),controller=new AbortController();
 options.onAccepted?.(initial);
 let timer:ReturnType<typeof setTimeout>|undefined,wake:(()=>void)|undefined;
 const pending=()=>new BulkMutationPendingError(commandId,initial);
 const stop=new Promise<never>((_,reject)=>{
  wake=()=>{controller.abort();reject(pending());};
  timer=setTimeout(wake,options.timeoutMs??30000);
  options.signal?.addEventListener('abort',wake,{once:true});
 });
 if(options.signal?.aborted)wake?.();
 const read=async(url:string)=>{
  if(controller.signal.aborted)throw pending();
  const result=object(await send(url,{signal:controller.signal}));
  if(controller.signal.aborted)throw pending();
  return result;
 };
 const polling=async()=>{
  for(;;){
   const result=await read(`/api/bulk-mutations/${encodeURIComponent(commandId)}`);
   if(result.command_id!=null&&exactId(result.command_id)!==commandId)throw new Error('批量命令回执不匹配');
   if(terminal.has(String(result.status))){
    if(!Array.isArray(result.items))throw new Error('批量命令缺少逐项回执');
    const items=[...result.items];let offset=result.next_offset;
    const offsets=new Set<number>();
    while(offset!=null){
     if(!Number.isSafeInteger(offset)||offset<0||offsets.has(offset))throw new Error('批量命令回执分页无效');
     offsets.add(offset);
     const page=await read(`/api/bulk-mutations/${encodeURIComponent(commandId)}?offset=${offset}&limit=500`);
     if(page.command_id!=null&&exactId(page.command_id)!==commandId)throw new Error('批量命令回执不匹配');
     if(!Array.isArray(page.items))throw new Error('批量命令缺少逐项回执');
     items.push(...page.items);offset=page.next_offset;
    }
    return {...initial,...result,accepted:false,items};
   }
   await new Promise<void>(resolve=>{
    const delay=setTimeout(done,options.pollIntervalMs??750);
    function done(){clearTimeout(delay);controller.signal.removeEventListener('abort',done);resolve();}
    controller.signal.addEventListener('abort',done,{once:true});
   });
   if(controller.signal.aborted)throw pending();
  }
 };
 try{return await Promise.race([polling(),stop]);}
 catch{throw pending();}
 finally{if(timer!==undefined)clearTimeout(timer);if(wake)options.signal?.removeEventListener('abort',wake);}
}
/** The existing UI consumes legacy receipt fields; only updated item receipts acknowledge selection. */
export function projectBulkMutation(result:BulkMutationReceipt,resource:'accounts'|'codex'|'email',action:'delete'|'update'):BulkMutationReceipt {
 if(!Array.isArray(result.items))return result;
 const identity=(item:BulkMutationItem):Record<string,unknown>=>{
  const data=item.data||{};
  if(resource==='accounts')return {...data,id:exactId(item.key)};
  if(resource==='codex')return {...data,filename:String(item.key)};
  const [source,...email]=String(item.key).split(':');
  return {...data,source:typeof data.source==='string'?data.source:source,email:typeof data.email==='string'?data.email:email.join(':')};
 };
 const successes=result.items.filter(item=>item.status==='updated').map(identity);
 const skipped=result.items.filter(item=>item.status!=='updated').map(item=>({...identity(item),reason_code:item.reason_code||undefined,reason:item.reason||'未完成'}));
 const field=action==='delete'?'deleted':'updated';
 return {...result,[field]:resource==='codex'&&action==='delete'?successes.map(item=>item.filename):successes,[`${field}_count`]:successes.length,skipped,skipped_count:skipped.length};
}
