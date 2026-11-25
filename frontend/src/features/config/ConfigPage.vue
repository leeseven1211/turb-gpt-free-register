<script setup lang="ts">
import {computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch} from 'vue';
import type {ConfigDraftOwner, ConfigField as Field} from './contracts';
import type {ConfigActions} from './configActions';
import ConfigNavigation from './ConfigNavigation.vue';
import ConfigField from './ConfigField.vue';
import ConfigChoicePicker from './ConfigChoicePicker.vue';
import ConfigActionTools from './ConfigActionTools.vue';
import {
  destination,
  domainsFor,
  extractProviders,
  fieldDestination,
  findDestination,
  menus,
  menuStorageKey,
  orderedMenus,
  searchText,
  settingGroups,
  subsectionsFor,
  visibleFields,
  type Destination,
} from './navigation';
import './config.css';

const props = withDefaults(defineProps<{owner: ConfigDraftOwner; actions: ConfigActions; active?: boolean}>(), {
  active: true,
});

const query = ref('');
const current = reactive<Destination>({menu: '', domain: '', section: ''});
const root = ref<HTMLElement>();
const rememberedDomains: Record<string, string> = {};
const rememberedSections: Record<string, string> = {};

const domainNames = computed(() => domainsFor(current.menu, props.owner.fields.value));
const sections = computed(() => subsectionsFor(current.domain, props.owner.fields.value));
const fields = computed(() => visibleFields(props.owner, current, !!query.value.trim()));
const groups = computed(() => settingGroups(current.domain, fields.value));

const proxyPrimaryKeys = new Set([
  'PROXY_POOL_SOURCE',
  'PROXY_POOL_DEFAULT_COUNTRY',
  'PROXY_POOL',
  ...['PROXY_1024_', 'PROXY_711_'].flatMap(prefix =>
    ['API_URL', 'PROTOCOL', 'SESSION_MINUTES'].map(key => `${prefix}${key}`),
  ),
]);
const proxyPrimary = computed(() => fields.value.filter(field => proxyPrimaryKeys.has(field.key)));
const proxyAdvanced = computed(() => fields.value.filter(field => !proxyPrimaryKeys.has(field.key)));

/** 判断字段是否归类为功能开关，兼容保留项与只读派生字段按参数项展示。 */
function isSwitchField(field: Field, isLegacy = false): boolean {
  return field.type === 'bool' && !isLegacy && field.key !== 'ACCOUNT_CODEX_DRIVER';
}

/** 按开关与参数两类拆分字段列表，保持各自原有的相对顺序。 */
function partitionFields(items: Field[], isLegacy = false) {
  const switches: Field[] = [];
  const inputs: Field[] = [];
  for (const item of items) {
    if (isSwitchField(item, isLegacy)) switches.push(item);
    else inputs.push(item);
  }
  return {switches, inputs};
}

const proxyPrimaryParts = computed(() => partitionFields(proxyPrimary.value));
const proxyAdvancedParts = computed(() => partitionFields(proxyAdvanced.value));
const groupSections = computed(() => {
  const legacy = current.domain === '代理与网络' && current.section === '高级兼容';
  return groups.value.map(group => ({
    title: group.title,
    legacy,
    ...partitionFields(group.fields, legacy),
  }));
});

const providers = computed(() => extractProviders(props.owner.fields.value));
const selectedProviders = computed(() =>
  providers.value
    .filter(provider => props.owner.readField(provider.enabledKey) === true)
    .map(provider => provider.value),
);
const errors = computed(() => Object.entries(props.owner.fieldErrors));

const tool = computed<'roxy' | 'proxy' | 'butler' | 'sentinel' | 'sub2api' | 'c2a' | 'concurrency' | null>(() => {
  if (current.domain === 'RoxyBrowser') return 'roxy';
  if (current.domain === '代理与网络' && current.section === '代理来源' && props.owner.readField('PROXY_POOL_SOURCE') !== 'manual') {
    return 'proxy';
  }
  if (current.domain === '邮箱 / OTP' && current.section === 'Email Butler') return 'butler';
  if (current.domain === '通用配置') return 'sentinel';
  if (current.domain === 'Codex' && current.section === 'sub2api') return 'sub2api';
  if (current.domain === 'C2A') return 'c2a';
  if (current.domain === '并发控制') return 'concurrency';
  return null;
});

function remember() {
  try {
    localStorage.setItem(menuStorageKey, current.domain || current.menu);
  } catch {
    /* 本地仅记忆导航分组，不持久化任何配置值。 */
  }
}

