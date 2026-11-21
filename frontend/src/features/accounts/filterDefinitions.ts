import type {DeepReadonly} from 'vue';
import type {AccountFacets} from '../../api/accounts';
import type {AccountQuerySpec} from './queryAdapter';

export type AccountFilterKey = 'id'|'email'|'source'|'registration_driver'|'token'|'account_status'|'password'|'plan'|'promotion'|'totp'|'risk'|'codex'|'date'|'email_status';
export type AccountFilterField = Exclude<AccountFilterKey,'date'>|'date_from'|'date_to';
export interface AccountColumn {key:AccountFilterKey;label:string;kind:'text'|'enum'|'date-range';group?:string;placeholder?:string;order?:readonly string[]}
export type AccountFacetLabel = (group:string,value:string)=>string;
export const accountFilters:readonly AccountColumn[] = [
  {key:'id',label:'ID',kind:'text',placeholder:'#'},
  {key:'email',label:'邮箱 / 姓名',kind:'text',placeholder:'邮箱或姓名'},
  {key:'source',label:'来源',kind:'enum',group:'source'},
  {key:'registration_driver',label:'注册驱动',kind:'enum',group:'registration_driver',order:['roxy','roxy_oss','protocol','protocol_oss','protocol_oss_2','sentinel_rs','cloakbrowser','unknown']},
  {key:'token',label:'Token',kind:'enum',group:'account_token',order:['has','expired','invalid_401','invalid_403','invalid_other','none']},
  {key:'account_status',label:'账号状态',kind:'enum',group:'account_status',order:['active','deactivated']},
  {key:'password',label:'账号密码',kind:'enum',group:'password'},
  {key:'plan',label:'套餐',kind:'enum',group:'plan'},
  {key:'promotion',label:'套餐优惠',kind:'enum',group:'promotion'},
  {key:'totp',label:'2FA',kind:'enum',group:'totp'},
  {key:'risk',label:'封号邮件',kind:'enum',group:'risk'},
  {key:'codex',label:'Codex',kind:'enum',group:'codex'},
  {key:'date',label:'创建 / 更新',kind:'date-range'},
  {key:'email_status',label:'邮箱状态',kind:'enum',group:'email_status',order:['invalid','unmarked']},
];
export function selectedValues(query:DeepReadonly<AccountQuerySpec>,key:AccountFilterKey):readonly string[] {
  if(key==='plan')return query.plan;
  if(key==='id'||key==='email'||key==='date')return [];
  return query.filters[key];
}
export function textValue(query:DeepReadonly<AccountQuerySpec>,key:AccountFilterField):string {
  if(key==='date_from'||key==='date_to')return query[key];
  if(key==='id'||key==='email')return query.filters[key];
  return '';
}
export function columnActive(query:DeepReadonly<AccountQuerySpec>,column:AccountColumn):boolean {
  if(column.kind==='date-range')return !!(query.date_from||query.date_to);
  if(column.kind==='text')return !!textValue(query,column.key as AccountFilterField);
  return selectedValues(query,column.key).length>0;
}
export const promotionOffers = ['plus_100','plus_50','plus_other','go_100','go_50','go_other'];

export function facetOptions(query:DeepReadonly<AccountQuerySpec>,facets:DeepReadonly<AccountFacets>,column:AccountColumn,label:AccountFacetLabel) {
  const selected=selectedValues(query,column.key);
  const source=column.kind==='enum' ? facets[column.key as keyof AccountFacets]||[] : [];
  const values=source.filter(item=>item.value&&(item.count>0||selected.includes(item.value))).map(item=>({...item}));
  for(const value of selected)if(!values.some(item=>item.value===value))values.push({value,count:0});
  const order=column.order||[];
  values.sort((a,b)=>{
    const left=order.indexOf(a.value),right=order.indexOf(b.value);
    return (left<0?order.length:left)-(right<0?order.length:right);
  });
  const options: {value:string;count:number|null;label:string}[] = values
    .filter(item=>column.key!=='promotion'||!promotionOffers.includes(item.value))
    .map(item=>({...item,label:label(column.group||column.key,item.value)}));
  if(column.key==='promotion')for(const value of promotionOffers)options.push({value,count:null,label:label('promotion',value)});
  return options;
}
export function filterChips(query:DeepReadonly<AccountQuerySpec>,label:AccountFacetLabel) {
  return accountFilters.flatMap(column=>{
    let value='';
    if(column.kind==='date-range')value=query.date_from&&query.date_to?`${query.date_from} 至 ${query.date_to}`:query.date_from?`自 ${query.date_from}`:query.date_to?`截至 ${query.date_to}`:'';
    else if(column.kind==='text')value=textValue(query,column.key as AccountFilterField);
    else value=selectedValues(query,column.key).map(value=>label(column.group||column.key,value)).join('、');
    const text=`${column.label}：${value}`;
    return value?[{key:column.key,label:text,title:text,removeLabel:`清除${column.label}筛选`}]:[];
  });
}
