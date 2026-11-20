import {afterEach,describe,expect,it,vi} from 'vitest';
import {useRegistration} from './useRegistration';
import type {RegistrationApi} from '../../api/registration';
const owners:ReturnType<typeof useRegistration>[]=[];
const makeOwner=(deps:Parameters<typeof useRegistration>[0])=>{const owner=useRegistration(deps);owners.push(owner);return owner;};
afterEach(()=>{owners.splice(0).forEach(owner=>owner.dispose());});
function apiFixture():RegistrationApi{
  return {
    metadata:vi.fn(async()=>({sources:[],registration_drivers:[]})),
    summary:vi.fn(async()=>({accounts:4,email_supply:{total:2,available:1,used:1,failed:0}})),
    jobs:vi.fn(async()=>({items:[{id:'9007199254740993'}],total:1})),
    progress:vi.fn(async(id)=>({ok:true,job:{id}})),
    create:vi.fn(async()=>({submitted:1,jobs:[{id:'9007199254740993',batch_id:'b-1'}]})),
    action:vi.fn(async()=>({ok:true,message:'已受理'})),
    log:vi.fn(async()=>({job:{status:'running'},log:'x'})),
    debug:vi.fn(async()=>({enabled:false})),
    diagnostics:vi.fn(async()=>({enabled:false})),
    compare:vi.fn(async()=>({baseline_job_id:'1',difference_count:0,differences:[]})),
  };
}
describe('registration owner lifecycle',()=>{
  it('does not read while hidden and ignores a late response after hiding',async()=>{
    const api=apiFixture();let resolve!: (value:any)=>void;
    vi.mocked(api.jobs).mockImplementationOnce(()=>new Promise(done=>{resolve=done;}));
    const owner=makeOwner({api,visible:false,view:'tasks'});
    await owner.load();
    expect(api.jobs).not.toHaveBeenCalled();
    owner.setVisible(true);
    const pending=owner.load();
    owner.setVisible(false);
    resolve({items:[{id:'9007199254740993'}],total:1});
    await pending;
    expect(owner.state.jobs).toEqual([]);
    owner.setVisible(true);
    await owner.load();
    expect(owner.state.jobs[0]?.id).toBe('9007199254740993');
    owner.setVisible(false);
  });
  it('keeps create acceptance receipt separate from the follow-up read',async()=>{
    const api=apiFixture(),notify=vi.fn(),owner=makeOwner({api,visible:true,notify});
    await owner.create({count:1,workers:3,email_source:'outlook',debug_enabled:false});
    expect(owner.state.receipt).toEqual({tone:'success',message:'已提交 1 个任务'});
    expect(notify).toHaveBeenCalledWith('已提交 1 个任务');
    owner.setVisible(false);
  });
  it('advances only the latest summary response',async()=>{
    const api=apiFixture();let first!: (value:any)=>void;let second!: (value:any)=>void;
    vi.mocked(api.summary).mockImplementationOnce(()=>new Promise(done=>{first=done;})).mockImplementationOnce(()=>new Promise(done=>{second=done;}));
    const owner=makeOwner({api,visible:true});
    const a=owner.loadSummary();const b=owner.loadSummary();
    second({accounts:2,email_supply:{available:2}});await b;
    first({accounts:99,email_supply:{available:99}});await a;
    expect(owner.state.summary?.accounts).toBe(2);
    owner.setVisible(false);
  });
  it('routes operation-backed logs to TaskCenter without opening a legacy dialog',async()=>{
    const api=apiFixture(),openTask=vi.fn(),owner=makeOwner({api,visible:true,openTask});
    owner.state.jobs=[{id:'21',operation_task_id:'9007199254740993',operation_run_id:'9007199254740995'}];
    owner.openLog('21','email_otp');
    expect(openTask).toHaveBeenCalledWith('9007199254740993','9007199254740995','email_otp');
    expect(owner.state.detail.id).toBeNull();
    owner.setVisible(false);
  });
});
