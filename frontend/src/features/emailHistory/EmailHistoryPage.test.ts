import {flushPromises, mount} from '@vue/test-utils';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import EmailHistoryPage from './EmailHistoryPage.vue';

const parent = {source: 'icloud_hide', id: '4', email: 'parent@example.test'};
const first = {id: 1, email: 'parent+one@example.test', parent_id: 4, parent_email: '<script>bad</script>@example.test', source: 'icloud_hide', state: 'available', created_at: '2026-10-20', can_disable: true};
const second = {...first, id: 2, email: 'parent+two@example.test', state: 'reserved', registered_account_id: 5, root_task_id: 'root-1'};
const third = {...first, id: 3, email: 'parent+three@example.test', state: 'reserved'};
const result = (items = [first, second], total = 60) => Response.json({items, total});
const wrappers: ReturnType<typeof mount>[] = [];
function page(clipboard = vi.fn(async (_text: string) => true)) {
  const wrapper = mount(EmailHistoryPage, {attachTo: document.body, props: {clipboard}});
  wrappers.push(wrapper);
  return wrapper;
}
beforeEach(() => {Object.defineProperty(document, 'hidden', {value: false, configurable: true});});
afterEach(() => {wrappers.splice(0).forEach(w => w.unmount()); vi.unstubAllGlobals(); vi.useRealTimers(); localStorage.clear();});

it('reads only the exact parent on first entry, escapes addresses, renders ownership, and filters by source', async () => {
  const fetch = vi.fn(async (_url: string, _options: RequestInit) => result()); vi.stubGlobal('fetch', fetch);
  const wrapper = page();
  wrapper.vm.setView(parent);
  await wrapper.vm.setVisible(true); await flushPromises();
  expect(fetch).toHaveBeenCalledTimes(1);
  const [url, options] = fetch.mock.calls[0]!;
  expect(url.split('?')[0]).toBe('/api/email-derivation/allocations');
  expect(Object.fromEntries(new URL(url, location.href).searchParams)).toEqual({source: 'icloud_hide', parent_id: '4', page: '1', page_size: '50'});
  expect(options.method).toBe('GET');
  expect(wrapper.get('tbody').text()).toContain('<script>bad</script>@example.test');
  expect(wrapper.get('tbody').text()).toContain('账号 #5 · 任务 #root-1');
  expect(wrapper.get('tbody').text()).toContain('历史未领取');
  expect(wrapper.find('tbody button, tbody script').exists()).toBe(false);
  await wrapper.get('tbody input').setValue(true);
  await wrapper.get('[aria-label="筛选来源"]').trigger('click');
  await flushPromises();
  const select = document.querySelector<HTMLSelectElement>('[role=dialog] select')!;
  select.value = 'outlook'; select.dispatchEvent(new Event('change', {bubbles: true}));
  await flushPromises();
  const next = new URL(fetch.mock.calls.at(-1)![0], location.href).searchParams;
  expect(next.get('source')).toBe('outlook'); expect(next.has('parent_id')).toBe(false);
  expect(wrapper.findAll('tbody input:checked')).toHaveLength(0);
});

it('copies whole page or cross-page selections, keeps mixed check state, and corrects a vanished last page', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(result()).mockResolvedValueOnce(result([third])).mockResolvedValueOnce(result([], 0)).mockResolvedValueOnce(result([], 0));
  vi.stubGlobal('fetch', fetch);
  const clipboard = vi.fn(async (_text: string) => true);
  const wrapper = page(clipboard); await wrapper.vm.setVisible(true); await flushPromises();
  const copy = wrapper.get('[data-history-copy]');
  await copy.trigger('click'); expect(clipboard).toHaveBeenLastCalledWith([first.email, second.email].join('\n'));
  await wrapper.get('tbody input').setValue(true);
  expect((wrapper.get('thead input').element as HTMLInputElement).indeterminate).toBe(true);
  await wrapper.get('[aria-label="第 2 页"]').trigger('click'); await flushPromises();
  expect(wrapper.get('tbody').text()).toContain('历史归属');
  await wrapper.get('thead input').setValue(true); await copy.trigger('click');
  expect(clipboard).toHaveBeenLastCalledWith([first.email, third.email].join('\n'));
  await wrapper.get('thead input').setValue(false); await copy.trigger('click');
  expect(clipboard).toHaveBeenLastCalledWith(first.email);
  await wrapper.vm.refresh(); await flushPromises();
  expect(new URL(fetch.mock.calls.at(-1)![0], location.href).searchParams.get('page')).toBe('1');
  expect(wrapper.get('tbody').text()).toContain('Email Butler');
  expect((wrapper.get('thead input').element as HTMLInputElement).disabled).toBe(true);
  expect(wrapper.findAll('[aria-label="每页条数"] option').map(o => o.attributes('value'))).toEqual(['10','20','30','50','100']);
});

