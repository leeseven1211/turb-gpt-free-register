import { createApp } from 'vue';
import TaskCenter from './features/tasks/TaskCenter.vue';

/** 任务模块只拥有挂载点和自身详情；全站导航仍由当前应用壳层拥有。 */
export function mountTaskCenter(element: HTMLElement, callbacks: {
  onBatch?: (batchId: string, roundId?: string) => void;
  onChanged?: () => void;
} = {}) {
  const app = createApp(TaskCenter, callbacks);
  const instance = app.mount(element) as InstanceType<typeof TaskCenter>;
  return instance;
}
