// Vue 页面负责状态、草稿、提交和轮询；此适配层负责加载、导航及加载失败后的只读展示。
window.BulkTasks = (() => {
  if (window.BulkTasks?.isVueOwner) return window.BulkTasks;
  let instance = null, loading = null, visible = false, generation = 0, drainingAccounts = null, fallback = null, fallbackReport = null;
  let navigation = {tab:'bulk',view:'list'}, pendingAccounts = null;
  const clone = value => JSON.parse(JSON.stringify(value));
  function normalize(raw = {}) {
    const nav = {tab:'bulk',view:['list','create','detail'].includes(raw.view)?raw.view:'list'};
    for (const key of ['batch_id','round_id','result_state','cursor','q','operation','state','created_from','created_to']) {
      if (typeof raw[key] === 'string' && raw[key]) nav[key] = raw[key];
    }
    if (nav.view === 'detail') {
      if (!/^[1-9]\d*$/.test(nav.batch_id || '')) return {tab:'bulk',view:'list'};
      if (nav.q || raw.reason_code) {delete nav.q; delete nav.cursor;}
      if (['attention_required','request_unknown','manual_reconcile','unknown','unconfirmed'].includes(nav.result_state)) nav.result_state = 'failed';
    }
    return nav;
  }
  function syncSidebar() {
    document.querySelectorAll('[data-bulk-nav]').forEach(button => button.classList.toggle('is-active', button.dataset.bulkNav === navigation.view));
  }
  function isVisible() {return visible && !document.hidden && !document.getElementById('tab-bulk')?.classList.contains('hidden');}
  function report(error) {showToast(`批量任务加载失败：${error.message || error}`);}
  const operationNames = {plan_check:'查询套餐',token_refresh:'刷新 AT',password_setup:'补密码',twofa_setup:'补 2FA',codex_retry:'补 Codex',account_completion:'组合补全'};
  function node(tag, text, attrs = {}) {
    const element = document.createElement(tag);
    if (text != null) element.textContent = String(text);
    for (const [key,value] of Object.entries(attrs)) element.setAttribute(key,String(value));
    return element;
  }
  function fallbackButton(text, action, value = '') {
    return node('button',text,{type:'button',class:'jobs-tb-btn','data-bulk-fallback-action':action,'data-value':value});
  }
  function closeFallbackReport(restoreFocus = true) {
    const owner = fallbackReport;if (!owner) return;
    fallbackReport = null;owner.controller.abort();
    if (owner.dialog.open) owner.dialog.close();
    owner.dialog.remove();
    if (restoreFocus && isVisible() && owner.opener?.isConnected && !owner.opener.disabled) owner.opener.focus({preventScroll:true});
  }
  function clearFallback() {
    closeFallbackReport(false);
    if (!fallback) return;
    fallback.controller?.abort();fallback.root.removeEventListener('click',fallback.click);fallback = null;
  }
  async function fallbackRequest(path, signal) {
    const response = await fetch(`/api/bulk${path}`,{method:'GET',credentials:'same-origin',signal});
    const payload = await response.json();
    if (!response.ok || payload.ok === false) {
      const detail = typeof payload.error === 'object' && payload.error ? payload.error : payload;
      throw new Error(detail.message || (typeof payload.error === 'string' ? payload.error : '') || `请求失败（HTTP ${response.status}）`);
    }
    return payload.data ?? payload;
  }
  function fallbackListQuery() {
    const query = new URLSearchParams({page_size:'20'});
    for (const key of ['cursor','q']) if (navigation[key]) query.set(key,navigation[key]);
    if (navigation.operation) query.set('operation_key[]',navigation.operation);
    if (navigation.state) query.set('control_state[]',navigation.state);
    for (const key of ['created_from','created_to']) {
      if (!navigation[key]) continue;
      const value = navigation[key], date = new Date(`${value}T00:00:00`);
      const [year,month,day] = value.split('-').map(Number);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || date.getFullYear() !== year || date.getMonth()+1 !== month || date.getDate() !== day) throw new Error('创建日期无效，请调整筛选条件');
      if (key === 'created_to') date.setDate(date.getDate()+1);
      query.set(key === 'created_to' ? 'created_before' : key,date.toISOString());
    }
    return query;
  }
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  function fallbackBusinessMarkup(metrics,expanded=false) {
    metrics={...metrics};
    if(Object.prototype.hasOwnProperty.call(metrics,'account.token_refresh.unconfirmed')){
      metrics['account.token_refresh.failed']=Number(metrics['account.token_refresh.failed']||0)+Number(metrics['account.token_refresh.unconfirmed']||0);
      delete metrics['account.token_refresh.unconfirmed'];
    }
    const names={'account.confirmed_no_offer':'本次确认无优惠','account.plan.free':'套餐 · Free','account.plan.plus':'套餐 · Plus','account.plan.pro':'套餐 · Pro','account.plan.team':'套餐 · Team','account.plan.go':'套餐 · Go',confirmed_no_offer_accounts:'本次确认无优惠',no_offer:'无优惠',free_trial:'免费试用',half_price:'半价优惠',other_discount:'其他折扣',success:'成功',failed:'失败',partial_success:'部分成功',confirmed:'已确认',newly_set:'新设置',already_set:'验证已有密码',newly_enabled:'新启用',already_satisfied:'原本已满足',usable_credential:'可用凭证',credential_pending_confirmation:'凭证缺失',confirmed_accounts:'已确认账号',country_success:'查询成功',country_failed:'查询失败','country_query.success':'国家项查询成功','country_query.failed':'国家项查询失败',plan:'套餐',plans:'套餐分布',promotion:'优惠',promotions:'优惠分布',countries:'国家项',password:'密码',twofa:'2FA',codex:'Codex',access_token:'AT',plan_check:'套餐查询',free:'Free',plus:'Plus',team:'Team',pro:'Pro',unknown:'记录缺失',none:'无优惠',not_executed:'未执行',attention_required:'失败',pending:'待执行'};
    for(const [kind,name]of Object.entries({none:'无优惠',free_trial:'免费试用',half_price:'半价优惠',other_discount:'其他折扣',discount:'折扣优惠',other_promo:'其他优惠'}))names[`account.plus_offer.${kind}`]=`优惠 · ${name}`;
    for(const [kind,name]of Object.entries({unchanged:'优惠未变化',new_offer:'新增优惠',offer_removed:'优惠消失',changed:'优惠变化',not_comparable:'历史条件不可比较'}))names[`account.comparison.${kind}`]=name;
    Object.assign(names,{'account.password_setup.confirmed':'密码已确认','account.twofa_setup.confirmed':'2FA 已确认','account.codex.credential_confirmed':'Codex 凭证已确认','account.token_refresh.confirmed':'AT 刷新成功','account.token_refresh.unconfirmed':'AT 刷新失败','account.token_refresh.failed':'AT 刷新失败'});
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
    const content=`<div class="bulk-business-groups">${[...groups].map(([name,rows])=>`<section class="bulk-business-group"><h4>${escape(name)} · ${name==='国家查询项'?'项':'账号数'}</h4><dl class="bulk-business-metrics">${rows.map(([title,value])=>`<div><dt>${escape(title)}</dt><dd>${value}</dd></div>`).join('')}</dl></section>`).join('')}</div>`;
    return groups.size?(expanded?content:`<details class="bulk-business-details"><summary>功能统计<span>展开查看</span></summary>${content}</details>`):'';
  }
  async function showFallbackReport(batchId, opener) {
    const fallbackOwner = fallback;
    if (!fallbackOwner || !isVisible() || !/^[1-9]\d*$/.test(batchId || '')) return;
    closeFallbackReport(false);
    const controller = new AbortController(), nav = JSON.stringify(navigation);
    const dialog = node('dialog',null,{class:'bulk-fallback-report-dialog','data-bulk-report-dialog':'','aria-labelledby':'bulk-fallback-report-title'});
    const styles = node('style',`
      .bulk-fallback-report-dialog{position:fixed;inset:24px;flex-direction:column;width:calc(100% - 48px);max-width:1280px;height:min(900px,calc(100dvh - 48px));max-height:calc(100dvh - 48px);margin:auto;padding:0;overflow:hidden;border:1px solid var(--ui-color-border-strong);border-radius:var(--ui-radius-lg);background:var(--ui-color-surface-subtle);color:var(--ui-color-text);font-family:var(--ui-font-sans);box-shadow:var(--ui-shadow-lg);box-sizing:border-box}
      .bulk-fallback-report-dialog[open]{display:flex}.bulk-fallback-report-dialog::backdrop{background:color-mix(in srgb,var(--ui-color-text) 38%,transparent)}
      .bulk-fallback-report-heading{display:flex;align-items:center;justify-content:space-between;flex:none;gap:16px;padding:16px 20px;border-bottom:1px solid var(--ui-color-border);background:var(--ui-color-surface)}
      .bulk-fallback-report-heading h2{margin:0;font-size:18px;overflow-wrap:anywhere}.bulk-fallback-report-body{flex:1;min-height:0;overflow:auto;padding:16px;overscroll-behavior:contain}
      @media(max-width:680px){.bulk-fallback-report-dialog{inset:8px;width:calc(100% - 16px);height:calc(100dvh - 16px);max-height:calc(100dvh - 16px)}.bulk-fallback-report-heading{padding:12px}.bulk-fallback-report-body{padding:10px}}
    `);
    const heading = node('header',null,{class:'bulk-fallback-report-heading'});
    const title = node('h2',`批次 #${batchId} 报告`,{id:'bulk-fallback-report-title'});
    const close = node('button','关闭报告',{type:'button',class:'jobs-tb-btn','data-bulk-report-close':''});
    const content = node('section','正在读取报告…',{class:'bulk-fallback-report-body','data-bulk-plan-report':'',tabindex:'-1',role:'region','aria-label':'批次报告','aria-busy':'true'});
    heading.append(title,close);dialog.append(styles,heading,content);
    const owner = {dialog,controller,opener};fallbackReport = owner;
    const current = () => fallbackReport === owner && fallback === fallbackOwner && !controller.signal.aborted && isVisible() && JSON.stringify(navigation) === nav;
    close.addEventListener('click',() => closeFallbackReport());
    dialog.addEventListener('cancel',event => {event.preventDefault();closeFallbackReport();});
    dialog.addEventListener('close',() => {if (fallbackReport === owner) closeFallbackReport();});
    dialog.addEventListener('click',event => {
      if (event.target !== dialog) return;
      const rect = dialog.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeFallbackReport();
    });
    document.body.append(dialog);dialog.showModal();close.focus({preventScroll:true});
    try {
      const query = new URLSearchParams({view:'current'});
      const detail = await fallbackRequest(`/batches/${batchId}?${query}`,controller.signal);
      if (!current()) return;
      title.textContent = `${detail.name || detail.title || `批次 #${batchId}`} · 报告`;
      const operation = detail.operation?.key || detail.operation_key || detail.action_key;
      if (!Object.hasOwn(operationNames,operation)) {content.textContent = '此操作暂无报告。';return;}
      const data = await fallbackRequest(`/batches/${batchId}/report?${query}`,controller.signal);
      if (!current()) return;
      if (!window.BulkPlanReport) throw new Error('报告组件未加载，请重试加载');
      content.innerHTML = window.BulkPlanReport.render(data,fallbackBusinessMarkup(data.business_summary || {},true));
      content.focus({preventScroll:true});
    } catch (error) {
      if (current()) {content.textContent = `读取报告失败：${error.message || error}`;content.setAttribute('role','alert');}
    } finally {
      if (current()) content.setAttribute('aria-busy','false');
    }
  }
  async function refreshFallback() {
    const owner = fallback;
    if (!owner || !isVisible()) return;
    owner.controller?.abort();
    const controller = new AbortController(), nav = clone(navigation);
    owner.controller = controller;owner.status.textContent = '正在读取…';
    const current = () => fallback === owner && !controller.signal.aborted && JSON.stringify(navigation) === JSON.stringify(nav);
    try {
      if (nav.view === 'create') {owner.status.textContent = '新建页面暂时无法加载，请重试加载。';return;}
      if (nav.view === 'detail') {
        const query = new URLSearchParams({view:nav.round_id?'round':'current'});
        if (nav.round_id) query.set('round_id',nav.round_id);
        const detail = await fallbackRequest(`/batches/${nav.batch_id}?${query}`,controller.signal);
        if (!current()) return;
        const operation = detail.operation?.key || detail.operation_key || detail.action_key;
        if (!Object.hasOwn(operationNames,operation)) {owner.content.replaceChildren(node('p','此操作暂无报告。'));owner.status.textContent = '';return;}
        const data = await fallbackRequest(`/batches/${nav.batch_id}/report?${query}`,controller.signal);
        if (!current()) return;
        if (!window.BulkPlanReport) throw new Error('报告组件未加载，请重试加载');
        const host = node('div',null,{'data-bulk-plan-report':'',tabindex:'-1',role:'region','aria-label':'批次报告'});
        host.innerHTML = window.BulkPlanReport.render(data,fallbackBusinessMarkup(data.business_summary || {},true));
        owner.content.replaceChildren(host);owner.status.textContent = '';
        host.focus({preventScroll:true});
      } else {
        const data = await fallbackRequest(`/batches?${fallbackListQuery()}`,controller.signal);
        if (!current()) return;
        if (!Array.isArray(data.items)) throw new Error('批次列表响应格式无效');
        const list = node('div',null,{class:'bulk-card'});
        for (const row of data.items) {
          const id = Number.isSafeInteger(row?.id) ? String(row.id) : row?.id;
          if (typeof id !== 'string' || !/^[1-9]\d*$/.test(id)) throw new Error('批次编号无效');
          const item = node('div',null,{class:'bulk-actions','data-bulk-row':id});
          item.append(node('span',`${row.name || row.title || '批次'} · #${id}`),fallbackButton('查看报告','report',id));list.append(item);
        }
        if (!data.items.length) list.append(node('p','没有匹配的批次。'));
        const cursor = data.next_cursor ?? data.page?.next_cursor;
        if (cursor != null && typeof cursor !== 'string') throw new Error('批次分页响应格式无效');
        const pager = node('nav',null,{'aria-label':'批次分页'});
        if (nav.cursor) pager.append(fallbackButton('返回首页','first'));
        if (cursor) pager.append(fallbackButton('下一页','next',cursor));
        const total = data.summary?.total_batches;
        owner.status.textContent = typeof total === 'number' && Number.isFinite(total) && total >= 0 ? `${total} 个批次` : `本页 ${data.items.length} 个批次`;
        owner.content.replaceChildren(list,pager);
      }
    } catch (error) {
      if (current()) {owner.status.textContent = error.message || String(error);owner.status.setAttribute('role','alert');}
    }
  }
  async function renderFallback(root, error) {
    clearFallback();root.replaceChildren();
    const status = node('p','',{role:'status'}),content = node('div');
    const actions = node('div',null,{class:'bulk-actions'});
    actions.append(fallbackButton('批次列表','list'),fallbackButton('刷新只读内容','refresh'),fallbackButton('重试加载','load'));
    root.append(node('h2','批量任务'),node('p',`页面组件加载失败，暂时展示只读内容：${error.message || error}`,{class:'bulk-notice'}),actions,status,content);
    root.setAttribute('data-bulk-fallback','');
    const owner = {root,status,content,controller:null,click(event) {
      const button = event.target.closest?.('[data-bulk-fallback-action]');
      if (!button || !root.contains(button)) return;
      const action = button.dataset.bulkFallbackAction;
      if (action === 'refresh') {status.setAttribute('role','status');void refreshFallback();}
      else if (action === 'load') void activate();
      else if (action === 'list') void navigate('list');
      else if (action === 'report') void showFallbackReport(button.dataset.value,button);
      else if (action === 'first' || action === 'next') void navigate('list',{...navigation,cursor:action === 'first' ? '' : button.dataset.value});
    }};
    fallback = owner;root.addEventListener('click',owner.click);await refreshFallback();
  }
  async function drainAccounts(api) {
    if (drainingAccounts) return drainingAccounts;
    const request = pendingAccounts;
    if (!request || request.generation !== generation || !isVisible()) return;
    const drain = Promise.resolve().then(() => {
      if (request !== pendingAccounts || request.generation !== generation || !isVisible()) return;
      return api.fromAccounts(request.selected, request.operationKey, request.snapshot);
    }).then(() => {if (pendingAccounts === request) pendingAccounts = null;});
    drainingAccounts = drain;
    try {await drain;} finally {if (drainingAccounts === drain) drainingAccounts = null;}
  }
  async function ensure() {
    if (instance) {await drainAccounts(instance); return instance;}
    if (!loading) {
      const root = document.getElementById('bulk-page-root');
      loading = (async () => {
        if (!root) throw new Error('找不到批量任务挂载位置');
        if (!document.getElementById('task-center-style')) {
          const style = document.createElement('link');style.id = 'task-center-style';style.rel = 'stylesheet';style.href = root.dataset.styleUrl;document.head.append(style);
        }
        const module = await import(root.dataset.moduleUrl);
        if (typeof module.mountBulk !== 'function') throw new Error('页面组件版本不匹配，请重新加载');
        clearFallback();root.removeAttribute('data-bulk-fallback');
        instance = module.mountBulk(root, {
          query: window.AccountQuery, navigation, isVisible,
          callbacks: {
            navigate() {}, updateNavigation() {}, notify: message => showToast(message),
            formatDateTime: value => value ? formatDateTime(value) : '—',
            facetLabel: (group,value) => facetLabel(group,value),
            openTask: (taskId,runId) => openAccountTaskLog(taskId,runId || null),
          },
          onNavigation: (nav,mode) => {
            navigation = {...nav};syncSidebar();visible = true;
            activateTab('bulk',true,'none');recordNavigationHistory(mode);
          },
        });
        instance.setVisible(isVisible());
        return instance;
      })().catch(async error => {
        loading = null;
        if (root) await renderFallback(root,error);
        throw error;
      });
    }
    const api = await loading;await drainAccounts(api);return api;
  }
  async function activate() {
    closeFallbackReport(false);
    visible = true;syncSidebar();
    try {const api = await ensure();if (isVisible()) await api.activate();else api.setVisible(false);}
    catch (error) {report(error);}
  }
  function navigationState() {return instance ? instance.navigationState() : {...navigation};}
  function restoreNavigation(raw) {closeFallbackReport(false);generation++;pendingAccounts = null;navigation = normalize(raw);instance?.restoreNavigation(navigation);syncSidebar();}
  async function navigate(view,extra = {},focusReport = false) {
    restoreNavigation({tab:'bulk',view,...extra});const ticket = generation;visible = true;
    activateTab('bulk',true,'none');recordNavigationHistory('push');
    try {
      const api = await ensure();
      if (ticket !== generation || !isVisible()) return;
      await api.activate();
      if (focusReport && ticket === generation && isVisible()) await api.showReport();
    }
    catch (error) {report(error);}
  }
  async function fromAccounts(selected = false,operationKey = 'plan_check',snapshot = null) {
    const owner = window.AccountsPage?.isReady?.() ? window.AccountsPage : null;
    const captured = snapshot || owner?.getAccountSelectionSnapshot();
    if (!captured) {showToast('账号范围未就绪，请返回账号页重试');return;}
    if (selected && !captured.ids?.length) {showToast('请先选择账号');return;}
    closeFallbackReport(false);
    generation++;
    pendingAccounts = {selected,operationKey,snapshot:clone(captured),generation};
    navigation = {tab:'bulk',view:'create'};visible = true;syncSidebar();
    activateTab('bulk',true,'none');
    try {await ensure();} catch (error) {report(error);}
  }
  document.querySelectorAll('[data-bulk-nav]').forEach(button => button.addEventListener('click',() => void navigate(button.dataset.bulkNav)));
  document.addEventListener('visibilitychange',() => {if (!isVisible()) closeFallbackReport(false);});
  return {
    isVueOwner:true,
    activate,navigationState,restoreNavigation,navigate,fromAccounts,
    setVisible(value) {const next = Boolean(value);if (!next) closeFallbackReport(false);if (!next && visible) {generation++;pendingAccounts = null;fallback?.controller?.abort();}visible = next;instance?.setVisible(isVisible());},
    async request(path,options) {return (await ensure()).request(path,options);},
    async intent(scope,path,body) {return (await ensure()).intent(scope,path,body);},
    async restoreSelectionRequest(body,result) {return (await ensure()).restoreSelectionRequest(body,result);},
  };
})();
