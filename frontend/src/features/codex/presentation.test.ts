import {describe, expect, it} from 'vitest';
import type {CodexRow} from '../../api/codex';
import {credentialStatus, oauthStatus} from './presentation';
import {clearFilter, codexColumns, facetLabel, filterChips} from './filterDefinitions';

const row = (fields: Partial<CodexRow> = {}): CodexRow => ({filename: 'synthetic.json', ...fields});
const filters = () => ({q: '', plan: '', status: '', oauth_status: '', account_id: '', sub2api_id: '', date_from: '', date_to: '', expired_date: ''});

describe('Codex 凭证事实展示', () => {
  it.each([
    {sub2api_account_id: null, sub2_sync_error: null},
    {sub2api_account_id: 150, sub2_sync_error: 'sub2api_http_error: 调度启用失败'},
  ])('有确认上传回执时显示已导出，保留后续启用结果独立事实：%j', receipt => {
    const status = credentialStatus(row({exported: false, exported_count: 0, sub2_uploaded_count: 2,
      sub2_uploaded_at: '2026-11-13T14:40:00', ...receipt}));
    expect(status).toEqual({label: '已导出', title: 'Sub2API 已上传 2 次，最近 2026-11-13T14:40:00', tone: 'success'});
    expect(status.title).not.toMatch(/已启用|导出 0 次|本地下载/);
  });
  it('上传回执与导出记录分别保留次数和时间', () => {
    const status = credentialStatus(row({exported_count: 1, exported_at: '2026-11-12T12:00:00',
      sub2_uploaded_count: 3, sub2_uploaded_at: '2026-11-13T14:40:00'}));
    expect(status).toEqual({label: '已导出',
      title: 'Sub2API 已上传 3 次，最近 2026-11-13T14:40:00；导出记录 1 次，最近 2026-11-12T12:00:00', tone: 'success'});
  });
  it.each([
    [{exported: true, exported_count: 0, sub2api_account_id: '9007199254740993'}, '已关联', 'success'],
    [{exported_count: 3, sub2api_account_id: 42}, '已导出', 'success'],
    [{exported: false, exported_count: 0}, '未导出', 'neutral'],
  ] as const)('导出与仅关联不同：%j', (input, label, tone) => {
    expect(credentialStatus(row(input))).toMatchObject({label, tone});
  });
  it('仅关联提示保留不透明 Sub2ID 和本地零下载事实', () => {
    const status = credentialStatus(row({exported: true, exported_count: 0, sub2api_account_id: '9007199254740993'}));
    expect(status.title).toContain('9007199254740993');
    expect(status.title).toContain('本地下载 0 次');
    expect(credentialStatus(row({exported_count: 2, exported_at: '2026-11-14T03:00:00Z'})).title).toContain('导出 2 次');
  });
  it.each([
    [{oauth_status: 'deactivated', sub2api_http_status: 401, oauth_reauth_required: true}, '账号停用', 'danger'],
    [{oauth_status: 'valid', sub2api_http_status: 401}, '401 失效', 'danger'],
    [{oauth_status: 'valid', oauth_reauth_required: true}, '需重授权', 'danger'],
    [{oauth_status: 'valid'}, '有效', 'success'],
    [{oauth_status: 'expiring'}, '即将过期', 'warning'],
    [{oauth_status: 'expired', oauth_refreshable: true}, '已过期', 'danger'],
    [{oauth_status: 'expired', oauth_refreshable: false}, '已过期·需重授权', 'danger'],
    [{oauth_status: 'missing'}, '缺少令牌', 'danger'],
    [{oauth_status: 'new-server-status'}, '未知', 'neutral'],
  ] as const)('OAuth事实优先级：%j', (input, label, tone) => {
    const status = oauthStatus(row(input));
    expect(status).toMatchObject({label, tone});
    expect(Array.from(status.label).length).toBeLessThanOrEqual(10);
  });
  it('标题保留时效和独立错误事实但不读取完整 token 字段', () => {
    const value = row({oauth_status: 'expired', oauth_seconds_left: -90000, oauth_expires_at: '2026-11-14T00:00:00Z', oauth_refreshable: true, sub2_uploaded_count: 2, oauth_refresh_error: '刷新受阻', sub2_sync_error: '同步待确认'});
    Object.assign(value, {access_token: 'must-not-leak', refresh_token: 'must-not-leak-either', content: 'secret-content'});
    const status = oauthStatus(value);
    expect(status.title).toContain('已过期 1天1小时');
    expect(status.title).toContain('存在 refresh_token');
    expect(status.title).toContain('已纳入 sub2 自动同步');
    expect(status.title).toContain('最近刷新失败：刷新受阻');
    expect(status.title).toContain('sub2 同步失败：同步待确认');
    expect(JSON.stringify(status)).not.toMatch(/must-not-leak|secret-content/);
  });
  it('缺失倒计时不伪装成零天有效，未知状态保持保守', () => {
    expect(oauthStatus(row({oauth_status: 'unknown', oauth_seconds_left: null})).title).not.toContain('剩余 0天');
    expect(oauthStatus(row({sub2api_http_status: 401})).label).not.toBe('账号停用');
  });
});

