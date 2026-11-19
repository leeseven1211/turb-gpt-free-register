import type {DeepReadonly} from 'vue';
import {shortErrorLabel} from '../../shared/errorLabels';
import type {AccountActionContext,AccountViewRow,useAccounts} from './useAccounts';
import type {AccountFacetLabel,AccountFilterKey} from './filterDefinitions';

export type AccountRenderRow=DeepReadonly<AccountViewRow>;
export type AccountCellKey='token'|'account_status'|'password'|'plan'|'quota'|'promotion'|'totp'|'risk'|'codex'|'time';
export interface AccountTableColumn {key:string;label:string;className:string;filter?:AccountFilterKey;cell?:AccountCellKey}
export const accountColumns:readonly AccountTableColumn[]=[
  {key:'selection',label:'选择',className:'col-check'},
  {key:'id',label:'ID',className:'col-id',filter:'id'},
  {key:'email',label:'邮箱 / 姓名',className:'col-email',filter:'email'},
  {key:'source',label:'来源',className:'col-source',filter:'source'},
  {key:'registration_driver',label:'注册驱动',className:'col-registration-driver',filter:'registration_driver'},
  {key:'token',label:'Token',className:'col-token',filter:'token',cell:'token'},
  {key:'account_status',label:'账号状态',className:'col-account-status',filter:'account_status',cell:'account_status'},
  {key:'password',label:'账号密码',className:'col-small col-password',filter:'password',cell:'password'},
  {key:'plan',label:'套餐',className:'col-plan',filter:'plan',cell:'plan'},
  {key:'quota',label:'额度',className:'col-quota',cell:'quota'},
  {key:'promotion',label:'套餐优惠',className:'col-trial',filter:'promotion',cell:'promotion'},
  {key:'totp',label:'2FA',className:'col-small col-2fa',filter:'totp',cell:'totp'},
  {key:'risk',label:'封号邮件',className:'col-risk-mail',filter:'risk',cell:'risk'},
  {key:'codex',label:'Codex',className:'col-status',filter:'codex',cell:'codex'},
  {key:'time',label:'创建 / 更新',className:'col-time',filter:'date',cell:'time'},
  {key:'actions',label:'操作',className:'col-actions'},
];
const accountColumnWeights=[36,72,160,80,104,84,88,72,88,88,192,72,88,72,96,108];
export const accountColumnWidths=accountColumnWeights.map(width=>width/accountColumnWeights.reduce((sum,value)=>sum+value,0)*1500);
export type AccountActionDescriptor = string;
export interface AccountCompactDisplay {label:string;style:string;title?:string;secondary?:string;secondaryTitle?:string}
export interface LegacyAccountPresenters {
  compactStatus?(text:string,fallback:string):string;
  codexDisplay?(row:AccountRenderRow):AccountCompactDisplay;
  healthDisplay?(row:AccountRenderRow):AccountCompactDisplay;
  statusLines?(display:AccountCompactDisplay,className:string):string;
  cells:Record<Exclude<AccountCellKey,'plan'|'codex'>,(row:AccountRenderRow)=>string>;
  plan(row:AccountRenderRow):string;
  extractLink(row:AccountRenderRow):string;
  codex(row:AccountRenderRow):string;
  menu(row:AccountRenderRow):string;
  emailInvalidBadge(row:AccountRenderRow):string;
  registrationDriverLabel(value:unknown):string;
  facetLabel:AccountFacetLabel;
  escape(value:unknown):string;
  short(value:string,length:number):string;
  htmlText(value:string):string;
}
export interface AccountPresentation {
  cell(key:AccountCellKey,row:AccountRenderRow):string;
  menu(row:AccountRenderRow):string;
  emailInvalidBadge(row:AccountRenderRow):string;
  registrationDriverLabel(value:unknown):string;
  facetLabel:AccountFacetLabel;
  mobileSummary(row:AccountRenderRow):string;
  rowTone(row:AccountRenderRow):'bad'|'warn'|'ok';
}
/** Only existing escaped presenter output enters this adapter; not arbitrary server HTML. */
export function createAccountPresentation(legacy:LegacyAccountPresenters):AccountPresentation {
  const line=(html:string,secondary='')=>`<div class="account-cell-lines"><div class="account-cell-line">${html}</div>${secondary?`<div class="account-cell-line account-cell-line--sub">${secondary}</div>`:''}</div>`;
  const shortError=(value:string)=>Array.from(value).length<=10?value:shortErrorLabel();
  function compactStatus(row:AccountRenderRow):string {
    const holder=document.createElement('template');holder.innerHTML=legacy.cells.account_status(row);
    const isDeactivated=['account_status','codex_status','codex_credential_state'].some(key=>String(row[key as keyof AccountRenderRow]||'').toLowerCase()==='deactivated');
    if(isDeactivated||row.live_check_status==='failed'){
      const secondary=holder.content.querySelector<HTMLElement>('.account-cell-line--sub');
      if(secondary){const full=secondary.title||String(isDeactivated?row.account_status_reason||secondary.textContent||'':row.live_check_error||secondary.textContent||'');secondary.title=full;secondary.textContent=shortError(full);}
      const primary=holder.content.querySelector<HTMLElement>('.account-cell-line > .is-fail');
      if(primary&&Array.from(primary.textContent||'').length>10){primary.title=[primary.title,primary.textContent].filter(Boolean).join('；');primary.textContent='Token 异常';}
    }
    return holder.innerHTML;
  }
  function compactExtract(row:AccountRenderRow):string {
    const holder=document.createElement('template');holder.innerHTML=legacy.extractLink(row);
    for(const label of holder.content.querySelectorAll<HTMLElement>('.pill')){
      const full=label.textContent||'';
      if(Array.from(full).length>10){label.title=[label.title,full].filter(Boolean).join('；');label.textContent=row.extract_link_status==='running'?'提链中':Array.from(full).slice(0,9).join('')+'…';}
    }
    return holder.innerHTML;
  }
  function menu(row:AccountRenderRow):string {
    const holder=document.createElement('template');holder.innerHTML=legacy.menu(row);
    // These two known old handlers become explicit actions, with no global selection reads.
    for(const button of holder.content.querySelectorAll<HTMLElement>('[onclick]')) {
      const handler=button.getAttribute('onclick')||'';
      if(/^checkSelectedLive\(\[Number\('/.test(handler))button.dataset.accountLiveCheck=String(row.id);
      else if(/^refreshSelectedToken\(\[Number\('/.test(handler)){button.dataset.accountRefreshToken=String(row.id);button.dataset.accountTokenRefresh=String(row.id);}
      else throw new Error('账号动作仍含未迁移的内联处理器');
      button.removeAttribute('onclick');
    }
    return holder.innerHTML;
  }
  return {
    cell(key,row){
      if(key==='plan')return line(legacy.plan(row),compactExtract(row));
      if(key==='account_status')return legacy.healthDisplay&&legacy.statusLines?legacy.statusLines(legacy.healthDisplay(row),'acc-v2-account-status'):compactStatus(row);
      if(key==='codex'){
        if(legacy.codexDisplay&&legacy.statusLines)return legacy.statusLines(legacy.codexDisplay(row),'acc-v2-codex');
        const summary=String(row.codex_error||(['queued','running','cancelling'].includes(String(row.codex_execution_status))?'授权处理中':''));
        return line(legacy.codex(row),summary?`<span title="${legacy.escape(summary)}">${legacy.escape(shortError(summary))}</span>`:'');
      }
      if(key==='risk'){
        const holder=document.createElement('template');holder.innerHTML=legacy.cells.risk(row);
        holder.content.querySelectorAll<HTMLElement>('[data-deactivation-mail-check]').forEach(button=>{button.dataset.accountDeactivationMail=button.dataset.deactivationMailCheck;});
        return holder.innerHTML;
      }
      return legacy.cells[key](row);
    },menu,emailInvalidBadge:legacy.emailInvalidBadge,registrationDriverLabel:legacy.registrationDriverLabel,facetLabel:legacy.facetLabel,
    mobileSummary(row){return [row.email_source,legacy.htmlText(legacy.plan(row)),row.totp_enabled?'2FA 已验证':'2FA 未验证',(()=>{const value=legacy.htmlText(legacy.codex(row));return value&&value!=='-'?`Codex ${value}`:'';})()].filter(value=>value&&value!=='-').join(' · ');},
    rowTone(row){if(legacy.healthDisplay){const style=legacy.healthDisplay(row).style;return style==='fail'?'bad':['mute','run'].includes(style)?'warn':'ok';}const html=legacy.cells.account_status(row);return /status-(failed|error|invalid|rejected)/.test(html)?'bad':/status-(warning|pending|unknown|used)/.test(html)?'warn':'ok';},
  };
}
const actionAttributes=[
  'account-registration-retry','account-registration-task','account-email-change','account-totp-copy',
  'account-copy-secret','account-setup','account-action','plan-check','deactivation-mail-check',
  'account-live-check','account-refresh-token','account-task-history','account-delete','account-archive',
  'account-restore','account-email-invalid','extract-link','qr-url','codex-stop','codex-reset-retrying','codex-retry','copy-id',
] as const;
export function actionFromTarget(target:EventTarget|null):{action:AccountActionDescriptor;trigger:HTMLElement}|undefined {
  if(!(target instanceof Element))return;
  const trigger=target.closest<HTMLElement>('button,[data-copy-id]');
  if(!trigger||trigger.hasAttribute('disabled')||trigger.getAttribute('aria-disabled')==='true'||trigger.classList.contains('feature-unavailable'))return;
  const found=actionAttributes.find(attribute=>trigger.hasAttribute(`data-${attribute}`));
  if(!found)return;
  const dynamic=['account-registration-task','account-copy-secret','account-action','qr-url','copy-id'].includes(found);
  const suffix=found==='account-email-invalid'?trigger.dataset.invalid:found==='account-archive'?trigger.dataset.archived:dynamic?trigger.getAttribute(`data-${found}`):undefined;
  return {action:suffix==null?found:`${found}:${suffix}`,trigger};
}

export type AccountsController=ReturnType<typeof useAccounts>;
export interface AccountsLegacyState {
  selectedIds:readonly string[];
  selectedEmails:Readonly<Record<string,string>>;
  total:number;page:number;size:number;archived:string;loading:boolean;visible:boolean;
}
export interface AccountsCallbacks {
  openDetail(accountId:string,rowSnapshot:AccountViewRow,lease:ReturnType<AccountsController['openPlanDetailsConsumer']>,trigger:HTMLElement|null):void;
  invoke(action:string,context:AccountActionContext,trigger:HTMLElement|null):void|Promise<void>;
  onStateChange?(state:AccountsLegacyState):void;
  afterRender?(root:HTMLElement):void;
  closeConsumers?(restoreFocus?:boolean):void;
  notify?(message:string):void;
}
