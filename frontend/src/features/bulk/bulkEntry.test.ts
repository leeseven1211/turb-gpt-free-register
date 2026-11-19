import {afterEach,expect,it,vi} from 'vitest';
import {mountBulk} from '../../bulk';
import {realAdapter} from '../accounts/uiTestSupport';

const mounted:ReturnType<typeof mountBulk>[]=[];
afterEach(()=>{mounted.splice(0).forEach(instance=>instance.destroy());document.body.innerHTML='';vi.unstubAllGlobals();});

it('同一个挂载节点只创建一个Vue页面，销毁后允许重新挂载',()=>{
  vi.stubGlobal('fetch',vi.fn());
  const host=document.createElement('div');document.body.append(host);
  const options={query:realAdapter(),isVisible:()=>true,onNavigation:vi.fn(),callbacks:{
    navigate:vi.fn(),updateNavigation:vi.fn(),notify:vi.fn(),formatDateTime:String,openTask:vi.fn(),
  }};
  const first=mountBulk(host,options);mounted.push(first);
  expect(mountBulk(host,options)).toBe(first);
  expect(host.querySelectorAll('[data-bulk-vue]')).toHaveLength(1);
  expect(fetch).not.toHaveBeenCalled();
  first.destroy();mounted.pop();
  const next=mountBulk(host,options);mounted.push(next);
  expect(next).not.toBe(first);expect(host.querySelectorAll('[data-bulk-vue]')).toHaveLength(1);
});
