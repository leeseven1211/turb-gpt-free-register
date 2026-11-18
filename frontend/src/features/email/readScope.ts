import {isAbort} from '../../api/client';
import {message} from './presentation';
export function readScope(state:{loading:boolean;error:string},read:(signal:AbortSignal,valid:()=>boolean)=>Promise<void>){
 let active=false,disposed=false,generation=0,controller:AbortController|undefined,timer:ReturnType<typeof setTimeout>|undefined;
 const eligible=()=>active&&!document.hidden&&!disposed;
 function invalidate(){generation++;controller?.abort();controller=undefined;clearTimeout(timer);timer=undefined;state.loading=false;}
 async function refresh(){invalidate();if(!eligible())return;const ticket=generation;controller=new AbortController();const signal=controller.signal;const valid=()=>ticket===generation&&eligible();state.loading=true;try{await read(signal,valid);if(valid())state.error='';}catch(cause){if(valid()&&!isAbort(cause))state.error=message(cause);}finally{if(valid()){state.loading=false;controller=undefined;}}}
 function schedule(delay=0){invalidate();if(!eligible())return;const ticket=generation;const run=()=>{if(ticket===generation&&eligible())void refresh();};if(delay)timer=setTimeout(run,delay);else queueMicrotask(run);}
 return{refresh,schedule,invalidate,setActive(value:boolean){if(value===active||disposed)return;active=value;if(value)void refresh();else invalidate();},dispose(){disposed=true;invalidate();},eligible};
}
