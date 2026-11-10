// 批量任务页面：持久选择、快速受理、轮次结果与可恢复控制。
window.BulkTasks = (() => {
  const labels = {pending_submit:'待提交', waiting_account:'等待账号', queued:'排队中', running:'执行中', waiting:'等待外部结果', success:'成功', partial_success:'部分成功', failed:'失败', not_executed:'未执行', not_executable:'材料或状态不满足', unassessed:'等待预检', unconfirmed:'结果待确认', cancelled:'已取消', attention_required:'待确认', preparing:'准备中', ready:'已固定', expired:'已过期', consumed:'已创建', active:'批次执行中', settling:'汇总中', completed:'已完成', ended:'已结束', cancel_requested:'取消中', stop_requested:'停止中'};
  const terminal = ['success','partial_success','failed','not_executed','cancelled','attention_required'];
  const operationNames = {plan_check:'查询套餐',token_refresh:'刷新 AT',password_setup:'补密码',twofa_setup:'补 2FA',codex_retry:'补 Codex',account_completion:'组合补全'};
  const state = {nav:{tab:'bulk',view:'list'}, epoch:0, catalog:null, timer:null, loading:false,
    list:null, detail:null, targets:null, rounds:[], listCursor:'', listPrev:[], targetPrev:[], selection:null,
    draft:null, facetsCache:new Map(), selected:new Set(), pendingRound:null, previewCursor:'', previewPrev:[],roundsCursor:null};
  const $b = selector => document.querySelector(`#tab-bulk ${selector}`);
  const text = value => esc(value == null ? '—' : String(value));
  const date = value => value ? formatDateTime(value) : '—';
  const label = value => labels[value] || value || '准备中';
  const busy = value => { state.loading = value; $b('[data-bulk-content]')?.setAttribute('aria-busy', String(value)); };
  function readSaved(key, fallback) { try {return JSON.parse(sessionStorage.getItem(key)) || fallback;} catch (_) {return fallback;} }
  function saveDraft() { try {sessionStorage.setItem('turb_bulk_draft_v1', JSON.stringify(state.draft));} catch (_) {} }
  function saveSelection() { try {if(state.selection)sessionStorage.setItem('turb_bulk_selection_v1',JSON.stringify(state.selection));else sessionStorage.removeItem('turb_bulk_selection_v1');} catch (_) {} }
  function defaultDraft() {return {name:'',operation_key:'plan_check',query:AccountQuery.normalize(),source:null,parameters:{},max_concurrency:3,limit:''};}
  function key() {return globalThis.crypto?.randomUUID?.() || `bulk-${Date.now()}-${Math.random().toString(36).slice(2)}`;}
  async function request(path, options = {}) {
    const response = await fetch(`/api/bulk${path}`, {credentials:'same-origin', ...options});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      const detail = typeof payload.error === 'object' ? payload.error : payload;
      const error = new Error(detail.message || (typeof payload.error === 'string' ? payload.error : '') || `请求失败（HTTP ${response.status}）`);
      error.code = detail.code || payload.code || ''; error.status = response.status;
      error.details = detail.details || payload.details || {}; error.field=detail.field||null; error.fields = detail.fields || payload.fields || {};
      throw error;
    }
    return payload.data ?? payload;
  }
  async function intent(scope, path, body) {
    const storageKey = `turb_bulk_intent:${scope}`;
    const signature = JSON.stringify({path,body});
    let saved = readSaved(storageKey, null);
    if (saved && saved.signature !== signature) {
      const error = new Error('上一请求的回执尚未确认，请先找回原请求，再提交新内容。');
      error.code = 'request_receipt_pending'; throw error;
    }
    if (!saved) saved = {key:key(),signature};
    sessionStorage.setItem(storageKey, JSON.stringify(saved));
    try {
      const result = await request(path, {method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':saved.key},body:JSON.stringify(body)});
      sessionStorage.removeItem(storageKey); renderRecovery(); return result;
    } catch (error) {
      // 明确拒绝未受理才释放键；断网、401 和服务故障必须保留同一请求身份。
      if ([400,403,404,409,410,422,429].includes(error.status)) sessionStorage.removeItem(storageKey);
      renderRecovery(); throw error;
    }
  }
  function pendingRequests() {
    const rows=[];try {for(let i=0;i<sessionStorage.length;i++){const id=sessionStorage.key(i);if(id.startsWith('turb_bulk_intent:')){const saved=readSaved(id,null);if(saved?.signature)rows.push({id,...saved});}}}catch(_){}return rows;
  }
  function renderRecovery() {const host=$b('[data-bulk-recovery]');if(!host)return;const pending=pendingRequests();host.hidden=!pending.length;host.innerHTML=pending.length?`<span>有 ${pending.length} 个请求等待确认回执，草稿已保留。</span><button type="button" class="jobs-tb-btn" data-bulk-action="recover">找回原请求</button>`:'';}
  function restoreSelectionRequest(body, result) {
    const source=body.source||{};
    const query=AccountQuery.normalize(source.kind==='query'?source.query:{});
    state.draft={...defaultDraft(),operation_key:body.operation.key,query,
      source:source.kind==='query'?null:source,parameters:{...(body.parameters||{})},limit:query.limit??''};
    state.selection={...result,request_parameters:body.parameters||{},config_revision:body.expected_config_revision};
    saveDraft();saveSelection();
  }
  async function recover() {
    const saved=pendingRequests()[0];if(!saved)return;const {path,body}=JSON.parse(saved.signature);
    const result=await intent(saved.id.slice('turb_bulk_intent:'.length),path,body);clearError();
    if(path==='/selections'){restoreSelectionRequest(body,result);navigate('create');notice('已恢复原请求的功能、条件与参数，请核对固定范围后创建。');}
    else if(path==='/batches'){state.selection=null;saveSelection();navigate('detail',{batch_id:String(result.id||result.batch_id)});}
    else {const match=path.match(/^\/batches\/(\d+)\//);if(match)navigate('detail',{batch_id:match[1]});notice('原请求回执已找回。');}
  }
  function errorText(error, message = '') {
    return `${message}${error.message}${error.code ? `（${error.code}）` : ''}${error.status === 401 ? '，请重新登录后返回，草稿与请求身份已保留。' : ''}`;
  }
  function report(error, message = '') {
    $b('[data-bulk-field-error]')?.remove();
    document.querySelectorAll('#tab-bulk [aria-invalid="true"]').forEach(input=>{input.removeAttribute('aria-invalid');input.removeAttribute('aria-describedby');});
    if(error.field){
      const input=Array.from(document.querySelectorAll('#tab-bulk [data-query], #tab-bulk [data-query-filter], #tab-bulk [name]')).find(node=>(node.dataset.query||node.dataset.queryFilter||node.name)===error.field);
      if(input){input.setAttribute('aria-invalid','true');input.setAttribute('aria-describedby','bulkFieldError');const hint=document.createElement('small');hint.id='bulkFieldError';hint.dataset.bulkFieldError='';hint.className='bulk-error';hint.textContent=error.message;input.parentElement.append(hint);input.focus({preventScroll:true});}
    }
    const messageText=errorText(error,message);
    const host = $b('[data-bulk-error]');
    if (host) {host.hidden=false;host.textContent=messageText;}
    const inline = $b('[data-bulk-action-error]');
    if (inline) {
      inline.hidden=false;inline.textContent=messageText;
      inline.scrollIntoView?.({block:'nearest',behavior:'smooth'});
    }
  }
  function clearError() {
    for(const selector of ['[data-bulk-error]','[data-bulk-action-error]']){
      const host=$b(selector);if(host){host.hidden=true;host.textContent='';}
    }
    $b('[data-bulk-field-error]')?.remove();
    document.querySelectorAll('#tab-bulk [aria-invalid="true"]').forEach(input=>{input.removeAttribute('aria-invalid');input.removeAttribute('aria-describedby');});
  }
  function confirmAction({title,body,items=[],confirm='确认',danger=true}){
    const dialog=$b('[data-bulk-confirm]');
    if(!dialog)return Promise.resolve(globalThis.confirm?.(`${title}\n\n${body}`) ?? true);
    $b('[data-bulk-confirm-title]').textContent=title;
    $b('[data-bulk-confirm-body]').textContent=body;
    const list=$b('[data-bulk-confirm-list]');
    list.innerHTML=items.map(item=>`<li>${text(item)}</li>`).join('');
    list.hidden=!items.length;
    const ok=$b('[data-bulk-confirm-ok]');
    ok.textContent=confirm;
    ok.classList.toggle('jobs-tb-btn--danger',danger);
    ok.classList.toggle('jobs-tb-btn--primary',!danger);
    return new Promise(resolve=>{
      let settled=false;
      const finish=value=>{if(settled)return;settled=true;dialog.removeEventListener('close',onClose);resolve(value);};
      const onClose=()=>finish(dialog.returnValue==='confirm');
      dialog.addEventListener('close',onClose);
      dialog.querySelectorAll('[data-bulk-confirm-cancel]').forEach(button=>{button.onclick=()=>{dialog.returnValue='cancel';dialog.close();};});
      ok.onclick=()=>{dialog.returnValue='confirm';dialog.close();};
      dialog.returnValue='';
      if(dialog.open)dialog.close();
      dialog.showModal();
    });
  }
  function preserveMarkup(host, markup) {
    if(!host||host.__bulkMarkup===markup)return;
    const selection=window.getSelection?.();if(selection?.toString()&&host.contains(selection.anchorNode))return;
    const active=document.activeElement;const attrs=active&&host.contains(active)?Array.from(active.attributes).filter(attr=>attr.name.startsWith('data-')).map(attr=>[attr.name,attr.value]):[];
    const openDetails=Array.from(host.querySelectorAll('details[open]')).map(node=>node.querySelector('summary')?.textContent);
    host.innerHTML=markup;host.__bulkMarkup=markup;
    for(const details of host.querySelectorAll('details'))if(openDetails.includes(details.querySelector('summary')?.textContent))details.open=true;
    if(attrs.length){const match=Array.from(host.querySelectorAll('button,input,select,a')).find(node=>attrs.every(([name,value])=>node.getAttribute(name)===value));match?.focus({preventScroll:true});}
  }
  function navigationState() {return {...state.nav};}
  function restoreNavigation(nav) {
    state.nav = {...nav,tab:'bulk',view:['list','create','detail'].includes(nav.view) ? nav.view : 'list'};
    state.epoch++; state.loading=false;state.listCursor=nav.view==='list'?(nav.cursor||''):'';state.listPrev=[]; state.targetPrev=[];state.selected.clear();state.targets=null;state.detail=null;state.rounds=[];state.roundsCursor=null;
  }
  function navigate(view, extra = {}) {
    restoreNavigation({tab:'bulk',view,...extra});
    activateTab('bulk',true,'none'); recordNavigationHistory('push');
  }
  function updateNavigation(extra) {
    state.nav = {...state.nav,...extra};state.epoch++;state.loading=false;state.targets=null;state.targetPrev=[];state.selected.clear();
    recordNavigationHistory('push'); renderDetailShell(); void loadDetail(true);
  }
  function ensureCatalog(force = false) {
    if (state.catalog && !force) return Promise.resolve(state.catalog);
    return request('/catalog').then(value => {state.catalog=value;return value;});
  }
  async function ensureFacets() {
    const query=AccountQuery.normalize(state.draft?.query);const signature=JSON.stringify(query);
    const cached=state.facetsCache.get(signature);if(cached&&Date.now()-cached.at<30000){state.facets=cached.value;return;}
    const data=await request(`/query-facets?query=${encodeURIComponent(signature)}`);
    const value=data.facets||data;state.facetsCache.set(signature,{value,at:Date.now()});
    if(signature===JSON.stringify(AccountQuery.normalize(state.draft?.query))){state.facets=value;state.matched=data.matched??null;if(typeof renderMatch==='function')renderMatch();}
    if(state.facetsCache.size>10)state.facetsCache.delete(state.facetsCache.keys().next().value);
  }
  function scheduleFacets() {
    clearTimeout(state.facetsTimer);
    const epoch=state.epoch;const signature=JSON.stringify(AccountQuery.normalize(state.draft?.query));
    state.facetsTimer=setTimeout(async()=>{
      try{
        await ensureFacets();
        if(epoch!==state.epoch||signature!==JSON.stringify(AccountQuery.normalize(state.draft?.query)))return;
        AccountFilters.updateOptions($b('[data-bulk-filters]'),filterSchema());
      }catch(error){if(epoch===state.epoch)report(error,'筛选选项更新失败：');}
    },350);
  }
  function filterSchema() {
    const schema=state.catalog.query_schema||{};const fields=Array.isArray(schema.fields)?schema.fields:[];
    const merged=new Map(fields.map(field=>[field.key,{...field}]));
    for(const [name,values] of Object.entries(state.facets||{})){if(Array.isArray(values))merged.set(name,{...(merged.get(name)||{key:name}),options:values.map(row=>({...row,label:row.label||facetLabel(name==='token'?'account_token':name,row.value)}))});}
    return {...schema,fields:[...merged.values()]};
  }
  function operations() {return state.catalog?.operations || [];}
  function operation() {return operations().find(item => item.key === state.draft?.operation_key);}
  function configRevision() {return String(operation()?.effective_settings?.config_revision ?? operation()?.config_revision ?? state.catalog?.config_revision ?? '');}
  function operationLabel(value) {return operations().find(item=>item.key===value)?.label || operationNames[value] || value || '批量操作';}
  function shell() {
    const root=document.getElementById('tab-bulk');
    root.innerHTML=`<div class="bulk-page"><header class="bulk-heading"><div class="bulk-heading-copy"><button type="button" class="bulk-back" data-bulk-action="list" aria-label="返回批次列表" ${state.nav.view==='list'?'hidden':''}>←</button><div><h2 data-bulk-title>批次列表</h2><p data-bulk-subtitle></p></div></div><div class="bulk-actions"><button type="button" class="jobs-tb-btn" data-bulk-action="refresh">刷新</button><button type="button" class="jobs-tb-btn ${state.nav.view==='list'?'jobs-tb-btn--primary':''}" data-bulk-action="new">新建批次</button></div></header><p class="bulk-error" data-bulk-error role="alert" hidden></p><p class="bulk-notice" data-bulk-notice role="status" hidden></p><div class="bulk-notice bulk-inline-fields" data-bulk-recovery hidden></div><div data-bulk-content></div><dialog class="bulk-confirm" data-bulk-confirm aria-labelledby="bulkConfirmTitle"><form method="dialog" class="bulk-confirm-card"><div class="bulk-confirm-head"><strong id="bulkConfirmTitle" data-bulk-confirm-title>确认操作</strong><button type="button" class="bulk-confirm-close" data-bulk-confirm-cancel aria-label="关闭">×</button></div><p class="bulk-confirm-body" data-bulk-confirm-body></p><ul class="bulk-confirm-list" data-bulk-confirm-list hidden></ul><div class="bulk-confirm-actions"><button type="button" class="jobs-tb-btn" data-bulk-confirm-cancel>返回</button><button type="button" class="jobs-tb-btn jobs-tb-btn--danger" data-bulk-confirm-ok>确认</button></div></form></dialog></div>`;
    const dialog=$b('[data-bulk-confirm]');
    dialog?.addEventListener('click',event=>{if(event.target===dialog){dialog.returnValue='cancel';dialog.close();}});
  }
  async function activate() {
    clearTimeout(state.timer);
    shell();renderRecovery();document.querySelectorAll('[data-bulk-nav]').forEach(button=>button.classList.toggle('is-active',button.dataset.bulkNav===state.nav.view));
    if (state.nav.view === 'create') {
      state.draft ||= readSaved('turb_bulk_draft_v1', defaultDraft());
      state.selection ||= readSaved('turb_bulk_selection_v1', null);
      $b('[data-bulk-title]').textContent='新建批次';
      $b('[data-bulk-action="new"]').hidden=true;
      $b('[data-bulk-content]').innerHTML='<div class="bulk-empty" role="status">正在读取操作和筛选配置…</div>';
      const epoch=state.epoch;
      try {await ensureCatalog();try {await ensureFacets();}catch(error){if(epoch===state.epoch)report(error,'筛选选项读取失败：');}if(epoch===state.epoch) {renderCreate();if(state.selection)await pollSelection();}} catch(e){if(epoch===state.epoch)report(e,'读取配置失败：');}
    } else if(state.nav.view === 'detail' && state.nav.batch_id) {
      $b('[data-bulk-title]').textContent=`批次 #${state.nav.batch_id}`;
      renderDetailShell();await loadDetail(true);
    } else {state.nav.view='list';renderListShell();await loadList(true);}
    schedule();
  }
  function visible() {return !document.hidden && !document.getElementById('tab-bulk')?.classList.contains('hidden');}
  function schedule() {
    clearTimeout(state.timer);if(!visible())return;
    if(state.nav.view==='create' && !['preparing'].includes(state.selection?.state || state.selection?.status))return;
    if(state.nav.view==='detail' && state.detail && ['ended','completed'].includes(state.detail.control?.state || state.detail.control_state) && !state.pendingRound && !state.detail.control?.pending)return;
    state.timer=setTimeout(async()=>{if(!visible())return;try {
      if(state.nav.view==='list')await loadList(false);
      else if(state.nav.view==='detail')await loadDetail(false);
      else if(state.selection)await pollSelection();
    }finally{schedule();}},state.nav.view==='list'?7000:2000);
  }
  function notice(message) {
    for(const selector of ['[data-bulk-notice]','[data-bulk-action-notice]']){
      const host=$b(selector);if(host){host.textContent=message;host.hidden=!message;}
    }
  }
  function optionsMarkup(items, selected='') {return items.map(([value,name])=>`<option value="${attrEsc(value)}" ${value===selected?'selected':''}>${text(name)}</option>`).join('');}
  function popoverHeader(title) {return `<div class="bulk-filter-popover-heading"><strong>${text(title)}</strong><button type="button" data-bulk-close-popover aria-label="关闭${attrEsc(title)}筛选">完成</button></div>`;}
  function renderListShell() {
    $b('[data-bulk-content]').innerHTML=`<section class="bulk-card bulk-list-card"><div class="bulk-kpis" data-bulk-kpis hidden></div><form class="bulk-list-filters" data-bulk-list-form><label class="bulk-field bulk-search-field"><span class="bulk-sr-only">名称或批次号</span><input name="q" type="search" value="${attrEsc(state.nav.q||'')}" placeholder="搜索批次名称或编号"></label><label class="bulk-field"><span class="bulk-sr-only">操作</span><select name="operation" aria-label="操作"><option value="">全部操作</option>${optionsMarkup(Object.entries(operationNames),state.nav.operation||'')}</select></label><label class="bulk-field"><span class="bulk-sr-only">状态</span><select name="state" aria-label="状态"><option value="">全部状态</option>${optionsMarkup(['active','cancel_requested','stop_requested','ended'].map(x=>[x,label(x)]),state.nav.state||'')}</select></label><details class="bulk-filter-popover bulk-list-dates"><summary>创建日期${state.nav.created_from||state.nav.created_to?'<span class="bulk-filter-dot"></span>':''}</summary><div class="bulk-filter-popover-panel">${popoverHeader("创建日期")}<label class="bulk-field">创建日期从<input type="date" name="created_from" value="${attrEsc(state.nav.created_from||'')}"></label><label class="bulk-field">创建日期至<input type="date" name="created_to" value="${attrEsc(state.nav.created_to||'')}"></label></div></details><div class="bulk-filter-actions"><button type="button" class="bulk-link" data-bulk-action="reset-filters">重置</button><button class="jobs-tb-btn" type="submit">查询</button></div></form><div data-bulk-list class="bulk-table-wrap"><div class="bulk-empty" role="status">正在加载批次…</div></div><nav class="bulk-pager" aria-label="批次分页"><span data-list-page>第 1 页</span><div class="bulk-pager-actions"><button class="jobs-tb-btn" data-bulk-action="list-prev" disabled>上一页</button><button class="jobs-tb-btn" data-bulk-action="list-next" disabled>下一页</button></div></nav></section>`;
  }
  async function loadList(force) {
    if(state.loading)return;busy(true);const epoch=state.epoch;
    try {
      const params=new URLSearchParams({page_size:'20'});
      if(state.listCursor)params.set('cursor',state.listCursor);
      if(state.nav.q)params.set('q',state.nav.q);
      if(state.nav.operation)params.set('operation_key[]',state.nav.operation);
      if(state.nav.state)params.set('control_state[]',state.nav.state);
      for(const field of ['created_from','created_to'])if(state.nav[field])params.set(field,new Date(`${state.nav[field]}T${field==='created_to'?'23:59:59':'00:00:00'}`).toISOString());
      const data=await request(`/batches?${params}`);if(epoch!==state.epoch)return;
      const previousIds=JSON.stringify((state.list?.items||[]).map(item=>String(item.id)));
      const nextIds=JSON.stringify((data.items||[]).map(item=>String(item.id)));
      const changed=Boolean(state.list&&previousIds!==nextIds);
      state.list={...data,next_cursor:data.next_cursor??data.page?.next_cursor};state.listFetchedAt=Date.now();
      renderList(state.list);
      if(changed&&!force)showToast('批次列表已更新');
      if(force){clearError();notice('');}
    }catch(e){if(epoch===state.epoch){report(e,'加载批次失败：');if(!state.list)$b('[data-bulk-list]').innerHTML='<div class="bulk-empty">批次加载失败，点击上方刷新重试。</div>';}}finally{if(epoch===state.epoch)busy(false);}
  }
  const shortDate = value => value ? formatDateTime(value).slice(0,16) : '—';
  function renderKpis(data) {
    const host=$b('[data-bulk-kpis]');if(!host)return;
    const summary=data.summary||null;
    if(!summary||!Number(summary.total_batches)){host.hidden=true;host.innerHTML='';return;}
    host.hidden=false;
    const card=(name,value,note,warn)=>{const n=Number(value)||0;return `<div class="bulk-kpi${warn&&n?' is-warn':''}"><span>${name}</span><b>${n}${note?`<small>${note}</small>`:''}</b></div>`;};
    host.innerHTML=[card('执行中',summary.active_batches,'批'),card('已结束',summary.ended_batches,'批'),card('失败账号',summary.failed_targets,'可重跑',true),card('待确认',summary.attention_targets,'需核对',true)].join('');
  }
  function renderList(data) {
    const rows=data.items||[];
    const host=$b('[data-bulk-list]');if(!host)return;
    if(window.getSelection()?.toString()&&host.contains(window.getSelection()?.anchorNode))return;
    const updated=state.listFetchedAt?new Date(state.listFetchedAt).toLocaleTimeString('zh-CN',{hour12:false}):'—';
    renderKpis(data);
    const subtitle=$b('[data-bulk-subtitle]');
    if(subtitle){const summary=data.summary||{};subtitle.textContent=[`${Number(summary.total_batches??rows.length)} 个批次`,Number(summary.active_batches)?`${summary.active_batches} 个执行中`:''].filter(Boolean).join(' · ');}
    preserveMarkup(host,rows.length?`<table class="bulk-table bulk-batch-table"><thead><tr><th>批次</th><th>状态</th><th>完成进度</th><th>当前结果</th><th>创建时间</th><th><span class="bulk-sr-only">操作</span></th></tr></thead><tbody>${rows.map(item=>{
      const counts=item.summary||item.counts||{};const done=terminal.reduce((sum,k)=>sum+Number(counts[k]||0),0);const total=Number(item.target_count||0);const progress=total?Math.min(100,Math.round(done/total*100)):0;const finished=progress>=100||String(item.control?.state||item.control_state||item.state)==='ended';
      const pill=(key,className,title)=>{const n=Number(counts[key]||0);return `<button class="bulk-pill ${className}${n?'':' is-zero'}" data-bulk-open="${attrEsc(item.id)}" data-result-state="${key}" ${n?'':'disabled'}>${title} <b>${n}</b></button>`;};
      return `<tr><td class="bulk-cell-name" data-label="批次"><button class="bulk-batch-name" data-bulk-open="${attrEsc(item.id)}">${text(item.name||item.title||`批次 #${item.id}`)}</button><small>#${text(item.id)} · ${text(operationLabel(item.operation?.key||item.operation_key||item.action_key))}</small></td><td class="bulk-cell-state" data-label="状态">${badge(item.control?.state||item.control_state||item.state)}</td><td class="bulk-cell-progress" data-label="完成进度"><div class="bulk-progress-caption"><span>${done} / ${total}</span><span>${progress}%</span></div><progress class="bulk-progress${finished?' is-done':''}" value="${done}" max="${Math.max(1,total)}" aria-label="已结束 ${done} 个，共 ${total} 个"></progress></td><td class="bulk-cell-result" data-label="当前结果"><div class="bulk-result-links">${pill('success','is-success','成功')}${pill('failed','is-failed','失败')}${pill('attention_required','is-warn','待确认')}</div></td><td class="bulk-cell-date" data-label="创建时间">${text(shortDate(item.created_at))}</td><td class="bulk-cell-open" data-label="操作"><button class="bulk-open-arrow" data-bulk-open="${attrEsc(item.id)}" aria-label="打开批次详情">→</button></td></tr>`;
    }).join('')}</tbody></table>`:`<div class="bulk-empty"><strong>还没有${state.nav.q||state.nav.operation||state.nav.state?'匹配的':''}批次</strong><p>选择操作和账号范围，即可集中执行与追踪结果。</p><button type="button" class="jobs-tb-btn jobs-tb-btn--primary" data-bulk-action="new">新建批次</button></div>`);
    $b('[data-bulk-action="list-prev"]').disabled=!state.listPrev.length;
    $b('[data-bulk-action="list-next"]').disabled=!data.next_cursor;
    $b('[data-list-page]').textContent=`第 ${state.listPrev.length+1} 页 · 本页 ${rows.length} 个 · 更新于 ${updated}`;
  }
  function badge(value) {return `<span class="bulk-badge is-${attrEsc(value||'preparing')}">${text(label(value))}</span>`;}
  function operationSettingsSummary(op){
    const settings=op?.effective_settings||{};const parts=[];
    if(Array.isArray(settings.countries)&&settings.countries.length)parts.push(`国家 ${settings.countries.join('、')}`);
    for(const [key,name] of [['driver','驱动'],['password_driver','密码驱动'],['twofa_driver','2FA 驱动'],['codex_driver','Codex 驱动']])if(settings[key])parts.push(`${name} ${settings[key]}`);
    const steps=[['plan_check_enabled','套餐'],['password_enabled','密码'],['twofa_enabled','2FA'],['codex_enabled','Codex']].filter(([key])=>settings[key]).map(([,name])=>name);
    if(steps.length)parts.push(`启用 ${steps.join('、')}`);
    if(settings.auto_refresh_at_enabled!==undefined)parts.push(`自动刷新 AT ${settings.auto_refresh_at_enabled?'开':'关'}`);
    else if(settings.auto_refresh_at!==undefined)parts.push(`自动刷新 AT ${settings.auto_refresh_at?'开':'关'}`);
    return parts.join(' · ');
  }
  function renderMatch() {
    const bar=$b('[data-bulk-match]');if(!bar)return;
    const count=state.matched;
    if(count==null){bar.hidden=true;return;}
    bar.hidden=false;
    const node=$b('[data-bulk-match-count]');if(node)node.textContent=String(count);
    bar.classList.toggle('is-zero',Number(count)===0);
    const warn=$b('[data-bulk-side-warning]');
    if(warn){const big=Number(count)>=200;warn.hidden=!big;warn.textContent=big?`一次影响 ${count} 个账号，建议先限制 50 个试跑，确认结果后再放开。`:'';}
  }
  function renderFilterChips() {
    const host=$b('[data-bulk-filter-chips]');if(!host)return;
    const filters=state.draft?.query?.filters||{};const chips=[];
    for(const [key,value] of Object.entries(filters)){
      if(value==null||value==='')continue;
      if(Array.isArray(value)&&!value.length)continue;
      chips.push(`<span class="bulk-chip">${text(facetLabel(key))} <b>${text(Array.isArray(value)?value.join('、'):value)}</b></span>`);
      if(chips.length>=4)break;
    }
    host.innerHTML=(chips.join('')||'<span class="bulk-chip is-empty">未加条件，默认全部账号</span>')+'<span class="bulk-chip is-add">+ 添加条件</span>';
  }
  function renderSideSummary(){
    const draft=state.draft;if(!draft)return;
    const set=(selector,value)=>{const node=$b(selector);if(node)node.textContent=value;};
    set('[data-bulk-side-operation]',operationLabel(draft.operation_key));
    const source=draft.source;let scope='按当前筛选';
    if(source?.kind==='ids')scope=`已选 ${source.ids.length} 个账号`;
    else if(source?.kind==='batch_targets')scope=`批次 #${source.batch_id} 的固定名单`;
    else if(draft.query?.filters?.email)scope=`邮箱含「${draft.query.filters.email}」`;
    set('[data-bulk-side-scope]',scope);
    set('[data-bulk-side-limit]',source?'按固定名单':draft.limit?`${Number(draft.limit)} 个`:'全部匹配');
    set('[data-bulk-side-concurrency]',String(Number(draft.max_concurrency||3)));
    const brief=$b('[data-bulk-execution-brief]');
    if(brief)brief.textContent=`并发 ${Number(draft.max_concurrency||3)}${draft.limit?` · 最多 ${Number(draft.limit)} 个`:' · 全部匹配'}`;
  }
  function renderCreate() {
    const draft=state.draft;if(!operations().some(x=>x.key===draft.operation_key))draft.operation_key=operations()[0]?.key||'';
    const selectedOperation=operations().find(x=>x.key===draft.operation_key);
    if(selectedOperation?.availability?.available===false){const next=operations().find(x=>x.availability?.available!==false);if(next)draft.operation_key=next.key;}
    const source=draft.source;
    const descriptions={plan_check:'套餐与优惠',token_refresh:'获取最新访问令牌',password_setup:'补充登录密码',twofa_setup:'启用验证器',codex_retry:'获取授权凭证',account_completion:'完成已配置的项目'};
    const paths={plan_check:'M4 5h16v14H4z M4 10h16 M8 14h3',token_refresh:'M20 7v5h-5 M4 17v-5h5 M6 8a7 7 0 0 1 12-2l2 2 M4 16l2 2a7 7 0 0 0 12-2',password_setup:'M8 11V7a4 4 0 0 1 8 0v4 M6 11h12v10H6z M12 15v2',twofa_setup:'M12 3l8 4v5c0 5-8 9-8 9s-8-4-8-9V7z M8 12l3 3 5-6',codex_retry:'M8 7l-5 5 5 5 M16 7l5 5-5 5 M14 4l-4 16',account_completion:'M9 5h11 M9 12h11 M9 19h11 M3 5h1 M3 12h1 M3 19h1'};
    const cards=operations().map(item=>{
      const unavailable=item.availability?.available===false;
      const reason=item.availability?.reason||item.availability?.reason_code||'当前不可用';
      return `<label class="bulk-operation ${unavailable?'is-unavailable':''}" title="${attrEsc(unavailable?reason:'')}" ${unavailable?'aria-disabled="true"':''}><input type="radio" name="operation_key" value="${attrEsc(item.key)}" ${item.key===draft.operation_key?'checked':''} ${unavailable?'disabled':''} required><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[item.key]||paths.account_completion}"></path></svg><span><strong>${text(item.label||operationLabel(item.key))}</strong><small>${text(descriptions[item.key]||'批量账号操作')}</small></span>${unavailable?`<span class="bulk-operation-state">暂不可用</span>`:'<span class="bulk-operation-check" aria-hidden="true">✓</span>'}</label>`;
    }).join('');
    $b('[data-bulk-content]').innerHTML=`<form data-bulk-create-form class="bulk-create-form"><div class="bulk-create-main"><section class="bulk-card bulk-create-card"><div class="bulk-step-head"><span class="bulk-step-no">1</span><div><h3>选择操作</h3><p class="bulk-section-note">本次要对账号做什么</p></div></div><div class="bulk-operation-grid" role="radiogroup" aria-label="批量操作">${cards}</div><p class="bulk-error bulk-operation-warning" data-bulk-operation-warning hidden></p><p class="bulk-operation-summary" data-bulk-operation-summary></p><div data-bulk-parameters></div><div data-bulk-settings></div></section><section class="bulk-card bulk-create-card"><div class="bulk-step-head"><span class="bulk-step-no">2</span><div><h3>账号范围</h3><p class="bulk-section-note">与账号列表使用同一套筛选</p></div><button type="button" class="bulk-link" data-bulk-action="clear-filters">清空条件</button></div><p class="bulk-match" data-bulk-match hidden><span>当前条件匹配</span><b data-bulk-match-count>—</b><span>个账号</span></p><div class="bulk-chips" data-bulk-filter-chips></div><div data-bulk-source-note>${source?`<div class="bulk-source-banner"><span>${source.kind==='ids'?`已选 ${source.ids.length} 个账号`:`沿用批次 #${text(source.batch_id)} 的账号名单`}</span><button type="button" class="bulk-link" data-bulk-action="use-query">改为按条件筛选</button></div>`:''}</div><div data-bulk-filters ${source?'hidden':''}></div><div class="bulk-range-row" ${source?'hidden':''}><label class="bulk-field bulk-limit-field">最多处理数量<input name="limit" type="number" min="1" max="${Number(state.catalog?.limits?.target_limit_max||100000)}" value="${attrEsc(draft.limit||'')}" placeholder="全部匹配"></label><p class="bulk-muted">留空表示全部匹配账号；按账号 ID 从大到小固定。</p></div></section><section class="bulk-card bulk-create-card bulk-create-settings"><details class="bulk-advanced"><summary>批次设置<span data-bulk-execution-brief>并发 ${Number(draft.max_concurrency||3)}${draft.limit?` · 最多 ${Number(draft.limit)} 个`:' · 全部匹配'}</span></summary><div class="bulk-advanced-fields"><label class="bulk-field bulk-name-field">批次名称<input name="name" maxlength="120" value="${attrEsc(draft.name||'')}" placeholder="留空自动命名"></label><label class="bulk-field">本批并发上限<input name="max_concurrency" type="number" min="1" max="${Number(operation()?.max_concurrency||state.catalog?.limits?.concurrency_max||128)}" value="${attrEsc(draft.max_concurrency||3)}" required></label></div></details></section><section class="bulk-card bulk-preview-card" data-bulk-preview-panel hidden><div data-bulk-preview></div></section></div><aside class="bulk-card bulk-create-side"><div class="bulk-side-sticky"><div class="bulk-side-heading"><div><span class="bulk-side-kicker">执行摘要</span><strong data-bulk-create-summary>选择条件后预览账号</strong></div></div><div class="bulk-side-big" data-bulk-side-count>待预览</div><p class="bulk-side-hint" data-bulk-create-hint>预览后会显示实际可用数量</p><dl class="bulk-side-meta"><div><dt>操作</dt><dd data-bulk-side-operation>—</dd></div><div><dt>范围</dt><dd data-bulk-side-scope>—</dd></div><div><dt>数量上限</dt><dd data-bulk-side-limit>全部匹配</dd></div><div><dt>本批并发</dt><dd data-bulk-side-concurrency>3</dd></div></dl><p class="bulk-side-warning" data-bulk-side-warning hidden></p><p class="bulk-error" data-bulk-action-error role="alert" hidden></p><p class="bulk-notice" data-bulk-action-notice role="status" hidden></p><div class="bulk-side-actions"><button type="button" class="jobs-tb-btn jobs-tb-btn--primary" data-bulk-action="preview">预览账号</button><button type="submit" class="jobs-tb-btn jobs-tb-btn--primary" data-bulk-submit disabled hidden>创建并执行</button></div><p class="bulk-side-foot">预览只统计，不写入数据库</p><button type="button" class="bulk-side-back" data-bulk-action="list">← 返回批次列表</button></div></aside></form>`;
    AccountFilters.mount($b('[data-bulk-filters]'),draft.query,filterSchema(),value=>{draft.query=value;invalidateSelection();saveDraft();scheduleFacets();renderFilterChips();});
    renderParameters();renderSideSummary();renderSelection();renderFilterChips();renderMatch();
  }
  function renderParameters() {
    const op=operation();const schema=op?.parameter_schema?.properties||op?.parameter_schema||{};
    const entries=Object.entries(schema).filter(([name,definition])=>definition&&typeof definition==='object'&&name!=='timezone_offset_min');
    $b('[data-bulk-parameters]').innerHTML=entries.length?`<div class="bulk-filter-grid">${entries.map(([name,definition])=>{
      const value=state.draft.parameters?.[name]??definition.default??'';const title=definition.label||({driver:'执行驱动'}[name])||name;
      if(definition.enum)return `<label class="bulk-field">${text(title)}<select data-bulk-parameter="${attrEsc(name)}"><option value="">使用当前配置</option>${definition.enum.map(x=>`<option value="${attrEsc(x)}" ${String(x)===String(value)?'selected':''}>${text(definition.enum_labels?.[x]||x)}</option>`).join('')}</select></label>`;
      if(definition.type==='boolean')return `<label class="bulk-field bulk-check"><input type="checkbox" data-bulk-parameter="${attrEsc(name)}" ${value===true?'checked':''}>${text(title)}</label>`;
      return `<label class="bulk-field">${text(title)}<input data-bulk-parameter="${attrEsc(name)}" type="${definition.type==='integer'?'number':'text'}" value="${attrEsc(value)}"></label>`;
    }).join('')}</div>`:'';
    const settings=op?.effective_settings||{};
    const settingsLabels={countries:'查询国家',driver:'执行驱动',auto_refresh_at:'自动刷新 AT',auto_refresh_at_on_failure:'失败后刷新 AT',auto_refresh_at_enabled:'自动刷新 AT',plan_check_enabled:'套餐查询',password_enabled:'补密码',twofa_enabled:'补 2FA',codex_enabled:'补 Codex',config_revision:'配置版本',password_driver:'密码驱动',twofa_driver:'2FA 驱动',codex_driver:'Codex 驱动'};
    $b('[data-bulk-settings]').innerHTML=`${op?.availability?.available===false?`<p class="bulk-error">${text(op.availability.reason||op.availability.reason_code||'此操作暂不可用')}</p>`:''}<details class="bulk-settings"><summary>操作设置</summary><dl>${Object.entries(settings).filter(([k])=>settingsLabels[k]).map(([k,v])=>`<dt>${text(settingsLabels[k])}</dt><dd>${text(Array.isArray(v)?v.join('、'):typeof v==='boolean'?(v?'开启':'关闭'):v)}</dd>`).join('')||'<dt>设置来源</dt><dd>当前已保存配置</dd>'}</dl></details>`;
    const summary=operationSettingsSummary(op);
    const summaryHost=$b('[data-bulk-operation-summary]');if(summaryHost)summaryHost.textContent=summary?`当前设置：${summary}`:'';
    const warning=$b('[data-bulk-operation-warning]');
    if(warning){const unavailable=op?.availability?.available===false;warning.hidden=!unavailable;warning.textContent=unavailable?(op.availability.reason||op.availability.reason_code||'此操作暂不可用'):'';}
    renderSideSummary();
  }
  function invalidateSelection() {
    state.selection=null;saveSelection();state.previewCursor='';state.previewPrev=[];state.epoch++;clearTimeout(state.timer);renderSelection();
  }
  function parameters() {
    const result={...state.draft.parameters};
    if(operation()?.parameter_schema?.timezone_offset_min || operation()?.parameter_schema?.properties?.timezone_offset_min)result.timezone_offset_min=new Date().getTimezoneOffset();
    return result;
  }
  async function preview() {
    const form=$b('[data-bulk-create-form]');if(!form.reportValidity())return;
    const button=$b('[data-bulk-action="preview"]');if(button.disabled)return;
    button.disabled=true;button.textContent='正在固定范围…';clearError();
    const epoch=++state.epoch;
    const query=AccountQuery.normalize({...state.draft.query,limit:state.draft.limit||null});
    const body={operation:{key:state.draft.operation_key,version:operation()?.version||1},source:state.draft.source||{kind:'query',query},parameters:parameters(),expected_config_revision:configRevision()};
    try {
      const result=await intent('selection','/selections',body);if(epoch!==state.epoch)return;
      state.selection={...result,request_parameters:body.parameters,config_revision:body.expected_config_revision};state.previewCursor='';state.previewPrev=[];
      saveSelection();saveDraft();renderSelection();await pollSelection();schedule();
    }catch(e){if(epoch===state.epoch){report(e,'预览失败：');if(e.code==='config_revision_changed'){await ensureCatalog(true);invalidateSelection();renderParameters();notice('配置已更新，请查看当前设置后重新预览。');}}}
    finally {if(button.isConnected){button.disabled=false;button.textContent=state.selection?.state==='ready'?'重新预览':'预览账号';}}
  }
  async function pollSelection() {
    if(!state.selection)return;const id=String(state.selection.id);const epoch=state.epoch;
    try {
      const params=new URLSearchParams({page_size:'20'});if(state.previewCursor)params.set('cursor',state.previewCursor);
      const data=await request(`/selections/${encodeURIComponent(id)}?${params}`);
      if(epoch!==state.epoch||String(state.selection?.id)!==id)return;
      state.selection={...state.selection,...data,next_cursor:data.next_cursor??data.page?.next_cursor};saveSelection();renderSelection();
    }catch(e){if(epoch===state.epoch)report(e,'读取预览失败：');}
  }
  function renderSelection() {
    const host=$b('[data-bulk-preview]');if(!host)return;
    const selection=state.selection;const status=selection?.state||selection?.status;
    const ready=status==='ready';const count=selection?.target_count??selection?.total_count;
    const submit=$b('[data-bulk-submit]');if(submit){submit.disabled=!ready||Number(count)<=0||operation()?.availability?.available===false;submit.hidden=!ready;}
    const previewButton=$b('[data-bulk-action="preview"]');if(previewButton){previewButton.textContent=ready?'重新预览':'预览账号';previewButton.classList.toggle('jobs-tb-btn--primary',!ready);}
    const summary=$b('[data-bulk-create-summary]');if(summary)summary.textContent=ready?`已确认 ${Number(count)} 个账号`:status==='preparing'?'正在准备账号名单…':'选择条件后预览账号';
    const hint=$b('[data-bulk-create-hint]');if(hint)hint.textContent=ready?'仅执行这份名单内的账号':status==='preparing'?'可离开页面，稍后继续':'预览完成后确认创建';
    const sideCount=$b('[data-bulk-side-count]');if(sideCount)sideCount.textContent=ready?`${Number(count)} 个`:status==='preparing'?'准备中':'待预览';
    const panel=$b('[data-bulk-preview-panel]');if(panel)panel.hidden=!selection;
    renderSideSummary();
    if(!selection){host.innerHTML='';return;}
    const rows=selection.items||selection.targets||[];const preflight=selection.preflight?.counts||selection.preflight||{};
    const countReady=Number(preflight.ready??preflight.eligible??0),countWaiting=Number(preflight.waiting_account||0),countUnavailable=Number(preflight.not_executable??preflight.not_executed??0);
    preserveMarkup(host,`<div class="bulk-section-heading"><h3>名单预览</h3>${badge(status)}</div>${status==='failed'?`<p class="bulk-error">${text(selection.error?.message||selection.error_detail?.message||selection.error_code||'准备失败，请重新预览')}</p>`:''}${['expired','consumed'].includes(status)?'<p class="bulk-muted">此名单已过期或已使用，请重新预览。</p>':''}${status==='preparing'?'<div class="bulk-preparing" role="status"><span class="bulk-loading-dot"></span>正在筛选账号并检查执行条件…</div>':''}${ready?`<div class="bulk-preflight-summary"><div><span>账号总数</span><strong>${Number(count)}</strong></div><div><span>可提交</span><strong>${countReady}</strong></div><div><span>等待账号</span><strong>${countWaiting}</strong></div><div><span>条件不满足</span><strong>${countUnavailable}</strong></div></div><div class="bulk-preview-meta">${selection.selection_at?`名单生成于 ${text(date(selection.selection_at))}`:''}${selection.matched_count!=null?` · 匹配 ${Number(selection.matched_count)} 个`:''}</div>`:''}${rows.length?`<details class="bulk-preview-details" open><summary>查看账号名单<span>本页 ${rows.length} 个</span></summary><div class="bulk-table-wrap"><table class="bulk-table bulk-preview-table"><thead><tr><th>账号</th><th>执行条件</th></tr></thead><tbody>${rows.map(row=>`<tr><td data-label="账号">${text(row.display_snapshot?.email||row.display?.email||row.email||`账号 #${row.target_id||row.account_id}`)}</td><td data-label="执行条件">${text(row.preflight?.reason_label||row.preflight?.reason_code||(row.preflight?.status==='ready'?'可提交':label(row.preflight?.status||row.preflight?.state))||row.reason_code||'执行前核验')}</td></tr>`).join('')}</tbody></table></div>${ready?`<nav class="bulk-pager" aria-label="预览名单分页"><button type="button" class="jobs-tb-btn" data-bulk-action="preview-prev" ${!state.previewPrev.length?'disabled':''}>上一页</button><span>第 ${state.previewPrev.length+1} 页</span><button type="button" class="jobs-tb-btn" data-bulk-action="preview-next" ${!selection.next_cursor?'disabled':''}>下一页</button></nav>`:''}</details>`:''}`);
  }
  async function createBatch() {
    const button=$b('[data-bulk-submit]');if(button.disabled)return;button.disabled=true;button.textContent='正在创建批次…';clearError();
    const op=operation();const selection=state.selection;
    const body={name:state.draft.name,selection_id:String(selection.id),selection_revision:selection.selection_revision,operation:{key:op.key,version:op.version||1},expected_config_revision:selection.config_revision||configRevision(),parameters:selection.request_parameters||parameters(),execution:{max_concurrency:Number(state.draft.max_concurrency)}};
    try{const result=await intent('create','/batches',body);state.selection=null;saveSelection();showToast('批次已受理，正在后台提交目标');navigate('detail',{batch_id:String(result.id||result.batch_id)});}
    catch(e){report(e,'创建失败：');if(['config_revision_changed','selection_settings_mismatch'].includes(e.code)){await ensureCatalog(true);invalidateSelection();renderParameters();notice('设置已变化，请查看更新后的设置并重新预览。');}else if(e.code==='selection_consumed'&&e.details.existing_batch_id){notice(`该范围已用于批次 #${e.details.existing_batch_id}`);}else if(e.code==='selection_expired'){invalidateSelection();}else{button.disabled=false;}}
    finally{if(button.isConnected)button.textContent='创建并执行';}
  }
  function renderDetailShell() {
    $b('[data-bulk-content]').innerHTML=`<section class="bulk-card bulk-overview"><div class="bulk-detail-toolbar"><div data-bulk-detail-meta></div><div class="bulk-actions"><label class="bulk-round-picker"><span class="bulk-sr-only">结果视图</span><select data-bulk-view aria-label="结果视图"><option value="current">当前结果</option></select></label><button class="bulk-link" data-bulk-action="more-rounds" hidden>更多轮次</button><details class="bulk-menu"><summary>更多</summary><div class="bulk-menu-panel"><button data-bulk-action="copy-targets">同一名单再次执行</button><button data-bulk-action="copy-query">复制条件新建</button></div></details></div></div><div class="bulk-control-strip" data-bulk-control-strip><div class="bulk-control-copy"><strong>运行控制</strong><span data-bulk-control-note>只影响当前批次，已开始执行会协作收尾</span></div><div class="bulk-actions"><button type="button" class="jobs-tb-btn jobs-tb-btn--danger" data-bulk-action="cancel">取消排队账号</button><button type="button" class="jobs-tb-btn jobs-tb-btn--danger" data-bulk-action="stop">停止正在执行</button></div></div><div data-bulk-stats class="bulk-summary-grid"></div><p class="bulk-view-note" data-bulk-view-note></p><div data-bulk-business></div></section><section class="bulk-card bulk-results-card"><div class="bulk-results-heading"><h3>账号明细 <span data-bulk-selected></span><button type="button" class="bulk-link" data-bulk-action="clear-selection" hidden>清空选择</button></h3><div class="bulk-retry-toolbar"><select data-bulk-retry-states aria-label="重跑范围">${optionsMarkup([['failed','失败'],['partial_success','部分成功'],['attention_required','待确认'],['not_executed','未执行'],['cancelled','已取消'],['unsuccessful','全部未成功']])}</select><button class="jobs-tb-btn jobs-tb-btn--primary" data-bulk-action="retry">重跑失败</button><button class="jobs-tb-btn" data-bulk-action="retry-selected" disabled hidden>重跑勾选</button></div></div><p class="bulk-error" data-bulk-action-error role="alert" hidden></p><p class="bulk-notice" data-bulk-action-notice role="status" hidden></p><div data-bulk-state-strip class="bulk-state-strip"></div><form data-bulk-results-form class="bulk-results-filters"><label class="bulk-field bulk-search-field"><span class="bulk-sr-only">账号搜索</span><input type="search" name="q" value="${attrEsc(state.nav.q||'')}" placeholder="搜索本批账号"></label><label class="bulk-field bulk-state-picker"><span class="bulk-sr-only">结果</span><select name="state" aria-label="结果"><option value="">全部结果</option>${optionsMarkup(Object.entries(labels).filter(([k])=>['pending_submit','waiting_account','queued','running','waiting',...terminal].includes(k)),state.nav.result_state||'')}</select></label><details class="bulk-filter-popover"><summary>错误分类${state.nav.reason_code?'<span class="bulk-filter-dot"></span>':''}</summary><div class="bulk-filter-popover-panel">${popoverHeader("错误分类")}<label class="bulk-field">原因码<input name="reason_code" value="${attrEsc(state.nav.reason_code||'')}" placeholder="输入原因码"></label></div></details><button class="jobs-tb-btn" type="submit">筛选</button></form><div data-bulk-targets class="bulk-table-wrap"><div class="bulk-empty" role="status">正在加载账号结果…</div></div><nav class="bulk-pager" aria-label="账号结果分页"><button class="jobs-tb-btn" data-bulk-action="target-prev" disabled>上一页</button><span data-target-page>第 1 页</span><button class="jobs-tb-btn" data-bulk-action="target-next" disabled>下一页</button></nav></section>`;
  }
  function detailParams() {
    const params=new URLSearchParams({view:state.nav.round_id?'round':'current'});
    if(state.nav.round_id)params.set('round_id',state.nav.round_id);return params;
  }
  async function loadDetail(force=false) {
    if(state.loading)return;busy(true);const epoch=state.epoch;const params=detailParams();
    try {
      const detail=await request(`/batches/${encodeURIComponent(state.nav.batch_id)}?${params}`);if(epoch!==state.epoch)return;
      const oldRevision=state.detail?.summary_revision;state.detail=detail;
      if(detail.rounds_head){const merged=new Map(state.rounds.map(round=>[String(round.id),round]));detail.rounds_head.forEach(round=>merged.set(String(round.id),round));if(detail.selected_round)merged.set(String(detail.selected_round.id),detail.selected_round);state.rounds=[...merged.values()].sort((a,b)=>Number(b.round_no)-Number(a.round_no));}
      if(state.roundsCursor===null)state.roundsCursor=detail.rounds_next_cursor||'';
      state.detail.rounds_next_cursor=state.roundsCursor;
      renderDetail();
      if(state.pendingRound){const found=state.rounds.find(x=>String(x.id)===state.pendingRound);if(found&&found.state!=='preparing'){state.pendingRound=null;notice(found.completion_reason==='cancelled_before_freeze'?'重跑准备已取消，当前结果归属不变。':'重跑名单已固定，可以切换查看新轮次。');}}
      if(force||!state.targets||oldRevision!==detail.summary_revision)await loadTargets(epoch,force);
      if(force)clearError();
    }catch(e){if(epoch===state.epoch){report(e,'读取批次失败：');if(!state.detail)$b('[data-bulk-targets]').innerHTML='<div class="bulk-empty">无法读取批次，点击上方刷新重试。</div>';}}finally{if(epoch===state.epoch)busy(false);}
  }
  function renderDetail() {
    const data=state.detail;if(!data)return;
    $b('[data-bulk-title]').textContent=data.name||data.title||`批次 #${state.nav.batch_id}`;
    const counts=data.summary||data.counts||{};const total=data.target_count;const ended=terminal.reduce((n,k)=>n+Number(counts[k]||0),0);
    const active=['pending_submit','waiting_account','queued','running','waiting'].reduce((n,k)=>n+Number(counts[k]||0),0);
    const unsuccessful=terminal.filter(k=>k!=='success').reduce((n,k)=>n+Number(counts[k]||0),0);
    const control=data.control||{};const op=data.operation?.key||data.operation_key||data.action_key;
    $b('[data-bulk-subtitle]').textContent=`${operationLabel(op)} · #${state.nav.batch_id}`;
    preserveMarkup($b('[data-bulk-detail-meta]'),`<div class="bulk-detail-meta">${badge(control.state||data.control_state||data.state)}<span>创建于 ${text(date(data.created_at))}</span><details class="bulk-settings bulk-detail-settings"><summary>范围与设置</summary><dl><dt>名单生成</dt><dd>${text(date(data.selection_summary?.selection_at||data.selection_at))}</dd><dt>配置版本</dt><dd>${text(data.effective_settings?.config_revision||data.config_revision)}</dd><dt>结果更新</dt><dd>${text(date(data.projected_at))}</dd></dl></details></div>${data.projection?.state&&data.projection.state!=='current'?'<span class="bulk-projection-note">汇总同步中</span>':''}`);
    const select=$b('[data-bulk-view]');const selected=state.nav.round_id||'current';
    if(document.activeElement!==select)select.innerHTML=`<option value="current">当前结果</option>${state.rounds.map(round=>`<option value="${attrEsc(round.id)}" ${String(round.id)===selected?'selected':''}>${round.round_no===1?'首轮':`重跑 ${Number(round.round_no)-1}`} · ${text(label(round.state))}${round.target_count==null?' · 准备中':` · ${round.target_count} 个`}</option>`).join('')}`;
    select.value=selected;
    $b('[data-bulk-action="more-rounds"]').hidden=!data.rounds_next_cursor;
    const selectedRound=state.rounds.find(x=>String(x.id)===state.nav.round_id);
    $b('[data-bulk-view-note]').textContent=selectedRound?.completion_reason==='cancelled_before_freeze'?'本轮在名单生成前取消，当前结果未改变。':state.nav.round_id?'仅展示该轮名单及执行结果。':`已结束 ${ended} / ${total??'—'} 个 · 每个账号保留最近一轮结果`;
    preserveMarkup($b('[data-bulk-stats]'),`<div class="bulk-summary-item"><span>账号总数</span><strong>${total??'—'}</strong></div><div class="bulk-summary-item"><span>进行中</span><strong>${active}</strong></div><div class="bulk-summary-item is-success"><span>成功</span><strong>${Number(counts.success||0)}</strong></div><div class="bulk-summary-item ${unsuccessful?'is-warning':''}"><span>未成功</span><strong>${unsuccessful}</strong></div>`);
    const chip=k=>`<button type="button" class="bulk-state-chip ${state.nav.result_state===k?'is-selected':''}" data-bulk-stat="${k}" aria-label="${attrEsc(`${label(k)} ${Number(counts[k]||0)}`)}" aria-pressed="${state.nav.result_state===k}">${text(label(k))}<strong>${Number(counts[k]||0)}</strong></button>`;
    preserveMarkup($b('[data-bulk-state-strip]'),`<button type="button" class="bulk-state-chip ${!state.nav.result_state?'is-selected':''}" data-bulk-action="all-results" aria-pressed="${!state.nav.result_state}">全部<strong>${total??'—'}</strong></button>${['running','queued','success','failed','partial_success','attention_required'].map(chip).join('')}<details class="bulk-more-states"><summary>更多状态</summary><div>${['pending_submit','waiting_account','waiting','not_executed','cancelled'].map(chip).join('')}</div></details>`);
    renderBusiness(data.business_summary||data.metrics||{});
    updateRetryButton();
    $b('[data-bulk-action="copy-query"]').disabled=!data.selection_summary?.query&&!data.query_spec&&!data.selection?.query_spec;
    const capabilities=data.capabilities||data.operation?.capabilities||{};
    const endedState=Boolean(['ended','completed'].includes(control.state||data.control_state));
    const strip=$b('[data-bulk-control-strip]');if(strip)strip.hidden=endedState||(capabilities.cancel_not_started===false&&capabilities.request_stop===false);
    const controlNote=$b('[data-bulk-control-note]');if(controlNote)controlNote.textContent=endedState?'批次已结束':`${active} 个进行中 · 已结束 ${ended} / ${total??'—'}`;
    for(const [action,capability] of [['cancel','cancel_not_started'],['stop','request_stop']]){
      const button=$b(`[data-bulk-action="${action}"]`);if(!button)continue;
      button.hidden=capabilities[capability]===false;
      button.disabled=Boolean(control.pending)||endedState;
    }
  }
  function renderBusiness(metrics) {
    const names={'account.confirmed_no_offer':'本次确认无优惠','account.plan.free':'套餐 · Free','account.plan.plus':'套餐 · Plus','account.plan.pro':'套餐 · Pro','account.plan.team':'套餐 · Team','account.plan.go':'套餐 · Go',confirmed_no_offer_accounts:'本次确认无优惠',no_offer:'无优惠',free_trial:'免费试用',half_price:'半价优惠',other_discount:'其他折扣',success:'成功',failed:'失败',partial_success:'部分成功',confirmed:'已确认',newly_set:'新设置',already_set:'验证已有密码',newly_enabled:'新启用',already_satisfied:'原本已满足',usable_credential:'可用凭证',credential_pending_confirmation:'凭证待确认',confirmed_accounts:'已确认账号',country_success:'查询成功',country_failed:'查询失败','country_query.success':'国家项查询成功','country_query.failed':'国家项查询失败',plan:'套餐',plans:'套餐分布',promotion:'优惠',promotions:'优惠分布',countries:'国家项',password:'密码',twofa:'2FA',codex:'Codex',access_token:'AT',plan_check:'套餐查询',free:'Free',plus:'Plus',team:'Team',pro:'Pro',unknown:'待确认',none:'无优惠',not_executed:'未执行',attention_required:'待确认',pending:'待执行'};
    for(const [kind,name]of Object.entries({none:'无优惠',free_trial:'免费试用',half_price:'半价优惠',other_discount:'其他折扣',discount:'折扣优惠',other_promo:'其他优惠'}))names[`account.plus_offer.${kind}`]=`优惠 · ${name}`;
    for(const [kind,name]of Object.entries({unchanged:'优惠未变化',new_offer:'新增优惠',offer_removed:'优惠消失',changed:'优惠变化',not_comparable:'历史条件不可比较'}))names[`account.comparison.${kind}`]=name;
    Object.assign(names,{'account.password_setup.confirmed':'密码已确认','account.twofa_setup.confirmed':'2FA 已确认','account.codex.credential_confirmed':'Codex 凭证已确认','account.token_refresh.confirmed':'AT 刷新成功','account.token_refresh.unconfirmed':'AT 待确认','account.token_refresh.failed':'AT 刷新失败'});
    for(const [step,name]of Object.entries({password:'密码',twofa:'2FA',codex:'Codex',access_token:'AT',plan_check:'套餐'})){
      names[`step.${step}.confirmed`]=`${name} · 已完成`;
      names[`step.${step}.pending`]=`${name} · 待完成`;
    }
    const groups=new Map();
    function walk(obj,prefix='',depth=0){if(depth>3||!obj||typeof obj!=='object')return;for(const [k,v]of Object.entries(obj)){
      if(['schema','schema_version','version','updated_at'].includes(k))continue;
      const title=prefix?`${prefix} · ${names[k]||k}`:names[k]||k;
      if(typeof v==='number'){
        const group=k.startsWith('country_query.')||k.startsWith('country_')?'国家查询项':k.startsWith('account.plan.')?'套餐分布':k.startsWith('account.plus_offer.')||k.startsWith('account.comparison.')||k==='account.confirmed_no_offer'?'优惠结果':k.startsWith('step.')?'补全项目':'执行结果';
        if(!groups.has(group))groups.set(group,[]);groups.get(group).push([title,v,group==='国家查询项'?'项':'个']);
      }else if(v&&typeof v==='object')walk(v,title,depth+1);
    }}
    walk(metrics);
    preserveMarkup($b('[data-bulk-business]'),groups.size?`<details class="bulk-business-details"><summary>功能统计<span>展开查看</span></summary><div class="bulk-business-groups">${[...groups].map(([name,rows])=>`<section class="bulk-business-group"><h4>${text(name)} · ${name==='国家查询项'?'项':'账号数'}</h4><dl class="bulk-business-metrics">${rows.map(([title,value])=>`<div><dt>${text(title)}</dt><dd>${value}</dd></div>`).join('')}</dl></section>`).join('')}</div></details>`:'');
  }
  async function loadTargets(epoch=state.epoch,force=true) {
    const params=detailParams();params.set('page_size','50');if(state.nav.cursor)params.set('cursor',state.nav.cursor);
    if(state.nav.result_state)params.set('state[]',state.nav.result_state);
    if(state.nav.reason_code)params.set('reason_code[]',state.nav.reason_code);
    if(state.nav.q)params.set('q',state.nav.q);
    const data=await request(`/batches/${encodeURIComponent(state.nav.batch_id)}/targets?${params}`);
    if(epoch!==state.epoch)return;
    const changed=Boolean(state.targets&&JSON.stringify((data.items||[]).map(targetId))!==JSON.stringify((state.targets.items||[]).map(targetId)));
    state.targets={...data,next_cursor:data.next_cursor??data.page?.next_cursor};renderTargets();
    if(changed&&!force)showToast('当前页结果已更新');
  }
  function resultText(result) {
    if(result.refresh_outcome){const outcome=result.refresh_outcome;return ({pending:'等待本轮 AT 刷新',success:'本轮 AT 刷新成功',failed:'本轮 AT 刷新失败',unconfirmed:'本轮 AT 刷新待确认',not_executed:'本轮未执行 AT 刷新'})[outcome]||'AT 刷新待确认';}
    if(result.query_outcome) {
      if(result.query_outcome==='pending')return '等待本轮查询结果';
      if(result.query_outcome==='not_executed')return '本轮未执行';
      const outcomeLabel=result.query_outcome==='unconfirmed'?'待确认':label(result.query_outcome);const parts=[`查询${outcomeLabel}`];
      if(result.account_plan_type)parts.push(`套餐 ${result.account_plan_type}`);
      if(result.confirmed_no_offer)parts.push('本次确认无优惠');
      else if(result.plus_offer_kind&&result.plus_offer_kind!=='unknown')parts.push(facetLabel('promotion',result.plus_offer_kind));
      if(result.comparison&&result.comparison!=='not_comparable')parts.push(({unchanged:'优惠未变化',new_offer:'新增优惠',offer_removed:'优惠消失',changed:'优惠变化'})[result.comparison]||'优惠变化');
      if(result.countries_requested?.length)parts.push(`国家项成功 ${result.country_success_count||0} / ${result.countries_requested.length}`);
      return parts.join(' · ');
    }
    if(result.confirmation)return result.confirmation==='confirmed'?'已确认 · 变更方式未记录':result.confirmation==='not_executed'?'未执行':'尚未确认';
    if(result.credential_confirmation)return result.credential_confirmation==='confirmed'?'本轮可用凭证已确认':result.existing_asset_preserved?'本轮未确认 · 已有可用凭证保留':'本轮凭证尚未确认';
    if(result.required_steps){const stepNames={password:'密码',twofa:'2FA',codex:'Codex',access_token:'AT',plan_check:'套餐'};return `已完成 ${(result.completed_steps||[]).map(x=>stepNames[x]||x).join('、')||'暂无'}${result.pending_steps?.length?`；待完成 ${result.pending_steps.map(x=>stepNames[x]||x).join('、')}`:''}`;}
    return '';
  }
  function targetId(row) {return String(row.canonical_target_id||row.target_id||row.id);}
  function renderTargets() {
    const host=$b('[data-bulk-targets]');if(!host)return;
    if(window.getSelection()?.toString()&&host.contains(window.getSelection()?.anchorNode))return;
    const rows=state.targets?.items||[];
    const focused=document.activeElement?.dataset.bulkTarget;
    const selectedCount=rows.filter(row=>state.selected.has(targetId(row))).length;
    preserveMarkup(host,rows.length?`<table class="bulk-table bulk-target-table"><thead><tr><th><input type="checkbox" data-bulk-select-page aria-label="选择当前页目标" ${selectedCount===rows.length&&rows.length?'checked':''}></th><th>账号</th><th>结果 / 阶段</th><th>结果摘要</th><th>错误分类</th><th>操作</th></tr></thead><tbody>${rows.map(row=>{
      const id=targetId(row);const projected=row.result||{};const result=projected.result||row.result_summary||projected;const error=row.reason||projected.reason||row.error||row.error_info||{};const display=row.display_snapshot||row.display||{};
      const taskId=row.task_id||row.owned_task_id||row.execution?.task_id||row.owned_runs?.[0]?.task_id;const runId=row.owned_run_id||row.run_id||row.execution?.run_id||row.owned_runs?.[0]?.run_id;
      const summary=result.summary||result.message||row.result_label||row.summary_text||resultText(result);
      const reason=error.label||error.message||row.reason_label||row.reason_code||error.code||'';
      return `<tr><td class="bulk-target-check" data-label="选择"><input type="checkbox" data-bulk-target="${attrEsc(id)}" ${state.selected.has(id)?'checked':''} aria-label="选择账号 ${attrEsc(display.email||row.account_id||id)}"></td><td class="bulk-target-account" data-label="账号"><strong>${text(display.email||row.email||`账号 #${row.account_id||display.account_id||id}`)}</strong><small>#${text(row.account_id||display.account_id||display.id||row.entity_id||id)}</small></td><td class="bulk-target-state" data-label="结果 / 阶段">${badge(row.state||row.outcome||row.status)}<small>${text(row.stage_label||row.current_stage_label||row.stage||'')}</small></td><td class="bulk-target-summary" data-label="结果摘要">${text(summary||'等待本轮结果')}${result.capabilities?`<details><summary>分项结果</summary>${Object.entries(result.capabilities).map(([k,v])=>`<p>${text(operationLabel(k))}：${text(label(v.state||v.status))}</p>`).join('')}</details>`:''}</td><td class="bulk-target-reason" data-label="错误分类">${reason?`<details><summary>${text(short(reason,60))}</summary><p class="bulk-error-detail">${text(error.message||row.error_message||reason)}</p><small>${text(error.code||row.reason_code)}</small></details>`:'—'}</td><td class="bulk-target-actions" data-label="操作">${taskId?`<button type="button" class="jobs-tb-btn" data-bulk-task="${attrEsc(taskId)}" data-bulk-run="${attrEsc(runId||'')}">查看执行</button>`:'尚未创建执行'}${row.blocker_task_id?`<button class="bulk-link" data-bulk-task="${attrEsc(row.blocker_task_id)}">查看占用任务（其他执行）</button>`:''}</td></tr>`;
    }).join('')}</tbody></table>`:'<div class="bulk-empty">当前条件下没有目标。更改结果筛选不会改变本批固定名单。</div>');
    if(focused)Array.from(host.querySelectorAll('[data-bulk-target]')).find(x=>x.dataset.bulkTarget===focused)?.focus({preventScroll:true});
    const pageBox=$b('[data-bulk-select-page]');if(pageBox){pageBox.checked=Boolean(rows.length)&&selectedCount===rows.length;pageBox.indeterminate=selectedCount>0&&selectedCount<rows.length;}
    $b('[data-bulk-action="target-prev"]').disabled=!state.targetPrev.length;
    $b('[data-bulk-action="target-next"]').disabled=!state.targets?.next_cursor;
    $b('[data-target-page]').textContent=`第 ${state.targetPrev.length+1} 页 · 本页 ${rows.length} 个`;
    updateSelected();
  }
  function updateSelected() {
    const count=state.selected.size;
    $b('[data-bulk-selected]').textContent=count?`已选 ${count} 个（可跨页）`:'';
    const clear=$b('[data-bulk-action="clear-selection"]');if(clear){clear.hidden=!count;clear.disabled=!count;}
    const button=$b('[data-bulk-action="retry-selected"]');if(button){button.disabled=!count;button.hidden=!count;button.textContent=count?`重跑勾选 (${count})`:'重跑勾选';}
  }
  function updateRetryButton() {
    const select=$b('[data-bulk-retry-states]');const button=$b('[data-bulk-action="retry"]');if(!select||!button||!state.detail)return;
    const choice=select.value||'failed';const states=choice==='unsuccessful'?['failed','partial_success','attention_required','not_executed','cancelled']:[choice];
    const counts=state.detail.summary||state.detail.counts||{};const amount=states.reduce((sum,key)=>sum+Number(counts[key]||0),0);
    button.textContent=`重跑${select.selectedOptions[0]?.textContent||'失败'}${amount?` (${amount})`:''}`;button.disabled=!amount;
  }
  async function retry(selected=false, targetIds=null) {
    if(!state.detail)return;const button=$b(`[data-bulk-action="${selected?'retry-selected':'retry'}"]`);if(button?.disabled)return;if(button)button.disabled=true;clearError();
    const choice=$b('[data-bulk-retry-states]')?.value||'failed';
    const states=choice==='unsuccessful'?['failed','partial_success','attention_required','not_executed','cancelled']:[choice];
    const counts=state.detail.summary||state.detail.counts||{};
    const amount=selected?state.selected.size:states.reduce((sum,key)=>sum+Number(counts[key]||0),0);
    if(amount>=10||choice==='unsuccessful'){
      const ok=await confirmAction({title:'确认重跑',body:`将在当前批次下新建一轮，重跑 ${amount} 个账号；不会覆盖历史轮次。`,items:[`范围：${state.nav.round_id?'当前轮':'当前结果'}`,`预计账号：${amount} 个`],confirm:`重跑 ${amount} 个`});
      if(!ok){if(button)button.disabled=false;return;}
    }
    const body={source:{view:state.nav.round_id?'round':'current',round_id:state.nav.round_id||null,observed_summary_revision:state.detail.summary_revision,observed_target_count:amount},selection:selected?{kind:'targets',target_ids:targetIds||[...state.selected]}:{kind:'result_filter',states},retry_mode:'automatic'};
    try{const result=await intent(`retry:${state.nav.batch_id}`,`/batches/${encodeURIComponent(state.nav.batch_id)}/rounds`,body);state.pendingRound=String(result.round_id||result.id);notice('重跑已受理，正在按固定时点的结果准备新轮次。');state.selected.clear();await loadDetail(true);schedule();}
    catch(e){report(e,'重跑失败：');}finally{if(button?.isConnected)button.disabled=false;updateSelected();updateRetryButton();}
  }
  async function control(action) {
    if(!state.detail)return;const element=$b(`[data-bulk-action="${action==='request_stop'?'stop':'cancel'}"]`);if(element?.disabled)return;
    const counts=state.detail.summary||state.detail.counts||{};
    const stop=action==='request_stop';
    const affected=stop?Number(counts.running||0)+Number(counts.waiting||0):Number(counts.pending_submit||0)+Number(counts.waiting_account||0)+Number(counts.queued||0)+Number(counts.waiting||0);
    const scope=state.nav.round_id?'当前轮':'整个批次';
    const ok=await confirmAction({title:stop?'停止正在执行':'取消排队账号',body:stop?'已开始执行的账号会收到协作停止请求，正在收尾的步骤会完成，不会立即强制中断。':'尚未开始的目标会取消；已开始账号链的必要步骤会继续收尾。',items:[`范围：${scope}`,`预计影响：${affected} 个账号`],confirm:stop?'停止执行':'取消排队'});
    if(!ok){if(element)element.disabled=false;return;}
    if(element)element.disabled=true;clearError();
    const body={action,expected_control_revision:state.detail.control?.revision??state.detail.control_revision,scope:state.nav.round_id?{kind:'round',round_id:state.nav.round_id}:{kind:'batch'}};
    try{await intent(`control:${state.nav.batch_id}:${action}`,`/batches/${encodeURIComponent(state.nav.batch_id)}/control`,body);notice(stop?'停止请求已受理；未开始目标将取消，已开始执行正在协作收尾。':'取消请求已受理；已开始账号链的必要步骤继续收尾。');await loadDetail(true);schedule();}
    catch(e){report(e,'控制失败：');if(['control_revision_conflict','control_revision_changed'].includes(e.code))await loadDetail(false);else if(element)element.disabled=false;}
  }
  function fromAccounts(selected=false, operationKey='plan_check') {
    const ids=selected?Array.from(ACCOUNT_SELECTED).map(String):null;
    if(selected&&!ids.length){showToast('请先选择账号');return;}
    state.draft={...defaultDraft(),operation_key:operationKey,query:AccountQuery.fromAccountList(),source:selected?{kind:'ids',entity:'account',ids}:null};state.selection=null;saveSelection();saveDraft();navigate('create');
  }
  function copyBatch(fixed) {
    const data=state.detail;if(!data)return;
    const query=data.selection_summary?.query||data.query_spec||data.selection?.query_spec||{};
    state.draft={...defaultDraft(),operation_key:data.operation?.key||data.operation_key||data.action_key||'plan_check',query:AccountQuery.normalize(query),parameters:data.parameters||{},source:fixed?{kind:'batch_targets',batch_id:state.nav.batch_id,selection:{kind:'all'}}:null};state.selection=null;saveSelection();saveDraft();navigate('create');
  }
  async function action(name) {
    if(name==='recover')await recover();
    else if(name==='new'){state.draft=defaultDraft();state.selection=null;saveSelection();saveDraft();navigate('create');}
    else if(name==='list')navigate('list');
    else if(name==='refresh'){clearError();if(state.nav.view==='list')await loadList(true);else if(state.nav.view==='detail')await loadDetail(true);else{await ensureCatalog(true);renderCreate();if(state.selection)await pollSelection();scheduleFacets();}}
    else if(name==='preview')await preview();
    else if(name==='all-results')updateNavigation({result_state:'',cursor:''});
    else if(name==='clear-filters'||name==='use-query'){state.draft.query=AccountQuery.normalize();state.draft.source=null;state.draft.limit='';invalidateSelection();saveDraft();renderCreate();scheduleFacets();}
    else if(name==='reset-filters'){state.nav={...state.nav,q:'',operation:'',state:'',created_from:'',created_to:'',cursor:''};state.listCursor='';state.listPrev=[];recordNavigationHistory('replace');renderListShell();void loadList(true);}
    else if(name==='list-next'&&state.list?.next_cursor){state.listPrev.push(state.listCursor);state.listCursor=state.list.next_cursor;state.nav.cursor=state.listCursor;recordNavigationHistory('replace');await loadList(true);}
    else if(name==='list-prev'){state.listCursor=state.listPrev.pop()||'';state.nav.cursor=state.listCursor;recordNavigationHistory('replace');await loadList(true);}
    else if(name==='target-next'&&state.targets?.next_cursor){state.epoch++;state.loading=false;state.targetPrev.push(state.nav.cursor||'');state.nav.cursor=state.targets.next_cursor;recordNavigationHistory('replace');await loadTargets();}
    else if(name==='target-prev'){state.epoch++;state.loading=false;state.nav.cursor=state.targetPrev.pop()||'';recordNavigationHistory('replace');await loadTargets();}
    else if(name==='preview-next'&&state.selection?.next_cursor){state.previewPrev.push(state.previewCursor);state.previewCursor=state.selection.next_cursor;await pollSelection();}
    else if(name==='preview-prev'){state.previewCursor=state.previewPrev.pop()||'';await pollSelection();}
    else if(name==='clear-selection'){state.selected.clear();renderTargets();updateSelected();}
    else if(name==='retry')await retry();
    else if(name==='retry-selected')await retry(true);
    else if(name==='cancel')await control('cancel_not_started');
    else if(name==='stop')await control('request_stop');
    else if(name==='copy-query')copyBatch(false);
    else if(name==='copy-targets')copyBatch(true);
    else if(name==='more-rounds'){const data=await request(`/batches/${encodeURIComponent(state.nav.batch_id)}/rounds?cursor=${encodeURIComponent(state.roundsCursor)}`);const merged=new Map(state.rounds.map(round=>[String(round.id),round]));(data.items||[]).forEach(round=>merged.set(String(round.id),round));state.rounds=[...merged.values()].sort((a,b)=>Number(b.round_no)-Number(a.round_no));state.roundsCursor=data.next_cursor??data.page?.next_cursor??'';state.detail.rounds_next_cursor=state.roundsCursor;renderDetail();}
  }
  document.getElementById('tab-bulk')?.addEventListener('click',event=>{
    const button=event.target.closest('button');if(!button||button.disabled)return;
    if(button.hasAttribute('data-bulk-close-popover')){const details=button.closest('details');details.open=false;details.querySelector('summary').focus({preventScroll:true});return;}
    if(button.dataset.bulkAction){event.preventDefault();Promise.resolve(action(button.dataset.bulkAction)).catch(e=>report(e));}
    else if(button.dataset.bulkOpen)navigate('detail',{batch_id:button.dataset.bulkOpen,result_state:button.dataset.resultState||''});
    else if(button.dataset.bulkStat)updateNavigation({result_state:state.nav.result_state===button.dataset.bulkStat?'':button.dataset.bulkStat,cursor:''});
    else if(button.dataset.bulkTask)openAccountTaskLog(button.dataset.bulkTask,button.dataset.bulkRun||null);
  });
  document.getElementById('tab-bulk')?.addEventListener('keydown',event=>{
    if(event.key!=='Escape')return;
    const open=$b('.bulk-filter-popover[open], .bulk-menu[open], .bulk-more-states[open]');
    if(open){open.open=false;open.querySelector('summary').focus({preventScroll:true});}
  });
  document.getElementById('tab-bulk')?.addEventListener('submit',event=>{
    event.preventDefault();const form=event.target;
    if(form.matches('[data-bulk-create-form]'))void createBatch();
    if(form.matches('[data-bulk-list-form]')){const values=Object.fromEntries(new FormData(form));state.nav={tab:'bulk',view:'list',...values};state.epoch++;state.loading=false;state.listCursor='';state.listPrev=[];recordNavigationHistory('push');void loadList(true);}
    if(form.matches('[data-bulk-results-form]')){const values=Object.fromEntries(new FormData(form));updateNavigation({result_state:values.state,q:values.q,reason_code:values.reason_code,cursor:''});}
  });
  document.getElementById('tab-bulk')?.addEventListener('input',event=>{
    if(!event.target.closest('[data-bulk-create-form]'))return;
    const input=event.target;if(!input.name&&!input.dataset.bulkParameter)return;
    if(input.dataset.bulkParameter){const name=input.dataset.bulkParameter;state.draft.parameters[name]=input.type==='checkbox'?input.checked:input.type==='number'?Number(input.value):input.value;if(input.value==='')delete state.draft.parameters[name];invalidateSelection();}
    else if(['name','max_concurrency','limit'].includes(input.name)){state.draft[input.name]=input.value;if(input.name==='limit')invalidateSelection();}
    renderSideSummary();
    saveDraft();
  });
  document.getElementById('tab-bulk')?.addEventListener('change',event=>{
    const input=event.target;
    if(input.name==='operation_key'){state.draft.operation_key=input.value;state.draft.parameters={};invalidateSelection();saveDraft();renderParameters();renderSideSummary();}
    if(input.matches('[data-bulk-retry-states]'))updateRetryButton();
    if(input.matches('[data-bulk-view]'))updateNavigation({round_id:input.value==='current'?'':input.value,cursor:''});
    if(input.dataset.bulkTarget){if(input.checked)state.selected.add(input.dataset.bulkTarget);else state.selected.delete(input.dataset.bulkTarget);updateSelected();}
    if(input.matches('[data-bulk-select-page]')){for(const row of state.targets?.items||[]){if(input.checked)state.selected.add(targetId(row));else state.selected.delete(targetId(row));}renderTargets();}
  });
  document.querySelectorAll('[data-bulk-nav]').forEach(button=>button.addEventListener('click',()=>{if(button.dataset.bulkNav==='create'){state.draft ||= defaultDraft();}navigate(button.dataset.bulkNav);}));
  document.addEventListener('visibilitychange',()=>{clearTimeout(state.timer);if(visible()){if(state.nav.view==='list')void loadList(true);else if(state.nav.view==='detail')void loadDetail(true);else if(state.selection)void pollSelection();schedule();}});
  return {activate,navigationState,restoreNavigation,navigate,fromAccounts,request,intent,restoreSelectionRequest};
})();
