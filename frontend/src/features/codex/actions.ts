import {ref, type Ref} from 'vue';
import {codexApi, type CodexCallbacks, type CodexRow, type CodexDownload, type CodexTaskReference} from '../../api/codex';
import {BulkMutationPendingError} from '../../api/bulkMutations';
export type {CodexCallbacks} from '../../api/codex';
export type CodexAction = 'download' | 'downloadCpa' | 'downloadBulk' | 'downloadBulkCpa' | 'archive' | 'archiveBulk' | 'delete' | 'deleteBulk' | 'reset' | 'refreshToken' | 'reauthorize' | 'uploadSub2';
export interface CodexActionContext {
  selected: Ref<Set<string>>; items: Ref<CodexRow[]>; archived: Ref<boolean>;
  refresh(): Promise<unknown>; callbacks: CodexCallbacks;
}
const singleActions = new Set<CodexAction>(['download', 'downloadCpa', 'archive', 'delete', 'reset']);
const queuedActions = new Set<CodexAction>(['refreshToken', 'reauthorize', 'uploadSub2']);
const labels: Record<CodexAction, string> = {download: '下载', downloadCpa: '从 CPA 下载', downloadBulk: '批量下载', downloadBulkCpa: '从 CPA 批量下载',
  archive: '归档', archiveBulk: '归档', delete: '删除', deleteBulk: '批量删除', reset: '重置', refreshToken: '刷新 OAuth Token', reauthorize: '重跑 Codex 授权', uploadSub2: '上传 sub2api'};
function message(error: unknown): string {return error instanceof Error ? error.message : '请求失败，请稍后重试。';}
function filenames(references: CodexTaskReference[] = []): string[] {
  return references.filter(item => item.accepted !== false).map(item => item.filename).filter((name): name is string => typeof name === 'string' && !!name);
}
function saveDownload(result: CodexDownload): void {
  const url = URL.createObjectURL(result.blob), anchor = document.createElement('a');
  anchor.href = url; anchor.download = result.filename;
  const release = () => {URL.revokeObjectURL(url); anchor.remove();};
  try {document.body.appendChild(anchor); anchor.click();}
  catch (error) {release(); throw error;}
  setTimeout(release, 800);
}
function confirmation(action: CodexAction, names: string[], archived: boolean, context: CodexActionContext, row?: CodexRow): string {
  const count = names.length;
  switch (action) {
    case 'archiveBulk': return `${archived ? '归档' : '恢复'}选中的 ${count} 个 Codex 授权凭证？`;
    case 'delete': return `确定删除 Codex 凭证？\n\n${names[0]}\n\n会删除数据库中的凭证及导出状态。此操作不可撤销。`;
    case 'deleteBulk': return `确定删除选中的 ${count} 个 Codex 凭证吗？\n\n会删除数据库中的凭证及导出状态。此操作不可撤销。`;
    case 'reset': return `把 ${names[0]} 标记重置为未导出？`;
    case 'downloadBulk': return `选中 ${count} 个凭证，打包到一个 JSON 文件下载。\n\n⚠ 这个聚合格式 CPA 不能直接读，主要用于备份/迁移。\n要给 CPA 用请用每行的"下载 JSON"单个下载。\n\n继续？`;
    case 'downloadBulkCpa': return `选中 ${count} 个本地记录，将按邮箱到 CPA auth-files 查找并下载真实 Codex JSON。\n\n下载结果会打包成 ZIP，解压后每个 JSON 可直接放入 CPA auth-dir。\n如 CPA 中找不到对应邮箱，会在 zip 的 manifest.json 记录错误。\n\n继续？`;
    case 'uploadSub2': return `把选中的 ${count} 个 Codex OAuth 凭证上传到 sub2api？\n\n同名账号将按 sub2api 的导入策略更新。`;
    case 'reauthorize': return `确定为选中的 ${count} 个账号重新执行 Codex OAuth 授权吗？\n\n按实际验证要求使用邮箱 OTP。手机接码仅在开关开启且遇到手机验证时使用；关闭后遇到手机验证会报错退出。\n\n账号操作公共并发：${context.callbacks.operationWorkers()}\n\n授权成功后会更新本地 Codex 凭证；若“授权后自动上传并启用 sub2api”开关开启，将自动上传并恢复调度；关闭时需在成功后手工点击“上传 sub2api”。`;
    case 'refreshToken': {
      const untracked = [...context.items.value, ...(row ? [row] : [])].some(item => names.includes(item.filename) && Number(item.exported_count || 0) > 0 && Number(item.sub2_uploaded_count || 0) === 0);
      return `使用 refresh_token 刷新选中的 ${count} 个 Codex OAuth 凭证？\n\n这个操作不发邮箱验证码、不用接码短信。刷新成功后，本地凭证会更新；已记录为上传过 sub2api 的凭证也会自动同步。`
        + (untracked ? '\n\n⚠ 检测到旧版“已导出”记录，无法区分当时是下载还是上传 sub2api。如果这些凭证正在 sub2api 使用，建议先取消并点一次“上传 sub2api”，建立自动同步记录。' : '');
    }
    default: return '';
  }
}

