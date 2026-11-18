const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(process.env.ACCOUNTS_DETAIL_SOURCE || path.resolve(__dirname, '../../webui/static/js/pages/accounts/page.js'), 'utf8');
const tooltipSource = source.slice(source.indexOf('let _accountsTooltipNode'), source.indexOf('function bindAccountsHoverTooltips'));
const detailSource = source.slice(source.indexOf('function _copyAccountConsumerSnapshot'), source.indexOf('function closeAccountsV2MoreMenus'));
// Drawer lifecycle/ABA/focus cases now execute the real Vue owner in
// frontend/src/features/accounts/{useAccountDetail,AccountDetail}.test.ts.
function deferred() { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return {promise, resolve, reject}; }
async function settle() { for (let n = 0; n < 12; n++) await Promise.resolve(); }
function node() {
  const attributes = new Map(), classes = new Set();
  return {dataset: {}, style: {}, hidden: false, isConnected: true, innerHTML: '', textContent: '', focusCount: 0,
    classList: {add: x => classes.add(x), remove: x => classes.delete(x), contains: x => classes.has(x), toggle(x, on) { if (on) classes.add(x); else classes.delete(x); }},
    setAttribute(k, v) { attributes.set(k, v); }, getAttribute(k) { return attributes.get(k) ?? null; }, removeAttribute(k) { attributes.delete(k); if (k === 'data-account-id') delete this.dataset.accountId; },
    focus() { this.focusCount++; }, addEventListener() {}, matches() { return false; }, contains() { return false; }, getClientRects() { return [1]; }, getBoundingClientRect() { return {left: 10, top: 10, bottom: 30, width: 150, height: 50}; }, closest() { return null; },
  };
}
function lease(generation) {
  const wait = deferred();
  return {openGeneration: generation, releases: 0, calls: [], wait, loadPlanDetails(id, gen) { this.calls.push([id, gen]); return wait.promise; }, release() { this.releases++; }};
}
function fixture(rows = []) {
  const nodes = Object.fromEntries(['accountDetailDrawer', 'accountDetailBody', 'accountDetailTitle', 'accountDetailSubtitle', 'accountDetailBackdrop', 'btnCloseAccountDetail'].map(id => [id, node()]));
  const requests = [], toasts = [], legacyPlans = [], created = [];
  const context = {console, JSON, Promise, Number, String, Object, Array, Boolean, Math, Error, setTimeout, clearTimeout,
    ACCOUNTS: rows, window: {innerWidth: 1000, innerHeight: 800},
    document: {activeElement: null, body: {appendChild() {}}, createElement() { const el = node(); el.querySelectorAll = () => [{dataset: {accountsTooltip: el.innerHTML}}]; created.push(el); return el; }},
    $: selector => nodes[selector.slice(1)], showToast: message => toasts.push(message), facetLabel: (_, v) => v || '', updateModalScrollLock() {},
    _accountDetailMarkup: row => JSON.stringify(row), _promotionCell: row => row.detail || row.plan_summary?.label || 'summary',
    loadAccountPlanDetails: row => { legacyPlans.push(row); return Promise.resolve(row); },
    api: url => { const wait = deferred(); requests.push({url, ...wait}); return wait.promise; },
  };
  vm.createContext(context); vm.runInContext(tooltipSource + '\n' + detailSource, context);
  function target(id) {
    const el = node(), cell = {querySelectorAll: () => [el]}, tr = {querySelector: () => ({dataset: {accountId: String(id)}})};
    el.dataset.accountsTooltip = 'summary';
    el.closest = selector => selector === 'tr' ? tr : selector === '.col-trial' || selector.includes('.col-trial') ? cell : null;
    return el;
  }
  return {context, nodes, requests, toasts, legacyPlans, created, target, body: () => JSON.parse(nodes.accountDetailBody.innerHTML)};
}

test('tooltip reads through its owner lease and never mutates the source snapshot', async () => {
  const f = fixture(), l = lease(3), row = Object.freeze({id: 7, detail: 'summary', plan_details_revision: 'v1'}), target = f.target(7);
  f.context.window.AccountsPage = {isReady: () => true, getRowSnapshot: () => row, openPlanDetailsConsumer: () => l};
  f.context._showAccountsTooltip(target); assert.deepEqual(l.calls, [['7', 3]]);
  l.wait.resolve({accountId: '7', revision: 'v1', item: {detail: 'full-promotion'}}); await settle();
  assert.equal(f.created.find(x => x.id === 'accountsHoverTooltip').textContent, 'full-promotion');
  assert.equal(row.detail, 'summary'); assert.equal(target.dataset.accountsTooltip, 'summary');
  f.context.closeAccountsVueTooltip(); assert.equal(l.releases, 1);
});

