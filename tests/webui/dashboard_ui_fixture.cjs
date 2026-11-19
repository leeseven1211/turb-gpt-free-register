// Run the dashboard's presentation functions without a server, timer or npm dependencies.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const js = path.resolve(__dirname, '../../webui/static/js');
const read = file => fs.readFileSync(path.join(js, file), 'utf8');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const noop = () => {};

function loadFunction(context, file, name) {
  const body = read(file).match(new RegExp(`^(?:async )?function ${name}\\([^]*?^\\}`, 'm'));
  if (!body) throw new Error(`Missing ${name} in ${file}`);
  vm.runInContext(body[0], context, {filename: file});
}

function configMenus() {
  const context = vm.createContext({CONFIG: input, esc: String, attrEsc: String,
    window: {addEventListener: noop}, $: () => ({addEventListener: noop})});
  vm.runInContext(read('pages/config/page.js'), context);
  return ['注册主链路', '通用配置'].map(domain => context.renderConfigSectionHead(domain));
}

function startupTabs() {
  return [null, 'accounts'].map(saved => {
    const tabs = [];
    const context = vm.createContext({localStorage: {getItem: key => key === 'gpt_console_active_tab' ? saved : null},
      location: {hash: ''}, parseNavigationHash: () => null, activateTab: tab => tabs.push(tab),
      document: {addEventListener: noop}, window: {addEventListener: noop}, $: () => null,
      recordNavigationHistory: noop, navigationHistoryBound: false, setInterval: noop,
      initResizableTables: noop, loadRuntimeUiSettings: noop, loadSummary: noop, loadCapabilities: noop,
      restoreModuleViewState: noop});
    loadFunction(context, 'shared/common.js', 'initializeNavigationHistory');
    vm.runInContext(read('bootstrap.js'), context);
    return tabs;
  });
}

async function accountFacets() {
  const synced = {};
  const context = vm.createContext({
    accountListQueryParams: () => 'paged=1', api: async () => ({items: [], total: 0, facets: {
      plan: [{value: 'plus', count: 1}], promotion: [{value: 'free_trial', count: 1}],
    }}),
    PAGERS: {accounts: {page: 1, size: 10}}, accountsReadGeneration: 0, accountsLoading: false,
    SHOW_ARCHIVED_ACCOUNTS: false, showAccountsLoadingState: noop, setListBusy: noop,
    showAccountSearchError: noop, renderAccountSearchTerms: noop, renderAccounts: noop, markViewReady: noop,
    syncFacetSelect(id, items, {group}) {
      if (items) synced[id] = {group, items};
    },
  });
  loadFunction(context, 'pages/accounts/page.js', 'loadAccounts');
  await context.loadAccounts();
  return synced;
}

async function run() {
  const context = vm.createContext({});
  switch (process.argv[2]) {
    case 'queue':
      for (const name of ['accountTaskAdmissionReasons', 'accountTaskAdmissionReasonText', 'accountTaskResultText']) {
        loadFunction(context, 'pages/operations/page.js', name);
      }
      return input.map(task => context.accountTaskResultText(task));
    case 'password':
      loadFunction(context, 'pages/registration/page.js', 'progressJobResult');
      return input.map(job => context.progressJobResult(job));
    case 'config': return configMenus();
    case 'startup': return startupTabs();
    case 'account-facets': return accountFacets();
    default: throw new Error(`Unknown fixture ${process.argv[2]}`);
  }
}

run().then(value => console.log(JSON.stringify(value))).catch(error => { console.error(error); process.exitCode = 1; });
