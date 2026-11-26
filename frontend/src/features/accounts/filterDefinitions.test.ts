import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {runInNewContext} from 'node:vm';
import {describe,expect,it} from 'vitest';
import {accountFilters,facetOptionGroups,facetOptions,filterChips} from './filterDefinitions';

describe('账号筛选定义',()=>{
 it('在现有套餐优惠筛选中提供 Team 优惠选项',()=>{
  const column=accountFilters.find(entry=>entry.key==='promotion')!;
  const query={plan:[],filters:{promotion:[]}} as never;
  const options=facetOptions(query,{promotion:[{value:'team_eligible',count:3}]} as never,column,
   (_group,value)=>value==='team_eligible'?'Team 优惠':value);
  expect(options).toContainEqual(expect.objectContaining({value:'team_eligible',count:3,label:'Team 优惠'}));
 });

 it('按真实动态分面分组展示九种优惠，并保留状态与计数',()=>{
  const column=accountFilters.find(entry=>entry.key==='promotion')!;
  const query={plan:[],filters:{promotion:[]}} as never;
  const offer=(hex:string,group:string,label:string,count:number)=>({value:`offer_v1_${hex}`,group,label,count});
  const facets={promotion:[
   offer('00000000000000000000000000000001','team','Team 免费 1 个月',7),
   offer('00000000000000000000000000000002','plus','Plus 半价 3 个月',3),
   offer('00000000000000000000000000000003','plus','Plus 免费 1 个月',8),
   offer('00000000000000000000000000000004','plus','Plus 半价 1 个月',6),
   offer('00000000000000000000000000000005','plus','Plus 半价 2 个月',5),
   offer('00000000000000000000000000000006','go','Go 半价 2 个月',4),
   offer('00000000000000000000000000000007','go','Go 免费 1 个月',9),
   offer('00000000000000000000000000000008','go','Go 半价 1 个月',2),
   offer('00000000000000000000000000000009','go','Go 半价 3 个月',1),
   {value:'none',group:'status',label:'Plus 无优惠',count:11},
   {value:'unknown',group:'status',label:'历史 Plus 待复查',count:2},
   {value:'free_trial',group:'legacy',label:'免费试用',count:99},
   {value:'eligible',group:'legacy',label:'免费试用资格',count:6},
  ]} as never;
  const groups=facetOptionGroups(query,facets,column,(_group,value)=>value);
  expect(groups.map(group=>group.key)).toEqual(['team','plus','go','status']);
  expect(groups.find(group=>group.key==='team')?.options).toEqual([
   expect.objectContaining({value:'offer_v1_00000000000000000000000000000001',count:7,label:'Team 免费 1 个月'}),
  ]);
  expect(groups.find(group=>group.key==='plus')?.options.map(option=>option.label)).toEqual([
   'Plus 免费 1 个月','Plus 半价 1 个月','Plus 半价 2 个月','Plus 半价 3 个月',
  ]);
  expect(groups.find(group=>group.key==='go')?.options.map(option=>option.label)).toEqual([
   'Go 免费 1 个月','Go 半价 1 个月','Go 半价 2 个月','Go 半价 3 个月',
  ]);
  expect(groups.find(group=>group.key==='status')?.options.map(option=>[option.label,option.count])).toEqual([
   ['Plus 无优惠',11],['历史 Plus 待复查',2],
  ]);
  expect(facetOptions(query,facets,column,(_group,value)=>value)).toHaveLength(11);
 });

 it('只在选中时保留旧泛称和零命中值，并在摘要中使用分面元数据',()=>{
  const column=accountFilters.find(entry=>entry.key==='promotion')!;
  const query={plan:[],filters:{promotion:['free_trial','offer_v1_0000000000000000000000000000000a'],source:[],registration_driver:[],token:[],account_status:[],password:[],totp:[],risk:[],codex:[],email_status:[]}} as never;
  const facets={promotion:[
   {value:'free_trial',group:'legacy',label:'免费试用',count:0},
   {value:'offer_v1_0000000000000000000000000000000a',group:'plus',label:'Plus 其他折扣 12 个月',count:0},
   {value:'none',group:'status',label:'Plus 无优惠',count:5},
  ]} as never;
  const options=facetOptions(query,facets,column,(_group,value)=>value);
  expect(options.map(option=>option.value)).toEqual([
   'offer_v1_0000000000000000000000000000000a','none','free_trial',
  ]);
  expect(filterChips(query,(_group,value)=>value,facets)).toEqual([
   expect.objectContaining({key:'promotion',label:'套餐优惠：免费试用、Plus 其他折扣 12 个月'}),
  ]);
 });

 it('按明确标签解析小数月和周单位，随机摘要键不影响优惠排序',()=>{
  const column=accountFilters.find(entry=>entry.key==='promotion')!;
  const query={plan:[],filters:{promotion:[]}} as never;
  const facets={promotion:[
   {value:'offer_v1_00000000000000000000000000000001',group:'plus',label:'Plus 半价 1.5 个月',count:1},
   {value:'offer_v1_00000000000000000000000000000002',group:'plus',label:'Plus 半价 1 周',count:1},
   {value:'offer_v1_00000000000000000000000000000003',group:'plus',label:'Plus 半价 2 个月',count:1},
   {value:'offer_v1_00000000000000000000000000000004',group:'plus',label:'Plus 免费 1 周',count:1},
   {value:'offer_v1_00000000000000000000000000000005',group:'plus',label:'Plus 其他折扣',count:1},
  ]} as never;
  expect(facetOptionGroups(query,facets,column,(_group,value)=>value).find(group=>group.key==='plus')?.options.map(option=>option.label)).toEqual([
   'Plus 免费 1 周','Plus 半价 1 周','Plus 半价 1.5 个月','Plus 半价 2 个月','Plus 其他折扣',
  ]);
 });

 it('免费优先，其余按明确折扣比例降序，同折扣期限升序，未知比例最后',()=>{
  const column=accountFilters.find(entry=>entry.key==='promotion')!;
  const query={plan:[],filters:{promotion:[]}} as never;
  const facets={promotion:[
   {value:'offer_v1_00000000000000000000000000000011',group:'plus',label:'Plus 半价 2 个月',count:1},
   {value:'offer_v1_00000000000000000000000000000012',group:'plus',label:'Plus 75% 折扣 2 个月',count:1},
   {value:'offer_v1_00000000000000000000000000000013',group:'plus',label:'Plus 75% 折扣 1 个月',count:1},
   {value:'offer_v1_00000000000000000000000000000014',group:'plus',label:'Plus 25% 折扣 1 个月',count:1},
   {value:'offer_v1_00000000000000000000000000000015',group:'plus',label:'Plus 其他折扣 1 个月',count:1},
   {value:'offer_v1_00000000000000000000000000000016',group:'plus',label:'Plus 免费 3 个月',count:1},
  ]} as never;
  expect(facetOptionGroups(query,facets,column,(_group,value)=>value).find(group=>group.key==='plus')?.options.map(option=>option.label)).toEqual([
   'Plus 免费 3 个月','Plus 75% 折扣 1 个月','Plus 75% 折扣 2 个月',
   'Plus 半价 2 个月','Plus 25% 折扣 1 个月','Plus 其他折扣 1 个月',
  ]);
 });

 it('动态键缺失 metadata 时使用可读 fallback，不把摘要键泄露到选项和 chip',()=>{
  const column=accountFilters.find(entry=>entry.key==='promotion')!;
  const offer='offer_v1_0000000000000000000000000000000a';
  const query={plan:[],filters:{promotion:[offer],source:[],registration_driver:[],token:[],account_status:[],password:[],totp:[],risk:[],codex:[],email_status:[]}} as never;
  const options=facetOptions(query,{promotion:[{value:offer,count:0}]} as never,column,(_group,value)=>value);
  expect(options[0]?.label).toBe('已选优惠（信息暂不可用）');
  expect(filterChips(query,(_group,value)=>value,{promotion:[{value:offer,count:0}]} as never)[0]?.label).toContain('已选优惠（信息暂不可用）');
  expect(options[0]?.label).not.toContain(offer);
 });

 it('动态键缺 group 时从明确套餐标签分组，label 回调前缀也不泄露原始键',()=>{
  const column=accountFilters.find(entry=>entry.key==='promotion')!;
  const offer='offer_v1_0000000000000000000000000000000b';
  const query={plan:[],filters:{promotion:[offer],source:[],registration_driver:[],token:[],account_status:[],password:[],totp:[],risk:[],codex:[],email_status:[]}} as never;
  const facets={promotion:[{value:offer,label:'Plus 半价 1 个月',count:2}]} as never;
  const groups=facetOptionGroups(query,facets,column,(_group,value)=>`旧前缀:${value}`);
  expect(groups.find(group=>group.key==='plus')?.options[0]?.label).toBe('Plus 半价 1 个月');
  const missing='offer_v1_0000000000000000000000000000000c';
  const missingQuery={plan:[],filters:{promotion:[missing],source:[],registration_driver:[],token:[],account_status:[],password:[],totp:[],risk:[],codex:[],email_status:[]}} as never;
  const fallback=facetOptions(missingQuery,{promotion:[{value:missing,count:0}]} as never,column,(_group,value)=>`旧前缀:${value}`);
  expect(fallback[0]?.label).toBe('已选优惠（信息暂不可用）');
  expect(fallback[0]?.label).not.toContain(missing);
 });

 it('未选且有计数的动态键缺 metadata 时使用通用 fallback',()=>{
  const column=accountFilters.find(entry=>entry.key==='promotion')!;
  const offer='offer_v1_0000000000000000000000000000000d';
  const query={plan:[],filters:{promotion:[],source:[],registration_driver:[],token:[],account_status:[],password:[],totp:[],risk:[],codex:[],email_status:[]}} as never;
  const option=facetOptions(query,{promotion:[{value:offer,count:3}]} as never,column,(_group,value)=>`旧前缀:${value}`)[0];
  expect(option?.label).toBe('优惠信息暂不可用');
  expect(option?.label).not.toContain(offer);
 });

 it('无分面时已选旧优惠仍使用兼容中文标签',()=>{
  const column=accountFilters.find(entry=>entry.key==='promotion')!;
  const query={plan:[],filters:{promotion:['none','plus_50'],source:[],registration_driver:[],token:[],account_status:[],password:[],totp:[],risk:[],codex:[],email_status:[]}} as never;
  const label=(_group:string,value:string)=>({none:'Plus 无优惠',plus_50:'Plus 半价优惠'}[value]||value);
  expect(facetOptions(query,{},column,label).map(option=>option.label)).toEqual(['Plus 无优惠','Plus 半价优惠']);
  expect(filterChips(query,label,{})[0]?.label).toBe('套餐优惠：Plus 无优惠、Plus 半价优惠');
 });
});

describe('旧版账号分面标签',()=>{
 it('将 team_eligible 显示为 Team 优惠',()=>{
  const source=readFileSync(resolve(process.cwd(),'../webui/static/js/shared/common.js'),'utf8');
  const sandbox={document:{querySelector:()=>null,querySelectorAll:()=>[],getElementById:()=>null,addEventListener:()=>{},body:{}},
   window:{addEventListener:()=>{}},MutationObserver:class{observe(){}},setInterval:()=>0,clearInterval:()=>{},console};
  runInNewContext(source,sandbox,{filename:'common.js'});
  expect((sandbox as unknown as {facetLabel:(group:string,value:string)=>string}).facetLabel('promotion','team_eligible')).toBe('Team 优惠');
  expect((sandbox as unknown as {facetLabel:(group:string,value:string)=>string}).facetLabel('promotion','pending')).toBe('待查询 / 查询中');
 });
});
