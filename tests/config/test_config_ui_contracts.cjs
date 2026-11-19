// Behavior replacements for ModernConfigUiContractTests' legacy page.js slices.
// The fixture compiles and mounts the production Vue components and draft owner.
const assert = require('node:assert/strict');
const test = require('node:test');
const {harness, field, createConfigView, cleanup, flush, navigation} = require('./vue_fixture.cjs');
const completeSchema = require('../../frontend/src/features/config/schemaNavigation.fixture.json');
test.afterEach(cleanup);

const choices = wrapper => wrapper.findAll('[data-choice]');
const namedChoice = (wrapper, text) => choices(wrapper).find(button => button.text().includes(text));
const country = (key, extra = {}) => field(key, '注册与账号', {
  label: '国家列表', type: 'list_str_multiline', value: ['SG', 'JP'],
  country_codes: ['US', 'JP', 'SG', 'DE'], ...extra,
});

test('country_pickers_search_names_and_codes_and_keep_ordered_pending_selection', async () => {
  for (const key of ['PROXY_POOL_COUNTRIES', 'PLAN_CHECK_COUNTRIES']) {
    const view = createConfigView([country(key)]);
    const wrapper = view.mountField(key);
    const picker = wrapper.get('details');
    assert.equal(picker.element.open, false);
    assert.match(picker.get('summary').text(), /SG.*JP/);
    await picker.get('input[type=search]').setValue('日本');
    assert.equal(choices(picker).length, 1);
    assert.match(choices(picker)[0].text(), /JP/);
    await picker.get('input[type=search]').setValue(' de ');
    assert.equal(choices(picker).length, 1);
    await choices(picker)[0].trigger('click');
    assert.deepEqual(view.owner.readField(key), ['SG', 'JP', 'DE']);
    await picker.get('[aria-label="移除 SG"]').trigger('click');
    assert.deepEqual(view.owner.readField(key), ['JP', 'DE']);
    assert.equal(wrapper.findAll(`[data-key="${key}"]`).length, 1);
    assert.equal(wrapper.find('textarea').exists(), false);
    await picker.get('input[type=search]').setValue('不存在的国家');
    assert.equal(choices(picker).length, 0);
    assert.match(picker.text(), /未找到匹配选项/);
  }
});

test('empty_country_selection_explains_each_feature_and_overrides_saved_values', async () => {
  for (const [key, summary, help] of [
    ['PLAN_CHECK_COUNTRIES', '沿用账号注册国家', '按选择顺序查询；留空沿用账号注册国家，不影响注册查套餐。'],
    ['PROXY_POOL_COUNTRIES', '未选择额外预热国家', '留空不额外预热；实际可用线路取决于代理来源和库存。'],
  ]) {
    const view = createConfigView([country(key, {value: ['JP'], help})]);
    const wrapper = view.mountField(key);
    await wrapper.get('[aria-label="移除 JP"]').trigger('click');
    assert.deepEqual(view.owner.readField(key), []);
    assert.equal(wrapper.get('summary').text(), summary);
    assert.match(wrapper.text(), new RegExp(help));
    assert.equal(wrapper.find('[aria-pressed=true]').exists(), false);
    await view.owner.saveAll();
    assert.deepEqual(view.saves[0], {[key]: []});
  }
});

test('country_inputs_normalize_separators_without_dropping_invalid_values_or_splitting_proxies', async () => {
  for (const key of ['PROXY_POOL_COUNTRIES', 'PLAN_CHECK_COUNTRIES']) {
    const view = createConfigView([country(key, {country_codes: [], value: []})]);
    const wrapper = view.mountField(key);
    await wrapper.get('textarea').setValue('jp, US\n sg jp ZZ');
    assert.deepEqual(view.owner.readField(key), ['JP', 'US', 'SG', 'ZZ']);
    await wrapper.get('textarea').setValue('');
    assert.deepEqual(view.owner.readField(key), []);
  }
  const view = createConfigView([field('PROXY_POOL', '代理与网络', {type: 'list_str_multiline', value: []})]);
  await view.mountField('PROXY_POOL').get('textarea').setValue('http://proxy.test/a,b\nhttp://second.test');
  assert.deepEqual(view.owner.readField('PROXY_POOL'), ['http://proxy.test/a,b', 'http://second.test']);
});