test('hide and reopen same tooltip target rejects stale completion and preserves aria description', async () => {
  const f = fixture(), first = lease(1), second = lease(2), target = f.target(7); let active = first;
  target.setAttribute('aria-describedby', 'existing');
  f.context.window.AccountsPage = {isReady: () => true, getRowSnapshot: () => ({id: 7}), openPlanDetailsConsumer: () => active};
  f.context._showAccountsTooltip(target); f.context._showAccountsTooltip(target);
  assert.equal(first.calls.length, 1);
  f.context._hideAccountsTooltip(); assert.equal(first.releases, 1); assert.equal(target.getAttribute('aria-describedby'), 'existing');
  active = second; f.context._showAccountsTooltip(target);
  first.wait.resolve({accountId: '7', item: {detail: 'old'}}); await settle();
  assert.equal(f.created.find(x => x.id === 'accountsHoverTooltip').textContent, 'summary');
  second.wait.resolve({accountId: '7', item: {detail: 'new'}}); await settle();
  assert.equal(f.created.find(x => x.id === 'accountsHoverTooltip').textContent, 'new');
  f.context._hideAccountsTooltip(); assert.equal(second.releases, 1); assert.equal(target.getAttribute('aria-describedby'), 'existing');
});

test('disconnected tooltip cannot repaint and closeConsumers restores focus from a connected tooltip', async () => {
  const f = fixture(), first = lease(1), second = lease(2), target = f.target(7); let active = first;
  f.context.window.AccountsPage = {isReady: () => true, getRowSnapshot: () => ({id: 7}), openPlanDetailsConsumer: () => active};
  f.context._showAccountsTooltip(target); assert.equal(first.calls.length, 1);
  target.isConnected = false; first.wait.resolve({accountId: '7', item: {detail: 'detached'}}); await settle();
  const tip = f.created.find(x => x.id === 'accountsHoverTooltip'); assert.equal(tip.textContent, 'summary');
  f.context.closeAccountsVueTooltip(); assert.equal(first.releases, 1); assert.equal(target.focusCount, 0);
  target.isConnected = true; active = second; f.context._showAccountsTooltip(target);
  tip.contains = () => true; f.context.closeAccountsVueTooltip();
  assert.equal(second.releases, 1); assert.equal(target.focusCount, 1);
});

test('a completed tooltip releases its consumer when a list render replaces its DOM target', async () => {
  const f = fixture(), l = lease(1), target = f.target(7);
  f.context.window.AccountsPage = {isReady: () => true, getRowSnapshot: () => ({id: 7}), openPlanDetailsConsumer: () => l};
  f.context._showAccountsTooltip(target); l.wait.resolve({accountId: '7', item: {detail: 'expanded'}}); await settle();
  const tip = f.created.find(x => x.id === 'accountsHoverTooltip');
  assert.equal(l.releases, 0); assert.equal(tip.hidden, false);
  target.isConnected = false;
  assert.equal(typeof f.context.syncAccountsVueTooltip, 'function');
  f.context.syncAccountsVueTooltip();
  assert.equal(l.releases, 1); assert.equal(tip.hidden, true);
});

test('a list render retains a tooltip whose DOM target remains connected', () => {
  const f = fixture(), l = lease(1), target = f.target(7);
  f.context.window.AccountsPage = {isReady: () => true, getRowSnapshot: () => ({id: 7}), openPlanDetailsConsumer: () => l};
  f.context._showAccountsTooltip(target);
  assert.equal(typeof f.context.syncAccountsVueTooltip, 'function');
  f.context.syncAccountsVueTooltip();
  assert.equal(l.releases, 0); assert.equal(f.created.find(x => x.id === 'accountsHoverTooltip').hidden, false);
});


test('legacy drawer entry delegates identity and trigger to Vue without reading legacy rows', () => {
  const f = fixture([{id: 7, email: 'must-not-be-read'}]), calls = [], trigger = node();
  f.context.window.AccountsPage = {isReady: () => true, openDetail: (...args) => calls.push(args), closeDetail: value => calls.push(value)};
  f.context.document.activeElement = trigger;
  f.context.openAccountDetail(7);
  f.context.closeAccountDetail(false);
  assert.equal(calls[0][0], '7'); assert.equal(calls[0][1], trigger); assert.equal(calls[1], false);
  assert.equal(f.requests.length, 0); assert.equal(f.legacyPlans.length, 0);
});

test('unmounted drawer entry releases passed lease and reports loading without a second owner', () => {
  const f = fixture(), l = lease(1);
  f.context.openAccountDetail(7, {lease: l});
  assert.equal(l.releases, 1); assert.equal(f.toasts.length, 1);
  assert.equal(f.requests.length, 0); assert.equal(f.legacyPlans.length, 0);
});


test('unmounted tooltip keeps its summary without reading legacy rows or making detail requests', async () => {
  const f = fixture([{id: 7, _planDetailsPending: true, detail: 'legacy'}]), target = f.target(7);
  f.context._showAccountsTooltip(target); await settle();
  assert.equal(f.created.find(x => x.id === 'accountsHoverTooltip').textContent, 'summary');
  assert.equal(f.requests.length, 0); assert.equal(f.legacyPlans.length, 0);
});
