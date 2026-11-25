import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {ref} from 'vue';
import {createCodexActions, type CodexAction} from './actions';
import type {CodexRow} from '../../api/codex';
function json(body: unknown, status = 200) {return new Response(JSON.stringify(body), {status, headers: {'Content-Type': 'application/json'}});}
function setup(names = ['a.json', 'b.json', 'other-page.json']) {
  const selected = ref(new Set(names)), items = ref<CodexRow[]>([{filename: 'a.json', email: 'same@example.test', exported_count: 2, sub2_uploaded_count: 0}]);
  const archived = ref(false), refresh = vi.fn().mockResolvedValue(undefined);
  const callbacks = {notify: vi.fn(), confirm: vi.fn().mockResolvedValue(true), openTasks: vi.fn(), operationWorkers: () => 3};
  return {selected, items, archived, refresh, callbacks, ...createCodexActions({selected, items, archived, refresh, callbacks})};
}
let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock);});
afterEach(() => {vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.useRealTimers();});

describe('Codex action receipts', () => {
  it('keeps all selections when an accepted command cannot yet be confirmed',async()=>{
    fetchMock.mockResolvedValueOnce(json({ok:true,accepted:true,command_id:'96'},202)).mockRejectedValueOnce(new Error('offline'));
    const actions=setup();await actions.run('deleteBulk');
    expect(actions.selected.value.size).toBe(3);expect(actions.refresh).not.toHaveBeenCalled();
    expect(actions.callbacks.notify).toHaveBeenLastCalledWith(expect.stringMatching(/^批量命令已受理.*96/));
    expect(actions.error.value).not.toContain('删除失败');
  });
  it('uses final item receipts to clear successful filenames and display retained failures',async()=>{
    fetchMock.mockResolvedValueOnce(json({ok:true,accepted:true,command_id:'97'},202))
      .mockResolvedValueOnce(json({ok:true,status:'partial_success',items:[{key:'a.json',status:'updated'},{key:'b.json',status:'failed',reason:'locked'}]}));
    const actions=setup();await actions.run('archiveBulk');
    expect([...actions.selected.value]).toEqual(['b.json','other-page.json']);
    expect(actions.callbacks.notify).toHaveBeenLastCalledWith(expect.stringContaining('未完成 1'));
  });
  it('queued upload stays here and removes only acknowledged cross-page filenames', async () => {
    const queued = [{filename: 'other-page.json', accepted: true, task_id: 71, run_id: 3}];
    fetchMock.mockResolvedValue(json({ok: true, accepted: true, queued, queued_count: 1, failed_count: 1, skipped_count: 1}, 202));
    const actions = setup(); await actions.run('uploadSub2');
    expect(JSON.parse(fetchMock.mock.calls[0]![1].body)).toEqual({filenames: ['a.json', 'b.json', 'other-page.json']});
    expect([...actions.selected.value]).toEqual(['a.json', 'b.json']);
    expect(actions.callbacks.openTasks).not.toHaveBeenCalled(); expect(actions.refresh).not.toHaveBeenCalled();
    expect(actions.callbacks.notify).toHaveBeenCalledWith('手动上传已入队 1 个，2 个未入队，可点击“查看上传进度”查看最终结果');
    expect(actions.callbacks.notify.mock.calls.flat().join(' ')).not.toContain('已上传'); expect(actions.uploadProgress.value).toBe(true);
    actions.showProgress(); expect(actions.callbacks.openTasks).toHaveBeenCalledWith();
  });
  it('a 202 with no queued item leaves every selection and does not pretend progress exists', async () => {
    fetchMock.mockResolvedValue(json({ok: true, accepted: true, queued: [], queued_count: 0, failed_count: 3}, 202));
    const actions = setup(); await actions.run('uploadSub2');
    expect(actions.selected.value.size).toBe(3); expect(actions.uploadProgress.value).toBe(false);
    expect(actions.refresh).not.toHaveBeenCalled(); expect(actions.callbacks.openTasks).not.toHaveBeenCalled();
    expect(actions.callbacks.notify.mock.calls.flat().join(' ')).toContain('已入队 0 个');
  });
  it.each([['refreshToken', 'codex_token_refresh'], ['reauthorize', 'codex_retry']] as const)('%s follows started receipts and never derives a filename from email', async (action, type) => {
    fetchMock.mockResolvedValue(json({ok: true, started: [{filename: 'other-page.json', accepted: true, task_id: 5}, {email: 'same@example.test', accepted: true, task_id: 8}], started_count: 2, skipped: [{filename: 'b.json'}]}, 202));
    const actions = setup(); await actions.run(action);
    expect([...actions.selected.value]).toEqual(['a.json', 'b.json']); expect(actions.callbacks.openTasks).toHaveBeenCalledExactlyOnceWith(type);
    expect(actions.refresh).not.toHaveBeenCalled(); expect(actions.callbacks.notify.mock.calls.flat().join(' ')).toContain('跳过 1 个');
  });
  it.each([['archiveBulk', {updated: [{filename: 'other-page.json', archived: true}], updated_count: 1}], ['deleteBulk', {deleted: ['other-page.json'], deleted_count: 1}]] as const)('%s preserves skipped and unrelated selected rows', async (action, receipt) => {
    fetchMock.mockResolvedValue(json({ok: true, ...receipt, skipped: [{filename: 'a.json'}]}));
    const actions = setup(); await actions.run(action);
    expect([...actions.selected.value]).toEqual(['a.json', 'b.json']); expect(actions.refresh).toHaveBeenCalledTimes(1);
    expect(actions.busy.value).toBe(false);
  });
  it('single-row actions use the explicit filename and archive state, not every selected item', async () => {
    fetchMock.mockResolvedValue(json({ok: true, filename: 'b.json', archived: false}));
    const actions = setup(); await actions.run('archive', ['b.json'], {filename: 'b.json', archived: true});
    expect(fetchMock.mock.calls[0]![0]).toBe('/api/codex/archive');
    expect(JSON.parse(fetchMock.mock.calls[0]![1].body)).toEqual({filename: 'b.json', archived: false});
    expect([...actions.selected.value]).toEqual(['a.json', 'other-page.json']); expect(actions.callbacks.confirm).not.toHaveBeenCalled();
  });
  it('reset has no filename receipt and preserves the selection', async () => {
    fetchMock.mockResolvedValue(json({ok: true})); const actions = setup(); await actions.run('reset', ['a.json']);
    expect(JSON.parse(fetchMock.mock.calls[0]![1].body)).toEqual({filename: 'a.json'}); expect(actions.selected.value.size).toBe(3);
    expect(actions.refresh).toHaveBeenCalledTimes(1);
  });
  it('a single delete uses its deleted receipt', async () => {
    fetchMock.mockResolvedValue(json({ok: true, deleted: 'b.json'})); const actions = setup(); await actions.run('delete', ['b.json']);
    expect([...actions.selected.value]).toEqual(['a.json', 'other-page.json']);
  });
});

