import {reactive,watch} from 'vue';
import {createExtractApi} from '../../api/extract';
import type {CandidateFilters,CandidatePreview,CreateBatchPayload,ExtractConfig,ExtractDeps,ExtractReceipt} from './contracts';
import {linkTypes,message,modes,sourceSuffix} from './presentation';
export function createExtractBatch(input:ExtractDeps={},refresh:()=>Promise<unknown>=async()=>{}){
 const api=input.api||createExtractApi(input);
 const state=reactive({config:null as ExtractConfig|null,filters:{query:'',source:'',date_from:'',date_to:'',extract_status:'not_succeeded',promotion:'eligible'} as CandidateFilters,limit:100,workers:1,title:'',provider:'',mode:'',type:'',preview:null as CandidatePreview|null,previewSignature:'',receipt:null as (ExtractReceipt&{submission_id:string})|null,submissionSignature:'',error:'',feedback:'',creating:false,loading:false,opened:false});
 let dead=false,sequence=0,openSequence=0,controller:AbortController|undefined,initializedWorkers=false,submission:{signature:string;id:string}|null=null;
 const signature=()=>JSON.stringify({filters:{...state.filters},limit:Number(state.limit)});
 function invalidate(){sequence++;controller?.abort();state.preview=null;state.previewSignature='';state.loading=false;state.feedback='筛选条件已变更，请刷新匹配数量。';}
 const stop=watch(()=>signature(),invalidate,{flush:'sync'});
 function setProvider(value:string){state.provider=value;const provider=state.config?.providers.find(item=>item.id===value),allowed=modes(provider),types=linkTypes(provider);state.mode=allowed.includes(state.mode)?state.mode:allowed.includes('extract_only')?'extract_only':allowed.includes('manual_payment')?'manual_payment':'';state.type=types.includes(state.type)?state.type:types.includes(provider?.default_type||'')?provider!.default_type!:types[0]||'';}
 async function open(config?:ExtractConfig){state.opened=true;state.error='';const epoch=++openSequence;const value=config||await api.config();if(dead||epoch!==openSequence||!state.opened)return;state.config=value;if(!initializedWorkers){const max=workersMax(),n=value.batch_workers_default;state.workers=Number.isInteger(n)&&Number(n)>=1&&Number(n)<=max?n!:1;initializedWorkers=true;}const id=value.providers.some(item=>item.id===state.provider)?state.provider:value.providers.some(item=>item.id===value.default_provider)?value.default_provider!:value.providers[0]?.id||'';setProvider(id);}
 function workersMax(){const max=state.config?.batch_workers_max;return Number.isInteger(max)&&Number(max)>=1&&Number(max)<=50?max!:50;}
 async function preview(){if(dead||!state.opened)return;controller?.abort();controller=new AbortController();const epoch=++sequence,key=signature(),filters={...state.filters},limit=Number(state.limit);state.preview=null;state.previewSignature='';state.loading=true;state.error='';
  try{if(!Number.isInteger(limit)||limit<1||limit>5000)throw Error('本批运行数量须为 1 至 5000 的整数');const result=await api.candidates(filters,limit,controller.signal);if(dead||epoch!==sequence||!state.opened||key!==signature())return;if(!Number.isSafeInteger(result.total)||!Number.isSafeInteger(result.selected_count)||result.selected_count<0||result.selected_count>limit)throw Error('候选统计响应无效');state.preview=result;state.previewSignature=key;state.feedback=`匹配 ${result.total.toLocaleString('zh-CN')} 个可用账号，本批计划运行 ${result.selected_count.toLocaleString('zh-CN')} 个。`;}
  catch(error){if(!dead&&epoch===sequence&&state.opened){state.error=`匹配数量统计失败：${message(error)}`;state.feedback='请检查筛选条件后重试。';}}finally{if(epoch===sequence)state.loading=false;}
 }
 async function submit(){if(dead||state.creating||!state.opened||!state.preview?.selected_count||state.previewSignature!==signature())return;state.creating=true;state.error='';
  try{const provider=state.config?.providers.find(item=>item.id===state.provider),allowed=modes(provider),types=linkTypes(provider),workers=Number(state.workers),limit=Number(state.limit);if(!provider||!allowed.includes(state.mode)||!types.includes(state.type))throw Error('请选择平台公布的运行模式和提链类型');if(!Number.isInteger(workers)||workers<1||workers>workersMax())throw Error(`批次并发请输入 1 到 ${workersMax()} 的整数`);
   const base={workers,title:state.title.trim(),provider_id:state.provider,mode:state.mode,type:state.type,filters:{...state.filters},limit},key=JSON.stringify(base);
   if(base.mode==='auto_payment'&&!(await (input.confirm?input.confirm(`将为本批约 ${state.preview.selected_count} 个账号启用自动支付任务${sourceSuffix({...provider,mode:base.mode})}，确认继续？`):window.confirm('确认继续此批自动支付任务？'))))return;
   if(dead||!state.opened||key!==JSON.stringify({workers:Number(state.workers),title:state.title.trim(),provider_id:state.provider,mode:state.mode,type:state.type,filters:{...state.filters},limit:Number(state.limit)}))return;
   if(!submission||submission.signature!==key){submission={signature:key,id:globalThis.crypto.randomUUID()};state.receipt=null;}state.submissionSignature=key;
   const payload:CreateBatchPayload={...base,submission_id:submission.id};const result=await api.create(payload),receipt={...result,submission_id:submission.id};state.receipt=receipt;state.preview=null;state.previewSignature='';submission=null;state.feedback=`已创建批次，入队 ${result.started||0} 个任务，跳过 ${result.skipped||0} 个，提交失败 ${result.failed||0} 个。`;state.error='';try{await refresh();}catch{/* The persisted receipt remains authoritative if list reload fails. */}return receipt;
  }catch(error){state.error=`${message(error)}；可重试获取同一批次的提交结果。`;}finally{state.creating=false;}
 }
 function close(){state.opened=false;openSequence++;invalidate();}
 function destroy(){dead=true;close();stop();}
 return{state,open,setProvider,workersMax,preview,invalidate,submit,close,destroy};
}
