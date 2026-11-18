/** Safe numeric IDs remain compatible; PostgreSQL bigint IDs retain their exact decimal text. */
export type TaskId=number|string;
const idFields=['id','task_id','job_id','run_id','last_run_id','current_run_id','codex_active_run_id','parent_task_id','parent_job_id','parent_id','root_task_id','root_job_id','baseline_job_id','child_task_id','blocker_task_id','owned_task_id','registered_account_id','account_id','sub2api_account_id','related_task_id','related_run_id','owner_task_id','owner_run_id','operation_task_id','operation_run_id','registration_job_id','registration_attempt_id','registration_run_id','event_id','next_after_id','attempt_id','batch_id','existing_batch_id','bulk_batch_id','source_job_id','latest_legacy_job_id','target_id','canonical_target_id'] as const;
type IdField=typeof idFields[number];
type IdValue<T>=T extends number?TaskId:T;
type IdArray<T>=T extends number[]?TaskId[]:T;
export type TaskResponse<T>=T extends readonly unknown[]?{[K in keyof T]:TaskResponse<T[K]>}:T extends object?{[K in keyof T]:K extends IdField?IdValue<T[K]>:K extends 'deleted'|'event_ids'|'job_ids'|'task_ids'|'run_ids'|'attempt_ids'|'account_ids'|'target_ids'|'child_task_ids'|'parent_task_ids'?IdArray<T[K]>:TaskResponse<T[K]>}:T;
export function taskId(value:unknown):TaskId {
 if(typeof value==='number'){if(Number.isSafeInteger(value)&&value>0)return value;throw new Error('任务或运行标识无效');}
 if(typeof value!=='string'||!/^[1-9]\d*$/.test(value))throw new Error('任务或运行标识无效');
 const number=Number(value);return Number.isSafeInteger(number)?number:value;
}
export function optionalTaskId(value:unknown):TaskId|null {return value==null||value===''||value===0||value==='0'?null:taskId(value);}
export function sameTaskId(left:unknown,right:unknown):boolean {return left!=null&&right!=null&&String(left)===String(right);}
export function compareTaskIds(left:TaskId,right:TaskId):number {const a=String(left),b=String(right);return a.length-b.length||(a<b?-1:a>b?1:0);}

/** Lex JSON tokens before parsing, changing only integer ID values. Strings and non-ID numbers are untouched. */
export function parseTaskJson(source:string):unknown {
 const identifiers=new Set<string>(idFields),arrays=new Set(['event_ids','job_ids','task_ids','run_ids','attempt_ids','account_ids','target_ids','child_task_ids','parent_task_ids','deleted']);
  const records=new Set(['task','tasks','run','runs','job','jobs','attempt','attempts','parent','parents','batch','batches','items','event','events','account','accounts','target','targets','resource','resources','related_task','related_run','owned_task','owned_run']);
 const replacements:{start:number;end:number;text:string}[]=[];let cursor=0;
 const fail=()=>{throw new SyntaxError('任务响应 JSON 格式无效');};
 const space=()=>{while(/[\t\n\r ]/.test(source[cursor]||'\0'))cursor++;};
 function string():string {
  const start=cursor;if(source[cursor++]!=='"')return fail();
  while(cursor<source.length){const char=source[cursor++];if(char==='\\'){cursor++;continue;}if(char==='"')return JSON.parse(source.slice(start,cursor)) as string;}
  return fail();
 }
 function value(field='',depth=0,path:string[]=[]):void {
  if(depth>256)throw new SyntaxError('任务响应嵌套过深');space();const char=source[cursor];
  if(char==='{'){
   cursor++;space();if(source[cursor]==='}'){cursor++;return;}
   for(;;){space();const key=string();space();if(source[cursor++]!==':')fail();value(key,depth+1,[...path,key]);space();const separator=source[cursor++];if(separator==='}')return;if(separator!==',')fail();}
  }
  if(char==='['){cursor++;space();if(source[cursor]===']'){cursor++;return;}for(;;){value(arrays.has(field)?'array_id':'',depth+1,[...path,'[]']);space();const separator=source[cursor++];if(separator===']')return;if(separator!==',')fail();}}
  if(char==='"'){string();return;}
  for(const literal of ['true','false','null'])if(source.startsWith(literal,cursor)){cursor+=literal.length;return;}
  const number=source.slice(cursor).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);if(!number)return fail();
  const token=number[0],start=cursor;cursor+=token.length;
  const parent=path.filter(segment=>segment!=='[]').at(-2);
  if(field==='array_id'||identifiers.has(field)&&(field!=='id'||!parent||records.has(parent))){
   if(!/^\d+$/.test(token))throw new SyntaxError('任务响应中的标识必须为非负整数');
   if(!Number.isSafeInteger(Number(token)))replacements.push({start,end:cursor,text:JSON.stringify(token)});
  }
 }
 value();space();if(cursor!==source.length)fail();
 let result='',start=0;for(const replacement of replacements){result+=source.slice(start,replacement.start)+replacement.text;start=replacement.end;}
 return JSON.parse(result+source.slice(start));
}
