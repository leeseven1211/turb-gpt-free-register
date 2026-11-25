import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {runInNewContext} from 'node:vm';
import {describe,expect,it} from 'vitest';
import {accountFilters,facetOptions} from './filterDefinitions';

describe('账号筛选定义',()=>{
 it('在现有套餐优惠筛选中提供 Team 优惠选项',()=>{
  const column=accountFilters.find(entry=>entry.key==='promotion')!;
  const query={plan:[],filters:{promotion:[]}} as never;
  const options=facetOptions(query,{promotion:[{value:'team_eligible',count:3}]} as never,column,
   (_group,value)=>value==='team_eligible'?'Team 优惠':value);
  expect(options).toContainEqual({value:'team_eligible',count:3,label:'Team 优惠'});
 });
});

describe('旧版账号分面标签',()=>{
 it('将 team_eligible 显示为 Team 优惠',()=>{
  const source=readFileSync(resolve(process.cwd(),'../webui/static/js/shared/common.js'),'utf8');
  const sandbox={document:{querySelector:()=>null,querySelectorAll:()=>[],getElementById:()=>null,addEventListener:()=>{},body:{}},
   window:{addEventListener:()=>{}},MutationObserver:class{observe(){}},setInterval:()=>0,clearInterval:()=>{},console};
  runInNewContext(source,sandbox,{filename:'common.js'});
  expect((sandbox as unknown as {facetLabel:(group:string,value:string)=>string}).facetLabel('promotion','team_eligible')).toBe('Team 优惠');
 });
});
