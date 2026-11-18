import type {Facets, TaskFilters} from '../../api/tasks';
import {label} from './presentation';

export type FilterColumnKey = 'task_id' | 'type' | 'target' | 'status' | 'target_status' | 'batch' | 'run_count' | 'stage' | 'created' | 'result';
export interface FilterColumn {
  key: FilterColumnKey;
  label: string;
  fields: readonly (keyof TaskFilters)[];
  kind: 'search' | 'select' | 'date-range';
  group?: string;
  placeholder?: string;
}

export const filterColumns: readonly FilterColumn[] = [
  {key: 'task_id', label: 'ID', fields: ['task_id'], kind: 'search', placeholder: '任务 ID'},
  {key: 'type', label: '类型', fields: ['type'], kind: 'select', group: 'task_type'},
  {key: 'target', label: '目标', fields: ['target'], kind: 'search', placeholder: '账号、邮箱或注册尝试'},
  {key: 'status', label: '执行状态', fields: ['status'], kind: 'select', group: 'status'},
  {key: 'target_status', label: '目标状态', fields: ['target_status'], kind: 'select', group: 'target_status'},
  {key: 'batch', label: '批次 / 触发', fields: ['batch'], kind: 'search', placeholder: '批次或触发方式'},
  {key: 'run_count', label: '运行次数', fields: ['run_count'], kind: 'select', group: 'run_count'},
  {key: 'stage', label: '当前步骤', fields: ['stage'], kind: 'select', group: 'stage'},
  {key: 'created', label: '创建 / 完成', fields: ['created_from', 'created_to'], kind: 'date-range'},
  {key: 'result', label: '结果 / 错误', fields: ['result'], kind: 'search', placeholder: '结果或错误关键词'},
];

export function isFilterActive(column: FilterColumn, filters: TaskFilters): boolean {
  return column.fields.some(field => !!filters[field]);
}

export function filterSummary(column: FilterColumn, filters: TaskFilters, facets: Facets): string {
  if (column.kind === 'date-range') {
    const from = filters.created_from, to = filters.created_to;
    return from && to ? `创建日期 ${from} 至 ${to}` : from ? `创建日期自 ${from}` : to ? `创建日期截至 ${to}` : '';
  }
  const value = filters[column.fields[0]!];
  if (!value || column.kind !== 'select') return value;
  const group = column.group || '';
  const options = facets[group] || [];
  const whole = options.find(item => item.value === value)?.label;
  return whole || value.split(',').map(item => {
    const normalized = item.trim();
    return options.find(option => option.value === normalized)?.label || label(group, normalized);
  }).join('、');
}

export function clearColumnFilter(column: FilterColumn, filters: TaskFilters): TaskFilters {
  const cleared = {...filters};
  for (const field of column.fields) cleared[field] = '';
  return cleared;
}