function resetViewport() {
  void nextTick(() => {
    const content = root.value?.querySelector<HTMLElement>('.config-vue-content');
    const scrolled = !!(
      content?.scrollTop ||
      content?.scrollLeft ||
      window.scrollY ||
      window.scrollX ||
      document.documentElement.scrollTop
    );
    if (content) {
      content.scrollTop = 0;
      content.scrollLeft = 0;
    }
    if (scrolled) window.scrollTo({top: 0, left: 0, behavior: 'auto'});
  });
}

function selectMenu(name: string) {
  const next = destination(name, props.owner.fields.value);
  if (menus[name] && rememberedDomains[next.menu]) next.domain = rememberedDomains[next.menu]!;
  next.section = rememberedSections[next.domain] || subsectionsFor(next.domain, props.owner.fields.value)[0] || '';
  Object.assign(current, next);
  remember();
  resetViewport();
}

function selectDomain(name: string) {
  current.domain = name;
  rememberedDomains[current.menu] = name;
  current.section = rememberedSections[name] || subsectionsFor(name, props.owner.fields.value)[0] || '';
  remember();
  resetViewport();
}

function selectSection(name: string) {
  current.section = name;
  rememberedSections[current.domain] = name;
  resetViewport();
}

function search(value: string) {
  query.value = value;
  const found = findDestination(value, props.owner.fields.value, current.menu);
  if (!found || (current.menu === found.menu && current.domain === found.domain && current.section === found.section)) {
    return;
  }
  Object.assign(current, found);
  resetViewport();
}

function selectProviders(values: string[]) {
  for (const provider of providers.value) {
    props.owner.setField(provider.enabledKey, values.includes(provider.value));
  }
}

async function focusField(key: string) {
  const field = props.owner.field(key);
  if (!field) return;
  if (query.value.trim() && !searchText(field, props.owner.fields.value).includes(query.value.trim().toLowerCase())) {
    query.value = '';
  }
  Object.assign(current, fieldDestination(field, props.owner.fields.value));
  remember();
  await nextTick();
  const wrapper = Array.from(root.value?.querySelectorAll<HTMLElement>('[data-config-setting]') || []).find(
    element => element.dataset.configSetting === key,
  );
  wrapper?.querySelectorAll<HTMLDetailsElement>('details').forEach(element => {
    element.open = true;
  });
  const details = wrapper?.closest('details');
  if (details) details.open = true;
  const element = wrapper?.querySelector<HTMLElement>('input:not([type=hidden]),select,textarea,summary,button');
  element?.focus();
  element?.scrollIntoView?.({block: 'nearest'});
}

function discard() {
  if (props.owner.dirtyCount.value && window.confirm('确定撤销全部未保存的配置修改？')) {
    props.owner.reset();
  }
}

function protectDraft(event: BeforeUnloadEvent) {
  if (props.owner.dirtyCount.value) {
    event.preventDefault();
    event.returnValue = '';
  }
}

async function save() {
  const result = await props.owner.saveAll();
  if (result.status === 'validation-error') {
    const key = Object.keys(result.fields || {})[0];
    if (key) props.owner.navigateField(key);
  }
}

watch(() => props.owner.navigationTarget.value, target => {
  if (target) void focusField(target.key);
});

watch(() => props.active, active => props.actions.setPageActive(active), {immediate: true});

onBeforeUnmount(() => {
  props.actions.setPageActive(false);
  window.removeEventListener('beforeunload', protectDraft);
});

watch(
  () => props.owner.fields.value,
  () => {
    const menuList = orderedMenus(props.owner.fields.value);
    if (!menuList.length) return;
    if (!current.menu) {
      let saved = '';
      try {
        saved = localStorage.getItem(menuStorageKey) || '';
      } catch {
        /* 忽略本地存储读取异常 */
      }
      Object.assign(current, destination(saved || menuList[0]!, props.owner.fields.value));
    }
    if (!menuList.includes(current.menu)) Object.assign(current, destination(menuList[0]!, props.owner.fields.value));
    if (!domainNames.value.includes(current.domain)) current.domain = domainNames.value[0] || current.menu;
    if (!sections.value.includes(current.section)) current.section = sections.value[0] || '';
  },
  {immediate: true},
);

onMounted(() => {
  window.addEventListener('beforeunload', protectDraft);
  void props.owner.initialize().catch(() => {
    /* 读取失败与重试操作由 owner 暴露。 */
  });
  void props.actions.loadExtractTypes();
});

defineExpose({open: selectMenu, focusField});

