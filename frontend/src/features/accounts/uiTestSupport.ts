import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {runInNewContext} from 'node:vm';
import type {AccountRow,AccountsListResponse,AccountsReadApi} from '../../api/accounts';
import {createAccountQueryAdapter,type AccountQueryAdapter} from './queryAdapter';
import type {AccountPresentation} from './presentation';
export function realAdapter(){const context={window:{} as {AccountQuery:AccountQueryAdapter},URLSearchParams};runInNewContext(readFileSync(resolve(process.cwd(),'../webui/static/js/shared/account-query.js'),'utf8'),context);return createAccountQueryAdapter(context.window.AccountQuery);}
export function accountRow(id=1,fields:Partial<AccountRow>={}):AccountRow{return{id,email:`account-${id}@example.test`,has_access_token:false,has_account_password:false,totp_enabled:false,email_invalid:false,email_invalid_at:null,email_invalid_reason:null,email_invalid_source:null,plus_promo_kind:'',plus_promo_eligible:false,plus_trial_eligible:false,plus_discount_eligible:false,...fields};}
export function listResponse(items:AccountRow[],page=1,size=10,total=30):AccountsListResponse{return{ok:true,compact:true,items,total,page,page_size:size,offset:(page-1)*size,limit:size,revision:'list',facets:{},search_terms:[]};}
export function deferred<T>(){let resolve!:(value:T)=>void,reject!:(error:unknown)=>void;const promise=new Promise<T>((done,fail)=>{resolve=done;reject=fail;});return{promise,resolve,reject};}
export const presentation:AccountPresentation={
 cell(key,row){if(key==='totp')return `<button type="button" data-account-action="twofa" data-account-id="${row.id}">补充</button>`;if(key==='token')return `<button type="button" data-copy-id="copy-key-${row.id}">复制 Token</button>`;return `<span title="${key} complete evidence">${key}</span>`;},
 menu(row){return `<button type="button" data-account-email-invalid="${row.id}" data-invalid="1">标记邮箱失效</button><button type="button" data-account-delete="${row.id}">删除账号</button><button type="button" data-codex-retry="${row.email}">补跑 Codex</button>`;},
 emailInvalidBadge(){return '';},registrationDriverLabel(value){return String(value||'未记录');},facetLabel(group,value){return group==='plan'&&value==='plus'?'Plus':value;},mobileSummary(){return '来源 · 套餐';},rowTone(){return 'ok';},
};
export function readApi(){const requests:{page:number;size:number;q:string;signal?:AbortSignal}[]=[];const api:AccountsReadApi={
 async list(query,page,size,signal){requests.push({page,size,q:query.q,signal});return listResponse([accountRow(page)],page,size);},
 async statuses(_query,page,size){return{ok:true,items:[],total:0,page,page_size:size,offset:(page-1)*size,limit:size,revision:'empty',status_fields:[],queue:{workers:1,registration_workers:1,queue_limit:100,min_interval:0,jitter:0}};},
 async planDetails(){return{ok:true,item:{account_promotions:null,promotion_query_snapshot:null,plan_check_country_results:[]}};},
};return{api,requests};}
