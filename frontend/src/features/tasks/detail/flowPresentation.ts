import {progressLabel, stepId, stepLabel, stepState, type Step} from './model';

/** 阶段排序由服务端的实际记录决定；位置相邻不代表串行或并行。 */
export const phaseSteps = (steps?: Step[]): Step[] => (steps || []).filter(step =>
  stepState(step) !== 'skipped' || !!step.execution?.condition || step.execution?.kind === 'conditional');

export function phaseState(step: Step): string {
  const execution = step.execution;
  if (execution?.condition?.state === 'not_met') return '条件未满足';
  const state = stepState(step);
  if (state === 'not_executed') {
    return execution?.dependency_state === 'waiting' && execution.waits_for?.length
      ? '未执行 · 等待子任务'
      : '未执行';
  }
  if (execution?.dependency_state === 'blocked') return execution.waits_for?.length ? '子任务未完成' : '前置阶段失败';
  if (execution?.dependency_state === 'waiting') return execution.waits_for?.length ? '等待子任务' : '等待前置阶段';
  if (execution?.retry?.state === 'recovered') return '重试已恢复';
  return progressLabel(state);
}

export function phaseMarkers(step: Step): string[] {
  const execution = step.execution;
  if (!execution) return [];
  return [
    execution.kind === 'conditional' ? '条件阶段' : execution.kind === 'child_task' ? '子任务' : '',
    execution.parallel_group ? '并行分支' : '',
    execution.retry?.state === 'observed' ? '有重试记录' : '',
  ].filter(Boolean);
}

export function phaseRelations(step: Step, siblings: Step[] = []): {label: string; value: string}[] {
  const execution = step.execution;
  const entries: {label: string; value: string}[] = [];
  const dependencies = step.depends_on || [];
  if (dependencies.length) entries.push({label: '依赖阶段', value: dependencies.map(id => {
    const related = siblings.find(item => item.id === id);
    return related ? stepLabel(related) : id;
  }).join('、')});
  if (execution?.condition) {
    const state = {met: '已满足', not_met: '未满足', unknown: '未确认'}[execution.condition.state];
    entries.push({label: '触发条件', value: `${execution.condition.label} · ${state}`});
  }
  if (execution?.dependency_state && execution.dependency_state !== 'unknown') {
    entries.push({label: '依赖状态', value: {waiting: execution.waits_for?.length ? '等待子任务完成' : '等待前置完成', blocked: execution.waits_for?.length ? '子任务未成功完成' : '前置阶段失败', satisfied: '已满足'}[execution.dependency_state]});
  }
  if (execution?.parallel_group) entries.push({label: '并行分组', value: execution.parallel_group});
  if (execution?.retry && execution.retry.state !== 'unknown') {
    entries.push({label: '重试', value: `${execution.retry.state === 'recovered' ? '重试已恢复' : '有重试记录'}${execution.retry.attempt_count ? ` · ${execution.retry.attempt_count} 次尝试` : ''}`});
  }
  if (!execution || !entries.length && !execution.waits_for?.length) {
    entries.push({label: '关系记录', value: '没有足够证据确定依赖或并行关系'});
  }
  if (step.observed_order != null) entries.push({label: '首次记录', value: `第 ${step.observed_order} 个被记录的阶段`});
  return entries;
}

/** 在上方步骤卡片内直接展示简洁的前置依赖、子任务等待、触发条件与并行分组标签。 */
export function phaseDependencyTags(step: Step, siblings: Step[] = []): string[] {
  const tags: string[] = [];
  if (step.depends_on?.length) {
    tags.push('前置：' + step.depends_on.map(id => {
      const related = siblings.find(s => stepId(s) === id);
      return related ? stepLabel(related) : id;
    }).join('、'));
  }
  const waitsFor = step.execution?.waits_for;
  if (waitsFor?.length) {
    const taskIds = waitsFor.filter(w => w.task_id).map(w => '#' + w.task_id);
    tags.push(taskIds.length ? '等待子任务 ' + taskIds.join('、') : '等待关联子任务');
  }
  if (step.execution?.condition?.label) {
    tags.push('条件：' + step.execution.condition.label);
  }
  if (step.execution?.parallel_group) {
    tags.push('并行：' + step.execution.parallel_group);
  }
  return tags;
}
