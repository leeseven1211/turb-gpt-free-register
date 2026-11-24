import {afterEach,describe,expect,it,vi} from 'vitest';
import {createExtractWorkbench} from './useExtractWorkbench';
import {createExtractBatch} from './useExtractBatch';
import {createExtractArtifacts} from './useExtractArtifacts';
import {createExtractStats} from './useExtractStats';
import type {ExtractApi} from './contracts';
import {BulkMutationPendingError} from '../../api/bulkMutations';
const deferred=<T,>()=>{let resolve!:(value:T)=>void,reject!:(error:Error)=>void;const promise=new Promise<T>((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};};
export const apiStub=()=>({config:vi.fn(async()=>({providers:[{id:'legacy',modes:['extract_only','auto_payment'],link_types:['upi'],default_type:'upi'}],batch_workers_default:2})),summary:vi.fn(async()=>({today_extracted:1})),batches:vi.fn(async()=>({items:[],total:0,page:1,page_size:20})),batch:vi.fn(async()=>({item:{batch_id:4}})),tasks:vi.fn(async()=>({items:[],total:0,page:1,page_size:20,counts:{}})),candidates:vi.fn(async()=>({total:800,selected_count:100,items:[]})),create:vi.fn(async()=>({ok:true,batch_id:9,started:500})),cancel:vi.fn(async()=>({ok:true,cancelled:1})),detail:vi.fn(async()=>({item:{task_id:1},events:[]})),action:vi.fn(async()=>({ok:true,accepted:true})),paymentEntry:vi.fn(async()=>({ok:true,entry:{payment_url:'https://pay.example/'}})),links:vi.fn(async()=>({url:'https://pay.example/'})),secret:vi.fn(async()=>({value:'secret'})),analytics:vi.fn(async()=>({ok:true,totals:{total:1},daily:[],providers:[],modes:[],failures:[]})),export:vi.fn(async()=>new Blob(['csv']))}) as unknown as ExtractApi;
afterEach(()=>vi.useRealTimers());
describe('extract read ownership',()=>{
 it('drops old lists and hidden-page replies; retains independent batch and config caches',async()=>{
  const api=apiStub(),m=createExtractWorkbench({api,visible:true});await m.load();const first=deferred<any>(),next=deferred<any>();vi.mocked(api.tasks).mockReturnValueOnce(first.promise).mockReturnValueOnce(next.promise);m.state.query.query='old';const a=m.load();m.state.query.query='new';const b=m.load();next.resolve({items:[{task_id:'9007199254740993'}],total:1,page:1,counts:{}});await b;first.resolve({items:[{task_id:1}],total:1,page:1,counts:{}});await a;expect(m.state.items[0]?.task_id).toBe('9007199254740993');expect(api.config).toHaveBeenCalledTimes(1);expect(api.batches).toHaveBeenCalledTimes(1);await m.load({force:true});expect(api.config).toHaveBeenCalledTimes(2);expect(api.batches).toHaveBeenCalledTimes(2);const late=deferred<any>();vi.mocked(api.tasks).mockReturnValueOnce(late.promise);const pending=m.load();m.setVisible(false);late.resolve({items:[{task_id:8}],total:1,page:1,counts:{}});await pending;expect(m.state.items).not.toEqual([{task_id:8}]);m.destroy();
 });
 it('batch switching clears task filters without discarding the batch navigation cache',async()=>{
  const api=apiStub(),m=createExtractWorkbench({api,visible:true});await m.load();m.state.query.status='failed';m.state.query.page=4;await m.switchBatch('9007199254740993');expect(m.state.query.page).toBe(1);expect(m.state.query.status).toBe('');expect(api.batches).toHaveBeenCalledTimes(1);expect(api.tasks).toHaveBeenLastCalledWith(expect.objectContaining({batch:'9007199254740993',page:1}),expect.any(AbortSignal));m.destroy();
 });
 it('failed list reads retain data, retry within configured bounds and stop all reads when hidden',async()=>{
  vi.useFakeTimers();const api=apiStub(),m=createExtractWorkbench({api,visible:true});await m.load();vi.mocked(api.tasks).mockRejectedValue(new Error('offline'));await m.load();expect(m.state.error).toBe('offline');expect(vi.getTimerCount()).toBe(1);m.setVisible(false);await vi.advanceTimersByTimeAsync(600000);expect(api.tasks).toHaveBeenCalledTimes(2);m.destroy();
 });
});
describe('extract create receipts',()=>{
 it('keeps one submission after a lost reply and never writes twice concurrently',async()=>{
  const api=apiStub(),pending=deferred<any>();vi.mocked(api.create).mockReturnValueOnce(pending.promise).mockRejectedValueOnce(new Error('offline'));
  const b=createExtractBatch({api,confirm:()=>true},async()=>{throw new Error('list offline');});await b.open(await api.config());await b.preview();const a=b.submit();await b.submit();expect(api.create).toHaveBeenCalledTimes(1);pending.reject(new Error('lost'));await a;await b.submit();expect(vi.mocked(api.create).mock.calls[0]?.[0].submission_id).toBe(vi.mocked(api.create).mock.calls[1]?.[0].submission_id);
  vi.mocked(api.create).mockResolvedValueOnce({ok:true,batch_id:9,started:500});await b.submit();expect(b.state.receipt?.batch_id).toBe(9);expect(b.state.error).toBe('');expect(b.state.feedback).toContain('已创建批次');b.destroy();
 });
 it('invalidates candidates immediately and refuses invalid workers or mode',async()=>{const api=apiStub(),b=createExtractBatch({api},async()=>{});await b.open(await api.config());await b.preview();b.state.filters.promotion='none';b.invalidate();await b.submit();expect(api.create).not.toHaveBeenCalled();await b.preview();b.state.workers=0;await b.submit();expect(api.create).not.toHaveBeenCalled();b.destroy();});
});
describe('extract independent dialogs',()=>{
 it('ignores late payment/detail replies when closed or another task opens',async()=>{const api=apiStub(),old=deferred<any>();vi.mocked(api.paymentEntry).mockReturnValueOnce(old.promise);const a=createExtractArtifacts({api});const p=a.showPaymentEntry(1);await a.showPaymentEntry(2);old.resolve({entry:{qr_data:'old'}});await p;expect(a.state.payment.entry?.payment_url).toBe('https://pay.example/');a.closeDialogs();expect(a.state.payment.entry).toBeNull();a.destroy();});
 it('stores accepted action receipt even when the following list refresh fails',async()=>{const api=apiStub(),a=createExtractArtifacts({api},async()=>{throw new Error('list failed');});await a.taskAction(1,'sync_status');expect(a.state.receipt?.accepted).toBe(true);expect(a.state.error).toBe('');expect(api.action).toHaveBeenCalledTimes(1);a.destroy();});
});
describe('extract stats scopes',()=>{
 it('hides previous range data while new range loads, discards late responses and retains same-scope data on failure',async()=>{const api=apiStub(),s=createExtractStats({api,visible:true});await s.load();vi.mocked(api.analytics).mockRejectedValueOnce(new Error('offline'));await s.load();expect(s.state.data?.totals.total).toBe(1);const old=deferred<any>();vi.mocked(api.analytics).mockReturnValueOnce(old.promise);s.state.days=7;const p=s.load();expect(s.state.data).toBeNull();s.state.days=90;await s.load();old.resolve({ok:true,totals:{total:7},daily:[]});await p;expect(s.state.data?.totals.total).toBe(1);s.setVisible(false);await s.load();expect(api.analytics).toHaveBeenCalledTimes(4);s.destroy();});
});

describe('baseline migration boundaries',()=>{
 it('renders tasks while config, summary and navigation are still pending or failed',async()=>{
  const api=apiStub(),config=deferred<any>(),summary=deferred<any>(),batches=deferred<any>();
  vi.mocked(api.config).mockReturnValue(config.promise);vi.mocked(api.summary).mockReturnValue(summary.promise);vi.mocked(api.batches).mockReturnValue(batches.promise);
  const m=createExtractWorkbench({api,visible:true});const p=m.load();await Promise.resolve();expect(api.tasks).toHaveBeenCalledTimes(1);await p;expect(m.state.loading).toBe(false);config.reject(Error('config offline'));summary.reject(Error('summary offline'));batches.reject(Error('nav offline'));await Promise.resolve();await Promise.resolve();expect(m.state.error).toBe('');m.destroy();
 });
 it('shares in-flight auxiliary reads across overlapping task loads and ignores old batch-detail scope',async()=>{
  const api=apiStub(),config=deferred<any>(),batches=deferred<any>(),detail=deferred<any>();vi.mocked(api.config).mockReturnValue(config.promise);vi.mocked(api.batches).mockReturnValue(batches.promise);vi.mocked(api.batch).mockReturnValueOnce(detail.promise);
  const m=createExtractWorkbench({api,visible:true});await m.load();await m.load({quiet:true});expect(api.config).toHaveBeenCalledTimes(1);expect(api.batches).toHaveBeenCalledTimes(1);const a=m.switchBatch(1);await a;await m.switchBatch(2);detail.resolve({item:{batch_id:1}});await Promise.resolve();await Promise.resolve();expect(String(m.state.batchDetail?.batch_id)).not.toBe('1');config.resolve({providers:[]});batches.resolve({items:[],total:0,page:1});m.destroy();
 });
 it('uses server poll configuration and stops polling on browser visibility loss',async()=>{
  vi.useFakeTimers();const api=apiStub();vi.mocked(api.config).mockResolvedValue({providers:[],poll:{active_seconds:7,idle_seconds:19,backoff_max_seconds:25}});vi.mocked(api.tasks).mockResolvedValue({items:[],total:0,page:1,counts:{processing:1}});const m=createExtractWorkbench({api,visible:true});await m.load();await Promise.resolve();await vi.advanceTimersByTimeAsync(6999);expect(api.tasks).toHaveBeenCalledTimes(1);await vi.advanceTimersByTimeAsync(1);expect(api.tasks).toHaveBeenCalledTimes(2);Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));await vi.advanceTimersByTimeAsync(60000);expect(api.tasks).toHaveBeenCalledTimes(2);Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));m.destroy();
 });
 it('discards invalidated candidates without assigning the new filter signature',async()=>{
  const api=apiStub(),old=deferred<any>();vi.mocked(api.candidates).mockReturnValueOnce(old.promise);const b=createExtractBatch({api});await b.open(await api.config());const p=b.preview();b.state.filters.query='new';b.invalidate();old.resolve({total:800,selected_count:500});await p;await b.submit();expect(b.state.preview).toBeNull();expect(api.create).not.toHaveBeenCalled();b.destroy();
 });
 it('uses configured default provider/type/workers and changing providers selects only allowed modes and types',async()=>{
  const api=apiStub(),b=createExtractBatch({api});await b.open({providers:[{id:'legacy',modes:['extract_only'],link_types:['pix','upi'],default_type:'upi'},{id:'huanguang',modes:['auto_payment'],link_types:['upi']}],default_provider:'legacy',batch_workers_default:7,batch_workers_max:10});expect(b.state.type).toBe('upi');expect(b.state.workers).toBe(7);b.setProvider('huanguang');expect(b.state.mode).toBe('');expect(b.state.type).toBe('upi');b.destroy();
 });
 it('auto payment confirmation locks submission before awaiting confirmation',async()=>{
  const api=apiStub(),ask=deferred<boolean>();const b=createExtractBatch({api,confirm:()=>ask.promise});await b.open(await api.config());await b.preview();b.state.mode='auto_payment';const p=b.submit();await b.submit();ask.resolve(true);await p;expect(api.create).toHaveBeenCalledTimes(1);b.destroy();
 });
 it('new-range errors never restore old analytics and late hidden analytics does not mutate',async()=>{
  const api=apiStub(),s=createExtractStats({api,visible:true});await s.load();s.state.days=7;vi.mocked(api.analytics).mockRejectedValueOnce(Error('offline'));await s.load();expect(s.state.data).toBeNull();const old=deferred<any>();vi.mocked(api.analytics).mockReturnValueOnce(old.promise);const p=s.load();s.setVisible(false);old.resolve({totals:{total:999},daily:[]});await p;expect(s.state.data).toBeNull();s.destroy();
 });
 it('deduplicates action writes and refuses retry/auto_payment for unknown remote outcomes',async()=>{
  const api=apiStub(),pending=deferred<any>();vi.mocked(api.detail).mockResolvedValue({item:{task_id:1,task_status:'attention_required',extraction_status:'unknown',mode:'auto_payment'},events:[]});const a=createExtractArtifacts({api,confirm:()=>true});await a.openDetail(1);await a.taskAction(1,'retry');await a.taskAction(1,'auto_payment');expect(api.action).not.toHaveBeenCalled();vi.mocked(api.action).mockReturnValueOnce(pending.promise);const p=a.taskAction(1,'sync_status');await a.taskAction(1,'sync_status');pending.resolve({accepted:true,task_id:1});await p;expect(api.action).toHaveBeenCalledTimes(1);a.destroy();
 });
});

