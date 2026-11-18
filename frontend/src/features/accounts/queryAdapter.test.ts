import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {runInNewContext} from 'node:vm';
import {describe, expect, it, vi} from 'vitest';
import {createAccountQueryAdapter, type AccountQueryAdapter} from './queryAdapter';

const source = readFileSync(resolve(process.cwd(), '../webui/static/js/shared/account-query.js'), 'utf8');
function setup() {
  const sandbox = {window: {} as {AccountQuery: AccountQueryAdapter}, URLSearchParams,
    accountListQueryParams() { throw new Error('新适配器不得从旧DOM重读查询'); }};
  runInNewContext(source, sandbox, {filename: 'account-query.js'});
  const legacy = sandbox.window.AccountQuery;
  return {legacy, adapter: createAccountQueryAdapter(legacy)};
}
function plain(value: unknown) { return JSON.parse(JSON.stringify(value)); }

describe('AccountQuery 唯一适配', () => {
  it('空查询与规范化对象完整保留既有v1结构，不引入第二套缺省值', () => {
    const {adapter} = setup();
    expect(plain(adapter.normalize())).toEqual({
      schema_version: 1, entity: 'account', archived: '0', q: '', date_from: '', date_to: '', plan: [],
      filters: {id: '', source: [], registration_driver: [], token: [], password: [], promotion: [],
        totp: [], risk: [], codex: [], account_status: [], email_status: [], email: ''},
      order: [{field: 'id', direction: 'desc'}], limit: null,
    });
  });

  it('完整旧参数往返保留文本逗号、大ID、全部枚举和稳定顺序', () => {
    const {adapter, legacy} = setup();
    const params = new URLSearchParams({
      archived: 'all', q: '协议/jp 备注:"a/b 待整理"', date_from: '2026-11-01', date_to: '2026-11-15',
      email: '姓名,别名+mail@example.test', plan: 'unqueried,free,free', id: '9007199254740993',
      source: 'outlook,icloud_hide', registration_driver: 'protocol_oss_2,future_driver',
      token: 'none,expired', password: 'none', promotion: 'discount,none', totp: 'disabled',
      risk: 'pending', codex: 'future_state', account_status: 'deactivated', email_status: 'invalid', limit: '500',
    });
    const input = params.toString();
    const result = adapter.fromLegacy(params);
    expect(plain(result)).toEqual(plain(legacy.fromLegacy(params)));
    expect(result.filters.id).toBe('9007199254740993');
    expect(result.filters.email).toBe('姓名,别名+mail@example.test');
    expect(result.q).toBe('协议/jp 备注:"a/b 待整理"');
    expect(result.plan).toEqual(['free', 'unqueried']);
    expect(result.filters.promotion).toEqual(['discount', 'none']);
    expect(result.limit).toBe(500);
    const serialized = adapter.toLegacy(result, {paged: '1', page: 3, page_size: 20});
    expect(Object.fromEntries(serialized)).toEqual({
      paged: '1', page: '3', page_size: '20', archived: 'all', q: '协议/jp 备注:"a/b 待整理"',
      date_from: '2026-11-01', date_to: '2026-11-15', email: '姓名,别名+mail@example.test', plan: 'free,unqueried',
      id: '9007199254740993', source: 'icloud_hide,outlook', registration_driver: 'future_driver,protocol_oss_2',
      token: 'expired,none', password: 'none', promotion: 'discount,none', totp: 'disabled',
      risk: 'pending', codex: 'future_state', account_status: 'deactivated', email_status: 'invalid',
    });
    expect(serialized.toString()).toBe(legacy.toLegacy(result, {paged: '1', page: 3, page_size: 20}).toString());
    expect(serialized.has('limit')).toBe(false);
    expect(params.toString()).toBe(input);
  });

  it('只委托注入的真实toLegacy处理参数，保留它返回的URLSearchParams', () => {
    const {legacy} = setup();
    const serialize = vi.spyOn(legacy, 'toLegacy');
    const adapter = createAccountQueryAdapter(legacy);
    const query = adapter.normalize({q: '备注:"a/b"'});
    const paging = {paged: '1', page: 2, page_size: 10};
    const result = adapter.toLegacy(query, paging);
    expect(serialize).toHaveBeenCalledExactlyOnceWith(query, paging);
    expect(result).toBe(serialize.mock.results[0]!.value);
    expect(result.get('q')).toBe('备注:"a/b"');
  });

  it('JS既有宽松行为不被批次严格规则替代：空格大小写、未知值和日期原样交给服务端', () => {
    const {adapter} = setup();
    const raw = {archived: 'TRUE', q: '  ID:#17  ', date_from: '2026-11-01T00:00:00', date_to: '',
      plan: ['Plus', 'free'], filters: {id: '  #17,18  ', email: '  Test+Alias@example.test  ',
        source: [' Outlook ', 'outlook'], registration_driver: ['future_driver'],
        promotion: ['discount']}};
    const before = JSON.stringify(raw);
    const query = adapter.normalize(raw);
    expect(query.archived).toBe('TRUE');
    expect(query.q).toBe('ID:#17');
    expect(query.date_from).toBe('2026-11-01T00:00:00');
    expect(query.filters.id).toBe('#17,18');
    expect(query.filters.email).toBe('Test+Alias@example.test');
    expect(query.filters.source).toEqual([' Outlook ', 'outlook']);
    expect(query.filters.registration_driver).toEqual(['future_driver']);
    expect(query.filters.promotion).toEqual(['discount']);
    expect(query.plan).toEqual(['Plus', 'free']);
    expect(JSON.stringify(raw)).toBe(before);
  });

  it('fromLegacy字符串入口不依赖DOM，保留空键与q中的引号转义和斜杠', () => {
    const {adapter} = setup();
    const query = adapter.fromLegacy('archived=only&q=note%3A%22a%2Fb+%5C%22quoted%5C%22%22&email=a%2Bb%40example.test&id=%230017&plan=');
    expect(query.archived).toBe('only');
    expect(query.q).toBe('note:"a/b \\"quoted\\""');
    expect(query.filters.email).toBe('a+b@example.test');
    expect(query.filters.id).toBe('#0017');
    expect(query.plan).toEqual([]);
    expect(adapter.toLegacy(query).get('q')).toBe('note:"a/b \\"quoted\\""');
  });

  it('旧trial别名保持既有JS表现，未在适配器私自改成promotion', () => {
    const {adapter, legacy} = setup();
    const query = adapter.fromLegacy('trial=eligible&archived=include');
    expect(plain(query)).toEqual(plain(legacy.fromLegacy('trial=eligible&archived=include')));
    expect(query.archived).toBe('include');
    expect(query.filters.promotion).toEqual([]);
    expect(adapter.toLegacy(query).has('trial')).toBe(false);
  });
});

