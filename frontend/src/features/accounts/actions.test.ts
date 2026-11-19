import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {request} from '../../api/client';
import {createAccountActions, type AccountActionDependencies} from './actions';
import {createAccountDownloads} from './browserDownloads';
import type {AccountActionContext} from './useAccounts';
import {deferred, realAdapter} from './uiTestSupport';
const fetchMock = vi.fn<typeof fetch>();
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {status, headers:{'Content-Type':'application/json'}});
function context(accountIds: readonly string[] = ['7', '11']): AccountActionContext {
  return Object.freeze({accountIds:Object.freeze([...accountIds]),expectedEmails:Object.freeze({'7':'current@test','11':'offpage@test'}),querySnapshot:realAdapter().normalize(),archived:'0',rowHints:Object.freeze([])});
}
function setup(overrides: Partial<AccountActionDependencies> = {}) {
  const chosen: AccountActionDependencies = {
    request, notify:()=>{}, confirm:async()=>true, clipboard:async()=>true,
    downloadBlob:()=>{}, downloadUrl:()=>{}, now:()=>new Date(2026,10,15,3,4,5),
    schedule:(callback,delay)=>setTimeout(callback,delay), reloadCodex:()=>{},
    canInvoke:()=>true, beginBusy:()=>()=>{}, ...overrides,
  };
  const deps = {...chosen, notify:vi.fn(chosen.notify), confirm:vi.fn(chosen.confirm), clipboard:vi.fn(chosen.clipboard),
    downloadBlob:vi.fn(chosen.downloadBlob),downloadUrl:vi.fn(chosen.downloadUrl),reloadCodex:vi.fn(chosen.reloadCodex),
    canInvoke:vi.fn(chosen.canInvoke),beginBusy:vi.fn(chosen.beginBusy)};
  return {deps,actions:createAccountActions(deps)};
}
const secretResponse = (values: unknown[] = ['first','second']) => ({ok:true,field:'copy_line',count:values.length,values:values.map((value,index)=>({id:index?11:7,email:index?'offpage@test':'current@test',value})),skipped:[]});
const sessionResponse = (fields:Record<string,unknown>={}) => ({ok:true,prepared:true,download_id:'session-id',download_url:'/api/downloads/session-id',filename:'accounts-session-bulk-20261115-030405.zip',added_count:1,skipped_count:1,skipped:[{id:11,email:'offpage@test',error_code:'session_missing',reason:'未保存 Session'}],...fields});
const cpaResponse = (fields:Record<string,unknown>={}) => ({ok:true,prepared:true,download_id:'cpa-id',download_url:'/api/downloads/cpa-id',filename:'accounts-cpa-bulk-20261115-030405.zip',added_count:1,error_count:1,...fields});
function posted(){return JSON.parse(fetchMock.mock.calls[0]![1]!.body as string);}
beforeEach(()=>{vi.useFakeTimers();vi.stubGlobal('fetch',fetchMock);fetchMock.mockReset();});
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();});

