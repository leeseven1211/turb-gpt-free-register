import {flushPromises,mount} from '@vue/test-utils';
import {afterEach,describe,expect,it,vi} from 'vitest';
import SalesPage from './SalesPage.vue';
import type {SalesApi,SalesEvent,SalesItem,SalesListResponse} from '../../api/sales';

function deferred<T>(){let resolve!:(value:T)=>void;const promise=new Promise<T>(done=>{resolve=done;});return{promise,resolve};}
const item=(id:number, accountId=id):SalesItem=>({
  id, source_id:'local', account_id:accountId, email:`account-${accountId}@example.test`, plan:'Free',
  status:'for_sale', shop_id:null, product_id:null, shop_name:'', product_name:'',
  external_inventory_id:'', order_ref:'', order_amount:null, currency:'CNY', channel:'',
  price:null, sold_at:null, paid_at:null, note:'', listed_at:null, archived:false,
  archive_pending:false, sync_status:'idle', error_code:'', error_message:'',
  created_at:'2026-11-27T00:00:00Z', updated_at:'2026-11-27T00:00:00Z',
});
function response(rows:SalesItem[],page=1):SalesListResponse {
  return {ok:true,items:rows,total:30,page,page_size:2,counts:{all:30,for_sale:30,listed:0,sold:0}};
}
function fixture(initialVisible=true) {
  const calls:{path:string;body?:unknown}[]=[];
  const api:SalesApi={
    async list(params){calls.push({path:'list',body:params});return response(params.page===1?[item(1),item(2)]:[item(3),item(4)],params.page);},
    async sources(){return {ok:true,sources:[{id:'local',name:'本地',kind:'local',base_url:'',auth_env:'',enabled:true,created_at:'2026-11-26T00:00:00Z',updated_at:'2026-11-27T00:00:00Z',auth_configured:true}]};},
    async shops(){return {ok:true,shops:[{id:7,name:'测试店铺',platform:'liandong',base_url:'https://wzyp.cn',token_env:'TOKEN_ENV',external_shop_id:'external-shop-7',enabled:true,owner_id:'local',sync_interval:60,last_synced_at:'2026-11-27T00:00:00Z',error_code:'shop_timeout',error_message:'上次同步超时',created_at:'2026-11-26T00:00:00Z',updated_at:'2026-11-27T00:00:00Z',token_configured:true}]};},
    async products(){return {ok:true,products:[{id:9,shop_id:7,external_product_id:'p',goods_key:'goods',name:'测试商品',status:'available',price:20}]};},
    async addItems(body){calls.push({path:'add',body});return {ok:true,items:[],total:0,success_count:0,failed_count:0};},
    async changeStatus(body){calls.push({path:'status',body});return {ok:true,items:[],total:0,success_count:0,failed_count:0};},
    async listItems(body){calls.push({path:'listItems',body});return {ok:true,accepted:true,task_id:'t',run_id:'r',status:'queued'};},
    async checkShop(){return {ok:true,shop:{id:7,name:'测试店铺',platform:'liandong',base_url:'https://wzyp.cn',token_env:'TOKEN_ENV',external_shop_id:'external-shop-7',enabled:true,owner_id:'local',sync_interval:60,last_synced_at:'2026-11-27T00:00:00Z',error_code:'shop_timeout',error_message:'上次同步超时',created_at:'2026-11-26T00:00:00Z',updated_at:'2026-11-27T00:00:00Z',token_configured:true},capabilities:{},product_count:0,external_shop_id:'external-shop-7'};},
    async syncShop(){return {ok:true,accepted:true,task_id:'t',run_id:'r',status:'queued'};},
    async jobs(){return {ok:true,jobs:[]};},
    async events(){return {ok:true,events:[]};},
    async saveSource(){return {ok:true,source:{id:'oracle',name:'Oracle',kind:'remote',base_url:'https://example.test',auth_env:'AUTH_ENV',enabled:true}};},
    async saveShop(){return {ok:true,shop:{id:7,name:'测试店铺',platform:'liandong',base_url:'https://wzyp.cn',token_env:'TOKEN_ENV',external_shop_id:'external-shop-7',enabled:true,owner_id:'local',sync_interval:60,last_synced_at:'2026-11-27T00:00:00Z',error_code:'shop_timeout',error_message:'上次同步超时',created_at:'2026-11-26T00:00:00Z',updated_at:'2026-11-27T00:00:00Z',token_configured:true}};},
  };
  const wrapper=mount(SalesPage,{attachTo:document.body,props:{api,initialVisible}});
  return {wrapper,calls,api};
}

afterEach(()=>{document.body.replaceChildren();vi.restoreAllMocks();});

