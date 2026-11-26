import type {DeepReadonly} from 'vue';
import type {AccountFacets} from '../../api/accounts';
import type {AccountQuerySpec} from './queryAdapter';

export type AccountFilterKey = 'id'|'email'|'source'|'registration_driver'|'token'|'account_status'|'password'|'plan'|'promotion'|'totp'|'risk'|'codex'|'date'|'email_status';
export type AccountFilterField = Exclude<AccountFilterKey,'date'>|'date_from'|'date_to';
export interface AccountColumn {key:AccountFilterKey;label:string;kind:'text'|'enum'|'date-range';group?:string;placeholder?:string;order?:readonly string[]}
export type AccountFacetLabel = (group:string,value:string)=>string;
export interface AccountFacetOption {value:string;count?:number|null;label?:string;group?:string}
export interface AccountFacetOptionGroup {key:string;label:string;options:AccountFacetOption[]}
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
const promotionGroups:Readonly<Record<string,string>>={team:'Team',plus:'Plus',go:'Go',status:'状态',legacy:'兼容条件'};
const promotionGroupOrder=['team','plus','go','status','legacy'] as const;
const promotionStatusOrder=['none','unknown','pending','failed','not_applicable'];
const legacyPromotionValues=new Set(['free_trial','half_price','other_discount','discount','other_promo','team_eligible',
  'plus_100','plus_50','plus_other','go_100','go_50','go_other','plus_50_1m','plus_50_2m','plus_50_3m']);
const promotionStatusValues=new Set(promotionStatusOrder);
const dynamicPromotionPattern=/^offer_v1_[0-9a-f]{32}$/i;
type FacetCollection=DeepReadonly<AccountFacets>|Readonly<Record<string,readonly AccountFacetOption[]|undefined>>;