describe('detail node A',()=>{
 it('reads saved payment artifact inside detail without opening payment dialog; old node A cannot leak into next detail',async()=>{const api=apiStub(),old=deferred<any>();vi.mocked(api.detail).mockImplementation(async id=>({item:{task_id:id,has_payment_entry:true},events:[]}));vi.mocked(api.paymentEntry).mockReturnValueOnce(old.promise).mockResolvedValueOnce({entry:{qr_data:'current'}});const a=createExtractArtifacts({api});await a.openDetail(1);await a.openDetail(2);await Promise.resolve();old.resolve({entry:{qr_data:'old'}});await Promise.resolve();await Promise.resolve();expect(a.state.nodeA.entry?.qr_data).toBe('current');expect(a.state.payment.open).toBe(false);a.closeDetail();expect(a.state.nodeA.entry).toBeNull();a.destroy();});
});

describe('post-review read and write boundaries',()=>{
 it('does not issue details after hiding during pending batch navigation',async()=>{const api=apiStub(),pending=deferred<any>();vi.mocked(api.batches).mockReturnValue(pending.promise);const m=createExtractWorkbench({api,visible:true});m.state.query.batch='8';await m.load();m.setVisible(false);pending.resolve({items:[],total:0,page:1});await Promise.resolve();await Promise.resolve();expect(api.batch).not.toHaveBeenCalled();m.destroy();});
 it('prevents a late action failure from reusing an older accepted receipt as success',async()=>{const api=apiStub();vi.mocked(api.detail).mockResolvedValue({item:{task_id:1,task_status:'failed'}});const a=createExtractArtifacts({api});await a.taskAction(1,'sync_status');vi.mocked(api.action).mockRejectedValueOnce(Error('rejected current action'));await a.taskAction(1,'sync_status');expect(a.state.receipt?.accepted).toBe(true);expect(a.state.error).toBe('rejected current action');a.destroy();});
 it('uses account_id for AT and never stores the fetched secret in reactive state',async()=>{const api=apiStub(),copyText=vi.fn(async()=>{});vi.mocked(api.detail).mockResolvedValue({item:{task_id:'9007199254740993',account_id:'9007199254740995',email:'synthetic@example.test'}});const a=createExtractArtifacts({api,copyText});await a.copy('9007199254740993','at');expect(api.secret).toHaveBeenCalledWith('9007199254740995');expect(copyText).toHaveBeenCalledWith('secret');expect(JSON.stringify(a.state)).not.toContain('secret');a.destroy();});
});

