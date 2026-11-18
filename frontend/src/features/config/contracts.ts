import type {ComputedRef, DeepReadonly, Ref} from 'vue';

export type ConfigValue = string | number | boolean | null | string[];
export type ConfigUpdates = Record<string, ConfigValue>;
export type ConfigFieldErrors = Record<string, string>;
export type ConfigRevision = string | number | null;
export interface ConfigOption {
  value: string;
  label: string;
  disabled?: boolean;
  reason?: string;
}
export interface ConfigField {
  key: string;
  type: 'str' | 'int' | 'float' | 'bool' | 'list_str_multiline' | (string & {});
  group: string;
  label: string;
  value: ConfigValue;
  help?: string;
  secret?: boolean;
  configured?: boolean;
  default?: ConfigValue;
  options?: ConfigOption[];
  csv_options?: string[];
  country_codes?: string[];
  country_names?: Record<string, string>;
  range?: {min?: number; max?: number};
  min?: number;
  max?: number;
  readonly?: boolean;
  editable?: boolean;
  hidden?: boolean;
  disable_enable?: boolean;
  reason?: string;
  restart?: boolean;
  requires_restart?: boolean;
  hot_edit?: boolean;
  aliases?: Record<string, unknown>;
  source?: string;
  source_key?: string | null;
  published_effective_value?: ConfigValue;
  published_effective_source?: string;
  published_source_key?: string | null;
  published_revision?: ConfigRevision;
  configured_value?: ConfigValue;
  configured_source?: string;
  configured_source_key?: string | null;
  pending_reload?: boolean;
  pending?: boolean;
  invalid_env?: boolean;
  config_revision?: ConfigRevision;
  file?: string | null;
  module?: string | null;
  storage?: string;
  allow_prefix?: string;
}
export type SecretDraft =
  | {mode: 'retain'}
  | {mode: 'set'; value: string | string[]}
  | {mode: 'clear'};
export interface ConfigCompositeDraft {mode: string; raw: string}
export interface WorkerApplication {
  state: 'unknown' | 'pending' | 'applied' | 'error' | (string & {});
  applied_db_revision?: ConfigRevision;
  error_code?: string | null;
}
export interface ConfigSaveResponse {
  ok?: boolean;
  updated?: string[];
  ignored?: string[];
  env_updated?: string[];
  database_updated?: string[];
  reloaded?: boolean;
  reload_modules?: string[];
  restart_required?: string[];
  config_revision?: ConfigRevision;
  persisted_db_revision?: ConfigRevision;
  local_snapshot_revision?: ConfigRevision;
  web_reloaded?: boolean;
  worker_application?: WorkerApplication;
}
export interface ConfigSaveReceipt {
  savedKeys: string[];
  ignoredKeys: string[];
  persistedDbRevision: ConfigRevision;
  localSnapshotRevision: ConfigRevision;
  webReloaded: boolean | null;
  workerApplication: WorkerApplication;
  restartRequired: string[];
  refreshFailed: boolean;
}
export interface ConfigSaveOutcome {
  status: 'saved' | 'noop' | 'busy' | 'validation-error' | 'error' | 'disposed';
  receipt?: ConfigSaveReceipt;
  fields?: ConfigFieldErrors;
}
export interface ConfigSavedEvent {
  keys: readonly string[];
  receipt: ConfigSaveReceipt;
  /** Saved metadata only; secret contents are always empty. */
  fields: readonly ConfigField[];
}
export interface ConfigApi {
  getSchema(options?: {signal?: AbortSignal; force?: boolean}): Promise<ConfigField[]>;
  save(updates: ConfigUpdates): Promise<ConfigSaveResponse>;
  invalidate(): void;
}
export interface ConfigDraftDependencies {
  api: ConfigApi;
  initialFields?: ConfigField[];
  onNavigateField?: (key: string) => void;
  validate?: (updates: ConfigUpdates, fields: readonly ConfigField[]) => ConfigFieldErrors;
}
export interface ConfigDraftOwner {
  readonly fields: Ref<readonly ConfigField[]>;
  readonly dirtyKeys: ComputedRef<string[]>;
  readonly dirtyCount: ComputedRef<number>;
  readonly fieldErrors: DeepReadonly<ConfigFieldErrors>;
  readonly loading: Ref<boolean>;
  readonly saving: Ref<boolean>;
  readonly error: Ref<string>;
  readonly refreshError: Ref<string>;
  readonly receipt: Ref<ConfigSaveReceipt | null>;
  readonly navigationTarget: Ref<{key: string; generation: number} | null>;
  field(key: string): ConfigField | undefined;
  readField(key: string, source?: 'effective' | 'saved'): ConfigValue | undefined;
  isDirty(key: string): boolean;
  secretDraft(key: string): SecretDraft;
  readComposite(key: string): ConfigCompositeDraft | undefined;
  setField(key: string, value: ConfigValue, options?: {force?: boolean}): void;
  setSecret(key: string, draft: SecretDraft): void;
  clearSecret(key: string): void;
  setComposite(key: string, draft: ConfigCompositeDraft): void;
  reset(keys?: readonly string[]): void;
  initialize(): Promise<void>;
  refresh(options?: {force?: boolean}): Promise<void>;
  saveAll(): Promise<ConfigSaveOutcome>;
  /** An explicit update map is the Roxy immediate-save command; no unrelated drafts are submitted. */
  saveSubset(keysOrUpdates: readonly string[] | ConfigUpdates): Promise<ConfigSaveOutcome>;
  navigateField(key: string): void;
  subscribeSaved(callback: (event: ConfigSavedEvent) => void): () => void;
  dispose(): void;
}
