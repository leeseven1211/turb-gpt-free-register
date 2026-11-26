import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { tasksApi } from '../../../api/tasks';
import TaskDetail from './TaskDetail.vue';
import TaskProgress from './TaskProgress.vue';
import type { TaskProgress as Progress } from '../../../api/tasks';

const originalShowModal = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'showModal');
const originalClose = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'close');
beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function (this: HTMLDialogElement) { this.open = true; } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function (this: HTMLDialogElement) { this.open = false; this.dispatchEvent(new Event('close')); } });
  vi.spyOn(tasksApi, 'detail').mockResolvedValue({ ok: true, task: { id: 1, task_type: 'plan_check', status: 'failed', last_run_id: 10,
    runs: [{ id: 10, status: 'failed', run_no: 1, error_message: '邮箱验证码等待超时' }] } });
  vi.spyOn(tasksApi, 'progress').mockResolvedValue({ ok: true, progress: { task_id: 1, run_id: 10, revision: '1',
    main_steps: [{ id: 'authenticate', label: '登录验证', state: 'failed', raw_stages: ['email_otp'], attempts: [{ event_id: 1, state: 'failed', message: '等待超时' }] }],
    outcome: { status: 'failed' } } });
  vi.spyOn(tasksApi, 'events').mockResolvedValue({ ok: true, items: [{ id: 1, stage: 'email_otp', message: '验证码等待结束' },
    { id: 2, stage: 'queued', message: '任务进入队列' }], next_after_id: 2, has_more: false });
  vi.spyOn(tasksApi, 'logs').mockResolvedValue({ ok: true, items: [{ message: '本次运行技术日志', stage: 'email_otp' }], next_cursor: 100,
    available: true, has_more: false, run_terminal: true });
});
afterEach(() => {
  vi.restoreAllMocks(); document.body.replaceChildren();
  if (originalShowModal) Object.defineProperty(HTMLDialogElement.prototype, 'showModal', originalShowModal);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal');
  if (originalClose) Object.defineProperty(HTMLDialogElement.prototype, 'close', originalClose);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, 'close');
});

