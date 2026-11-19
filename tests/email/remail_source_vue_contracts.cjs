const assert = require('node:assert/strict');
const {createVueHarness} = require('../frontend_vue_loader.cjs');
const {installNetworkFence} = require('../config/vue_migration_contracts.cjs');

async function run() {
  const closeNetworkFence = installNetworkFence(), harness = createVueHarness();
  const requests = [];
  let inventoryEnabled = true, registrationEnabled = true;
  const unavailable = '本地库存不足';
  const settle = async () => {
    for (let index = 0; index < 5; index++) await new Promise(resolve => setImmediate(resolve));
    await harness.nextTick();
  };
  try {
    Object.defineProperty(document, 'hidden', {configurable: true, value: false});
    HTMLDialogElement.prototype.showModal = function () {this.setAttribute('open', '');};
    HTMLDialogElement.prototype.close = function () {this.removeAttribute('open');};
    window.scrollTo = () => {};
    // Exercise the real typed API/client/JSON decoding. Only its fetch boundary
    // supplies synthetic GET responses; the network fence rejects any escape.
    globalThis.fetch = async (url, options = {}) => {
      const route = String(url);
      assert.equal(options.method || 'GET', 'GET', 'source-form contracts must not submit a business action');
      assert.equal(options.credentials, 'same-origin');
      requests.push(route);
      let body;
      if (route === '/api/email-sources') {
        body = {manual_mode: false, registration_drivers: [], sources: [
          {value: 'outlook', label: 'Outlook', enabled: inventoryEnabled, kind: 'local_pool', reason: inventoryEnabled ? '' : unavailable},
          {value: 'email_butler', label: 'Email Butler', enabled: false, kind: 'local_pool', reason: unavailable},
        ]};
      } else if (route === '/api/capabilities') {
        body = {features: {register: {enabled: registrationEnabled, reason: registrationEnabled ? '' : unavailable}},
          email_sources: {
            outlook: {enabled: registrationEnabled, reason: registrationEnabled ? '' : unavailable},
            email_butler: {enabled: false, reason: unavailable},
          }};
      } else if (route.startsWith('/api/jobs?')) body = {items: [], total: 0, progress_batches: []};
      else if (route === '/api/summary') body = {accounts: 0, email_supply: {status: 'known', total: 1, available: 1}};
      else throw new Error(`unexpected source-form request: ${route}`);
      return new Response(JSON.stringify(body), {headers: {'Content-Type': 'application/json'}});
    };

    const Registration = harness.load('src/features/registration/RegistrationPage.vue').default;
    const registration = harness.mount(Registration, {props: {deps: {visible: false}}});
    registration.vm.setVisible(true);
    await settle();
    const source = registration.get('.registration-launcher select');
    const outlook = source.get('option[value="outlook"]');
    assert.equal(source.element.disabled, false);
    assert.equal(outlook.text(), 'Outlook');
    assert.equal(outlook.element.disabled, false);
    await source.setValue('outlook');
    assert.equal(source.element.value, 'outlook');
    assert.deepEqual(requests.filter(route => route === '/api/email-sources'), ['/api/email-sources']);
    assert.deepEqual(requests.filter(route => route === '/api/capabilities'), ['/api/capabilities']);
    assert.equal(source.find('option[value="email_butler"]').exists(), false, 'unavailable inventory is not a launch source');

    // Even a previously enabled source response cannot override an explicit
    // unavailable inventory capability. Refresh the mounted owner, not old DOM.
    registrationEnabled = false;
    await registration.vm.ensureMeta(true);
    await settle();
    assert.equal(inventoryEnabled, true, 'source response remains enabled to isolate the capability guard');
    assert.equal(source.find('option[value="outlook"]').exists(), false);
    assert.equal(source.element.value, '');
    const start = registration.get('.registration-launcher button');
    assert.equal(start.element.disabled, true);
    assert.match(start.attributes('title'), new RegExp(unavailable));
    assert.match(registration.get('.registration-launch').text(), new RegExp(unavailable));
    assert.equal(requests.filter(route => route === '/api/email-sources').length, 2);
    assert.equal(requests.filter(route => route === '/api/capabilities').length, 2);
    registration.vm.setVisible(false);

    const host = document.createElement('div');
    host.id = 'accountEmailChangeHost';
    document.body.appendChild(host);
    const EmailChange = harness.load('src/features/accounts/EmailChange.vue').default;
    const {request} = harness.load('src/api/client.ts');
    const change = harness.mount(EmailChange, {props: {deps: {
      request, notify() {}, refreshAccounts() {}, openTasks() {}, recordReceipt() {}, syncModalScrollLock() {},
    }}});
    const context = {accountIds: ['7'], expectedEmails: {'7': 'account@example.test'}, querySnapshot: {}, archived: false,
      rowHints: [{id: 7, email: 'account@example.test', email_source: 'outlook'}]};
    const before = requests.length;
    assert.equal(change.vm.openSingle('7', context), true);
    await settle();
    assert.deepEqual(requests.slice(before), ['/api/email-sources']);
    const changeSource = host.querySelector('#emailChangeSource');
    assert.ok(changeSource);
    assert.equal(changeSource.value, 'outlook');
    assert.equal(changeSource.disabled, false);
    const changeOption = changeSource.querySelector('option[value="outlook"]');
    assert.equal(changeOption.textContent, 'Outlook');
    assert.equal(changeOption.disabled, false);

    inventoryEnabled = false;
    const beforeDisabled = requests.length;
    assert.equal(change.vm.openSingle('7', context), true);
    await settle();
    assert.deepEqual(requests.slice(beforeDisabled), ['/api/email-sources']);
    assert.equal(changeSource.value, '');
    assert.equal(changeSource.disabled, true);
    const disabledOption = changeSource.querySelector('option[value="outlook"]');
    assert.equal(disabledOption.disabled, true);
    assert.match(disabledOption.textContent, /Outlook.*不可用/);
    assert.equal(disabledOption.getAttribute('data-reason'), unavailable);
    assert.match(host.querySelector('#emailChangeSourceError').textContent, /没有已配置且可用的新邮箱来源/);
    console.log('ok registration and email-change source contracts');
  } finally {
    harness.close();
    closeNetworkFence();
  }
}

if (require.main === module) run().catch(error => {console.error(error); process.exitCode = 1;});
module.exports = {run};
