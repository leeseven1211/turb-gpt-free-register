import {afterEach,describe,expect,it,vi} from 'vitest';
import {createRegistrationApi} from './registration';

function json(value:unknown,status=200){
  return new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
}

afterEach(()=>vi.unstubAllGlobals());

describe('registration api metadata',()=>{
  it('只读取邮箱来源接口并保留注册资格结果',async()=>{
    const fetch=vi.fn().mockResolvedValue(json({
      sources:[{value:'outlook',label:'Outlook',enabled:true}],
      registration_drivers:[],
      capabilities:{features:{register:{enabled:true,reason:'库存正常'}}},
    }));
    vi.stubGlobal('fetch',fetch);

    await expect(createRegistrationApi().metadata()).resolves.toMatchObject({
      sources:[{value:'outlook',enabled:true}],
      capabilities:{features:{register:{enabled:true,reason:'库存正常'}}},
    });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0]?.[0]).toBe('/api/email-sources');
  });
});
