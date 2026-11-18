import {mount, flushPromises} from '@vue/test-utils';
import {afterEach, expect, it, vi} from 'vitest';
import {effectScope} from 'vue';
import ConfigActionTools from './ConfigActionTools.vue';
import ConfigFieldActions from './ConfigFieldActions.vue';
import {createConfigDraft} from './useConfigDraft';
import {createConfigActions} from './configActions';
import {useConfigActions} from './useConfigActions';
import type {ConfigField} from './contracts';

const owners: ReturnType<typeof createConfigDraft>[] = [];
const actions: ReturnType<typeof createConfigActions>[] = [];
const wrappers: ReturnType<typeof mount>[] = [];
function fixture() {
  const fields = [{key: 'ROXY_WORKSPACE_ID', value: '7', label: '团队', group: 'RoxyBrowser', type: 'str'}, {key: 'ROXY_PROJECT_ID', value: '8', label: '项目', group: 'RoxyBrowser', type: 'str'}, {key: 'EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY', value: '', label: '密钥', group: '提链', type: 'str', secret: true, configured: true}] as ConfigField[];
  const save = vi.fn(async () => ({ok: true, updated: ['ROXY_WORKSPACE_ID', 'ROXY_PROJECT_ID']}));
  const owner = createConfigDraft({initialFields: fields, api: {getSchema: async () => fields, save, invalidate() {}}});
  owners.push(owner); return {owner, save};
}
afterEach(() => {wrappers.splice(0).forEach(wrapper => wrapper.unmount()); actions.splice(0).forEach(item => item.dispose()); owners.splice(0).forEach(item => item.dispose()); vi.useRealTimers();});

it('Roxy component keeps selection in the sole draft owner and saves only selected IDs', async () => {
  const {owner, save} = fixture(); const action = createConfigActions(owner, {request: async () => ({items: [{id: '1', projectId: '2', label: '团队一'}]})}); actions.push(action);
  const wrapper = mount(ConfigActionTools, {props: {owner, actions: action, tool: 'roxy'}}); wrappers.push(wrapper);
  await wrapper.get('[data-config-action="load-roxy"]').trigger('click'); await flushPromises();
  await wrapper.get('select').setValue('1::2');
  expect(owner.readField('ROXY_WORKSPACE_ID')).toBe('1'); expect(save).not.toHaveBeenCalled();
  await wrapper.get('[data-config-action="save-roxy"]').trigger('click'); await flushPromises();
  expect(save).toHaveBeenCalledWith({ROXY_WORKSPACE_ID: '1', ROXY_PROJECT_ID: '2'});
});
it('quota component preserves zero balance and adds no competing secret editor', async () => {
  const {owner} = fixture(); const action = createConfigActions(owner, {request: async () => ({ok: true, balance: {available_points: 0, pending_points: null, used_points: 0, cost_points: 1}})}); actions.push(action);
  const wrapper = mount(ConfigFieldActions, {props: {actions: action, fieldKey: 'EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY'}}); wrappers.push(wrapper);
  await wrapper.get('button').trigger('click'); await flushPromises();
  expect(wrapper.findAll('input')).toHaveLength(0); expect(wrapper.get('[role="status"]').text()).toContain('可用 0 积分');
});
it('Sentinel mount starts observation and deactivation stops subsequent polling', async () => {
  vi.useFakeTimers(); const {owner} = fixture(); const request = vi.fn(async () => ({ok: true, running: true})); const action = createConfigActions(owner, {request}); actions.push(action);
  const wrapper = mount(ConfigActionTools, {props: {owner, actions: action, tool: 'sentinel', active: true}}); wrappers.push(wrapper); await flushPromises();
  expect(request).toHaveBeenCalledTimes(1); await wrapper.setProps({active: false});
  await vi.advanceTimersByTimeAsync(4500); expect(request).toHaveBeenCalledTimes(1);
});
it('scope cleanup removes the visibility listener and stops polling', async () => {
  vi.useFakeTimers(); const {owner} = fixture(); const request = vi.fn(async () => ({ok: true, running: true}));
  const remove = vi.spyOn(document, 'removeEventListener'); const scope = effectScope();
  const action = scope.run(() => useConfigActions(owner, {request}))!; action.setVisible('sentinel', true); await flushPromises(); scope.stop();
  await vi.advanceTimersByTimeAsync(4500); expect(request).toHaveBeenCalledTimes(1); expect(remove).toHaveBeenCalledWith('visibilitychange', expect.any(Function));
});
