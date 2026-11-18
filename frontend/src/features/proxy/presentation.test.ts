import {describe,expect,it} from 'vitest';
import {bytes,errorPresentation,recordDetails,trafficBytes,taskSummary} from './presentation';
import {fixtureTraffic,fixtureLease} from './fixtures';
describe('public proxy projections',()=>{
 it('distinguishes unknown/absent bytes from measured zero and preserves partial protocol semantics',()=>{
  expect(bytes(0)).toBe('0 B');expect(bytes(null)).toBe('—');expect(trafficBytes({...fixtureTraffic,total_bytes:null}).text).toBe('未采集');
  expect(trafficBytes(fixtureTraffic).title).toContain('部分字节未知');expect(trafficBytes(fixtureTraffic).secondary).toBe('部分字节未知');expect(taskSummary({operation_run_id:7}).text).toBe('未关联任务');
 });
 it('distinguishes task namespaces, deleted task types and registration-only associations',()=>{
  expect(taskSummary({operation_task_id:99}).text).toBe('未关联任务');expect(taskSummary({source:'roxy_cdp',operation_run_id:76,registration_job_id:77,operation_task_type:'registration'})).toMatchObject({text:'注册',secondary:'运行 #76 · 注册 job #77'});
  const fields=recordDetails('traffic',fixtureTraffic);expect(fields).toContainEqual({label:'任务类型',value:'查套餐'});expect(fields).toContainEqual({label:'任务',value:'9007199254740995'});expect(fields).toContainEqual({label:'运行',value:'35'});expect(fields).toContainEqual({label:'注册 job',value:'28'});
 });
 it('retains every original history detail field and no private extras',()=>{
  const fields=recordDetails('history',{...fixtureLease,proxy_url:'private-sentinel'});expect(fields.map(field=>field.label)).toEqual(['租约 ID','线路来源','出口 IP','状态','账号','用途','任务','运行','注册 job','重试序号','获取时间','到期时间','释放时间']);expect(fields).toContainEqual({label:'重试序号',value:'2'});expect(JSON.stringify(fields)).not.toContain('private-sentinel');
 });
 it('keeps full safe evidence with short error labels rather than slicing raw text',()=>{
  const result=errorPresentation('supply_candidates_duplicate');expect([...result.label].length).toBeLessThanOrEqual(10);expect(result.evidence).toContain('候选');
  expect(errorPresentation('raw-long-unknown-error-code')).toMatchObject({label:'库存异常',evidence:'raw-long-unknown-error-code'});
 });
 it('keeps the full protocol, tunnel, resource and coverage detail contract with 50-item bounds',()=>{
  const row={...fixtureTraffic,resource_details:Array.from({length:60},(_,i)=>({url:'resource-'+i,total_bytes:i,resource_type:'script'}))};
  const fields=recordDetails('traffic',row),text=fields.map(f=>f.label+' '+f.value).join('\n');
  for(const phrase of ['HTTP 传输正文','状态族','注册 Attempt','注册 Run','代理隧道传输','与页面字节重叠，不相加','没有估算节省字节','未观察到执行不能证明资源可安全拦截','resource-49'])expect(text).toContain(phrase);
  expect(text).not.toContain('resource-50');expect(text).not.toContain('[object Object]');
 });
});
