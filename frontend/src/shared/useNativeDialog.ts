import {nextTick,onBeforeUnmount,onMounted,watch,type Ref} from 'vue';
interface ScrollSnapshot {top:string;topPriority:string;bodyOverflow:string;bodyPriority:string;rootOverflow:string;rootPriority:string;scrollY:number;external:boolean;classExisted:boolean}
const locks=new Set<HTMLDialogElement>();
let snapshot:ScrollSnapshot|undefined;
let observer:MutationObserver|undefined,observedExternal=false;
function retainNativeLock(){
 const saved=snapshot;if(!saved||!locks.size)return;
 const body=document.body,root=document.documentElement,external=body.classList.contains('modal-open');
 if(observedExternal&&!external&&saved.external){
  // The previous legacy owner restored its baseline while our dialog remains.
  // That restored state is now the baseline; never resurrect its old lock.
  saved.external=false;saved.top=body.style.getPropertyValue('top');saved.topPriority=body.style.getPropertyPriority('top');
  saved.rootOverflow=root.style.getPropertyValue('overflow');saved.rootPriority=root.style.getPropertyPriority('overflow');
 }
 observedExternal=external;
 if(!external){
  const top=`-${saved.scrollY}px`;
  if(body.style.top!==top)body.style.setProperty('top',top);
  if(root.style.overflow!=='hidden')root.style.setProperty('overflow','hidden');
 }
 if(body.style.overflow!=='hidden')body.style.setProperty('overflow','hidden');
 if(!body.classList.contains('em-native-dialog-lock'))body.classList.add('em-native-dialog-lock');
}
function acquire(dialog:HTMLDialogElement){
 if(locks.has(dialog))return;
 if(!locks.size){
  const body=document.body,root=document.documentElement,external=body.classList.contains('modal-open');
  const borrowedScroll=external&&/^-\d+(?:\.\d+)?px$/.test(body.style.top)?-parseFloat(body.style.top):null;
  snapshot={top:body.style.getPropertyValue('top'),topPriority:body.style.getPropertyPriority('top'),bodyOverflow:body.style.getPropertyValue('overflow'),bodyPriority:body.style.getPropertyPriority('overflow'),rootOverflow:root.style.getPropertyValue('overflow'),rootPriority:root.style.getPropertyPriority('overflow'),scrollY:borrowedScroll??(window.scrollY||root.scrollTop||0),external,classExisted:body.classList.contains('em-native-dialog-lock')};
  if(!external)body.style.setProperty('top',`-${snapshot.scrollY}px`);
  body.classList.add('em-native-dialog-lock');body.style.setProperty('overflow','hidden');root.style.setProperty('overflow','hidden');
  observedExternal=external;observer=new MutationObserver(retainNativeLock);observer.observe(body,{attributes:true,attributeFilter:['class','style']});observer.observe(root,{attributes:true,attributeFilter:['style']});
 }
 locks.add(dialog);
}
function release(dialog:HTMLDialogElement){
 if(locks.has(dialog))retainNativeLock();
 if(!locks.delete(dialog)||locks.size||!snapshot)return;
 observer?.disconnect();observer=undefined;
 const saved=snapshot; snapshot=undefined;
 const body=document.body,root=document.documentElement,external=body.classList.contains('modal-open');
 if(!saved.classExisted)body.classList.remove('em-native-dialog-lock');
 body.style.setProperty('overflow',saved.bodyOverflow,saved.bodyPriority);
 // A legacy modal opened while ours was up owns the current top/root lock.
 // Its existing manager will restore those when its own last dialog closes.
 if(external&&!saved.external)return;
 body.style.setProperty('top',saved.top,saved.topPriority);root.style.setProperty('overflow',saved.rootOverflow,saved.rootPriority);
 if(!external&&!saved.external)window.scrollTo(0,saved.scrollY);
}
function visibleOwner(element:HTMLElement){
 if(!element.isConnected||element.closest('[hidden],.hidden,[inert]'))return false;
 for(let parent:HTMLElement|null=element;parent;parent=parent.parentElement){const style=getComputedStyle(parent);if(style.display==='none'||style.visibility==='hidden')return false;}
 return true;
}
export function useNativeDialog(element:Ref<HTMLDialogElement|undefined>,opened:()=>boolean,canRestoreFocus:()=>boolean=()=>true){
 let opener:HTMLElement|null=null,disposed=false,owned:HTMLDialogElement|undefined;
 async function sync(){
  const dialog=element.value;if(!dialog||disposed)return;
  if(opened()&&!dialog.open){opener=document.activeElement instanceof HTMLElement?document.activeElement:null;dialog.showModal();owned=dialog;acquire(dialog);await nextTick();if(!disposed&&dialog.open)dialog.querySelector<HTMLElement>('button,input,select,textarea')?.focus();}
  else if(!opened()){if(dialog.open)dialog.close();release(dialog);if(opener&&canRestoreFocus()&&!document.hidden&&visibleOwner(opener))opener.focus();}
 }
 watch(opened,()=>void sync(),{flush:'post'});onMounted(()=>void sync());onBeforeUnmount(()=>{disposed=true;owned?.close();if(owned)release(owned);});
}
