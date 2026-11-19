const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {createRequire}=require('node:module');
const {JSDOM}=createRequire(path.join(__dirname,'../../frontend/package.json'))('jsdom');
const source=fs.readFileSync(path.join(__dirname,'../../webui/static/js/pages/bulk/page.js'),'utf8');
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return{promise,resolve,reject};}
function setup(t){
 const loading=deferred(),calls=[],notices=[];
 const dom=new JSDOM('<section id="tab-bulk"><div id="bulk-page-root" data-module-url="synthetic" data-style-url="synthetic.css"></div></section><link id="task-center-style">');
 t.after(()=>dom.window.close());
 const document=dom.window.document,classes=document.getElementById('tab-bulk').classList;
 let mounts=0;
 let nav={tab:'bulk',view:'list'};
 const api={navigationState:()=>({...nav}),restoreNavigation:value=>{nav={...value};},setVisible:value=>calls.push(['visible',value]),activate:async()=>calls.push(['activate']),showReport:async()=>calls.push(['report']),
  fromAccounts:async(selected,operationKey,snapshot)=>{calls.push(['accounts',selected,operationKey,JSON.parse(JSON.stringify(snapshot))]);nav={tab:'bulk',view:'create'};},
  request:async()=>({}),intent:async()=>({}),restoreSelectionRequest(){}};
 Object.defineProperty(document,'hidden',{value:false,configurable:true});
 const context={window:null,document,Promise,showToast:value=>notices.push(value),formatDateTime:String,facetLabel:(_,value)=>value,openAccountTaskLog(){},AccountQuery:{},recordNavigationHistory(){},loadModule:()=>loading.promise,
  activateTab(){classes.remove('hidden');}};
 context.window=context;vm.createContext(context);vm.runInContext(source.replace('import(root.dataset.moduleUrl)','loadModule(root.dataset.moduleUrl)'),context);
 return{bridge:context.BulkTasks,api,calls,notices,classes,get mounts(){return mounts;},resolve(){loading.resolve({mountBulk:()=>{mounts++;return api;}});}};
}
test('leaving bulk while its module loads cancels the pending account navigation',async t=>{
 const h=setup(t),opening=h.bridge.fromAccounts(true,'plan_check',{ids:['9007199254740993'],query:{archived:'only'}});
 h.classes.add('hidden');h.bridge.setVisible(false);h.resolve();await opening;
 assert.equal(h.calls.filter(call=>call[0]==='accounts').length,0);
});
test('simultaneous module callers hand off one immutable account snapshot',async t=>{
 const h=setup(t),snapshot={ids:['9007199254740993'],query:{q:'first'}};
 const opening=h.bridge.fromAccounts(true,'plan_check',snapshot),activation=h.bridge.activate();snapshot.ids.push('9');snapshot.query.q='changed';h.resolve();await Promise.all([opening,activation]);
 assert.deepEqual(h.calls.filter(call=>call[0]==='accounts'),[['accounts',true,'plan_check',{ids:['9007199254740993'],query:{q:'first'}}]]);
 assert.equal(h.mounts,1);assert.deepEqual(h.notices,[]);
});
test('failed account handoff remains recoverable on retry and does not remount',async t=>{
 const h=setup(t);let attempt=0;
 const original=h.api.fromAccounts;
 h.api.fromAccounts=async(...args)=>{if(++attempt===1)throw new Error('handoff failed');return original(...args);};
 const opening=h.bridge.fromAccounts(true,'plan_check',{ids:['7'],query:{}});h.resolve();await opening;
 assert.equal(h.notices.length,1);await h.bridge.activate();
 assert.equal(h.calls.filter(call=>call[0]==='accounts').length,1);assert.equal(attempt,2);
 assert.equal(h.mounts,1);await h.bridge.activate();
 assert.equal(h.calls.filter(call=>call[0]==='accounts').length,1);assert.equal(h.mounts,1);
});
