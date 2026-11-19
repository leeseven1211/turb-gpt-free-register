/** 由 Playwright CLI run-code 调用；相同本机内存 API、冷缓存、真实 DOM 操作。 */
export default async function sample(driverPage, config) {
  const old = config.variant === 'baseline';
  const page = await driverPage.context().newPage();
  const cdp = await page.context().newCDPSession(page);
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await cdp.send('Network.enable');
  await cdp.send('Network.setCacheDisabled', {cacheDisabled: true});
  await page.setViewportSize({width: 1440, height: 1000});
  await page.addInitScript(() => {
    window.__bench = {marks: {}, longTasks: []};
    new PerformanceObserver(list => window.__bench.longTasks.push(...list.getEntries().map(e => ({start: e.startTime, duration: e.duration}))))
      .observe({type: 'longtask', buffered: true});
  });
  const url = `http://127.0.0.1:${old ? (config.baselinePort || 8018) : (config.currentPort || 8019)}/#tasks`;
  const firstId = old ? '#accountTasksBody tr:first-child td:nth-child(2)' : '.tc-table tbody tr:first-child td[data-label=ID]';
  const results = {};
  async function painted() { await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))); }
  async function stats(name, from = 0) {
    return page.evaluate(({name, from}) => {
      if (name !== 'cold' && !from && window.__bench.marks[name] === undefined) throw new Error(`缺少点击起点：${name}`);
      const end = performance.now(), start = from || window.__bench.marks[name] || 0;
      const resources = performance.getEntriesByType('resource').filter(e => e.startTime >= start && e.responseEnd <= end);
      const api = resources.filter(e => new URL(e.name).pathname.startsWith('/api/'));
      const list = api.filter(e => new URL(e.name).pathname === '/api/operations');
      const evidence = api.filter(e => /\/(events|progress|logs)$/.test(new URL(e.name).pathname));
      return {elapsed_ms: end - start, api_count: api.length, list_count: list.length, evidence_count: evidence.length,
        api: api.map(e => ({path: new URL(e.name).pathname + new URL(e.name).search, duration_ms: e.duration, bytes: e.encodedBodySize})),
        resource_count: resources.length, bytes: resources.reduce((n, e) => n + e.encodedBodySize, 0),
        transfer_bytes: resources.reduce((n, e) => n + e.transferSize, 0),
        long_task_ms: window.__bench.longTasks.filter(e => e.start >= start && e.start <= end).reduce((n, e) => n + e.duration, 0),
        dom_nodes: document.querySelectorAll('*').length};
    }, {name, from});
  }
  async function markClick(locator, name) {
    // 旧筛选菜单会替换选项节点，document 捕获器不会在 locator 重新定位时丢失。
    await page.evaluate(name => document.addEventListener('click', () => { window.__bench.marks[name] = performance.now(); }, {capture: true, once: true}), name);
    await locator.click();
  }
  async function waitFirst(id) {
    await page.waitForFunction(({selector, id}) => document.querySelector(selector)?.textContent.trim() === `#${id}`, {selector: firstId, id});
    await painted();
  }
  try {
    await page.goto(url, {waitUntil: 'domcontentloaded'});
    await waitFirst(2000);
    results.cold = await stats('cold');
    // 首次导航后立即测离散筛选，计时从实际选项点击起。
    if (old) await page.locator('[data-column-filter="accountTaskStatusFilterV2"] [data-column-filter-trigger]').click();
    else await page.getByRole('button', {name: '筛选执行状态', exact: true}).click();
    const option = old ? page.locator('[data-column-filter="accountTaskStatusFilterV2"] [data-column-filter-option="failed"]')
      : page.locator('.tc-filter-popover input[value="failed"]');
    await markClick(option, 'filter');
    await waitFirst(1999);
    results.filter = await stats('filter');
    const next = old ? page.locator('#pager-accountTasks-v2 button[title="下一页"]')
      : page.getByRole('button', {name: '下一页', exact: true});
    await markClick(next, 'page');
    await waitFirst(1879);
    results.page = await stats('page');
    const details = old ? page.locator('[data-account-task-log="1879"]')
      : page.getByRole('button', {name: '#1879', exact: true});
    await markClick(details, 'detail');
    const eventSelector = old ? '#accountTaskLogContent .account-task-event' : '#tc-detail-panel-events .tc-event';
    await page.waitForFunction(selector => document.querySelectorAll(selector).length === 500, eventSelector);
    await page.locator(old ? '#accountTaskStageProgress .account-task-stage-step' : '.tc-progress .tc-step').first().waitFor();
    await painted();
    results.detail = await stats('detail');
    await page.locator(old ? '#btnCloseAccountTaskLog' : '[aria-label="关闭任务详情"]').click();
    await painted();
    await page.locator('[data-tab="overview"]').click();
    await page.locator('#tab-overview').waitFor({state: 'visible'});
    await painted();
    await markClick(page.locator('[data-tab="tasks"]'), 'reentry');
    await page.locator(firstId).waitFor({state: 'visible'});
    await waitFirst(1879);
    results.reentry = await stats('reentry');
    results.event_rows = 500;
    return {variant: config.variant, index: config.index, browser: page.context().browser().version(), results, errors};
  } finally { await cdp.detach(); await page.close(); }
}
