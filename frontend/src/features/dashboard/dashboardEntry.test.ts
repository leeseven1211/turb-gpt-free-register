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

it('dashboard bridge forwards a daily plan snapshot without consulting account selection',()=>{
 new Function(script)();
 const dependencies=(bridge?.dependencies as (()=>Record<string,unknown>)|undefined)?.();
 const query={
  q:'注册任务日期:2026-11-26..2026-11-26',
  archived:'0',
  filters:{promotion:['none']},
 };
 (dependencies?.onBulkPlanCreate as ((value:{name:string;query:typeof query})=>void))?.({
  name:'2026-11-26 无优惠账号查套餐',
  query,
 });
 expect(browser.BulkTasks?.fromAccounts).toHaveBeenCalledWith(false,'plan_check',{
  ids:[],
  query,
  name:'2026-11-26 无优惠账号查套餐',
 });
});
