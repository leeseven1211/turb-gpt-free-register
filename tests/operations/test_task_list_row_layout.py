"""Measure task rows in the real stylesheet and list renderer without starting the application."""

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader


WEBUI = Path(__file__).resolve().parents[2] / 'webui'


@pytest.mark.parametrize('width', [1440, 375])
def test_task_rows_keep_their_height_while_reading_full_text(width):
    api = pytest.importorskip('playwright.sync_api')
    template = Environment(loader=FileSystemLoader(WEBUI / 'templates')).get_template('index.html')
    html = template.render(url_for=lambda _, filename, **kwargs: f'/static/{filename}')
    with api.sync_playwright() as runtime:
        if not Path(runtime.chromium.executable_path).exists():
            pytest.skip('本机未安装隔离 Chromium 测试运行时')
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={'width': width, 'height': 840}, has_touch=width < 600)
        page.set_default_timeout(5000)
        page.route('**/*', lambda route: route.abort())
        page.route('http://task.test/', lambda route: route.fulfill(content_type='text/html', body=html))
        for asset in ['css/**/*.css', 'js/shared/**/*.js', 'js/pages/accounts/page.js', 'js/pages/operations/page.js',
                      'js/pages/operations/list-display.js']:
            for file in (WEBUI / 'static').glob(asset):
                page.route(f'http://task.test/static/{file.relative_to(WEBUI / "static")}',
                           lambda route, request, file=file: route.fulfill(path=file))
        page.goto('http://task.test/')
        page.evaluate("""() => {
          const tab = document.querySelector('#tab-accounts');
          document.getElementById('tab-overview').classList.add('hidden');
          tab.dataset.moduleView = 'tasks';
          tab.classList.remove('hidden');
          ACCOUNT_TASKS = [
            {id: 71, task_type:'展示很长的任务类型'.repeat(9), status:'failed', duration_ms:45000,
             current_stage_label:'收尾', failure_stage:'sample', failure_stage_label:'合成的完整失败位置'},
            {id: 72, task_type:'sample', status:'queued', admission_wait_reasons:[
              {code:'global_capacity', occupied:10, limit:10}, {code:'account_busy'}]},
          ];
          ACCOUNT_TASKS_TOTAL = ACCOUNT_TASKS.length;
          renderAccountTasks();
        }""")
        header = page.locator('#accountTasksPanel th[data-column-filter="accountTaskIdFilterV2"]')
        assert header.is_visible()
        trigger = header.get_by_role('button', name='按任务 ID 筛选')
        trigger.tap() if width < 600 else trigger.click()
        header.get_by_role('searchbox').fill('71')
        chip = page.locator('#accountTasksPanel [data-clear-filter-id="accountTaskIdFilterV2"]')
        assert 'ID：71' in chip.inner_text()
        chip.tap() if width < 600 else chip.click()
        assert header.locator('input').input_value() == ''
        if width < 600:
            wrap = page.locator('.account-tasks-table-wrap')
            assert wrap.evaluate('el => el.scrollWidth > el.clientWidth && el.clientWidth <= innerWidth')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        rows = page.locator('#accountTasksBody tr')
        first = rows.first
        row_height = first.bounding_box()['height']
        # The ID glyph midline and the row midline should coincide even beside two-line content.
        offset = first.locator('td').nth(1).evaluate("""cell => {
          const range = document.createRange(); range.selectNodeContents(cell);
          const glyph = range.getBoundingClientRect(), box = cell.getBoundingClientRect();
          return (glyph.top + glyph.bottom - box.top - box.bottom) / 2;
        }""")
        assert abs(offset) <= 2
        assert first.locator('.task-cell-two-lines').evaluate("""cell => {
          const limit = 2 * parseFloat(getComputedStyle(cell).lineHeight);
          return cell.clientHeight <= limit && cell.scrollHeight > limit;
        }""")
        step = first.locator('td').nth(8)
        assert step.inner_text().splitlines() == ['失败于 合成的完整失败位置', '45s']
        step.tap() if width < 600 else step.focus()
        tip = page.get_by_role('tooltip')
        assert tip.inner_text() == '收尾 · 失败于 合成的完整失败位置 · 45s'
        assert first.bounding_box()['height'] == row_height
        assert tip.bounding_box()['x'] >= 0
        assert tip.bounding_box()['x'] + tip.bounding_box()['width'] <= width
        page.keyboard.press('Escape')
        assert not tip.is_visible()
        waiting = rows.nth(1)
        wait_height = waiting.bounding_box()['height']
        waiting.locator('summary').click()
        assert waiting.locator('details[open] > div').inner_text().splitlines() == [
            '等待全局空位（10/10）', '账号正由其他任务使用',
        ]
        assert waiting.locator('details[open] > div').evaluate("""el => {
          const r = el.getBoundingClientRect();
          return el.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2));
        }""")
        assert waiting.bounding_box()['height'] == wait_height
        browser.close()
