// @vitest-environment jsdom
import {mount} from '@vue/test-utils';
import {describe, expect, it} from 'vitest';
import ListPagination from './ListPagination.vue';

describe('通用列表分页', () => {
  it('大列表保留首尾和当前页邻近入口，并显示当前记录范围', async () => {
    const wrapper = mount(ListPagination, {props: {page: 50, size: 20, total: 2010}});
    expect(wrapper.get('nav').attributes('aria-label')).toBe('列表分页');
    expect(wrapper.get('.list-pagination__range').text()).toBe('981–1,000 / 共 2,010 条');
    expect(wrapper.findAll('.list-pagination__number').map(button => button.text())).toEqual(['1', '49', '50', '51', '101']);
    expect(wrapper.findAll('.list-pagination__ellipsis')).toHaveLength(2);
    expect(wrapper.get('[aria-current="page"]').text()).toBe('50');
    await wrapper.get('button[aria-label="第 101 页"]').trigger('click');
    expect(wrapper.emitted('update:page')).toEqual([[101]]);
    await wrapper.setProps({page: 101});
    expect(wrapper.get('.list-pagination__range').text()).toBe('2,001–2,010 / 共 2,010 条');
    expect(wrapper.get('.list-pagination__next').attributes('disabled')).toBeDefined();
  });

  it('提交跳页支持任意有效页码，越界输入归入首尾页', async () => {
    const wrapper = mount(ListPagination, {props: {page: 3, size: 20, total: 125}});
    const input = wrapper.get('input[aria-label="跳转页码"]');
    await input.setValue('6');
    await wrapper.get('form').trigger('submit');
    expect(wrapper.emitted('update:page')?.at(-1)).toEqual([6]);
    await input.setValue('999');
    await wrapper.get('form').trigger('submit');
    expect(wrapper.emitted('update:page')?.at(-1)).toEqual([7]);
    expect((input.element as HTMLInputElement).value).toBe('7');
    await input.setValue('0');
    await wrapper.get('form').trigger('submit');
    expect(wrapper.emitted('update:page')?.at(-1)).toEqual([1]);
  });

  it('拒绝空值、小数和非数字，不发出无效翻页请求', async () => {
    const wrapper = mount(ListPagination, {props: {page: 1, size: 20, total: 125}});
    const input = wrapper.get('input');
    for (const value of ['', '2.5', 'text', '1e2']) {
      await input.setValue(value);
      await wrapper.get('form').trigger('submit');
      expect(input.attributes('aria-invalid')).toBe('true');
      expect(wrapper.get('[role="alert"]').text()).toBe('请输入整数页码');
    }
    expect(wrapper.emitted('update:page')).toBeUndefined();
    await input.setValue('2');
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
  });

  it('空列表保持零条统计，加载期间不能翻页或修改每页条数', async () => {
    const wrapper = mount(ListPagination, {props: {page: 1, size: 20, total: 0}});
    expect(wrapper.get('.list-pagination__range').text()).toBe('共 0 条');
    expect(wrapper.findAll('button').every(button => button.attributes('disabled') !== undefined)).toBe(true);
    expect(wrapper.get('input').attributes('disabled')).toBeDefined();
    await wrapper.setProps({total: 125, busy: true});
    expect(wrapper.get('nav').attributes('aria-busy')).toBe('true');
    expect(wrapper.findAll('button,input,select').every(control => control.attributes('disabled') !== undefined)).toBe(true);
    await wrapper.get('form').trigger('submit');
    await wrapper.get('select').trigger('change');
    expect(wrapper.emitted('update:page')).toBeUndefined();
    expect(wrapper.emitted('update:size')).toBeUndefined();
  });

  it('修改自定义每页条数回到第一页，页数减少后更新跳页输入', async () => {
    const wrapper = mount(ListPagination, {props: {page: 8, size: 10, total: 125, pageSizes: [10, 25, 50], label: '账号列表分页'}});
    expect(wrapper.get('nav').attributes('aria-label')).toBe('账号列表分页');
    await wrapper.get('select').setValue('25');
    expect(wrapper.emitted('update:page')).toEqual([[1]]);
    expect(wrapper.emitted('update:size')).toEqual([[25]]);
    await wrapper.setProps({page: 1, size: 25});
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('1');
    await wrapper.get('input').setValue('5');
    await wrapper.setProps({total: 20});
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('1');
    expect(wrapper.get('input').attributes('disabled')).toBeDefined();
    expect(wrapper.get('.list-pagination__range').text()).toBe('1–20 / 共 20 条');
  });
});
