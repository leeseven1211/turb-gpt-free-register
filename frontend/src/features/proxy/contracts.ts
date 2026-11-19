import type { TaskId } from '../../api/taskIds';
export type ProxyModuleView = 'pool' | 'records';
export type ProxyRecordView = 'current' | 'history' | 'traffic';
/** Public fixed-field backend projection; components render explicit allowlists. */
export interface ProxyRow {
  id?: TaskId;
  [key: string]: unknown;
}
export interface ProxyQuery {
  page: number;
  size: number;
  window: string;
  purpose: string;
  state: string;
  search: string;
}
export interface ProxyPage {
  items: ProxyRow[];
  count: number;
  total: number;
  limit: number;
  offset: number;
  has_more?: boolean;
  aggregate?: Record<string, number>;
}
export interface ProxySummary {
  ok?: boolean;
  total_bytes: number;
  today_bytes: number;
  today_request_count?: number;
  today_browser_count?: number;
  today_route_count?: number;
  purposes?: string[];
  lease_states?: string[];
  browser_states?: string[];
  [key: string]: unknown;
}
export interface ProxyPoolSnapshot {
  policy: Record<string, number>;
  counts: Record<string, number>;
  items?: ProxyRow[];
  country_pools?: ProxyRow[];
  waiting_local?: number;
  workers_local?: number;
  capacity_warning?: string | null;
  [key: string]: unknown;
}
export interface ProxyTrafficApi {
  page(view: ProxyRecordView, query: ProxyQuery, signal?: AbortSignal): Promise<ProxyPage>;
  summary(signal?: AbortSignal): Promise<ProxySummary>;
  pool(signal?: AbortSignal): Promise<ProxyPoolSnapshot | null>;
}
export interface ProxyTrafficDeps {
  api?: ProxyTrafficApi;
  visible?: boolean;
  view?: ProxyModuleView;
  facetLabel?(group: string, value: string): string;
  notify?(message: string): void;
  onReady?(): void;
  openTask?(taskId: TaskId, runId?: TaskId | null): void;
}
export interface ProxyTrafficHandle {
  load(view?: ProxyRecordView | null): Promise<void>;
  setVisible(value: boolean): void;
  setView(view: ProxyModuleView): void;
  closeDetail(options?: { restoreFocus?: boolean }): void;
  destroy(): void;
}
export interface ProxyDetailSnapshot {
  view: 'history' | 'traffic';
  row: ProxyRow;
  opener: HTMLElement | null;
}
