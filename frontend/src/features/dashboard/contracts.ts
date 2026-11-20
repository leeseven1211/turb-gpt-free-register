import type {DashboardApi,PendingCapabilities} from '../../api/dashboard';
export interface DashboardDeps {
 visible?:boolean;
 notify?(message:string):void;
 onNavigate?(tab:string):void;
 onConfig?(group:string):void;
 onCapabilities?(value:any):void;
 onReady?():void;
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