test('config_enum_values_preserve_none_without_changing_text_placeholders', async () => {
  const fields = ['REGISTRATION_PROXY_MODE', 'CLOUDFLARE_AUTH_MODE'].map(key => field(key, '通用配置', {
    value: ' NONE ', options: [{value: 'none', label: '无'}, {value: 'auto', label: '自动'}],
  }));
  const view = createConfigView([...fields, field('REGISTER_NAME', '注册主链路'), field('PROXY_POOL_DEFAULT_COUNTRY', '代理与网络', {value: 'NA', country_codes: ['JP', 'NA']})]);
  for (const {key} of fields) {
    const control = view.mountField(key).get('select');
    assert.equal(control.element.value, 'none');
    assert.equal(control.findAll('option').length, 2);
    await control.setValue('none');
    assert.equal(view.owner.readField(key), 'none');
  }
  const name = view.mountField('REGISTER_NAME').get('input');
  for (const value of ['none', '-', ' 无 ', '']) {
    await name.setValue(value);
    assert.equal(view.owner.readField('REGISTER_NAME'), '');
  }
  await name.setValue(' Alice Smith ');
  assert.equal(view.owner.readField('REGISTER_NAME'), 'Alice Smith');
  // Normalize when editing is committed, without eating the space while typing.
  name.element.value = 'Alice ';
  await name.trigger('input');
  assert.equal(view.owner.readField('REGISTER_NAME'), 'Alice ');
  name.element.value = 'Alice Smith';
  await name.trigger('input');
  await name.trigger('change');
  assert.equal(view.owner.readField('REGISTER_NAME'), 'Alice Smith');
  assert.equal(view.mountField('PROXY_POOL_DEFAULT_COUNTRY').get('select').element.value, 'NA');
});

test('region_select_preserves_empty_and_canonical_options', async () => {
  for (const [value, expected] of [['', ''], ['JP', 'JP'], ['us', 'US'], ['Rand', 'Rand']]) {
    const view = createConfigView([field('PROXY_1024_REGION', '代理与网络', {value, options: [
      {value: '', label: '沿用 API URL'}, {value: 'US', label: '美国'},
      {value: 'JP', label: '日本'}, {value: 'Rand', label: '随机地区'}, null, {}, {value: null},
    ]})]);
    const wrapper = view.mountField('PROXY_1024_REGION');
    assert.equal(wrapper.get('select').element.value, expected);
    assert.equal(wrapper.findAll('option').length, 4);
    assert.doesNotMatch(wrapper.text(), /当前配置/);
    await wrapper.get('select').setValue('');
    assert.equal(view.owner.readField('PROXY_1024_REGION'), '');
  }
});

test('email_source_uses_an_ordered_multi_select', async () => {
  const view = createConfigView([field('EMAIL_SOURCE', '邮箱 / OTP', {value: 'mailnest,outlook', csv_options: ['outlook', 'mailnest'], options: [
    {value: 'outlook', label: 'Outlook'}, {value: 'mailnest', label: 'MailNest'},
  ]})]);
  const picker = view.wrapper.get('details');
  assert.equal(picker.get('summary').text(), 'MailNest、Outlook');
  await namedChoice(picker, 'MailNest').trigger('click');
  await namedChoice(picker, 'MailNest').trigger('click');
  assert.equal(view.owner.readField('EMAIL_SOURCE'), 'outlook,mailnest');
  await view.owner.saveAll();
  assert.deepEqual(view.saves[0], {EMAIL_SOURCE: 'outlook,mailnest'});
});

