import type {BulkApi,BulkRecord} from '../features/bulk/contracts';

export class BulkApiError extends Error {
  constructor(message:string,public status:number,public code='',public details:BulkRecord={},public field:string|null=null,
    public fields:BulkRecord={},public requestId?:string,public retryable?:boolean){super(message);this.name='BulkApiError';}
}
/** Bulk keeps its domain envelope and field errors without changing other API clients. */
export function createBulkApi(fetcher:typeof fetch=fetch):BulkApi {
  return{async request<T=BulkRecord>(path:string,options:RequestInit={}):Promise<T>{
    if(!path.startsWith('/')||path.startsWith('//'))throw new Error('批量接口路径无效');
    const response=await fetcher('/api/bulk'+path,{credentials:'same-origin',...options});
    const contentType=response.headers?.get('content-type');
    if(contentType&&!contentType.includes('application/json'))throw new BulkApiError(
      response.status===401||response.redirected?'登录已失效，请重新登录后返回。':'服务返回了非 JSON 响应',response.status);
    const payload:unknown=await response.json().catch(()=>null);
    const body=payload&&typeof payload==='object'&&!Array.isArray(payload)?payload as BulkRecord:{};
    if(!response.ok||body.ok===false){
      const error=body.error&&typeof body.error==='object'&&!Array.isArray(body.error)?body.error as BulkRecord:body;
      const object=(value:unknown):BulkRecord=>value&&typeof value==='object'&&!Array.isArray(value)?value as BulkRecord:{};
      throw new BulkApiError(String(error.message||(typeof body.error==='string'?body.error:'')||`请求失败（HTTP ${response.status}）`),response.status,
        String(error.code||body.code||''),object(error.details||body.details),typeof error.field==='string'?error.field:null,
        object(error.fields||body.fields),typeof body.request_id==='string'?body.request_id:undefined,
        typeof error.retryable==='boolean'?error.retryable:undefined);
    }
    if(payload===null||typeof payload!=='object'||Array.isArray(payload)||body.ok===true&&(!body.data||typeof body.data!=='object'||Array.isArray(body.data)))throw new BulkApiError('服务返回了无效 JSON 响应',response.status);
    return (body.data??body) as T;
  }};
}
