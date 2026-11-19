import {describe,expect,it} from 'vitest';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {runInNewContext} from 'node:vm';
import {actionFromTarget,createAccountPresentation,type LegacyAccountPresenters} from './presentation';
import {accountRow} from './uiTestSupport';
function legacy():LegacyAccountPresenters{return{cells:{token:()=>'',account_status:()=>'<div class="account-cell-lines"><div class="account-cell-line"><span class="is-fail">Token 异常 · HTTP 403</span></div><div class="account-cell-line--sub">详细错误</div></div>',password:()=>'',quota:()=>'',promotion:()=>'<span data-accounts-tooltip="完整优惠">优惠原语义</span>',totp:()=>'',risk:()=>'',time:()=>''},plan:()=>'<span>free</span>',extractLink:()=>'<span class="pill">这是执行提链过程中很长的内部进度说明</span>',codex:()=>'<span>失败</span>',menu:row=>`<button onclick="checkSelectedLive([Number('${row.id}')], this); return false;">查活</button><button onclick="refreshSelectedToken([Number('${row.id}')], this); return false;">刷新AT</button>`,emailInvalidBadge:()=>'',registrationDriverLabel:String,facetLabel:(_g,v)=>v,escape:value=>String(value).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;'),short:(value,length)=>value.slice(0,length),htmlText:html=>{const el=document.createElement('div');el.innerHTML=html;return el.textContent||'';}};}
function html(value:string){const el=document.createElement('div');el.innerHTML=value;return el;}
describe('账号旧presenter边界',()=>{
 it('转换两种旧inline动作且保留绑定ID，未知inline拒绝执行',()=>{const old=legacy(),p=createAccountPresentation(old),menu=html(p.menu(accountRow(7)));expect(menu.querySelector('[onclick]')).toBeNull();expect(menu.querySelector('[data-account-live-check]')?.getAttribute('data-account-live-check')).toBe('7');expect(actionFromTarget(menu.querySelector('[data-account-refresh-token]'))?.action).toBe('account-refresh-token');old.menu=()=>'<button onclick="unexpected()">危险</button>';expect(()=>createAccountPresentation(old).menu(accountRow())).toThrow();});
 it('长错误和执行结果均≤10字，全文留在title且优惠展示不改写',()=>{const old=legacy(),p=createAccountPresentation(old),error='这是一个包含完整原始诊断细节的长错误消息';const row=accountRow(1,{codex_error:error,live_check_status:'failed',live_check_error:error,extract_link_status:'running'});const codex=html(p.cell('codex',row)),status=html(p.cell('account_status',row)),plan=html(p.cell('plan',row));expect(Array.from(codex.querySelector('.account-cell-line--sub')?.textContent||'').length).toBeLessThanOrEqual(10);expect(codex.querySelector('[title]')?.getAttribute('title')).toBe(error);expect(Array.from(status.querySelector('.account-cell-line--sub')?.textContent||'').length).toBeLessThanOrEqual(10);expect(Array.from(status.querySelector('.is-fail')?.textContent||'').length).toBeLessThanOrEqual(10);expect(plan.textContent).toContain('提链中');expect(plan.querySelector('[title]')?.getAttribute('title')).toContain('很长的内部进度说明');expect(p.cell('promotion',row)).toBe('<span data-accounts-tooltip="完整优惠">优惠原语义</span>');});
 it('真实旧账号状态已恢复查活时历史停用原因不覆盖成功时间',()=>{
  const source=readFileSync(resolve(process.cwd(),'../webui/static/js/pages/accounts/page.js'),'utf8');
  const functionSource=(name:string)=>{const start=source.indexOf(`function ${name}(`);const next=source.slice(start+1).search(/\n(?:async )?function /);return source.slice(start,next<0?undefined:start+1+next);};
  const context:Record<string,unknown>={esc:(value:unknown)=>String(value??''),short:(value:string,length:number)=>value.slice(0,length)};
  runInNewContext(['accountIsDeactivated','_liveCheckHttpStatus','_fmtPlanTime','_accountStatusCellV2'].map(functionSource).join('\n'),context);
  const old=legacy();old.cells.account_status=context._accountStatusCellV2 as LegacyAccountPresenters['cells']['account_status'];
  const row=accountRow(1,{account_status:'active',account_status_reason:'用户确认该账号已经成功恢复访问权限',live_check_status:'live',live_checked_at:'2026-11-15T10:20:00'});
  const result=html(createAccountPresentation(old).cell('account_status',row));expect(result.querySelector('.account-cell-line--sub')?.textContent).toBe('11-15 10:20');expect(result.textContent).toContain('查活通过');
 });
 it('旧gate别名仍定位AT刷新和封号邮件，disabled capability不派发',()=>{
  const old=legacy();old.cells.risk=row=>`<button data-deactivation-mail-check="${row.id}">复查</button>`;const p=createAccountPresentation(old);const menu=html(p.menu(accountRow()));const cell=html(p.cell('risk',accountRow()));
  const token=menu.querySelector<HTMLElement>('[data-account-token-refresh]');const mail=cell.querySelector<HTMLElement>('[data-account-deactivation-mail]');expect(token).not.toBeNull();expect(mail).not.toBeNull();token!.setAttribute('aria-disabled','true');token!.classList.add('feature-unavailable');mail!.setAttribute('disabled','');expect(actionFromTarget(token)).toBeUndefined();expect(actionFromTarget(mail)).toBeUndefined();
 });
 it('真实多国优惠保持最近两国和历史tooltip内容',()=>{
  const source=readFileSync(resolve(process.cwd(),'../webui/static/js/pages/accounts/page.js'),'utf8');const section=source.slice(source.indexOf('function _plusPromotionKind('),source.indexOf('function _planAction('));const context:Record<string,unknown>={esc:(value:unknown)=>String(value??'').replaceAll('&','&amp;').replaceAll('"','&quot;'),_fmtPlanTime:(value:unknown)=>String(value||'')};runInNewContext(section,context);
  const old=legacy();old.cells.promotion=context._promotionCell as LegacyAccountPresenters['cells']['promotion'];const row=accountRow(1,{plan_check_status:'failed',plan_check_country_results:[
    {country:'US',status:'success',checked_at:'2026-11-01T10:00:00Z',result:{account_promotions:[{plan:'plus',kind:'free_trial',eligible:true,duration_num_periods:1,duration_period:'month'}]}},
    {country:'JP',status:'success',checked_at:'2026-11-14T10:00:00Z',result:{account_promotions:[{plan:'plus',kind:'discount',eligible:true,discount_percentage:50,duration_num_periods:2,duration_period:'month'}]}},
    {country:'DE',status:'failed',checked_at:'2026-11-15T10:00:00Z',error:'本次网络故障',last_success_at:'2026-11-12T10:00:00Z',result:{account_promotions:[{plan:'plus',kind:'discount',eligible:true,discount_percentage:25,duration_num_periods:1,duration_period:'month'}]}},
  ]});
  const value=createAccountPresentation(old).cell('promotion',row);expect(value).toBe(old.cells.promotion(row));const result=html(value);expect(result.querySelectorAll('.account-promotion-country-row')).toHaveLength(2);expect(result.textContent).toContain('JP');expect(result.textContent).toContain('DE');expect(result.textContent).not.toContain('US');expect(result.querySelector('[data-accounts-tooltip]')?.getAttribute('data-accounts-tooltip')).toContain('本次网络故障');
 });
 it('动态action保留URL冒号和邮箱无关值，disabled不派发',()=>{const el=html('<button data-qr-url="https://example.test/a:b">二维码</button><button data-account-email-invalid="1" data-invalid="0">解除</button><button data-account-action="password" disabled>禁用</button>');const buttons=el.querySelectorAll('button');expect(actionFromTarget(buttons[0]!)?.action).toBe('qr-url:https://example.test/a:b');expect(actionFromTarget(buttons[1]!)?.action).toBe('account-email-invalid:0');expect(actionFromTarget(buttons[2]!)).toBeUndefined();});
 it('uses mainline compact health and Codex presenters for HTTP, confirmed deactivation and legacy execution state',()=>{
  const source=readFileSync(resolve(process.cwd(),'../webui/static/js/pages/accounts/page.js'),'utf8');
  const functionSource=(name:string)=>{const start=source.indexOf(`function ${name}(`);const next=source.slice(start+1).search(/\n(?:async )?function /);return source.slice(start,next<0?undefined:start+1+next);};
  const context:Record<string,unknown>={esc:(value:unknown)=>String(value??'').replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;')};
  runInNewContext(['accountIsDeactivated','_liveCheckHttpStatus','_fmtPlanTime','compactAccountStatus','accountCodexDisplay','accountHealthDisplay','accountStatusLines'].map(functionSource).join('\n'),context);
  const old=legacy();old.healthDisplay=context.accountHealthDisplay as NonNullable<LegacyAccountPresenters['healthDisplay']>;old.codexDisplay=context.accountCodexDisplay as NonNullable<LegacyAccountPresenters['codexDisplay']>;old.statusLines=context.accountStatusLines as NonNullable<LegacyAccountPresenters['statusLines']>;
  const view=createAccountPresentation(old);const health=html(view.cell('account_status',accountRow(1,{live_check_status:'failed',live_check_http_status:403,live_check_error:'upstream failure full diagnostic'})));
  expect(health.querySelector('.account-cell-line--sub')?.textContent).toBe('HTTP 403');expect(health.querySelector('.account-cell-line > span')?.textContent).toBe('Token 异常');
  expect(html(view.cell('codex',accountRow(1,{codex_status:'completed'}))).textContent).toBe('已通过');expect(html(view.cell('codex',accountRow(1,{codex_status:'running'}))).textContent).toContain('补跑中');
  expect(html(view.cell('codex',accountRow(1,{account_status:'deactivated',codex_execution_status:'running'}))).textContent).toContain('封号');
  expect(view.rowTone(accountRow(1,{account_status:'deactivated'}))).toBe('bad');
 });

});
