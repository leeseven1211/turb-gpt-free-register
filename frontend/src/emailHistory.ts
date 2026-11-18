import {createApp} from 'vue';
import EmailHistoryPage from './features/emailHistory/EmailHistoryPage.vue';

export function mountEmailHistory(element: HTMLElement, deps: {clipboard: (value: string) => Promise<boolean>}) {
  const app = createApp(EmailHistoryPage, {clipboard: deps.clipboard});
  const page = app.mount(element) as InstanceType<typeof EmailHistoryPage>;
  return {setView: page.setView, setVisible: page.setVisible, refresh: page.refresh, destroy: () => app.unmount()};
}
