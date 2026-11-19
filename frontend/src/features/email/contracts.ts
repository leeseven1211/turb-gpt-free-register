export type EmailView='overview'|'list'|'derivations';
export type LocalImportSource='outlook'|'generic_api'|'email_butler';
export interface EmailMountDependencies {
 view?:EmailView;visible?:boolean;
 notify(message:string):void;confirm(message:string):boolean|Promise<boolean>;
 clipboard(text:string):Promise<void>;onNavigate(view:EmailView):void;onInventoryChanged():Promise<void>;
}
export interface EmailHandle {
 setView(view:EmailView):void;setVisible(visible:boolean):void;
 refreshOverview():Promise<void>;refreshInventory():Promise<void>;refreshHistory():Promise<void>;refreshDerivationSummary():Promise<void>;
 openImport(source?:LocalImportSource):Promise<void>;openButlerImport():Promise<void>;closeDialogs():void;destroy():void;
}
export interface EmailIdentity {source:string;email:string}
export interface EmailRow extends EmailIdentity {
 id?:number|string;status?:string;usage_state?:string;registered_account_id?:number|string|null;
 resource_meta?:{password?:boolean;client_id?:boolean;refresh_token?:boolean;code_url?:boolean};
 remote_active?:boolean|null;remote_label?:string|null;last_activity_at?:string;used_at?:string;updated_at?:string;created_at?:string;synced_at?:string;
 service_sync_error?:string;note?:string;disabled_reason?:string;error_code?:string;reason_code?:string;disabled_reason_code?:string;
}
export interface InventoryQuery {page:number;size:number;source:string;q:string;status:string;used_date:string}
export interface Facet {value:string;count?:number}
export interface InventoryResponse {items:EmailRow[];total:number;facets?:{source?:Facet[];status?:Facet[]};page?:number;page_size?:number}
export interface HistoryRow {id:number|string;source:string;email:string;parent_id?:number|string;parent_email?:string;state?:string;registered_account_id?:number|string|null;root_task_id?:number|string|null;created_at?:string}
export interface HistoryQuery {page:number;size:number;source:string;parent_id:string;q:string;parent_q:string;state:string;related_q:string;created_from:string;created_to:string}
export interface ParentHistory {source:string;parent_id:number|string;parent_email?:string;child_count?:number}
export interface SourceCard {source:string;label?:string;kind?:string;enabled?:boolean|string;dependency?:boolean|string;history_available?:boolean|string;default_visible?:boolean|string;dependency_reason?:string;total?:number;available?:number;used?:number;failed?:number;disabled?:number}
export interface Receipt {label:string;detail:string;tone:'neutral'|'success'|'warning'|'danger'}
export interface LocalImportPayload {source:LocalImportSource;text:string;expires_at?:string}
export interface LocalPreview {source?:string;total_lines?:number;valid?:number;invalid?:number;invalid_rows?:{line:number;reason:string}[];duplicate_in_input?:number;existing?:number;new?:number;extra_fields?:number}
export interface LocalImportResult {inserted?:number;accepted_count?:number;pending_sync_count?:number;skipped?:number;parsed?:number;invalid?:number;invalid_rows?:{line:number;reason:string}[];extra_fields?:number}
export interface MutationItem extends EmailIdentity {reason?:string;reason_code?:string;sync?:{message?:string;lease_retained?:boolean}}
export interface MutationResult {
 deleted?:boolean|MutationItem[];deleted_count?:number;updated?:boolean|MutationItem[];updated_count?:number;skipped?:MutationItem[];
 reason?:string;reason_code?:string;sync?:{message?:string;lease_retained?:boolean};lease_retained_count?:number;
}
export interface ButlerFilters {provider:string;count:number}
export interface ButlerPreview {preview_token:string;available?:number;selected:number;resource_total?:number;availability_buckets?:Record<string,number>;filters?:ButlerFilters}
export interface ButlerRequest {request_id:string;preview_token:string;filters?:ButlerFilters}
export interface ButlerBatch {
 batch_id:string;request_id?:string;status:string;total?:number;requested?:number;
 imported?:number;skipped?:number;failed?:number;unknown?:number;pending?:number;submitting?:number;
 can_retry?:boolean;can_cancel?:boolean;internal_unknown_count?:number;internal_status?:string;
 error_code?:string;error_counts?:Record<string,number>;blocked_by?:string[];updated_at?:string;
}
export interface BatchResponse {ok?:boolean;batch:ButlerBatch}
export interface EmailStorage {getItem(key:string):string|null;setItem(key:string,value:string):void;removeItem(key:string):void}