describe('independent create configuration',()=>{
 it('editing candidate filters while provider config is pending does not discard the provider config',async()=>{const api=apiStub(),config=deferred<any>();vi.mocked(api.config).mockReturnValueOnce(config.promise);const b=createExtractBatch({api});const p=b.open();b.state.filters.query='edit while loading';config.resolve({providers:[{id:'huanguang',modes:['extract_only'],link_types:['upi']}]});await p;expect(b.state.config?.providers[0]?.id).toBe('huanguang');expect(b.state.provider).toBe('huanguang');b.destroy();});
});

describe('public projection preserves remote uncertainty',()=>{
 it('does not replay failures whose authoritative internal receipt was unknown',async()=>{const api=apiStub();vi.mocked(api.detail).mockResolvedValue({item:{task_id:1,task_status:'failed',extraction_status:'failed',payment_status:'failed',internal_task_status:'attention_required',internal_extraction_status:'unknown',internal_payment_status:'request_unknown'} as any});const a=createExtractArtifacts({api,confirm:()=>true});await a.taskAction(1,'retry');await a.taskAction(1,'auto_payment');expect(api.action).not.toHaveBeenCalled();a.destroy();});
});

describe('polling remains independent from open detail',()=>{
 it('retries a failed batch switch within idle/backoff bounds even while detail is still pending',async()=>{vi.useFakeTimers();const api=apiStub(),detail=deferred<any>();vi.mocked(api.config).mockResolvedValue({providers:[],poll:{active_seconds:3,idle_seconds:5,backoff_max_seconds:12}});vi.mocked(api.tasks).mockResolvedValueOnce({items:[],total:0,page:1,counts:{processing:1}}).mockRejectedValueOnce(Error('switch offline')).mockResolvedValue({items:[],total:0,page:1,counts:{processing:1}});vi.mocked(api.detail).mockReturnValue(detail.promise);const m=createExtractWorkbench({api,visible:true}),a=createExtractArtifacts({api});await m.load();await Promise.resolve();const pending=a.openDetail(1);await m.switchBatch(8);expect(m.state.error).toBe('switch offline');await vi.advanceTimersByTimeAsync(5000);expect(api.tasks).toHaveBeenCalledTimes(3);expect(a.state.detailLoading).toBe(true);m.setVisible(false);await vi.advanceTimersByTimeAsync(30000);expect(api.tasks).toHaveBeenCalledTimes(3);a.closeDialogs();detail.resolve({item:{task_id:1}});await pending;expect(a.state.detail).toBeNull();a.destroy();m.destroy();});
});

