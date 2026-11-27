// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { effectScope, nextTick, ref } from 'vue';
import { useTeamPolling } from './useTeamPolling';

afterEach(() => vi.useRealTimers());

describe('Team 可见性轮询', () => {
  it('切走后旧请求仍在执行时，恢复可见不会丢失下一轮', async () => {
    vi.useFakeTimers();
    const visible = ref(true);
    let finishFirst: () => void = () => {};
    const first = new Promise<void>(resolve => { finishFirst = resolve; });
    const onPoll = vi.fn().mockImplementationOnce(() => first).mockResolvedValue(undefined);
    const scope = effectScope();
    scope.run(() => useTeamPolling({ visible: () => visible.value, shouldPoll: () => true, onPoll, intervalMs: 500 }));
    await vi.advanceTimersByTimeAsync(500);
    expect(onPoll).toHaveBeenCalledTimes(1);
    visible.value = false;
    await nextTick();
    visible.value = true;
    await nextTick();
    finishFirst();
    await Promise.resolve();
    await Promise.resolve();
    expect(onPoll).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(500);
    expect(onPoll).toHaveBeenCalledTimes(3);
    scope.stop();
    await vi.advanceTimersByTimeAsync(1000);
    expect(onPoll).toHaveBeenCalledTimes(3);
  });
});
