import {optionalTaskId, taskId, type TaskId} from '../../api/taskIds';

export interface AccountTaskOpen {
  filters?: Record<string, unknown>;
  taskId?: TaskId;
  runId?: TaskId | null;
}
interface AccountTaskReference {taskId: TaskId; runId: TaskId | null}
interface AccountTaskNavigationDependencies {
  openTasks(options: AccountTaskOpen): void | Promise<unknown>;
  openTask?(id: TaskId, runId: TaskId | null): void | Promise<unknown>;
}
interface AccountTaskNavigationOptions {single: boolean; type: string; target?: string; result?: unknown}

export function accountTaskReference(result: unknown): AccountTaskReference | null {
  if (!result || typeof result !== 'object' || Array.isArray(result)) return null;
  const value = result as Record<string, unknown>;
  const candidates = [value, ...['started', 'queued', 'reused'].flatMap(field =>
    Array.isArray(value[field]) ? value[field] as unknown[] : [])];
  for (const candidate of candidates) {
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) continue;
    const item = candidate as Record<string, unknown>;
    const id = item.operation_task_id || item.task_id;
    if (id) return {taskId: taskId(id), runId: optionalTaskId(item.operation_run_id || item.run_id)};
  }
  return null;
}

export async function openAccountOperationTasks(
  deps: AccountTaskNavigationDependencies, options: AccountTaskNavigationOptions,
): Promise<void> {
  // 根据发起入口判断单条与批量；批量只有一项被受理时仍打开任务列表。
  const reference = options.single ? accountTaskReference(options.result) : null;
  if (reference && deps.openTask) {
    await deps.openTask(reference.taskId, reference.runId);
    return;
  }
  await deps.openTasks({
    filters: {type: options.type, target: options.single ? options.target || '' : ''},
    ...(reference || {}),
  });
}
