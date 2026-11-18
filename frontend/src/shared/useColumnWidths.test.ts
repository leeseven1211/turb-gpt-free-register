import {effectScope} from 'vue';
import {afterEach, describe, expect, it} from 'vitest';
import {useColumnWidths} from './useColumnWidths';

const scopes: ReturnType<typeof effectScope>[] = [];
function widths(options: Parameters<typeof useColumnWidths>[0]) {
  const scope = effectScope(); scopes.push(scope);
  return scope.run(() => useColumnWidths(options))!;
}
afterEach(() => { scopes.splice(0).forEach(scope => scope.stop()); localStorage.clear(); });

describe('共享列宽保留页面存储语义', () => {
  it('任务页恢复px且允许保存40px，键盘调整仍按65到800约束', () => {
    localStorage.setItem('task-columns', '[40,100]');
    const columns = widths({defaults: [40,72], storageKey: 'task-columns', min: 65, max: 800, savedMin: 40});
    expect(columns.widths.value).toEqual([40,100]);
    columns.resizeWithKeyboard(1, 10);
    expect(JSON.parse(localStorage.getItem('task-columns')!)).toEqual([40,110]);
    columns.resizeWithKeyboard(0, -10); expect(columns.widths.value[0]).toBe(65);
    columns.resizeWithKeyboard(1, 1000); expect(columns.widths.value[1]).toBe(800);
    columns.resetColumns(); expect(columns.widths.value).toEqual([40,72]);
    expect(localStorage.getItem('task-columns')).toBeNull();
  });
  it('旧Codex比例和整表宽共同恢复，调整后仍写兼容的两个key', () => {
    localStorage.setItem('gpt_console_table_widths_codex', '[1,3]');
    localStorage.setItem('gpt_console_table_total_codex', '800');
    const columns = widths({defaults:[100,300], storageKey:'gpt_console_table_widths_codex', totalStorageKey:'gpt_console_table_total_codex', min:28,max:1600});
    expect(columns.widths.value).toEqual([200,600]); expect(columns.total.value).toBe(800);
    columns.resizeWithKeyboard(0,20);
    const saved = JSON.parse(localStorage.getItem('gpt_console_table_widths_codex')!);
    expect(saved[0] / saved[1]).toBeCloseTo(220 / 600, 4);
    expect(localStorage.getItem('gpt_console_table_total_codex')).toBe('820');
    columns.resetColumns();
    expect(localStorage.getItem('gpt_console_table_total_codex')).toBeNull();
  });
  it('比例缺少total时使用默认整表宽，损坏记录回退默认', () => {
    localStorage.setItem('ratio', '[1,3]');
    const valid = widths({defaults:[120,280],storageKey:'ratio',totalStorageKey:'total',min:28,max:1600});
    expect(valid.widths.value).toEqual([100,300]);
    localStorage.setItem('broken', '[0,"bad"]');
    const invalid = widths({defaults:[120,280],storageKey:'broken',totalStorageKey:'total',min:28,max:1600});
    expect(invalid.widths.value).toEqual([120,280]);
  });
  it('账号列宽保留小数总宽和八位比例，重新挂载不逐次截掉像素', () => {
    localStorage.setItem('account-ratios', '[1,3]');
    localStorage.setItem('account-total', '1500.1234');
    const options = {defaults:[375,1125], storageKey:'account-ratios', totalStorageKey:'account-total',
      min:1, max:Infinity, ratioPrecision:8, totalPrecision:4};
    const columns = widths(options);
    columns.resizeWithKeyboard(0, 0.1);
    expect(localStorage.getItem('account-total')).toBe('1500.2234');
    const expectedRatio = Number((columns.widths.value[0]! / columns.total.value * 100).toFixed(8));
    expect(JSON.parse(localStorage.getItem('account-ratios')!)[0]).toBe(expectedRatio);
    const restored = widths(options);
    expect(restored.widths.value[0]).toBeCloseTo(columns.widths.value[0]!, 6);
    expect(restored.total.value).toBeCloseTo(1500.2234, 6);
  });
  it('拖动结束持久化，卸载取消拖动并不再响应document事件', () => {
    const columns = widths({defaults:[100,200],storageKey:'drag',min:65,max:800});
    columns.resize(0,new MouseEvent('pointerdown',{clientX:10}) as PointerEvent);
    document.dispatchEvent(new MouseEvent('pointermove',{clientX:50}));
    expect(columns.widths.value).toEqual([140,200]);
    document.dispatchEvent(new MouseEvent('pointerup'));
    expect(localStorage.getItem('drag')).toBe('[140,200]');
    columns.resize(0,new MouseEvent('pointerdown',{clientX:10}) as PointerEvent);
    scopes.at(-1)!.stop();
    document.dispatchEvent(new MouseEvent('pointermove',{clientX:100}));
    expect(columns.widths.value).toEqual([140,200]);
  });
});
