// Vue 页面负责 Team 工作区状态、探测、成员与邀请列表及轮询；此适配层负责按需加载与主壳导航桥接。
window.TeamsPage = (() => {
  const TEAM_ID_RE = /^[1-9]\d*$/;
  let instance = null;
  let loading = null;
  let visible = false;
  let generation = 0;
  let drainingJoin = null;
  let pendingJoin = null;
  let navigation = { tab: 'teams', view: 'list' };

  const clone = value => JSON.parse(JSON.stringify(value));

  function normalize(raw = {}) {
    const view = raw?.view === 'detail' ? 'detail' : 'list';
    if (view === 'detail') {
      const teamId = typeof raw?.team_id === 'string' ? raw.team_id.trim() : '';
      if (!TEAM_ID_RE.test(teamId)) return { tab: 'teams', view: 'list' };
      const section = raw?.section === 'invitations' ? 'invitations' : 'members';
      return { tab: 'teams', view: 'detail', team_id: teamId, section };
    }
    return { tab: 'teams', view: 'list' };
  }

  function isVisible() {
    return visible && !document.hidden && !document.getElementById('tab-teams')?.classList.contains('hidden');
  }

  function report(error) {
    showToast(`Team 管理加载失败：${error?.message || error}`);
  }

  function renderLoadError(root, error) {
    root.replaceChildren();
    const message = document.createElement('p');
    message.setAttribute('role', 'alert');
    message.textContent = `Team 管理加载失败：${error?.message || error}`;
    const retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'jobs-tb-btn';
    retry.textContent = '重新加载';
    retry.addEventListener('click', () => void activate());
    root.append(message, retry);
  }

  async function drainPendingJoin(api) {
    if (drainingJoin) return drainingJoin;
    const request = pendingJoin;
    if (!request || request.generation !== generation || !isVisible()) return;
    const drain = Promise.resolve().then(() => {
      if (request !== pendingJoin || request.generation !== generation || !isVisible()) return;
      return api.openJoinFromAccounts?.(request.payload);
    }).then(() => {
      if (pendingJoin === request) pendingJoin = null;
    });
    drainingJoin = drain;
    try {
      await drain;
    } finally {
      if (drainingJoin === drain) drainingJoin = null;
    }
  }

  async function ensure() {
    if (instance) {
      await drainPendingJoin(instance);
      return instance;
    }
    if (!loading) {
      const root = document.getElementById('teams-page-root');
      loading = (async () => {
        if (!root) throw new Error('找不到 Team 管理挂载位置');
        if (!document.getElementById('task-center-style')) {
          const style = document.createElement('link');
          style.id = 'task-center-style';
          style.rel = 'stylesheet';
          style.href = root.dataset.styleUrl;
          document.head.append(style);
        }
        const module = await import(root.dataset.moduleUrl);
        if (typeof module.mountTeams !== 'function') throw new Error('Team 管理组件版本不匹配，请重新加载');
        root.replaceChildren();
        instance = module.mountTeams(root, {
          navigation: { ...navigation },
          visible: isVisible(),
          callbacks: {
            notify: msg => showToast(msg),
            formatDateTime: v => (v ? formatDateTime(v) : '—'),
            openTask: (taskId, runId) => (
              window.TaskCenter
                ? window.TaskCenter.open({ taskId, runId: runId || null }).then(() => activateTab('tasks'))
                : openAccountTaskLog(taskId, runId || null)
            ),
            openTasksForTeam: (teamId) => {
              if (window.TaskCenter) {
                void window.TaskCenter.open({ filters: { team_id: String(teamId) } });
              } else {
                activateTab('tasks');
              }
            },
            openAccountDetail: (accountId) => {
              setModuleView('accounts', 'team', true, 'none');
              activateTab('accounts');
              setTimeout(() => openAccountDetail(String(accountId)), 60);
            },
            openAccountsCandidateMode: (team) => window.AccountsPage?.enterTeamCandidateMode?.({
              team_id: String(team.team_id),
              effective_name: team.effective_name || '',
            }),
            onNavigation: (nav, mode = 'push') => {
              navigation = normalize(nav);
              visible = true;
              activateTab('teams', true, 'none');
              recordNavigationHistory(mode === 'replace' ? 'replace' : 'push');
            },
          },
        });
        instance.setVisible?.(isVisible());
        return instance;
      })().catch(error => {
        loading = null;
        if (root) renderLoadError(root, error);
        throw error;
      });
    }
    const api = await loading;
    await drainPendingJoin(api);
    return api;
  }

  async function activate() {
    visible = true;
    try {
      const api = await ensure();
      api.setVisible?.(isVisible());
    } catch (error) {
      report(error);
    }
  }

  function navigationState() {
    return instance?.navigationState ? normalize(instance.navigationState()) : { ...navigation };
  }

  function restoreNavigation(raw = {}) {
    generation++;
    pendingJoin = null;
    navigation = normalize(raw);
    instance?.navigate?.(navigation, 'replace', { emit: false });
  }

  async function navigate(raw = {}, mode = 'push') {
    const next = normalize(raw);
    restoreNavigation(next);
    const ticket = generation;
    visible = true;
    activateTab('teams', true, 'none');
    recordNavigationHistory(mode === 'replace' ? 'replace' : 'push');
    try {
      const api = await ensure();
      if (ticket !== generation || !isVisible()) return;
      api.navigate?.(next, mode === 'replace' ? 'replace' : 'push', { emit: false });
      api.setVisible?.(true);
    } catch (error) {
      report(error);
    }
  }

  async function openJoinFromAccounts(payload = {}) {
    const targetTeamId = typeof payload.targetTeamId === 'string' && TEAM_ID_RE.test(payload.targetTeamId.trim())
      ? payload.targetTeamId.trim()
      : null;
    generation++;
    pendingJoin = { payload: clone({ ...payload, targetTeamId }), generation };
    if (targetTeamId) {
      navigation = normalize({ tab: 'teams', view: 'detail', team_id: targetTeamId, section: 'invitations' });
      instance?.navigate?.(navigation, 'replace', { emit: false });
    }
    visible = true;
    activateTab('teams', true, 'push');
    try {
      const api = await ensure();
      api.setVisible?.(isVisible());
    } catch (error) {
      report(error);
    }
  }

  function closeDialogs() {
    instance?.closeDialogs?.();
  }

  async function refresh() {
    try {
      if (instance) await instance.refresh?.();
      else if (visible) await ensure();
    } catch (error) {
      report(error);
    }
  }

  document.addEventListener('visibilitychange', () => {
    if (!isVisible()) closeDialogs();
  });

  return {
    isVueOwner: true,
    activate,
    setVisible(value) {
      const next = Boolean(value);
      if (!next && visible) {
        generation++;
        pendingJoin = null;
        closeDialogs();
      }
      visible = next;
      instance?.setVisible?.(isVisible());
    },
    navigationState,
    restoreNavigation,
    navigate,
    openJoinFromAccounts,
    closeDialogs,
    refresh,
  };
})();
