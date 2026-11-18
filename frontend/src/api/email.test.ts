import {afterEach,describe,expect,it,vi} from 'vitest';
import {createEmailApi} from './email';

afterEach(()=>vi.unstubAllGlobals());
describe('email existing HTTP contracts',()=>{
  it('preserves all inventory/history filters and supports aborting reads',async()=>{
    const send=vi.fn(async(_path:string,_options?:RequestInit)=>({items:[],total:0})),api=createEmailApi(send);
    const signal=new AbortController().signal;
    await api.inventory({page:2,size:20,source:'all',q:'邮箱 +',status:'used',used_date:'2026-11-16'},signal);
    await api.history({page:3,size:50,source:'outlook',parent_id:'9',q:'child',parent_q:'mother',state:'reserved',related_q:'12',created_from:'2026-11-01',created_to:'2026-11-16'},signal);
    const first=new URL(send.mock.calls[0]![0],'http://fixture');
    expect(Object.fromEntries(first.searchParams)).toEqual({paged:'1',page:'2',page_size:'20',source:'all',q:'邮箱 +',status:'used',used_date:'2026-11-16'});
    expect(send.mock.calls[0]![1]).toEqual({signal});
    expect(Object.fromEntries(new URL(send.mock.calls[1]![0],'http://fixture').searchParams)).toEqual({page:'3',page_size:'50',source:'outlook',parent_id:'9',q:'child',parent_q:'mother',state:'reserved',related_q:'12',created_from:'2026-11-01',created_to:'2026-11-16'});
  });
  it('never changes source-specific imports or original request identities',async()=>{
    const send=vi.fn(async(_path:string,_options?:RequestInit)=>({ok:true})),api=createEmailApi(send);
    await api.localPreview({source:'generic_api',text:'raw====url',expires_at:'2026-12-01T12:00:00+08:00'});
    await api.localImport({source:'email_butler',text:'original@example.test'});
    await api.createBatch({request_id:'original',preview_token:'preview'});
    await api.retryBatch('batch/one',{request_id:'original',preview_token:'preview'});
    await api.cancelBatch('batch/one');
    expect(send.mock.calls.map(call=>call[0])).toEqual(['/api/outlook/import-preview','/api/outlook/import','/api/email-butler/imports','/api/email-butler/imports/batch%2Fone/retry','/api/email-butler/imports/batch%2Fone/cancel']);
    expect(JSON.parse(String(send.mock.calls[0]![1]!.body))).toEqual({source:'generic_api',text:'raw====url',expires_at:'2026-12-01T12:00:00+08:00'});
    expect(JSON.parse(String(send.mock.calls[1]![1]!.body))).toEqual({source:'email_butler',text:'original@example.test'});
    expect(send.mock.calls[4]![1]).toEqual({method:'POST'});
  });
  it('copies secrets only on explicit identity-bound calls',async()=>{
    const send=vi.fn(async(_path:string,_options?:RequestInit)=>({value:'secret'})),api=createEmailApi(send);
    await api.secret({source:'outlook',email:'a+b@example.test'});
    await api.secrets([{source:'email_butler',email:'same@example.test'}]);
    expect(send.mock.calls[0]![0]).toContain('email=a%2Bb%40example.test');
    expect(JSON.parse(String(send.mock.calls[1]![1]!.body))).toEqual({items:[{source:'email_butler',email:'same@example.test'}],field:'copy_line'});
  });
  it('keeps PostgreSQL bigint identities exact through the real Response.text decoder',async()=>{
    vi.stubGlobal('fetch',vi.fn(async()=>new Response('{"items":[{"id":9007199254740993,"source":"outlook","email":"fixture@example.test","parent_id":9007199254740995,"registered_account_id":9007199254740997,"root_task_id":9007199254740999}],"parents":[{"parent_id":9007199254741001}],"total":1}',{headers:{'Content-Type':'application/json'}})));
    const api=createEmailApi(),rows=await api.history({page:1,size:50,source:'all',parent_id:'',q:'',parent_q:'',state:'',related_q:'',created_from:'',created_to:''}),summary=await api.derivationSummary();
    expect(rows.items[0]).toMatchObject({id:'9007199254740993',parent_id:'9007199254740995',registered_account_id:'9007199254740997',root_task_id:'9007199254740999'});
    expect(summary.parents?.[0]?.parent_id).toBe('9007199254741001');
  });
});
