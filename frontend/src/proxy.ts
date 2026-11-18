import { createApp } from 'vue';
import ProxyTrafficPage from './features/proxy/ProxyTrafficPage.vue';
import type { ProxyTrafficDeps, ProxyTrafficHandle } from './features/proxy/contracts';
export type { ProxyTrafficDeps, ProxyTrafficHandle } from './features/proxy/contracts';
/** The host owns lazy loading/navigation; this mount owns the complete read-only page. */
export function mountProxyTraffic(element: HTMLElement, deps: ProxyTrafficDeps = {}): ProxyTrafficHandle {
  const app = createApp(ProxyTrafficPage, { deps });
  const page = app.mount(element) as InstanceType<typeof ProxyTrafficPage>;
  return {
    load: page.load,
    setVisible: page.setVisible,
    setView: page.setView,
    closeDetail: page.closeDetail,
    destroy: () => app.unmount(),
  };
}