describe('confirmation and submission boundaries', () => {
  it('reauthorization preserves automatic upload explanation and cancellation sends no request', async () => {
    const actions = setup(); actions.callbacks.confirm.mockResolvedValue(false); await actions.run('reauthorize');
    const note = actions.callbacks.confirm.mock.calls[0]![0];
    for (const text of ['更新本地 Codex 凭证', '授权后自动上传并启用 sub2api', '开启', '自动上传并恢复调度', '关闭', '上传 sub2api', '账号操作公共并发：3', '邮箱 OTP', '手机接码']) expect(note).toContain(text);
    expect(fetchMock).not.toHaveBeenCalled(); expect(actions.busy.value).toBe(false); expect(actions.selected.value.size).toBe(3);
  });
  it('token refresh preserves the old exported-but-untracked warning', async () => {
    const actions = setup(); actions.callbacks.confirm.mockResolvedValue(false); await actions.run('refreshToken');
    expect(actions.callbacks.confirm.mock.calls[0]![0]).toContain('建立自动同步记录');
    expect(actions.callbacks.confirm.mock.calls[0]![0]).toContain('不发邮箱验证码、不用接码短信');
  });
  it('guards duplicate writes while asynchronous confirmation or HTTP is pending', async () => {
    const actions = setup(); let confirm!: (value: boolean) => void;
    actions.callbacks.confirm.mockImplementation(() => new Promise<boolean>(resolve => {confirm = resolve;}));
    let complete!: (value: Response) => void;
    fetchMock.mockImplementation(() => new Promise<Response>(resolve => {complete = resolve;}));
    const run = actions.run('deleteBulk'); await actions.run('deleteBulk');
    expect(actions.busy.value).toBe(true); expect(actions.callbacks.confirm).toHaveBeenCalledTimes(1); expect(fetchMock).not.toHaveBeenCalled();
    confirm(true); await Promise.resolve(); await actions.run('uploadSub2'); expect(fetchMock).toHaveBeenCalledTimes(1);
    complete(json({ok: true, deleted: [], deleted_count: 0})); await run; expect(actions.busy.value).toBe(false);
  });
  it.each([['refreshToken', 501], ['uploadSub2', 501], ['reauthorize', 501], ['archiveBulk', 1001], ['deleteBulk', 1001], ['downloadBulk', 1001], ['downloadBulkCpa', 1001]] as const)('%s reports the endpoint limit without silently chunking', async (action, count) => {
    const actions = setup(Array.from({length: count}, (_, i) => `${i}.json`)); await actions.run(action);
    expect(fetchMock).not.toHaveBeenCalled(); expect(actions.error.value).toContain(String(count - 1)); expect(actions.selected.value.size).toBe(count);
  });
  it('HTTP business failure is visible, leaves selections and releases busy for a deliberate retry', async () => {
    fetchMock.mockResolvedValueOnce(json({ok: false, error: '凭证不可用'}, 409)).mockResolvedValueOnce(json({ok: true, deleted: ['a.json'], deleted_count: 1}));
    const actions = setup(); await actions.run('deleteBulk');
    expect(actions.error.value).toContain('凭证不可用'); expect(actions.busy.value).toBe(false); expect(actions.selected.value.size).toBe(3); expect(fetchMock).toHaveBeenCalledTimes(1);
    await actions.run('deleteBulk'); expect(fetchMock).toHaveBeenCalledTimes(2); expect(actions.error.value).toBe('');
  });
  it('reports a read refresh failure separately from a completed mutation', async () => {
    fetchMock.mockResolvedValue(json({ok: true, deleted: ['a.json'], deleted_count: 1})); const actions = setup();
    actions.refresh.mockRejectedValue(new Error('列表暂时不可用')); await actions.run('deleteBulk');
    expect(actions.selected.value.has('a.json')).toBe(false); expect(actions.error.value).toContain('操作已完成'); expect(actions.error.value).toContain('列表刷新失败');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe('download actions', () => {
  it.each(['download', 'downloadCpa'] as const)('%s triggers one native save and releases its object URL', async (action) => {
    vi.useFakeTimers(); const create = vi.fn().mockReturnValue('blob:test'), revoke = vi.fn();
    vi.stubGlobal('URL', class extends URL {static createObjectURL = create; static revokeObjectURL = revoke;});
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    fetchMock.mockResolvedValue(new Response('{"access_token":"fixture-only"}', {headers: {'Content-Type': 'application/json', 'Content-Disposition': 'attachment; filename="actual.json"'}}));
    const actions = setup(); await actions.run(action, ['a.json']);
    expect(fetchMock).toHaveBeenCalledTimes(1); expect(click).toHaveBeenCalledTimes(1); expect(create).toHaveBeenCalledTimes(1);
    expect(document.querySelector<HTMLAnchorElement>('a[download]')?.download).toBe('actual.json');
    expect([...actions.selected.value]).toEqual(['a.json', 'b.json', 'other-page.json']); expect(actions.refresh).toHaveBeenCalledTimes(1);
    await vi.runAllTimersAsync(); expect(revoke).toHaveBeenCalledExactlyOnceWith('blob:test'); expect(document.querySelector('a[download]')).toBeNull();
    expect(actions.callbacks.notify.mock.calls.flat().join(' ')).not.toContain('fixture-only');
  });
  it('local bulk download reports actual success count and retains failed selections', async () => {
    vi.useFakeTimers(); vi.stubGlobal('URL', class extends URL {static createObjectURL = vi.fn().mockReturnValue('blob:test'); static revokeObjectURL = vi.fn();});
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    fetchMock.mockResolvedValue(new Response(JSON.stringify({count: 1, credentials: [{filename: 'a.json', data: {}}], errors: [{filename: 'b.json', error: 'missing'}]}), {headers: {'Content-Type': 'application/json', 'Content-Disposition': 'attachment; filename="bulk.json"'}}));
    const actions = setup(); await actions.run('downloadBulk');
    expect([...actions.selected.value]).toEqual(['b.json', 'other-page.json']); expect(actions.callbacks.notify.mock.calls.flat().join(' ')).toContain('已打包下载 1 个');
    expect(actions.callbacks.confirm.mock.calls[0]![0]).toContain('CPA 不能直接读'); await vi.runAllTimersAsync();
  });
  it('invalid download never clicks or changes selection', async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    fetchMock.mockResolvedValue(json({ok: false, error: '没有成功从 CPA 下载任何凭证'}, 502));
    const actions = setup(); await actions.run('downloadBulkCpa');
    expect(click).not.toHaveBeenCalled(); expect(actions.selected.value.size).toBe(3); expect(actions.error.value).toContain('没有成功'); expect(actions.refresh).not.toHaveBeenCalled();
  });
  it('saves the local bulk failure report and states zero success without clearing selections', async () => {
    vi.useFakeTimers(); vi.stubGlobal('URL', class extends URL {static createObjectURL = vi.fn().mockReturnValue('blob:test'); static revokeObjectURL = vi.fn();});
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    fetchMock.mockResolvedValue(new Response(JSON.stringify({count: 0, credentials: [], errors: [{filename: 'a.json', error: 'missing'}]}), {headers: {'Content-Type': 'application/json', 'Content-Disposition': 'attachment; filename="bulk.json"'}}));
    const actions = setup(); await actions.run('downloadBulk', ['a.json']);
    expect(click).toHaveBeenCalledTimes(1); expect(actions.selected.value.size).toBe(3);
    expect(actions.callbacks.notify.mock.calls.flat().join(' ')).toContain('成功 0 个，已下载错误清单');
    expect(actions.error.value).toBe(''); await vi.runAllTimersAsync();
  });
});