describe('任务详情组件交互', () => {
  it('后台轮询保持头部稳定，手动刷新复用正在读取的请求并显示反馈', async () => {
    vi.useFakeTimers();
    const running = { ok: true, task: { id: 1, task_type: 'plan_check', status: 'running', last_run_id: 10,
      runs: [{ id: 10, status: 'running', run_no: 1 }] } };
    vi.mocked(tasksApi.detail).mockResolvedValue(running);
    const wrapper = mount(TaskDetail, { attachTo: document.body });
    try {
      await wrapper.vm.open(1); await flushPromises();
      const header = document.querySelector('.tc-detail-header')!;
      const refresh = header.querySelector<HTMLButtonElement>('.tc-detail-header-actions button')!;
      expect(refresh.classList.contains('ui-refresh-button')).toBe(true);
      const selector = header.querySelector('select')!;
      const firstEvent = document.querySelector('.tc-event')!;
      let resolve!: (value: Awaited<ReturnType<typeof tasksApi.detail>>) => void;
      vi.mocked(tasksApi.detail).mockReturnValueOnce(new Promise(done => { resolve = done; }));
      vi.mocked(tasksApi.events).mockResolvedValueOnce({ ok: true, items: [{ id: 3, message: '后台新增记录' }],
        next_after_id: 3, has_more: false });

      await vi.advanceTimersByTimeAsync(2000);
      expect(refresh.textContent).toBe('刷新');
      expect(refresh.disabled).toBe(false);
      expect(header.querySelector('select')).toBe(selector);
      expect(document.querySelector('.tc-event')).toBe(firstEvent);
      const reads = vi.mocked(tasksApi.detail).mock.calls.length;

      refresh.click(); await flushPromises();
      expect(refresh.textContent).toBe('刷新中…');
      expect(refresh.disabled).toBe(true);
      expect(tasksApi.detail).toHaveBeenCalledTimes(reads);

      resolve(running); await flushPromises();
      expect(refresh.textContent).toBe('刷新');
      expect(refresh.disabled).toBe(false);
      expect(document.querySelector('.tc-event')).toBe(firstEvent);
      expect(document.querySelector('#tc-detail-panel-events')?.textContent).toContain('后台新增记录');
    } finally { wrapper.unmount(); vi.useRealTimers(); }
  });
  it('诊断入口绑定当前 Run，切换历史运行时不展示其它运行的产物', async () => {
    // 从 test_roxy_refresh_frontend.cjs 迁移真实产物展示契约；旧页面继续验证入口传参。
    vi.mocked(tasksApi.detail).mockResolvedValue({ ok: true, task: { id: 1, task_type: 'token_refresh',
      status: 'failed', last_run_id: 8, resources: [], runs: [
        { id: 7, run_no: 1, status: 'failed', debug_artifacts: {
          available: true, har_url: '/api/operations/1/runs/7/debug/har',
        } },
        { id: 8, run_no: 2, status: 'failed', result_summary: { debug_browser_kept: true }, debug_artifacts: {
          available: true, state: 'failed', har_url: '/api/operations/1/runs/8/debug/har',
          screenshot_url: '/api/operations/1/runs/8/debug/screenshot',
          page_state_url: '/api/operations/1/runs/8/debug/page-state', summary: { request_count: 12 },
        } },
      ] } });
    vi.mocked(tasksApi.progress).mockImplementation(async (taskId, runId) => ({ ok: true,
      progress: { task_id: taskId, run_id: runId, revision: String(runId), main_steps: [], outcome: { status: 'failed' } } }));
    const wrapper = mount(TaskDetail, { attachTo: document.body });
    try {
      await wrapper.vm.open(1, 8); await flushPromises();
      document.querySelector<HTMLButtonElement>('[data-detail-tab=artifacts]')!.click(); await flushPromises();
      const panel = () => document.querySelector<HTMLElement>('#tc-detail-panel-artifacts')!;
      const links = () => [...panel().querySelectorAll('a')].map(link => link.getAttribute('href'));
      expect(links()).toEqual(['/api/operations/1/runs/8/debug/har', '/api/operations/1/runs/8/debug/page-state',
        '/api/operations/1/runs/8/debug/screenshot']);
      expect(panel().textContent).toContain('失败窗口已保留');
      expect(panel().textContent).toContain('查看失败截图');
      expect(panel().textContent).toContain('请求 12 条');
      expect(panel().innerHTML).not.toContain('/runs/7/');

      const run = document.querySelector<HTMLSelectElement>('select[aria-label="选择执行实例"]')!;
      run.value = '7'; run.dispatchEvent(new Event('change')); await flushPromises();
      expect(links()).toEqual(['/api/operations/1/runs/7/debug/har']);
      expect(panel().innerHTML).not.toContain('/runs/8/');
      expect(panel().textContent).not.toContain('失败窗口已保留');
      expect(panel().textContent).not.toContain('查看失败截图');

      run.value = '8'; run.dispatchEvent(new Event('change')); await flushPromises();
      expect(links()).toContain('/api/operations/1/runs/8/debug/screenshot');
      expect(panel().innerHTML).not.toContain('/runs/7/');
    } finally { wrapper.unmount(); }
  });
  it('标题、目标、状态和运行选择共用头部，页签与读取控制共用工具栏', async () => {
    vi.mocked(tasksApi.detail).mockResolvedValue({ ok: true, task: { id: 1, task_type: 'plan_check', status: 'failed',
      email_snapshot: 'account@example.com', last_run_id: 10, runs: [{ id: 10, status: 'failed', run_no: 1, duration_ms: 5000 }] } });
    const wrapper = mount(TaskDetail, { attachTo: document.body });
    await wrapper.vm.open(1); await flushPromises();
    const header = document.querySelector('.tc-detail-header')!;
    expect(header.textContent).toContain('任务 #1');
    expect(header.querySelector('.tc-detail-target')?.textContent).toBe('account@example.com');
    expect(header.querySelector('.tc-detail-status')?.textContent).toContain('耗时 5.0 秒');
    expect(header.querySelector('select[aria-label="选择执行实例"]')).not.toBeNull();
    const toolbar = document.querySelector('.tc-detail-view-toolbar')!;
    expect(toolbar.querySelector('[role=tablist]')).not.toBeNull();
    const start = toolbar.querySelector<HTMLButtonElement>('.tc-detail-read-toolbar button')!;
    expect(start.getAttribute('aria-pressed')).toBe('false');
    start.click(); await flushPromises();
    expect(start.getAttribute('aria-pressed')).toBe('true');
    expect(tasksApi.events).toHaveBeenLastCalledWith(1, 10, { after_id: 0, limit: 500 }, expect.any(AbortSignal));
    toolbar.querySelector<HTMLButtonElement>('[data-detail-tab=artifacts]')!.click(); await flushPromises();
    expect(toolbar.querySelector('.tc-detail-read-toolbar')).toBeNull();
    wrapper.unmount();
  });
  it('执行与步骤同一失败只显示一个可展开摘要并保留两边证据', async () => {
    vi.mocked(tasksApi.progress).mockResolvedValue({ ok: true, progress: { task_id: 1, run_id: 10, revision: '1', main_steps: [],
      outcome: { status: 'failed' }, failure: { stage: 'email_otp', label: '登录验证', message: '邮箱验证码等待超时',
        error_info: { cause_summary: '验证码未在等待时间内到达' }, evidence: { event_id: 7 } } } });
    const wrapper = mount(TaskDetail, { attachTo: document.body });
    await wrapper.vm.open(1); await flushPromises();
    const summaries = document.querySelectorAll('.tc-task-failure');
    expect(summaries).toHaveLength(1);
    const summary = summaries[0]!.querySelector('summary')!;
    expect(summary.textContent).toContain('验证码未在等待时间内到达');
    expect(summary.textContent).not.toContain('执行错误');
    expect(summaries[0]!.querySelector('pre')?.textContent).toContain('邮箱验证码等待超时');
    expect(summaries[0]!.querySelector('pre')?.textContent).toContain('"event_id": 7');
    wrapper.unmount();
  });
  it('同一通用分类下不同失败原因不被去重，进度读取错误独立显示', async () => {
    vi.mocked(tasksApi.detail).mockResolvedValue({ ok: true, task: { id: 1, task_type: 'plan_check', status: 'failed', last_run_id: 10,
      runs: [{ id: 10, status: 'failed', run_no: 1, error_info: { summary: '登录失败', cause_summary: '代理连接被拒绝' } }] } });
    vi.mocked(tasksApi.progress).mockResolvedValue({ ok: true, progress: { task_id: 1, run_id: 10, revision: '1', main_steps: [],
      outcome: { status: 'failed' }, failure: { stage: 'email_otp', label: '登录验证',
        error_info: { summary: '登录失败', cause_summary: '邮箱验证码等待超时' } } } });
    const wrapper = mount(TaskDetail, { attachTo: document.body });
    await wrapper.vm.open(1); await flushPromises();
    const summary = document.querySelector('.tc-task-failure summary')!;
    expect(summary.textContent).toContain('邮箱验证码等待超时');
    expect(summary.textContent).toContain('执行错误：登录失败 · 代理连接被拒绝');
    vi.mocked(tasksApi.progress).mockRejectedValueOnce(new Error('进度服务暂不可用'));
    document.querySelector<HTMLButtonElement>('.tc-detail-header-actions button')!.click(); await flushPromises();
    expect(document.querySelectorAll('.tc-task-failure')).toHaveLength(1);
    const readError = document.querySelector('.tc-detail-error[role=status]');
    expect(readError?.textContent).toContain('进度读取失败：进度服务暂不可用');
    expect(readError?.textContent).toContain('保留上次快照');
    expect(readError?.closest('.tc-task-failure')).toBeNull();
    wrapper.unmount();
  });
  it('进度首次读取失败时仍可查看执行失败摘要', async () => {
    vi.mocked(tasksApi.progress).mockRejectedValueOnce(new Error('进度服务暂不可用'));
    const wrapper = mount(TaskDetail, { attachTo: document.body });
    await wrapper.vm.open(1); await flushPromises();
    expect(document.querySelector('.tc-task-failure summary')?.textContent).toContain('邮箱验证码等待超时');
    expect(document.querySelector('.tc-detail-error[role=status]')?.textContent).toContain('进度读取失败');
    wrapper.unmount();
  });
  it('步骤筛选只影响事件视图，关闭后返回原触发按钮', async () => {
    const trigger = document.createElement('button');
    trigger.textContent = '打开详情';
    document.body.append(trigger);
    trigger.focus();
    const wrapper = mount(TaskDetail, { attachTo: document.body });
    await wrapper.vm.open(1);
    await flushPromises();
    const dialog = document.querySelector<HTMLDialogElement>('.tc-detail-dialog')!;
    expect(dialog.open).toBe(true);
    expect(dialog.querySelectorAll('.tc-event')).toHaveLength(2);
    dialog.querySelector<HTMLButtonElement>('.tc-step-select')!.click();
    await flushPromises();
    expect(dialog.querySelectorAll('.tc-event')).toHaveLength(1);
    expect(dialog.textContent).toContain('验证码等待结束');
    dialog.dispatchEvent(new Event('cancel', { cancelable: true }));
    await flushPromises();
    expect(dialog.open).toBe(false);
    expect(document.activeElement).toBe(trigger);
    expect(wrapper.emitted('close')).toHaveLength(1);
    wrapper.unmount();
  });
  it('键盘切换页签按需加载日志，步骤详情独立关闭', async () => {
    const wrapper = mount(TaskDetail, { attachTo: document.body });
    await wrapper.vm.open(1);
    await flushPromises();
    const dialog = document.querySelector<HTMLDialogElement>('.tc-detail-dialog')!;
    const tabs = dialog.querySelector<HTMLElement>('[role=tablist]')!;
    tabs.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true, cancelable: true }));
    await flushPromises();
    expect(tasksApi.logs).toHaveBeenCalledTimes(1);
    expect(dialog.querySelector('[data-detail-tab=logs]')?.getAttribute('aria-selected')).toBe('true');
    const inspect = dialog.querySelector<HTMLButtonElement>('.tc-step-inspect')!;
    inspect.focus(); inspect.click();
    await flushPromises();
    const stepDialog = dialog.querySelector<HTMLDialogElement>('.tc-step-dialog')!;
    expect(stepDialog.open).toBe(true);
    expect(stepDialog.textContent).toContain('阶段事件（1）');
    stepDialog.dispatchEvent(new Event('cancel', { cancelable: true }));
    await flushPromises();
    expect(stepDialog.open).toBe(false);
    expect(dialog.open).toBe(true);
    expect(document.activeElement).toBe(inspect);
    wrapper.unmount();
  });
  it('标题滚轮路由到正文，嵌套步骤弹窗滚动不会移动外层正文', async () => {
    const wrapper = mount(TaskDetail, { attachTo: document.body });
    await wrapper.vm.open(1); await flushPromises();
    const dialog = document.querySelector<HTMLDialogElement>('.tc-detail-dialog')!;
    const content = dialog.querySelector<HTMLElement>('.tc-detail-content')!;
    Object.defineProperties(content, { scrollHeight: { value: 1000 }, clientHeight: { value: 200 } });
    dialog.querySelector('.tc-detail-header')!.dispatchEvent(new WheelEvent('wheel', { deltaY: 80, bubbles: true, cancelable: true }));
    expect(content.scrollTop).toBe(80);
    dialog.querySelector<HTMLButtonElement>('.tc-step-inspect')!.click(); await flushPromises();
    const stepDialog = dialog.querySelector<HTMLDialogElement>('.tc-step-dialog')!;
    const stepContent = stepDialog.querySelector<HTMLElement>('.tc-step-dialog-body')!;
    Object.defineProperties(stepContent, { scrollHeight: { value: 800 }, clientHeight: { value: 100 } });
    stepDialog.querySelector('header')!.dispatchEvent(new WheelEvent('wheel', { deltaY: 40, bubbles: true, cancelable: true }));
    expect(stepContent.scrollTop).toBe(40);
    expect(content.scrollTop).toBe(80);
    const nativeScroll = new WheelEvent('wheel', { deltaY: 40, bubbles: true, cancelable: true });
    stepContent.dispatchEvent(nativeScroll);
    expect(nativeScroll.defaultPrevented).toBe(false);
    expect(content.scrollTop).toBe(80);
    wrapper.unmount();
  });
  it('日志保留技术字段和缺失时间，并显示浏览器时区', async () => {
    vi.mocked(tasksApi.logs).mockResolvedValue({ ok: true, items: [{ message: '无时间记录', fields: { http_status: 409, empty: '', step_state: 'failed' } }],
      next_cursor: 20, available: true, has_more: false, run_terminal: true });
    const wrapper = mount(TaskDetail, { attachTo: document.body });
    await wrapper.vm.open(1); await flushPromises();
    document.querySelector<HTMLButtonElement>('[data-detail-tab=logs]')!.click(); await flushPromises();
    const panel = document.querySelector('#tc-detail-panel-logs')!;
    expect(panel.textContent).toContain('时间缺失');
    expect(panel.textContent).toContain('"http_status": 409');
    expect(panel.textContent).not.toContain('step_state');
    expect(document.querySelector('.tc-detail-footer')?.textContent).toContain(Intl.DateTimeFormat().resolvedOptions().timeZone);
    wrapper.unmount();
  });
  it('整页500事件保留技术证据和展开状态，切换页签不裁剪记录', async () => {
    const items = Array.from({ length: 500 }, (_, index) => ({ id: index + 1, stage: 'email_otp',
      created_at: '2026-01-01T00:00:00Z', message: `事件证据 ${index + 1}`,
      detail: { step_state: index === 499 ? 'failed' : 'running', evidence: { sequence: index + 1 } } }));
    vi.mocked(tasksApi.events).mockResolvedValue({ ok: true, items, next_after_id: 500, has_more: false });
    const wrapper = mount(TaskDetail, { attachTo: document.body });
    await wrapper.vm.open(1); await flushPromises();
    const panel = document.querySelector('#tc-detail-panel-events')!;
    expect(panel.querySelectorAll('.tc-event')).toHaveLength(500);
    expect(panel.querySelectorAll('.tc-event .tc-technical pre')).toHaveLength(500);
    expect(panel.querySelector('.tc-event:last-of-type')?.textContent).toContain('事件证据 500');
    expect(panel.querySelector('.tc-event:last-of-type pre')?.textContent).toContain('"sequence": 500');
    expect(panel.querySelectorAll('.tc-event--error')).toHaveLength(1);
    const expanded = panel.querySelector<HTMLDetailsElement>('.tc-technical')!;
    expanded.open = true;
    document.querySelector<HTMLButtonElement>('[data-detail-tab=logs]')!.click(); await flushPromises();
    document.querySelector<HTMLButtonElement>('[data-detail-tab=events]')!.click(); await flushPromises();
    expect(panel.querySelectorAll('.tc-event')).toHaveLength(500);
    expect(panel.querySelector('.tc-technical')).toBe(expanded);
    expect(expanded.open).toBe(true);
    wrapper.unmount();
  });
});

