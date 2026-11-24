const {createVueHarness}=require('../frontend_vue_loader.cjs');
const harness=createVueHarness(),win=harness.document.defaultView;
win.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};
win.HTMLDialogElement.prototype.close=function(){if(!this.open)return;this.removeAttribute('open');this.dispatchEvent(new win.Event('close'));};win.scrollTo=()=>{};
const {createExtractWorkbench}=harness.load('src/features/extract/useExtractWorkbench.ts');
const {createExtractBatch}=harness.load('src/features/extract/useExtractBatch.ts');
const {createExtractArtifacts}=harness.load('src/features/extract/useExtractArtifacts.ts');
const presentation=harness.load('src/features/extract/presentation.ts');
const Page=harness.load('src/features/extract/ExtractWorkbench.vue').default;
const live=[];
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};};
const flush=async()=>{await new Promise(r=>setImmediate(r));await harness.nextTick();};
const task=(extra={})=>({task_id:'9007199254740993',account_id:'9007199254740995',email:'synthetic@example.test',provider_id:'legacy',mode:'extract_only',task_status:'failed',preflight_status:'passed',extraction_status:'failed',payment_status:'unpaid',plus_status:'pending',run_count:2,created_at:'2026-11-17T00:00:00Z',...extra});
function setup(overrides={}){
 const calls=[],copied=[],messages=[];
 const defaults={config:async()=>({providers:[{id:'legacy',label:'虾扯蛋链',modes:['extract_only','manual_payment','auto_payment'],link_types:['pix','upi'],default_type:'upi',payment_source:'xxsyun',payment_source_label:'XXSYUN'}],unavailable_providers:[{id:'huanguang',label:'幻光提链',unavailable_reason:'平台未启用'}],default_provider:'legacy',batch_workers_default:3,batch_workers_max:7}),summary:async()=>({today_extracted:1,awaiting_payment:2,needs_review:3}),batches:async page=>({items:[{batch_id:7,title:'合成批次',requested_count:31,mode:'auto_payment',payment_source:'native',counts:{queued:1}}],total:31,page,page_size:20}),batch:async id=>({item:{batch_id:id,counts:{}}}),tasks:async q=>({items:[task()],total:31,page:q.page,page_size:q.size,counts:{all:31}}),candidates:async(_filters,limit)=>({total:800,selected_count:Math.min(800,limit),items:[{account_id:1,email:'synthetic@example.test'}]}),create:async()=>({ok:true,batch_id:'9007199254740997',started:500,skipped:2,failed:1}),cancel:async id=>({ok:true,batch_id:id,cancelled:1,skipped:2,failed:0}),detail:async id=>({item:task({task_id:id,has_payment_entry:true,has_extract_link:true}),events:[{label:'提链响应',status:'failed',message:'synthetic diagnostic'}],history:[task({run_id:2})]}),paymentEntry:async()=>({entry:{payment_page_url:'https://pay.example.test/page',payment_url:'https://pay.example.test/entry',qr_data:'plain-qr-data',qr_image_url_png:'https://pay.example.test/qr.png',qr_image_url_svg:'https://pay.example.test/qr.svg',amount:0,expires_at:'2026-11-17T00:05:00Z'}}),action:async(id)=>({ok:true,accepted:true,task_id:id,run_id:'9007199254740999'}),actionBulk:async(ids)=>({ok:true,command_id:'9007199254740997',status:'success',items:ids.map(id=>({key:String(id),status:'updated',data:{task_id:String(id),run_id:'9007199254740999'}}))}),paymentEntries:async(ids)=>({ok:true,items:ids.map(id=>({task_id:String(id),status:'updated',entry:{payment_url:'https://pay.example.test/local'}}))}),links:async()=>({ok:true,url:'https://pay.example.test/link'}),secret:async()=>({ok:true,value:'ephemeral-secret'}),export:async()=>new Blob(['csv'])};
 const api=Object.fromEntries(Object.entries(defaults).map(([name,impl])=>[name,(...args)=>{calls.push({name,args});return (overrides[name]||impl)(...args);} ]));
 const deps={api,visible:true,notify:x=>messages.push(x),confirm:async()=>true,copyText:async x=>copied.push(x),accountSources:{cloudflare_domain:'域名邮箱',email_butler:'Email Butler',manual:'手动导入'}};
 function owner(){const value=createExtractWorkbench(deps);live.push(value);return value;}
 function batch(){const value=createExtractBatch(deps);live.push(value);return value;}
 function artifacts(refresh){const value=createExtractArtifacts(deps,refresh);live.push(value);return value;}
 function page(){return harness.mount(Page,{props:{deps}});}
 return{api,deps,calls,copied,messages,owner,batch,artifacts,page,requests:name=>calls.filter(x=>x.name===name)};
}
function cleanup(){live.splice(0).forEach(value=>value.destroy());harness.cleanup();Object.defineProperty(harness.document,'hidden',{configurable:true,value:false});}
module.exports={harness,setup,cleanup,deferred,flush,task,presentation};
