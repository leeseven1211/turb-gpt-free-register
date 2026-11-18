import {computed, getCurrentScope, onScopeDispose, reactive, readonly, ref, shallowRef} from 'vue';
import {ConfigApiError, sanitizeConfigFields} from '../../api/config';
import {normalizeConfigReceipt, validateConfigUpdates} from './configState';
import type {
  ConfigCompositeDraft, ConfigDraftDependencies, ConfigDraftOwner, ConfigField, ConfigFieldErrors,
  ConfigSavedEvent, ConfigSaveOutcome, ConfigSaveReceipt, ConfigUpdates, ConfigValue, SecretDraft,
} from './contracts';

interface Entry {value: ConfigValue; generation: number; secret?: SecretDraft; composite?: ConfigCompositeDraft; forced?: boolean}
const clone = <T>(value: T): T => value === undefined ? value : JSON.parse(JSON.stringify(value));
const equal = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right);

/** One owner for every configuration menu and action. No draft is persisted in browser storage. */
export function createConfigDraft(deps: ConfigDraftDependencies): ConfigDraftOwner {
  const fields = shallowRef<readonly ConfigField[]>(sanitizeConfigFields(deps.initialFields || []));
  const entries = reactive<Record<string, Entry>>({});
  const errors = reactive<ConfigFieldErrors>({});
  const loading = ref(false), saving = ref(false), error = ref(''), refreshError = ref('');
  const receipt = ref<ConfigSaveReceipt | null>(null);
  const navigationTarget = ref<{key: string; generation: number} | null>(null);
  const generations = new Map<string, number>();
  const listeners = new Set<(event: ConfigSavedEvent) => void>();
  const activeReads = new Set<AbortController>();
  let disposed = false, readGeneration = 0, navigationGeneration = 0;
  let initialPromise: Promise<void> | null = null;
  let submittedKeys = new Set<string>();
  const index = computed(() => new Map(fields.value.map(field => [field.key, field])));
  const dirtyKeys = computed(() => Object.keys(entries));
  const dirtyCount = computed(() => dirtyKeys.value.length);
  const field = (key: string) => index.value.get(key);
  const nextGeneration = (key: string) => {
    const generation = (generations.get(key) || 0) + 1;
    generations.set(key, generation);
    return generation;
  };
  function readField(key: string, source: 'effective' | 'saved' = 'effective') {
    const value = source === 'effective' && entries[key] ? entries[key]!.value : field(key)?.value;
    return clone(value);
  }
  function requireField(key: string): ConfigField {
    const found = field(key);
    if (!found) throw new Error(`未知配置字段：${key}`);
    return found;
  }
  function secretDraft(key: string): SecretDraft {return clone(entries[key]?.secret || {mode: 'retain'});}
  function setSecret(key: string, draft: SecretDraft) {
    if (disposed) return;
    const schema = requireField(key);
    if (!schema.secret) throw new Error(`字段不是密钥：${key}`);
    const generation = nextGeneration(key);
    if (schema.group !== '并发控制') Object.keys(errors).forEach(errorKey => delete errors[errorKey]);
    delete errors[key];
    if (draft.mode === 'retain') {delete entries[key]; return;}
    const value = draft.mode === 'clear' ? schema.type === 'list_str_multiline' ? [] : '' : clone(draft.value);
    entries[key] = {value, generation, secret: clone(draft)};
  }
  function setField(key: string, value: ConfigValue, options: {force?: boolean} = {}) {
    if (disposed) return;
    const schema = requireField(key);
    if (schema.group !== '并发控制') Object.keys(errors).forEach(errorKey => delete errors[errorKey]);
    if (schema.secret) {
      const empty = value === null || typeof value === 'string' && value.trim() === '' || Array.isArray(value) && !value.length;
      setSecret(key, empty ? {mode: 'retain'} : {mode: 'set', value: clone(value) as string | string[]});
      return;
    }
    const generation = nextGeneration(key);
    delete errors[key];
    const forced = !!options.force || !!entries[key]?.forced;
    if (!forced && !submittedKeys.has(key) && equal(value, schema.value)) {delete entries[key]; return;}
    entries[key] = {value: clone(value), generation, forced};
  }
  function setComposite(key: string, draft: ConfigCompositeDraft) {
    if (disposed) return;
    requireField(key);
    let value: ConfigValue;
    if (key === 'PROXY_POOL_WAIT_TIMEOUT') {
      value = draft.mode === 'timed' ? draft.raw.trim() === '' ? null : Number(draft.raw) : 0;
    } else if (key === 'SMS_MAX_PRICE') {
      value = draft.mode === 'limited' ? draft.raw : '';
    } else {
      value = draft.raw;
    }
    const generation = nextGeneration(key);
    if (requireField(key).group !== '并发控制') Object.keys(errors).forEach(errorKey => delete errors[errorKey]);
    delete errors[key];
    entries[key] = {value, generation, composite: clone(draft)};
  }
  function reset(keys: readonly string[] = dirtyKeys.value) {
    for (const key of keys) {
      nextGeneration(key);
      delete entries[key]; delete errors[key];
    }
    error.value = '';
  }
  function navigateField(key: string) {
    navigationTarget.value = {key, generation: ++navigationGeneration};
    deps.onNavigateField?.(key);
  }
  async function refresh(options: {force?: boolean} = {}) {
    if (disposed) return;
    const generation = ++readGeneration;
    const controller = new AbortController();
    activeReads.add(controller); loading.value = true;
    try {
      const updated = await deps.api.getSchema({...options, signal: controller.signal});
      if (disposed || generation !== readGeneration || controller.signal.aborted) return;
      fields.value = sanitizeConfigFields(updated);
      refreshError.value = '';
    } catch (failure) {
      if (!disposed && generation === readGeneration && !controller.signal.aborted) {
        refreshError.value = '配置读取失败，当前草稿已保留';
        throw failure;
      }
    } finally {
      activeReads.delete(controller);
      if (generation === readGeneration) loading.value = false;
    }
  }
  async function initialize() {
    if (disposed || fields.value.length) return;
    if (!initialPromise) initialPromise = refresh().finally(() => {initialPromise = null;});
    return initialPromise;
  }
  function validate(updates: ConfigUpdates): ConfigFieldErrors {
    const found = {...validateConfigUpdates(updates, fields.value), ...deps.validate?.(updates, fields.value)};
    for (const key of Object.keys(updates)) {
      const composite = entries[key]?.composite;
      if (!composite) continue;
      if (key === 'PROXY_POOL_WAIT_TIMEOUT' && composite.mode === 'timed'
        && (!composite.raw.trim() || !Number.isFinite(Number(composite.raw)) || Number(composite.raw) <= 0)) {
        found[key] = '请填写限时等待秒数，或切换为持续等待';
      }
      if (key === 'SMS_MAX_PRICE' && composite.mode === 'limited'
        && (!composite.raw.trim() || !Number.isFinite(Number(composite.raw)) || Number(composite.raw) < 0)) {
        found[key] = '请填写短信价格上限，或切换为不设上限';
      }
    }
    return found;
  }
  function showErrors(found: ConfigFieldErrors) {
    Object.assign(errors, found);
    const first = Object.keys(found)[0];
    if (first) navigateField(first);
  }
  async function save(keys: readonly string[]): Promise<ConfigSaveOutcome> {
    if (disposed) return {status: 'disposed'};
    if (saving.value) return {status: 'busy'};
    const snapshot = new Map<string, Entry>();
    const updates: ConfigUpdates = {};
    for (const key of keys) {
      if (!entries[key]) continue;
      snapshot.set(key, clone(entries[key]!));
      updates[key] = clone(entries[key]!.value);
    }
    if (!snapshot.size) return {status: 'noop'};
    const invalid = validate(updates);
    if (Object.keys(invalid).length) {showErrors(invalid); return {status: 'validation-error', fields: invalid};}
    saving.value = true; error.value = ''; submittedKeys = new Set(snapshot.keys());
    try {
      const response = await deps.api.save(updates);
      if (disposed) return {status: 'disposed'};
      // Suppress any older GET before applying the authoritative save receipt.
      readGeneration++;
      const saved = normalizeConfigReceipt(response, [...snapshot.keys()]);
      const savedSet = new Set(saved.savedKeys);
      fields.value = fields.value.map(schema => {
        const entry = snapshot.get(schema.key);
        if (!entry || !savedSet.has(schema.key)) return schema;
        const next = schema.secret
          ? {...schema, value: '' as ConfigValue, configured: entry.secret?.mode !== 'clear',
            configured_value: '' as ConfigValue, published_effective_value: '' as ConfigValue}
          : {...schema, value: clone(entry.value), configured_value: clone(entry.value)};
        return next;
      });
      for (const [key, entry] of snapshot) {
        if (!savedSet.has(key)) continue;
        if (generations.get(key) === entry.generation) {delete entries[key]; delete errors[key];}
      }
      deps.api.invalidate();
      receipt.value = saved;
      try {await refresh({force: true});} catch {saved.refreshFailed = true; receipt.value = {...saved};}
      if (!disposed) {
        const event = {keys: saved.savedKeys, receipt: clone(saved), fields: clone(fields.value)};
        for (const callback of listeners) {
          try {callback(event);} catch {/* A consumer cannot turn committed persistence into a failed save. */}
        }
      }
      return {status: 'saved', receipt: clone(saved)};
    } catch (failure) {
      if (disposed) return {status: 'disposed'};
      const found = failure instanceof ConfigApiError ? failure.fields : {};
      if (Object.keys(found).length) {
        const current = Object.fromEntries(Object.entries(found).filter(([key]) => {
          const submitted = snapshot.get(key);
          return !submitted || generations.get(key) === submitted.generation;
        }));
        showErrors(current);
        return {status: 'validation-error', fields: clone(current)};
      }
      error.value = failure instanceof ConfigApiError ? failure.message : '配置保存失败，草稿已保留';
      return {status: 'error'};
    } finally {
      saving.value = false; submittedKeys = new Set();
    }
  }
  async function saveSubset(keysOrUpdates: readonly string[] | ConfigUpdates): Promise<ConfigSaveOutcome> {
    if (disposed) return {status: 'disposed'};
    if (saving.value) return {status: 'busy'};
    if (Array.isArray(keysOrUpdates)) return save(keysOrUpdates);
    for (const [key, value] of Object.entries(keysOrUpdates)) setField(key, value, {force: true});
    return save(Object.keys(keysOrUpdates));
  }
  function dispose() {
    disposed = true; readGeneration++;
    for (const read of activeReads) read.abort();
    activeReads.clear(); listeners.clear();
    for (const key of Object.keys(entries)) delete entries[key];
    loading.value = false;
  }
  return {
    fields, dirtyKeys, dirtyCount, fieldErrors: readonly(errors), loading, saving, error, refreshError, receipt,
    navigationTarget, field, readField, isDirty: key => Boolean(entries[key]), secretDraft,
    readComposite: key => clone(entries[key]?.composite), setField, setSecret,
    clearSecret: key => setSecret(key, {mode: 'clear'}), setComposite, reset, initialize, refresh,
    saveAll: () => save(dirtyKeys.value), saveSubset, navigateField,
    subscribeSaved(callback) {listeners.add(callback); return () => listeners.delete(callback);},
    dispose,
  };
}

export function useConfigDraft(deps: ConfigDraftDependencies): ConfigDraftOwner {
  const owner = createConfigDraft(deps);
  if (getCurrentScope()) onScopeDispose(owner.dispose);
  return owner;
}