describe('submission confirmation evidence',()=>{
 it('confirms automatic payment with the selected count and configured source while saved task sources remain independent',async()=>{const api=apiStub(),confirm=vi.fn(async()=>true);const b=createExtractBatch({api,confirm});await b.open({providers:[{id:'legacy',modes:['auto_payment'],link_types:['upi'],payment_source:'xxsyun',payment_source_label:'XXSYUN'}]});b.state.mode='auto_payment';await b.preview();await b.submit();expect(confirm).toHaveBeenCalledWith(expect.stringContaining('100'));expect(confirm).toHaveBeenCalledWith(expect.stringContaining('XXSYUN'));b.destroy();});
});

describe('candidate late failures',()=>{
 it('does not replace a newer successful preview with an older rejected preview',async()=>{const api=apiStub(),old=deferred<any>();vi.mocked(api.candidates).mockReturnValueOnce(old.promise).mockResolvedValueOnce({total:2,selected_count:2});const b=createExtractBatch({api});await b.open(await api.config());const p=b.preview();b.state.filters.query='new';await b.preview();old.reject(Error('old failure'));await p;expect(b.state.preview?.total).toBe(2);expect(b.state.error).toBe('');b.destroy();});
});

describe('receipts belong to a specific submission',()=>{
 it('does not expose an earlier batch receipt as a newer failed submission success',async()=>{const api=apiStub(),b=createExtractBatch({api});await b.open(await api.config());await b.preview();await b.submit();expect(b.state.receipt?.batch_id).toBe(9);b.state.title='new explicit submission';await b.preview();vi.mocked(api.create).mockRejectedValueOnce(Error('new create failed'));await b.submit();expect(b.state.receipt?.batch_id).not.toBe(9);expect(b.state.error).toContain('new create failed');b.destroy();});
 it('uses a new identity for an explicitly previewed submission after success even when the payload is unchanged',async()=>{
  const api=apiStub(),b=createExtractBatch({api},async()=>{throw Error('list offline');});
  vi.mocked(api.create).mockResolvedValueOnce({ok:true,batch_id:9,started:100}).mockResolvedValueOnce({ok:true,batch_id:10,started:100});
  await b.open(await api.config());await b.preview();await b.submit();
  expect(b.state.receipt?.batch_id).toBe(9);expect(b.state.error).toBe('');
  const firstId=b.state.receipt?.submission_id;
  await b.preview();await b.submit();
  expect(api.create).toHaveBeenCalledTimes(2);
  const [first,second]=vi.mocked(api.create).mock.calls.map(call=>call[0]);
  expect(second?.submission_id).not.toBe(first?.submission_id);
  expect({...second,submission_id:undefined}).toEqual({...first,submission_id:undefined});
  expect(b.state.receipt?.batch_id).toBe(10);expect(b.state.receipt?.submission_id).not.toBe(firstId);expect(b.state.error).toBe('');
  b.destroy();
 });
 it('returns the accepted receipt only for the current successful create even when refreshing fails',async()=>{
  const api=apiStub(),b=createExtractBatch({api},async()=>{throw Error('list offline');});
  await b.open(await api.config());await b.preview();
  const receipt=await b.submit();
  expect(receipt).toMatchObject({batch_id:9});expect(receipt).toEqual(b.state.receipt);expect(b.state.error).toBe('');
  b.destroy();
 });
 it('returns no current receipt after invalid workers while preserving the earlier accepted receipt',async()=>{
  const api=apiStub(),b=createExtractBatch({api});
  await b.open(await api.config());await b.preview();await b.submit();const accepted=b.state.receipt;
  await b.preview();b.state.workers=0;
  expect(await b.submit()).toBeUndefined();expect(api.create).toHaveBeenCalledTimes(1);
  expect(b.state.receipt).toEqual(accepted);expect(b.state.error).toContain('批次并发');
  b.destroy();
 });
 it('returns no current receipt when automatic payment confirmation is cancelled',async()=>{
  const api=apiStub(),confirm=vi.fn(async()=>false),b=createExtractBatch({api,confirm});
  await b.open(await api.config());await b.preview();await b.submit();const accepted=b.state.receipt;
  b.state.mode='auto_payment';await b.preview();
  expect(await b.submit()).toBeUndefined();expect(confirm).toHaveBeenCalledTimes(1);expect(api.create).toHaveBeenCalledTimes(1);
  expect(b.state.receipt).toEqual(accepted);expect(b.state.error).toBe('');
  b.destroy();
 });
});


