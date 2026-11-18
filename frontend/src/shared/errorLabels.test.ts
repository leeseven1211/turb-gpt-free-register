import {describe, expect, it} from 'vitest';
import catalog from '../generated/task-error-labels.json';
import {shortErrorLabel} from './errorLabels';

describe('同源错误短语适配', () => {
  it('所有生成错误码均可用于列表，文案不超过十字', () => {
    for (const [field, values] of [['code', catalog.codeLabels], ['cause_code', catalog.causeCodeLabels], ['cause_display_code', catalog.displayCodeLabels], ['category', catalog.categoryLabels]] as const) {
      for (const [code, expected] of Object.entries(values)) {
        const label = shortErrorLabel({[field]: code});
        expect(label, code).toBe(expected);
        expect([...label].length, code).toBeLessThanOrEqual(10);
      }
    }
  });
  it('优先具体原因，动态HTTP错误保留事实，不根据401或原文判封号', () => {
    expect(shortErrorLabel({code: 'external.email', cause_code: 'email_otp_timeout'})).toBe(catalog.causeCodeLabels.email_otp_timeout);
    expect(shortErrorLabel({cause_display_code: 'LINK-HTTP-401', code: 'external.extract_link.rejected'})).toBe('提链请求未授权');
    expect(shortErrorLabel({cause_display_code: 'LINK-HTTP-429'})).toBe('提链请求受限流');
    expect(shortErrorLabel({cause_display_code: 'LINK-HTTP-503'})).toBe('提链服务端异常');
    expect(shortErrorLabel({summary: '401 deactivated'})).toBe(catalog.fallback);
    expect(shortErrorLabel({code: '__proto__'})).toBe(catalog.fallback);
  });
});
