import {computed, onBeforeUnmount, onMounted, ref, shallowRef} from 'vue';
import {analyticsURL, providerLabel, providerLabels, readStatistics, updatedAt} from './statistics';
import type {RangeDays, Statistics, StatsDependencies} from './statistics';

export function useExtractStats(deps: StatsDependencies) {
  const days = ref<RangeDays>(30), provider = ref('');
  const providers = ref(new Map(providerLabels));
  const scope = computed(() => analyticsURL(days.value, provider.value));
  const lastSuccess = shallowRef<{scope: string; data: Statistics} | null>(null);
  const data = computed(() => lastSuccess.value?.scope === scope.value ? lastSuccess.value.data : null);
  const busy = ref(false), error = ref('');
  let visible = false, disposed = false;
  let pending: {scope: string; controller: AbortController; promise: Promise<void>} | null = null;

  const status = computed(() => {
    if (busy.value) return data.value ? '正在刷新统计…' : '正在加载统计…';
    if (error.value) return '统计加载失败';
    return data.value ? updatedAt(data.value.generated_at) : '准备加载统计';
  });
  function suspend() {
    pending?.controller.abort();
    pending = null;
    busy.value = false;
  }
  function load(): Promise<void> {
    if (disposed || !visible || document.hidden) return Promise.resolve();
    const path = scope.value;
    if (pending?.scope === path) return pending.promise;
    suspend();
    const controller = new AbortController();
    busy.value = true;
    error.value = '';
    const promise = readStatistics(days.value, provider.value, controller.signal).then(result => {
      if (controller.signal.aborted) return;
      lastSuccess.value = {scope: path, data: result};
      for (const {provider_id: id} of result.providers ?? []) {
        if (id && id !== 'lumen') providers.value.set(id, providerLabel(id));
      }
      deps.onReady?.();
    }).catch(failure => {
      if (!controller.signal.aborted) error.value = failure instanceof Error ? failure.message || '请稍后重试' : '请稍后重试';
    }).finally(() => {
      if (pending?.controller === controller) {pending = null; busy.value = false;}
    });
    pending = {scope: path, controller, promise};
    return promise;
  }
  function setDays(value: RangeDays) {
    if (days.value !== value) {days.value = value; void load();}
  }
  function setVisible(value: boolean) {
    if (visible === value) return;
    visible = value;
    if (visible) void load(); else suspend();
  }
  function documentChanged() {
    if (document.hidden) suspend(); else if (visible) void load();
  }
  onMounted(() => {
    document.addEventListener('visibilitychange', documentChanged);
    setVisible(deps.visible ?? true);
  });
  onBeforeUnmount(() => {
    disposed = true;
    suspend();
    document.removeEventListener('visibilitychange', documentChanged);
  });
  return {days, provider, providers, data, busy, error, status, load, setDays, setVisible};
}
