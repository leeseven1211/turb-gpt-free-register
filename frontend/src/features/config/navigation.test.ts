import {describe,it,expect} from 'vitest';
// Test-only schema snapshot: static AST extraction of config/schema.py _FIELD_DEFINITIONS.
// Values are empty placeholders; the application still loads its schema from the API.
import fixture from './schemaNavigation.fixture.json';
import type {ConfigField} from './contracts';
import {projectedFields,fieldDomain,menuFor,subsectionFor,findDestination,orderedMenus,extractProviders} from './navigation';
const fields=fixture as ConfigField[];
describe('complete legacy configuration navigation',()=>{
 it('matches all 346 legacy field destinations captured before the renderer cutover',()=>{expect(fixture).toHaveLength(346);for(const field of fixture){const item=field.legacyNavigation;expect(fieldDomain(field),field.key).toBe(item.domain);expect(menuFor(fieldDomain(field)),field.key).toBe(item.menu);if(['邮箱 / OTP','接码平台','代理与网络','Codex','提链'].includes(item.domain))expect(subsectionFor(field,fields),field.key).toBe(item.section);}});
 it('projects each visible key exactly once across all seven menus',()=>{const duplicate=[...fields,fields[0]!];const projected=projectedFields(duplicate);expect(new Set(projected.map(field=>field.key)).size).toBe(projected.length);expect(orderedMenus(fields)).toEqual(['注册与账号','代理与网络','邮箱与验证码','浏览器','服务集成','提链','系统与维护']);});
 it('finds exact keys before prefix matches and old aliases/help in hidden sections',()=>{for(const key of ['PLAN_CHECK_AUTO_REFRESH_AT_ENABLED','CODEX_OAUTH_AUTO_UPLOAD_SUB2API','C2A_API_KEY','ACCOUNT_AT_REFRESH_COUNTRY','EMAIL_BUTLER_API_KEY','SUB2API_MONITOR_GROUP_IDS','SUB2API_UPLOAD_GROUP_IDS']){const field=fields.find(field=>field.key===key)!;expect(findDestination(key,fields)?.domain).toBe(fieldDomain(field));}expect(findDestination('网站配置',fields)?.domain).toBe('WebUI 授权');});
 it('routes independent payment and provider settings without the synthetic platform field',()=>{const f=(key:string,extra={})=>({key,group:'提链',label:key,type:'str',value:'',...extra}) as ConfigField;const sample=[f('EXTRACT_LINK_DEFAULT_PROVIDER',{options:[{value:'legacy',label:'旧'},{value:'huanguang',label:'幻光'}]}),f('EXTRACT_LINK_LEGACY_ENABLED'),f('EXTRACT_LINK_HUANGUANG_ENABLED'),f('EXTRACT_LINK_HUANGUANG_CDK'),f('EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY')];expect(extractProviders(sample)).toHaveLength(2);expect(findDestination('EXTRACT_LINK_HUANGUANG_CDK',sample)?.section).toBe('幻光');expect(findDestination('EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY',sample)?.section).toBe('独立支付');});
});
