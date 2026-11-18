import { formatDateTime } from '../../shared/time';
import type { ProxyRow } from './contracts';
export type FacetLabel = (group: string, value: string) => string;
export function display(value: unknown, fallback = '—'): string {
  return value == null || value === ''
    ? fallback
    : typeof value === 'string' || typeof value === 'number'
      ? String(value)
      : fallback;
}
export function object(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
export function list(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? (value.filter((item) => item && typeof item === 'object' && !Array.isArray(item)) as Record<
        string,
        unknown
      >[])
    : [];
}
export function number(value: unknown): number | null {
  if (value == null || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? n : null;
}
export function bytes(value: unknown): string {
  const n = number(value);
  if (n == null) return '—';
  if (n < 1024) return `${n} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let scaled = n,
    index = -1;
  while (scaled >= 1024 && index < units.length - 1) {
    scaled /= 1024;
    index++;
  }
  return `${scaled >= 100 ? scaled.toFixed(0) : scaled >= 10 ? scaled.toFixed(1) : scaled.toFixed(2)} ${units[index]}`;
}
const statuses: Record<string, string> = {
  pending: '待验证',
  fetching: '提取中',
  checking: '复检中',
  ready: '可领取',
  shared: '共享库存',
  shared_pending: '共享线路检测中',
  shared_leased: '共享查询中',
  pool_leased: '任务独占中',
  cooldown: '冷却中',
  quarantine: '故障隔离',
  rotation_wait: '等待轮换',
  retired: '已退役',
  leased: '租约中',
  recent: '最近释放',
  released: '已释放',
  expired: '已过期',
  failed: '失败',
  unavailable: '未采集',
  observed: '可观测',
  complete: '已完成',
  running: '运行中',
  available: '可观测',
};
export function status(value: unknown) {
  const raw = display(value, '');
  return {
    label: statuses[raw] || '未知状态',
    title: raw || '未提供状态',
    tone: (['failed', 'quarantine'].includes(raw)
      ? 'danger'
      : ['leased', 'shared_leased', 'pool_leased', 'running'].includes(raw)
        ? 'active'
        : ['ready', 'available', 'observed', 'released'].includes(raw)
          ? 'success'
          : 'neutral') as 'danger' | 'active' | 'success' | 'neutral',
  };
}
const errorLabels: Record<string, { label: string; evidence: string }> = {
  supply_unavailable: { label: '补货暂不可用', evidence: '补货暂不可用' },
  supply_candidates_duplicate: { label: '候选已占用', evidence: '供应商返回的候选均已占用或处于冷却期' },
  transport_failure: { label: '线路连接失败', evidence: '线路连接失败' },
  check_interrupted: { label: '复检中断', evidence: '复检中断' },
  health_check_failed: { label: '健康检查失败', evidence: '健康检查失败' },
};
export function errorPresentation(value: unknown) {
  const raw = display(value, '');
  const known = errorLabels[raw];
  return known
    ? { ...known, evidence: `${known.evidence}（${raw}）` }
    : { label: raw ? '库存异常' : '—', evidence: raw };
}
export function taskType(row: ProxyRow, label?: FacetLabel) {
  const hasJob = row.registration_job_id != null && row.registration_job_id !== '';
  if ((row.operation_task_id == null || row.operation_task_id === '') && !hasJob) return '未关联任务';
  const type = display(row.operation_task_type, hasJob ? 'registration' : '');
  return type
    ? label?.('task_type', type) ||
        (
          {
            registration: '注册',
            plan_check: '查套餐',
            token_refresh: '刷新 Token',
            live_check: '查活',
          } as Record<string, string>
        )[type] ||
        type
    : '未关联任务';
}
export function correlation(row: ProxyRow, includeJob = false) {
  const entries = [
    ['任务', row.operation_task_id],
    ['运行', row.operation_run_id],
    ...(includeJob ? [['注册 job', row.registration_job_id]] : []),
  ].filter(([, value]) => value != null && value !== '');
  return entries.map(([name, value]) => `${name} #${display(value)}`).join(' · ') || '—';
}
export function taskSummary(row: ProxyRow, label?: FacetLabel) {
  return {
    text: taskType(row, label),
    secondary: correlation(row, row.operation_task_id == null || row.operation_task_id === ''),
    title: [taskType(row, label), correlation(row, true)].join(' · '),
  };
}
export function trafficBytes(row: ProxyRow) {
  if (row.availability !== 'available' || number(row.total_bytes) == null)
    return { text: '未采集', title: '未采集' };
  const text = `${bytes(row.upload_bytes)} / ${bytes(row.download_bytes)} / ${bytes(row.total_bytes)}`;
  const partial = row.source === 'protocol_http' && (number(row.byte_unknown_count) || 0) > 0;
  return {
    text,
    secondary: partial ? '部分字节未知' : undefined,
    title: text + (partial ? '（部分字节未知）' : ''),
  };
}
export interface DetailField {
  label: string;
  value: string;
}
function statusFamilyCounts(value: unknown): string {
  const counts = object(value);
  return ['1xx', '2xx', '3xx', '4xx', '5xx', 'unknown']
    .flatMap((family) => {
      const count = counts[family];
      return typeof count === 'number' && Number.isSafeInteger(count) && count >= 0
        ? [`${family}: ${count}`]
        : [];
    })
    .join(' / ');
}
export function recordDetails(view: 'history' | 'traffic', row: ProxyRow, label?: FacetLabel): DetailField[] {
  const fields: DetailField[] = [];
  const add = (name: string, value: unknown) => {
    if (value != null && value !== '') fields.push({ label: name, value: display(value) });
  };
  const date = (value: unknown) => (value ? formatDateTime(value) : null);
  if (view === 'history') {
    [
      ['租约 ID', row.lease_id],
      ['线路来源', row.provider],
      ['出口 IP', row.exit_ip],
      ['状态', statuses[display(row.state)] || row.state],
      ['账号', row.account_id],
      ['用途', row.purpose],
      ['任务', row.operation_task_id],
      ['运行', row.operation_run_id],
      ['注册 job', row.registration_job_id],
      ['重试序号', row.route_attempt_no],
      ['获取时间', date(row.acquired_at)],
      ['到期时间', date(row.expires_at)],
      ['释放时间', date(row.released_at)],
    ].forEach(([name, value]) => add(String(name), value));
    return fields;
  }
  [
    ['来源', row.source],
    [
      '字节口径',
      row.source === 'protocol_http'
        ? 'HTTP 传输正文；不含请求/响应头、TLS、隧道或代理商账单'
        : '浏览器可观测字节；不等同代理商账单',
    ],
    ['总请求耗时', row.duration_ms == null ? null : `${display(row.duration_ms)} 毫秒`],
    ['状态族', statusFamilyCounts(row.status_families)],
    ['重定向次数', row.redirect_count],
    ['解压后响应正文', row.decoded_response_bytes == null ? null : bytes(row.decoded_response_bytes)],
    ['字节未知请求数', row.byte_unknown_count],
    ['注册 Attempt', row.registration_attempt_id],
    ['注册 Run', row.registration_run_id],
    ['方法', row.method],
    ['上传流量', bytes(row.upload_bytes)],
    ['下载流量', bytes(row.download_bytes)],
    ['总流量', bytes(row.total_bytes)],
    ['请求数', row.request_count],
    ['失败数', row.failed_count],
    ['未完成数', row.unfinished_count],
    ['未知数', row.unknown_count],
    ['线路租约', row.proxy_lease_id],
    ['账号', row.account_id],
    ['任务类型', taskType(row, label)],
    ['注册 job', row.registration_job_id],
    ['任务', row.operation_task_id],
    ['运行', row.operation_run_id],
    ['开始时间', date(row.started_at)],
    ['完成时间', date(row.ended_at)],
  ].forEach(([name, value]) => add(String(name), value));
  const transport = object(row.proxy_transport);
  if (transport.available) {
    add('代理隧道传输', bytes(transport.total_bytes));
    add(
      '隧道口径',
      '含 TLS、启动和后台请求；与页面字节重叠，不相加；不含 TCP/IP 开销、缓存匿名填充和代理商账单',
    );
    add('连接前已拦截', `${number(transport.blocked_connection_count) ?? 0} 次；没有估算节省字节`);
    for (const target of list(transport.destinations).slice(0, 50))
      add(
        `目标 ${display(target.host)}:${display(target.port)}`,
        `${bytes(target.total_bytes)} · 连接 ${display(target.connection_count)} · 失败 ${display(target.failed_connection_count)} · 拦截 ${display(target.blocked_connection_count)} · 重试 ${display(target.connect_retry_count)} · 恢复 ${display(target.recovered_connection_count)}`,
      );
  }
  const resources = list(row.resource_details);
  if (resources.length) {
    add(
      '资源明细',
      `页面可观测口径；以下显示前 ${Math.min(50, resources.length)} 项，完整有界明细见任务日志`,
    );
    for (const resource of resources.slice(0, 50))
      add(display(resource.url), `${display(resource.resource_type)} · ${bytes(resource.total_bytes)}`);
  }
  const coverage = object(row.js_coverage);
  if (coverage.enabled) {
    add(
      'JS 覆盖率',
      `target ${display(coverage.target_count)} · 已采集 ${display(coverage.collected_target_count)} · 不支持/失败 ${display(coverage.unsupported_target_count)}；未观察到执行不能证明资源可安全拦截`,
    );
    for (const script of list(coverage.scripts).slice(0, 50))
      add(
        display(script.url),
        `函数 ${display(script.function_count)} · 观察到执行 ${display(script.executed_function_count)}`,
      );
  }
  return fields;
}