const poolRules = [
  ['注册与账号认证', '注册主链路的注册国家；账号认证沿用账号历史国家', '独占租约'],
  ['查询套餐', '业务国家顺序（逐国申请）', '按池用途策略复用'],
  ['查活', '账号历史国家；缺失时使用池默认国家', '认证链路保持同一线路'],
  ['刷新 AT', '优先使用独立的 AT 刷新国家；留空时跟随账号注册国家', '单次登录保持同线；网络故障换线重新登录'],
  ['补密码 / 2FA / 换绑 / Codex', '账号历史国家；缺失时使用池默认国家', '独占租约'],
];
</script>

<template>
  <div ref="root" class="config-vue-page">
    <p v-if="owner.loading.value" class="config-vue-banner" role="status">正在读取配置…</p>
    <p v-if="owner.error.value" class="config-vue-banner config-vue-error" role="alert">{{ owner.error.value }}</p>
    <p v-if="owner.refreshError.value" class="config-vue-banner config-vue-error" role="status">
      <span>{{ owner.refreshError.value }}</span>
      <button type="button" @click="owner.refresh({force: true})">重新读取配置</button>
    </p>
    <div v-if="errors.length" class="config-vue-error-summary" role="alert" tabindex="-1">
      <strong>请检查 {{ errors.length }} 项配置，草稿已保留</strong>
      <ul>
        <li v-for="[key, error] in errors" :key="key">
          <button type="button" @click="owner.navigateField(key)">{{ owner.field(key)?.label || key }}：{{ error }}</button>
        </li>
      </ul>
    </div>

    <div class="config-vue-layout">
      <ConfigNavigation :owner="owner" :active="current.menu" :query="query" @select="selectMenu" @search="search" />

      <div v-if="current.domain" class="config-vue-content">
        <header class="config-vue-content-header">
          <h2>{{ domainNames.length > 1 ? current.menu : (current.domain === '注册与账号' ? '查询套餐' : current.domain) }}</h2>
          <div
            v-show="domainNames.length > 1"
            class="config-vue-tabs config-vue-domains"
            role="group"
            :aria-label="`${current.menu}配置领域`"
          >
            <button
              v-for="domain in domainNames"
              :key="domain"
              type="button"
              :data-config-domain-v2="domain"
              :aria-pressed="current.domain === domain"
              @click="selectDomain(domain)"
            >
              {{ domain === '注册与账号' ? '查询套餐' : domain }}
            </button>
          </div>
          <div
            v-if="sections.length"
            class="config-vue-tabs config-vue-subsections"
            role="group"
            :aria-label="`${current.domain}配置分类`"
          >
            <button
              v-for="section in sections"
              :key="section"
              type="button"
              :data-config-subsection="section"
              :aria-pressed="current.section === section"
              @click="selectSection(section)"
            >
              {{ section }}
            </button>
          </div>
        </header>

        <section class="config-vue-editor" :data-config-section="current.domain">
          <div v-if="current.domain === '代理与网络' && current.section === '任务用池'" class="config-vue-table-card">
            <table class="config-vue-pool-rules">
              <caption>任务用池规则</caption>
              <thead>
                <tr>
                  <th>任务</th>
                  <th>国家需求</th>
                  <th>领取规则</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in poolRules" :key="row[0]">
                  <td v-for="cell in row" :key="cell">{{ cell }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div
            v-if="current.domain === '提链' && current.section === '通用配置'"
            class="config-vue-subblock config-vue-subblock--inputs"
          >
            <div class="config-vue-input-card">
              <div class="config-vue-field">
                <div class="config-vue-field-copy">
                  <div class="config-vue-field-name">
                    <label>启用平台</label>
                  </div>
                  <p class="hint">选择允许在提链工作台中使用的平台；取消选择不会清除该平台的地址或 CDK。</p>
                </div>
                <div class="config-vue-field-control">
                  <ConfigChoicePicker
                    label="启用平台"
                    :values="selectedProviders"
                    :options="providers"
                    @change="selectProviders"
                  />
                </div>
              </div>
            </div>
          </div>

          <template v-if="current.domain === '代理与网络' && current.section === '代理来源'">
            <div
              v-if="proxyPrimaryParts.switches.length"
              class="config-vue-subblock config-vue-subblock--switches"
            >
              <div class="config-vue-switch-grid">
                <ConfigField
                  v-for="field in proxyPrimaryParts.switches"
                  :key="field.key"
                  :owner="owner"
                  :field="field"
                  :actions="actions"
                />
              </div>
            </div>

            <div
              v-if="proxyPrimaryParts.inputs.length"
              class="config-vue-subblock config-vue-subblock--inputs"
            >
              <div class="config-vue-input-card">
                <ConfigField
                  v-for="field in proxyPrimaryParts.inputs"
                  :key="field.key"
                  :owner="owner"
                  :field="field"
                  :actions="actions"
                />
              </div>
            </div>

            <details v-if="proxyAdvanced.length" class="config-vue-source-advanced" :open="!!query.trim()">
              <summary>高级提取与检测参数</summary>
              <div class="config-vue-advanced-body">
                <div
                  v-if="proxyAdvancedParts.switches.length"
                  class="config-vue-subblock config-vue-subblock--switches"
                >
                  <div class="config-vue-switch-grid">
                    <ConfigField
                      v-for="field in proxyAdvancedParts.switches"
                      :key="field.key"
                      :owner="owner"
                      :field="field"
                      :actions="actions"
                    />
                  </div>
                </div>

                <div
                  v-if="proxyAdvancedParts.inputs.length"
                  class="config-vue-subblock config-vue-subblock--inputs"
                >
                  <div class="config-vue-input-card">
                    <ConfigField
                      v-for="field in proxyAdvancedParts.inputs"
                      :key="field.key"
                      :owner="owner"
                      :field="field"
                      :actions="actions"
                    />
                  </div>
                </div>
              </div>
            </details>
          </template>

          <template v-else>
            <div v-for="group in groupSections" :key="group.title" class="config-vue-setting-group">
              <h3 v-if="group.title">{{ group.title }}</h3>

              <div v-if="group.switches.length" class="config-vue-subblock config-vue-subblock--switches">
                <div class="config-vue-switch-grid">
                  <ConfigField
                    v-for="field in group.switches"
                    :key="field.key"
                    :owner="owner"
                    :field="field"
                    :actions="actions"
                    :legacy="group.legacy"
                  />
                </div>
              </div>

              <div v-if="group.inputs.length" class="config-vue-subblock config-vue-subblock--inputs">
                <div class="config-vue-input-card">
                  <ConfigField
                    v-for="field in group.inputs"
                    :key="field.key"
                    :owner="owner"
                    :field="field"
                    :actions="actions"
                    :legacy="group.legacy"
                  />
                </div>
              </div>
            </div>
          </template>

          <p v-if="current.domain === '邮箱 / OTP' && current.section === 'iCloud 隐藏邮箱'" class="hint config-vue-section-note">
            隐藏邮箱的创建、状态与管理请在邮箱服务（Email Butler）中完成。本页只维护已导入与历史邮箱的固定收件连接。
          </p>
          <p v-if="current.domain === '注册调试'" class="hint config-vue-section-note">
            “调试模式”仍是单个注册批次的现场保留开关，本页只控制失败诊断、保留时长和抓包预算。
          </p>

          <ConfigActionTools v-if="tool" :key="tool" :owner="owner" :actions="actions" :tool="tool" :active="active" />
        </section>
      </div>
    </div>

    <div v-if="owner.dirtyCount.value || owner.receipt.value" class="config-vue-savebar">
      <div class="config-vue-save-state" role="status" aria-live="polite">
        <strong>
          {{
            errors.length
              ? '请检查标记的配置项'
              : owner.error.value
                ? '保存失败，请重试'
                : owner.dirtyCount.value
                  ? `${owner.dirtyCount.value} 项待保存`
                  : '配置已保存'
          }}
        </strong>
        <span v-if="owner.error.value && !errors.length">请检查网络或服务状态后重试</span>
        <span v-if="owner.receipt.value">
          数据库保存{{ owner.receipt.value.persistedDbRevision !== null ? `版本 ${owner.receipt.value.persistedDbRevision}` : '成功' }}
          · Worker
          {{
            owner.receipt.value.workerApplication.state === 'applied'
              ? '已应用'
              : owner.receipt.value.workerApplication.state === 'error'
                ? '应用异常'
                : owner.receipt.value.workerApplication.state === 'pending'
                  ? '等待应用'
                  : '应用状态待确认'
          }}
        </span>
        <span v-if="owner.receipt.value?.restartRequired.length">
          需重启：{{ owner.receipt.value.restartRequired.join('、') }}
        </span>
      </div>
      <div class="config-vue-save-actions">
        <button type="button" :disabled="!owner.dirtyCount.value || owner.saving.value" @click="discard">撤销修改</button>
        <button type="button" class="primary" :disabled="!owner.dirtyCount.value || owner.saving.value" @click="save">
          {{ owner.saving.value ? '正在保存…' : '保存全部配置' }}
        </button>
      </div>
    </div>
  </div>
</template>
