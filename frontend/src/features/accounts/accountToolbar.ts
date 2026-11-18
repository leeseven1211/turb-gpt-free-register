import type {AccountActionContext} from './useAccounts';
export interface AccountToolbarState {selectedCount:number;archived:boolean;pending?:Readonly<Record<string,boolean>>;labels?:Readonly<Record<string,string>>}
export interface AccountToolbarCapability {enabled:boolean;reason?:string}
export type AccountToolbarCapabilities=Readonly<Record<string,AccountToolbarCapability|undefined>>;
export interface AccountToolbarButton {id:string;label:string;section:string;action:string;className:string;title:string;selection:boolean;feature?:string}
export type AccountToolbarInvoke=(descriptor:string,context:AccountActionContext,trigger:HTMLElement)=>unknown|Promise<unknown>;
export const ACCOUNT_TOOLBAR_SECTIONS=Object.freeze(['操作','批次与巡检','复制与导出','资产管理']);
export const ACCOUNT_TOOLBAR_BUTTONS:readonly Readonly<AccountToolbarButton>[]=Object.freeze([
  Object.freeze({"id":"btnCheckSelectedLiveV2","label":"查活","section":"操作","action":"checkSelectedLive","className":"jobs-tb-btn jobs-tb-btn--primary","title":"只在线验证现有 Token；不会发送邮箱验证码或刷新 AT","selection":true,"feature":"live_check"}),
  Object.freeze({"id":"btnCheckSelectedPlansV2","label":"查套餐","section":"操作","action":"checkSelectedPlans","className":"jobs-tb-btn jobs-tb-btn--primary","title":"查询选中账号当前套餐；free 账号会检查 Plus 免费试用或折扣优惠","selection":true,"feature":"plan_check"}),
  Object.freeze({"id":"btnRefreshSelectedTokenV2","label":"刷新 AT","section":"操作","action":"refreshSelectedToken","className":"jobs-tb-btn jobs-tb-btn--primary","title":"按已保存的刷新驱动获取最新 AT","selection":true,"feature":"token_refresh"}),
  Object.freeze({"id":"btnReimportSelectedC2aV2","label":"批量同步到 C2A","section":"操作","action":"reimportSelectedC2a","className":"jobs-tb-btn jobs-tb-btn--good","title":"批量同步选中账号的本地当前 AT，支持跨页选择；只更新唯一同邮箱的 C2A 既有账号","selection":true,"feature":"c2a_sync"}),
  Object.freeze({"id":"btnEmailChangeSelectedV2","label":"批量换绑邮箱","section":"操作","action":"openBulkEmailChangeForSelectedAccounts","className":"jobs-tb-btn jobs-tb-btn--primary","title":"为选中账号批量领取新邮箱并执行协议换绑","selection":true}),
  Object.freeze({"id":"btnCheckSelectedDeactivationMailV2","label":"查封号邮件","section":"操作","action":"checkSelectedDeactivationMail","className":"jobs-tb-btn jobs-tb-btn--primary","title":"扫描 Email Butler / Cloudflare / iCloud 转发邮箱中的 OpenAI 封号通知；不会刷新 AT","selection":true,"feature":"deactivation_mail"}),
  Object.freeze({"id":"btnAddPasswordSelectedAccountsV2","label":"补密码","section":"操作","action":"addPasswordSelectedAccounts","className":"jobs-tb-btn jobs-tb-btn--good","title":"只给选中账号补充登录密码","selection":true,"feature":"password_setup"}),
  Object.freeze({"id":"btnAddTwofaSelectedAccountsV2","label":"补 2FA","section":"操作","action":"addTwofaSelectedAccounts","className":"jobs-tb-btn jobs-tb-btn--good","title":"只给选中账号补充 Authenticator 2FA","selection":true}),
  Object.freeze({"id":"btnChangePasswordSelectedAccountsV2","label":"修改密码","section":"操作","action":"changePasswordSelectedAccounts","className":"jobs-tb-btn jobs-tb-btn--primary","title":"强制通过忘记密码流程修改选中账号密码","selection":true,"feature":"password_setup"}),
  Object.freeze({"id":"btnChangeTwofaSelectedAccountsV2","label":"修改 2FA","section":"操作","action":"changeTwofaSelectedAccounts","className":"jobs-tb-btn jobs-tb-btn--primary","title":"先关闭旧 Authenticator，再启用并确认新的 2FA","selection":true,"feature":"twofa_change"}),
  Object.freeze({"id":"btnCompleteSelectedAccountsV2","label":"补全账号","section":"操作","action":"completeSelectedAccounts","className":"jobs-tb-btn jobs-tb-btn--good","title":"按配置补全账号密码、套餐、2FA、Codex；刷新 AT 是否包含由配置决定","selection":true}),
  Object.freeze({"id":"btnRetrySelectedRegistrationV2","label":"重跑注册","section":"操作","action":"retryAccountRegistration","className":"jobs-tb-btn jobs-tb-btn--primary","title":"找到选中账号的原注册任务，按当前进度继续注册或补跑缺失步骤","selection":true}),
  Object.freeze({"id":"btnRetrySelectedCodexV2","label":"补 Codex","section":"操作","action":"retrySelectedCodex","className":"jobs-tb-btn jobs-tb-btn--primary","title":"给选中的账号批量补跑 Codex 授权","selection":true,"feature":"codex_retry"}),
  Object.freeze({"id":"btnExtractSelectedLinksV2","label":"提链","section":"操作","action":"extractSelectedLinks","className":"jobs-tb-btn jobs-tb-btn--good","title":"仅给已确认 Plus 免费试用资格的 free 账号批量提链；折扣优惠会跳过","selection":true,"feature":"extract_link"}),
  Object.freeze({"id":"btnBulkFromAccountFilters","label":"按当前筛选创建批次","section":"批次与巡检","action":"bulk-from-account-filters","className":"jobs-tb-btn","title":"","selection":false}),
  Object.freeze({"id":"btnBulkFromSelectedAccounts","label":"用已选账号创建批次","section":"批次与巡检","action":"bulk-from-selected-accounts","className":"jobs-tb-btn","title":"","selection":false}),
  Object.freeze({"id":"btnAccountInspection","label":"一键巡检","section":"批次与巡检","action":"openAccountInspectionStart","className":"jobs-tb-btn","title":"","selection":false}),
  Object.freeze({"id":"btnAccountInspectionHistory","label":"巡检历史","section":"批次与巡检","action":"openAccountInspectionHistory","className":"jobs-tb-btn","title":"","selection":false}),
  Object.freeze({"id":"btnCopySelectedTokensV2","label":"复制 Token","section":"复制与导出","action":"copySelectedAccountTokens","className":"jobs-tb-btn jobs-tb-btn--good","title":"复制选中账号的 Token，每个账号一行","selection":true}),
  Object.freeze({"id":"btnCopySelectedLinesV2","label":"复制行","section":"复制与导出","action":"copySelectedAccountLines","className":"jobs-tb-btn jobs-tb-btn--good","title":"复制选中账号的完整整行，每个账号一行","selection":true}),
  Object.freeze({"id":"btnCopySelectedExtractLinksV2","label":"复制提炼地址","section":"复制与导出","action":"copySelectedAccountExtractLinks","className":"jobs-tb-btn jobs-tb-btn--good","title":"复制选中账号已成功生成的提炼地址，每个地址一行","selection":true}),
  Object.freeze({"id":"btnCopySelectedEmailsV2","label":"复制邮箱","section":"复制与导出","action":"copySelectedAccountEmails","className":"jobs-tb-btn jobs-tb-btn--good","title":"复制选中账号的邮箱，每个账号一行","selection":true}),
  Object.freeze({"id":"btnCopySelectedPasswordsV2","label":"复制密码","section":"复制与导出","action":"copySelectedAccountPasswords","className":"jobs-tb-btn jobs-tb-btn--good","title":"复制选中账号中本地已保存的账号密码，格式为 邮箱----密码","selection":true}),
  Object.freeze({"id":"btnCopySelectedTotpsV2","label":"复制 2FA","section":"复制与导出","action":"copySelectedAccountTotpSecrets","className":"jobs-tb-btn jobs-tb-btn--good","title":"复制选中账号的 2FA 密钥，每个账号一行，不是 6 位验证码","selection":true}),
  Object.freeze({"id":"btnDownloadSelectedTxtV2","label":"下载 TXT","section":"复制与导出","action":"downloadSelectedAccountTxt","className":"jobs-tb-btn jobs-tb-btn--good","title":"把选中账号的完整整行保存为 TXT 文件，每个账号一行","selection":true}),
  Object.freeze({"id":"btnDownloadSelectedSessionsV2","label":"下载 Session","section":"复制与导出","action":"downloadSelectedAccountSessions","className":"jobs-tb-btn jobs-tb-btn--good","title":"把选中账号已保存的 Session 按每账号一个 JSON 打包为 ZIP；缺失账号列入结果清单","selection":true}),
  Object.freeze({"id":"btnMarkSelectedEmailInvalidV2","label":"标记邮箱失效","section":"资产管理","action":"setAccountsEmailInvalid:1","className":"jobs-tb-btn","title":"为选中账号标记邮箱失效，不修改 OpenAI 账号状态","selection":true}),
  Object.freeze({"id":"btnClearSelectedEmailInvalidV2","label":"解除邮箱失效","section":"资产管理","action":"setAccountsEmailInvalid:0","className":"jobs-tb-btn","title":"仅清除本地邮箱失效标记，邮箱可用性仍需确认","selection":true}),
  Object.freeze({"id":"btnDownloadSelectedCpaV2","label":"下载 CPA","section":"资产管理","action":"downloadSelectedCpa","className":"jobs-tb-btn jobs-tb-btn--good","title":"从 CPA auth-files 下载选中账号的 Codex JSON，并打包 ZIP","selection":true,"feature":"cpa_download"}),
  Object.freeze({"id":"btnUploadSelectedCodexSub2V2","label":"上传 sub2","section":"资产管理","action":"uploadSelectedCodexSub2","className":"jobs-tb-btn jobs-tb-btn--good","title":"把选中账号已通过的 Codex OAuth 凭证上传到 sub2api","selection":true,"feature":"sub2_upload"}),
  Object.freeze({"id":"btnStopSelectedCodexV2","label":"停止 Codex","section":"资产管理","action":"stopSelectedCodex","className":"jobs-tb-btn jobs-tb-btn--danger","title":"停止选中账号中正在补跑的 Codex 授权","selection":true}),
  Object.freeze({"id":"btnArchiveSelectedAccountsV2","label":"归档选中","section":"资产管理","action":"archiveSelectedAccounts","className":"jobs-tb-btn","title":"归档选中的账号；默认账号列表将不再查询/显示这些账号","selection":true}),
  Object.freeze({"id":"btnDeleteSelectedAccountsV2","label":"删除","section":"资产管理","action":"deleteSelectedAccounts","className":"jobs-tb-btn jobs-tb-btn--danger","title":"删除选中的本地账号/token记录","selection":true}),
  Object.freeze({"id":"btnDeleteDeactivatedAccounts","label":"删除已废","section":"资产管理","action":"deleteDeactivatedAccounts","className":"jobs-tb-btn jobs-tb-btn--danger","title":"","selection":false}),
]);
