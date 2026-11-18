import {DOMWrapper,flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import CodexTable from './CodexTable.vue';
const filters={q:'',plan:'',status:'',oauth_status:'',account_id:'',sub2api_id:'',date_from:'',date_to:'',expired_date:''};
const row={filename:'large-凭证.json',email:'demo@example.test',plan:'plus',account_id:'90071992547409931',sub2api_account_id:'90071992547409932',exported:true,exported_count:2,oauth_status:'valid',mtime:'2026-11-14 10:20:30',expired:'2026-11-20 10:20:30',oauth_refresh_error:'详细错误证据不应成为第三行'};
const props={items:[row],selected:new Set<string>(),filters,facets:{},loading:false,error:'',busy:false,visible:true,openFilter:null};
const wrappers:ReturnType<typeof mount>[]=[];
function table(extra:Record<string,unknown>={}) {const w=mount(CodexTable,{attachTo:document.body,props:{...props,...extra}});wrappers.push(w);return w;}
beforeEach(()=>vi.stubGlobal('ResizeObserver',class{observe(){}unobserve(){}disconnect(){}}));
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());localStorage.clear();vi.unstubAllGlobals();});
describe('Codex凭证表格',()=>{
  it('显示完整字符串身份，两行单元格保留文件名和错误详情，选择发filename',async()=>{
    const w=table();expect(w.find('tbody tr').exists()).toBe(true);
    expect(w.get('td[data-label="Account ID"]').text()).toBe('90071992547409931');
    expect(w.get('td[data-label="Sub2API ID"]').text()).toBe('90071992547409932');
    expect(w.get('td[data-label="邮箱 / 文件"]').text()).toContain('large-凭证.json');
    expect(w.text()).not.toContain(row.oauth_refresh_error);
    expect(w.get('td[data-label="OAuth 状态"] [title]').attributes('title')).toContain(row.oauth_refresh_error);
    await w.get('input[aria-label="选择凭证 large-凭证.json"]').setValue(true);
    expect(w.emitted('select')?.[0]).toEqual(['large-凭证.json',true]);
  });
  it('本页复选框独立于其他页选择，取消只发当前页差集意图',async()=>{
    const w=table({selected:new Set(['elsewhere.json',row.filename])});
    expect(w.find('input[aria-label="全选当前页 Codex 凭证"]').exists()).toBe(true);
    const all=w.get<HTMLInputElement>('input[aria-label="全选当前页 Codex 凭证"]');expect(all.element.checked).toBe(true);
    await all.setValue(false);expect(w.emitted('selectPage')?.at(-1)).toEqual([false]);
  });
  it('更多操作保留能力选择器和原动作，页面隐藏关闭Portal',async()=>{
    const w=table();expect(w.find('button[aria-label="更多操作 large-凭证.json"]').exists()).toBe(true);
    await w.get('button[aria-label="更多操作 large-凭证.json"]').trigger('click');await flushPromises();
    const body=new DOMWrapper(document.body);
    expect(body.find('.cx-row-menu [data-codex-reauthorize]').exists()).toBe(true);
    expect(body.find('.cx-row-menu [data-codex-download-cpa]').exists()).toBe(true);
    expect(body.find('.cx-row-menu [data-codex-upload-sub2]').exists()).toBe(true);
    expect(body.find('.cx-row-menu [data-codex-reset]').exists()).toBe(true);
    expect(body.find('.cx-row-menu [data-codex-download]').exists()).toBe(true);
    expect(body.find('.cx-row-menu [data-codex-archive]').exists()).toBe(true);
    expect(body.find('.cx-row-menu [data-codex-delete]').exists()).toBe(true);
    expect(body.findAll('.cx-menu-actions button')).toHaveLength(8);
    await body.get('.cx-row-menu [data-codex-refresh-token]').trigger('click');
    expect(w.emitted('action')?.at(-1)).toEqual(['refreshToken',row]);
    await w.get('button[aria-label="更多操作 large-凭证.json"]').trigger('click');await flushPromises();
    await w.setProps({visible:false});await flushPromises();
    expect(body.find('.cx-row-menu').exists()).toBe(false);
  });
  it('恢复旧比例与total且列宽键盘调整写回原key',async()=>{
    localStorage.setItem('gpt_console_table_widths_codex','[4,20,6,10,10,10,10,10,10,10]');localStorage.setItem('gpt_console_table_total_codex','1000');
    const w=table();expect(w.find('col').exists()).toBe(true);
    expect(w.findAll('col')).toHaveLength(10);expect(w.findAll('thead th')).toHaveLength(10);
    expect(w.findAll('col')[1]!.attributes('style')).toContain('200px');
    await w.get('button[aria-label="调整邮箱 / 文件列宽，方向键调整"]').trigger('keydown',{key:'ArrowRight'});
    expect(w.findAll('col')[1]!.attributes('style')).toContain('210px');
    expect(localStorage.getItem('gpt_console_table_total_codex')).toBe('1010');
    w.vm.resetColumns();await w.vm.$nextTick();
    expect(localStorage.getItem('gpt_console_table_widths_codex')).toBeNull();
    expect(localStorage.getItem('gpt_console_table_total_codex')).toBeNull();
    expect(w.findAll('col')[1]!.attributes('style')).toContain('228px');
  });
  it('无数据的失败可重试，已有数据的失败不清空表格',async()=>{
    const w=table({items:[],error:'网络中断'});expect(w.find('[role="alert"]').exists()).toBe(true);
    await w.findAll('button').find(b=>b.text()==='重新加载')!.trigger('click');expect(w.emitted('retry')).toHaveLength(1);
    await w.setProps({items:[row]});expect(w.findAll('tbody tr')).toHaveLength(1);
  });
  it('更新时间和过期时间分日期与时间两行，完整原值留在title',()=>{
    const w=table({items:[{...row,mtime:'2026-11-14T10:20:30',expired:'2026-11-20T11:22:33'}]});
    const updated=w.get('td[data-label="更新时间"]');
    expect(updated.get('.list-cell-primary').text()).toBe('2026/11/14');
    expect(updated.get('.list-cell-secondary').text()).toBe('10:20:30');
    expect(updated.get('[title]').attributes('title')).toBe('2026-11-14T10:20:30');
    const expires=w.get('td[data-label="过期时间"]');
    expect(expires.get('.list-cell-primary').text()).toBe('2026/11/20');
    expect(expires.get('.list-cell-secondary').text()).toBe('11:22:33');
  });
  it('从未下载的凭证没有重置动作，归档行显示恢复',async()=>{
    const w=table({items:[{...row,exported_count:0,archived:true}]});
    await w.get('button[aria-label="更多操作 large-凭证.json"]').trigger('click');await flushPromises();
    const body=new DOMWrapper(document.body);expect(body.find('.cx-row-menu [data-codex-reset]').exists()).toBe(false);
    expect(body.get('.cx-row-menu [data-codex-archive]').text()).toBe('恢复');
    expect(body.get('.cx-row-menu [data-codex-archive]').attributes('data-archived')).toBe('0');
  });
  it('原生click能力门禁可拦截Portal动作，Escape关闭后可重新打开',async()=>{
    const w=table();await w.get('button[aria-label="更多操作 large-凭证.json"]').trigger('click');await flushPromises();
    const body=new DOMWrapper(document.body);
    const gate=(event:Event)=>{if((event.target as HTMLElement).closest('[data-codex-upload-sub2]')){event.preventDefault();event.stopImmediatePropagation();}};
    document.addEventListener('click',gate,true);
    try{await body.get('.cx-row-menu [data-codex-upload-sub2]').trigger('click');expect(w.emitted('action')).toBeUndefined();}
    finally{document.removeEventListener('click',gate,true);}
    await body.get('.cx-row-menu').trigger('keydown',{key:'Escape'});await flushPromises();expect(body.find('.cx-row-menu').exists()).toBe(false);
  });
  it('同凭证关联多个账号时只打开所点行详情，动作仍使用原filename',async()=>{
    const first={...row,sub2api_account_id:'101'},second={...row,sub2api_account_id:'202'};
    const w=table({items:[first,second]});
    await w.findAll('tbody tr')[1]!.get('button[aria-label^="更多操作"]').trigger('click');await flushPromises();
    const body=new DOMWrapper(document.body);
    expect(body.findAll('.cx-row-menu')).toHaveLength(1);
    const menu=body.get('.cx-row-menu');
    expect(menu.findAll('dt').find(label=>label.text()==='Sub2API ID')!.element.nextElementSibling?.textContent).toBe('202');
    expect(menu.get('[data-codex-upload-sub2]').attributes('data-codex-upload-sub2')).toBe(row.filename);
    await menu.get('[data-codex-upload-sub2]').trigger('click');
    expect(w.emitted('action')?.at(-1)).toEqual(['uploadSub2',second]);
  });
  it('重复filename及完全重复行重排更新不丢行、不产生重复key警告',async()=>{
    const warn=vi.spyOn(console,'warn').mockImplementation(()=>{});
    try{
      const first={...row,sub2api_account_id:'101'},second={...row,sub2api_account_id:'202'};
      const left={...row,filename:'left.json',sub2api_account_id:'301'},right={...row,filename:'right.json',sub2api_account_id:'302'};
      const w=table({items:[left,first,second,{...second},right]});
      await w.setProps({items:[right,{...second},first,second,left]});await flushPromises();
      expect(w.findAll('tbody tr')).toHaveLength(5);
      expect(w.findAll('td[data-label="Sub2API ID"]').map(cell=>cell.text())).toEqual(['302','202','101','202','301']);
      await w.setProps({items:[{...second},first,second]});await flushPromises();
      expect(w.findAll('tbody tr')).toHaveLength(3);
      expect(w.findAll('td[data-label="Sub2API ID"]').map(cell=>cell.text())).toEqual(['202','101','202']);
      expect(warn).not.toHaveBeenCalled();
      await w.findAll('tbody tr')[2]!.get('button[aria-label^="更多操作"]').trigger('click');await flushPromises();
      expect(new DOMWrapper(document.body).findAll('.cx-row-menu')).toHaveLength(1);
    }finally{warn.mockRestore();}
  });
  it('刷新或重排行数据时关闭旧详情，重开使用当前行',async()=>{
    const first={...row,sub2api_account_id:'101'},second={...row,sub2api_account_id:'202'};
    const w=table({items:[first,second]}),body=new DOMWrapper(document.body);
    await w.findAll('tbody tr')[1]!.get('button[aria-label^="更多操作"]').trigger('click');await flushPromises();
    await w.setProps({items:[{...second,plan:'team'},first]});await flushPromises();
    expect(body.findAll('.cx-row-menu')).toHaveLength(0);
    await w.findAll('tbody tr')[0]!.get('button[aria-label^="更多操作"]').trigger('click');await flushPromises();
    expect(body.findAll('.cx-row-menu')).toHaveLength(1);
    expect(body.get('.cx-row-menu').findAll('dt').find(label=>label.text()==='Plan')!.element.nextElementSibling?.textContent).toBe('team');
    await w.setProps({items:[{...second,plan:'plus'},first]});await flushPromises();
    expect(body.findAll('.cx-row-menu')).toHaveLength(0);
  });
  it('同filename的关联行共享凭证选择，重排后仍按filename选择',async()=>{
    const first={...row,sub2api_account_id:'101'},second={...row,sub2api_account_id:'202'};
    const w=table({items:[first,second]});
    const boxes=()=>w.findAll<HTMLInputElement>('tbody input[type="checkbox"]');
    await boxes()[1]!.setValue(true);expect(w.emitted('select')?.at(-1)).toEqual([row.filename,true]);
    await w.setProps({selected:new Set([row.filename])});
    expect(boxes().map(box=>box.element.checked)).toEqual([true,true]);
    await w.setProps({items:[second,first]});
    expect(boxes().map(box=>box.element.checked)).toEqual([true,true]);
    await boxes()[0]!.setValue(false);expect(w.emitted('select')?.at(-1)).toEqual([row.filename,false]);
    await w.setProps({selected:new Set()});
    expect(boxes().map(box=>box.element.checked)).toEqual([false,false]);
  });
});
