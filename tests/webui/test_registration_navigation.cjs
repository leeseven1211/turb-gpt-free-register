const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.resolve(__dirname,'../../webui/static/js/shared/common.js'),'utf8');
const block=(from,to)=>{
 const start=source.indexOf(from),end=source.indexOf(to,start+from.length);
 assert.ok(start>=0&&end>start,`navigation contract block exists: ${from}`);
 return source.slice(start,end);
};
test('registration tasks compatibility route retains its view through hash normalization and restoration',()=>{
 const calls=[],nodes=new Map([['tab-register',{dataset:{moduleView:'launch'}}]]);
 const context={window:null,URLSearchParams,console,document:{getElementById:id=>nodes.get(id),querySelectorAll:()=>[]},
  localStorage:{setItem:(...args)=>calls.push(['saved',...args])},$:()=>null,
  closePageDialogsForNavigation:()=>calls.push(['close']),closeMobileSidebar(){},updateNavigationBackButton(){},
  recordNavigationHistory(){},ACTIVE_TAB:'register',SHOW_ARCHIVED_ACCOUNTS:false,
  activateTab:tab=>calls.push(['tab',tab]),RegistrationPage:{setView:view=>calls.push(['view',view])}};
 context.window=context;
 const code=[
  "const NAV_ALLOWED_TABS=['register','overview','bulk'];",
  block('const MODULE_VIEW_META =','function setModuleView('),
  block('function navigationModuleForTab(','function currentNavigationState('),
  block('function navigationHash(','function historyNavigationState('),
  block('function applyNavigationState(','function initializeNavigationHistory('),
  block('function setModuleView(', "$$('[data-module-subnav]').forEach"),
 ].join('\n');
 vm.runInNewContext(code,context);
 const hash=context.navigationHash({tab:'register',view:'tasks'});
 assert.equal(hash,'#register/tasks');
 const restored=context.parseNavigationHash(hash);
 assert.equal(restored.tab,'register');
 assert.equal(restored.module,'register');
 assert.equal(restored.view,'tasks');
 context.applyNavigationState(restored);
 assert.equal(nodes.get('tab-register').dataset.moduleView,'tasks');
 assert.deepEqual(calls.filter(call=>call[0]==='view'),[['view','tasks']]);
 assert.deepEqual(calls.filter(call=>call[0]==='tab'),[['tab','register']]);
});
