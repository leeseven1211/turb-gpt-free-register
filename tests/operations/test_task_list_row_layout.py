"""Measure the current Vue task table and its real styles in offline Chromium."""

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


FRONTEND = Path(__file__).resolve().parents[2] / 'frontend'


@pytest.fixture(scope='module')
def task_table_assets(tmp_path_factory):
    """Bundle source components into a temporary fixture, never the release assets."""
    node = shutil.which('node')
    if node is None:
        pytest.skip('本机未安装 Node.js 前端测试运行时')
    output = tmp_path_factory.mktemp('vue-task-row-layout')
    entry = """
      import {createApp, computed, h, ref} from 'vue';
      import TaskTable from './src/features/tasks/TaskTable.vue';
      import TaskFilters from './src/features/tasks/TaskFilters.vue';
      import ListFilterSummary from './src/components/ListFilterSummary.vue';
      import {emptyFilters} from './src/api/tasks.ts';
      import {clearColumnFilter, filterColumns, filterSummary, isFilterActive}
        from './src/features/tasks/filterDefinitions.ts';
      import './src/styles/task-center.css';
      const items = [
        {id: 71, task_type:'展示很长的任务类型'.repeat(9), status:'failed', duration_ms:45000,
         current_stage_label:'收尾', failure_stage:'sample', failure_stage_label:'合成的完整失败位置',
         error_code:'synthetic_task_error', error_message:'合成的完整错误原因'.repeat(8),
         error_info:{code:'synthetic.classified', cause_code:'synthetic.root_cause',
           display_code:'SYN-71', cause_display_code:'CAUSE-71', summary:'合成的分类摘要'}},
        {id: 72, task_type:'sample', status:'queued', admission_wait_reasons:[
          {code:'global_capacity', occupied:10, limit:10}, {code:'account_busy'}]},
      ];
      createApp({setup() {
        const filters = ref(emptyFilters()), openFilter = ref(null);
        const active = computed(() => filterColumns.filter(column => isFilterActive(column, filters.value)));
        const update = value => {filters.value = value;};
        return () => h('section', {class:'tc-root'}, [
          h('div', {class:'tc-toolbar'}, [
            h(TaskFilters, {modelValue:filters.value, facets:{}, open:openFilter.value === 'mobile',
              'onUpdate:modelValue':update, 'onUpdate:open':value => {openFilter.value = value ? 'mobile' : null;}}),
            h(ListFilterSummary, {items:active.value.map(column => ({key:column.key,
              label:`${column.label}：${filterSummary(column, filters.value, {})}`,
              removeLabel:`清除${column.label}筛选`})),
              onRemove:key => update(clearColumnFilter(filterColumns.find(column => column.key === key), filters.value))}),
          ]),
          h(TaskTable, {items, selected:new Set(), loading:false, error:'', busy:false,
            filters:filters.value, facets:{}, openFilter:openFilter.value,
            'onUpdate:filters':update, 'onUpdate:openFilter':value => {openFilter.value = value;}}),
        ]);
      }}).mount('#fixture');
    """
    build_script = """
      import {build} from 'vite';
      import vue from '@vitejs/plugin-vue';
      import path from 'node:path';
      const source = JSON.parse(process.env.TASK_ROW_FIXTURE_SOURCE);
      const id = path.join(process.cwd(), '__task_row_layout_fixture__.js');
      await build({configFile:false, logLevel:'error', root:process.cwd(),
        plugins:[vue(), {name:'offline-task-row-fixture',
          resolveId(value) {if(value === id) return id;},
          load(value) {if(value === id) return source;}}],
        define:{'process.env.NODE_ENV':JSON.stringify('production')},
        build:{outDir:process.env.TASK_ROW_FIXTURE_OUTPUT, emptyOutDir:false,
          lib:{entry:id, name:'TaskRowFixture', formats:['iife'],
            fileName:()=>'fixture.js', cssFileName:'fixture'}}});
    """
    result = subprocess.run(
        [node, '--input-type=module', '-e', build_script], cwd=FRONTEND,
        env={**os.environ, 'TASK_ROW_FIXTURE_SOURCE': json.dumps(entry),
             'TASK_ROW_FIXTURE_OUTPUT': str(output)},
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return output


@pytest.mark.parametrize('width', [1440, 375])
def test_task_rows_keep_their_height_while_reading_full_text(width, task_table_assets):
    api = pytest.importorskip('playwright.sync_api')
    html = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
      <style>body{margin:0}#fixture{width:100%;min-width:0}</style>
      <link rel="stylesheet" href="/fixture.css"></head>
      <body><main id="fixture"></main><script src="/fixture.js"></script></body></html>"""
    with api.sync_playwright() as runtime:
        if not Path(runtime.chromium.executable_path).exists():
            pytest.skip('本机未安装隔离 Chromium 测试运行时')
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={'width': width, 'height': 840}, has_touch=width < 600)
        page.set_default_timeout(5000)
        page.route('**/*', lambda route: route.abort())
        page.route('http://task.test/', lambda route: route.fulfill(content_type='text/html', body=html))
        for file in task_table_assets.iterdir():
            page.route(f'http://task.test/{file.name}',
                       lambda route, request, file=file: route.fulfill(path=file))
        page.goto('http://task.test/')
        trigger = page.get_by_role('button', name='筛选任务条件' if width < 600 else '筛选ID', exact=True)
        trigger.tap() if width < 600 else trigger.click()
        search = page.get_by_role('searchbox', name='任务 ID', exact=True)
        search.fill('71')
        chip = page.get_by_role('button', name='清除ID筛选', exact=True)
        assert 'ID：71' in chip.inner_text()
        page.get_by_role('button', name='完成', exact=True).click()
        chip.tap() if width < 600 else chip.click()
        trigger.tap() if width < 600 else trigger.click()
        assert search.input_value() == ''
        page.keyboard.press('Escape')
        if width < 600:
            # The Vue narrow layout uses cards rather than the retired horizontal table.
            assert page.locator('.tc-table thead').is_hidden()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        rows = page.locator('.tc-table tbody tr')
        first = rows.first
        row_height = first.bounding_box()['height']
        if width >= 600:
            # The ID control stays vertically centered next to two-line cells.
            offset = first.locator('td[data-label="ID"]').evaluate("""cell => {
              const glyph = cell.querySelector('button').getBoundingClientRect(), box = cell.getBoundingClientRect();
              return (glyph.top + glyph.bottom - box.top - box.bottom) / 2;
            }""")
            assert abs(offset) <= 2
        else:
            assert first.evaluate("row => getComputedStyle(row).display") == 'grid'
        task_type = first.locator('td[data-label="类型"] .list-cell-primary')
        assert task_type.evaluate("""cell => {
          const limit = 2 * parseFloat(getComputedStyle(cell).lineHeight);
          return cell.clientHeight <= limit + 1 && cell.scrollHeight > limit;
        }""")
        assert first.locator('td[data-label="类型"] .list-cell').get_attribute('title') == '展示很长的任务类型' * 9
        step = first.locator('td[data-label="当前步骤"] .list-cell')
        assert step.inner_text().splitlines() == ['失败于 合成的完整失败位置', '45.0 秒']
        assert step.get_attribute('title') == '收尾 · 失败于 合成的完整失败位置 · 45.0 秒'
        step.tap() if width < 600 else step.hover()
        assert first.bounding_box()['height'] == row_height
        result = first.locator('td[data-label="结果 / 错误"] details')
        compact = result.locator('summary')
        assert len(compact.inner_text().replace('\n', '')) <= 10
        evidence = result.locator('.list-result-details')
        assert not evidence.is_visible()
        compact.tap() if width < 600 else compact.click()
        for full_text in ['合成的完整错误原因' * 8, 'SYN-71', 'CAUSE-71',
                          'synthetic_task_error', 'synthetic.classified', 'synthetic.root_cause']:
            assert full_text in evidence.inner_text()
            assert full_text in compact.get_attribute('title')
        assert first.bounding_box()['height'] > row_height
        if width < 600:
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        compact.tap() if width < 600 else compact.click()
        assert first.bounding_box()['height'] == row_height
        waiting = rows.nth(1)
        wait_height = waiting.bounding_box()['height']
        wait_summary = waiting.locator('td[data-label="结果 / 错误"] summary')
        assert wait_summary.inner_text() == '等待全局空位'
        assert len(wait_summary.inner_text()) <= 10
        wait_summary.tap() if width < 600 else wait_summary.click()
        wait_evidence = waiting.locator('.list-result-details')
        assert wait_evidence.is_visible()
        for reason in ['等待全局空位（10/10）', '账号正由其他任务使用']:
            assert reason in wait_evidence.inner_text()
        wait_summary.tap() if width < 600 else wait_summary.click()
        assert waiting.bounding_box()['height'] == wait_height
        browser.close()
