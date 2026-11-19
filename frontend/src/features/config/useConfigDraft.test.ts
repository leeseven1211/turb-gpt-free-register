import {describe, expect, it, vi} from 'vitest';
import {effectScope} from 'vue';
import {createConfigDraft, useConfigDraft} from './useConfigDraft';
import type {ConfigApi, ConfigField, ConfigSaveResponse} from './contracts';
import {ConfigApiError} from '../../api/config';

const fields = (): ConfigField[] => [
  {key: 'ONE', type: 'int', group: '注册与账号', label: '一', value: 1},
  {key: 'TWO', type: 'str', group: '浏览器', label: '二', value: 'saved'},
  {key: 'THREE', type: 'str', group: '系统与维护', label: '三', value: 'old'},
  {key: 'KEY', type: 'str', group: '服务', label: '密钥', value: '', secret: true, configured: true},
  {key: 'KEYS', type: 'list_str_multiline', group: '服务', label: '多个密钥', value: '', secret: true},
  {key: 'ROXY_WORKSPACE_ID', type: 'str', group: '浏览器', label: '团队', value: 'old-team'},
  {key: 'ROXY_PROJECT_ID', type: 'str', group: '浏览器', label: '项目', value: 'old-project'},
  {key: 'PROXY_POOL_WAIT_TIMEOUT', type: 'int', group: '代理', label: '超时', value: 0},
  {key: 'SMS_MAX_PRICE', type: 'str', group: '接码', label: '价格', value: ''},
  {key: 'LIST', type: 'list_str_multiline', group: '系统', label: '列表', value: ['A', 'unknown']},
];
function deferred<T>() {let resolve!: (value:T)=>void, reject!: (reason:unknown)=>void; const promise=new Promise<T>((yes,no)=>{resolve=yes;reject=no;}); return {promise,resolve,reject};}
function fixture() {
  const api: ConfigApi = {
    getSchema: vi.fn().mockResolvedValue(fields()),
    save: vi.fn().mockImplementation(async updates => ({updated: Object.keys(updates), reloaded: true})),
    invalidate: vi.fn(),
  };
  const owner = createConfigDraft({api, initialFields: fields()});
  return {owner, api};
}

