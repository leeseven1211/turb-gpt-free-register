import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';

const script=readFileSync(resolve(process.cwd(),'../webui/static/js/pages/dashboard/page.js'),'utf8');
const browser=window as unknown as {
 createPageBridge?: (options:Record<string,unknown>)=>unknown;
 DashboardPage?: unknown;
 BulkTasks?: {fromAccounts?: ReturnType<typeof vi.fn>};
};
let bridge:Record<string,unknown>|undefined;
beforeEach(()=>{
 bridge=undefined;
 browser.BulkTasks={fromAccounts:vi.fn()};
 browser.createPageBridge=vi.fn(options=>{bridge=options;return{};});
 delete browser.DashboardPage;
});
afterEach(()=>{
 delete browser.createPageBridge;
 delete browser.DashboardPage;
 delete browser.BulkTasks;
 vi.restoreAllMocks();
});

it('总览桥接不再接入查套餐批量预填回调',()=>{
 new Function(script)();
 const dependencies=(bridge?.dependencies as (()=>Record<string,unknown>)|undefined)?.();
 expect(dependencies).toBeDefined();
 expect(dependencies).not.toHaveProperty('onBulkPlanCreate');
 expect(browser.BulkTasks?.fromAccounts).not.toHaveBeenCalled();
});

it('总览桥接继续把导航操作转发到目标页签',()=>{
 const navigate=vi.fn();
 vi.stubGlobal('activateTab',navigate);
 try{
  new Function(script)();
  const dependencies=(bridge?.dependencies as (()=>Record<string,unknown>)|undefined)?.();
  (dependencies?.onNavigate as ((tab:string)=>void))?.('accounts');
  expect(navigate).toHaveBeenCalledExactlyOnceWith('accounts');
 }finally{vi.unstubAllGlobals();}
});
