<script setup lang="ts">
import {ref} from 'vue';
import type {LocalImportSource} from './contracts';
import {importFormats,type useLocalImport} from './useLocalImport';
import {useNativeDialog} from './useNativeDialog';
import EmailReceipt from './EmailReceipt.vue';
const props=defineProps<{owner:ReturnType<typeof useLocalImport>;active:boolean}>(),state=props.owner.state;
const dialog=ref<HTMLDialogElement>();useNativeDialog(dialog,()=>state.open,()=>props.active);
</script>
<template>
 <dialog ref="dialog" class="em-dialog" data-email-local-import aria-labelledby="emailLocalImportTitle" :aria-busy="state.busy||state.loading" @cancel.prevent="owner.close()" @click="($event.target===dialog)&&owner.close()">
  <div class="em-dialog-head"><div><h3 id="emailLocalImportTitle">导入邮箱资源</h3><p>手动补充本地库存；Outlook 和通用 API 保留原格式，Butler 类型每行粘贴一个完整 iCloud HME 地址。</p></div><button class="em-button" aria-label="关闭邮箱导入" @click="owner.close()">关闭</button></div>
  <div class="em-dialog-body"><EmailReceipt :receipt="state.receipt"/><p v-if="state.error" class="em-error" role="alert">{{ state.error }}</p>
   <label class="em-field">导入类型<select aria-label="导入类型" :value="state.source" :disabled="state.busy" @change="owner.update({source:($event.target as HTMLSelectElement).value as LocalImportSource})"><option v-for="(format,source) in importFormats" :key="source" :value="source">{{ format.label }}</option></select></label>
   <p class="em-help">注册任务只领取本地可用库存；Butler 导入会交接原地址，不自动生成邮箱。</p>
   <label class="em-field">邮箱资源<textarea aria-label="邮箱资源" :value="state.text" :placeholder="importFormats[state.source].placeholder" :disabled="state.busy" @input="owner.update({text:($event.target as HTMLTextAreaElement).value})"/></label><p class="em-help">{{ importFormats[state.source].hint }}</p>
   <label v-if="state.source==='generic_api'" class="em-field">批次有效期（可选）<input aria-label="批次有效期" type="text" :value="state.expiresAt" :disabled="state.busy" placeholder="2026-12-01T12:00:00+08:00" @input="owner.update({expiresAt:($event.target as HTMLInputElement).value})"><small>只补充未在第三字段填写有效期的通用 API 邮箱；留空保留旧两段格式，不会推算有效期。</small></label>
   <section v-if="state.preview" class="em-preview" aria-label="导入前检查"><strong>导入前检查</strong><div class="em-stats"><div v-for="item in [['输入行数',state.preview.total_lines],['可解析',state.preview.valid],['可新增',state.preview.new],['已存在',state.preview.existing],['输入重复',state.preview.duplicate_in_input],['无效行',state.preview.invalid]]" :key="String(item[0])"><strong>{{ item[1]||0 }}</strong><span>{{ item[0] }}</span></div></div><p v-if="state.preview.extra_fields">检测到 {{ state.preview.extra_fields }} 个多余字段，导入时会忽略。</p><details v-if="state.preview.invalid_rows?.length"><summary>无效行详情</summary><p v-for="row in state.preview.invalid_rows" :key="row.line">第 {{ row.line }} 行：{{ row.reason }}</p></details></section>
  </div>
  <div class="em-dialog-foot"><button class="em-button" @click="owner.close()">取消</button><button class="em-button" :disabled="state.loading||state.busy" @click="owner.preview()">{{ state.loading?'解析中…':'解析预览' }}</button><button class="em-button em-primary" data-local-submit :disabled="state.busy||state.loading||!state.text.trim()||!!state.preview&&!state.preview.new" @click="owner.submit()">{{ state.busy?'正在导入…':'导入到邮箱池' }}</button></div>
 </dialog>
</template>
