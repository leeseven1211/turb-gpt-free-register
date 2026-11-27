// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils';
import TeamDetailView from './TeamDetailView.vue';
import TeamMembersTab from './TeamMembersTab.vue';
import type { TeamsApi } from '../../api/teams';
import type { TeamDTO, TeamDetailResponse, TeamMembersListResponse, TeamsHostCallbacks } from './contracts';

const team: TeamDTO = {
  id: '9007199254740993', revision: 4, workspace_id: 'workspace-loading',
  name: '加载状态团队', display_name: null, role: 'owner',
  manager_account: { id: '71', email: 'owner@example.test', archived: false },
  purchased_seats: 10, planned_member_limit: 8, confirmed_member_count: 0,
  pending_invite_count: 0, processing_count: 0, last_synced_at: null, last_sync_status: 'never',
};
const detailResponse: TeamDetailResponse = {
  team, permission_verified_at: null,
  actions: {
    sync: { enabled: true, reason_code: null },
    reverify: { enabled: true, reason_code: null },
    join: { enabled: true, reason_code: null },
  },
};
const membersResponse: TeamMembersListResponse = {
  items: [], total: 0, page: 1, page_size: 20, revision: 'members:1',
};
const callbacks: TeamsHostCallbacks = {
  notify: vi.fn(), formatDateTime: value => value || '—', openTask: vi.fn(),
  openTasksForTeam: vi.fn(), openAccountDetail: vi.fn(), openAccountsCandidateMode: vi.fn(), onNavigation: vi.fn(),
};
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (cause: unknown) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}
const mounted: VueWrapper[] = [];
beforeEach(() => {
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
});
afterEach(() => {
  for (const wrapper of mounted.splice(0)) wrapper.unmount();
  vi.restoreAllMocks();
});
function mountDetail(detail: TeamsApi['detail']) {
  const wrapper = mount(TeamDetailView, {
    attachTo: document.body,
    props: { api: { detail } as TeamsApi, teamId: team.id, section: 'members', visible: true, callbacks },
    global: { stubs: { TeamMembersTab: true, TeamInvitationsTab: true } },
  });
  mounted.push(wrapper);
  return wrapper;
}
function detailRefreshButton(wrapper: VueWrapper) {
  return wrapper.get<HTMLButtonElement>('.tm-detail-nav button:nth-child(2)');
}

describe('Team 读取请求接替时正确结束加载状态', () => {
  it.each(['成功', '失败'] as const)('详情静默读取接替普通读取，当前请求%s后解除 loading', async result => {
    const old = deferred<TeamDetailResponse>(), current = deferred<TeamDetailResponse>();
    const detail = vi.fn<TeamsApi['detail']>().mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
    const wrapper = mountDetail(detail);
    expect(detailRefreshButton(wrapper).element.disabled).toBe(true);
    const refresh = wrapper.vm.refresh({ silent: true });
    expect(detail.mock.calls[0]?.[1]?.aborted).toBe(true);
    old.resolve(detailResponse);
    await flushPromises();
    expect(detailRefreshButton(wrapper).element.disabled).toBe(true);
    if (result === '成功') current.resolve(detailResponse);
    else current.reject(new Error('详情读取失败'));
    await refresh;
    await flushPromises();
    expect(detailRefreshButton(wrapper).element.disabled).toBe(false);
    expect(detailRefreshButton(wrapper).text()).toBe('刷新详情');
    expect(wrapper.text()).not.toContain('正在加载工作区详情');
    if (result === '成功') expect(wrapper.text()).toContain('加载状态团队');
    else expect(wrapper.get('[role="alert"]').text()).toContain('详情读取失败');
  });

  it('详情旧普通请求收尾不能清除新普通请求的 loading', async () => {
    const old = deferred<TeamDetailResponse>(), current = deferred<TeamDetailResponse>();
    const detail = vi.fn<TeamsApi['detail']>().mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
    const wrapper = mountDetail(detail);
    const refresh = wrapper.vm.refresh();
    old.resolve(detailResponse);
    await flushPromises();
    expect(detailRefreshButton(wrapper).element.disabled).toBe(true);
    current.resolve(detailResponse);
    await refresh;
    await flushPromises();
    expect(detailRefreshButton(wrapper).element.disabled).toBe(false);
  });

  it('成员旧普通请求收尾不能清除新普通请求的 loading', async () => {
    const old = deferred<TeamMembersListResponse>(), current = deferred<TeamMembersListResponse>();
    const listMembers = vi.fn<TeamsApi['listMembers']>().mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
    const wrapper = mount(TeamMembersTab, { attachTo: document.body, props: {
      api: { listMembers } as unknown as TeamsApi, teamId: team.id, visible: true, callbacks,
    } });
    mounted.push(wrapper);
    const refreshButton = () => wrapper.get<HTMLButtonElement>('.ui-refresh-button');
    expect(refreshButton().element.disabled).toBe(true);
    const refresh = wrapper.vm.refresh();
    expect(listMembers.mock.calls[0]?.[2]?.aborted).toBe(true);
    old.resolve(membersResponse);
    await flushPromises();
    expect(refreshButton().element.disabled).toBe(true);
    expect(wrapper.get('[aria-label="成员表格，可横向滚动"]').attributes('aria-busy')).toBe('true');
    current.resolve(membersResponse);
    await refresh;
    await flushPromises();
    expect(refreshButton().element.disabled).toBe(false);
    expect(wrapper.get('[aria-label="成员表格，可横向滚动"]').attributes('aria-busy')).toBe('false');
    expect(wrapper.text()).not.toContain('正在加载工作区成员');
  });
});
