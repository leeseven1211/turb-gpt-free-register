import type {AccountActionContext} from './useAccounts';

export interface AccountToolbarState {selectedCount:number;archived:boolean;pending?:Readonly<Record<string,boolean>>;labels?:Readonly<Record<string,string>>}
export interface AccountToolbarCapability {enabled:boolean;reason?:string}
export type AccountToolbarCapabilities=Readonly<Record<string,AccountToolbarCapability|undefined>>;
export interface AccountToolbarButton {id:string;label:string;section:string;action:string;className:string;title:string;selection:boolean;feature?:string}
export type AccountToolbarInvoke=(descriptor:string,context:AccountActionContext,trigger:HTMLElement)=>unknown|Promise<unknown>;

export const ACCOUNT_TOOLBAR_SECTIONS=Object.freeze(['查询','处理','运维','服务','账号']);
export const ACCOUNT_TOOLBAR_BUTTONS:readonly Readonly<AccountToolbarButton>[]=Object.freeze([
  Object.freeze({id:'btnCheckSelectedPlansV2',label:'查套餐',section:'查询',action:'checkSelectedPlans',className:'jobs-tb-btn',title:'查询选中账号当前套餐，并检查 free 账号可用的 Plus 免费试用或折扣优惠',selection:true,feature:'plan_check'}),
  Object.freeze({id:'btnAccountInspectionHistory',label:'巡检历史',section:'查询',action:'openAccountInspectionHistory',className:'jobs-tb-btn',title:'打开账号巡检历史，查看当前账号范围的巡检记录',selection:false}),
  Object.freeze({id:'btnCheckSelectedLiveV2',label:'查活',section:'查询',action:'checkSelectedLive',className:'jobs-tb-btn',title:'只在线验证选中账号现有 Token，不发送邮箱验证码或刷新 AT',selection:true,feature:'live_check'}),
  Object.freeze({id:'btnCheckSelectedDeactivationMailV2',label:'封号邮件',section:'查询',action:'checkSelectedDeactivationMail',className:'jobs-tb-btn',title:'扫描选中账号关联邮箱中的 OpenAI 封号通知，不刷新 AT',selection:true,feature:'deactivation_mail'}),

  Object.freeze({id:'btnRefreshSelectedTokenV2',label:'刷新AT',section:'处理',action:'refreshSelectedToken',className:'jobs-tb-btn',title:'按已保存的刷新驱动为选中账号获取最新 AT',selection:true,feature:'token_refresh'}),
  Object.freeze({id:'btnRetrySelectedCodexV2',label:'补Codex',section:'处理',action:'retrySelectedCodex',className:'jobs-tb-btn',title:'给选中的账号批量补跑 Codex 授权',selection:true,feature:'codex_retry'}),
  Object.freeze({id:'btnRetrySelectedRegistrationV2',label:'重跑注册',section:'处理',action:'retryAccountRegistration',className:'jobs-tb-btn',title:'找到选中账号的原注册任务，按当前进度继续注册或补跑缺失步骤',selection:true}),
  Object.freeze({id:'btnAddPasswordSelectedAccountsV2',label:'补密码',section:'处理',action:'addPasswordSelectedAccounts',className:'jobs-tb-btn',title:'只给选中账号补充登录密码',selection:true,feature:'password_setup'}),
  Object.freeze({id:'btnCompleteSelectedAccountsV2',label:'补全账号',section:'处理',action:'completeSelectedAccounts',className:'jobs-tb-btn',title:'按配置补全选中账号的密码、套餐、2FA 和 Codex，刷新 AT 是否包含由配置决定',selection:true}),
  Object.freeze({id:'btnAddTwofaSelectedAccountsV2',label:'补2FA',section:'处理',action:'addTwofaSelectedAccounts',className:'jobs-tb-btn',title:'只给选中账号补充 Authenticator 2FA',selection:true}),
  Object.freeze({id:'btnEmailChangeSelectedV2',label:'换绑邮箱',section:'处理',action:'openBulkEmailChangeForSelectedAccounts',className:'jobs-tb-btn',title:'为选中账号批量领取新邮箱并执行协议换绑',selection:true}),
  Object.freeze({id:'btnChangePasswordSelectedAccountsV2',label:'修改密码',section:'处理',action:'changePasswordSelectedAccounts',className:'jobs-tb-btn',title:'强制通过忘记密码流程修改选中账号密码',selection:true,feature:'password_setup'}),
  Object.freeze({id:'btnChangeTwofaSelectedAccountsV2',label:'改2FA',section:'处理',action:'changeTwofaSelectedAccounts',className:'jobs-tb-btn',title:'先关闭选中账号旧 Authenticator，再启用并确认新的 2FA',selection:true,feature:'twofa_change'}),
  Object.freeze({id:'btnExtractSelectedLinksV2',label:'提链',section:'处理',action:'extractSelectedLinks',className:'jobs-tb-btn',title:'仅给已确认 Plus 免费试用资格的 free 账号批量提链，折扣优惠会跳过',selection:true,feature:'extract_link'}),

  Object.freeze({id:'btnAccountInspection',label:'启动巡检',section:'运维',action:'openAccountInspectionStart',className:'jobs-tb-btn',title:'按当前账号范围启动批量巡检任务',selection:false}),
  Object.freeze({id:'btnBulkFromAccountFilters',label:'筛选建批',section:'运维',action:'bulk-from-account-filters',className:'jobs-tb-btn',title:'按当前账号筛选条件创建批次，不改变当前列表筛选',selection:false}),
  Object.freeze({id:'btnBulkFromSelectedAccounts',label:'已选建批',section:'运维',action:'bulk-from-selected-accounts',className:'jobs-tb-btn',title:'按当前已选账号创建批次，使用跨页选择结果',selection:false}),
  Object.freeze({id:'btnStopSelectedCodexV2',label:'停Codex',section:'运维',action:'stopSelectedCodex',className:'jobs-tb-btn jobs-tb-btn--danger',title:'停止选中账号中正在补跑的 Codex 授权',selection:true}),

  Object.freeze({id:'btnReimportSelectedC2aV2',label:'同步C2A',section:'服务',action:'reimportSelectedC2a',className:'jobs-tb-btn',title:'批量同步选中账号的本地当前 AT 到 C2A，唯一同邮箱时覆盖，未找到时新建账号',selection:true,feature:'c2a_sync'}),
  Object.freeze({id:'btnUploadSelectedCodexSub2V2',label:'传sub2',section:'服务',action:'uploadSelectedCodexSub2',className:'jobs-tb-btn',title:'把选中账号已通过的 Codex OAuth 凭证上传到 sub2api',selection:true,feature:'sub2_upload'}),
  Object.freeze({id:'btnDownloadSelectedCpaV2',label:'导CPA',section:'服务',action:'downloadSelectedCpa',className:'jobs-tb-btn',title:'从 CPA auth-files 下载选中账号的 Codex JSON，并打包为 ZIP',selection:true,feature:'cpa_download'}),
  Object.freeze({id:'btnJoinTeamSelectedV2',label:'加入Team',section:'服务',action:'joinSelectedAccountsToTeam',className:'jobs-tb-btn',title:'将选中的账号批量加入指定 Team 工作区（进入预览与席位确认）',selection:true}),

  Object.freeze({id:'btnCopySelectedTokensV2',label:'复制AT',section:'账号',action:'copySelectedAccountTokens',className:'jobs-tb-btn',title:'复制选中账号的 AT，每个账号一行',selection:true}),
  Object.freeze({id:'btnCopySelectedLinesV2',label:'复制整行',section:'账号',action:'copySelectedAccountLines',className:'jobs-tb-btn',title:'复制选中账号的账号、密码和 2FA，每个账号一行',selection:true}),
  Object.freeze({id:'btnArchiveSelectedAccountsV2',label:'归档选中',section:'账号',action:'archiveSelectedAccounts',className:'jobs-tb-btn',title:'归档选中的账号，默认账号列表将不再查询或显示这些账号',selection:true}),
  Object.freeze({id:'btnDeleteSelectedAccountsV2',label:'删除选中',section:'账号',action:'deleteSelectedAccounts',className:'jobs-tb-btn jobs-tb-btn--danger',title:'删除选中的本地账号和 Token 记录',selection:true}),
  Object.freeze({id:'btnDownloadSelectedTxtV2',label:'下载TXT',section:'账号',action:'downloadSelectedAccountTxt',className:'jobs-tb-btn',title:'把选中账号的完整整行保存为 TXT 文件，每个账号一行',selection:true}),
  Object.freeze({id:'btnCopySelectedEmailsV2',label:'复制邮箱',section:'账号',action:'copySelectedAccountEmails',className:'jobs-tb-btn',title:'复制选中账号的邮箱，每个账号一行',selection:true}),
  Object.freeze({id:'btnDeleteDeactivatedAccounts',label:'清理已废',section:'账号',action:'deleteDeactivatedAccounts',className:'jobs-tb-btn jobs-tb-btn--danger',title:'清理当前归档范围内的已废账号，不受勾选、搜索或分页限制',selection:false}),
  Object.freeze({id:'btnCopySelectedPasswordsV2',label:'复制密码',section:'账号',action:'copySelectedAccountPasswords',className:'jobs-tb-btn',title:'复制选中账号中本地已保存的账号密码，格式为 邮箱----密码',selection:true}),
  Object.freeze({id:'btnCopySelectedTotpsV2',label:'复制密钥',section:'账号',action:'copySelectedAccountTotpSecrets',className:'jobs-tb-btn',title:'复制选中账号的 2FA 密钥（Authenticator 密钥），不是 6 位验证码，每个账号一行',selection:true}),
  Object.freeze({id:'btnCopySelectedExtractLinksV2',label:'复制提链',section:'账号',action:'copySelectedAccountExtractLinks',className:'jobs-tb-btn',title:'复制选中账号已成功生成的提炼地址，每个地址一行',selection:true}),
  Object.freeze({id:'btnDownloadSelectedSessionsV2',label:'下载会话',section:'账号',action:'downloadSelectedAccountSessions',className:'jobs-tb-btn',title:'把选中账号已保存的 Session 按每个账号一个 JSON 打包为 ZIP，缺失账号列入结果清单',selection:true}),
  Object.freeze({id:'btnMarkSelectedEmailInvalidV2',label:'标记失效',section:'账号',action:'setAccountsEmailInvalid:1',className:'jobs-tb-btn',title:'为选中账号标记邮箱失效，不修改 OpenAI 账号状态',selection:true}),
  Object.freeze({id:'btnClearSelectedEmailInvalidV2',label:'解除失效',section:'账号',action:'setAccountsEmailInvalid:0',className:'jobs-tb-btn',title:'仅清除选中账号的本地邮箱失效标记，邮箱可用性仍需确认',selection:true}),
]);
