// Exercise the actual Vue dialog/receipt from legacy compatibility tests.
const {vueHarness: vue} = require('./actions_fixture.cjs');
const {flushPromises} = require('../../frontend/node_modules/@vue/test-utils');

function mountC2aFixture(deps, {preserve=false}={}) {
  if(!preserve)vue.cleanup();
  const document = vue.document;
  if(!preserve)document.body.innerHTML = '<button id="btnReimportSelectedC2aV2">重新导入 C2A</button><details id="accountsMoreActionsV2"><summary>更多</summary></details><div id="accountC2aConfirmHost"></div><div id="accountC2aReceiptHost"></div>';
  else for(const id of ['accountC2aConfirmHost','accountC2aReceiptHost']){if(!document.getElementById(id)){const host=document.createElement('div');host.id=id;document.body.append(host);}}
  const browser = document.defaultView, prior = new Map();
  for (const name of ['Document', 'ShadowRoot', 'HTMLButtonElement']) {
    prior.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, {configurable: true, writable: true, value: browser[name]});
  }
  browser.HTMLDialogElement.prototype.showModal = function () {this.open = true;};
  browser.HTMLDialogElement.prototype.close = function (value = '') {this.open = false; this.returnValue = value; this.dispatchEvent(new browser.Event('close'));};
  const wrapper = vue.mount(vue.load('src/features/accounts/C2aReimport.vue').default, {props: {deps}});
  const get = id => document.getElementById(id);
  return {
    wrapper, document, get, flush: flushPromises,
    bind(owner) {
      owner.openC2a = (context,trigger) => wrapper.vm.open(context, trigger||get('btnReimportSelectedC2aV2'));
      owner.closeC2a = (...args) => wrapper.vm.close(...args);
      owner.submitC2a = () => wrapper.vm.submit();
    },
    async click(id) {get(id).click(); await flushPromises();},
    async frame() {await new Promise(resolve => browser.requestAnimationFrame(resolve));},
    close() {if(preserve)wrapper.unmount();else vue.cleanup(); for (const [name, descriptor] of prior) {if (descriptor) Object.defineProperty(globalThis, name, descriptor); else delete globalThis[name];}},
  };
}
module.exports = {mountC2aFixture};