export function createCodexActions(context: CodexActionContext) {
  const busy = ref(false), error = ref(''), uploadProgress = ref(false);
  const {callbacks} = context;
  function clearAcknowledged(receipts: string[], requested: string[]) {
    const selected = new Set(context.selected.value), allowed = new Set(requested);
    for (const name of receipts) if (allowed.has(name)) selected.delete(name);
    context.selected.value = selected;
  }
  async function refreshAfterCompletion() {
    try {await context.refresh();}
    catch (failure) {error.value = `操作已完成，但列表刷新失败：${message(failure)}`; callbacks.notify(error.value);}
  }
  async function run(action: CodexAction, supplied?: string[], row?: CodexRow): Promise<void> {
    if (busy.value) return;
    const names = [...new Set((supplied ?? [...context.selected.value]).filter(name => !!name))];
    if (!names.length) return;
    busy.value = true; error.value = '';
    const archived = !(row?.archived ?? context.archived.value);
    try {
      const limit = singleActions.has(action) ? 1 : queuedActions.has(action) ? 500 : 1000;
      if (names.length > limit) throw new Error(`单次最多 ${limit} 个凭证，请调整选择后重试。`);
      const note = confirmation(action, names, archived, context, row);
      if (note && !await callbacks.confirm(note)) return;
      const filename = names[0]!;
      switch (action) {
        case 'download': case 'downloadCpa': case 'downloadBulk': case 'downloadBulkCpa': {
          const bulk = action === 'downloadBulk' || action === 'downloadBulkCpa', cpa = action === 'downloadCpa' || action === 'downloadBulkCpa';
          const result = bulk ? await codexApi.downloadBulk(names, cpa) : await codexApi.download(filename, cpa);
          saveDownload(result);
          if (bulk) clearAcknowledged(result.acknowledged, names);
          callbacks.notify(bulk ? cpa ? '已从 CPA 下载 ZIP，成功与失败详情见 manifest.json' : result.acknowledged.length ? `已打包下载 ${result.acknowledged.length} 个${result.failed ? `，${result.failed} 个失败` : ''}` : '成功 0 个，已下载错误清单' : cpa ? '已从 CPA 下载' : '已下载 JSON');
          await refreshAfterCompletion(); break;
        }
        case 'archive': case 'archiveBulk': {
          const result = action === 'archive' ? await codexApi.archive(filename, archived) : await codexApi.archiveBulk(names, archived,{onAccepted:result=>callbacks.notify(`批量命令已受理，正在执行（命令 ${result.command_id}）`)});
          clearAcknowledged(action === 'archive' ? result.filename ? [result.filename] : [] : (result.updated || []).map(item => item.filename), names);
          callbacks.notify(action === 'archive' ? archived ? '已归档' : '已恢复' : `${archived ? '归档' : '恢复'}成功 ${result.updated_count || 0} 个${result.skipped?.length?`，未完成 ${result.skipped.length} 个`:''}`);
          await refreshAfterCompletion(); break;
        }
        case 'delete': case 'deleteBulk': {
          const result = action === 'delete' ? await codexApi.delete(filename) : await codexApi.deleteBulk(names,{onAccepted:result=>callbacks.notify(`批量命令已受理，正在执行（命令 ${result.command_id}）`)});
          clearAcknowledged(typeof result.deleted === 'string' ? [result.deleted] : result.deleted || [], names);
          const skipped = result.skipped?.length || 0;
          callbacks.notify(action === 'delete' ? 'Codex 凭证已删除' : `已删除 ${result.deleted_count || 0} 个${skipped ? `，跳过 ${skipped} 个` : ''}`);
          await refreshAfterCompletion(); break;
        }
        case 'reset': await codexApi.reset(filename); callbacks.notify('已重置'); await refreshAfterCompletion(); break;
        case 'refreshToken': case 'reauthorize': {
          const result = action === 'refreshToken' ? await codexApi.refreshToken(names) : await codexApi.reauthorize(names);
          clearAcknowledged(filenames(result.started), names);
          const skipped = result.skipped?.length || 0;
          callbacks.notify(skipped ? `已开始${action === 'refreshToken' ? '刷新' : '重跑'} ${result.started_count || 0} 个，跳过 ${skipped} 个` : result.message || `已开始${action === 'refreshToken' ? '刷新 OAuth Token' : '重跑 Codex 授权'}`);
          callbacks.openTasks(action === 'refreshToken' ? 'codex_token_refresh' : 'codex_retry'); break;
        }
        case 'uploadSub2': {
          const result = await codexApi.uploadSub2(names), issues = (result.failed_count || 0) + (result.skipped_count || 0);
          clearAcknowledged(filenames(result.accepted ? result.queued : result.uploaded), names);
          if (result.accepted) {
            const queued = result.queued || [];
            const hasProgress = queued.some(item => item.accepted && Number(item.task_id));
            callbacks.notify(`手动上传已入队 ${result.queued_count || 0} 个${issues ? `，${issues} 个未入队` : ''}${hasProgress ? '，可点击“查看上传进度”查看最终结果' : ''}`);
            callbacks.track(queued, '手动上传', {navigate: false});
            uploadProgress.value ||= hasProgress;
          } else {
            callbacks.notify(issues ? `已上传 ${result.uploaded_count || 0} 个，${issues} 个未完成` : `已上传 ${result.uploaded_count || 0} 个到 sub2api`);
            await refreshAfterCompletion();
          }
          break;
        }
      }
    } catch (failure) {
      error.value = failure instanceof BulkMutationPendingError?failure.message:`${labels[action]}失败: ${message(failure)}`; callbacks.notify(error.value);
    } finally {busy.value = false;}
  }
  return {busy, error, uploadProgress, run, showProgress: () => callbacks.openTasks()};
}
