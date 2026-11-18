import {computed, onScopeDispose, ref} from 'vue';
export interface ColumnWidthOptions {
  defaults: number[]; storageKey: string; totalStorageKey?: string; min: number; max: number; savedMin?: number;
  ratioPrecision?: number; totalPrecision?: number; onPersist?: () => void; onReset?: () => void;
}
export function useColumnWidths(options: ColumnWidthOptions) {
  const widths = ref([...options.defaults]);
  const total = computed(() => widths.value.reduce((sum, n) => sum + n, 0));
  try {
    const saved = JSON.parse(localStorage.getItem(options.storageKey) || 'null');
    if (Array.isArray(saved) && saved.length === options.defaults.length && saved.every(n => typeof n === 'number' && Number.isFinite(n) && n > 0)) {
      if (options.totalStorageKey) {
        // 旧列表以比例和整表像素宽分开持久化，不能把比例当作像素。
        const savedTotal = Number(localStorage.getItem(options.totalStorageKey));
        const pixelTotal = Number.isFinite(savedTotal) && savedTotal > 0 ? savedTotal : total.value;
        const ratioTotal = saved.reduce((sum, n) => sum + n, 0);
        const pixels = saved.map(n => n / ratioTotal * pixelTotal);
        if (pixels.every(n => Number.isFinite(n) && n > 0)) widths.value = pixels;
      } else if (saved.every(n => n >= (options.savedMin ?? options.min) && n <= options.max)) widths.value = saved;
    }
  } catch { /* 无效或不可访问的存储使用默认列宽。 */ }
  let cleanup: (() => void) | undefined;
  function persist() {
    try {
      const values = options.totalStorageKey ? widths.value.map(n => Number((n / total.value * 100).toFixed(options.ratioPrecision ?? 4))) : widths.value;
      localStorage.setItem(options.storageKey, JSON.stringify(values));
      if (options.totalStorageKey) localStorage.setItem(options.totalStorageKey, String(Number(total.value.toFixed(options.totalPrecision ?? 0))));
      options.onPersist?.();
    } catch { /* 存储不可用时保留本页列宽。 */ }
  }
  function resizeWithKeyboard(index: number, delta: number) {
    if (widths.value[index] == null || !Number.isFinite(delta)) return;
    widths.value[index] = Math.max(options.min, Math.min(options.max, widths.value[index]! + delta));
    persist();
  }
  function resize(index: number, event: PointerEvent) {
    if (widths.value[index] == null) return;
    cleanup?.();
    const initial = widths.value[index]!, origin = event.clientX;
    const move = (event: PointerEvent) => { widths.value[index] = Math.max(options.min, Math.min(options.max, initial + event.clientX - origin)); };
    const end = () => { cleanup?.(); persist(); };
    cleanup = () => {
      document.removeEventListener('pointermove', move);
      document.removeEventListener('pointerup', end);
      document.removeEventListener('pointercancel', end);
      cleanup = undefined;
    };
    document.addEventListener('pointermove', move);
    document.addEventListener('pointerup', end, {once: true});
    document.addEventListener('pointercancel', end, {once: true});
  }
  function resetColumns() {
    cleanup?.(); widths.value = [...options.defaults];
    try {
      localStorage.removeItem(options.storageKey);
      if (options.totalStorageKey) localStorage.removeItem(options.totalStorageKey);
      options.onReset?.();
    } catch { /* 默认列宽仍在本页生效。 */ }
  }
  onScopeDispose(() => cleanup?.());
  return {widths, total, resize, resizeWithKeyboard, resetColumns};
}
