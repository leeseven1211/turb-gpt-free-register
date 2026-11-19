import {request,ApiError} from './client';
import {parseTaskJson,taskId} from './taskIds';
import type {TaskId} from './taskIds';
import type {ExtractApi,ExtractDeps,ExtractQuery,ExtractList,ExtractBatchList,ExtractAnalytics,ExtractConfig,ExtractReceipt} from '../features/extract/contracts';
const base='/api/extract-workbench';
export function extractParams(query:ExtractQuery){const p=new URLSearchParams({provider_id:query.provider,mode:query.mode,status:query.status,query:query.query,page:String(query.page),page_size:String(query.size)});if(query.batch)p.set('batch_id',String(taskId(query.batch)));return p;}
export function createExtractApi(deps:Pick<ExtractDeps,'dataSource'|'statsDataSource'>={}):ExtractApi {
 async function read<T>(path:string,options:RequestInit={},stats=false):Promise<T>{const source=stats?(deps.statsDataSource||deps.dataSource):deps.dataSource;const payload=source?await source(path,options):await request<unknown>(path,options,parseTaskJson);if(!payload||typeof payload!=='object'||(payload as {ok?:boolean}).ok===false)throw new Error('提链接口响应无效');return payload as T;}
 const post=<T,>(path:string,body:unknown={},signal?:AbortSignal)=>read<T>(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal});
 const idPath=(id:TaskId)=>`${base}/tasks/${encodeURIComponent(taskId(id))}`;
 function list<T extends ExtractList|ExtractBatchList>(value:T):T{if(!Array.isArray(value.items)||!Number.isSafeInteger(value.total)||value.total<0||!Number.isSafeInteger(value.page)||value.page<1)throw new Error('提链分页响应无效');return value;}
 return{
  async config(signal){const value=await read<ExtractConfig>(`${base}/config`,{signal});if(!Array.isArray(value.providers))throw new Error('提链配置响应无效');return value;},
  summary:signal=>read(`${base}/summary`,{signal}),
  async batches(page,signal){const value=list(await read<ExtractBatchList>(`${base}/batches?page=${page}&page_size=20`,{signal}));for(const item of value.items)taskId(item.batch_id);return value;},
  async batch(id,signal){const value=await read<Awaited<ReturnType<ExtractApi['batch']>>>(`${base}/batches/${encodeURIComponent(taskId(id))}`,{signal});if(!value.item||String(taskId(value.item.batch_id))!==String(taskId(id)))throw new Error('提链批次响应不匹配');return value;},
  async tasks(query,signal){const value=list(await read<ExtractList>(`${base}/tasks?${extractParams(query)}`,{signal}));for(const item of value.items)taskId(item.task_id);return value;},
  async candidates(filters,limit,signal){const value=await read<Awaited<ReturnType<ExtractApi['candidates']>>>(`${base}/candidates?${new URLSearchParams({...filters,limit:String(limit)})}`,{signal});if(!Number.isSafeInteger(value.total)||!Number.isSafeInteger(value.selected_count)||value.total<0||value.selected_count<0||value.selected_count>Math.min(value.total,limit))throw new Error('候选统计响应无效');for(const item of value.items||[])taskId(item.account_id);return value;},
  create:payload=>post<ExtractReceipt>(`${base}/batches`,payload),cancel:id=>post(`${base}/batches/${encodeURIComponent(taskId(id))}/cancel`),
  detail:async(id,signal)=>{const value=await read<Awaited<ReturnType<ExtractApi['detail']>>>(idPath(id),{signal});if(!value.item||String(value.item.task_id)!==String(id))throw new Error('提链详情响应不匹配');return value;},
  action:(id,action)=>post(`${idPath(id)}/actions`,{action}),
  async paymentEntry(id,signal){const value=await post<Awaited<ReturnType<ExtractApi['paymentEntry']>>>(`${idPath(id)}/payment-entry`,{},signal);if(!value.entry||!['payment_page_url','payment_url','qr_data','qr_image_url_png','qr_image_url_svg'].some(key=>typeof value.entry[key as keyof typeof value.entry]==='string'&&value.entry[key as keyof typeof value.entry]))throw new Error('当前任务没有已保存的支付入口');return value;},
  links:(id,kind)=>post(`${idPath(id)}/links`,{kind}),
  secret:id=>read(`/api/accounts/${encodeURIComponent(taskId(id))}/secret?field=access_token`),
  async analytics(days,provider,signal){const params=new URLSearchParams({days:String(days)});if(provider)params.set('provider_id',provider);const value=await read<ExtractAnalytics>(`${base}/analytics?${params}`,{signal},true);if(!value.totals||!Array.isArray(value.daily))throw new Error('统计响应格式不完整');return value;},
  async export(query){const params=extractParams(query);params.delete('page');params.delete('page_size');const response=await fetch(`${base}/export?${params}`,{credentials:'same-origin'});if(!response.ok||response.redirected||!/(text\/csv|application\/octet-stream)/i.test(response.headers.get('content-type')||''))throw new ApiError('导出失败，请重新登录或重试',response.status);return response.blob();},
 };
}
