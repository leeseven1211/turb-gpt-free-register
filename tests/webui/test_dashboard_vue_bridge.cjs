const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function deferred() { let resolve, reject; const promise = new Promise((yes,no)=>{resolve=yes;reject=no;}); return {promise,resolve,reject}; }

test('dashboard facade uses the shared bridge, retries a failed lazy import and keeps hidden activation inert', async () => {
  const pending = deferred(), calls = [], children = [], imports = [], mounts = [];
  const root = {
    dataset: {moduleUrl:'/dashboard.js',styleUrl:'/dashboard/dashboard.css'},
    replaceChildren(){children.length=0;}, append(...nodes){children.push(...nodes);},
  };
  const elements = new Map([
    ['dashboard-page-root',root],
    ['tab-overview',{classList:{contains:()=>false}}],
  ]);
  const context = {
    window:null, document:{
      hidden:false,
      getElementById:id=>elements.get(id),
      createElement(){return {setAttribute(k,v){this[k]=v;},addEventListener(k,fn){this[k]=fn;}};},
      head:{append(node){elements.set(node.id,node);}},
      addEventListener(){},
    },
    showToast:message=>calls.push(['toast',message]),
    markViewReady(){}, activateTab(){}, openConfigGroup(){},
    applyFeatureGates(){calls.push(['capabilities']);},
    api:async()=>({}), apiCached:async()=>({}), $:()=>null, esc:String, attrEsc:String,
    CAPABILITIES:{},
    loadResourceModule:url=>{imports.push(url);return pending.promise;},
  };
  context.window=context;
  const shared=fs.readFileSync(path.join(__dirname,'../../webui/static/js/shared/page-bridge.js'),'utf8')
    .replace('import(node.dataset.moduleUrl)','loadResourceModule(node.dataset.moduleUrl)');
  vm.runInNewContext(shared,context);
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../webui/static/js/pages/dashboard/page.js'),'utf8'),context);
  await context.window.DashboardPage.setVisible(false);
  assert.equal(children.length,0);
  assert.equal(imports.length,0);
  const opening=context.window.DashboardPage.setVisible(true);
  pending.reject(new Error('chunk offline'));
  await opening;
  assert.equal(children.length,2);
  assert.equal(children[1].textContent,'重新加载');
  assert.equal(calls.filter(call=>call[0]==='toast').length,1);
  context.loadResourceModule=async url=>{
    imports.push(url);
    return {mountDashboard(node,deps){
      mounts.push({node,deps});
      return {setVisible:value=>calls.push(['visible',value]),load:async()=>calls.push(['load'])};
    }};
  };
  children[1].click();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(imports.length,2);
  assert.equal(mounts.length,1);
  assert.equal(mounts[0].deps.visible,false);
  assert.equal(calls.filter(call=>call[0]==='visible'&&call[1]).length,1);
  await context.DashboardPage.setVisible(true);
  assert.equal(imports.length,2);
  assert.equal(calls.filter(call=>call[0]==='visible'&&call[1]).length,1);
});

function createDashboardBridgeFixture() {
  const pending = deferred(), calls = [], imports = [], mounts = [], elements = new Map();
  const root = {dataset:{moduleUrl:'/dashboard/dashboard.js',styleUrl:'/dashboard/dashboard.css'},
    replaceChildren(){},append(){}};
  elements.set('dashboard-page-root',root);
  elements.set('tab-overview',{classList:{contains:()=>false}});
  elements.set('task-center-style',{href:'/existing-other-page.css'});
  const owner = {
    setVisible:value=>calls.push(['visible',value]),
    load:()=>calls.push(['load']),
    openCustomizer:()=>calls.push(['open']),
    closeCustomizer:()=>calls.push(['close']),
    resetLayout:()=>calls.push(['reset']),
  };
  const context = {
    document:{
      getElementById:id=>elements.get(id),
      createElement:()=>({setAttribute(){},addEventListener(){}}),
      head:{append:node=>elements.set(node.id,node)},
    },
    CAPABILITIES:{},showToast:value=>calls.push(['notice',value]),
    markViewReady:value=>calls.push(['ready',value]),
    activateTab:value=>calls.push(['navigate',value]),
    openConfigGroup:value=>calls.push(['config',value]),
    loadResourceModule:url=>{imports.push(url);return pending.promise;},
  };
  context.window=context;
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../webui/static/js/shared/page-bridge.js'),'utf8')
    .replace('import(node.dataset.moduleUrl)','loadResourceModule(node.dataset.moduleUrl)'),context);
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../webui/static/js/pages/dashboard/page.js'),'utf8'),context);
  return {context,owner,calls,imports,mounts,elements,
    finish(){pending.resolve({mountDashboard(node,deps){mounts.push({node,deps});return owner;}});}};
}

test('dashboard import is shared and navigation cancels a stale customizer request', async () => {
  const view=createDashboardBridgeFixture(),bridge=view.context.DashboardPage;
  await view.context.loadDashboard();
  assert.equal(view.imports.length,0,'hidden compatibility reads must not load the page');
  const first=bridge.setVisible(true),opening=view.context.openOverviewCustomizer();
  bridge.closeDialogs();
  await bridge.setVisible(false);
  const returning=bridge.setVisible(true);
  view.finish();await Promise.all([first,opening,returning]);
  assert.equal(view.imports.length,1);
  assert.equal(view.mounts.length,1);
  assert.deepEqual(view.calls,[['visible',true]]);
  await view.context.openOverviewCustomizer();
  await view.context.loadDashboard();
  await view.context.resetOverviewLayout();
  view.context.closeOverviewCustomizer();
  await bridge.setVisible(false);
  assert.deepEqual(view.calls,[['visible',true],['open'],['load'],['reset'],['close'],['visible',false]]);
});

test('dashboard assets and shell callbacks stay scoped to the overview page', async () => {
  const view=createDashboardBridgeFixture(),opening=view.context.DashboardPage.setVisible(true);
  view.finish();await opening;
  assert.deepEqual(view.imports,['/dashboard/dashboard.js']);
  assert.equal(view.elements.get('dashboard-page-root-style').href,'/dashboard/dashboard.css');
  assert.equal(view.elements.get('task-center-style').href,'/existing-other-page.css');
  const deps=view.mounts[0].deps,capabilities={features:{sample:{enabled:true}}};
  deps.onCapabilities(capabilities);
  assert.equal(view.context.CAPABILITIES,capabilities);
  deps.onReady();deps.onNavigate('overview');deps.onConfig('代理与网络');
  assert.deepEqual(view.calls.slice(1),[['ready','overview'],['navigate','overview'],['config','代理与网络']]);
});
