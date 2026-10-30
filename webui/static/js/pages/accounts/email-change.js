// 换绑邮箱弹窗：依赖 common.js 的页面工具和 accounts.js 的账号列表状态。
let emailChangeReturnFocus = null;
async function loadEmailChangeSources(preferredSource = '') {
  const source = $('#emailChangeSource');
  const error = $('#emailChangeSourceError');
  if (!source) return false;
  source.disabled = true;
  source.innerHTML = '<option value="">正在读取邮箱来源…</option>';
  try {
    const result = await api('/api/email-sources');
    const items = Array.isArray(result.sources) ? result.sources : [];
    source.innerHTML = '<option value="">请选择邮箱来源</option>';
    items.forEach(item => {
      const option = document.createElement('option');
      option.value = String(item.value || '');
      option.textContent = item.enabled ? String(item.label || item.value) : `${item.label || item.value}（不可用）`;
      option.disabled = !item.enabled;
      option.title = String(item.reason || '');
      option.dataset.reason = String(item.reason || '');
      source.appendChild(option);
    });
    const enabled = items.filter(item => item.enabled);
    const preferred = enabled.find(item => String(item.value) === preferredSource);
    source.value = String((preferred || enabled[0] || {}).value || '');
    source.disabled = enabled.length === 0;
    if (!enabled.length && error) {
      error.textContent = '没有已配置且可用的新邮箱来源';
      error.hidden = false;
    }
    return enabled.length > 0;
  } catch (err) {
    source.innerHTML = '<option value="">邮箱来源读取失败</option>';
    if (error) { error.textContent = `邮箱来源读取失败：${err.message}`; error.hidden = false; }
    return false;
  }
}
async function openEmailChangeModal(id, trigger = null) {
  const account = ACCOUNTS.find(item => Number(item.id) === Number(id));
  if (!account) { showToast('账号详情暂不可用，请先刷新列表'); return; }
  const modal = $('#emailChangeModal');
  const source = $('#emailChangeSource');
  const error = $('#emailChangeSourceError');
  if (!modal || !source) return;
  emailChangeReturnFocus = trigger || document.activeElement;
  modal.dataset.accountId = String(account.id);
  modal.dataset.accountIds = '';
  $('#emailChangeTitle').textContent = '换绑邮箱';
  $('#emailChangeAccountLabel').textContent = `账号 #${account.id} · 当前邮箱 ${account.email || '-'}`;
  const preferredSource = String(account.email_source || '').trim().toLowerCase();
  source.setCustomValidity('');
  if (error) { error.textContent = ''; error.hidden = true; }
  modal.classList.remove('hidden');
  modal.setAttribute('aria-hidden', 'false');
  updateModalScrollLock();
  await loadEmailChangeSources(preferredSource);
  source.focus({preventScroll:true});
}
async function openBulkEmailChangeModal(ids, trigger = null) {
  const accountIds = [...new Set((ids || []).map(Number).filter(id => Number.isInteger(id) && id > 0))];
  if (!accountIds.length) { showToast('请先选择账号'); return; }
  if (accountIds.length > 500) { showToast('单次最多换绑 500 个账号'); return; }
  const modal = $('#emailChangeModal');
  const source = $('#emailChangeSource');
  const error = $('#emailChangeSourceError');
  if (!modal || !source) return;
  emailChangeReturnFocus = trigger || document.activeElement;
  modal.dataset.accountId = '';
  modal.dataset.accountIds = JSON.stringify(accountIds);
  $('#emailChangeTitle').textContent = '批量换绑邮箱';
  $('#emailChangeAccountLabel').textContent = `已选 ${accountIds.length} 个账号 · 将按账号分别领取新邮箱`;
  source.setCustomValidity('');
  if (error) { error.textContent = ''; error.hidden = true; }
  modal.classList.remove('hidden');
  modal.setAttribute('aria-hidden', 'false');
  updateModalScrollLock();
  await loadEmailChangeSources('');
  source.focus({preventScroll:true});
}
function closeEmailChangeModal({restoreFocus = true} = {}) {
  const modal = $('#emailChangeModal');
  if (!modal || modal.classList.contains('hidden')) return;
  modal.classList.add('hidden');
  modal.setAttribute('aria-hidden', 'true');
  modal.dataset.accountId = '';
  modal.dataset.accountIds = '';
  $('#emailChangeTitle').textContent = '换绑邮箱';
  updateModalScrollLock();
  if (restoreFocus && emailChangeReturnFocus?.isConnected) {
    emailChangeReturnFocus.focus({preventScroll:true});
  }
  emailChangeReturnFocus = null;
}
function trapEmailChangeFocus(event) {
  const modal = $('#emailChangeModal');
  if (!modal || modal.classList.contains('hidden') || event.key !== 'Tab') return;
  const controls = Array.from(modal.querySelectorAll('button, select, [href], [tabindex]:not([tabindex="-1"])'))
    .filter(item => !item.disabled && !item.hidden);
  if (!controls.length) return;
  const first = controls[0];
  const last = controls[controls.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
async function submitEmailChange(event) {
  event.preventDefault();
  const modal = $('#emailChangeModal');
  const source = $('#emailChangeSource');
  const error = $('#emailChangeSourceError');
  const submit = $('#btnSubmitEmailChange');
  let bulkIds = [];
  try {
    const rawIds = JSON.parse(String(modal?.dataset.accountIds || ''));
    if (Array.isArray(rawIds)) {
      bulkIds = [...new Set(rawIds.map(Number).filter(id => Number.isInteger(id) && id > 0))];
    }
  } catch (_) {}
  const isBulk = bulkIds.length > 0;
  const accountId = Number(modal?.dataset.accountId || 0);
  const account = ACCOUNTS.find(item => Number(item.id) === accountId);
  if ((!isBulk && (!accountId || !account)) || (isBulk && bulkIds.length > 500)) {
    closeEmailChangeModal();
    showToast(isBulk ? '批量换绑账号数量无效，请重新选择' : '账号已不在当前列表，请刷新后重试');
    return;
  }
  source?.setCustomValidity?.('');
  if (!source?.checkValidity() || !source.value) {
    source?.setCustomValidity?.('请选择新邮箱来源');
    if (error) { error.textContent = '请选择新邮箱来源'; error.hidden = false; }
    source?.reportValidity();
    source?.focus();
    return;
  }
  if (error) { error.textContent = ''; error.hidden = true; }
  if (submit) { submit.disabled = true; submit.textContent = '提交中…'; }
  try {
    const result = await api(isBulk ? '/api/accounts/email-change-bulk' : `/api/accounts/${encodeURIComponent(accountId)}/email-change`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(isBulk
        ? {account_ids: bulkIds, email_source: source.value}
        : {email_source: source.value}),
    });
    if (isBulk) {
      const started = Number(result.started_count || 0);
      const skipped = Number(result.skipped_count || 0);
      showToast(`批量换绑已入队 ${started} 个${skipped ? `，跳过 ${skipped} 个` : ''}`);
    } else {
      showToast(result.message || `邮箱换绑已入队 · 任务 #${result.task_id || '-'}`);
    }
    closeEmailChangeModal({restoreFocus:false});
    loadAccounts();
    const search = $('#accountTaskTargetFilterV2');
    const typeFilter = $('#accountTaskTypeFilterV2');
    if (search) search.value = isBulk ? '' : account.email || `#${accountId}`;
    if (typeFilter) typeFilter.value = 'email_change';
    PAGERS.accountTasks.page = 1;
    activateTab('tasks');
  } catch (err) {
    const message = `提交失败：${err.message}`;
    if (error) { error.textContent = message; error.hidden = false; }
    showToast('换绑邮箱失败: ' + err.message);
  } finally {
    if (submit) { submit.disabled = false; submit.textContent = '开始换绑'; }
  }
}
$('#btnCloseEmailChange')?.addEventListener('click', () => closeEmailChangeModal());
$('#btnCancelEmailChange')?.addEventListener('click', () => closeEmailChangeModal());
$('#emailChangeForm')?.addEventListener('submit', submitEmailChange);
$('#emailChangeModal')?.addEventListener('click', event => {
  if (event.target.id === 'emailChangeModal') closeEmailChangeModal();
});
document.addEventListener('keydown', event => {
  if ($('#emailChangeModal')?.classList.contains('hidden')) return;
  if (event.key === 'Escape') { event.preventDefault(); closeEmailChangeModal(); }
  else trapEmailChangeFocus(event);
});
