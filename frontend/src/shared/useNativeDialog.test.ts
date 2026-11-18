import {flushPromises,mount} from '@vue/test-utils';
import {defineComponent,ref} from 'vue';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {useNativeDialog} from './useNativeDialog';
const wrappers:ReturnType<typeof mount>[]=[];
const Component=defineComponent({setup(){
 const first=ref<HTMLDialogElement>(),second=ref<HTMLDialogElement>(),one=ref(false),two=ref(false),active=ref(true);
 useNativeDialog(first,()=>one.value,()=>active.value);useNativeDialog(second,()=>two.value,()=>active.value);
 return{first,second,one,two,active};
},template:'<section :style="{display:active?undefined:\'none\'}"><button id="dialog-opener" @click="one=true">open</button><dialog ref="first"><button>first</button></dialog><dialog ref="second"><button>second</button></dialog></section>'});
beforeEach(()=>{
 Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value:function(){this.open=true;}});
 Object.defineProperty(HTMLDialogElement.prototype,'close',{configurable:true,value:function(){this.open=false;}});
 Object.defineProperty(document,'hidden',{configurable:true,value:false});Object.defineProperty(window,'scrollY',{configurable:true,value:240});vi.stubGlobal('scrollTo',vi.fn());
 document.body.style.overflow='clip';document.body.style.top='';document.documentElement.style.overflow='visible';
});
afterEach(()=>{wrappers.splice(0).forEach(wrapper=>wrapper.unmount());document.body.classList.remove('modal-open','em-native-dialog-lock');document.body.removeAttribute('style');document.documentElement.removeAttribute('style');vi.unstubAllGlobals();});
async function page(){const wrapper=mount(Component,{attachTo:document.body});wrappers.push(wrapper);return wrapper;}
describe('native dialog shared scroll/focus lifetime',()=>{
 it('locks the background for the entire stack and restores exact prior styles/scroll on final close',async()=>{
  const wrapper=await page();wrapper.vm.one=true;await flushPromises();
  expect(document.body.classList.contains('em-native-dialog-lock')).toBe(true);expect(document.body.style.overflow).toBe('hidden');expect(document.body.style.top).toBe('-240px');expect(document.documentElement.style.overflow).toBe('hidden');
  wrapper.vm.two=true;await flushPromises();wrapper.vm.one=false;await flushPromises();
  expect(document.body.classList.contains('em-native-dialog-lock')).toBe(true);expect(document.documentElement.style.overflow).toBe('hidden');
  wrapper.vm.two=false;await flushPromises();
  expect(document.body.classList.contains('em-native-dialog-lock')).toBe(false);expect(document.body.style.overflow).toBe('clip');expect(document.body.style.top).toBe('');expect(document.documentElement.style.overflow).toBe('visible');expect(window.scrollTo).toHaveBeenCalledWith(0,240);
 });
 it('borrows an existing external modal lock without removing it or changing its saved scroll',async()=>{
  document.body.classList.add('modal-open');document.body.style.top='-123px';document.documentElement.style.overflow='hidden';
  const wrapper=await page();wrapper.vm.one=true;await flushPromises();wrapper.vm.one=false;await flushPromises();
  expect(document.body.classList.contains('modal-open')).toBe(true);expect(document.body.style.top).toBe('-123px');expect(document.documentElement.style.overflow).toBe('hidden');expect(window.scrollTo).not.toHaveBeenCalled();
 });
 it('keeps a newly opened external owner locked and releases owned locks on unmount',async()=>{
  const wrapper=await page();wrapper.vm.one=true;await flushPromises();document.body.classList.add('modal-open');document.body.style.top='-80px';
  wrapper.unmount();wrappers.pop();
  expect(document.body.classList.contains('em-native-dialog-lock')).toBe(false);expect(document.body.classList.contains('modal-open')).toBe(true);expect(document.body.style.top).toBe('-80px');expect(document.documentElement.style.overflow).toBe('hidden');expect(document.body.style.overflow).toBe('clip');expect(window.scrollTo).not.toHaveBeenCalled();
 });
 it('keeps the native lock after a borrowed external modal closes first and releases the final page lock',async()=>{
  document.body.classList.add('modal-open');document.body.style.top='-123px';document.documentElement.style.overflow='hidden';
  const wrapper=await page();wrapper.vm.one=true;await flushPromises();
  document.body.classList.remove('modal-open');document.body.style.top='';document.documentElement.style.overflow='';await flushPromises();
  expect(document.body.classList.contains('em-native-dialog-lock')).toBe(true);expect(document.body.style.top).toBe('-123px');expect(document.documentElement.style.overflow).toBe('hidden');
  wrapper.vm.one=false;await flushPromises();expect(document.body.style.top).toBe('');expect(document.documentElement.style.overflow).toBe('');expect(document.body.style.overflow).toBe('clip');expect(document.body.classList.contains('em-native-dialog-lock')).toBe(false);expect(window.scrollTo).toHaveBeenCalledWith(0,123);
 });
 it('does not resurrect an external lock when both owners close in the same Vue flush',async()=>{
  document.body.classList.add('modal-open');document.body.style.top='-123px';document.documentElement.style.overflow='hidden';
  const wrapper=await page();wrapper.vm.one=true;await flushPromises();
  wrapper.vm.one=false;document.body.classList.remove('modal-open');document.body.style.top='';document.documentElement.style.overflow='';await flushPromises();
  expect(document.body.classList.contains('em-native-dialog-lock')).toBe(false);expect(document.body.style.top).toBe('');expect(document.documentElement.style.overflow).toBe('');
 });
 it('restores an explicit close focus but never focuses an inactive or document-hidden owner',async()=>{
  const wrapper=await page(),opener=wrapper.get('#dialog-opener').element as HTMLButtonElement;
  opener.focus();wrapper.vm.one=true;await flushPromises();wrapper.vm.one=false;await flushPromises();expect(document.activeElement).toBe(opener);
  opener.focus();wrapper.vm.one=true;await flushPromises();const focus=vi.spyOn(opener,'focus');wrapper.vm.active=false;wrapper.vm.one=false;await flushPromises();expect(focus).not.toHaveBeenCalled();
  wrapper.vm.active=true;opener.focus();wrapper.vm.one=true;await flushPromises();focus.mockClear();Object.defineProperty(document,'hidden',{configurable:true,value:true});wrapper.vm.one=false;await flushPromises();expect(focus).not.toHaveBeenCalled();
 });
});
