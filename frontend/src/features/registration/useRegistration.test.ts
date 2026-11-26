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
  it('keeps the first jobs read loading until its response arrives',async()=>{
    const api=apiFixture();let resolve!: (value:any)=>void;
    vi.mocked(api.jobs).mockImplementationOnce(()=>new Promise(done=>{resolve=done;}));
    const owner=makeOwner({api,visible:false,view:'tasks'});
    owner.setVisible(true);
    expect(owner.state.loading).toBe(true);
    resolve({items:[],total:0});
    await Promise.resolve();await Promise.resolve();
    expect(owner.state.loading).toBe(false);
    expect(owner.state.jobs).toEqual([]);
    owner.setVisible(false);
  });
  it('keeps an automatic refresh error visible until a later refresh succeeds',async()=>{
    const api=apiFixture(),owner=makeOwner({api,visible:false,view:'tasks'});
    owner.setVisible(true);
    await Promise.resolve();await Promise.resolve();
    owner.state.error='上一次读取失败';
    let reject!: (reason:Error)=>void;
    vi.mocked(api.jobs).mockImplementationOnce(()=>new Promise((_,fail)=>{reject=fail;}));
    const failed=owner.load({automatic:true});
    expect(owner.state.error).toBe('上一次读取失败');
    reject(new Error('本次读取仍失败'));await failed;
    expect(owner.state.error).toBe('本次读取仍失败');
    vi.mocked(api.jobs).mockResolvedValueOnce({items:[{id:'9007199254740993'}],total:1});
    await owner.load({automatic:true});
    expect(owner.state.error).toBe('');
    owner.setVisible(false);
  });
  it('恢复同一列表范围时保持旧数据和错误提示稳定',async()=>{
    const api=apiFixture(),owner=makeOwner({api,visible:false,view:'tasks'});
    owner.setVisible(true);
    await Promise.resolve();await Promise.resolve();
    owner.state.error='上一次读取失败';
    owner.setVisible(false);
    let resolve!: (value:{items:any[];total:number})=>void;
    vi.mocked(api.jobs).mockImplementationOnce(()=>new Promise(done=>{resolve=done;}));
    owner.setVisible(true);
    expect(owner.state.loading).toBe(false);
    expect(owner.state.jobs).toEqual([{id:'9007199254740993'}]);
    expect(owner.state.error).toBe('上一次读取失败');
    resolve({items:[{id:'9007199254740993'}],total:1});
    await Promise.resolve();await Promise.resolve();
    expect(owner.state.error).toBe('');
    owner.setVisible(false);
  });
  it('首次读取和切换列表范围时仍显示加载状态',async()=>{
    const api=apiFixture(),owner=makeOwner({api,visible:false,view:'tasks'});
    let firstResolve!: (value:{items:any[];total:number})=>void;
    vi.mocked(api.jobs).mockImplementationOnce(()=>new Promise(done=>{firstResolve=done;}));
    owner.setVisible(true);
    expect(owner.state.loading).toBe(true);
    firstResolve({items:[{id:'9007199254740993'}],total:1});
    await Promise.resolve();await Promise.resolve();
    let nextResolve!: (value:{progress_batch:{batch_id:string;items:any[]}})=>void;
    vi.mocked(api.jobs).mockImplementationOnce(()=>new Promise(done=>{nextResolve=done;}));
    owner.setView('launch');
    expect(owner.state.loading).toBe(true);
    nextResolve({progress_batch:{batch_id:'batch-1',items:[]}});
    await Promise.resolve();await Promise.resolve();
    let launchResolve!: (value:{progress_batch:{batch_id:string;items:any[]}})=>void;
    vi.mocked(api.jobs).mockImplementationOnce(()=>new Promise(done=>{launchResolve=done;}));
    owner.setView('tasks');
    expect(owner.state.loading).toBe(true);
    launchResolve({progress_batch:{batch_id:'batch-1',items:[]}});
    await Promise.resolve();await Promise.resolve();
    owner.setVisible(false);
  });
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
  it('does not show a loading row while polling an expanded running log',async()=>{
    vi.useFakeTimers();
    try{
      const api=apiFixture(),owner=makeOwner({api,visible:false,view:'tasks'});
      owner.setVisible(true);
      await vi.advanceTimersByTimeAsync(0);
      vi.mocked(api.log).mockResolvedValueOnce({job:{id:'9007199254740993',status:'running'},log:'初始日志'});
      vi.mocked(api.debug).mockResolvedValue({enabled:true});
      owner.openLog('9007199254740993');
      await vi.advanceTimersByTimeAsync(0);
      expect(owner.state.detail.loading).toBe(false);
      let resolve!: (value:{job:{id:string;status:string};log:string})=>void;
      vi.mocked(api.log).mockImplementationOnce(()=>new Promise(done=>{resolve=done;}));
      await vi.advanceTimersByTimeAsync(2000);
      expect(owner.state.detail.loading).toBe(false);
      resolve({job:{id:'9007199254740993',status:'running'},log:'更新日志'});
      await vi.advanceTimersByTimeAsync(0);
      expect(owner.state.detail.loading).toBe(false);
      owner.setVisible(false);
    }finally{vi.useRealTimers();}
  });
  it('首次日志失败的自动重试保留反馈，成功后可见性恢复静默',async()=>{
    vi.useFakeTimers();
    let hidden=false;
    Object.defineProperty(document,'hidden',{configurable:true,get:()=>hidden});
    try{
      const api=apiFixture(),owner=makeOwner({api,visible:false,view:'tasks'});
      owner.setVisible(true);
      await vi.advanceTimersByTimeAsync(0);
      let reject!: (reason:Error)=>void;
      vi.mocked(api.log).mockImplementationOnce(()=>new Promise((_,fail)=>{reject=fail;}));
      vi.mocked(api.debug).mockResolvedValue({enabled:true});
      owner.openLog('9007199254740993');
      expect(owner.state.detail.loading).toBe(true);
      reject(new Error('日志暂不可用'));
      await vi.advanceTimersByTimeAsync(0);
      expect(owner.state.detail.loading).toBe(false);
      expect(owner.state.detail.error).toBe('日志暂不可用');
      let retryResolve!: (value:{job:{id:string;status:string};log:string})=>void;
      vi.mocked(api.log).mockImplementationOnce(()=>new Promise(done=>{retryResolve=done;}));
      await vi.advanceTimersByTimeAsync(2000);
      expect(owner.state.detail.loading).toBe(true);
      expect(owner.state.detail.error).toBe('日志暂不可用');
      retryResolve({job:{id:'9007199254740993',status:'running'},log:'恢复后的日志'});
      await vi.advanceTimersByTimeAsync(0);
      expect(owner.state.detail.loading).toBe(false);
      expect(owner.state.detail.error).toBe('');
      hidden=true;document.dispatchEvent(new Event('visibilitychange'));
      await vi.advanceTimersByTimeAsync(0);
      let visibleResolve!: (value:{job:{id:string;status:string};log:string})=>void;
      vi.mocked(api.log).mockImplementationOnce(()=>new Promise(done=>{visibleResolve=done;}));
      hidden=false;document.dispatchEvent(new Event('visibilitychange'));
      expect(owner.state.detail.loading).toBe(false);
      visibleResolve({job:{id:'9007199254740993',status:'running'},log:'可见性恢复后的日志'});
      await vi.advanceTimersByTimeAsync(0);
      expect(owner.state.detail.loading).toBe(false);
      owner.setVisible(false);
    }finally{
      hidden=false;
      Object.defineProperty(document,'hidden',{configurable:true,value:false});
      vi.useRealTimers();
    }
  });
});
