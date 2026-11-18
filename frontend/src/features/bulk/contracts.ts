export type BulkRecord = Record<string, unknown>;
export interface BulkNavigation {
  tab: 'bulk';
  view: 'list' | 'create' | 'detail';
  batch_id?: string;
  result_state?: string;
  cursor?: string;
  q?: string;
  operation?: string;
  state?: string;
  created_from?: string;
  created_to?: string;
}
export interface BulkPageData {
  items: BulkRecord[];
  page: { has_more: boolean; next_cursor?: string | null; page_size: number };
  summary?: BulkRecord;
}
export interface BulkListDependencies {
  api: { request(path: string, options: { method: 'GET'; signal: AbortSignal }): Promise<unknown> };
  callbacks: {
    navigate(view: BulkNavigation['view'], extra?: Partial<BulkNavigation>, focusReport?: boolean): void;
    updateNavigation(extra: Partial<BulkNavigation>): void;
    notify?(message: string): void;
    formatDateTime(value: unknown): string;
  };
}
function record(value: unknown): BulkRecord {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('批次列表响应格式无效');
  return value as BulkRecord;
}

export function readBulkPage(response: unknown) {
  const data = record(response);
  if (!Array.isArray(data.items)) throw new Error('批次列表响应格式无效');
  const items = data.items.map((value: unknown): BulkRecord & { id: string } => {
    const row = record(value);
    const id = Number.isSafeInteger(row.id) ? String(row.id) : row.id;
    if (typeof id !== 'string' || !/^[1-9]\d*$/.test(id)) throw new Error('批次编号无效');
    return { ...row, id };
  });
  const cursor = data.next_cursor ?? (data.page == null ? null : record(data.page).next_cursor);
  if (cursor != null && typeof cursor !== 'string') throw new Error('批次分页响应格式无效');
  const summary = data.summary == null ? {} : record(data.summary);
  return { items, summary, nextCursor: cursor || null };
}
