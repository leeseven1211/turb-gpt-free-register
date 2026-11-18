import {mount} from '@vue/test-utils';
import {describe, expect, it} from 'vitest';
import CursorPagination from './CursorPagination.vue';

describe('游标列表分页', () => {
  it('只显示当前页数量与可用方向，不编造总页数或数字跳页', async () => {
    const wrapper = mount(CursorPagination, {props: {hasPrevious: false, nextCursor: 'opaque.next', itemCount: 20, label: '批次分页'}});
    expect(wrapper.get('nav').attributes('aria-label')).toBe('批次分页');
    expect(wrapper.text()).toContain('本页 20 个');
    expect(wrapper.text()).not.toMatch(/第\s*\d+\s*页|共\s*\d+|\/\s*\d+/);
    expect(wrapper.find('input').exists()).toBe(false);
    expect(wrapper.get('[data-cursor-previous]').attributes('disabled')).toBeDefined();
    await wrapper.get('[data-cursor-next]').trigger('click');
    expect(wrapper.emitted('next')).toEqual([[]]);
  });

  it('直达游标没有前页历史时可以回到起点，不把它标成第一页', async () => {
    const wrapper = mount(CursorPagination, {props: {hasPrevious: false, nextCursor: null, itemCount: 3, hasCursor: true}});
    expect(wrapper.get('[data-cursor-next]').attributes('disabled')).toBeDefined();
    expect(wrapper.get('[data-cursor-previous]').attributes('disabled')).toBeDefined();
    await wrapper.get('[data-cursor-first]').trigger('click');
    expect(wrapper.emitted('first')).toEqual([[]]);
    expect(wrapper.text()).not.toMatch(/第\s*1\s*页/);
  });

  it('有访问历史才允许返回上一页，加载中所有方向均不能触发', async () => {
    const wrapper = mount(CursorPagination, {props: {hasPrevious: true, nextCursor: 'next', hasCursor: true, itemCount: 1}});
    await wrapper.get('[data-cursor-previous]').trigger('click');
    expect(wrapper.emitted('previous')).toEqual([[]]);
    await wrapper.setProps({busy: true});
    expect(wrapper.get('nav').attributes('aria-busy')).toBe('true');
    expect(wrapper.findAll('button').every(button => button.attributes('disabled') !== undefined)).toBe(true);
    await wrapper.get('[data-cursor-previous]').trigger('click');
    await wrapper.get('[data-cursor-next]').trigger('click');
    await wrapper.get('[data-cursor-first]').trigger('click');
    expect(wrapper.emitted('previous')).toEqual([[]]);
    expect(wrapper.emitted('next')).toBeUndefined();
    expect(wrapper.emitted('first')).toBeUndefined();
  });

  it('空页保持零数量，下一游标可用时仍允许继续读取', async () => {
    const wrapper = mount(CursorPagination, {props: {hasPrevious: false, nextCursor: 'resume', itemCount: 0}});
    expect(wrapper.text()).toContain('本页 0 个');
    await wrapper.get('[data-cursor-next]').trigger('click');
    expect(wrapper.emitted('next')).toEqual([[]]);
  });
});
