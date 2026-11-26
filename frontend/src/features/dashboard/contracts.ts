import type {DashboardApi,PendingCapabilities} from '../../api/dashboard';
import type {AccountQuerySpec} from '../accounts/queryAdapter';
export interface DashboardDeps {
 visible?:boolean;
 notify?(message:string):void;
 onNavigate?(tab:string):void;
 onConfig?(group:string):void;
 onCapabilities?(value:any):void;
 onReady?():void;
 onBulkPlanCreate?(value:{name:string;query:AccountQuerySpec}):void;
}
export interface DashboardMountDependencies extends DashboardDeps {
 api?:DashboardApi;
 pendingCapabilities?:PendingCapabilities;
}
export interface DashboardHandle {
 setVisible(value:boolean):void;
 load():Promise<void>;
 openCustomizer():void;
 closeCustomizer():void;
 resetLayout():void;
 destroy():void;
}
export type DashboardRegion='metrics'|'panels';
export interface DashboardCard {
 id:string;region:DashboardRegion;label:string;available:(data:any)=>boolean;
}
export interface DashboardPreferences {
 order:Record<DashboardRegion,string[]>;
 hidden:string[];
 sizes:Record<string,string>;
 heights:Record<string,number>;
}

export interface DailyRegistrationRow {
 date:string;
 total?:number|null;
 counts?:Record<string,number>|null;
 accounts_total?:number|null;
 plans?:Record<string,number>|null;
 unpromoted_count?:number|null;
 query?:AccountQuerySpec;
 [key:string]:unknown;
}

export type DailyRegistrationSummary=Omit<DailyRegistrationRow,'date'>;

export interface DailyRegistrationData {
 ok?:boolean;
 timezone?:string;
 date_from?:string;
 date_to?:string;
 updated_at?:string|null;
 rows?:DailyRegistrationRow[];
 summary?:DailyRegistrationSummary|null;
 [key:string]:unknown;
}

export interface DailyRegistrationStatsState {
 data:DailyRegistrationData|null;
 loading:boolean;
 error:string;
 updatedAt:string|null;
 requestedRange:{from?:string;to?:string}|null;
 displayedRange:{from?:string;to?:string}|null;
 scopeCurrent:boolean;
 load(dateFrom?:string,dateTo?:string):Promise<void>;
}
