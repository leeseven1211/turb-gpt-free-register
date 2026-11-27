import { onScopeDispose, ref, watch } from 'vue';

export interface UseTeamPollingOptions {
  /** 当前页面或页签是否处于可见状态。 */
  visible: () => boolean;
  /** 是否存在需要持续轮询的活跃任务。 */
  shouldPoll: () => boolean;
  /** 轮询触发回调。 */
  onPoll: () => Promise<void> | void;
  /** 轮询间隔（毫秒），默认 3000ms。 */
  intervalMs?: number;
}

export interface UseTeamPollingHandle {
  isPolling: ReturnType<typeof ref<boolean>>;
  triggerNow: () => Promise<void>;
  stop: () => void;
}

function isDocumentHidden(): boolean {
  return typeof document !== 'undefined' && Boolean(document.hidden);
}

/**
 * 可见性感知的 Team 定时轮询：
 * - 仅当 `visible() && !document.hidden && shouldPoll()` 为真时维持 `setTimeout` 循环
 * - 页面切走或标签页隐藏时立即清除定时器
 * - 恢复可见时若 `shouldPoll()` 仍为真，立即触发一次刷新
 */
export function useTeamPolling(options: UseTeamPollingOptions): UseTeamPollingHandle {
  const intervalMs = Math.max(500, options.intervalMs ?? 3000);
  const isPolling = ref(false);

  let timerId: ReturnType<typeof setTimeout> | undefined;
  let inFlight = false;
  let disposed = false;
  let cycleEpoch = 0;
  let pendingEpoch: number | undefined;

  function clearTimer(): void {
    if (timerId !== undefined) {
      clearTimeout(timerId);
      timerId = undefined;
    }
    isPolling.value = false;
  }

  function canRun(): boolean {
    return !disposed && options.visible() && !isDocumentHidden() && options.shouldPoll();
  }

  function scheduleNext(epoch: number): void {
    clearTimer();
    if (!canRun() || epoch !== cycleEpoch) return;
    isPolling.value = true;
    timerId = setTimeout(() => {
      timerId = undefined;
      if (!canRun() || epoch !== cycleEpoch) {
        isPolling.value = false;
        return;
      }
      void executePoll(epoch);
    }, intervalMs);
  }

  async function executePoll(epoch: number): Promise<void> {
    if (!canRun() || epoch !== cycleEpoch) return;
    if (inFlight) {
      pendingEpoch = epoch;
      return;
    }
    inFlight = true;
    isPolling.value = true;
    try {
      await options.onPoll();
    } finally {
      inFlight = false;
      const pending = pendingEpoch;
      pendingEpoch = undefined;
      if (pending !== undefined && pending === cycleEpoch && canRun()) {
        void executePoll(pending);
      } else if (!disposed && epoch === cycleEpoch && canRun()) {
        scheduleNext(epoch);
      } else {
        isPolling.value = false;
      }
    }
  }

  async function triggerNow(): Promise<void> {
    clearTimer();
    cycleEpoch += 1;
    const epoch = cycleEpoch;
    await executePoll(epoch);
  }

  function stop(): void {
    pendingEpoch = undefined;
    cycleEpoch += 1;
    clearTimer();
  }

  function syncState(becameVisible: boolean): void {
    if (!canRun()) {
      stop();
      return;
    }
    if (becameVisible) {
      void triggerNow();
      return;
    }
    if (timerId === undefined && !inFlight) {
      scheduleNext(cycleEpoch);
    }
  }

  function handleVisibilityChange(): void {
    if (isDocumentHidden()) {
      stop();
      return;
    }
    syncState(true);
  }

  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', handleVisibilityChange);
  }

  watch(
    [() => options.visible(), () => options.shouldPoll()],
    ([nextVisible, nextShould], prevValues) => {
      const prevVisible = prevValues?.[0];
      const becameVisible = prevVisible === false && nextVisible === true && nextShould;
      syncState(becameVisible);
    },
    { immediate: true },
  );

  onScopeDispose(() => {
    disposed = true;
    stop();
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    }
  });

  return {
    isPolling,
    triggerNow,
    stop,
  };
}
