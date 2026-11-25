import {describe,expect,it} from 'vitest';
import {ACCOUNT_ACTION_USAGE_KEY,ACCOUNT_QUICK_ACTION_DEFAULTS} from './useAccountQuickActions';

describe('账号快捷操作元数据',()=>{
  it('保留历史键名但固定快捷入口顺序',()=>{
    expect(ACCOUNT_ACTION_USAGE_KEY).toBe('turb_account_action_usage_v1');
    expect(ACCOUNT_QUICK_ACTION_DEFAULTS).toEqual([
      'btnCopySelectedTokensV2',
      'btnRefreshSelectedTokenV2',
      'btnCopySelectedLinesV2',
      'btnRetrySelectedCodexV2',
      'btnArchiveSelectedAccountsV2',
    ]);
  });
});
