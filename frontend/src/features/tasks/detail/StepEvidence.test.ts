import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import StepEvidence from './StepEvidence.vue';
import { formatDateTime } from '../presentation';
import type { Step } from './model';

const step = (extra: Partial<Step> = {}): Step => ({
  id: 'authenticate', label: '登录验证', state: 'running', ...extra,
});

describe('阶段事件的原始时间证据', () => {
  it('显示每条真实事件及安全文本，不把开始和完成记录解释为重试', () => {
    const wrapper = mount(StepEvidence, { props: { step: step({
      attempts: [
        { event_id: '9007199254740993', raw_stage: 'page', raw_stage_label: '打开页面', state: 'running', created_at: '2026-10-13T08:48:18Z', message: '<线路就绪>' },
        { event_id: '9007199254740995', raw_stage: 'page', raw_stage_label: '打开页面', state: 'success', created_at: '2026-10-13T08:49:09Z' },
        { event_id: '9007199254740997', raw_stage: 'submit_email', raw_stage_label: '提交邮箱', state: 'running', created_at: '2026-10-13T08:49:10Z' },
      ],
    }) } });
    try {
      expect(wrapper.get('details > summary').text()).toBe('阶段事件（3）');
      expect(wrapper.findAll('.tc-event-meta')).toHaveLength(3);
      expect(wrapper.findAll('.tc-event-meta time').map(time => time.text())).toEqual([
        formatDateTime('2026-10-13T08:48:18Z'),
        formatDateTime('2026-10-13T08:49:09Z'),
        formatDateTime('2026-10-13T08:49:10Z'),
      ]);
      expect(wrapper.text()).toContain('事件 9007199254740997');
      expect(wrapper.text()).toContain('<线路就绪>');
      expect(wrapper.html()).toContain('&lt;线路就绪&gt;');
      expect(wrapper.get('ol').text()).not.toMatch(/重试|尝试记录/);
    } finally { wrapper.unmount(); }
  });

  it('明确标出历史缺少的实际发生时间，并且不借用阶段开始时间', () => {
    const wrapper = mount(StepEvidence, { props: { step: step({
      started_at: '2026-10-13T09:24:23Z',
      attempts: [{
        raw_stage: 'submit_email', raw_stage_label: '提交邮箱', state: 'running',
        started_at: '2026-10-13T09:24:23Z', created_at: null, event_time_known: false,
      }],
    }) } });
    try {
      const event = wrapper.get('.tc-event-meta');
      expect(event.get('time').text()).toBe('发生时间未记录');
      expect(event.text()).not.toContain(formatDateTime('2026-10-13T09:24:23Z'));
      expect(wrapper.get('pre').text()).toContain('"started_at": "2026-10-13T09:24:23Z"');
    } finally { wrapper.unmount(); }
  });

  it('保留非法事件时间以便诊断，未声明的历史时间仍保持缺失', () => {
    const wrapper = mount(StepEvidence, { props: { step: step({
      attempts: [
        { raw_stage: 'page', state: 'running', created_at: 'not-a-time' },
        { raw_stage: 'submit_email', state: 'running', started_at: '2026-10-13T09:24:23Z' },
      ],
    }) } });
    try {
      expect(wrapper.findAll('.tc-event-meta time').map(time => time.text())).toEqual([
        '无效时间：not-a-time', '—',
      ]);
    } finally { wrapper.unmount(); }
  });
});