it('retains same-query successful rows on error, retries, and ignores late results while hidden', async () => {
  let finish!: (r: Response) => void;
  const fetch = vi.fn().mockResolvedValueOnce(result()).mockRejectedValueOnce(new Error('合成故障'))
    .mockImplementationOnce(() => new Promise(resolve => {finish = resolve;})).mockResolvedValueOnce(result([third], 1));
  vi.stubGlobal('fetch', fetch);
  const wrapper = page(); await wrapper.vm.setVisible(true); await flushPromises();
  await wrapper.vm.refresh(); await flushPromises();
  expect(wrapper.get('[role=alert]').text()).toContain('合成故障'); expect(wrapper.get('tbody').text()).toContain(first.email);
  await wrapper.get('[role=alert] button').trigger('click'); await flushPromises();
  wrapper.vm.setVisible(false);
  expect(fetch.mock.calls[2]![1].signal.aborted).toBe(true);
  await wrapper.vm.setVisible(true); await flushPromises();
  finish(result([first])); await flushPromises();
  expect(wrapper.get('tbody').text()).toContain(third.email); expect(wrapper.get('tbody').text()).not.toContain(first.email);
  expect(wrapper.find('[role=alert]').exists()).toBe(false);
});

it('combines the seven column filters, renders removable chips beside the count, and clears selected scope', async () => {
  const fetch = vi.fn(async (_url: string) => result()); vi.stubGlobal('fetch', fetch);
  const wrapper = page(); await wrapper.vm.setVisible(true); await flushPromises();
  async function open(label: string) {
    const trigger = wrapper.get(`[aria-label="筛选${label}"]`);
    await trigger.trigger('pointerdown');
    (trigger.element as HTMLButtonElement).focus();
    await trigger.trigger('click'); await flushPromises();
    const dialog = document.querySelector<HTMLElement>(`[role="dialog"][aria-label="筛选${label}"]`);
    expect(dialog, `筛选${label}；当前弹层 ${Array.from(document.querySelectorAll('[role=dialog]'), d => d.textContent).join(' / ')}`).not.toBeNull();
    return dialog!;
  }
  function set(dialog: HTMLElement, label: string, value: string) {
    const input = dialog.querySelector<HTMLInputElement | HTMLSelectElement>(`[aria-label="${label}"]`)!;
    input.value = value;
    input.dispatchEvent(new Event(input.tagName === 'SELECT' ? 'change' : 'input', {bubbles: true}));
  }
  for (const [label, value] of [['子邮箱','abc'],['母邮箱','parent'],['关联账号 / 任务','job'],['状态','retired'],['来源','outlook']]) {
    const dialog = await open(label);
    if (label === '状态') expect(Array.from(dialog.querySelectorAll('option'), el => el.value)).toEqual(['','available','disabled','reserved','used','replaced','retired']);
    if (label === '来源') expect(Array.from(dialog.querySelectorAll('option'), el => el.value)).toEqual(['all','icloud_hide','outlook']);
    set(dialog, label, value);
  }
  const dates = await open('生成时间'); set(dates, '开始日期','2026-10-01'); set(dates, '结束日期','2026-10-20'); await flushPromises();
  expect(Object.fromEntries(new URL(fetch.mock.calls.at(-1)![0],location.href).searchParams)).toEqual({
    page:'1', page_size:'50', source:'outlook', q:'abc', parent_q:'parent', related_q:'job', state:'retired', created_from:'2026-10-01', created_to:'2026-10-20',
  });
  const counts = wrapper.get('[data-email-count-row]');
  expect(counts.text()).toContain('60 条历史记录'); expect(counts.findAll('[aria-label^="移除"]')).toHaveLength(7);
  await counts.get('[aria-label="移除结束日期筛选"]').trigger('click'); await flushPromises();
  expect(new URL(fetch.mock.calls.at(-1)![0],location.href).searchParams.has('created_to')).toBe(false);
  await wrapper.get('.eh-clear').trigger('click'); await flushPromises();
  expect(Object.fromEntries(new URL(fetch.mock.calls.at(-1)![0],location.href).searchParams)).toEqual({page:'1', page_size:'50', source:'all'});
});

it('restores old proportional column widths and reports a rejected clipboard copy', async () => {
  localStorage.setItem('gpt_console_table_widths_derivations', '[5,20,20,10,10,15,10,10]');
  localStorage.setItem('gpt_console_table_total_derivations','1200');
  vi.stubGlobal('fetch', vi.fn(async () => result()));
  const wrapper = page(vi.fn(async () => false)); await wrapper.vm.setVisible(true); await flushPromises();
  const col = wrapper.findAll('col')[1].element as HTMLTableColElement;
  expect(col.style.width).toBe('240px');
  await wrapper.get('[aria-label="调整子邮箱列宽"]').trigger('keydown', {key:'ArrowRight'});
  expect(col.style.width).toBe('250px');
  expect(localStorage.getItem('gpt_console_table_total_derivations')).toBe('1210');
  await wrapper.get('.eh-reset-widths').trigger('click');
  expect(localStorage.getItem('gpt_console_table_widths_derivations')).toBeNull(); expect(col.style.width).toBe('248px');
  await wrapper.get('[data-history-copy]').trigger('click'); await flushPromises();
  expect(wrapper.get('[role=status]').text()).toContain('复制失败');
});