function facetRows(facets:FacetCollection,key:string):readonly AccountFacetOption[] {
  const rows=(facets as Readonly<Record<string,unknown>>)[key];
  return Array.isArray(rows)?rows as readonly AccountFacetOption[]:[];
}
function promotionGroup(value:string,group?:string,labelText=''):string {
  if(group&&Object.hasOwn(promotionGroups,group))return group;
  if(promotionStatusValues.has(value))return 'status';
  if(dynamicPromotionPattern.test(value)){
    const normalized=labelText.toLowerCase();
    if(/^team(?:\s|·|：|:)/.test(normalized))return 'team';
    if(/^plus(?:\s|·|：|:)/.test(normalized))return 'plus';
    if(/^go(?:\s|·|：|:)/.test(normalized))return 'go';
  }
  return 'legacy';
}
function promotionFallbackLabel(value:string,selected=false):string {
  return dynamicPromotionPattern.test(value)?(selected?'已选优惠（信息暂不可用）':'优惠信息暂不可用'):value;
}
function promotionText(value:AccountFacetOption,label:AccountFacetLabel,selected=false):string {
  const raw=String(value.value);
  if(value.label)return String(value.label);
  if(dynamicPromotionPattern.test(raw))return promotionFallbackLabel(raw,selected);
  return String(label('promotion',raw)||raw);
}
function promotionSortKey(option:AccountFacetOption,index:number):[number,number,number,string,number] {
  const text=String(option.label||'').toLowerCase();
  const free=/免费|free(?:\s+trial)?/.test(text);
  const half=/半价|五折|half[\s-]*price|50\s*%/.test(text);
  const percentageText=text.match(/(\d+(?:\.\d+)?)\s*%/);
  const percentage=percentageText?Number(percentageText[1]):half?50:free?100:null;
  const durationText=text.match(/(\d+(?:\.\d+)?)\s*(个?月|周|天|年|months?|weeks?|days?|years?)/);
  const durationValue=durationText?Number(durationText[1]):Number.POSITIVE_INFINITY;
  const durationUnit=durationText?.[2]||'';
  const durationDays=durationUnit.includes('年')||durationUnit.includes('year')?durationValue*365
    :durationUnit.includes('月')||durationUnit.includes('month')?durationValue*30
    :durationUnit.includes('周')||durationUnit.includes('week')?durationValue*7
    :durationUnit.includes('天')||durationUnit.includes('day')?durationValue:durationValue;
  const kind=free?0:percentage!==null?1:2;
  return [kind,percentage===null?0:-percentage,durationDays,text,index];
}
function promotionOptions(query:DeepReadonly<AccountQuerySpec>,facets:FacetCollection,label:AccountFacetLabel):AccountFacetOption[] {
  const selected=new Set(selectedValues(query,'promotion'));
  const source=facetRows(facets,'promotion');
  const hasDynamic=source.some(item=>dynamicPromotionPattern.test(String(item.value||'')));
  const found=new Map<string,AccountFacetOption>();
  for(const item of source){
    const value=String(item.value||'');
    if(!value||(!(Number(item.count||0)>0)&&!selected.has(value)))continue;
    const displayLabel=promotionText(item,label,selected.has(value));
    found.set(value,{...item,value,count:item.count==null?0:Number(item.count),group:promotionGroup(value,item.group,displayLabel),label:displayLabel});
  }
  for(const value of selected){
    if(!found.has(value)){
      const displayLabel=promotionText({value},label,true);
      found.set(value,{value,count:0,group:promotionGroup(value,undefined,displayLabel),label:displayLabel});
    }
  }
  return [...found.values()].filter(item=>dynamicPromotionPattern.test(item.value)||!hasDynamic
    || selected.has(item.value)
    || (item.group!=='legacy'&&!legacyPromotionValues.has(item.value)));
}
export function facetOptionGroups(query:DeepReadonly<AccountQuerySpec>,facets:FacetCollection,column:AccountColumn,label:AccountFacetLabel):AccountFacetOptionGroup[] {
  const selected=selectedValues(query,column.key);
  const source=column.kind==='enum' ? facetRows(facets,column.key) : [];
  if(column.key==='promotion'){
    const groups=new Map<string,AccountFacetOption[]>();
    for(const option of promotionOptions(query,facets,label)){
      const key=promotionGroup(option.value,option.group);
      const list=groups.get(key)||[];
      list.push({...option,group:key});
      groups.set(key,list);
    }
    for(const group of groups.values()){
      const groupKey=group[0]?.group||'legacy';
      group.sort((left,right)=>{
        if(groupKey==='status'){
          const rankLeft=promotionStatusOrder.indexOf(left.value),rankRight=promotionStatusOrder.indexOf(right.value);
          return (rankLeft<0?promotionStatusOrder.length:rankLeft)-(rankRight<0?promotionStatusOrder.length:rankRight);
        }
        if(groupKey==='team'||groupKey==='plus'||groupKey==='go'){
          const leftKey=promotionSortKey(left,group.indexOf(left)),rightKey=promotionSortKey(right,group.indexOf(right));
          for(let index=0;index<leftKey.length;index++){
            if(leftKey[index]!==rightKey[index])return leftKey[index]<rightKey[index]?-1:1;
          }
        }
        return 0;
      });
    }
    return promotionGroupOrder.filter(key=>groups.has(key)).map(key=>({key,label:promotionGroups[key]!,options:groups.get(key)!}));
  }
  const values=source.filter(item=>item.value&&(Number(item.count||0)>0||selected.includes(item.value))).map(item=>({...item}));
  for(const value of selected)if(!values.some(item=>item.value===value))values.push({value,count:0});
  const order=column.order||[];
  values.sort((a,b)=>{
    const left=order.indexOf(a.value),right=order.indexOf(b.value);
    return (left<0?order.length:left)-(right<0?order.length:right);
  });
  return values.length?[{key:column.group||column.key,label:'',options:values.map(item=>({...item,label:item.label||label(column.group||column.key,item.value)}))}]:[];
}
export function facetOptions(query:DeepReadonly<AccountQuerySpec>,facets:FacetCollection,column:AccountColumn,label:AccountFacetLabel):AccountFacetOption[] {
  return facetOptionGroups(query,facets,column,label).flatMap(group=>group.options);
}
export function filterChips(query:DeepReadonly<AccountQuerySpec>,label:AccountFacetLabel,facets?:FacetCollection) {
  return accountFilters.flatMap(column=>{
    let value='';
    if(column.kind==='date-range')value=query.date_from&&query.date_to?`${query.date_from} 至 ${query.date_to}`:query.date_from?`自 ${query.date_from}`:query.date_to?`截至 ${query.date_to}`:'';
    else if(column.kind==='text')value=textValue(query,column.key as AccountFilterField);
    else value=selectedValues(query,column.key).map(value=>{
      const metadata=facets&&facetRows(facets,column.key).find(item=>item.value===value);
      if(metadata?.label)return metadata.label;
      if(column.key==='promotion'&&dynamicPromotionPattern.test(value))return promotionFallbackLabel(value,true);
      return String(label(column.group||column.key,value)||value);
    }).join('、');
    const text=`${column.label}：${value}`;
    return value?[{key:column.key,label:text,title:text,removeLabel:`清除${column.label}筛选`}]:[];
  });
}