describe('one configuration draft owner', () => {
  it('saves edits across three menus in one request', async () => {
    const {owner, api} = fixture();
    owner.setField('ONE', 0); owner.setField('TWO', 'new'); owner.setField('THREE', 'third');
    expect(owner.dirtyCount.value).toBe(3);
    expect((await owner.saveAll()).status).toBe('saved');
    expect(api.save).toHaveBeenCalledExactlyOnceWith({ONE: 0, TWO: 'new', THREE: 'third'});
    expect(owner.dirtyCount.value).toBe(0);
  });

  it('preserves same-key and different-key edits made during a save', async () => {
    const {owner, api} = fixture(), pending = deferred<ConfigSaveResponse>();
    vi.mocked(api.save).mockReturnValueOnce(pending.promise);
    owner.setField('ONE', 2); const saving = owner.saveAll();
    owner.setField('ONE', 3); owner.setField('TWO', 'newer');
    pending.resolve({updated: ['ONE'], reloaded: true}); await saving;
    expect(owner.readField('ONE')).toBe(3);
    expect(owner.readField('TWO')).toBe('newer');
    expect(owner.dirtyKeys.value).toEqual(['ONE', 'TWO']);
  });

  it('does not clear an edit that returns to the old saved value while posting', async () => {
    const {owner, api} = fixture(), pending = deferred<ConfigSaveResponse>();
    vi.mocked(api.save).mockReturnValueOnce(pending.promise);
    owner.setField('ONE', 2); const saving = owner.saveAll();
    owner.setField('ONE', 1);
    pending.resolve({updated: ['ONE']}); await saving;
    expect(owner.readField('ONE')).toBe(1);
    expect(owner.isDirty('ONE')).toBe(true);
  });

  it('keeps secret retain/set/clear distinct including empty array secrets', async () => {
    const {owner, api} = fixture();
    owner.setField('KEY', '');
    expect(owner.secretDraft('KEY')).toEqual({mode: 'retain'});
    expect((await owner.saveAll()).status).toBe('noop');
    owner.setSecret('KEY', {mode: 'set', value: 'new-secret'});
    owner.clearSecret('KEYS');
    await owner.saveAll();
    expect(api.save).toHaveBeenCalledExactlyOnceWith({KEY: 'new-secret', KEYS: []});
    expect(owner.readField('KEY', 'saved')).toBe('');
    expect(owner.secretDraft('KEY')).toEqual({mode: 'retain'});
  });

  it('saved subscriptions never receive secret values', async () => {
    const {owner} = fixture(), callback = vi.fn();
    owner.subscribeSaved(callback);
    owner.setField('KEY', 'do-not-leak');
    await owner.saveAll();
    expect(callback).toHaveBeenCalledTimes(1);
    expect(JSON.stringify(callback.mock.calls)).not.toContain('do-not-leak');
  });

  it('Roxy subset saves only its IDs while retaining unrelated drafts', async () => {
    const {owner, api} = fixture();
    owner.setField('ONE', 4);
    await owner.saveSubset({ROXY_WORKSPACE_ID: 'team', ROXY_PROJECT_ID: 'project'});
    expect(api.save).toHaveBeenCalledExactlyOnceWith({ROXY_WORKSPACE_ID: 'team', ROXY_PROJECT_ID: 'project'});
    expect(owner.dirtyKeys.value).toEqual(['ONE']);
  });

  it('POST failure retains drafts and exact field errors then navigates first error', async () => {
    const {owner, api} = fixture();
    vi.mocked(api.save).mockRejectedValueOnce(new ConfigApiError('invalid', 400, '', {ONE: '必须为正整数'}));
    owner.setField('ONE', 0);
    expect((await owner.saveAll()).status).toBe('validation-error');
    expect(owner.readField('ONE')).toBe(0);
    expect(owner.fieldErrors.ONE).toBe('必须为正整数');
    expect(owner.navigationTarget.value?.key).toBe('ONE');
    owner.setField('ONE', 2); expect(owner.fieldErrors.ONE).toBeUndefined();
  });

  it('ordinary edits clear the prior server error summary across fields', async () => {
    const {owner, api} = fixture();
    vi.mocked(api.save).mockRejectedValueOnce(new ConfigApiError('invalid', 400, '', {ONE: '一无效', TWO: '二无效'}));
    owner.setField('ONE', 2); owner.setField('TWO', 'draft');
    expect((await owner.saveAll()).status).toBe('validation-error');
    expect(Object.keys(owner.fieldErrors)).toEqual(['ONE', 'TWO']);
    owner.setField('ONE', 3);
    expect(owner.fieldErrors).toEqual({});
  });

  it('a successful save with failed refresh is still saved and never POSTs twice', async () => {
    const {owner, api} = fixture();
    vi.mocked(api.getSchema).mockRejectedValueOnce(new Error('offline'));
    owner.setField('ONE', 8);
    const result = await owner.saveAll();
    expect(result.status).toBe('saved'); expect(result.receipt?.refreshFailed).toBe(true);
    expect(owner.readField('ONE', 'saved')).toBe(8);
    expect(owner.dirtyCount.value).toBe(0);
    expect(api.save).toHaveBeenCalledTimes(1);
    expect(owner.refreshError.value).not.toBe('');
  });

  it('refresh updates metadata without overwriting a dirty value or secret action', async () => {
    const {owner, api} = fixture();
    owner.setField('TWO', 'draft'); owner.clearSecret('KEY');
    vi.mocked(api.getSchema).mockResolvedValueOnce(fields().map(field => ({...field, label: 'new label'})));
    await owner.refresh({force: true});
    expect(owner.readField('TWO')).toBe('draft');
    expect(owner.secretDraft('KEY')).toEqual({mode: 'clear'});
    expect(owner.field('TWO')?.label).toBe('new label');
  });

  it('preserves unknown options, list ordering and zero without normalization', async () => {
    const {owner, api} = fixture();
    owner.setField('LIST', ['unknown', 'A']); owner.setField('ONE', 0);
    await owner.saveAll();
    expect(api.save).toHaveBeenCalledExactlyOnceWith({LIST: ['unknown', 'A'], ONE: 0});
  });

  it('composite limited-empty input cannot silently save unlimited values', async () => {
    const {owner, api} = fixture();
    owner.setComposite('PROXY_POOL_WAIT_TIMEOUT', {mode: 'timed', raw: ''});
    owner.setComposite('SMS_MAX_PRICE', {mode: 'limited', raw: ''});
    expect((await owner.saveAll()).status).toBe('validation-error');
    expect(Object.keys(owner.fieldErrors)).toEqual(['PROXY_POOL_WAIT_TIMEOUT', 'SMS_MAX_PRICE']);
    expect(api.save).not.toHaveBeenCalled();
    owner.setComposite('PROXY_POOL_WAIT_TIMEOUT', {mode: 'continuous', raw: ''});
    owner.setComposite('SMS_MAX_PRICE', {mode: 'unlimited', raw: ''});
    expect(owner.fieldErrors.PROXY_POOL_WAIT_TIMEOUT).toBeUndefined();
  });

  it('does not infer Worker application from a legacy local reload', async () => {
    const {owner} = fixture();
    owner.setField('ONE', 2);
    const result = await owner.saveAll();
    expect(result.receipt?.webReloaded).toBe(true);
    expect(result.receipt?.workerApplication.state).toBe('unknown');
    expect(result.receipt?.persistedDbRevision).toBeNull();
  });

  it('keeps DB, Web, Worker and restart evidence separate', async () => {
    const {owner, api} = fixture();
    vi.mocked(api.save).mockResolvedValueOnce({
      updated: ['ONE'], persisted_db_revision: '91', local_snapshot_revision: 12,
      web_reloaded: true, worker_application: {state: 'pending', applied_db_revision: '90'},
      restart_required: ['ONE'],
    });
    owner.setField('ONE', 2);
    const result = await owner.saveAll();
    expect(result.receipt).toMatchObject({
      persistedDbRevision: '91', localSnapshotRevision: 12, webReloaded: true,
      workerApplication: {state: 'pending', applied_db_revision: '90'}, restartRequired: ['ONE'],
    });
  });

  it('does not duplicate a POST when another save is already in flight', async () => {
    const {owner, api} = fixture(), pending = deferred<ConfigSaveResponse>();
    vi.mocked(api.save).mockReturnValueOnce(pending.promise);
    owner.setField('ONE', 2); const first = owner.saveAll();
    expect((await owner.saveSubset({TWO: 'x'})).status).toBe('busy');
    pending.resolve({updated: ['ONE']}); await first;
    expect(api.save).toHaveBeenCalledTimes(1);
  });

  it('reset discards only requested fields without submitting', () => {
    const {owner, api} = fixture();
    owner.setField('ONE', 2); owner.setField('TWO', 'new');
    owner.reset(['ONE']);
    expect(owner.readField('ONE')).toBe(1); expect(owner.readField('TWO')).toBe('new');
    expect(api.save).not.toHaveBeenCalled();
  });

  it('ignores a refresh started before a newer successful save', async () => {
    const {owner, api} = fixture(), old = deferred<ConfigField[]>();
    vi.mocked(api.getSchema).mockReturnValueOnce(old.promise).mockResolvedValueOnce(
      fields().map(field => field.key === 'ONE' ? {...field, value: 9} : field),
    );
    const refresh = owner.refresh({force: true});
    owner.setField('ONE', 9); await owner.saveAll();
    old.resolve(fields()); await refresh;
    expect(owner.readField('ONE')).toBe(9);
  });

  it('does not attach validation from an old submission to a newer corrected value', async () => {
    const {owner, api} = fixture(), pending = deferred<ConfigSaveResponse>();
    vi.mocked(api.save).mockReturnValueOnce(pending.promise);
    owner.setField('ONE', 0); const saving = owner.saveAll();
    owner.setField('ONE', 3);
    pending.reject(new ConfigApiError('invalid', 400, '', {ONE: '必须为正整数'}));
    const result = await saving;
    expect(result.status).toBe('validation-error');
    expect(owner.fieldErrors.ONE).toBeUndefined();
    expect(owner.navigationTarget.value).toBeNull();
    expect(owner.readField('ONE')).toBe(3);
  });

  it('ignored save keys remain dirty and are absent from saved receipt keys', async () => {
    const {owner, api} = fixture();
    vi.mocked(api.save).mockResolvedValueOnce({updated: ['ONE'], ignored: ['TWO']});
    owner.setField('ONE', 2); owner.setField('TWO', 'draft');
    const result = await owner.saveAll();
    expect(result.receipt?.savedKeys).toEqual(['ONE']);
    expect(owner.dirtyKeys.value).toEqual(['TWO']);
  });

  it('Roxy later ID edits survive the subset response', async () => {
    const {owner, api} = fixture(), pending = deferred<ConfigSaveResponse>();
    vi.mocked(api.save).mockReturnValueOnce(pending.promise);
    const saving = owner.saveSubset({ROXY_WORKSPACE_ID: 'team1', ROXY_PROJECT_ID: 'project1'});
    owner.setField('ROXY_PROJECT_ID', 'project2');
    pending.resolve({updated: ['ROXY_WORKSPACE_ID', 'ROXY_PROJECT_ID']}); await saving;
    expect(owner.readField('ROXY_PROJECT_ID')).toBe('project2');
    expect(owner.dirtyKeys.value).toEqual(['ROXY_PROJECT_ID']);
  });

  it('concurrency integer validation preserves the existing lexical boundary', async () => {
    const api: ConfigApi = {getSchema: vi.fn(), save: vi.fn(), invalidate: vi.fn()};
    const owner = createConfigDraft({api, initialFields: [
      {key: 'GLOBAL_TASK_WORKERS', group: '并发控制', label: '全局', type: 'int', value: 3},
    ]});
    for (const value of ['', null, '1e3', '1.0', '-2', '0']) {
      owner.setField('GLOBAL_TASK_WORKERS', value);
      expect((await owner.saveAll()).status).toBe('validation-error');
    }
    expect(api.save).not.toHaveBeenCalled();
  });

  it('saved subscriber failures do not turn a committed save into a failed operation', async () => {
    const {owner} = fixture();
    owner.subscribeSaved(() => {throw new Error('render failed');});
    owner.setField('ONE', 2);
    expect((await owner.saveAll()).status).toBe('saved');
    expect(owner.dirtyCount.value).toBe(0);
  });

  it('scope disposal removes secret drafts and aborts reads without cancelling a submitted POST', async () => {
    const api: ConfigApi = {getSchema: vi.fn(), save: vi.fn(), invalidate: vi.fn()};
    const pending = deferred<ConfigSaveResponse>(), read = deferred<ConfigField[]>();
    vi.mocked(api.getSchema).mockReturnValue(read.promise);
    vi.mocked(api.save).mockReturnValue(pending.promise);
    const scope = effectScope();
    const owner = scope.run(() => useConfigDraft({api, initialFields: fields()}))!;
    owner.setField('KEY', 'secret');
    const reading = owner.refresh(), saving = owner.saveAll();
    const signal = vi.mocked(api.getSchema).mock.calls[0]![0]!.signal!;
    scope.stop();
    expect(signal.aborted).toBe(true);
    expect(owner.secretDraft('KEY')).toEqual({mode: 'retain'});
    pending.resolve({updated: ['KEY']}); read.resolve(fields());
    expect((await saving).status).toBe('disposed');
    await reading;
    expect(api.save).toHaveBeenCalledTimes(1);
  });
});
