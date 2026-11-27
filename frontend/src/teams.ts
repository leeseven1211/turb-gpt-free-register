import { createApp } from 'vue';
import { createTeamsApi, type TeamsApi } from './api/teams';
import TeamsPageShell from './features/teams/TeamsPageShell.vue';
import type {
  AccountsJoinRequestPayload,
  TeamsHostCallbacks,
  TeamsNavigationState,
} from './features/teams/contracts';

export interface MountTeamsOptions {
  api?: TeamsApi;
  callbacks: TeamsHostCallbacks;
  navigation?: Partial<TeamsNavigationState>;
  visible?: boolean;
}

export interface MountedTeamsApp {
  setVisible(visible: boolean): void;
  navigate(state: Partial<TeamsNavigationState>, mode?: 'push' | 'replace', options?: { emit?: boolean }): void;
  navigationState(): TeamsNavigationState;
  openJoinFromAccounts(payload: AccountsJoinRequestPayload): void;
  openBindModal(): void;
  closeDialogs(): void;
  refresh(): Promise<void>;
  destroy(): void;
}

/** 现有应用壳层拥有侧栏与 hash/history；Team 模块独占 `#teams-page-root` 与内部状态。 */
export function mountTeams(root: HTMLElement, options: MountTeamsOptions): MountedTeamsApp {
  const api = options.api ?? createTeamsApi();
  const app = createApp(TeamsPageShell, {
    api,
    callbacks: options.callbacks,
    initialNavigation: options.navigation,
    initialVisible: options.visible ?? true,
  });
  const instance = app.mount(root) as InstanceType<typeof TeamsPageShell>;

  return {
    setVisible: nextVisible => instance.setVisible(nextVisible),
    navigate: (state, mode = 'push', navOptions) => instance.navigate(state, mode, navOptions),
    navigationState: () => instance.navigationState(),
    openJoinFromAccounts: payload => instance.openJoinFromAccounts(payload),
    openBindModal: () => instance.openBindModal(),
    closeDialogs: () => instance.closeDialogs(),
    refresh: () => instance.refresh(),
    destroy: () => app.unmount(),
  };
}
