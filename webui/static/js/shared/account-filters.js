// 账号列筛选与批次范围共用同一查询定义。
window.AccountFilters = (() => {
  const fallback = {
    source: [], registration_driver: ['roxy','roxy_oss','protocol','protocol_oss','protocol_oss_2','cloakbrowser','unknown'],
    token: ['has','expired','invalid_401','invalid_403','invalid_other','none'],
    password: ['has','none'], promotion: ['free_trial','half_price','other_discount','other_promo','none','unknown','pending','failed','not_applicable'],
    totp: ['enabled','disabled'], risk: ['detected','clear','pending'], codex: ['success','retrying','failed','stopped','deactivated','skipped','missing'],
    account_status: ['active','deactivated','unknown'], email_status: ['invalid','unmarked'], plan: ['free','plus','unqueried'],
  };
  function options(field, schema, selected) {
    const definitions=schema?.fields;
    const definition=Array.isArray(definitions)?definitions.find(x=>(x.key||x.name)===field.key):definitions?.[field.key];
    const source=document.getElementById(field.controlId);
    const rows=Array.isArray(definition?.options)?definition.options:Array.isArray(definition?.enum)?definition.enum:Array.isArray(definition?.values)&&definition.values.length?definition.values:
      source?.options?Array.from(source.options).filter(x=>x.value).map(x=>({value:x.value,label:x.textContent.replace(/\s*·\s*\d+$/,'')})):fallback[field.key]||[];
    const found=new Map();
    for(const row of rows){const value=String(typeof row==='object'?row.value:row);if(!value)continue;
      const group=field.key==='token'?'account_token':field.key;
      const localLabel=field.key==='email_status'?({invalid:'已标记失效',unmarked:'未标记失效'}[value]):null;
      found.set(value,localLabel||(typeof row==='object'?row.label||facetLabel(group,value):facetLabel(group,value)));}
    for(const value of selected)if(!found.has(value))found.set(value,facetLabel(field.key,value));
    return [...found].map(([value,label])=>({value,label}));
  }
  function fields(){return [{key:'plan',label:'套餐',controlId:'accountPlanFilterV2',type:'select'},...AccountQuery.fields];}
  function chips(query,schema) {
    const result=[];
    if(query.filters.email)result.push(['email',`邮箱：${query.filters.email}`]);
    if(query.q)result.push(['q',`搜索：${query.q}`]);
    if(query.date_from||query.date_to)result.push(['dates',`创建日期：${query.date_from||'不限'} ~ ${query.date_to||'不限'}`]);
    if(query.archived!=='0')result.push(['archived',query.archived==='only'?'仅归档账号':'含归档账号']);
    for(const field of fields()){
      const selected=field.key==='plan'?query.plan:query.filters[field.key];
      if(field.type==='text'){if(selected)result.push([field.key,`${field.label}：${selected}`]);continue;}
      if(!selected.length)continue;
      const map=new Map(options(field,schema,selected).map(row=>[row.value,row.label]));
      result.push([field.key,`${field.label}：${selected.map(value=>map.get(value)||value).join('、')}`]);
    }
    return result;
  }
  function refresh(host,schema) {
    const query=read(host);
    for(const details of host.querySelectorAll('[data-filter-field]')){
      const field=details.dataset.filterField;
      const selected=field==='plan'?query.plan:query.filters[field];
      const count=Array.isArray(selected)?selected.length:selected?1:0;
      details.classList.toggle('has-value',count>0);
      const badge=details.querySelector('[data-filter-count]');if(badge){badge.textContent=count||'';badge.hidden=!count;}
    }
    const date=host.querySelector('[data-filter-dates]');date?.classList.toggle('has-value',Boolean(query.date_from||query.date_to));
    const hostChips=host.querySelector('[data-query-chips]');const chosen=chips(query,schema);
    hostChips.innerHTML=chosen.length?chosen.map(([key,title])=>`<button type="button" class="bulk-filter-chip" data-clear-query="${attrEsc(key)}">${esc(title)}<span aria-hidden="true">×</span><span class="bulk-sr-only">移除此条件</span></button>`).join(''):'<span class="bulk-filter-empty">全部未归档账号</span>';
  }
  function updateOptions(host,schema) {
    if(!host)return;
    host.__accountFilterSchema=schema;
    const query=read(host);
    for(const field of fields()){
      if(field.type==='text')continue;
      const details=host.querySelector(`[data-filter-field="${field.key}"]`);
      if(!details)continue;
      const selected=field.key==='plan'?query.plan:query.filters[field.key];
      const rows=options(field,schema,selected);
      const panel=details.querySelector('.bulk-filter-options');
      // 新来源可立即出现；正在操作的复选框保留原节点和焦点，收起后再移除过期选项。
      if(details.open||details.contains(document.activeElement)){
        if(panel){
          const existing=new Set([...panel.querySelectorAll('input[data-query-filter]')].map(input=>input.value));
          const added=rows.filter(row=>!existing.has(row.value));
          if(added.length){panel.querySelector('.bulk-muted')?.remove();panel.insertAdjacentHTML('beforeend',added.map(row=>`<label><input type="checkbox" data-query-filter="${attrEsc(field.key)}" value="${attrEsc(row.value)}" ${selected.includes(row.value)?'checked':''}><span>${esc(row.label)}</span></label>`).join(''));}
        }
        continue;
      }
      if(panel)panel.innerHTML=rows.length?rows.map(row=>`<label><input type="checkbox" data-query-filter="${attrEsc(field.key)}" value="${attrEsc(row.value)}" ${selected.includes(row.value)?'checked':''}><span>${esc(row.label)}</span></label>`).join(''):'<span class="bulk-muted">暂无可用选项</span>';
    }
    refresh(host,schema);
  }
  function mount(host,raw,schema,onChange) {
    const query=AccountQuery.normalize(raw);
    host.innerHTML=`<div class="bulk-query-top"><label class="bulk-field bulk-query-search"><span class="bulk-sr-only">邮箱或姓名</span><input data-query="email" type="search" value="${attrEsc(query.filters.email)}" autocomplete="off" placeholder="搜索邮箱或姓名"></label><details class="bulk-filter-popover" data-filter-dates><summary>创建日期<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg></summary><div class="bulk-filter-popover-panel"><label class="bulk-field">创建日期从<input data-query="date_from" type="date" value="${attrEsc(query.date_from)}"></label><label class="bulk-field">创建日期至（含当天）<input data-query="date_to" type="date" value="${attrEsc(query.date_to)}"></label></div></details><details class="bulk-filter-popover"><summary>更多查询<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg></summary><div class="bulk-filter-popover-panel"><label class="bulk-field">高级搜索<input data-query="q" type="search" value="${attrEsc(query.q)}" placeholder="如：协议 jp" autocomplete="off"></label><label class="bulk-field">归档范围<select data-query="archived"><option value="0">未归档</option><option value="only">仅归档</option><option value="all">全部</option></select></label></div></details></div><div class="bulk-column-filters" aria-label="账号列筛选">${fields().map(field=>{
      const selected=field.key==='plan'?query.plan:query.filters[field.key];const rows=field.type==='text'?[]:options(field,schema,selected);
      return `<details class="bulk-filter-popover" data-filter-field="${attrEsc(field.key)}"><summary>${esc(field.label)}<span data-filter-count hidden></span><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg></summary><div class="bulk-filter-popover-panel">${field.type==='text'?`<label class="bulk-field">${esc(field.label)}<input data-query-filter="${attrEsc(field.key)}" value="${attrEsc(selected)}" inputmode="numeric" placeholder="输入账号 ID"></label>`:`<div class="bulk-filter-options">${rows.length?rows.map(row=>`<label><input type="checkbox" data-query-filter="${attrEsc(field.key)}" value="${attrEsc(row.value)}" ${selected.includes(row.value)?'checked':''}><span>${esc(row.label)}</span></label>`).join(''):'<span class="bulk-muted">暂无可用选项</span>'}</div>`}</div></details>`;
    }).join('')}</div><div class="bulk-query-chips" data-query-chips aria-label="已选账号条件"></div>`;
    host.querySelector('[data-query="archived"]').value=query.archived;
    for(const details of host.querySelectorAll('.bulk-filter-popover')){
      const title=details.querySelector('summary')?.textContent||'筛选条件';
      details.querySelector('.bulk-filter-popover-panel')?.insertAdjacentHTML('afterbegin',`<div class="bulk-filter-popover-heading"><strong>${esc(title)}</strong><button type="button" data-close-filter aria-label="关闭${attrEsc(title)}筛选">完成</button></div>`);
    }
    host.__accountFilterSchema=schema;
    host.oninput=()=>{refresh(host,host.__accountFilterSchema);onChange(read(host));};
    host.onchange=()=>{refresh(host,host.__accountFilterSchema);onChange(read(host));};
    host.onclick=event=>{
      const close=event.target.closest('[data-close-filter]');
      if(close){const details=close.closest('details');details.open=false;details.querySelector('summary').focus({preventScroll:true});updateOptions(host,host.__accountFilterSchema);return;}
      const clear=event.target.closest('[data-clear-query]');
      if(clear){const key=clear.dataset.clearQuery;
        for(const input of host.querySelectorAll('[data-query],[data-query-filter]')){
          const match=key==='dates'?['date_from','date_to'].includes(input.dataset.query):(input.dataset.query===key||input.dataset.queryFilter===key);
          if(match){if(input.type==='checkbox')input.checked=false;else input.value=key==='archived'?'0':'';}}
        refresh(host,host.__accountFilterSchema);onChange(read(host));return;}
      const summary=event.target.closest('summary');if(summary){const opening=summary.parentElement;for(const details of host.querySelectorAll('details[open]'))if(details!==opening)details.open=false;updateOptions(host,host.__accountFilterSchema);}
    };
    host.onkeydown=event=>{if(event.key==='Escape'){const open=host.querySelector('details[open]');if(open){open.open=false;open.querySelector('summary').focus();}}};
    host.onfocusout=()=>setTimeout(()=>{
      if(!host.isConnected)return;
      for(const details of host.querySelectorAll('details[open]'))if(!details.contains(document.activeElement))details.open=false;
      updateOptions(host,host.__accountFilterSchema);
    },0);
    refresh(host,schema);
  }
  function read(host) {
    const raw={filters:{}};
    host.querySelectorAll('[data-query]').forEach(input=>{raw[input.dataset.query]=input.value;});
    host.querySelectorAll('[data-query-filter]').forEach(input=>{const key=input.dataset.queryFilter;if(!raw.filters[key])raw.filters[key]=[];
      if(input.type==='checkbox'){if(input.checked)raw.filters[key].push(input.value);}else raw.filters[key]=input.value;});
    raw.plan=raw.filters.plan||[];delete raw.filters.plan;return AccountQuery.normalize(raw);
  }
  document.addEventListener('pointerdown',event=>{
    for(const details of document.querySelectorAll('#tab-bulk .bulk-filter-popover[open], #tab-bulk .bulk-menu[open], #tab-bulk .bulk-more-states[open]')){
      if(!details.contains(event.target))details.open=false;
    }
  });
  return {mount,read,chips,updateOptions};
})();
