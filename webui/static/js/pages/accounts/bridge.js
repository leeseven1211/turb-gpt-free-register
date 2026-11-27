// Vue owns the list state. The shell and legacy actions exchange explicit snapshots.
window.AccountsPage = (() => {
  let instance = null;
  let loading = null;
  let visible = false;
  let archived = false;
  let accountView = 'active';
  let pendingTargetTeam = null;
  let detailNavigationGeneration = 0;
  const actionButtons = {downloadSelectedCpa:'btnDownloadSelectedCpaV2',downloadSelectedAccountSessions:'btnDownloadSelectedSessionsV2',
    checkSelectedPlans:'btnCheckSelectedPlansV2',checkSelectedLive:'btnCheckSelectedLiveV2',refreshSelectedToken:'btnRefreshSelectedTokenV2',
    checkSelectedDeactivationMail:'btnCheckSelectedDeactivationMailV2',extractSelectedLinks:'btnExtractSelectedLinksV2',
    setupSelectedAccounts:'btnSetupSelectedAccountsV2',addPasswordSelectedAccounts:'btnAddPasswordSelectedAccountsV2',addTwofaSelectedAccounts:'btnAddTwofaSelectedAccountsV2',
    changePasswordSelectedAccounts:'btnChangePasswordSelectedAccountsV2',changeTwofaSelectedAccounts:'btnChangeTwofaSelectedAccountsV2',completeSelectedAccounts:'btnCompleteSelectedAccountsV2',
    retryAccountRegistration:'btnRetrySelectedRegistrationV2',uploadSelectedCodexSub2:'btnUploadSelectedCodexSub2V2',stopSelectedCodex:'btnStopSelectedCodexV2',retrySelectedCodex:'btnRetrySelectedCodexV2',
    archiveSelectedAccounts:'btnArchiveSelectedAccountsV2',deleteSelectedAccounts:'btnDeleteSelectedAccountsV2',deleteDeactivatedAccounts:'btnDeleteDeactivatedAccounts',
    'setAccountsEmailInvalid:1':'btnMarkSelectedEmailInvalidV2','setAccountsEmailInvalid:0':'btnClearSelectedEmailInvalidV2'};
  const actionButton = (action, trigger) => trigger || (actionButtons[action] ? document.getElementById(actionButtons[action]) : null);

  const report = error => showToast(`账号列表加载失败：${error.message || error}`);
  function owner() {
    if (!instance) throw new Error('账号列表正在加载，请稍后重试');
    return instance;
  }
  async function ensure() {
    if (instance) return instance;
    if (loading) return loading;
    const root = document.getElementById('accounts-list-root');
    loading = (async () => {
      if (!root) throw new Error('找不到账号列表挂载位置');
      let style = document.getElementById('task-center-style');
      if (!style) {
        style = document.createElement('link');
        style.id = 'task-center-style'; style.rel = 'stylesheet'; style.href = root.dataset.styleUrl;
        document.head.append(style);
      }
      const module = await import(root.dataset.moduleUrl);
      try { migrateAccountTableWidths(); } catch { /* 存储受限时组件使用默认列宽。 */ }
      instance = module.mountAccounts(root, {
        query: window.AccountQuery,
        capabilities: CAPABILITIES.features || {},
        presentation: createAccountVuePresentation(),
        detailPresentation: {renderBody: _accountDetailMarkup, sourceLabel: value => facetLabel('source', value)},
        syncModalScrollLock: () => updateModalScrollLock(),
        inspectionDependencies: {
          notify: message => showToast(message), operationWorkers: () => getAccountOperationWorkers(),
          randomUUID: () => crypto.randomUUID(), refreshAccounts: () => window.AccountsPage.refresh(),
          refreshSummary: () => loadSummary(), openTask: id => openAccountTaskLog(id),
          openTasks: options => window.TaskCenter.open(options),
          formatDateTime: value => formatDateTime(value), fallbackFocus: () => document.getElementById('btnAccountInspection'),
        },
        emailChangeDependencies: {
          notify: message => showToast(message), refreshAccounts: context => accountActionRefresh(context),
          openTasks: options => window.TaskCenter.open(options),
          openTask: (id, runId) => openAccountTaskLog(id, runId),
          syncModalScrollLock: () => updateModalScrollLock(), fallbackFocus: () => document.getElementById('btnEmailChangeSelectedV2'),
        },
        c2aDependencies: {
          notify: message => showToast(message), refreshAccounts: context => accountActionRefresh(context),
          selectionChanged: context => accountActionSelectionUi(context),
          openTasks: options => window.TaskCenter.open(options),
          beginBusy: (trigger, label) => {
            const button = trigger || document.getElementById('btnReimportSelectedC2aV2'), old = button?.textContent;
            const managed = Boolean(button?.closest?.('#accountsToolbarV2'));
            if (managed) instance?.setToolbarBusyLabel('reimportSelectedC2a',label);
            else if (button) {button.disabled = true; button.textContent = label;}
            return () => {if(managed)instance?.setToolbarBusyLabel('reimportSelectedC2a');else if(button){button.textContent = old;button.disabled = false;} updateAccountSelectionUi(); applyFeatureGates();};
          },
        },
        actionDependencies: {
          notify: message => showToast(message), confirm: message => confirm(message),
          clipboard: (text, feedback) => copyText(text, feedback), reloadCodex: () => loadCodex(),
          setup: {
            refresh: context => accountActionRefresh(context), pollStatuses: context => accountActionPollStatuses(context),
            operationWorkers: () => getAccountOperationWorkers(), openTasks: options => window.TaskCenter.open(options), openLog: id => openLog(id),
            openTask: (id, runId) => openAccountTaskLog(id, runId),
            showRegistrationResult: (result, context, open) => owner().showRegistrationResult(result, context, open),
          },
          local: {
            prompt: (message, initial) => prompt(message, initial), refresh: context => accountActionRefresh(context), refreshSummary: () => loadSummary(),
            removeAcknowledgedSelection: (ids, context) => accountActionRemoveAcknowledged(ids, context),
            clearSelection: context => accountActionClearSelection(context), selectionChanged: context => accountActionSelectionUi(context),
          },
          queued: {
            refresh: context => accountActionRefresh(context), pollStatuses: context => accountActionPollStatuses(context),
            refreshSummary: () => loadSummary(), reloadTasks: () => loadAccountTasks(), operationWorkers: () => getAccountOperationWorkers(),
            configuredLiveCheckDriver: () => configuredLiveCheckDriver(), readConfig: () => apiCached('/api/config', {}, 30000), fallbackConfig: () => CONFIG,
            openLiveLog: email => openLiveLog(email), openAccountTaskLog: (id, runId) => openAccountTaskLog(id, runId),
            openTasks: options => window.TaskCenter.open(options),
            openReceiptTask: (taskId, runId) => window.TaskCenter.open({taskId, runId}),
            getRowSnapshot: id => instance?.getRowSnapshot(id), isOwnerActive: () => visible && !document.hidden,
            clearScheduled: handle => clearTimeout(handle),
            updateBusyLabel: (action, trigger, label) => { const button = actionButton(action, trigger); if(button?.closest?.('#accountsToolbarV2')) instance?.setToolbarBusyLabel(action,label);else if(button) button.textContent = label; },
          },
          canInvoke: (action, trigger) => {
            const button = actionButton(action, trigger);
            return !button || (!button.disabled && button.getAttribute('aria-disabled') !== 'true' && !button.classList.contains('feature-unavailable'));
          },
          beginBusy: (action, trigger, label) => {
            const button = actionButton(action, trigger);
            const old = button?.textContent;
            const managed = Boolean(button?.closest?.('#accountsToolbarV2'));
            if (managed) instance?.setToolbarBusyLabel(action,label);
            else if (button) { button.disabled = true; if (label) button.textContent = label; }
            return () => {
              if (managed) instance?.setToolbarBusyLabel(action);
              else if (button) { if (old != null) button.textContent = old; button.disabled = false; }
              instance?.syncToolbarPending(); updateAccountSelectionUi(); applyFeatureGates();
            };
          },
        },
        callbacks: {
          notify: message => showToast(message),
          invoke: (action, context, trigger) => invokeAccountAction(action, context, trigger),
          onStateChange: state => updateAccountSelectionUi(null, state),
          afterRender: () => { applyFeatureGates(); syncAccountsVueTooltip(); },
          closeConsumers: () => closeAccountsVueTooltip(),
        },
      });
      bindAccountsHoverTooltips();
      if (typeof instance.setAccountView === 'function') instance.setAccountView(accountView);
      else instance.setArchived(archived);
      if (pendingTargetTeam && typeof instance.enterTeamCandidateMode === 'function') {
        const target = pendingTargetTeam;
        pendingTargetTeam = null;
        instance.enterTeamCandidateMode(target);
      }
      instance.setVisible(visible);
      return instance;
    })().catch(error => {
      loading = null; instance = null;
      if (root) {
        root.replaceChildren();
        const message = document.createElement('p');
        message.setAttribute('role', 'alert');
        message.textContent = `账号列表加载失败：${error.message || error}`;
        const retry = document.createElement('button');
        retry.className = 'jobs-tb-btn'; retry.textContent = '重新加载';
        retry.addEventListener('click', () => window.AccountsPage.setVisible(visible));
        root.append(message, retry);
      }
      throw error;
    });
    return loading;
  }
  function detailNavigationCurrent(ticket, view) {
    return ticket === detailNavigationGeneration && visible && accountView === view && !document.hidden
      && !document.getElementById('tab-accounts')?.classList.contains('hidden');
  }
  async function openDetailById(accountId, {trigger = null} = {}) {
    const id = String(accountId ?? '').trim();
    if (!/^[1-9]\d*$/.test(id) || (typeof accountId === 'number' && !Number.isSafeInteger(accountId))) {
      showToast('账号 ID 无效，无法打开详情');
      return;
    }
    let ticket = ++detailNavigationGeneration;
    let targetView = null;
    try {
      // 管理母号不一定已有 joined 关系，先只读定位，再进入与账号事实一致的菜单。
      const lookup = window.AccountQuery.normalize({team_scope: 'all', archived: 'all', q: `ID:${id}`});
      const params = window.AccountQuery.toLegacy(lookup, {paged: '1', page: 1, page_size: 1});
      params.set('include_facets', '0');
      const result = await api(`/api/accounts?${params}`);
      if (ticket !== detailNavigationGeneration || document.hidden) return;
      if (result?.ok !== true || !Array.isArray(result.items)) throw new Error('账号查询返回格式无效，请刷新后重试');
      const row = result.items.find(item => String(item.id) === id);
      if (!row) {
        showToast(`未找到账号 #${id}，请刷新 Team 成员后重试`);
        return;
      }
      const joined = Array.isArray(row.team_memberships) && row.team_memberships.some(item => item?.membership_state === 'joined');
      targetView = joined ? 'team' : row.archived === true ? 'archived' : 'active';
      pendingTargetTeam = null;
      instance?.clearTeamCandidateMode?.();
      setModuleView('accounts', targetView, true, 'none');
      activateTab('accounts');
      // 主壳导航会同步设置范围与可见性，完成后再记录本次详情请求。
      ticket = ++detailNavigationGeneration;
      const pageApi = await ensure();
      if (!detailNavigationCurrent(ticket, targetView)) return;
      const query = window.AccountQuery.normalize({
        team_scope: targetView === 'team' ? 'team' : targetView === 'active' ? 'non_team' : 'all',
        archived: targetView === 'team' ? 'all' : targetView === 'archived' ? 'only' : '0',
        q: `ID:${id}`,
      });
      pageApi.updateQuery(query);
      pageApi.setPage(1);
      await pageApi.refresh();
      if (!detailNavigationCurrent(ticket, targetView)) return;
      const currentQuery = window.AccountQuery.normalize(pageApi.getActionContext().querySnapshot);
      if (JSON.stringify(currentQuery) !== JSON.stringify(query)) return;
      if (!pageApi.getRowSnapshot(id)) {
        showToast(`当前账号范围未找到账号 #${id}，请刷新 Team 成员后重试`);
        return;
      }
      return pageApi.openDetail(id, trigger);
    } catch (error) {
      if (ticket === detailNavigationGeneration && !document.hidden) showToast(`账号详情打开失败：${error.message || error}`);
    }
  }
  document.addEventListener?.('visibilitychange', () => {
    if (document.hidden) ++detailNavigationGeneration;
  });
  return {
    isReady: () => instance !== null,
    async setVisible(value) {
      visible = Boolean(value);
      if (!visible) ++detailNavigationGeneration;
      if (instance) { instance.setVisible(visible); return; }
      if (visible) { try { await ensure(); } catch (error) { report(error); } }
    },
    setArchived(value) {
      const previousView = accountView;
      archived = Boolean(value);
      accountView = archived ? 'archived' : (accountView === 'team' ? 'team' : 'active');
      if (accountView !== previousView) ++detailNavigationGeneration;
      if (instance) {
        if (typeof instance.setAccountView === 'function') instance.setAccountView(accountView);
        else instance.setArchived(archived);
      }
    },
    setAccountView(view) {
      const previousView = accountView;
      accountView = ['active', 'team', 'archived'].includes(view) ? view : 'active';
      if (accountView !== previousView) ++detailNavigationGeneration;
      archived = accountView === 'archived';
      if (instance) {
        if (typeof instance.setAccountView === 'function') instance.setAccountView(accountView);
        else instance.setArchived(archived);
      }
    },
    enterTeamCandidateMode(team) {
      if (!team || !team.team_id) return;
      ++detailNavigationGeneration;
      const normalized = { team_id: String(team.team_id), effective_name: String(team.effective_name || '') };
      accountView = 'active';
      archived = false;
      if (typeof setModuleView === 'function') setModuleView('accounts', 'active', true, 'none');
      if (instance && typeof instance.enterTeamCandidateMode === 'function') {
        pendingTargetTeam = null;
        instance.enterTeamCandidateMode(normalized);
      } else {
        pendingTargetTeam = normalized;
      }
      if (typeof activateTab === 'function') activateTab('accounts');
    },
    clearTeamCandidateMode() {
      pendingTargetTeam = null;
      instance?.clearTeamCandidateMode?.();
    },
    openTeamJoin: context => owner().openTeamJoin(context),
    async refresh() {
      try {
        if (instance) await instance.refresh();
        else if (visible) await ensure();
      } catch (error) { report(error); }
    },
    async pollStatuses() { if (instance) await instance.pollStatuses(); },
    getAccountSelectionSnapshot: options => owner().getAccountSelectionSnapshot(options),
    getActionContext: options => owner().getActionContext(options),
    getRowSnapshot: id => owner().getRowSnapshot(String(id)),
    openPlanDetailsConsumer: id => owner().openPlanDetailsConsumer(String(id)),
    openDetail: (id, trigger = null) => owner().openDetail(String(id), trigger),
    openDetailById,
    closeDetail: (restoreFocus = true) => instance?.closeDetail(restoreFocus),
    isActionSupported: action => instance?.isActionSupported(action) === true,
    isActionPending: action => instance?.isActionPending(action) === true,
    invokeAction: (action, context, trigger = null) => owner().invokeAction(action, context, trigger),
    setCapabilities: value => instance?.setCapabilities(value),
    refreshQuickActions: () => instance?.refreshQuickActions(),
    showRegistrationResult: (result, context, open) => owner().showRegistrationResult(result, context, open),
    syncToolbarPending: () => instance?.syncToolbarPending(),
    closeMoreMenus: () => instance?.closeMoreMenus(),
    openInspectionStart: (context, trigger = null) => owner().openInspectionStart(context, trigger),
    openInspectionHistory: (trigger = null) => owner().openInspectionHistory(trigger),
    openInspectionFailures: (id, trigger = null) => owner().openInspectionFailures(Number(id), trigger),
    closeInspection: kind => instance?.closeInspection(kind),
    refreshInspectionHistory: () => instance?.refreshInspectionHistory(),
    refreshInspectionFailures: () => instance?.refreshInspectionFailures(),
    changeInspectionPage: delta => owner().changeInspectionPage(delta),
    changeInspectionFailuresPage: delta => owner().changeInspectionFailuresPage(delta),
    stopInspection: id => owner().stopInspection(Number(id)),
    openEmailChange: (id, context, trigger = null) => owner().openEmailChange(String(id), context, trigger),
    openBulkEmailChange: (context, trigger = null) => owner().openBulkEmailChange(context, trigger),
    closeEmailChange: options => instance?.closeEmailChange(options),
    openC2a: (context, trigger = null) => owner().openC2a(context, trigger),
    closeC2a: (returnValue, options) => instance?.closeC2a(returnValue, options),
    submitC2a: () => owner().submitC2a(), showC2aResult: result => owner().showC2aResult(result),
    openC2aTasks: items => owner().openC2aTasks(items),
    removeAcknowledgedSelection: ids => owner().removeAcknowledgedSelection(ids.map(String)),
    clearSelection: () => owner().clearSelection(),
    setPage: value => { ++detailNavigationGeneration; return owner().setPage(value); },
    setSize: value => { ++detailNavigationGeneration; return owner().setSize(value); },
    updateQuery: value => { ++detailNavigationGeneration; return owner().updateQuery(value); },
    updateFilters: value => { ++detailNavigationGeneration; return owner().updateFilters(value); },
    resetFilters: () => { ++detailNavigationGeneration; return owner().resetFilters(); },
    resetColumns: () => owner().resetColumns(),
  };
})();
