import { mount, flushPromises } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ProxyTrafficPage from './ProxyTrafficPage.vue';
import { mountProxyTraffic } from '../../proxy';
import {
  fixtureApi,
  fixtureTraffic,
  fixtureLease,
  fixturePage,
  fixtureSummary,
  fixturePool,
} from './fixtures';
const wrappers: ReturnType<typeof mount>[] = [];
function setup(view: 'pool' | 'records' = 'pool') {
  const api = fixtureApi(),
    openTask = vi.fn(),
    notify = vi.fn();
  const wrapper = mount(ProxyTrafficPage, {
    attachTo: document.body,
    props: {
      deps: {
        api,
        visible: true,
        view,
        openTask,
        notify,
        facetLabel: (group, value) => (group === 'task_type' && value === 'plan_check' ? '查套餐' : value),
      },
    },
  });
  wrappers.push(wrapper);
  return { wrapper, api, openTask, notify };
}
beforeEach(() => {
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '');
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open');
    this.dispatchEvent(new Event('close'));
  };
});
afterEach(() => {
  wrappers.splice(0).forEach((w) => w.unmount());
  document.body.replaceChildren();
  localStorage.clear();
});
describe('complete proxy Vue page', () => {
  it('retains inventory/country counts, supply reason, capacity warning and masked inventory', async () => {
    const { wrapper, api } = setup();
    api.pool = async () => ({
      ...fixturePool,
      country_pools: [
        ...fixturePool.country_pools!,
        { provider: 'roxy', region: 'VN', counts: { ready: 1 }, waiting_local: 1, target_ready: 4 },
      ],
    });
    await flushPromises();
    const pool = wrapper.get('[data-proxy-module-panel="pool"]');
    for (const text of [
      '17 / 20',
      'JP',
      '1024proxy',
      '等待 3',
      '目标 6',
      '7 秒后补货',
      '203.0.113.0/24',
      'resource-1',
      '超过全池容量 20',
      'VN',
      '等待轮换 2',
      '故障隔离 1',
    ])
      expect(pool.text()).toContain(text);
    for (const [key, value] of [
      ['poolReady', '3'],
      ['poolFetching', '1'],
      ['poolChecking', '2'],
      ['poolLeased', '4'],
      ['poolShared', '5'],
    ])
      expect(wrapper.get(`[data-proxy-summary="${key}"]`).text()).toBe(value);
    expect(wrapper.findAll('.list-result').length).toBeGreaterThan(0);
    expect(wrapper.findAll('[data-proxy-view]')).toHaveLength(3);
  });
  it('renders all original records columns and plain task associations with global zero summary', async () => {
    const { wrapper, openTask } = setup('records');
    await flushPromises();
    expect(wrapper.get('[data-proxy-summary="todayRequestCount"]').text()).toBe('0');
    expect(wrapper.get('[data-proxy-table="current"]').text()).toContain('lease-public-17');
    await wrapper.get('[data-proxy-view="history"]').trigger('click');
    expect(wrapper.get('[data-proxy-table="history"]').text()).toContain('28');
    await wrapper.get('[data-proxy-view="traffic"]').trigger('click');
    const table = wrapper.get('[data-proxy-table="traffic"]');
    for (const text of ['protocol_http', 'POST', '46 B', '9 / 2 / 1 / 3', '查套餐', '9007199254740995'])
      expect(table.text()).toContain(text);
    expect(table.findAll('a')).toHaveLength(0);
    expect(openTask).not.toHaveBeenCalled();
    expect(table.find('details').exists()).toBe(false);
    expect(wrapper.get('[data-proxy-summary="totalBytes"]').text()).toBe('2.00 KB');
    expect(wrapper.findAll('.list-pagination').length).toBeGreaterThan(0);
  });
  it('opens a frozen complete record detail and safely escapes resource and tunnel values', async () => {
    const { wrapper, api } = setup('records');
    api.page = async (view) =>
      fixturePage(
        view,
        view === 'traffic'
          ? [
              {
                ...fixtureTraffic,
                resource_details: [
                  { url: '<script>fixture</script>', resource_type: 'script', total_bytes: 4 },
                ],
                proxy_transport: {
                  available: true,
                  total_bytes: 100,
                  blocked_connection_count: 2,
                  destinations: [{ host: '<img src=x>', port: 443, total_bytes: 100 }],
                },
              },
            ]
          : [{ ...fixtureLease }],
      );
    await flushPromises();
    await wrapper.get('[data-proxy-view="traffic"]').trigger('click');
    const trigger = wrapper.get('[data-proxy-table="traffic"] [data-proxy-detail]');
    await trigger.trigger('click');
    await flushPromises();
    const dialog = wrapper.get('dialog');
    expect(dialog.attributes()).toHaveProperty('open');
    for (const phrase of [
      '代理隧道传输',
      '注册 Attempt',
      '解压后响应正文',
      '<script>fixture</script>',
      '与页面字节重叠，不相加',
    ])
      expect(dialog.text()).toContain(phrase);
    expect(dialog.find('script').exists()).toBe(false);
    expect(dialog.text()).toContain('<img src=x>');
    expect(dialog.find('img').exists()).toBe(false);
    api.page = async (view) => fixturePage(view, [{ id: 18, total_bytes: 999, source: 'new-source' }]);
    await (wrapper.vm as unknown as { load(): Promise<void> }).load();
    expect(dialog.text()).toContain('protocol_http');
    expect(dialog.text()).not.toContain('new-source');
    await wrapper.get('[data-proxy-close-detail]').trigger('click');
    await flushPromises();
    expect(wrapper.find('dialog[open]').exists()).toBe(false);
  });
  it('keeps legacy browser-only summary count fallback while preserving explicit zero', async () => {
    const { wrapper, api } = setup('records');
    api.summary = async () => ({ ...fixtureSummary, today_request_count: undefined, today_browser_count: 7 });
    await flushPromises();
    expect(wrapper.get('[data-proxy-summary="todayRequestCount"]').text()).toBe('7');
    api.summary = async () => ({ ...fixtureSummary, today_request_count: 0, today_browser_count: 7 });
    await (wrapper.vm as unknown as { load(): Promise<void> }).load();
    await flushPromises();
    expect(wrapper.get('[data-proxy-summary="todayRequestCount"]').text()).toBe('0');
  });
  it('keeps keyboard tab navigation and closes detail when page hides', async () => {
    const { wrapper } = setup('records');
    await flushPromises();
    const tabs = wrapper.get('[role="tablist"]');
    await tabs.trigger('keydown', { key: 'End' });
    expect(wrapper.get('[data-proxy-view="traffic"]').attributes('aria-selected')).toBe('true');
    await wrapper.get('[data-proxy-detail]').trigger('click');
    await flushPromises();
    (wrapper.vm as unknown as { setVisible(v: boolean): void }).setVisible(false);
    await flushPromises();
    expect(wrapper.find('dialog[open]').exists()).toBe(false);
  });
  it('restores explicit close focus without moving dialog scroll during refresh', async () => {
    const { wrapper } = setup('records');
    await flushPromises();
    await wrapper.get('[data-proxy-view="traffic"]').trigger('click');
    const trigger = wrapper.get('[data-proxy-table="traffic"] [data-proxy-detail]');
    (trigger.element as HTMLElement).focus();
    await trigger.trigger('click');
    await flushPromises();
    const dialog = wrapper.get('dialog').element as HTMLDialogElement;
    dialog.scrollTop = 130;
    await (wrapper.vm as unknown as { load(): Promise<void> }).load();
    await flushPromises();
    expect(dialog.scrollTop).toBe(130);
    await wrapper.get('[data-proxy-close-detail]').trigger('click');
    await flushPromises();
    expect(document.activeElement).toBe(trigger.element);
    expect(document.body.style.overflow).toBe('');
  });
  it('mount handle stays hidden until activated and destroys its dialog and poll owner', async () => {
    const root = document.createElement('div');
    document.body.append(root);
    const api = fixtureApi(),
      page = vi.spyOn(api, 'page');
    const handle = mountProxyTraffic(root, { api });
    await handle.load();
    expect(page).not.toHaveBeenCalled();
    handle.setView('records');
    handle.setVisible(true);
    await handle.load();
    expect(page).toHaveBeenCalledTimes(3);
    expect(root.querySelector('[data-proxy-module-panel="records"]')).not.toBeNull();
    handle.destroy();
    expect(root.children).toHaveLength(0);
  });
  it('keeps legacy ratio column widths and only resets the active table', async () => {
    localStorage.setItem('gpt_console_table_widths_proxyHistory', '[1,1,1,1,1,1,1,1]');
    localStorage.setItem('gpt_console_table_total_proxyHistory', '1600');
    localStorage.setItem('gpt_console_table_widths_proxyTraffic', '[1,1,1,1,1,1,1,1]');
    localStorage.setItem('gpt_console_table_total_proxyTraffic', '1800');
    const { wrapper, notify } = setup('records');
    await flushPromises();
    await wrapper.get('[data-proxy-view="history"]').trigger('click');
    const table = wrapper.get('[data-proxy-table="history"]');
    expect(table.get('col').attributes('style')).toContain('200px');
    await wrapper.get('button[aria-label="恢复当前列表列宽"]').trigger('click');
    expect(localStorage.getItem('gpt_console_table_total_proxyHistory')).toBeNull();
    expect(localStorage.getItem('gpt_console_table_total_proxyTraffic')).toBe('1800');
    expect(notify).toHaveBeenCalledWith('已恢复默认列宽');
  });
  it('retains polling scroll and focus but resets only the changed list after an accepted page read', async () => {
    const { wrapper, api } = setup('records');
    api.page = async (view) => ({ ...fixturePage(view), total: 60 });
    await flushPromises();
    const scroll = wrapper.get('[data-proxy-table="current"]').element.parentElement!;
    scroll.scrollTop = 120;
    scroll.scrollLeft = 80;
    const reset = wrapper.get('button[aria-label="恢复当前列表列宽"]').element as HTMLElement;
    reset.focus();
    await (wrapper.vm as unknown as { load(): Promise<void> }).load();
    await flushPromises();
    expect(scroll.scrollTop).toBe(120);
    expect(scroll.scrollLeft).toBe(80);
    expect(document.activeElement).toBe(reset);
    const next = wrapper.get('[data-proxy-panel="current"] .list-pagination__next');
    await next.trigger('click');
    await flushPromises();
    expect(scroll.scrollTop).toBe(0);
    expect(scroll.scrollLeft).toBe(80);
  });
  it('never exposes private extras from otherwise public inventory and traffic fixtures', async () => {
    const { wrapper, api } = setup('records');
    const originalPool = api.pool;
    api.pool = async () =>
      ({
        ...(await originalPool()),
        proxy_url: 'private-sentinel-1',
        username: 'private-sentinel-2',
        items: [{ resource_id: 'r', password: 'private-sentinel-3' }],
      }) as Awaited<ReturnType<typeof api.pool>>;
    api.page = async (view) =>
      fixturePage(view, [
        { ...fixtureTraffic, proxy_url: 'private-sentinel-4', cookies: 'private-sentinel-5' },
      ]);
    await flushPromises();
    await wrapper.get('[data-proxy-view="traffic"]').trigger('click');
    await wrapper.get('[data-proxy-table="traffic"] [data-proxy-detail]').trigger('click');
    await flushPromises();
    expect(wrapper.text()).not.toContain('private-sentinel');
  });
  it('keeps a chosen header filter and removable chip synchronized', async () => {
    const { wrapper } = setup('records');
    await flushPromises();
    await wrapper.get('[data-proxy-table="current"] button[aria-label="筛选状态"]').trigger('click');
    await flushPromises();
    const option = document.querySelector<HTMLButtonElement>('[data-proxy-filter-option="leased"]');
    expect(option).not.toBeNull();
    option!.click();
    await flushPromises();
    const chips = wrapper.get('.list-filter-summary');
    expect(chips.text()).toContain('租约中');
    await chips.get('button').trigger('click');
    await flushPromises();
    expect(wrapper.find('.list-filter-summary').exists()).toBe(false);
  });
});
