// 保留历史键名，供旧桥接代码平滑升级；当前快捷入口不读写该存储。
export const ACCOUNT_ACTION_USAGE_KEY='turb_account_action_usage_v1';
export const ACCOUNT_QUICK_ACTION_DEFAULTS=Object.freeze([
  'btnCopySelectedTokensV2',
  'btnRefreshSelectedTokenV2',
  'btnCopySelectedLinesV2',
  'btnRetrySelectedCodexV2',
  'btnArchiveSelectedAccountsV2',
]);
