import {afterEach,describe,expect,it,vi} from 'vitest';
import {useRegistration} from './useRegistration';
import type {RegistrationApi} from '../../api/registration';
const owners:ReturnType<typeof useRegistration>[]=[];
const makeOwner=(deps:Parameters<typeof useRegistration>[0])=>{const owner=useRegistration(deps);owners.push(owner);return owner;};
afterEach(()=>{owners.splice(0).forEach(owner=>owner.dispose());});
function apiFixture():RegistrationApi{
  return {
    metadata:vi.fn(async()=>({sources:[],registration_drivers:[],capabilities:{features:{register:{enabled:true}}}})),
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
    await owner.ensureMeta();
    await owner.create({count:1,workers:3,email_source:'outlook',debug_enabled:false});
    expect(owner.state.receipt).toEqual({tone:'success',message:'已提交 1 个任务'});
    expect(notify).toHaveBeenCalledWith('已提交 1 个任务');
    owner.setVisible(false);
  });
  it('批次重跑只提交失败与部分成功任务，取消项仍可单条重试',async()=>{
    const api=apiFixture(),confirm=vi.fn(async()=>true),owner=makeOwner({api,visible:true,confirm});
    owner.state.batchId='batch-retry';
    owner.state.batch={
      batch_id:'batch-retry',
      items:[
        {id:1,status:'failed',retryable:true},
        {id:2,status:'partial_success',retryable:true},
        {id:3,status:'cancelled',retryable:true},
        {id:4,status:'stopped',retryable:true},
        {id:5,status:'cancelled',display_status:'partial_success',retryable:true},
        {id:6,status:'stopped',display_status:'failed',retryable:true},
      ],
    };
    const cancelled=owner.state.batch.items[2]!;
    await owner.executeAction('retryBatch');
    expect(api.action).toHaveBeenCalledWith('/api/jobs/retry-bulk',{
      job_ids:[1,2],
      debug_enabled:false,
    });

    await owner.executeAction('retry',cancelled);
    expect(api.action).toHaveBeenLastCalledWith('/api/jobs/3/retry',{debug_enabled:false});
    await owner.executeAction('retryBulk',undefined,[5,6]);
    expect(api.action).toHaveBeenLastCalledWith('/api/jobs/retry-bulk',{
      job_ids:[5,6],
      debug_enabled:false,
    });
    expect(confirm).toHaveBeenCalledTimes(3);
    owner.setVisible(false);
  });
  it('does not submit before registration eligibility is confirmed',async()=>{
    const api=apiFixture(),owner=makeOwner({api,visible:true});
    await expect(owner.create({count:1,workers:3,email_source:'outlook',debug_enabled:false})).rejects.toThrow('注册资格未确认');
    expect(api.create).not.toHaveBeenCalled();
    owner.setVisible(false);
  });
  it('refreshes on visible re-entry and updates an empty inventory after the ten-second poll',async()=>{
    vi.useFakeTimers();
    try{
      const api=apiFixture(),owner=makeOwner({api,visible:false});
      vi.mocked(api.metadata)
        .mockResolvedValueOnce({sources:[],registration_drivers:[],capabilities:{features:{register:{enabled:true}}}})
        .mockResolvedValue({sources:[{value:'outlook',label:'Outlook',enabled:true}],registration_drivers:[],capabilities:{features:{register:{enabled:true}}}});
      owner.setVisible(true);
      await vi.advanceTimersByTimeAsync(0);
      expect(api.metadata).toHaveBeenCalledTimes(1);
      expect(owner.state.meta?.sources).toEqual([]);
      owner.setVisible(false);
      owner.setVisible(true);
      await vi.advanceTimersByTimeAsync(0);
      expect(api.metadata).toHaveBeenCalledTimes(2);
      expect(owner.state.meta?.sources[0]?.value).toBe('outlook');
      await vi.advanceTimersByTimeAsync(10000);
      expect(api.metadata).toHaveBeenCalledTimes(3);
      owner.setVisible(false);
    }finally{vi.useRealTimers();}
  });
  it('starts the ten-second metadata refresh from the poll deadline when the first response took 100ms',async()=>{
    vi.useFakeTimers();
    try{
      const api=apiFixture(),owner=makeOwner({api,visible:false});
      vi.mocked(api.metadata)
        .mockImplementationOnce(()=>new Promise(resolve=>{
          window.setTimeout(()=>resolve({sources:[],registration_drivers:[],capabilities:{features:{register:{enabled:true}}}}),100);
        }))
        .mockResolvedValue({sources:[{value:'outlook',label:'Outlook',enabled:true}],registration_drivers:[],capabilities:{features:{register:{enabled:true}}}});
      owner.setVisible(true);
      await vi.advanceTimersByTimeAsync(100);
      expect(api.metadata).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(9900);
      expect(api.metadata).toHaveBeenCalledTimes(2);
      expect(owner.state.meta?.sources[0]?.value).toBe('outlook');
      owner.setVisible(false);
    }finally{vi.useRealTimers();}
  });
  it('keeps the registration gate closed when a later metadata refresh fails',async()=>{
    const api=apiFixture(),owner=makeOwner({api,visible:false});
    owner.setVisible(true);
    await owner.ensureMeta();
    vi.mocked(api.metadata).mockRejectedValueOnce(new Error('库存暂时不可用'));
    await owner.ensureMeta(true);
    expect(owner.registrationUnavailable.value).toContain('库存暂时不可用');
    await expect(owner.create({count:1,workers:3,email_source:'outlook',debug_enabled:false})).rejects.toThrow('库存暂时不可用');
    expect(api.create).not.toHaveBeenCalled();
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
