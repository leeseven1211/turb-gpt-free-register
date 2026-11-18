import type {CodexFacets, CodexFilters} from '../../api/codex';

export type CodexColumnKey = 'q' | 'plan' | 'status' | 'oauth_status' | 'account_id' | 'sub2api_id' | 'date' | 'expired_date';
export interface CodexColumn {
  key: CodexColumnKey;
  label: string;
  fields: readonly (keyof CodexFilters)[];
  kind: 'text' | 'enum' | 'date' | 'date-range';
  placeholder?: string;
}
export const codexColumns: readonly CodexColumn[] = [
  {key: 'q', label: '邮箱 / 文件', fields: ['q'], kind: 'text', placeholder: '邮箱、文件名或 Sub2API ID'},
  {key: 'plan', label: 'Plan', fields: ['plan'], kind: 'enum'},
  {key: 'status', label: '状态', fields: ['status'], kind: 'enum'},
  {key: 'oauth_status', label: 'OAuth 状态', fields: ['oauth_status'], kind: 'enum'},
  {key: 'account_id', label: 'Account ID', fields: ['account_id'], kind: 'text', placeholder: '输入 Account ID'},
  {key: 'sub2api_id', label: 'Sub2API ID', fields: ['sub2api_id'], kind: 'text', placeholder: '输入 Sub2API ID'},
  {key: 'date', label: '更新时间', fields: ['date_from', 'date_to'], kind: 'date-range'},
  {key: 'expired_date', label: '过期时间', fields: ['expired_date'], kind: 'date'},
];
const labels: Record<string, Record<string, string>> = {
  status: {exported: '已导出', unexported: '未导出', archived: '已归档'},
  oauth_status: {valid: '有效', expiring: '即将过期', expired: '已过期', missing: '缺少令牌', unknown: '未知', deactivated: '账号停用'},
};
export function facetLabel(group: string, value: string): string {
  if (group === 'plan') return value === 'unqueried' ? '未查询' : value ? value.charAt(0).toUpperCase() + value.slice(1) : '-';
  return labels[group]?.[value] || value || '-';
}
export function filterChips(filters: CodexFilters, facets: CodexFacets): {key: string; label: string; title: string; removeLabel: string}[] {
  return codexColumns.flatMap(column => {
    let value = filters[column.fields[0]!];
    if (column.kind === 'date-range') {
      const from = filters.date_from, to = filters.date_to;
      value = from && to ? `${from} 至 ${to}` : from ? `自 ${from}` : to ? `截至 ${to}` : '';
    } else if (column.kind === 'enum' && value) {
      // Codex API uses single values; a comma is not an implicit multi-select.
      value = facets[column.key]?.find(item => item.value === value)?.label || facetLabel(column.key, value);
    }
    if (!value) return [];
    const label = `${column.label}：${value}`;
    return [{key: column.key, label, title: label, removeLabel: `清除${column.label}筛选`}];
  });
}
export function clearFilter(filters: CodexFilters, key: string): CodexFilters {
  const result = {...filters};
  for (const field of codexColumns.find(column => column.key === key)?.fields || []) result[field] = '';
  return result;
}
