// Real Vue toolbar and usage composable; only browser capabilities and action boundary are doubled.
const {vueHarness: vue} = require('./actions_fixture.cjs');
const {flushPromises} = require('../../frontend/node_modules/@vue/test-utils');
const {ACCOUNT_TOOLBAR_BUTTONS} = vue.load('src/features/accounts/accountToolbar.ts');
const {ACCOUNT_ACTION_USAGE_KEY} = vue.load('src/features/accounts/useAccountQuickActions.ts');
const {default: AccountsToolbar} = vue.load('src/features/accounts/AccountsToolbar.vue');
function mountToolbarFixture({saved=null,storageBlocked=false,state={selectedCount:2,archived:false},capabilities={},getContext,invoke,notify}={}) {
  vue.cleanup();
  const document=vue.document,frames=new Map(),storage={value:saved,writes:[]};let frameId=0,storageListener;
  const calls=[];
  const runtime={
    storage:{getItem(){if(storageBlocked)throw new Error('存储不可用');return storage.value;},setItem(key,value){storage.writes.push({key,value});if(storageBlocked)throw new Error('存储不可用');storage.value=value;}},
    requestFrame(callback){frames.set(++frameId,callback);return frameId;},cancelFrame(handle){frames.delete(handle);},
    addStorageListener(listener){storageListener=listener;return()=>{storageListener=undefined;};},
  };
  const context=Object.freeze({accountIds:Object.freeze(['7','8']),expectedEmails:Object.freeze({'7':'seven@test','8':'eight@test'}),querySnapshot:Object.freeze({schema_version:1,entity:'account',archived:'0',filters:{}}),archived:'0',rowHints:Object.freeze([])});
  const wrapper=vue.mount(AccountsToolbar,{props:{state,capabilities,getContext:getContext||(()=>context),runtime,
    invoke:(...args)=>{calls.push(args);return invoke?.(...args);},notify:notify||(()=>{})}});
  const get=id=>document.getElementById(id);
  return{wrapper,document,storage,calls,context,get,ready:flushPromises(),
    ids:()=>Array.from(get('accountsQuickActionsV2').querySelectorAll('button')).map(button=>button.id),
    async flush(){const pending=[...frames.values()];frames.clear();pending.forEach(callback=>callback());await flushPromises();},
    async refresh(){wrapper.vm.refreshQuickActions();await flushPromises();},
    async click(id){get(id).click();await flushPromises();},
    external(key=ACCOUNT_ACTION_USAGE_KEY){storageListener?.({key});},
    setState(value){return wrapper.setProps({state:value});},setCapabilities(value){return wrapper.setProps({capabilities:value});},
    close(){wrapper.unmount();},
  };
}
module.exports={mountToolbarFixture,ACCOUNT_TOOLBAR_BUTTONS,ACCOUNT_ACTION_USAGE_KEY};
