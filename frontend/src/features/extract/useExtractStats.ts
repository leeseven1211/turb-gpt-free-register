import {reactive} from 'vue';
import {createExtractApi} from '../../api/extract';
import type {ExtractAnalytics,ExtractDeps} from './contracts';
import {message,providerLabels} from './presentation';
export function createExtractStats(input:ExtractDeps={}){
 const api=input.api||createExtractApi(input),state=reactive({days:30,provider:'',data:null as ExtractAnalytics|null,scope:'',error:'',loading:false,visible:input.visible!==false,providers:{...providerLabels}});
 let dead=false,sequence=0,controller:AbortController|undefined;
 const active=()=>!dead&&state.visible&&!document.hidden;
 async function load(){if(!active())return;const seq=++sequence,scope=`${state.days}:${state.provider}`,previous=state.scope===scope?state.data:null;controller?.abort();controller=new AbortController();state.loading=true;state.error='';state.data=previous;
  try{const value=await api.analytics(state.days,state.provider,controller.signal);if(seq!==sequence||!active())return;state.data=value;state.scope=scope;for(const p of value.providers||[])if(p.provider_id)state.providers[p.provider_id]=providerLabels[p.provider_id]||p.provider_id;input.onReady?.();}
  catch(error){if(seq===sequence&&active()){state.error=message(error);state.data=previous;}}
  finally{if(seq===sequence)state.loading=false;}
 }
 function suspend(){sequence++;controller?.abort();state.loading=false;}
 function setVisible(value:boolean){state.visible=value;if(value)void load();else suspend();}
 function onVisibility(){if(document.hidden)suspend();else if(state.visible)void load();}
 document.addEventListener('visibilitychange',onVisibility);
 function destroy(){dead=true;suspend();document.removeEventListener('visibilitychange',onVisibility);}
 return{state,load,setVisible,destroy};
}
