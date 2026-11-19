import type {OperationTask} from '../../api/tasks';
import {admissionText, label, statusTone} from './presentation';

type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'active';
interface StatusDisplay {label: string; tone: Tone; title: string; secondary?: string}
const failed = new Set(['failed', 'attention_required', 'request_unknown', 'manual_reconcile', 'password_confirmation_pending']);
const ongoing = new Set(['running', 'waiting', 'stopping', 'cancelling', 'settling']);
const stopped = new Set(['cancelled', 'stopped', 'interrupted']);
const targetLabels: Record<string, string> = {
  email_verification_pending: '待验证或补全', credential_pending_confirmation: '凭证待核验',
};

function sourceTitle(group: 'status' | 'target_status', value: string, internal?: string | null): string {
  const title = `${group === 'status' ? '执行状态' : '目标状态'}：${label(group, value)}${value ? `（${value}）` : ''}`;
  return internal && internal !== value ? `${title} · 原始状态：${internal}` : title;
}

/** waiting 已进入执行生命周期；只有明确的子任务动作才据此描述等待对象。 */
export function taskWaitingLabel(task: OperationTask): string {
  return task.next_actions?.some(action => action.action === 'await_child') ? '等待子任务' : '等待中';
}

/** 仅用于列表，详情标签、动作资格和筛选值继续使用原字段。 */
export function taskListStatus(task: OperationTask): {execution: StatusDisplay; target: StatusDisplay | null} {
  const status = String(task.status || ''), target = String(task.target_status || '');
  const execution: StatusDisplay = {
    label: label('status', status), tone: statusTone(status) as Tone,
    title: sourceTitle('status', status, task.internal_status),
  };
  if (task.debug_pause) {
    execution.label = '已暂停'; execution.tone = 'warning'; execution.secondary = '等待结束调试';
    execution.title = `调试暂停 · ${execution.title}`;
  } else if (['queued', 'pending'].includes(status)) {
    execution.label = '排队中'; execution.tone = 'warning'; execution.secondary = admissionText(task) || undefined;
  } else if (ongoing.has(status)) {
    execution.label = '进行中';
    if (status === 'waiting') execution.secondary = admissionText(task) || taskWaitingLabel(task);
    if (['stopping', 'cancelling'].includes(status)) execution.secondary = '停止中';
    if (status === 'settling') execution.secondary = '收尾中';
  } else if (status === 'success') execution.label = '已完成';
  else if (status === 'partial_success') execution.label = '部分完成';
  else if (failed.has(status)) { execution.label = '失败'; execution.tone = 'danger'; }
  else if (stopped.has(status)) execution.label = '已停止';

  // 只省略相同语义。重跑期间目标上的旧失败、已确认的账号/凭证成果仍是额外信息。
  const redundant = !task.debug_pause && (failed.has(target) && failed.has(status)
    || target === 'completed' && status === 'success'
    || target === 'in_progress' && ongoing.has(status)
    || target === 'pending' && ['queued', 'pending', 'waiting'].includes(status)
    || target === 'cancelled' && ['cancelled', 'stopped'].includes(status));
  return {execution, target: !target || redundant ? null : {
    label: targetLabels[target] || label('target_status', target),
    tone: statusTone(target) as Tone,
    title: sourceTitle('target_status', target, task.internal_target_status),
  }};
}
