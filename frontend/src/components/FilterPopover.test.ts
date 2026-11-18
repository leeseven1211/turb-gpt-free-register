// @vitest-environment jsdom
import {DOMWrapper, flushPromises, mount} from '@vue/test-utils';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import FilterPopover from './FilterPopover.vue';

const wrappers: ReturnType<typeof mount>[] = [];
beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
});
afterEach(() => { wrappers.forEach(wrapper => wrapper.unmount()); wrappers.length = 0; vi.unstubAllGlobals(); });

describe('共享列筛选浮层', () => {
  it('触发器请求打开，受控浮层承载页面提供的筛选内容并支持关闭', async () => {
    const wrapper = mount(FilterPopover, {attachTo: document.body, props: {label: '来源', open: false}, slots: {default: '<label>来源名称<input aria-label="来源名称"></label>'}});
    wrappers.push(wrapper);
    await wrapper.get('button').trigger('click');
    expect(wrapper.emitted('update:open')?.at(-1)).toEqual([true]);
    await wrapper.setProps({open: true}); await flushPromises();
    const page = new DOMWrapper(document.body);
    expect(page.get('.tc-filter-popover').attributes('aria-label')).toBe('筛选来源');
    expect(page.find('input[aria-label="来源名称"]').exists()).toBe(true);
    await page.get('button[aria-label="关闭来源筛选"]').trigger('click');
    expect(wrapper.emitted('update:open')?.at(-1)).toEqual([false]);
    await wrapper.setProps({open: false}); await flushPromises();
    expect(page.find('.tc-filter-popover').exists()).toBe(false);
  });

  it('保留筛选摘要，Escape 请求关闭且不依赖任务页面容器', async () => {
    const wrapper = mount(FilterPopover, {attachTo: document.body, props: {label: '状态', triggerLabel: '筛选', summary: '已完成', active: true, open: true}});
    wrappers.push(wrapper); await flushPromises();
    const trigger = wrapper.get('.tc-column-filter-trigger');
    expect(trigger.text()).toBe('筛选');
    expect(trigger.attributes('title')).toBe('状态：已完成');
    expect(trigger.attributes('aria-expanded')).toBe('true');
    const page = new DOMWrapper(document.body);
    await page.get('.tc-filter-popover').trigger('keydown', {key: 'Escape'});
    await flushPromises();
    expect(wrapper.emitted('update:open')?.at(-1)).toEqual([false]);
  });
});