describe('任务进度证据', () => {
  const progress = (failure: Progress['failure']): Progress => ({ task_id: 1, run_id: 10, revision: '1',
    main_steps: [], outcome: { status: 'failed' }, failure });
  it('具体分类修正历史失败位置，保留原始失败字段', () => {
    const data = progress({ label: '校验 Token', stage: 'access_token', message: 'Roxy 浏览器登录未完成',
      error_info: { stage: 'remote_sync', summary: '原单查询 HTTP 404' } });
    const wrapper = mount(TaskProgress, { props: { progress: data, filter: null, active: true, context: '1:10' } });
    expect(wrapper.text()).toContain('失败位置：原单状态查询');
    expect(wrapper.text()).toContain('原单查询 HTTP 404');
    expect(wrapper.find('.tc-task-failure summary').text()).not.toContain('校验 Token');
    expect(wrapper.find('.tc-task-failure pre').text()).toContain('校验 Token');
    expect(data.failure?.message).toBe('Roxy 浏览器登录未完成');
    wrapper.unmount();
  });
  it('逐国具体原因取代重复聚合文案，自动刷新 AT 主因仍优先显示', async () => {
    const data = progress({ stage: 'plan_request', label: '查询套餐', message: 'JP：本地 AT 已过期；VN：服务端返回 HTTP 401',
      country_failures: [{ country: 'JP', summary: '本地检查发现 AT 已过期，未发起套餐请求' }, { country: 'VN', summary: '服务端返回 HTTP 401 <拒绝>' }, { country: 'IN' }] });
    const wrapper = mount(TaskProgress, { props: { progress: data, filter: null, active: true, context: '1:10' } });
    expect(wrapper.text()).toContain('JP：本地检查发现 AT 已过期，未发起套餐请求');
    expect(wrapper.html()).toContain('&lt;拒绝&gt;');
    expect(wrapper.text()).toContain('IN：诊断记录不完整');
    expect(wrapper.find('.tc-task-failure summary').text()).not.toContain('JP：本地 AT 已过期；VN：服务端返回 HTTP 401');
    expect(wrapper.find('.tc-task-failure pre').text()).toContain('JP：本地 AT 已过期；VN：服务端返回 HTTP 401');
    await wrapper.setProps({ progress: progress({ ...data.failure, message: '自动刷新 AT 失败：MFA 验证被拒绝',
      error_info: { summary: '自动刷新 AT 失败：MFA 验证被拒绝', auto_refresh_at_failed: true } }) });
    expect(wrapper.text().indexOf('自动刷新 AT 失败：MFA 验证被拒绝')).toBeLessThan(wrapper.text().indexOf('JP：本地检查发现'));
    wrapper.unmount();
  });
  it('调试暂停保留运行原始状态，并按原时间展示阶段事件', async () => {
    const data: Progress = { ...progress(null), outcome: { status: 'running' }, debug_pause: { state: 'paused', paused_at: '2026-01-01T00:00:10Z' },
      main_steps: [{ id: 'auth', label: '登录验证', state: 'running', display_status: 'debug_paused', started_at: '2026-01-01T00:00:00Z',
        debug_pause: { paused_at: '2026-01-01T00:00:10Z' }, attempts: [{ state: 'failed', created_at: '2026-01-01T00:00:09Z', message: '阶段事件证据' }] }] };
    const wrapper = mount(TaskProgress, { props: { progress: data, filter: null, active: true, context: '1:10' }, attachTo: document.body });
    expect(wrapper.text()).toContain('调试暂停');
    expect(wrapper.text()).toContain('10.0 秒');
    await wrapper.find('.tc-step-inspect').trigger('click'); await flushPromises();
    expect(wrapper.text()).toContain('阶段事件（1）');
    expect(wrapper.text()).toContain('阶段事件证据');
    expect(wrapper.text()).not.toContain('尝试记录');
    expect(data.main_steps[0]?.state).toBe('running');
    expect(data.outcome.status).toBe('running');
    wrapper.unmount();
  });
  it('事件时间线通过 event_ids 与内联查活回退关联主步骤，不再显示未关联步骤', async () => {
    vi.mocked(tasksApi.detail).mockResolvedValue({ ok: true, task: { id: 9, task_type: 'sentinel_maintenance_check', status: 'running',
      last_run_id: 90, runs: [{ id: 90, status: 'running', run_no: 1 }] } });
    vi.mocked(tasksApi.progress).mockResolvedValue({ ok: true, progress: { task_id: 9, run_id: 90, revision: '1',
      main_steps: [
        { id: 'refresh_token', label: '刷新 AT', state: 'running', raw_stages: ['refresh_token'] },
        { id: 'sentinel_check', label: '检查 Sentinel 资源', state: 'success', raw_stages: [], event_ids: ['102'] },
      ],
      outcome: { status: 'running' } } });
    vi.mocked(tasksApi.events).mockResolvedValue({ ok: true, items: [
      { id: 101, stage: 'nested_live_check', message: '内联触发查活与刷新' },
      { id: 102, stage: 'reconcile', message: '完成结果核验' },
    ], next_after_id: 102, has_more: false });
    const wrapper = mount(TaskDetail, { attachTo: document.body });
    try {
      await wrapper.vm.open(9); await flushPromises();
      expect(document.querySelector('.tc-detail-header h2')?.textContent).toContain('Sentinel 维护检查');
      const events = [...document.querySelectorAll('#tc-detail-panel-events .tc-event')];
      expect(events).toHaveLength(2);
      expect(events[0]?.querySelector('.tc-event-stage')?.textContent).toBe('内联查活与刷新');
      expect(events[0]?.querySelector('.tc-event-step')?.textContent).toBe('刷新 AT');
      expect(events[1]?.querySelector('.tc-event-stage')?.textContent).toBe('结果核验');
      expect(events[1]?.querySelector('.tc-event-step')?.textContent).toBe('检查 Sentinel 资源');
    } finally { wrapper.unmount(); }
  });
  it('内联刷新子阶段失败不被外层 preflight 分类覆盖，保留主步骤与子阶段中文定位', () => {
    const data = progress({ step_id: 'refresh_token', label: '刷新 Token', stage: 'login_password',
      message: 'Protocol v2 认证未完成', error_info: { stage: 'preflight', summary: '密码提交后未取得有效响应或下一步页面' } });
    const wrapper = mount(TaskProgress, { props: { progress: data, filter: null, active: true, context: '1:10' } });
    expect(wrapper.find('.tc-task-failure summary').text()).toContain('失败位置：刷新 Token · 账号密码');
    expect(wrapper.find('.tc-task-failure summary').text()).not.toContain('失败位置：配置预检');
    wrapper.unmount();
  });
});
