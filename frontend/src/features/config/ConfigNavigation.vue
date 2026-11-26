<script setup lang="ts">
import {computed, nextTick, ref, watch} from 'vue';
import type {ConfigDraftOwner} from './contracts';
import {orderedMenus, projectedFields, menuFor, navigationCategory, searchText} from './navigation';

const props = defineProps<{owner: ConfigDraftOwner; active: string; query: string}>();
const emit = defineEmits<{select: [name: string]; search: [query: string]}>();
const expanded = ref(false);
const toggle = ref<HTMLButtonElement>();
const searchQuery = computed(() => props.query.trim().toLowerCase());

const menuList = computed(() => orderedMenus(props.owner.fields.value));

const fieldsByMenu = computed(() => {
  const result = new Map<string, ReturnType<typeof projectedFields>>();
  for (const field of projectedFields(props.owner.fields.value)) {
    const menu = menuFor(field.group);
    const fields = result.get(menu) || [];
    fields.push(field);
    result.set(menu, fields);
  }
  return result;
});

const keyToMenu = computed(() => {
  const map = new Map<string, string>();
  for (const [menu, fields] of fieldsByMenu.value) {
    for (const field of fields) map.set(field.key, menu);
  }
  return map;
});

// 仅遍历实际修改过的字段键汇总各菜单待保存数，避免每次搜索按键扫描全部配置项。
const dirtyCountByMenu = computed(() => {
  const counts = new Map<string, number>();
  for (const key of props.owner.dirtyKeys.value) {
    const menu = keyToMenu.value.get(key);
    if (menu) counts.set(menu, (counts.get(menu) || 0) + 1);
  }
  return counts;
});

const groups = computed(() => {
  const query = searchQuery.value;
  const schemaFields = props.owner.fields.value;
  const items = menuList.value.flatMap(name => {
    const fields = fieldsByMenu.value.get(name) || [];
    if (
      query &&
      !name.toLowerCase().includes(query) &&
      !fields.some(field => searchText(field, schemaFields).includes(query))
    ) {
      return [];
    }
    return [
      {
        name,
        category: navigationCategory(name),
        dirty: dirtyCountByMenu.value.get(name) || 0,
      },
    ];
  });
  return ['业务流程', '资源与服务', '系统']
    .map(name => ({
      name,
      items: items.filter(item => item.category === name),
    }))
    .filter(group => group.items.length);
});

function select(name: string) {
  expanded.value = false;
  emit('select', name);
  void nextTick(() => {
    if (toggle.value?.getClientRects().length) toggle.value.focus({preventScroll: true});
  });
}

watch(searchQuery, query => {
  expanded.value = Boolean(query);
});
</script>

<template>
  <nav class="config-vue-navigation" aria-label="配置分类">
    <div class="config-vue-navigation-head">
      <label for="config-vue-search">搜索配置</label>
      <div class="config-vue-search-box">
        <svg class="config-vue-search-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <circle cx="7" cy="7" r="4.5" stroke="currentColor" stroke-width="1.4" />
          <path d="M10.5 10.5L13.5 13.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
        </svg>
        <input
          id="config-vue-search"
          type="search"
          :value="query"
          placeholder="搜索名称或配置键"
          @input="emit('search', ($event.target as HTMLInputElement).value)"
        />
      </div>
      <button
        ref="toggle"
        type="button"
        class="config-vue-nav-toggle"
        :aria-expanded="expanded"
        aria-controls="config-vue-menu"
        aria-label="切换配置分类"
        @click="expanded = !expanded"
      >
        <span>{{ active || '选择配置分类' }}</span>
        <span class="config-vue-chevron" aria-hidden="true"></span>
      </button>
    </div>

    <div id="config-vue-menu" class="config-vue-menu" :class="{'is-expanded': expanded}">
      <div v-for="group in groups" :key="group.name" class="config-vue-nav-group">
        <p>{{ group.name }}</p>
        <button
          v-for="item in group.items"
          :key="item.name"
          type="button"
          :data-config-nav="item.name"
          :aria-current="active === item.name ? 'page' : undefined"
          @click="select(item.name)"
        >
          <span class="config-vue-nav-label">{{ item.name }}</span>
          <small v-if="item.dirty" class="config-vue-pending">{{ item.dirty }} 待保存</small>
        </button>
      </div>
      <p v-if="searchQuery && !groups.length" class="hint config-vue-no-match" role="status">未找到匹配配置</p>
    </div>
  </nav>
</template>