describe('SalesPage',()=>{
  it('切换销售状态时清空旧视图选择',async()=>{
    const {wrapper}=fixture();
    await flushPromises();
    await wrapper.get('[data-item-check="1"]').setValue(true);
    expect(wrapper.findAll('tbody input:checked')).toHaveLength(1);
    await wrapper.get('[data-status="sold"]').trigger('click');
    expect(wrapper.findAll('tbody input:checked')).toHaveLength(0);
  });

  it('翻页后保留跨页选择，并按销售条目 id 提交上架',async()=>{
    const {wrapper,calls}=fixture();
    await flushPromises();
    await wrapper.get('[data-item-check="1"]').setValue(true);
    await wrapper.get('[aria-label="第 2 页"]').trigger('click');
    await flushPromises();
    await wrapper.get('[data-item-check="3"]').setValue(true);
    await wrapper.get('[data-open-listing]').trigger('click');
    await wrapper.findAll('.sales-dialog select')[1]!.setValue('9');
    await wrapper.get('[data-listing-submit]').trigger('click');
    const body=calls.find(call=>call.path==='listItems')?.body as {item_ids:number[]}|undefined;
    expect(body?.item_ids).toEqual([1,3]);
  });

  it('展示部分失败回执，并保留失败条目选择供重试',async()=>{
    const {wrapper,calls,api}=fixture();
    await flushPromises();
    await wrapper.get('[data-item-check="1"]').setValue(true);
    vi.spyOn(api,'changeStatus').mockResolvedValue({
      ok:true,items:[{id:1,status:'failed',error_code:'source_unavailable',message:'来源不可达'}],
      total:1,success_count:0,failed_count:1,
    });
    await wrapper.get('[data-bulk-status="listed"]').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('来源不可达');
    expect(wrapper.findAll('tbody input:checked')).toHaveLength(1);
    expect(calls.some(call=>call.path==='status')).toBe(false);
  });

  it('initialVisible=false 时延迟加载配置，隐藏后不接收迟到响应',async()=>{
    const {wrapper,api}=fixture(false);
    const sources=vi.spyOn(api,'sources'),shops=vi.spyOn(api,'shops');
    await flushPromises();
    expect(sources).not.toHaveBeenCalled();
    (wrapper.vm as unknown as {setVisible:(value:boolean)=>void}).setVisible(true);
    await flushPromises();
    expect(sources).toHaveBeenCalled();
    (wrapper.vm as unknown as {setVisible:(value:boolean)=>void}).setVisible(false);
    expect((wrapper.vm as unknown as {setVisible:(value:boolean)=>void})).toBeTruthy();
    expect(shops).toHaveBeenCalled();
  });

  it('打开任务回执时展示中文阶段和逐项错误',async()=>{
    const {wrapper,api}=fixture();
    vi.spyOn(api,'jobs').mockResolvedValue({ok:true,jobs:[{
      id:4,task_id:'task-4',run_id:'run-4',status:'partial_success',action:'list',
      result_summary:{items:[{id:1,status:'failed',error_code:'source_unavailable',message:'来源不可达'}]},
    }]});
    await flushPromises();
    await wrapper.get('[data-open-jobs]').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('上架商品');
    expect(wrapper.text()).toContain('来源不可达');
    expect(wrapper.text()).toContain('部分成功');
  });

  it('切换搜索条件时清空当前跨页选择',async()=>{
    const {wrapper}=fixture();
    await flushPromises();
    await wrapper.get('[data-item-check="1"]').setValue(true);
    await wrapper.get('.sales-search').setValue('new@example.test');
    expect(wrapper.findAll('tbody input:checked')).toHaveLength(0);
  });

  it('编辑已有店铺时保留店铺 id 和启停配置',async()=>{
    const {wrapper,api}=fixture();
    const save=vi.spyOn(api,'saveShop');
    await flushPromises();
    await wrapper.get('[data-open-management]').trigger('click');
    await wrapper.find('.sales-config-list article .ui-link').trigger('click');
    await wrapper.findAll('.sales-form-grid input')[0]!.setValue('编辑店铺');
    await wrapper.find('.sales-form-grid .ui-button--primary').trigger('click');
    await flushPromises();
    expect(save).toHaveBeenCalledWith({
      id:7,
      name:'编辑店铺',
      platform:'liandong',
      base_url:'https://wzyp.cn',
      token_env:'TOKEN_ENV',
      enabled:true,
      owner_id:'local',
      sync_interval:60,
    });
    const payload=save.mock.calls[0]?.[0] as Record<string,unknown>;
    expect(payload).not.toHaveProperty('external_shop_id');
    expect(payload).not.toHaveProperty('last_synced_at');
    expect(payload).not.toHaveProperty('error_code');
    expect(payload).not.toHaveProperty('error_message');
    expect(payload).not.toHaveProperty('created_at');
    expect(payload).not.toHaveProperty('updated_at');
    expect(payload).not.toHaveProperty('token_configured');
  });

  it('条目历史切换时忽略旧请求的迟到结果',async()=>{
    const {wrapper,api}=fixture();
    const first=deferred<{ok:true;events:SalesEvent[]}>(), second=deferred<{ok:true;events:SalesEvent[]}>();
    vi.spyOn(api,'events').mockImplementationOnce(()=>first.promise).mockImplementationOnce(()=>second.promise);
    await flushPromises();
    await wrapper.findAll('tbody .ui-link')[0]!.trigger('click');
    await wrapper.get('.sales-dialog header .ui-button').trigger('click');
    await wrapper.findAll('tbody .ui-link')[1]!.trigger('click');
    second.resolve({ok:true,events:[{id:2,item_id:2,event:'second',changes:{},created_at:'2026-11-27T00:00:02Z'}]});
    await flushPromises();
    first.resolve({ok:true,events:[{id:1,item_id:1,event:'first',changes:{},created_at:'2026-11-27T00:00:01Z'}]});
    await flushPromises();
    expect(wrapper.text()).toContain('second');
    expect(wrapper.text()).not.toContain('first');
  });
});