test('regular_config_controls_expose_field_labels', () => {
  const fields = [field('COUNT', '通用配置', {label: '数量', type: 'int', value: 2}),
    field('RATIO', '通用配置', {label: '比例', type: 'float', value: 0.5}),
    field('NAME', '通用配置', {label: '名称', value: 'demo'}),
    field('LINES', '通用配置', {label: '多行', type: 'list_str_multiline', value: ['a']})];
  const view = createConfigView(fields);
  for (const schema of fields) {
    const wrapper = view.mountField(schema.key);
    const control = wrapper.get(`[data-key="${schema.key}"]`);
    assert.equal(control.attributes('aria-label'), schema.label);
    assert.equal(wrapper.get(`label[for="${control.attributes('id')}"]`).text(), schema.label);
  }
});

test('config_page_exposes_runtime_status_and_refreshes_after_save', async () => {
  const fields = [field('REGISTER_NAME', '注册主链路', {value: 'old', invalid_env: true}), field('BOOT', '注册主链路', {restart: true})];
  let reads = 0;
  const view = createConfigView(fields, {getSchema: async () => {reads++; return fields.map(item => ({...item, invalid_env: false, value: item.key === 'REGISTER_NAME' ? 'new' : item.value}));},
    save: async updates => ({updated: Object.keys(updates), persisted_db_revision: 9, local_snapshot_revision: 4, web_reloaded: true, restart_required: ['BOOT'], worker_application: {state: 'pending', applied_db_revision: 8}})});
  assert.match(view.wrapper.text(), /配置值无效，未生效/);
  assert.match(view.wrapper.text(), /已配置 · 需重启/);
  await view.control('REGISTER_NAME').setValue('new');
  await view.save();
  assert.equal(reads, 1);
  assert.doesNotMatch(view.wrapper.text(), /配置值无效，未生效/);
  assert.equal(view.owner.readField('REGISTER_NAME', 'saved'), 'new');
  assert.match(view.wrapper.get('.config-vue-savebar').text(), /数据库保存版本 9 · Worker 等待应用/);
  assert.match(view.wrapper.get('.config-vue-savebar').text(), /需重启：BOOT/);
});

test('extract_link_fields_cover_platforms_and_payment_without_menu_introduction', async () => {
  const view = createConfigView(completeSchema);
  for (const key of ['EXTRACT_LINK_DEFAULT_PROVIDER', 'EXTRACT_LINK_HUANGUANG_CDK', 'EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY']) {
    await view.search(key);
    assert.equal(view.wrapper.get('[data-config-section]').attributes('data-config-section'), '提链');
    assert.equal(view.wrapper.findAll(`[data-config-setting="${key}"]`).length, 1);
  }
  assert.doesNotMatch(view.wrapper.text(), /管理平台启用、默认模式、支付权限、平台凭据与并发。/);
});

test('workspace_has_one_save_bar_without_redundant_page_header', async () => {
  const view = createConfigView([field('REGISTER_NAME', '注册主链路')]);
  await view.control('REGISTER_NAME').setValue('draft');
  assert.equal(view.wrapper.findAll('.config-vue-savebar').length, 1);
  assert.equal(view.wrapper.find('h1').exists(), false);
  assert.equal(view.wrapper.findAll('h2').length, 1);
  assert.match(view.wrapper.get('.config-vue-savebar').text(), /撤销修改.*保存全部配置/);
});

test('navigation_exposes_grouped_search_metadata_and_dirty_state', async () => {
  const view = createConfigView([field('REGISTER_NAME', '注册主链路', {help: '昵称搜索帮助'}), field('C2A_API_BASE', 'C2A'), field('TASK_CENTER_RETENTION_DAYS', '任务中心')]);
  assert.match(view.wrapper.get('nav').text(), /业务流程.*资源与服务.*系统/);
  await view.control('REGISTER_NAME').setValue('draft');
  assert.match(view.wrapper.get('[data-config-nav="注册与账号"]').text(), /1 待保存/);
  await view.search('昵称搜索帮助');
  assert.equal(view.wrapper.findAll('[data-config-nav]').length, 1);
  await view.search('C2A_API_BASE');
  assert.equal(view.wrapper.get('[data-config-nav][aria-current=page]').text().startsWith('服务集成'), true);
  assert.equal(view.owner.readField('REGISTER_NAME'), 'draft');
});

