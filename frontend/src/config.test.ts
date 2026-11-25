import {flushPromises} from '@vue/test-utils';
import {afterEach, expect, it, vi} from 'vitest';
import {mountConfig} from './config';

let mounted: ReturnType<typeof mountConfig> | undefined;
afterEach(() => {
  mounted?.destroy(); mounted = undefined;
  document.body.replaceChildren(); localStorage.clear();
  vi.useRealTimers(); vi.unstubAllGlobals();
});

function setup(hidden = false) {
  vi.useFakeTimers();
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(hidden);
  const fetcher = vi.fn(async (path: string) => new Response(JSON.stringify(
    path === '/api/config'
      ? [{key: 'SYSTEM_FIELD', group: '通用配置', label: '通用字段', type: 'str', value: ''}]
      : path === '/api/maintenance/sentinel' ? {ok: true, running: true} : {items: []},
  ), {headers: {'Content-Type': 'application/json'}}));
  vi.stubGlobal('fetch', fetcher);
  const element = document.createElement('div');
  document.body.append(element);
  mounted = mountConfig(element, {onSavedFields() {}, onNavigateTasks() {}});
  return {fetcher, polls: () => fetcher.mock.calls.filter(([path]) => path === '/api/maintenance/sentinel').length};
}

it('the production mount suspends polling when the document is hidden and removes its listener on destroy', async () => {
  const {polls} = setup();
  await flushPromises(); expect(polls()).toBe(1);
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
  document.dispatchEvent(new Event('visibilitychange'));
  await vi.advanceTimersByTimeAsync(6000); expect(polls()).toBe(1);
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
  document.dispatchEvent(new Event('visibilitychange'));
  await flushPromises(); expect(polls()).toBe(2);
  const remove = vi.spyOn(document, 'removeEventListener');
  mounted!.destroy(); mounted = undefined;
  expect(remove).toHaveBeenCalledWith('visibilitychange', expect.any(Function));
  document.dispatchEvent(new Event('visibilitychange'));
  await vi.advanceTimersByTimeAsync(6000); expect(polls()).toBe(2);
});

it('the production mount respects initial document visibility and keeps a departed page inactive', async () => {
  const {polls} = setup(true);
  await flushPromises(); await vi.advanceTimersByTimeAsync(6000);
  expect(polls()).toBe(0);
  mounted!.setVisible(false);
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
  document.dispatchEvent(new Event('visibilitychange'));
  await flushPromises(); await vi.advanceTimersByTimeAsync(6000);
  expect(polls()).toBe(0);
  mounted!.setVisible(true);
  await flushPromises(); expect(polls()).toBe(1);
});
