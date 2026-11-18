import {onScopeDispose} from 'vue';
import {createConfigActions, type ConfigActionDependencies} from './configActions';
import type {ConfigDraftOwner} from './contracts';

/** Component-scoped visibility lifecycle; accepted POSTs remain owned by Task Center. */
export function useConfigActions(owner: ConfigDraftOwner, dependencies: ConfigActionDependencies = {}) {
  const actions = createConfigActions(owner, dependencies);
  const visibility = () => actions.setForeground(!document.hidden);
  if (typeof document !== 'undefined') {
    visibility();
    document.addEventListener('visibilitychange', visibility);
  }
  onScopeDispose(() => {
    if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', visibility);
    actions.dispose();
  });
  return actions;
}
