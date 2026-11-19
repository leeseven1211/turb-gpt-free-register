import type { components } from '../../../api/schema';
import {compareTaskIds,type TaskResponse} from '../../../api/taskIds';

export type Progress = TaskResponse<components['schemas']['OperationProgress']>;
export type Step = TaskResponse<components['schemas']['ProgressStep']>;
export type TaskEvent = TaskResponse<components['schemas']['OperationEvent']>;
export type TaskLog = TaskResponse<components['schemas']['OperationLog']>;
export type Failure = TaskResponse<components['schemas']['ProgressFailure']>;
export type DetailTab = 'events' | 'logs' | 'artifacts';
export type WindowMode = 'tail' | 'start';

export function object(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown> : {};
}
export const text = (value: unknown): string => value == null ? '' : String(value);
export const records = (value: unknown): Record<string, unknown>[] => Array.isArray(value) ? value.map(object) : [];
export const strings = (value: unknown): string[] => Array.isArray(value) ? value.map(text) : [];

const progressLabels: Record<string, string> = {
  pending: '未开始', queued: '排队中', waiting: '等待中', running: '执行中', success: '已完成', skipped: '已跳过', failed: '失败',
  recovered: '重试已恢复', unconfirmed: '响应记录缺失', not_executed: '未执行', request_unknown: '失败',
  record_incomplete: '记录不完整', debug_paused: '调试暂停', stopped: '已中断', cancelled: '已取消',
  interrupted: '已中断', attention_required: '失败', partial_success: '部分完成', deferred: '已延后',
  awaiting_confirmation: '等待响应', manual_reconcile: '失败', unsupported: '不支持', deactivated: '已停用',
};
export const stepState = (step: Step): string => text(step.display_status || step.state || 'pending').toLowerCase();
export const progressLabel = (value: unknown): string => progressLabels[text(value)] || text(value) || '状态记录缺失';
export const stepId = (step: Step): string => text(step.id || step.step_id);
export const stepLabel = (step: Step): string => ({ authenticate: '登录验证', set_twofa: '配置 2FA' })[stepId(step)] || step.label || step.name || stepId(step);
export const visibleSteps = (steps?: Step[]): Step[] => (steps || []).filter(step => stepState(step) !== 'skipped');

export function matchesStep(item: TaskEvent | TaskLog, filter: string | null, steps: Step[], isLog = false): boolean {
  if (!filter) return true;
  const detail = object(isLog ? item.fields : item.detail);
  const selected = steps.find(step => stepId(step) === filter || step.raw_stages?.includes(filter));
  const selectedStages = selected?.raw_stages || [];
  const mainStep = text(item.main_step_id || detail.main_step_id);
  const stage = text(item.stage || detail.stage);
  const stageLabel = isLog ? '' : text(item.stage_label || detail.stage_label);
  const eventId = text(item.event_id || (isLog ? detail.event_id : item.id));
  if (mainStep) return mainStep === (selected?.id || filter) || eventId === filter;
  if (eventId === filter || selected && strings(selected.event_ids).includes(eventId)) return true;
  const raw = [text(item.raw_stage || detail.raw_stage), ...strings(item.raw_stages || detail.raw_stages)];
  const stages = [stage, stageLabel, ...raw].filter(Boolean);
  const matches = steps.filter(step => stages.some(value => step.raw_stages?.includes(value)));
  // 复用 raw stage（如 dispatch）且没有明确主步骤时保留未关联状态。
  if (selected && matches.length > 1) return false;
  return [stage, stageLabel, ...raw].includes(filter)
    || stages.some(value => selectedStages.includes(value));
}

export function mergeEvents(current: TaskEvent[], incoming: TaskEvent[]): TaskEvent[] {
  const known = new Set(current.map(item => String(item.id)));
  return [...current, ...incoming.filter(item => !known.has(String(item.id)))];
}

export function orderedEvents(items: TaskEvent[]): TaskEvent[] {
  return [...items].sort((a, b) => (Date.parse(a.created_at || '') || 0) - (Date.parse(b.created_at || '') || 0) || compareTaskIds(a.id,b.id));
}

export function meaningfulDetail(value: unknown): Record<string, unknown> | null {
  const entries = Object.entries(object(value)).filter(([key, item]) => key !== 'step_state' && item != null && item !== ''
    && (!Array.isArray(item) || item.length > 0)
    && (typeof item !== 'object' || Array.isArray(item) || Object.keys(object(item)).length > 0));
  return entries.length ? Object.fromEntries(entries) : null;
}

export function eventState(event: TaskEvent): string {
  const explicit = text(object(event.detail).step_state || (event.event_type || '').replace(/^stage\./, '')).toLowerCase();
  if (['pending', 'running', 'success', 'skipped', 'failed'].includes(explicit)) return explicit;
  return text(event.level).toUpperCase() === 'ERROR' ? 'failed' : '';
}

export function failureMessage(failure: Failure): string {
  const value = failure.error_info?.cause_summary || failure.error_info?.summary || failure.message || '';
  return !value || /^(?:远端)?(?:结果)?(?:待确认|未确认|待核验|未知)$/.test(value) ? '失败诊断记录缺失' : value;
}

export function failureIsInferred(failure: Failure): boolean {
  const evidence = object(failure.evidence);
  return failure.inferred === true || evidence.inferred === true
    || ['inferred', 'legacy', 'unobserved'].includes(text(failure.evidence))
    || evidence.source === 'inferred' || evidence.kind === 'inferred';
}

export function stepDuration(step: Step, now = Date.now()): number | null {
  const start = Date.parse(step.started_at || '');
  const end = Date.parse(step.completed_at || '');
  const paused = Date.parse(text(object(step.debug_pause).paused_at));
  const state = stepState(step);
  const duration = state === 'debug_paused' ? paused - start
    : state === 'running' && Number.isFinite(start) ? now - start
    : step.duration_ms ?? (end - start);
  return Number.isFinite(duration) && duration >= 0 ? duration : null;
}

/** 诊断下载只允许本应用的同源端点，避免第三方数据变成可执行链接。 */
export function artifactUrl(value: unknown): string | null {
  const url = text(value);
  return /^\/api\/operations\/\d+\/runs\/\d+\/debug\/(har|page-state|screenshot)(?:\?.*)?$/.test(url) ? url : null;
}