describe('account action dispatcher',()=>{
  it('does no secret work on construction and leaves unmigrated descriptors explicitly unsupported',async()=>{
    const {actions,deps}=setup();expect(actions.isSupported('copySelectedAccountTokens')).toBe(true);expect(actions.isSupported('account-copy-secret:chatgpt_session')).toBe(true);
    for(const descriptor of ['account-copy-secret:arbitrary','copySelectedAccountTokens:extra','qr-url:https://example.test:443/image','account-delete'])expect(actions.isSupported(descriptor)).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();expect(deps.clipboard).not.toHaveBeenCalled();await expect(actions.invoke('account-delete',context())).rejects.toThrow('未支持');expect(fetchMock).not.toHaveBeenCalled();
  });
  it('opt-in local mutations execute the real mutation owner through this dispatcher',async()=>{
    fetchMock.mockResolvedValue(json({ok:true,deleted:true}));const removed=vi.fn();
    const {actions}=setup({local:{prompt:()=>null,refresh:async()=>{},refreshSummary:()=>{},removeAcknowledgedSelection:removed,clearSelection:()=>{}}});
    expect(actions.isSupported('account-delete')).toBe(true);const input=context(['7']);await actions.invoke('account-delete',input);
    expect(fetchMock.mock.calls[0]![0]).toBe('/api/accounts/7/delete');expect(posted()).toEqual({});expect(removed).toHaveBeenCalledWith(['7'],input);
  });
  it('uses only explicit IDs without reading rows, emails or old selection globals',async()=>{
    fetchMock.mockResolvedValue(json(secretResponse()));const input=context(),guarded={...input};
    Object.defineProperties(guarded,{rowHints:{get(){throw new Error('must not read rows');}},expectedEmails:{get(){throw new Error('must not read emails');}}});
    const {actions,deps}=setup();await actions.invoke('copySelectedAccountLines',guarded);expect(posted()).toEqual({account_ids:[7,11],field:'account_credentials_line'});expect(deps.clipboard).toHaveBeenCalledWith('first\nsecond');expect(input.accountIds).toEqual(['7','11']);
  });
  it('blocks disabled or gated triggers before confirmation or HTTP',async()=>{
    const {actions,deps}=setup({canInvoke:()=>false});await actions.invoke('downloadSelectedCpa',context(),document.createElement('button'));expect(fetchMock).not.toHaveBeenCalled();expect(deps.confirm).not.toHaveBeenCalled();expect(deps.beginBusy).not.toHaveBeenCalled();
  });
  it.each(['0','-1','1.5','1e2','9007199254740993'])('rejects invalid ID %s before HTTP',async id=>{
    const {actions,deps}=setup();await actions.invoke('copySelectedAccountTokens',context([id]));expect(fetchMock).not.toHaveBeenCalled();expect(deps.notify).toHaveBeenCalledWith(expect.stringContaining('账号 ID 无效'));
  });
  it('rejects empty selection and multi-account row actions',async()=>{
    const {actions,deps}=setup();await actions.invoke('downloadSelectedAccountSessions',context([]));await actions.invoke('account-totp-copy',context());expect(fetchMock).not.toHaveBeenCalled();expect(deps.notify.mock.calls.flat().join(' ')).toContain('请先选择账号');expect(deps.notify.mock.calls.flat().join(' ')).toContain('一个账号');
  });
});

