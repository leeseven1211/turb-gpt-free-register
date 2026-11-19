import type {ConfigField, ConfigFieldErrors, ConfigSaveReceipt, ConfigSaveResponse, ConfigUpdates} from './contracts';

export function normalizeConfigReceipt(response: ConfigSaveResponse, submitted: readonly string[]): ConfigSaveReceipt {
  const ignored = response.ignored || [];
  const saved = response.updated ?? submitted.filter(key => !ignored.includes(key));
  return {
    savedKeys: [...saved],
    ignoredKeys: [...ignored],
    persistedDbRevision: response.persisted_db_revision ?? null,
    localSnapshotRevision: response.local_snapshot_revision ?? response.config_revision ?? null,
    webReloaded: response.web_reloaded ?? response.reloaded ?? null,
    workerApplication: response.worker_application
      ? {...response.worker_application} : {state: 'unknown', applied_db_revision: null},
    restartRequired: [...(response.restart_required || [])],
    refreshFailed: false,
  };
}

/** Match the existing concurrency form's positive integer boundary. */
export function validateConfigUpdates(updates: ConfigUpdates, fields: readonly ConfigField[]): ConfigFieldErrors {
  const errors: ConfigFieldErrors = {};
  const schema = new Map(fields.map(field => [field.key, field]));
  for (const [key, value] of Object.entries(updates)) {
    const field = schema.get(key);
    if (field?.group === '并发控制' && field.type === 'int' && key !== 'CONCURRENCY_POLICY_REVISION') {
      const text = String(value ?? '').trim();
      if (!/^\d+$/.test(text) || !/[1-9]/.test(text)) {
        errors[key] = '请填写不小于 1 的整数；暂停请使用任务暂停或取消。';
      }
    }
  }
  return errors;
}
