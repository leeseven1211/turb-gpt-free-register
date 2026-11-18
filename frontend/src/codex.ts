import {createApp} from 'vue';
import CodexCredentials from './features/codex/CodexCredentials.vue';
import type {CodexCallbacks} from './api/codex';

/** 现有壳层拥有导航；凭证模块独占挂载点与列表状态。 */
export function mountCodexCredentials(element: HTMLElement, callbacks: CodexCallbacks) {
  return createApp(CodexCredentials, {callbacks}).mount(element) as InstanceType<typeof CodexCredentials>;
}