test('fields_show_compact_help_without_detail_disclosures', async () => {
  const view = createConfigView(['ROXY_ONE_PROFILE_PER_ACCOUNT', 'ROXY_RANDOM_PROFILE_NAME_ON_CREATE'].map(key => field(key, 'RoxyBrowser', {label:'浏览器配置', type: 'bool', help: `字段帮助 ${key}`})));
  for (const key of ['ROXY_ONE_PROFILE_PER_ACCOUNT', 'ROXY_RANDOM_PROFILE_NAME_ON_CREATE']) {
    const row = view.wrapper.get(`[data-config-setting="${key}"]`);
    assert.equal(row.find('details').exists(), false);
    assert.equal(row.get('.hint').text(), `字段帮助 ${key}`);
    assert.equal(row.get('code').text(), key);
    assert.match(row.get('[data-key]').attributes('aria-describedby'), new RegExp(`${key}-help`));
  }
  assert.doesNotMatch(view.wrapper.text(), /详细帮助/);
});

test('unsaved_config_is_protected_and_reset_only_discards_pending_values', async t => {
  const view = createConfigView([field('REGISTER_NAME', '注册主链路', {value: 'saved'}), field('C2A_API_BASE', 'C2A', {value: 'saved-base'})]);
  const unload = () => {const event = new window.Event('beforeunload', {cancelable: true}); window.dispatchEvent(event); return event.defaultPrevented;};
  assert.equal(unload(), false);
  await view.edit('REGISTER_NAME', 'draft');
  await view.edit('C2A_API_BASE', 'draft-base');
  assert.equal(unload(), true);
  const confirm = t.mock.method(window, 'confirm', () => false);
  await view.wrapper.get('.config-vue-savebar button').trigger('click');
  assert.equal(view.owner.dirtyCount.value, 2);
  confirm.mock.mockImplementation(() => true);
  await view.wrapper.get('.config-vue-savebar button').trigger('click');
  assert.equal(view.owner.dirtyCount.value, 0);
  assert.equal(view.owner.readField('REGISTER_NAME'), 'saved');
  assert.equal(view.owner.readField('C2A_API_BASE'), 'saved-base');
  assert.equal(unload(), false);
  assert.equal(view.saves.length, 0);
  cleanup();
  assert.equal(unload(), false);
});

test('save_bar_is_hidden_until_changes_or_a_save_receipt_exist', async () => {
  const view = createConfigView([field('REGISTER_NAME', '注册主链路', {value: 'saved'})]);
  const shown = () => view.wrapper.find('.config-vue-savebar').exists() && view.wrapper.get('.config-vue-savebar').isVisible();
  assert.equal(shown(), false);
  await view.control('REGISTER_NAME').setValue('draft');
  assert.equal(shown(), true);
  view.owner.reset(); await flush();
  assert.equal(shown(), false);
  await view.control('REGISTER_NAME').setValue('saved-again');
  await view.save();
  assert.equal(view.owner.dirtyCount.value, 0);
  assert.equal(shown(), true);
  assert.match(view.wrapper.get('.config-vue-savebar').text(), /数据库保存成功.*Worker 应用状态待确认/);
});