describe('on-demand secret copy',()=>{
  it.each([
    ['copySelectedAccountTokens','access_token','已复制 2 个 Token'],['copySelectedAccountLines','account_credentials_line','已复制 2 行'],['copySelectedAccountEmails','email','已复制 2 个邮箱'],['copySelectedAccountExtractLinks','extract_link','已复制 2 个提炼地址'],['copySelectedAccountPasswords','account_password_line','本地未保存密码的账号已跳过'],['copySelectedAccountTotpSecrets','totp_secret','未设置 2FA 的账号已跳过'],
  ])('%s preserves endpoint, cross-page IDs and ordered nonempty values',async(descriptor,field,notice)=>{
    fetchMock.mockResolvedValue(json(secretResponse(['first',null,'',false,0,'second'])));const {actions,deps}=setup();await actions.invoke(descriptor,context());
    expect(fetchMock).toHaveBeenCalledTimes(1);expect(fetchMock.mock.calls[0]![0]).toBe('/api/accounts/secret-bulk');expect(fetchMock.mock.calls[0]![1]).toMatchObject({credentials:'same-origin',method:'POST',headers:{'Content-Type':'application/json'}});expect(posted()).toEqual({account_ids:[7,11],field});expect(deps.clipboard.mock.calls[0]?.[0]).toBe('first\nsecond');expect(deps.notify).toHaveBeenCalledWith(expect.stringContaining(notice));expect(deps.confirm).not.toHaveBeenCalled();expect(deps.reloadCodex).not.toHaveBeenCalled();
  });
  it.each(['copy_line','chatgpt_session','account_password','totp_secret','access_token'])('fetches single %s only on invocation',async field=>{
    fetchMock.mockResolvedValue(json({ok:true,id:7,field,value:'server-only-secret'}));const {actions,deps}=setup();await actions.invoke(`account-copy-secret:${field}`,context(['7']));expect(fetchMock.mock.calls[0]![0]).toBe(`/api/accounts/7/secret?field=${field}`);expect(deps.clipboard).toHaveBeenCalledWith('server-only-secret');expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it('does not copy or claim success for empty secrets',async()=>{
    fetchMock.mockResolvedValueOnce(json(secretResponse([]))).mockResolvedValueOnce(json({ok:true,id:7,field:'copy_line',value:null}));const {actions,deps}=setup();await actions.invoke('copySelectedAccountLines',context());await actions.invoke('account-copy-secret:copy_line',context(['7']));expect(deps.clipboard).not.toHaveBeenCalled();expect(deps.notify.mock.calls.flat().join(' ')).toContain('可复制内容为空');
  });
  it.each([[],null,{ok:true,values:{}},{ok:true,values:[null]},{ok:true,values:[{value:{secret:'unexpected'}}]}])('rejects malformed response %j without copying',async body=>{
    fetchMock.mockResolvedValue(json(body));const {actions,deps}=setup();await actions.invoke('copySelectedAccountTokens',context());expect(deps.clipboard).not.toHaveBeenCalled();expect(deps.notify).toHaveBeenCalledWith(expect.stringContaining('响应格式无效'));
  });
  it.each(['copySelectedAccountEmails','copySelectedAccountExtractLinks'])('%s reports explicit clipboard failure without success',async descriptor=>{
    fetchMock.mockResolvedValue(json(secretResponse()));const {actions,deps}=setup({clipboard:vi.fn().mockResolvedValue(false)});await actions.invoke(descriptor,context());expect(deps.clipboard).toHaveBeenCalledWith('first\nsecond',false);expect(deps.notify.mock.calls.flat().join(' ')).toContain('失败');expect(deps.notify.mock.calls.flat().join(' ')).not.toContain('已复制');
  });
  it('keeps row pending across recreated triggers until clipboard settles',async()=>{
    fetchMock.mockResolvedValue(json({ok:true,id:7,field:'access_token',value:'secret'}));const pending=deferred<boolean>(),restore=vi.fn();const {actions,deps}=setup({clipboard:()=>pending.promise,beginBusy:()=>restore});const first=actions.invoke('account-copy-secret:access_token',context(['7']),document.createElement('button'));await vi.advanceTimersByTimeAsync(0);expect(actions.isPending('account-copy-secret:access_token',context(['7']))).toBe(true);await actions.invoke('account-copy-secret:access_token',context(['7']),document.createElement('button'));expect(fetchMock).toHaveBeenCalledTimes(1);expect(restore).not.toHaveBeenCalled();pending.resolve(true);await first;expect(restore).toHaveBeenCalledTimes(1);expect(actions.isPending('account-copy-secret:access_token',context(['7']))).toBe(false);expect(deps.notify).toHaveBeenCalledWith('Token 已复制');
  });
  it('keeps server error, releases controls and permits only explicit retry',async()=>{
    fetchMock.mockResolvedValue(json({ok:false,error:'账号不存在',code:'missing'},404));const restore=vi.fn();const {actions,deps}=setup({beginBusy:()=>restore});await actions.invoke('account-copy-secret:access_token',context(['7']));expect(fetchMock).toHaveBeenCalledTimes(1);expect(deps.notify).toHaveBeenCalledWith('复制失败: 账号不存在');expect(restore).toHaveBeenCalledTimes(1);await actions.invoke('account-copy-secret:access_token',context(['7']));expect(fetchMock).toHaveBeenCalledTimes(2);
  });
  it('copies TOTP and preserves zero remaining seconds',async()=>{
    fetchMock.mockResolvedValue(json({ok:true,id:7,code:'012345',remaining_seconds:0}));const {actions,deps}=setup();await actions.invoke('account-totp-copy',context(['7']));expect(fetchMock.mock.calls[0]![0]).toBe('/api/accounts/7/totp-code');expect(deps.clipboard).toHaveBeenCalledWith('012345',false);expect(deps.notify).toHaveBeenCalledWith('验证码已复制，剩余 0 秒');
  });
  it('distinguishes empty TOTP from clipboard failure without automatic retry',async()=>{
    fetchMock.mockResolvedValueOnce(json({ok:true,id:7,code:''})).mockResolvedValueOnce(json({ok:true,id:7,code:'123456',remaining_seconds:19}));const {actions,deps}=setup({clipboard:vi.fn().mockResolvedValue(false)});await actions.invoke('account-totp-copy',context(['7']));expect(deps.notify).toHaveBeenCalledWith('复制验证码失败: 验证码为空');expect(deps.clipboard).not.toHaveBeenCalled();await actions.invoke('account-totp-copy',context(['7']));expect(deps.notify).toHaveBeenCalledWith('验证码已查询，但复制失败');
  });
});

describe('TXT and prepared ZIP downloads',()=>{
  it('downloads TXT with timestamped filename, UTF-8 BOM and final newline',async()=>{
    fetchMock.mockResolvedValue(json(secretResponse(['甲@test----密码','offpage@test----pass'])));const {actions,deps}=setup();await actions.invoke('downloadSelectedAccountTxt',context());expect(posted()).toEqual({account_ids:[7,11],field:'copy_line'});expect(deps.downloadBlob).toHaveBeenCalledTimes(1);const [blob,filename]=deps.downloadBlob.mock.calls[0]!;expect(filename).toBe('accounts-selected-20261115-030405.txt');expect(blob.type).toBe('text/plain;charset=utf-8');vi.useRealTimers();const reader=new FileReader();const bytes=new Promise<ArrayBuffer>(resolve=>{reader.onload=()=>resolve(reader.result as ArrayBuffer);reader.readAsArrayBuffer(blob);});const data=new Uint8Array(await bytes);expect([...data.slice(0,3)]).toEqual([239,187,191]);expect(new TextDecoder().decode(data.slice(3))).toBe('甲@test----密码\noffpage@test----pass\n');expect(deps.notify).toHaveBeenCalledWith('已下载 2 个账号 TXT');expect(deps.confirm).not.toHaveBeenCalled();
  });
  it('reports TXT blob failure and releases pending state',async()=>{
    fetchMock.mockResolvedValue(json(secretResponse()));const {actions,deps}=setup({downloadBlob:()=>{throw new Error('blob unavailable');}});await actions.invoke('downloadSelectedAccountTxt',context());expect(deps.notify).toHaveBeenCalledWith('生成 TXT 失败: blob unavailable');expect(actions.isPending('downloadSelectedAccountTxt',context())).toBe(false);expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it('uses prepared Session URL and full IDs while preserving selection and skipped manifest meaning',async()=>{
    fetchMock.mockResolvedValue(json(sessionResponse()));const {actions,deps}=setup();const input=context();await actions.invoke('downloadSelectedAccountSessions',input);expect(fetchMock.mock.calls[0]![0]).toBe('/api/accounts/download-session-bulk');expect(posted()).toEqual({account_ids:[7,11],prepare:true});expect(deps.downloadUrl).toHaveBeenCalledWith('/api/downloads/session-id','accounts-session-bulk-20261115-030405.zip');expect(deps.downloadBlob).not.toHaveBeenCalled();expect(input.accountIds).toEqual(['7','11']);expect(deps.confirm).not.toHaveBeenCalled();expect(deps.notify).toHaveBeenCalledWith('已打包 1 个账号 Session，跳过 1 个；开始下载，结果见 ZIP 内 manifest.json');
  });
  it('downloads a Session manifest even when every account is skipped',async()=>{
    fetchMock.mockResolvedValue(json(sessionResponse({added_count:0,skipped_count:2})));const {actions,deps}=setup();await actions.invoke('downloadSelectedAccountSessions',context());expect(deps.downloadUrl).toHaveBeenCalledTimes(1);expect(deps.notify.mock.calls.flat().join(' ')).toContain('没有可下载的 Session，已生成结果清单，跳过 2 个');expect(deps.notify.mock.calls.flat().join(' ')).toContain('Session 缺失或无效的账号请先刷新 AT，读取失败的账号请重试');
  });
  it('keeps Session pending across selection changes and sends the original scope',async()=>{
    const response=deferred<Response>();fetchMock.mockReturnValue(response.promise);const restore=vi.fn();const {actions}=setup({beginBusy:()=>restore});const input={...context(),accountIds:['7','11']};const first=actions.invoke('downloadSelectedAccountSessions',input);input.accountIds.splice(0,2,'99');expect(actions.isPending('downloadSelectedAccountSessions',context(['99']))).toBe(true);await actions.invoke('downloadSelectedAccountSessions',context(['99']));expect(fetchMock).toHaveBeenCalledTimes(1);expect(posted()).toEqual({account_ids:[7,11],prepare:true});response.resolve(json(sessionResponse()));await first;expect(restore).toHaveBeenCalledTimes(1);expect(actions.isPending('downloadSelectedAccountSessions',input)).toBe(false);
  });
  it.each([undefined,null,''])('rejects missing Session URL %j without download or retry',async download_url=>{
    fetchMock.mockResolvedValue(json(sessionResponse({download_url})));const {actions,deps}=setup();await actions.invoke('downloadSelectedAccountSessions',context());expect(deps.downloadUrl).not.toHaveBeenCalled();expect(fetchMock).toHaveBeenCalledTimes(1);expect(deps.notify).toHaveBeenCalledWith('下载 Session 失败: 服务端未返回下载地址');
  });
  it('freezes CPA scope before confirmation and delays reload/control restoration 1200 ms',async()=>{
    const confirmation=deferred<boolean>();fetchMock.mockResolvedValue(json(cpaResponse()));const restore=vi.fn();const {actions,deps}=setup({confirm:()=>confirmation.promise,beginBusy:()=>restore});const input={...context(),accountIds:['7','11']};const first=actions.invoke('downloadSelectedCpa',input);input.accountIds.splice(0,2,'99');await actions.invoke('downloadSelectedCpa',context(['99']));expect(fetchMock).not.toHaveBeenCalled();confirmation.resolve(true);await first;expect(posted()).toEqual({account_ids:[7,11],prepare:true});expect(fetchMock.mock.calls[0]![0]).toBe('/api/accounts/download-cpa-bulk');expect(deps.downloadUrl).toHaveBeenCalledWith('/api/downloads/cpa-id','accounts-cpa-bulk-20261115-030405.zip');expect(deps.notify).toHaveBeenCalledWith('已生成 ZIP，开始下载（1 个失败见 manifest）');expect(deps.reloadCodex).not.toHaveBeenCalled();expect(restore).not.toHaveBeenCalled();expect(actions.isPending('downloadSelectedCpa',context(['99']))).toBe(true);await vi.advanceTimersByTimeAsync(1199);expect(restore).not.toHaveBeenCalled();await vi.advanceTimersByTimeAsync(1);expect(deps.reloadCodex).toHaveBeenCalledTimes(1);expect(restore).toHaveBeenCalledTimes(1);expect(actions.isPending('downloadSelectedCpa',context())).toBe(false);
  });
  it('preserves CPA confirmation scope and cancellation sends no request',async()=>{
    const {actions,deps}=setup({confirm:vi.fn().mockResolvedValue(false)});await actions.invoke('downloadSelectedCpa',context());expect(deps.confirm).toHaveBeenCalledWith('确定从 CPA 下载选中的 2 个账号的 CPA/Codex JSON 吗？\n\n会按账号邮箱匹配 CPA auth-files，成功的文件会打包成 ZIP，缺失文件会写入 manifest 错误清单。');expect(fetchMock).not.toHaveBeenCalled();expect(deps.beginBusy).not.toHaveBeenCalled();expect(actions.isPending('downloadSelectedCpa',context())).toBe(false);
  });
  it('does not replay accepted CPA prepare when later Codex refresh fails',async()=>{
    fetchMock.mockResolvedValue(json(cpaResponse({error_count:0})));const {actions,deps}=setup({reloadCodex:async()=>{throw new Error('refresh offline');}});await actions.invoke('downloadSelectedCpa',context());await vi.advanceTimersByTimeAsync(1200);expect(fetchMock).toHaveBeenCalledTimes(1);expect(deps.downloadUrl).toHaveBeenCalledTimes(1);expect(deps.notify.mock.calls.flat().join(' ')).toContain('下载已开始，但 Codex 列表刷新失败');
  });
  it.each([
    ['server error',()=>Promise.resolve(json({ok:false,error:'CPA unavailable'},502)),'CPA unavailable'],['network error',()=>Promise.reject(new Error('offline')),'offline'],['HTML login',()=>Promise.resolve(new Response('<html>login</html>',{status:401,headers:{'Content-Type':'text/html'}})),'登录已失效'],['ZIP instead of prepare JSON',()=>Promise.resolve(new Response('PK zip',{headers:{'Content-Type':'application/zip'}})),'非 JSON'],
  ])('does not download or retry %s',async(_name,response,reason)=>{
    fetchMock.mockImplementation(response);const {actions,deps}=setup();await actions.invoke('downloadSelectedCpa',context());expect(fetchMock).toHaveBeenCalledTimes(1);expect(deps.downloadUrl).not.toHaveBeenCalled();expect(deps.notify.mock.calls.flat().join(' ')).toContain(reason);await vi.advanceTimersByTimeAsync(1200);expect(actions.isPending('downloadSelectedCpa',context())).toBe(false);expect(deps.reloadCodex).not.toHaveBeenCalled();
  });
});

describe('browser download ownership',()=>{
  function browser(){const urls={createObjectURL:vi.fn().mockReturnValue('blob:local-test'),revokeObjectURL:vi.fn()};const downloads=createAccountDownloads({document,origin:'https://console.example.test',urls,schedule:(fn,delay)=>setTimeout(fn,delay)});const click=vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{});return {urls,downloads,click};}
  afterEach(()=>{document.querySelectorAll('a[download]').forEach(el=>el.remove());});
  it('owns TXT anchor/object URL for 800 ms and then removes both',async()=>{
    const {downloads,urls,click}=browser();downloads.downloadBlob(new Blob(['txt']),'accounts.txt');const anchor=document.querySelector('a[download]') as HTMLAnchorElement;expect(anchor.download).toBe('accounts.txt');expect(anchor.href).toBe('blob:local-test');expect(click).toHaveBeenCalledTimes(1);await vi.advanceTimersByTimeAsync(799);expect(anchor.isConnected).toBe(true);expect(urls.revokeObjectURL).not.toHaveBeenCalled();await vi.advanceTimersByTimeAsync(1);expect(anchor.isConnected).toBe(false);expect(urls.revokeObjectURL).toHaveBeenCalledWith('blob:local-test');
  });
  it('opens prepared ZIP with a normal same-origin anchor and removes it after 1000 ms',async()=>{
    const {downloads,urls,click}=browser();downloads.downloadUrl('/api/downloads/session-id','session.zip');const anchor=document.querySelector('a[download]') as HTMLAnchorElement;expect(anchor.getAttribute('href')).toBe('/api/downloads/session-id');expect(anchor.download).toBe('session.zip');expect(anchor.rel).toBe('noopener');expect(anchor.target).toBe('');expect(click).toHaveBeenCalledTimes(1);expect(urls.createObjectURL).not.toHaveBeenCalled();await vi.advanceTimersByTimeAsync(999);expect(anchor.isConnected).toBe(true);await vi.advanceTimersByTimeAsync(1);expect(anchor.isConnected).toBe(false);
  });
  it.each(['https://other.test/file.zip','//other.test/file.zip','javascript:alert(1)','data:application/zip,secret','blob:https://console.example.test/id'])('rejects unsafe prepared URL %s before inserting DOM',url=>{
    const {downloads,click}=browser();expect(()=>downloads.downloadUrl(url,'file.zip')).toThrow('同源');expect(click).not.toHaveBeenCalled();expect(document.querySelector('a[download]')).toBeNull();
  });
  it('immediately removes anchor and revokes object URL if clicking fails',()=>{
    const {downloads,urls,click}=browser();click.mockImplementation(()=>{throw new Error('click failed');});expect(()=>downloads.downloadBlob(new Blob(['txt']),'file.txt')).toThrow('click failed');expect(urls.revokeObjectURL).toHaveBeenCalledTimes(1);expect(document.querySelector('a[download]')).toBeNull();
  });
});
