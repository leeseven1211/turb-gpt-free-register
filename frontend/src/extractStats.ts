import {createApp} from 'vue';
import ExtractStatsPage from './features/extractStats/ExtractStatsPage.vue';
import type {StatsDependencies} from './features/extractStats/statistics';
import '../../webui/static/css/pages/extract_stats.css';

export function mountExtractStats(element: HTMLElement, deps: StatsDependencies = {}) {
  const app = createApp(ExtractStatsPage, {deps});
  const page = app.mount(element) as InstanceType<typeof ExtractStatsPage>;
  return {load: page.load, setVisible: page.setVisible, destroy: () => app.unmount()};
}
