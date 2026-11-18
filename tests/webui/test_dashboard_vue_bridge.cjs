const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function deferred() { let resolve, reject; const promise = new Promise((yes,no)=>{resolve=yes;reject=no;}); return {promise,resolve,reject}; }

test('dashboard facade uses the shared bridge, retries a failed lazy import and keeps hidden activation inert', async () => {
  const pending = deferred(), calls = [], children = [], imports = [], mounts = [];
  const root = {
    dataset: {moduleUrl:'/dashboard.js',styleUrl:'/task-center.css'},
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
    AccountsPage:{setCapabilities(){}},
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