describe('extract selected collection commands',()=>{
 it('reads only selected usable payment entries once and copies safe results once',async()=>{
  const api=apiStub(),copyText=vi.fn(async()=>{}),notify=vi.fn();
  vi.mocked(api.tasks).mockResolvedValue({items:[{task_id:'9007199254740993',email:'first@example.test',has_payment_entry:true},{task_id:2,email:'missing@example.test'},{task_id:3,email:'qr@example.test',has_qr:true}],total:3,page:1,counts:{}});
  const paymentEntries=vi.fn(async()=>({items:[{task_id:'9007199254740993',status:'updated' as const,entry:{payment_page_url:'javascript:unsafe',payment_url:'https://pay.example.test/local'}},{task_id:'3',status:'updated' as const,entry:{qr_data:'plain-qr'}}]}));Object.assign(api,{paymentEntries});
  const owner=createExtractWorkbench({api,copyText,notify});await owner.load();['9007199254740993','2','3'].forEach(id=>owner.state.selected.add(id));await owner.bulkAction('links');
  expect(paymentEntries).toHaveBeenCalledOnce();expect(paymentEntries).toHaveBeenCalledWith(['9007199254740993',3]);expect(api.paymentEntry).not.toHaveBeenCalled();expect(copyText).toHaveBeenCalledWith('first@example.test\thttps://pay.example.test/local\nqr@example.test\tplain-qr');expect(notify).toHaveBeenCalledWith('已复制 2 条支付链接，跳过 1 个');owner.destroy();
 });
 it('awaits one bulk sync result and does not report accepted work as finished',async()=>{
  const api=apiStub(),pending=deferred<any>(),notify=vi.fn(),actionBulk=vi.fn(()=>pending.promise);Object.assign(api,{actionBulk});
  vi.mocked(api.tasks).mockResolvedValue({items:[{task_id:'9007199254740993'},{task_id:2}],total:2,page:1,counts:{}});
  const owner=createExtractWorkbench({api,notify});await owner.load();owner.state.selected.add('9007199254740993');owner.state.selected.add('2');const action=owner.bulkAction('sync');await owner.bulkAction('sync');
  expect(actionBulk).toHaveBeenCalledOnce();expect(actionBulk).toHaveBeenCalledWith(['9007199254740993',2],'sync_status');expect(api.action).not.toHaveBeenCalled();expect(notify).not.toHaveBeenCalled();expect(owner.state.bulkBusy).toBe(true);
  pending.resolve({ok:true,command_id:'4',status:'partial_success',items:[{key:'9007199254740993',status:'updated',data:{task_id:'9007199254740993',run_id:'5'}},{key:'2',status:'skipped',reason:'任务仍在执行'}]});await action;
  expect(notify).toHaveBeenCalledWith('原单同步已入队：1 个，跳过 1 个');expect(owner.state.receipt?.command_id).toBe('4');expect(owner.state.selected.has('9007199254740993')).toBe(false);expect(owner.state.selected.has('2')).toBe(true);owner.destroy();
 });
});

it('retains an accepted sync command when waiting stops without claiming failure or resubmitting',async()=>{
 const api=apiStub(),notify=vi.fn(),actionBulk=vi.fn(async()=>{throw new BulkMutationPendingError('99',{command_id:'99',accepted:true});});Object.assign(api,{actionBulk});vi.mocked(api.tasks).mockResolvedValue({items:[{task_id:1}],total:1,page:1,counts:{}});
 const owner=createExtractWorkbench({api,notify});await owner.load();owner.state.selected.add('1');await owner.bulkAction('sync');
 expect(actionBulk).toHaveBeenCalledOnce();expect(owner.state.receipt).toMatchObject({command_id:'99',accepted:true});expect(owner.state.error).toBe('');expect(owner.state.selected.has('1')).toBe(true);expect(notify).toHaveBeenCalledWith(expect.stringContaining('仍在执行'));owner.destroy();
});
