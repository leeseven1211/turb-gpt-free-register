const test = require('node:test');
const assert = require('node:assert/strict');
const {harness, field, createConfigView, cleanup, flush} = require('./vue_fixture.cjs');
const {ConfigApiError, createConfigApi} = harness.load('src/api/config.ts');
test.afterEach(cleanup);
test.after(() => harness.close());
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => {resolve = yes; reject = no;});
  return {promise, resolve, reject};
}
const fields = () => [field('REGISTER_NAME', '注册主链路', {value: 'old'}), field('ROXY_API_BASE', 'RoxyBrowser')];

test('配置保存使 schema 缓存失效，旧读取不覆盖新一代', async () => {
  const old = deferred(), calls = [];
  const api = createConfigApi(async (url, options = {}) => {
    calls.push({url, options});
    if (calls.length === 1) return old.promise;
    if (options.method === 'POST') return Response.json({ok:true, updated:['REGISTER_NAME']});
    return Response.json([field('REGISTER_NAME', '注册主链路', {value:'saved'})]);
  });
  const reading = api.getSchema();
  await api.save({REGISTER_NAME:'saved'});
  old.resolve(Response.json(fields()));
  await reading;
  assert.equal((await api.getSchema())[0].value, 'saved');
  assert.equal(calls.length, 3);
  assert.deepEqual(JSON.parse(calls[1].options.body), {updates:{REGISTER_NAME:'saved'}});
  assert.equal(calls[1].options.credentials, 'same-origin');
});

test('保存中可以跨菜单继续编辑，重复点击只提交一次，回到原值也能再次保存', async () => {
  const pending = deferred();
  const view = createConfigView(fields(), {save: () => pending.promise});
  await view.edit('REGISTER_NAME', 'submitted');
  const saving = view.owner.saveAll();
  await view.edit('ROXY_API_BASE', 'http://fixture.invalid');
  view.owner.setField('REGISTER_NAME', 'old');
  assert.equal((await view.owner.saveAll()).status, 'busy');
  assert.deepEqual(view.saves, [{REGISTER_NAME: 'submitted'}]);
  pending.resolve({ok: true, updated: ['REGISTER_NAME']});
  assert.equal((await saving).status, 'saved');
  assert.equal(view.owner.readField('REGISTER_NAME'), 'old');
  assert.equal(view.owner.isDirty('REGISTER_NAME'), true);
  assert.equal(view.owner.readField('ROXY_API_BASE'), 'http://fixture.invalid');
  view.dependencies.save = async updates => ({ok: true, updated: Object.keys(updates)});
  await view.owner.saveAll();
  assert.deepEqual(view.saves[1], {REGISTER_NAME: 'old', ROXY_API_BASE: 'http://fixture.invalid'});
});

test('旧请求的字段校验结果只标记仍是同一版的输入', async () => {
  const pending = deferred();
  const view = createConfigView(fields(), {save: () => pending.promise});
  view.owner.setField('REGISTER_NAME', 'submitted');
  const saving = view.owner.saveAll();
  view.owner.setField('REGISTER_NAME', 'newer');
  pending.reject(new ConfigApiError('invalid', 400, 'validation', {REGISTER_NAME: '旧版本校验错误'}));
  await saving;
  assert.deepEqual({...view.owner.fieldErrors}, {});
  assert.equal(view.owner.readField('REGISTER_NAME'), 'newer');
  assert.equal(view.owner.isDirty('REGISTER_NAME'), true);
});

test('缺少有效保存回执时保留草稿', async () => {
  const view = createConfigView(fields(), {save: async () => {throw new ConfigApiError('保存回执无效', 502, 'invalid_receipt');}});
  view.owner.setField('REGISTER_NAME', 'draft');
  assert.equal((await view.owner.saveAll()).status, 'error');
  assert.equal(view.owner.readField('REGISTER_NAME'), 'draft');
  assert.equal(view.owner.isDirty('REGISTER_NAME'), true);
  assert.equal(view.owner.receipt.value, null);
});

test('回执只清已保存项，私密值不回显，刷新失败仍说明哪些更改已保存', async () => {
  const view = createConfigView([...fields(), field('API_KEY', '通用配置', {secret: true, configured: true})], {
    save: async () => ({ok: true, updated: ['API_KEY'], ignored: ['REGISTER_NAME'], persisted_db_revision: 42}),
    getSchema: async () => {throw new Error('offline');},
  });
  view.owner.setField('REGISTER_NAME', 'unsaved');
  view.owner.setField('API_KEY', 'SYNTHETIC_PRIVATE_KEY');
  const result = await view.owner.saveAll();
  await flush();
  assert.equal(result.status, 'saved');
  assert.equal(view.owner.receipt.value.refreshFailed, true);
  assert.deepEqual(view.owner.receipt.value.savedKeys, ['API_KEY']);
  assert.equal(view.owner.isDirty('REGISTER_NAME'), true);
  assert.equal(view.owner.isDirty('API_KEY'), false);
  assert.equal(view.owner.readField('API_KEY'), '');
  assert.equal(JSON.stringify(view.owner.fields.value).includes('SYNTHETIC_PRIVATE_KEY'), false);
  assert.match(view.wrapper.text(), /42/);
});

test('保存前发出的读取晚返回时不会覆盖新配置或新草稿', async () => {
  const old = deferred();
  let reads = 0;
  const view = createConfigView(fields(), {getSchema: () => ++reads === 1 ? old.promise : Promise.resolve([
    field('REGISTER_NAME', '注册主链路', {value: 'saved'}), field('ROXY_API_BASE', 'RoxyBrowser'),
  ])});
  const reading = view.owner.refresh();
  view.owner.setField('REGISTER_NAME', 'saved');
  await view.owner.saveAll();
  view.owner.setField('REGISTER_NAME', 'newer-draft');
  old.resolve(fields());
  await reading;
  assert.equal(view.owner.readField('REGISTER_NAME', 'saved'), 'saved');
  assert.equal(view.owner.readField('REGISTER_NAME'), 'newer-draft');
  assert.equal(view.owner.isDirty('REGISTER_NAME'), true);
});

test('保存刷新重绘时保留正在编辑的密钥、焦点和光标位置', async () => {
  const refresh = deferred();
  const schema = [...fields(), field('API_KEY', '通用配置', {secret: true, configured: true})];
  const view = createConfigView(schema, {getSchema: () => refresh.promise});
  await view.edit('REGISTER_NAME', 'saved');
  const saving = view.owner.saveAll();
  await flush();
  await view.edit('API_KEY', 'draft-private-key');
  const input = view.control('API_KEY').element;
  input.focus();
  input.setSelectionRange(2, 7);
  refresh.resolve(schema);
  await saving;
  await flush();
  assert.equal(view.control('API_KEY').element, input);
  assert.equal(harness.document.activeElement, input);
  assert.equal(input.value, 'draft-private-key');
  assert.deepEqual([input.selectionStart, input.selectionEnd], [2, 7]);
  assert.equal(view.owner.secretDraft('API_KEY').mode, 'set');
});
