import {createApp, defineComponent, h, nextTick, shallowRef} from 'vue';
import {request} from './api/client';
import BulkList from './features/bulk/BulkList.vue';
import type {BulkListDependencies, BulkNavigation} from './features/bulk/contracts';
export {mountBulkReport} from './features/bulk/mountBulkReport';

type MountOptions = Pick<BulkListDependencies, 'callbacks'> & {view: BulkNavigation};

export function mountBulkList(element: HTMLElement, options: MountOptions) {
  const navigation = shallowRef(options.view);
  const list = shallowRef<InstanceType<typeof BulkList>>();
  const deps: BulkListDependencies = {
    callbacks: options.callbacks,
    api: {
      async request(path, {signal}) {
        const payload = await request<{data?: unknown}>(`/api/bulk${path}`, {signal});
        return payload?.data ?? payload;
      },
    },
  };
  const app = createApp(defineComponent({
    setup: () => () => h(BulkList, {ref: list, navigation: navigation.value, deps}),
  }));
  app.mount(element);
  return {
    setView(view: BulkNavigation) {navigation.value = view;},
    setVisible(visible: boolean) {
      list.value?.setVisible(visible);
      // Wait for a restored route to reach the component before reading its cursor.
      if (visible) void nextTick(() => list.value?.refresh());
    },
    refresh(poll = false) {return list.value?.refresh(poll);},
    destroy() {app.unmount();},
  };
}
