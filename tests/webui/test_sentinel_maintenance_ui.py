"""Sentinel maintenance controls exercise the real configuration-page JavaScript."""

from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]


class SentinelMaintenanceUiTests(unittest.TestCase):
    def run_js(self, assertions):
        harness = r'''
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(process.argv[1], 'utf8');
const calls = [], timers = new Map(), observers = [], handlers = {};
let nextTimer = 0;
const visibility = {tabHidden: false, attached: true};
const panel = {innerHTML: ''};
const tab = {
  hidden: false,
  classList: {contains: name => name === 'hidden' && visibility.tabHidden},
  addEventListener(name, fn) { (handlers[name] ||= []).push(fn); },
};
const document = {
  hidden: false,
  getElementById: id => id === 'tab-config' ? tab : null,
  querySelector: selector => selector.includes('[data-sentinel-maintenance]') && visibility.attached ? panel : null,
  querySelectorAll: () => [],
  addEventListener(name, fn) { (handlers[`document:${name}`] ||= []).push(fn); },
};
const status = (overrides = {}) => ({
  ok: true, running: false, last_checked_at: null, last_status: 'never', error_code: null,
  builtin: {version: '20261101', sha256: 'a'.repeat(64)}, candidate: null,
  comparison: 'not_checked', ...overrides,
});
const candidate = {
  version: '20261103', sha256: 'b'.repeat(64), fetched_at: 1793670000,
  generic_status: 'static_markers_present', proto2_status: 'needs_adaptation', runtime_verified: false,
};
let respond = async () => status();
const context = vm.createContext({
  assert, document, panel, visibility, calls, timers, handlers, status, candidate,
  CONFIG: [{key: 'EXAMPLE', value: 'saved'}], CSS: {escape: String},
  esc: value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;', "'":'&#39;'}[char])),
  $: selector => selector === '#tab-config' ? tab : null,
  window: {addEventListener() {}},
  localStorage: {getItem() { return null; }, setItem() {}},
  setTimeout(fn) { const id = ++nextTimer; timers.set(id, fn); return id; },
  clearTimeout(id) { timers.delete(id); },
  MutationObserver: class {
    constructor(callback) { this.callback = callback; observers.push(this); }
    observe() {}
  },
  api: async (url, options = {}) => {
    const call = {url, method: options.method || 'GET', options};
    calls.push(call);
    return respond(call);
  },
  setResponse(fn) { respond = fn; },
  notifyVisibility() { observers.forEach(observer => observer.callback([])); },
  async tick() { for (let i = 0; i < 8; i++) await Promise.resolve(); },
  async runTimer() {
    assert.equal(timers.size, 1);
    const [id, fn] = timers.entries().next().value;
    timers.delete(id);
    await fn();
    for (let i = 0; i < 8; i++) await Promise.resolve();
  },
  clickSentinel(action = 'check') {
    const target = {closest: selector => selector === '[data-sentinel-maintenance-action]' ? {dataset: {sentinelMaintenanceAction: action}} : null};
    const event = {target, preventDefault() {}};
    return Promise.all((handlers.click || []).map(fn => fn(event)));
  },
});
vm.runInContext(source, context);
Promise.resolve(vm.runInContext(process.argv[2], context)).catch(error => {
  console.error(error);
  process.exitCode = 1;
});
'''
        completed = subprocess.run(
            ["node", "--input-type=commonjs", "-e", harness,
             str(ROOT / "webui/static/js/pages/config/page.js"), assertions],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=15,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_card_lives_in_general_configuration_and_initial_load_never_checks(self):
        self.run_js(r'''
(async () => {
  renderConfigSectionHead = () => '';
  configGroupSlug = String;
  const general = renderConfigDomainSectionV2('通用配置', []);
  assert.match(general, /data-sentinel-maintenance/);
  assert.match(general, /Sentinel 检查/);
  assert.match(general, /不自动切换现用版本/);
  assert.doesNotMatch(renderConfigDomainSectionV2('其他', []), /data-sentinel-maintenance/);
  visibility.tabHidden = true;
  bindSentinelMaintenanceV2();
  await tick();
  assert.equal(calls.length, 0);
  visibility.tabHidden = false;
  notifyVisibility();
  await tick();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, '/api/maintenance/sentinel');
  assert.equal(calls[0].method, 'GET');
  assert.match(panel.innerHTML, /当前内置版本/);
  assert.match(panel.innerHTML, /20261101/);
  assert.match(panel.innerHTML, /尚未检查/);
  assert.match(panel.innerHTML, /role="status"[^>]*aria-live="polite"/);
  assert.equal(timers.size, 0);
})();
''')

    def test_explicit_check_is_single_flight_and_updates_only_the_card(self):
        self.run_js(r'''
(async () => {
  bindSentinelMaintenanceV2();
  await tick();
  CONFIG_PENDING_UPDATES.EXAMPLE = 'unsaved';
  let finish;
  setResponse(call => call.method === 'POST'
    ? new Promise(resolve => { finish = resolve; })
    : status({candidate, comparison: 'version_changed', last_status: 'refreshed', last_checked_at: 1793670000}));
  const first = clickSentinel();
  await tick();
  await clickSentinel();
  assert.equal(calls.filter(call => call.method === 'POST').length, 1);
  assert.equal(calls[1].url, '/api/maintenance/sentinel/check');
  assert.equal(calls[1].options.body, '{}');
  assert.match(panel.innerHTML, /disabled[^>]*>检查中…/);
  finish(status({started: true, running: true}));
  await first;
  await tick();
  assert.equal(timers.size, 1);
  await runTimer();
  assert.match(panel.innerHTML, /发现新版本/);
  assert.match(panel.innerHTML, /20261103/);
  assert.match(panel.innerHTML, /generic 静态检查：通过（未运行验证）/);
  assert.match(panel.innerHTML, /Proto2 静态检查：需要适配/);
  assert.equal(CONFIG_PENDING_UPDATES.EXAMPLE, 'unsaved');
  assert.equal(timers.size, 0);
})();
''')

    def test_navigation_cancels_polling_and_stale_get_does_not_restart_it(self):
        self.run_js(r'''
(async () => {
  let finish;
  setResponse(() => new Promise(resolve => { finish = resolve; }));
  bindSentinelMaintenanceV2();
  await tick();
  visibility.attached = false;
  syncSentinelMaintenanceV2();
  finish(status({running: true}));
  await tick();
  assert.equal(timers.size, 0);
  setResponse(() => status({running: true}));
  visibility.attached = true;
  syncSentinelMaintenanceV2();
  await tick();
  assert.equal(timers.size, 1);
  visibility.tabHidden = true;
  notifyVisibility();
  assert.equal(timers.size, 0);
  assert.equal(calls.length, 2);
})();
''')

    def test_failure_retains_candidate_and_retries_without_showing_debug_details(self):
        self.run_js(r'''
(async () => {
  setResponse(() => status({candidate, comparison: 'content_changed', last_status: 'refreshed', last_checked_at: 1793670000}));
  bindSentinelMaintenanceV2();
  await tick();
  assert.match(panel.innerHTML, /同版本内容变化/);
  setResponse(async () => { throw new Error('/private/secret.js raw source credentials'); });
  await clickSentinel();
  await tick();
  assert.match(panel.innerHTML, /20261103/);
  assert.match(panel.innerHTML, /重试/);
  assert.doesNotMatch(panel.innerHTML, /private|secret\.js|raw source|credentials/);
  assert.equal(timers.size, 0);
  setResponse(() => status({candidate, comparison: 'same', last_status: 'refreshed'}));
  await clickSentinel();
  await tick();
  assert.match(panel.innerHTML, /同当前一致/);
  assert.doesNotMatch(panel.innerHTML, /data-sentinel-maintenance-action="retry"/);
  assert.equal(calls.filter(call => call.method === 'POST').length, 2);
})();
''')

    def test_status_read_failure_has_a_get_retry_and_escapes_versions(self):
        self.run_js(r'''
(async () => {
  setResponse(async () => { throw new Error('GET /internal/path'); });
  bindSentinelMaintenanceV2();
  await tick();
  assert.match(panel.innerHTML, /重试/);
  assert.doesNotMatch(panel.innerHTML, /internal/);
  setResponse(() => status({builtin: {version: '<script>alert(1)</script>', sha256: 'a'.repeat(64)}}));
  await clickSentinel('retry');
  await tick();
  assert.equal(calls.length, 2);
  assert.equal(calls[1].method, 'GET');
  assert.match(panel.innerHTML, /&lt;script&gt;/);
  assert.doesNotMatch(panel.innerHTML, /<script>/);
})();
''')

    def test_corrupt_status_retains_last_candidate_and_offers_a_new_check(self):
        self.run_js(r'''
(async () => {
  setResponse(() => status({candidate, comparison: 'version_changed', last_status: 'refreshed'}));
  bindSentinelMaintenanceV2();
  await tick();
  setResponse(() => status({last_status: 'corrupt', comparison: 'unknown'}));
  await clickSentinel();
  await tick();
  assert.match(panel.innerHTML, /20261103/);
  assert.match(panel.innerHTML, /不可用/);
  assert.match(panel.innerHTML, /data-sentinel-maintenance-action="retry"/);
  assert.doesNotMatch(panel.innerHTML, /sha256|static_markers_present|needs_adaptation/);
})();
''')

    def test_hidden_document_pauses_polling_and_resumes_with_only_a_status_read(self):
        self.run_js(r'''
(async () => {
  setResponse(() => status({running: true}));
  bindSentinelMaintenanceV2();
  await tick();
  assert.equal(timers.size, 1);
  document.hidden = true;
  for (const fn of handlers['document:visibilitychange']) fn();
  assert.equal(timers.size, 0);
  document.hidden = false;
  for (const fn of handlers['document:visibilitychange']) fn();
  await tick();
  assert.equal(calls.length, 2);
  assert.ok(calls.every(call => call.method === 'GET'));
})();
''')


if __name__ == "__main__":
    unittest.main()
