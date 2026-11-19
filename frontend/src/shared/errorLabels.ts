import catalog from '../generated/task-error-labels.json';

/** 只消费既有结构化分类结果；目录由后端维护，不重新匹配日志文本。 */
export type ClassifiedError = Readonly<Record<string, unknown>>;
const codes: Record<string, string> = {...catalog.codeLabels, ...catalog.causeCodeLabels};
const displays: Record<string, string> = catalog.displayCodeLabels;
const categories: Record<string, string> = catalog.categoryLabels;
const rules = catalog.rules.map(rule => ({...rule, match: new RegExp(rule.pattern)}));
const lookup = (labels: Record<string, string>, key: string) => Object.hasOwn(labels, key) ? labels[key] : undefined;

export function shortErrorLabel(info?: ClassifiedError | null): string {
  if (!info) return catalog.fallback;
  for (const field of catalog.lookupFields) {
    const value = String(info[field] ?? '').trim();
    if (!value) continue;
    const exact = lookup(field.includes('display') ? displays : codes, value);
    if (exact) return exact;
    const rule = rules.find(rule => rule.fields.includes(field) && rule.match.test(value));
    if (rule) return rule.label;
  }
  return lookup(categories, String(info.category ?? '')) || lookup(categories, String(info.source ?? '')) || catalog.fallback;
}