test('custom_panels_and_subtabs_share_the_field_content_rail', async () => {
  const view = createConfigView([field('ROXY_API_BASE', 'RoxyBrowser'), field('PROXY_POOL_SOURCE', '代理与网络', {value: 'manual'})]);
  await view.open('RoxyBrowser');
  const main = view.wrapper.get('.config-vue-content');
  assert.equal(main.find('[data-config-tool="roxy"]').exists(), true);
  assert.equal(main.find('[data-config-setting="ROXY_API_BASE"]').exists(), true);
  assert.equal(main.get('[data-config-tool="roxy"]').element.closest('section'), main.get('[data-config-setting="ROXY_API_BASE"]').element.closest('section'));
  await view.open('代理与网络');
  assert.equal(main.find('[data-config-subsection]').exists(), true);
  assert.equal(main.find('table').exists(), true);
});

test('switching_config_groups_resets_the_page_viewport_without_losing_drafts', async t => {
  const view = createConfigView([field('REGISTER_NAME', '注册主链路'), field('C2A_API_BASE', 'C2A'), field('ROXY_API_BASE', 'RoxyBrowser')]);
  const scroll = t.mock.method(window, 'scrollTo', () => {});
  const main = view.wrapper.get('.config-vue-content').element;
  await view.control('REGISTER_NAME').setValue('draft');
  main.scrollTop = 500;
  await view.wrapper.get('[data-config-nav="服务集成"]').trigger('click');
  await flush();
  assert.equal(main.scrollTop, 0);
  assert.equal(scroll.mock.callCount(), 1);
  main.scrollTop = 400;
  await view.open('RoxyBrowser'); await flush();
  assert.equal(main.scrollTop, 0);
  assert.equal(view.owner.readField('REGISTER_NAME'), 'draft');
});

test('read_only_driver_values_keep_their_config_key_context', async () => {
  const options = [{value: 'protocol', label: '协议'}, {value: 'roxy', label: 'Roxy'}];
  const view = createConfigView([field('CODEX_OAUTH_DRIVER', '注册主链路', {value: 'roxy', options}), field('ACCOUNT_CODEX_DRIVER', '账号补全', {label:'Codex 授权方式', value: 'protocol', options})]);
  await view.open('账号补全');
  const row = view.wrapper.get('[data-config-setting="ACCOUNT_CODEX_DRIVER"]');
  assert.equal(row.get('code').text(), 'ACCOUNT_CODEX_DRIVER');
  assert.equal(row.find('[data-key]').exists(), false);
  assert.match(row.text(), /Roxy · 由注册主链路统一维护/);
});

test('config_domains_are_merged_into_seven_menus_without_mutating_schema_groups', async () => {
  const original = structuredClone(completeSchema);
  const view = createConfigView(completeSchema);
  assert.deepEqual(navigation.orderedMenus(view.owner.fields.value), ['注册与账号', '代理与网络', '邮箱与验证码', '浏览器', '服务集成', '提链', '系统与维护']);
  for (const [domain, menu] of [['注册主链路', '注册与账号'], ['账号补全', '注册与账号'], ['注册调试', '系统与维护'], ['RoxyBrowser', '浏览器'], ['接码平台', '邮箱与验证码']]) {
    await view.open(domain);
    assert.equal(view.wrapper.get('[data-config-nav][aria-current=page]').attributes('data-config-nav'), menu);
    assert.equal(view.wrapper.get('[data-config-section]').attributes('data-config-section'), domain);
  }
  assert.deepEqual(completeSchema, original);
});

test('lifecycle_pages_use_field_rows_without_an_execution_submenu', async () => {
  const view = createConfigView(completeSchema);
  for (const domain of ['注册主链路', '账号补全', '注册调试', '刷新 AT']) {
    await view.open(domain);
    assert.ok(view.wrapper.findAll('.config-vue-field').length > 0);
    assert.equal(view.wrapper.find('[data-config-subsection="执行方式"]').exists(), false);
    for (const row of view.wrapper.findAll('[data-config-setting]')) {
      assert.equal(row.findAll('.config-vue-field-copy').length, 1);
      assert.equal(row.findAll('.config-vue-field-control').length, 1);
    }
  }
  assert.equal(view.wrapper.find('[data-config-setting="OPENAI_PROTOCOL_VERSION"]').exists(), true);
});
