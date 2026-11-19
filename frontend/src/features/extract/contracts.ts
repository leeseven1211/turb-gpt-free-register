import type {TaskId} from '../../api/taskIds';
export type {TaskId} from '../../api/taskIds';
export interface ExtractProvider {id:string;label?:string;modes?:string[];link_types?:string[];default_type?:string;concurrency?:number;payment_source?:string;payment_source_label?:string;unavailable_reason?:string}
export interface ExtractConfig {providers:ExtractProvider[];unavailable_providers?:ExtractProvider[];default_provider?:string;batch_workers_default?:number;batch_workers_max?:number;poll?:{active_seconds?:number;idle_seconds?:number;backoff_max_seconds?:number}}
export interface ExtractStage {state?:string;status?:string;step?:string;percent?:number|null}
export interface ExtractTask {task_id:TaskId;run_id?:TaskId;account_id?:TaskId;batch_id?:TaskId;email?:string;provider_id?:string;mode?:string;link_type?:string;task_status?:string;internal_task_status?:string;internal_extraction_status?:string;internal_payment_status?:string;local_reconcile_halted?:boolean;preflight_status?:string;extraction_status?:string;payment_status?:string;plus_status?:string;plus_state?:string;payment_phase?:string;payment_confirmation_source?:string;payment_source?:string;payment_source_label?:string;payment_order?:{remote_order_id?:string;submission_state?:string;payment_state?:string};run_count?:number;created_at?:string;updated_at?:string;message?:string;error?:string;error_code?:string;error_info?:{summary?:string};has_extract_link?:boolean;has_payment_link?:boolean;has_payment_entry?:boolean;has_qr?:boolean;progress?:{percent?:number|null;label?:string;stage?:string};stages?:{prepare?:ExtractStage;run?:ExtractStage;verify?:ExtractStage};reconcile_halt?:{halted?:boolean;label?:string;reason?:string};remote_raw?:Record<string,unknown>}
export interface ExtractBatch {batch_id:TaskId;title?:string;provider_id?:string;mode?:string;status?:string;requested_count?:number;started_count?:number;skipped_count?:number;submission_failed_count?:number;counts?:Record<string,number>;payment_source?:string;payment_source_label?:string;workers?:number;created_at?:string}
export interface ExtractQuery {page:number;size:number;provider:string;mode:string;status:string;query:string;batch:string}
export interface ExtractList {items:ExtractTask[];total:number;page:number;page_size?:number;counts:Record<string,number>}
export interface ExtractBatchList {items:ExtractBatch[];total:number;page:number;page_size?:number}
export interface CandidateFilters {query:string;source:string;date_from:string;date_to:string;extract_status:string;promotion:string}
export interface CandidatePreview {total:number;selected_count:number;items?:{account_id:TaskId;email?:string}[]}
export interface CreateBatchPayload {workers:number;title:string;provider_id:string;mode:string;type:string;filters:CandidateFilters;limit:number;submission_id:string}
export interface ExtractReceipt {ok?:boolean;accepted?:boolean;batch_id?:TaskId;task_id?:TaskId;run_id?:TaskId;started?:number;skipped?:number;failed?:number;cancelled?:number;error?:string}
export interface PaymentEntry {payment_page_url?:string;payment_url?:string;qr_data?:string;qr_image_url_png?:string;qr_image_url_svg?:string;amount?:string|number|null;currency?:string;expires_at?:string|number;payment_status?:string;platform_plus_status?:string|boolean}
export interface ExtractEvent {label?:string;stage?:string;status?:string;message?:string;at?:string;created_at?:string;time?:string}
export interface ExtractRun extends Partial<ExtractTask> {run_id:TaskId;run_no?:number;status?:string;internal_status?:string;error_message?:string;completed_at?:string}
export interface ExtractDetail {item:ExtractTask;events?:ExtractEvent[];history?:ExtractRun[]}
export interface ExtractMetrics {total?:number;extracted?:number;extraction_failed?:number;paid?:number;payment_failed?:number;plus_confirmed?:number;failed?:number;processing?:number;awaiting_payment?:number;needs_review?:number;extraction_rate?:number|null;payment_rate?:number|null;avg_seconds?:number|null;date?:string;provider_id?:string;mode?:string}
export interface ExtractAnalytics {ok?:boolean;totals:ExtractMetrics;current?:ExtractMetrics;daily:ExtractMetrics[];providers?:ExtractMetrics[];modes?:ExtractMetrics[];failures?:{count:number;label?:string;code?:string}[];date_from?:string;date_to?:string;generated_at?:string}
export interface ExtractApi {
 config(signal?:AbortSignal):Promise<ExtractConfig>;summary(signal?:AbortSignal):Promise<Record<string,number>>;
 batches(page:number,signal?:AbortSignal):Promise<ExtractBatchList>;batch(id:TaskId,signal?:AbortSignal):Promise<{item:ExtractBatch}>;
 tasks(query:ExtractQuery,signal?:AbortSignal):Promise<ExtractList>;candidates(filters:CandidateFilters,limit:number,signal?:AbortSignal):Promise<CandidatePreview>;
 create(payload:CreateBatchPayload):Promise<ExtractReceipt>;cancel(id:TaskId):Promise<ExtractReceipt>;detail(id:TaskId,signal?:AbortSignal):Promise<ExtractDetail>;
 action(id:TaskId,action:string):Promise<ExtractReceipt>;paymentEntry(id:TaskId,signal?:AbortSignal):Promise<{entry:PaymentEntry}>;
 links(id:TaskId,kind:string):Promise<{url?:string;link?:string}>;secret(id:TaskId):Promise<{value?:string;access_token?:string}>;
 analytics(days:number,provider:string,signal?:AbortSignal):Promise<ExtractAnalytics>;export(query:ExtractQuery):Promise<Blob>;
}
export interface ExtractDeps {api?:ExtractApi;visible?:boolean;dataSource?:(path:string,options?:RequestInit)=>Promise<unknown>;statsDataSource?:(path:string,options?:RequestInit)=>Promise<unknown>;notify?:(message:string)=>void;confirm?:(message:string)=>boolean|Promise<boolean>;copyText?:(value:string)=>Promise<void>;onReady?:()=>void;accountSources?:Record<string,string>}
export interface ExtractLoadOptions {force?:boolean;quiet?:boolean}
export interface ExtractWorkbenchHandle {load(options?:ExtractLoadOptions):Promise<void>;setVisible(value:boolean):void;openCreate():Promise<void>;switchBatch(id:TaskId|''):Promise<void>;openDetail(id:TaskId):Promise<void>;showPaymentEntry(id:TaskId):Promise<void>;taskAction(id:TaskId,action:string):Promise<void>;showLink(id:TaskId,kind:string):Promise<void>;copy(id:TaskId,kind:string):Promise<void>;copyPayment(key:'payment_page_url'|'payment_url'|'qr_data'):Promise<void>;bulkAction(action:string):Promise<void>;cancelBatch(options?:{confirmed?:boolean}):Promise<void>;exportRows(filtered?:boolean):Promise<void>;closeDialogs():void;destroy():void}
export interface ExtractStatsHandle {load():Promise<void>;setVisible(value:boolean):void;destroy():void}
