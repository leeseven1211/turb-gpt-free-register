// 配置相同的格式器复用；不指定 timeZone，沿用浏览器本地时区。
const localDateTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
});
export function formatDateTime(value: unknown): string {
  if (!value) return '—';
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? `无效时间：${String(value)}` : localDateTimeFormatter.format(date);
}
/** 同一时区格式拆成两行，避免 ISO 长值把时间挤出列表单元格。 */
export function dateTimeLines(value: unknown): {text: string; secondary?: string} {
  const formatted = formatDateTime(value);
  const split = /^(\d{4}\/\d{2}\/\d{2})\s+(\d{2}:\d{2}:\d{2})$/.exec(formatted);
  return split ? {text: split[1]!, secondary: split[2]!} : {text: formatted};
}
