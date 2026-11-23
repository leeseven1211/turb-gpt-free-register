const {createVueHarness}=require('../frontend_vue_loader.cjs');
const h=createVueHarness();
const Dashboard=h.load('src/features/dashboard/DashboardPage.vue').default;
const Registration=h.load('src/features/registration/RegistrationPage.vue').default;
const model=h.load('src/features/dashboard/useDashboard.ts');
const settle=async()=>{for(let i=0;i<12;i++)await Promise.resolve();await h.nextTick();};
const supply=()=>({scope:'local_pool',status:'known',total:20,available:12,used:6,failed:2,sources:['outlook','generic_api','cloudflare_domain','icloud_hide','email_butler'].map((source,index)=>({source,label:source,kind:'local_pool',status:'known',enabled:false,total:index===3?20:0,available:index===3?12:0,used:index===3?6:0,failed:index===3?2:0}))});
const dashboard=(override={})=>({accounts:{total:12,active:10,archived:2,codex_ready:4,plans:{free:10,plus:8,pro:6,team:4,go:2}},email:{supply:supply(),sources:[]},jobs:{total:20,counts:{pending:3,running:2,stopping:1,success:10,failed:2,partial_success:3,stopped:1,cancelled:1},today:'今天',today_counts:{success:10,partial_success:3,failed:2}},proxy:{platform:'1024proxy',active_leases:4,leases:['a','b','c','d'].map(endpoint=>({endpoint,region:'US'}))},codex:{total:4,pending:1,exported:3},...override});
function prepare(){
 Object.defineProperty(h.document,'hidden',{configurable:true,value:false});
 HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};
 HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');};
 window.scrollTo=()=>{};
 h.cleanup();
}
async function mountDashboard(data=dashboard(),capabilities={},preferences){
 prepare();const calls=[],navigations=[],configs=[],ready=[],toasts=[],api={dashboard:async()=>{calls.push('/api/dashboard');return data;},capabilities:async()=>{calls.push('/api/capabilities');return capabilities;}};
 if(preferences)localStorage.setItem('gpt_console_overview_preferences_v1',JSON.stringify(preferences));
 const wrapper=h.mount(Dashboard,{props:{api,deps:{visible:true,onReady:()=>ready.push('overview'),notify:value=>toasts.push(value),onNavigate:value=>navigations.push(value),onConfig:value=>configs.push(value)}}});
 await settle();return {wrapper,calls,navigations,configs,ready,toasts,api};
}
async function mountRegistration(value={accounts:24,email_supply:supply()}){
 prepare();const calls=[];const api={metadata:async()=>({sources:[],registration_drivers:[]}),summary:async()=>{calls.push('/api/summary');if(value instanceof Error)throw value;return value;},jobs:async()=>({items:[],total:0}),create:async()=>({}),action:async()=>({}),log:async()=>({}),debug:async()=>({}),diagnostics:async()=>({}),compare:async()=>({})};
 const wrapper=h.mount(Registration,{props:{deps:{api,visible:false}}});wrapper.vm.setVisible(true);await settle();return {wrapper,calls,api};
}
module.exports={h,model,settle,supply,dashboard,mountDashboard,mountRegistration};
