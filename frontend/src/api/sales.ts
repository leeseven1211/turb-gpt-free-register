import {request as defaultRequest} from './client';

export type SalesStatus='for_sale'|'listed'|'sold';
export type SalesSyncStatus='idle'|'pending'|'running'|'success'|'failed'|'paused'|'unknown';
export interface SalesItem {
  id:number; source_id:string; account_id:number; email:string; plan:string; status:SalesStatus;
  shop_id:number|null; product_id:number|null; shop_name:string; product_name:string;
  external_inventory_id:string; order_ref:string; order_amount:number|null; currency:string; channel:string;
  price:number|null; sold_at:string|null; paid_at:string|null; note:string; listed_at:string|null;
  archived:boolean; archive_pending:boolean; sync_status:SalesSyncStatus; error_code:string; error_message:string;
  created_at:string; updated_at:string;
}
export interface SalesListResponse {ok:true;items:SalesItem[];total:number;page:number;page_size:number;counts:{all:number;for_sale:number;listed:number;sold:number}}
export interface SalesSource {id:string;name:string;kind:'local'|'remote';base_url:string;auth_env:string;enabled:boolean;created_at?:string|null;updated_at?:string|null;auth_configured?:boolean}
export interface SalesShop {id:number;name:string;platform:string;base_url:string;token_env:string;external_shop_id:string;enabled:boolean;owner_id:string;sync_interval:number;last_synced_at:string|null;error_code:string;error_message:string;created_at?:string|null;updated_at?:string|null;token_configured?:boolean}
export interface SalesProduct {id:number;shop_id:number;external_product_id:string;goods_key:string;name:string;status:string;price:number|null}
export interface SalesEvent {id:number;item_id:number;event:string;changes:Record<string,unknown>;created_at:string}
export interface SalesReceipt {id:number;status:string;error_code?:string;message?:string}
export interface SalesBatchResponse {ok:true;items:SalesReceipt[];total:number;success_count:number;failed_count:number}
export interface SalesAcceptedResponse {ok:true;accepted:true;task_id:string;run_id:string;status:string}
export interface SalesApi {
  list(params:SalesListParams):Promise<SalesListResponse>;
  sources():Promise<{ok:true;sources:SalesSource[]}>;
  shops():Promise<{ok:true;shops:SalesShop[]}>;
  products(shopId:number):Promise<{ok:true;products:SalesProduct[]}>;
  addItems(body:{source_id:string;account_ids:number[]}):Promise<SalesBatchResponse>;
  changeStatus(body:{item_ids:number[];status:SalesStatus;channel?:string;price?:number|null;currency?:string;sold_at?:string;note?:string}):Promise<SalesBatchResponse>;
  listItems(body:{shop_id:number;product_id:number;item_ids:number[];request_key:string}):Promise<SalesAcceptedResponse>;
  checkShop(shopId:number):Promise<{ok:true;shop:SalesShop;capabilities:Record<string,unknown>;product_count:number;external_shop_id:string}>;
  syncShop(shopId:number,requestKey?:string):Promise<SalesAcceptedResponse>;
  jobs():Promise<{ok:true;jobs:SalesJob[]}>;
  events(itemId:number):Promise<{ok:true;events:SalesEvent[]}>;
  saveSource(body:Partial<SalesSource>):Promise<{ok:true;source:SalesSource}>;
  saveShop(body:Partial<SalesShop>):Promise<{ok:true;shop:SalesShop}>;
}
export interface SalesJob {
  id:number|string; task_id?:string; run_id?:string; status:string; action:string; shop_id?:number|null;
  product_id?:number|null; result_summary?:unknown; error_code?:string; error_message?:string;
}
export interface SalesListParams {page:number;page_size:number;status?:string;shop_id?:number|null;source_id?:string;q?:string}
type Requester=(path:string,options?:RequestInit)=>Promise<unknown>;
function object(value:unknown):Record<string,unknown>{if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('销售接口返回格式无效');return value as Record<string,unknown>;}
function ok<T>(value:unknown,key?:string):T{const body=object(value);if(body.ok!==true)throw new Error(typeof body.error==='string'?body.error:'销售接口返回失败');if(key&&!Array.isArray(body[key]))throw new Error('销售接口返回格式无效');return body as unknown as T;}
function json(body:unknown):RequestInit{return{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};}
export function createSalesApi(request:Requester=defaultRequest):SalesApi {
  return {
    async list(params){return ok<SalesListResponse>(await request(`/api/sales/items?${new URLSearchParams(Object.entries(params).filter(([,value])=>value!==undefined&&value!==null&&value!=='').map(([key,value])=>[key,String(value)]))}`));},
    async sources(){return ok(await request('/api/sales/sources'),'sources') as {ok:true;sources:SalesSource[]};},
    async shops(){return ok(await request('/api/sales/shops'),'shops') as {ok:true;shops:SalesShop[]};},
    async products(shopId){return ok(await request(`/api/sales/shops/${encodeURIComponent(shopId)}/products`),'products') as {ok:true;products:SalesProduct[]};},
    async addItems(body){return ok(await request('/api/sales/items/add',json(body)),'items') as SalesBatchResponse;},
    async changeStatus(body){return ok(await request('/api/sales/items/status',json(body)),'items') as SalesBatchResponse;},
    async listItems(body){return ok(await request('/api/sales/list',json(body)) as unknown) as SalesAcceptedResponse;},
    async checkShop(shopId){return ok(await request(`/api/sales/shops/${encodeURIComponent(shopId)}/check`,json({}))) as {ok:true;shop:SalesShop;capabilities:Record<string,unknown>;product_count:number;external_shop_id:string};},
    async syncShop(shopId,requestKey){return ok(await request(`/api/sales/shops/${encodeURIComponent(shopId)}/sync`,json(requestKey?{request_key:requestKey}:{}))) as SalesAcceptedResponse;},
    async jobs(){return ok(await request('/api/sales/jobs'),'jobs') as {ok:true;jobs:SalesJob[]};},
    async events(itemId){return ok(await request(`/api/sales/items/${encodeURIComponent(itemId)}/events`),'events') as {ok:true;events:SalesEvent[]};},
    async saveSource(body){return ok(await request('/api/sales/sources',json(body))) as {ok:true;source:SalesSource};},
    async saveShop(body){return ok(await request('/api/sales/shops',json(body))) as {ok:true;shop:SalesShop};},
  };
}
