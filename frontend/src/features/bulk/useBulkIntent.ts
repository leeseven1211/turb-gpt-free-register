import type {BulkApi,BulkIntentClient,BulkIntentRecord,BulkRecord,BulkStorage} from './contracts';
import {BulkApiError} from '../../api/bulk';

const prefix='turb_bulk_intent:';
const rejected=new Set([400,403,404,409,410,422,429]);
/** Persist the exact request before sending; unknown receipts retain the original key and body. */
export function createBulkIntent(api:BulkApi,storage:BulkStorage,randomKey:()=>string):BulkIntentClient {
  const inflight=new Map<string,{signature:string;promise:Promise<unknown>}>();
  function decode(storageKey:string,value:string|null):BulkIntentRecord|null {
    if(!value)return null;
    const saved=JSON.parse(value) as {key?:unknown;signature?:unknown};
    if(typeof saved.key!=='string'||typeof saved.signature!=='string')throw new Error('未决请求记录无效，请先检查原回执');
    const original=JSON.parse(saved.signature) as {path?:unknown;body?:unknown};
    if(typeof original.path!=='string'||!original.body||typeof original.body!=='object'||Array.isArray(original.body))throw new Error('未决请求内容无效，请先检查原回执');
    return{storageKey,key:saved.key,signature:saved.signature,path:original.path,body:original.body as BulkRecord};
  }
  async function submit<T=BulkRecord>(scope:string,path:string,body:BulkRecord):Promise<T>{
    const storageKey=prefix+scope,signature=JSON.stringify({path,body});
    const existing=inflight.get(storageKey);
    if(existing){if(existing.signature!==signature)throw new BulkApiError('上一请求未收到回执，请先找回原请求，再提交新内容。',0,'request_receipt_pending');return existing.promise as Promise<T>;}
    const saved=decode(storageKey,storage.getItem(storageKey));
    if(saved&&saved.signature!==signature)throw new BulkApiError('上一请求未收到回执，请先找回原请求，再提交新内容。',0,'request_receipt_pending');
    const key=saved?.key||randomKey();
    storage.setItem(storageKey,JSON.stringify({key,signature}));
    const promise=api.request<T>(path,{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key},body:JSON.stringify(body)})
      .then(result=>{try{storage.removeItem(storageKey);}catch{/* An accepted receipt stays successful; replaying its retained key remains safe. */}return result;},error=>{if(rejected.has(Number(error?.status)))try{storage.removeItem(storageKey);}catch{/* Preserve the server's original rejection. */}throw error;})
      .finally(()=>inflight.delete(storageKey));
    inflight.set(storageKey,{signature,promise});return promise;
  }
  return{submit,pending(){const items:BulkIntentRecord[]=[];for(let i=0;i<storage.length;i++){const key=storage.key(i);if(key?.startsWith(prefix)){const item=decode(key,storage.getItem(key));if(item)items.push(item);}}return items;},
    recover<T=BulkRecord>(record:BulkIntentRecord){return submit<T>(record.storageKey.slice(prefix.length),record.path,record.body);}};
}