describe('Codex 列筛选展示', () => {
  it('八个字段定义完整覆盖现有九个查询字段，日期范围共用一列', () => {
    expect(codexColumns.map(column => [column.key, column.kind, [...column.fields]])).toEqual([
      ['q', 'text', ['q']], ['plan', 'enum', ['plan']], ['status', 'enum', ['status']],
      ['oauth_status', 'enum', ['oauth_status']], ['account_id', 'text', ['account_id']],
      ['sub2api_id', 'text', ['sub2api_id']], ['date', 'date-range', ['date_from', 'date_to']],
      ['expired_date', 'date', ['expired_date']],
    ]);
  });
  it('已选条件同栏摘要使用后端标签，未知单值完整保留，逗号文本不拆分', () => {
    const chips = filterChips({...filters(), q: 'fixture,a', plan: 'future', oauth_status: 'valid', sub2api_id: '9007199254740993'}, {oauth_status: [{value: 'valid', label: '有效凭证', count: 4}]});
    expect(chips.map(chip => [chip.key, chip.label])).toEqual([
      ['q', '邮箱 / 文件：fixture,a'], ['plan', 'Plan：Future'], ['oauth_status', 'OAuth 状态：有效凭证'], ['sub2api_id', 'Sub2API ID：9007199254740993'],
    ]);
    expect(chips.every(chip => chip.removeLabel.startsWith('清除'))).toBe(true);
    expect(filterChips({...filters(), status: 'exported,unexported'}, {})[0]?.label).toContain('exported,unexported');
  });
  it('日期区间摘要和清除一起处理两端，不清其他条件或修改输入', () => {
    const original = {...filters(), q: 'kept', date_from: '2026-11-01', date_to: '2026-11-14'};
    expect(filterChips(original, {}).find(chip => chip.key === 'date')?.label).toBe('更新时间：2026-11-01 至 2026-11-14');
    expect(clearFilter(original, 'date')).toEqual({...filters(), q: 'kept'});
    expect(original.date_from).toBe('2026-11-01');
    expect(clearFilter(original, 'unknown')).toEqual(original);
    expect(filterChips({...filters(), date_to: '2026-11-14'}, {})[0]?.label).toBe('更新时间：截至 2026-11-14');
  });
  it('筛选选项映射仍区分导出、停用、401与未知值', () => {
    expect(facetLabel('status', 'exported')).toBe('已导出');
    expect(facetLabel('oauth_status', 'deactivated')).toBe('账号停用');
    expect(facetLabel('oauth_status', 'new-server-value')).toBe('new-server-value');
    expect(facetLabel('plan', 'unqueried')).toBe('未查询');
  });
});
