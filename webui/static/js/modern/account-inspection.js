// 巡检弹窗：依赖 common.js、accounts.js 的账号状态及 account-tasks.js 的任务详情入口。
// 巡检使用原生 dialog 的焦点约束；阅读原始 Run 快照，不覆盖任务中心重跑历史。
let accountInspectionPage = 1;
let accountInspectionFailurePage = 1;
let accountInspectionFailureId = null;
let accountInspectionActive = false;
let accountInspectionStarting = false;
let accountInspectionRequestKey = null;
let accountInspectionHistoryVersion = 0;
let accountInspectionFailureVersion = 0;
const accountInspectionLoading = {history: false, failures: false};
const accountInspectionFocus = new Map();
function accountInspectionScope() { return SHOW_ARCHIVED_ACCOUNTS ? 'only' : '0'; }
function accountInspectionScopeLabel(scope) { return scope === 'only' ? '已归档账号' : scope === 'all' ? '全部账号' : '未归档账号'; }
function showAccountInspectionDialog(id) {
  const dialog = document.getElementById(id);
  if (!dialog || dialog.open) return;
  accountInspectionFocus.set(id, document.activeElement);
  dialog.showModal();
}
function closeAccountInspectionDialog(id) { document.getElementById(id)?.close(); }
['accountInspectionStart', 'accountInspectionHistory', 'accountInspectionFailures'].forEach(id => {
  document.getElementById(id)?.addEventListener('close', () => {
    const trigger = accountInspectionFocus.get(id);
    if (trigger?.isConnected) trigger.focus({preventScroll: true});
    else {
      // 历史自动刷新可能替换原按钮；关闭详情后把焦点留在仍打开的父弹窗。
      const parent = document.getElementById('accountInspectionHistory');
      const fallback = parent?.open ? parent.querySelector('button:not([disabled])') : document.getElementById('btnAccountInspection');
      fallback?.focus({preventScroll: true});
    }
    accountInspectionFocus.delete(id);
  });
});
async function accountInspectionRequest(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);
  try { return await api(url, {...options, signal: controller.signal}); }
  finally { clearTimeout(timeout); }
}
function openAccountInspectionStart() {
  const dialog = document.getElementById('accountInspectionStart');
  dialog.dataset.archived = accountInspectionScope();
  document.getElementById('accountInspectionScope').textContent = `本次范围：${accountInspectionScopeLabel(dialog.dataset.archived)}`;
  document.getElementById('accountInspectionWorkers').value = Math.min(16, getAccountOperationWorkers());
  document.getElementById('accountInspectionStartError').textContent = '';
  showAccountInspectionDialog('accountInspectionStart');
}
async function submitAccountInspection(event) {
  event.preventDefault();
  if (accountInspectionStarting) return;
  const workers = Number(document.getElementById('accountInspectionWorkers').value);
  if (!Number.isInteger(workers) || workers < 1 || workers > 16) return;
  accountInspectionStarting = true;
  const button = document.getElementById('btnConfirmAccountInspection');
  button.disabled = true;
  accountInspectionRequestKey ||= crypto.randomUUID();
  try {
    const result = await accountInspectionRequest('/api/accounts/inspections', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
      workers, archived: document.getElementById('accountInspectionStart').dataset.archived, idempotency_key: accountInspectionRequestKey,
    })});
    accountInspectionRequestKey = null;
    accountInspectionActive = true;
    closeAccountInspectionDialog('accountInspectionStart');
    showToast(result.created ? '巡检已加入统一任务队列' : '已有本次巡检记录，已打开历史');
    openAccountInspectionHistory();
  } catch (error) {
    document.getElementById('accountInspectionStartError').textContent = `启动结果待确认：${error.message}。可查看巡检历史，或使用当前提交再次确认。`;
  } finally { accountInspectionStarting = false; button.disabled = false; }
}
function openAccountInspectionHistory() {
  accountInspectionPage = 1;
  showAccountInspectionDialog('accountInspectionHistory');
  void refreshAccountInspectionHistory();
}
function changeAccountInspectionPage(delta) {
  if (accountInspectionLoading.history) return;
  accountInspectionPage = Math.max(1, accountInspectionPage + delta);
  accountInspectionHistoryVersion++;
  void refreshAccountInspectionHistory();
}
function accountInspectionRender(id, markup, key) {
  const content = document.getElementById(id);
  if (content.dataset.view === key && content.innerHTML === markup) return;
  const same = content.dataset.view === key;
  const wrap = content.querySelector('[data-inspection-scroll]');
  const left = same ? wrap?.scrollLeft || 0 : 0;
  const top = same ? content.scrollTop : 0;
  const restore = wrap === document.activeElement;
  content.innerHTML = markup;
  content.dataset.view = key;
  const next = content.querySelector('[data-inspection-scroll]');
  if (next) { next.scrollLeft = left; if (restore) next.focus({preventScroll: true}); }
  content.scrollTop = top;
}
function accountInspectionTable(heads, rows) {
  return `<div data-inspection-scroll tabindex="0" role="region" aria-label="可左右滚动查看巡检记录"><table class="data-table"><thead><tr>${heads.map(x => `<th scope="col">${esc(x)}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div>`;
}
async function refreshAccountInspectionHistory() {
  if (accountInspectionLoading.history) return;
  accountInspectionLoading.history = true;
  const page = accountInspectionPage, version = accountInspectionHistoryVersion;
  try {
    const result = await accountInspectionRequest(`/api/accounts/inspections?page=${page}`);
    if (page !== accountInspectionPage || version !== accountInspectionHistoryVersion) return;
    const wasActive = accountInspectionActive;
    accountInspectionActive = !!result.active;
    if (wasActive && !accountInspectionActive) { void loadAccounts(); void loadSummary(); }
    const names = {running: '进行中', completed: '已完成', interrupted: '已中断'};
    const rows = (result.items || []).map(r => {
      const failures = Number(r.live_failed_count || 0) + Number(r.deactivated_skipped_count || 0);
      return `<tr><td><button type="button" class="jobs-tb-btn" onclick="closeAccountInspectionDialog('accountInspectionHistory');openAccountTaskLog(${Number(r.task_id)})">#${Number(r.id)}</button></td><td>${esc(accountInspectionScopeLabel(r.archived))}</td><td>${esc(names[r.status] || r.status)}<div class="sub-cell">${esc(formatDateTime(r.created_at))}</div></td><td>${Number(r.workers)}</td><td>${Number(r.checked_count) + Number(r.skipped_count)} / ${Number(r.total_count)}<div class="sub-cell">跳过 ${Number(r.skipped_count)}（已废 ${Number(r.deactivated_skipped_count)}）</div></td><td>${Number(r.invalid_count)}</td><td>${Number(r.live_success_count)} / ${Number(r.live_failed_count)}${failures ? `<div><button type="button" class="jobs-tb-btn" onclick="openAccountInspectionFailures(${Number(r.id)})">失败详情 ${failures}</button></div>` : ''}</td><td>${Number(r.plan_success_count)} / ${Number(r.plan_failed_count)}</td><td>${r.status === 'running' ? `<button type="button" class="jobs-tb-btn" onclick="stopAccountInspection(${Number(r.id)})">停止</button>` : ''}</td></tr>`;
    }).join('');
    accountInspectionRender('accountInspectionHistoryContent', rows ? accountInspectionTable(['任务', '范围', '状态 / 时间', '并发', '进度', 'AT失效', '查活 成功/失败', '套餐 成功/失败', '操作'], rows) : '<p>暂无巡检记录。</p>', `history:${page}`);
    document.getElementById('accountInspectionPageLabel').textContent = `共 ${Number(result.total)} 条 · 第 ${page} 页`;
    document.getElementById('accountInspectionPrev').disabled = page <= 1;
    document.getElementById('accountInspectionNext').disabled = page * 20 >= Number(result.total);
  } catch (error) { showToast(`读取巡检历史失败：${error.message}`); }
  finally { accountInspectionLoading.history = false; }
}
function openAccountInspectionFailures(id) {
  accountInspectionFailureId = Number(id);
  accountInspectionFailurePage = 1;
  accountInspectionFailureVersion++;
  document.getElementById('accountInspectionFailuresTitle').textContent = `巡检 #${Number(id)} · 失败详情`;
  document.getElementById('accountInspectionFailuresContent').textContent = '正在读取本次失败记录…';
  document.getElementById('accountInspectionFailuresPageLabel').textContent = '';
  document.getElementById('accountInspectionFailuresPrev').disabled = true;
  document.getElementById('accountInspectionFailuresNext').disabled = true;
  showAccountInspectionDialog('accountInspectionFailures');
  void refreshAccountInspectionFailures();
}
function changeAccountInspectionFailuresPage(delta) {
  if (accountInspectionLoading.failures) return;
  accountInspectionFailurePage = Math.max(1, accountInspectionFailurePage + delta);
  accountInspectionFailureVersion++;
  void refreshAccountInspectionFailures();
}
async function refreshAccountInspectionFailures() {
  if (accountInspectionLoading.failures || !accountInspectionFailureId) return;
  accountInspectionLoading.failures = true;
  const id = accountInspectionFailureId, page = accountInspectionFailurePage, version = accountInspectionFailureVersion;
  try {
    const result = await accountInspectionRequest(`/api/accounts/inspections/${id}/failures?page=${page}`);
    if (id !== accountInspectionFailureId || page !== accountInspectionFailurePage || version !== accountInspectionFailureVersion) return;
    const names = {deactivated_skipped: '已废跳过', rejected: '未能入队', failed: '查活失败', error: '执行异常', attention_required: '结果待确认', interrupted: '执行中断'};
    const rows = (result.items || []).map(r => `<tr><td>#${Number(r.account_id)}</td><td>${esc(r.email)}</td><td>${esc(names[r.status] || r.status)}</td><td>${esc(formatDateTime(r.failed_at))}</td><td class="inspection-error-reason">${esc(r.error)}</td></tr>`).join('');
    accountInspectionRender('accountInspectionFailuresContent', rows ? accountInspectionTable(['账号', '邮箱', '类型', '时间', '原因'], rows) : '<p>本轮暂无查活失败或已废跳过。</p>', `failures:${id}:${page}`);
    document.getElementById('accountInspectionFailuresPageLabel').textContent = `共 ${Number(result.total)} 条 · 第 ${page} 页`;
    document.getElementById('accountInspectionFailuresPrev').disabled = page <= 1;
    document.getElementById('accountInspectionFailuresNext').disabled = page * 20 >= Number(result.total);
  } catch (error) {
    if (version === accountInspectionFailureVersion) document.getElementById('accountInspectionFailuresContent').textContent = `读取失败：${error.message}，可点击刷新重试。`;
  } finally {
    accountInspectionLoading.failures = false;
    if (version !== accountInspectionFailureVersion) void refreshAccountInspectionFailures();
  }
}
async function stopAccountInspection(id) {
  try {
    await accountInspectionRequest(`/api/accounts/inspections/${Number(id)}/cancel`, {method: 'POST'});
    showToast('已请求停止，将在安全检查点结束');
    void refreshAccountInspectionHistory();
  } catch (error) { showToast(`停止巡检失败：${error.message}`); }
}
let deletingDeactivatedAccounts = false;
async function deleteDeactivatedAccounts() {
  if (deletingDeactivatedAccounts) return;
  const archived = accountInspectionScope();
  if (!confirm(`确定删除「${accountInspectionScopeLabel(archived)}」范围内全部已废账号？\n\n不限当前页，不受勾选、搜索或其他筛选影响。仅删除本地账号记录，保留邮箱池和巡检历史。此操作不可撤销。`)) return;
  deletingDeactivatedAccounts = true;
  const button = document.getElementById('btnDeleteDeactivatedAccounts');
  button.disabled = true;
  try {
    const result = await accountInspectionRequest('/api/accounts/delete-deactivated', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({archived})});
    ACCOUNT_SELECTED.clear();
    showToast(`已删除 ${Number(result.deleted_count || 0)} 个已废账号`);
  } catch (error) { showToast(`删除结果待确认，请刷新核实：${error.message}`); }
  finally { deletingDeactivatedAccounts = false; button.disabled = false; void loadAccounts(); void loadSummary(); }
}
setInterval(() => {
  if (document.hidden) return;
  if (document.getElementById('accountInspectionHistory')?.open) void refreshAccountInspectionHistory();
  if (document.getElementById('accountInspectionFailures')?.open) void refreshAccountInspectionFailures();
}, 5000);
