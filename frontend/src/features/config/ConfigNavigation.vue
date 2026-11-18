<script setup lang="ts">
import {computed} from 'vue';
import type {ConfigDraftOwner} from './contracts';
import {orderedMenus, projectedFields, menuFor, navigationCategory, searchText} from './navigation';
const props = defineProps<{owner:ConfigDraftOwner; active:string; query:string}>();
const emit = defineEmits<{select:[name:string]; search:[query:string]}>();
const items = computed(() => orderedMenus(props.owner.fields.value).map(name => {
  const fields=projectedFields(props.owner.fields.value).filter(field=>menuFor(field.group)===name);
  return {name,category:navigationCategory(name),count:fields.length,dirty:fields.filter(field=>props.owner.isDirty(field.key)).length,
    matches:!props.query.trim() || name.toLowerCase().includes(props.query.toLowerCase()) || fields.some(field=>searchText(field,props.owner.fields.value).includes(props.query.trim().toLowerCase()))};
}));
</script>
<template>
  <nav class="config-vue-navigation" aria-label="配置分类">
    <label for="config-vue-search">搜索配置</label>
    <input id="config-vue-search" type="search" :value="query" placeholder="名称、配置键或帮助" @input="emit('search',($event.target as HTMLInputElement).value)">
    <div v-for="category in ['业务流程','资源与服务','系统']" :key="category" class="config-vue-nav-group">
      <p v-if="items.some(item=>item.category===category && item.matches)" class="hint">{{ category }}</p>
      <button v-for="item in items.filter(item=>item.category===category && item.matches)" :key="item.name" type="button" :data-config-nav="item.name" :aria-current="active===item.name?'page':undefined" @click="emit('select',item.name)">
        <span>{{ item.name }}</span><small>{{ item.count }} 项<span v-if="item.dirty"> · {{ item.dirty }} 待保存</span></small>
      </button>
    </div>
    <p v-if="!items.some(item=>item.matches)" role="status">未找到匹配配置</p>
  </nav>
</template>
