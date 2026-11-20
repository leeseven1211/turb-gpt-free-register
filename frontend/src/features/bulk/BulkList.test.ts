import { DOMWrapper, flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import BulkList from './BulkList.vue';
import type { BulkListDependencies, BulkNavigation, BulkPageData } from './contracts';
const wrappers: ReturnType<typeof mount>[] = [];
beforeEach(() =>
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  ),
);
afterEach(() => {
  window.getSelection()?.removeAllRanges();
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
  vi.unstubAllGlobals();
});
function fixture(data: BulkPageData, initial: Partial<BulkNavigation> = {}) {
  const request = vi.fn<(path: string, options?: RequestInit) => Promise<unknown>>().mockResolvedValue(data);
  const callbacks: BulkListDependencies['callbacks'] = {
    navigate: vi.fn(),
    updateNavigation: vi.fn(),
    notify: vi.fn(),
    openTask: vi.fn(),
    formatDateTime: (value) => String(value || '—'),
  };
  const wrapper = mount(BulkList, {
    attachTo: document.body,
    props: {
      navigation: { tab: 'bulk', view: 'list', ...initial },
      deps: {
        api: { request: <T>(path: string, options?: RequestInit) => request(path, options) as Promise<T> },
        callbacks,
      },
    },
  });
  wrapper.vm.setVisible(true);
  void wrapper.vm.refresh();
  wrappers.push(wrapper);
  return { wrapper, request, callbacks };
}
const example = (): BulkPageData => ({
  items: [
    {
      id: '9007199254740993',
      name: '<script>批次</script>',
      operation: { key: 'plan_check', version: 1 },
      control: { state: 'active', paused: false },
      target_count: 12,
      summary: { success: 3, partial_success: 1, failed: 2, queued: 6 },
      created_at: '2026-11-16T10:00:00+08:00',
    },
  ],
  page: { page_size: 20, has_more: true, next_cursor: 'next.one' },
  summary: { total_batches: 39, active_batches: 3, ended_batches: 7, failed_targets: 2 },
});
describe('批次列表组件', () => {
  it('真实汇总与两行身份保留，结果和报告入口传完整字符串ID', async () => {
    const h = fixture(example());
    await flushPromises();
    expect(h.wrapper.get('.bl-kpis').text()).toBe('执行中3批已结束7批失败账号2个');
    expect(h.wrapper.find('.bl-toolbar').exists()).toBe(false);
    expect(h.wrapper.text()).toContain('#9007199254740993');
    expect(h.wrapper.get('.bl-name').text()).toBe('<script>批次</script>');
    expect(h.wrapper.find('script').exists()).toBe(false);
    expect(h.wrapper.get('[data-bulk-progress]').text()).toContain('6 / 12');
    expect(h.wrapper.get('[data-bulk-progress]').text()).toContain('50%');
    expect(h.wrapper.get('[data-bulk-result="success"]').text()).toContain('成功 3');
    await h.wrapper.get('[data-bulk-open]').trigger('click');
    expect(h.callbacks.navigate).toHaveBeenLastCalledWith('detail', { batch_id: '9007199254740993' });
    await h.wrapper.get('[data-bulk-result="failed"]').trigger('click');
    expect(h.callbacks.navigate).toHaveBeenLastCalledWith('detail', {
      batch_id: '9007199254740993',
      result_state: 'failed',
    });
    await h.wrapper.get('[data-bulk-report]').trigger('click');
    expect(h.callbacks.navigate).toHaveBeenLastCalledWith('detail', { batch_id: '9007199254740993' }, true);
    expect(h.wrapper.text()).not.toMatch(/第\s*\d+\s*页/);
  });

  it('历史异常并入失败，明确返回的零与未知总数分别显示', async () => {
    const data = example();
    data.items = [
      {
        id: '42',
        target_count: 6,
        counts: { success: 1, failed: 1, attention_required: 2, cancelled: 1, queued: 1 },
      },
      { id: '41', target_count: 0, summary: {} },
    ];
    const h = fixture(data);
    await flushPromises();
    const historical = h.wrapper.get('[data-bulk-row="42"]');
    expect(historical.get('[data-bulk-result="failed"]').text()).toContain('失败 3');
    expect(historical.get('[data-bulk-progress]').text()).toContain('83%');
    expect(h.wrapper.get('[data-bulk-row="41"] [data-bulk-progress]').text()).toContain('0 / 0');
  });

  it('无统计和未知名单数量不推算成零总量或完成进度', async () => {
    const data = example();
    delete data.summary;
    data.items = [{ id: '25', name: '准备中', action_key: 'token_refresh', target_count: null }];
    const h = fixture(data);
    await flushPromises();
    expect(h.wrapper.find('.bl-toolbar').exists()).toBe(false);
    expect(h.wrapper.get('[data-bulk-progress]').text()).toContain('名单准备中');
    expect(h.wrapper.find('progress').exists()).toBe(false);
    expect(h.wrapper.find('.bl-kpis').exists()).toBe(false);
    expect(h.wrapper.text()).not.toContain('0 / 0');
  });

  it('表头操作筛选与摘要删除沿用同一导航范围并清游标', async () => {
    const h = fixture(example(), { cursor: 'direct' });
    await flushPromises();
    await h.wrapper.get('thead button[aria-label="筛选操作类型"]').trigger('click');
    await flushPromises();
    const body = new DOMWrapper(document.body);
    await body.get('input[type="radio"][value="token_refresh"]').setValue(true);
    await flushPromises();
    expect(h.callbacks.updateNavigation).toHaveBeenLastCalledWith({ operation: 'token_refresh', cursor: '' });
    expect(new URL(h.request.mock.calls.at(-1)![0], 'http://local').searchParams.get('operation_key[]')).toBe(
      'token_refresh',
    );
    const toolbar = h.wrapper.get('.bl-toolbar');
    expect(toolbar.get('.list-filter-summary').text()).toContain('刷新 AT');
    expect(toolbar.text()).not.toContain('个批次');
    expect(toolbar.text()).toContain('清除筛选');
    const stateTrigger = h.wrapper.get<HTMLButtonElement>('thead button[aria-label="筛选状态"]');
    await stateTrigger.trigger('pointerdown', { button: 0 });
    stateTrigger.element.focus();
    await stateTrigger.trigger('click');
    await flushPromises();
    expect(body.findAll('.list-filter-popover')).toHaveLength(1);
    await body.get('input[type="radio"][value="paused"]').setValue(true);
    await flushPromises();
    expect(h.callbacks.updateNavigation).toHaveBeenLastCalledWith({ state: 'paused', cursor: '' });
    await h.wrapper.get('.list-filter-summary button').trigger('click');
    await flushPromises();
    expect(h.callbacks.updateNavigation).toHaveBeenLastCalledWith({ operation: '', cursor: '' });
  });

  it('同页刷新保留焦点和已有行，失败显示重试', async () => {
    const h = fixture(example());
    await flushPromises();
    const name = h.wrapper.get<HTMLButtonElement>('[data-bulk-open]');
    name.element.focus();
    await h.wrapper.vm.refresh();
    await flushPromises();
    expect(document.activeElement).toBe(name.element);
    h.request.mockRejectedValueOnce(new Error('网络中断'));
    await h.wrapper.vm.refresh();
    await flushPromises();
    expect(h.wrapper.text()).toContain('#9007199254740993');
    expect(h.wrapper.get('[role="alert"]').text()).toContain('网络中断');
    await h.wrapper.get('[role="alert"] button').trigger('click');
    await flushPromises();
    expect(h.wrapper.find('[role="alert"]').exists()).toBe(false);
  });

  it('筛选期间旧行不可触发新范围的操作，空结果提供新建入口', async () => {
    const h = fixture(example());
    await flushPromises();
    h.request.mockRejectedValueOnce(new Error('旧范围错误'));
    await h.wrapper.vm.refresh();
    await flushPromises();
    let release!: (value: BulkPageData) => void;
    h.request.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = resolve as typeof release;
        }),
    );
    await h.wrapper.setProps({ navigation: { tab: 'bulk', view: 'list', q: 'none' } });
    await flushPromises();
    expect(h.wrapper.find('[data-bulk-open]').exists()).toBe(false);
    expect(h.wrapper.find('.bl-kpis').exists()).toBe(false);
    expect(h.wrapper.text()).not.toContain('旧范围错误');
    expect(h.wrapper.text()).toContain('正在加载批次');
    release({ items: [], page: { page_size: 20, has_more: false, next_cursor: null } });
    await flushPromises();
    await h.wrapper.get('[data-bulk-create]').trigger('click');
    expect(h.callbacks.navigate).toHaveBeenLastCalledWith('create');
  });

  it('用户选择批次文本时轮询不替换内容，解除选择后可刷新', async () => {
    const h = fixture(example());
    await flushPromises();
    const range = document.createRange();
    range.selectNodeContents(h.wrapper.get('.bl-name').element);
    window.getSelection()?.addRange(range);
    await h.wrapper.vm.refresh();
    expect(h.request).toHaveBeenCalledTimes(1);
    expect(window.getSelection()?.toString()).toBe('<script>批次</script>');
    window.getSelection()?.removeAllRanges();
    await h.wrapper.vm.refresh();
    expect(h.request).toHaveBeenCalledTimes(2);
  });

  it('同范围的轮询仅在行 ID 或顺序变化时提示，手动刷新安静更新', async () => {
    const h = fixture(example());
    await flushPromises();
    h.request.mockResolvedValueOnce({ ...example(), items: [{ id: '9007199254740993', name: '改名' }] });
    await h.wrapper.vm.refresh(true);
    expect(h.callbacks.notify).not.toHaveBeenCalled();
    const changed = { ...example(), items: [{ id: '17' }, { id: '16' }] };
    h.request.mockResolvedValueOnce(changed);
    await h.wrapper.vm.refresh();
    expect(h.callbacks.notify).not.toHaveBeenCalled();
    h.request.mockResolvedValueOnce({ ...changed, items: [...changed.items].reverse() });
    await h.wrapper.vm.refresh(true);
    expect(h.callbacks.notify).toHaveBeenCalledTimes(1);
    expect(h.callbacks.notify).toHaveBeenCalledWith('批次列表已更新');
  });

  it('请求发出后选中的文字也保留到下一次刷新', async () => {
    const h = fixture(example());
    await flushPromises();
    let release!: (value: BulkPageData) => void;
    h.request.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = resolve as typeof release;
        }),
    );
    const pending = h.wrapper.vm.refresh();
    const range = document.createRange();
    range.selectNodeContents(h.wrapper.get('.bl-name').element);
    window.getSelection()?.addRange(range);
    release({ ...example(), items: [] });
    await pending;
    await flushPromises();
    expect(window.getSelection()?.toString()).toBe('<script>批次</script>');
    window.getSelection()?.removeAllRanges();
    h.request.mockResolvedValueOnce({ ...example(), items: [] });
    await h.wrapper.vm.refresh();
    await flushPromises();
    expect(h.wrapper.find('[data-bulk-open]').exists()).toBe(false);
  });

  it('隐藏列表关闭Portal且禁止请求，Shell恢复时显式刷新一次', async () => {
    const h = fixture(example());
    await flushPromises();
    await h.wrapper.get('thead button[aria-label="筛选状态"]').trigger('click');
    await flushPromises();
    expect(new DOMWrapper(document.body).find('.list-filter-popover').exists()).toBe(true);
    h.wrapper.vm.setVisible(false);
    await flushPromises();
    expect(new DOMWrapper(document.body).find('.list-filter-popover').exists()).toBe(false);
    await h.wrapper.vm.refresh();
    expect(h.request).toHaveBeenCalledTimes(1);
    h.wrapper.vm.setVisible(true);
    await flushPromises();
    expect(h.request).toHaveBeenCalledTimes(1);
    await h.wrapper.vm.refresh();
    expect(h.request).toHaveBeenCalledTimes(2);
  });
});
