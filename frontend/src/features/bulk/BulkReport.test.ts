import {mount} from '@vue/test-utils';
import {describe, expect, it, vi} from 'vitest';
import BulkReport from './BulkReport.vue';
import {mountBulkReport} from './mountBulkReport';
import {duration,resultText,businessGroups,projectTarget} from './bulkDetailPresentation';

describe('报告挂载与既有外壳的接口', () => {
  it('替换回退视图，更新旧报告时保留原生展开状态，失败时提供原有重试动作', () => {
    const host = document.createElement('div');
    host.textContent = '旧报告占位';
    const operationKey = 'plan_check';
    const report = {
      operation_key: operationKey,
      view: {kind: 'round', round_no: 2},
      phase: 'running',
      business_summary: {'country_query.failed': 0},
      totals: {accounts: 5},
    };
    const outerClick = vi.fn();
    host.addEventListener('click', outerClick);
    const callbacks = {formatDateTime: () => '格式化时间', onRetry: vi.fn()};
    const handle = mountBulkReport(host, {operationKey, report: null, ...callbacks});
    expect(host.textContent).not.toContain('旧报告占位');
    expect(host.querySelector('[role=status]')?.textContent).toContain('正在汇总');
    handle.setView({operationKey, report, ...callbacks});
    expect(host.textContent).toContain('更新于 格式化时间');
    const more = host.querySelector('details')!;
    more.open = true;
    handle.setView({
      operationKey,
      report: {...report, phase: 'completed'},
      error: '<img src=x>',
      ...callbacks,
    });
    expect(host.textContent).toContain('查套餐完成报告');
    expect(host.textContent).toContain('重跑 1 · 固定名单');
    expect(host.querySelector('details')?.open).toBe(true);
    expect(host.querySelector('[role=alert]')?.textContent).toBe('<img src=x>');
    expect(host.querySelector('img')).toBeNull();
    host.querySelector<HTMLButtonElement>('button[data-bulk-action="report-refresh"]')!.click();
    expect(callbacks.onRetry).toHaveBeenCalledTimes(1);
    expect(outerClick).not.toHaveBeenCalled();
    handle.setView({operationKey: 'token_refresh', report: null, ...callbacks});
    expect(host.textContent).not.toContain('固定名单');
    expect(host.querySelector('[role=alert]')).toBeNull();
    handle.destroy();
    expect(host.textContent).toBe('');
  });
});

describe('六种报告的服务端事实展示', () => {
  it.each([
    ['plan_check', '查套餐'],
    ['token_refresh', '刷新 AT'],
    ['password_setup', '补密码'],
    ['twofa_setup', '补 2FA'],
    ['codex_retry', '补 Codex'],
    ['account_completion', '组合补全'],
  ])('%s标题与功能统计', (operation_key, name) => {
    const wrapper = mount(BulkReport, {
      props: {
        report: {
          operation_key,
          phase: 'completed',
          view: {kind: 'current'},
          totals: {accounts: 2, success: 1, failed: 1, active: 0},
          duration: {sample_count: 0, avg_seconds: null},
          business_summary: {'account.token_refresh.unconfirmed': 1},
        },
        formatDateTime: String,
      },
    });
    expect(wrapper.text()).toContain(`${name}完成报告`);
    expect(wrapper.text()).toContain('AT 刷新失败');
    expect(wrapper.text()).toContain('暂无有效耗时样本');
    expect(wrapper.find('.bulk-report-durations').text()).toContain('—');
    expect(wrapper.text().includes('AT 检查与自动刷新')).toBe(operation_key === 'plan_check');
  });
  it('未固定名单仅显示准备或取消说明，不伪造数字', () => {
    for (const phase of ['preparing', 'completed']) {
      const wrapper = mount(BulkReport, {
        props: {
          report: {operation_key: 'plan_check', population_ready: false, phase},
          formatDateTime: String,
        },
      });
      expect(wrapper.find('.bulk-report-outcomes').exists()).toBe(false);
      expect(wrapper.text()).toContain(phase === 'preparing' ? '账号名单准备中' : '该轮名单未固定');
    }
  });
  it('未知操作不显示已有操作的报告外壳', () => {
    const wrapper = mount(BulkReport, {
      props: {report: {operation_key: 'unknown'}, formatDateTime: String},
    });
    expect(wrapper.find('section').exists()).toBe(false);
  });
  it('未知不等于0，优惠重叠、套餐未知、AT待确认及汇总失败语义完整', () => {
    const wrapper = mount(BulkReport, {
      props: {
        report: {
          operation_key: 'plan_check',
          phase: 'running',
          projection: {state: 'failed'},
          totals: {success: null, failed: 0},
          offers: {
            with_offer_accounts: 2,
            by_plan: [{plan: 'plus', accounts: 2, kinds: [{kind: 'half_price', accounts: 2}]}],
          },
          plans: [
            {plan: 'unknown', accounts: 9},
            {plan: 'plus', accounts: 1},
          ],
          duration: {sample_count: 1, avg_seconds: 0, min_seconds: 0, max_seconds: 0, missing_count: 2},
          at_refresh: {unknown_accounts: 3},
        },
        formatDateTime: String,
      },
    });
    expect(wrapper.find('.bulk-report-outcomes').text()).toContain('—');
    expect(wrapper.text()).toContain('0 秒');
    expect(wrapper.text()).toContain('尚未收齐');
    expect(wrapper.text()).toContain('分项数量可能重叠');
    expect(wrapper.text()).toContain('远端拒绝不等于本地过期');
    expect(wrapper.findAll('.bulk-report-plan-list dt').map((x) => x.text())).toEqual([
      'Plus',
      '尚未确认',
    ]);
    expect(wrapper.text()).toContain('2 个已结束账号缺少有效耗时');
    expect(
      wrapper.findAll('.bulk-report-rail > span').every((x) => !x.attributes('style')?.includes('NaN')),
    ).toBe(true);
  });
  it('六种结果、不确定凭证和国家项维持含义，目标/账号/任务ID彼此独立',()=>{
    expect(resultText({refresh_outcome:'unconfirmed'})).toBe('本轮 AT 刷新失败');
    expect(resultText({credential_confirmation:'unconfirmed',existing_asset_preserved:true})).toContain('已有可用凭证保留');
    expect(resultText({confirmation:'confirmed'})).toContain('变更方式未记录');
    expect(resultText({query_outcome:'success',confirmed_no_offer:true})).toContain('确认无优惠');
    expect(resultText({required_steps:['password','twofa'],completed_steps:['password'],pending_steps:['twofa']})).toContain('待完成 2FA');
    expect(duration(null)).toBe('—');expect(duration(0)).toBe('0 秒');
    expect(businessGroups({'country_query.failed':2})[0]?.items[0]?.unit).toBe('项');
    expect(projectTarget({canonical_target_id:'9007199254740993',account_id:'9007199254740994',owned_task_id:'9007199254740995',owned_run_id:'9007199254740996',blocker_task_id:'9007199254740997'})).toMatchObject({
      id:'9007199254740993',accountId:'9007199254740994',taskId:'9007199254740995',runId:'9007199254740996',blockerTaskId:'9007199254740997',
    });
  });
});
