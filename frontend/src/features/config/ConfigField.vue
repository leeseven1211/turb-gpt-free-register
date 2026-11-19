<script setup lang="ts">
import {computed} from 'vue';
import type {ConfigDraftOwner,ConfigField as Field,ConfigOption,ConfigValue} from './contracts';
import type {ConfigActions} from './configActions';
import ConfigChoicePicker from './ConfigChoicePicker.vue';
import ConfigFieldActions from './ConfigFieldActions.vue';
import ConfigSub2ApiGroups from './ConfigSub2ApiGroups.vue';
import {schemaOptions,registrationDriverValue} from './navigation';
const props=defineProps<{owner:ConfigDraftOwner;field:Field;actions?:ConfigActions;legacy?:boolean}>();
const value=computed(()=>props.owner.readField(props.field.key));
const id=computed(()=>`config-field-${props.field.key}`);
const error=computed(()=>props.owner.fieldErrors[props.field.key] || '');
const readonly=computed(()=>!!props.field.readonly || props.field.editable===false || !!props.field.disable_enable&&!value.value);
const countryList=computed(()=>['PROXY_POOL_COUNTRIES','PLAN_CHECK_COUNTRIES'].includes(props.field.key));
const isCountry=computed(()=>countryList.value&&!!props.field.country_codes?.length);
const singleCountry=computed(()=>['PROXY_POOL_DEFAULT_COUNTRY','REGISTRATION_COUNTRY','ACCOUNT_AT_REFRESH_COUNTRY'].includes(props.field.key)&&!!props.field.country_codes?.length);
const multi=computed(()=>['EMAIL_SOURCE','ROXY_RANDOM_OS_CHOICES','BROWSER_DATA_SAVER_AUTH_FLOWS','BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES'].includes(props.field.key) || props.field.type==='list_str_multiline'&&!!(props.field.options?.length||props.field.csv_options?.length));
const list=computed(()=>{
 const separator=['EMAIL_SOURCE','ROXY_RANDOM_OS_CHOICES'].includes(props.field.key)?/[,\n]+/:isCountry.value||multi.value?/[,\n\s]+/:/\n/;
 const raw=(Array.isArray(value.value)?value.value:String(value.value??'').split(separator)).map(item=>item.trim()).filter(Boolean);
 const values=countryList.value?[...new Set(raw.map(item=>item.toUpperCase()))]:raw;
 return props.field.key==='EMAIL_SOURCE'&&Array.isArray(props.field.options)?values.filter(item=>schemaOptions(props.field).some(option=>option.value===item)):values;
});
function countryLabel(code:string){const name=props.field.country_names?.[code];try{return `${name||new Intl.DisplayNames(['zh-CN'],{type:'region'}).of(code)||code} · ${code}`;}catch{return name?`${name} · ${code}`:code;}}
const baseOptions=computed<ConfigOption[]>(()=>{
 let result:ConfigOption[]=isCountry.value||singleCountry.value ? (props.field.country_codes||[]).map(code=>({value:code,label:countryLabel(code)})) : schemaOptions(props.field);
 if(!result.length && props.field.csv_options)result=props.field.csv_options.map(item=>({value:item,label:item}));
 if(props.field.key==='EXTRACT_LINK_TYPE' && props.actions?.extractTypeOptions.value.length)result=props.actions.extractTypeOptions.value;
 if(props.field.key==='ACCOUNT_LIVE_CHECK_DRIVER' && !props.owner.readField('ACCOUNT_LIVE_CHECK_BROWSER_ENABLED')) result=result.filter(item=>item.value!=='browser_roxy'||item.disabled);
 if(props.field.key==='ACCOUNT_AT_REFRESH_COUNTRY')result=[{value:'',label:'跟随注册国家'},...result];
 return result;
});
const selectValue=computed(()=>{const current=props.field.key==='REGISTRATION_DRIVER'?registrationDriverValue(value.value):String(value.value??'');return baseOptions.value.find(item=>item.value.toLowerCase()===current.trim().toLowerCase())?.value??current;});
const options=computed<ConfigOption[]>(()=>{const result=baseOptions.value;const current=selectValue.value;return !multi.value&&!isCountry.value&&current&&!result.some(item=>item.value===current)?[{value:current,label:`当前配置（${current}）`},...result]:result;});
const hasSelect=computed(()=>singleCountry.value||!!props.field.options?.length||props.field.key==='EXTRACT_LINK_TYPE'&&options.value.length>0);
const composite=computed(()=>{
 const saved=props.owner.readComposite(props.field.key);if(saved)return saved;
 if(props.field.key==='PROXY_POOL_WAIT_TIMEOUT')return {mode:Number(value.value)>0?'timed':'continuous',raw:Number(value.value)>0?String(value.value):''};
 return {mode:String(value.value??'').trim()?'limited':'unlimited',raw:String(value.value??'')};
});
const compositeActive=computed(()=>['timed','limited'].includes(composite.value.mode));
function setCompositeMode(mode:string){props.owner.setComposite(props.field.key,{mode,raw:composite.value.raw||(['timed','limited'].includes(mode)?props.field.key==='SMS_MAX_PRICE'?'0.1':'60':'')});}
function set(next:ConfigValue){props.owner.setField(props.field.key,next);if(props.field.key==='CODEX_OAUTH_DRIVER'&&props.owner.field('ACCOUNT_CODEX_DRIVER'))props.owner.setField('ACCOUNT_CODEX_DRIVER',next);}
function input(event:Event){const element=event.target as HTMLInputElement;const type=props.field.type;
 if(type==='bool')set(element.checked);
 else if(type==='list_str_multiline'){const lines=element.value.split(countryList.value?/[,\n\s]+/:/\n/).map(line=>line.trim()).filter(Boolean);set(countryList.value?[...new Set(lines.map(line=>line.toUpperCase()))]:lines);}
 else if(type==='int'||type==='float')set(props.field.group==='并发控制'?element.value:element.value===''?null:Number(element.value));
 else set(element.value);
}
function normalizeText(event:Event){if(props.field.type!=='str'||props.field.secret)return;const text=(event.target as HTMLInputElement).value.trim();set(['','-','—','无','空','none','null','n/a','na','未设置','未配置'].includes(text.toLowerCase())?'':text);}
function setList(values:string[]){set(['EMAIL_SOURCE','ROXY_RANDOM_OS_CHOICES'].includes(props.field.key)?values.join(','):values);}
const status=computed(()=>props.owner.isDirty(props.field.key)?props.field.secret&&props.owner.secretDraft(props.field.key).mode==='clear'?'待清除':'待保存':props.field.invalid_env?'配置值无效，未生效':props.field.secret?props.field.configured?'密钥已配置':'未配置':props.field.restart?'已配置 · 需重启':'');
const accountCodex=computed(()=>props.field.key==='ACCOUNT_CODEX_DRIVER');
const quotaKeys=['EXTRACT_LINK_HUANGUANG_CDK','EXTRACT_LINK_HUANGUANG_PAYMENT_CDK','EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY','EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY'];
</script>
<template>
 <div class="config-vue-field" :data-config-setting="field.key" :class="{'is-invalid':error, 'is-dirty':owner.isDirty(field.key)}">
  <div class="config-vue-field-copy">
   <div class="config-vue-field-name">
    <label :for="id" :title="field.key">{{ field.label || field.key }}</label>
    <span v-if="status" class="config-vue-field-status" role="status">{{ status }}</span>
   </div>
   <p v-if="field.help" :id="`${id}-help`" class="hint">{{ field.help }}</p>
   <code v-if="field.label && field.label !== field.key">{{ field.key }}</code>
  </div>
  <div class="config-vue-field-control">
   <p v-if="legacy">兼容保留</p>
   <p v-else-if="accountCodex">{{ schemaOptions(owner.field('CODEX_OAUTH_DRIVER')).find(item=>item.value===owner.readField('CODEX_OAUTH_DRIVER'))?.label || owner.readField('CODEX_OAUTH_DRIVER') }} · 由注册主链路统一维护</p>
   <fieldset v-else :disabled="readonly" class="config-vue-control-group">
    <ConfigSub2ApiGroups v-if="field.key==='SUB2API_MONITOR_GROUP_IDS'&&actions" :id="id" :label="field.label" :value="String(value??'')" :actions="actions" @change="set" />
    <div v-else-if="['PROXY_POOL_WAIT_TIMEOUT','SMS_MAX_PRICE'].includes(field.key)" class="config-vue-composite">
     <select :id="id" :data-key="field.key" :value="composite.mode" :aria-label="field.key==='SMS_MAX_PRICE'?'价格上限模式':'领取等待模式'" :aria-invalid="!!error" @change="setCompositeMode(($event.target as HTMLSelectElement).value)">
      <template v-if="field.key==='PROXY_POOL_WAIT_TIMEOUT'"><option value="continuous">持续等待</option><option value="timed">限时等待</option></template><template v-else><option value="unlimited">不设上限</option><option value="limited">设上限</option></template>
     </select>
     <input v-if="compositeActive" type="number" :value="composite.raw" :min="field.key==='SMS_MAX_PRICE'?0:1" :step="field.key==='SMS_MAX_PRICE'?'0.001':'1'" :aria-label="field.key==='SMS_MAX_PRICE'?'短信价格上限':'限时等待秒数'" :aria-invalid="!!error" @input="owner.setComposite(field.key,{mode:composite.mode,raw:($event.target as HTMLInputElement).value})">
    </div>
    <ConfigChoicePicker v-else-if="isCountry||multi" :id="id" :data-key="field.key" :label="field.label" :country="isCountry" :values="list" :options="options" :empty-label="field.key==='PLAN_CHECK_COUNTRIES'?'沿用账号注册国家':field.key==='PROXY_POOL_COUNTRIES'?'未选择额外预热国家':'未选择'" @change="setList" />
    <select v-else-if="hasSelect" :id="id" :data-key="field.key" :value="selectValue" :aria-label="field.label" :aria-invalid="!!error" :aria-describedby="`${id}-help ${id}-error`" :disabled="options.length===1||options.every(item=>item.disabled)" @change="set(($event.target as HTMLSelectElement).value)"><option v-for="option in options" :key="option.value" :value="option.value" :disabled="option.disabled" :title="option.reason">{{ option.label }}{{ option.disabled&&option.reason?`（${option.reason}）`:'' }}</option></select>
    <textarea v-else-if="field.type==='list_str_multiline'" :id="id" :data-key="field.key" :value="list.join('\n')" :aria-label="field.label" :aria-invalid="!!error" :aria-describedby="`${id}-help ${id}-error`" :placeholder="field.secret?'留空保留已有值':'每行一条，可留空'" @input="input" />
    <label v-else-if="field.type==='bool'" class="config-vue-switch">
     <input :id="id" :data-key="field.key" type="checkbox" role="switch" :checked="!!value" :aria-label="field.label" :aria-invalid="!!error" :aria-describedby="`${id}-help ${id}-error`" @input="input">
     <span aria-hidden="true">{{ value ? '已开启' : '已关闭' }}</span>
    </label>
    <input v-else :id="id" :data-key="field.key" :type="['int','float'].includes(field.type)?'number':field.secret?'password':'text'" :value="value??''" :min="field.range?.min??field.min" :max="field.range?.max??field.max" :step="field.type==='int'?'1':field.type==='float'?'0.1':undefined" :placeholder="field.secret?'留空保留已有值':'可留空'" autocomplete="off" :aria-label="field.label" :aria-invalid="!!error" :aria-describedby="`${id}-help ${id}-error`" @input="input" @change="normalizeText">
    <button v-if="field.secret" type="button" :aria-label="`明确清除${field.label}`" @click="owner.clearSecret(field.key)">清除</button>
   </fieldset>
   <p v-if="accountCodex" class="hint">注册和账号补全共用同一套 Codex OAuth 执行方式，请到注册主链路修改。</p>
   <p v-if="field.reason" class="hint" role="status">{{ field.reason }}</p>
   <p v-if="error" :id="`${id}-error`" class="config-vue-error" role="alert">{{ error }}</p>
   <ConfigFieldActions v-if="actions&&quotaKeys.includes(field.key)" :actions="actions" :field-key="field.key" />
   <button v-if="actions&&field.group==='并发控制'&&field.key!=='GLOBAL_TASK_WORKERS'" type="button" @click="actions.locateConcurrencyTasks(field.key)">定位任务</button>
  </div>
 </div>
</template>
