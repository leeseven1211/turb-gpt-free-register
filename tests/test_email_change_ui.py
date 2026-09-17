from __future__ import annotations

import json
import subprocess
from html.parser import HTMLParser
from pathlib import Path

from tests.support_pg import PostgresTestCase
from webui.app import create_app


ROOT = Path(__file__).resolve().parents[1]


class _ElementCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def by_id(self, element_id: str):
        return next(
            ((tag, attrs) for tag, attrs in self.elements if attrs.get("id") == element_id),
            None,
        )


class EmailChangeUiTests(PostgresTestCase):
    def setUp(self):
        self.app = create_app(auth_code="test-auth")
        self.client = self.app.test_client()
        self.headers = {"X-Auth-Code": "test-auth"}

    def test_both_ui_variants_render_source_only_accessible_dialog(self):
        for path in ("/", "/?ui=legacy"):
            response = self.client.get(path, headers=self.headers)
            self.assertEqual(200, response.status_code)
            source = response.get_data(as_text=True)
            parser = _ElementCollector()
            parser.feed(source)

            modal = parser.by_id("emailChangeModal")
            self.assertIsNotNone(modal)
            self.assertEqual("dialog", modal[1].get("role"))
            self.assertEqual("true", modal[1].get("aria-modal"))
            self.assertEqual("emailChangeTitle", modal[1].get("aria-labelledby"))

            source_select = parser.by_id("emailChangeSource")
            self.assertIsNotNone(source_select)
            self.assertEqual("select", source_select[0])
            self.assertEqual("email_source", source_select[1].get("name"))
            self.assertIn("required", source_select[1])
            self.assertIsNone(parser.by_id("emailChangeTarget"))
            self.assertIn("不会启动浏览器", source)

    def test_modern_submit_posts_only_source_and_opens_email_change_tasks(self):
        source = (ROOT / "webui/static/js/modern/accounts.js").read_text(encoding="utf-8")
        start = source.index("async function submitEmailChange")
        end = source.index("function closeAccountsV2MoreMenus", start)
        function_source = source[start:end]
        harness = f"""
const calls = [];
const nodes = {{
  '#emailChangeModal': {{dataset: {{accountId: '7'}}, classList: {{add() {{}}}}}},
  '#emailChangeSource': {{value: 'outlook', checkValidity: () => true, reportValidity() {{}}, focus() {{}}}},
  '#emailChangeSourceError': {{textContent: '', hidden: true}},
  '#btnSubmitEmailChange': {{disabled: false, textContent: '提交换绑'}},
  '#accountTaskTargetFilterV2': {{value: ''}},
  '#accountTaskTypeFilterV2': {{value: ''}},
}};
const $ = selector => nodes[selector] || null;
const ACCOUNTS = [{{id: 7, email: 'old@example.test', email_source: 'outlook'}}];
const PAGERS = {{accountTasks: {{page: 3}}}};
async function api(url, options) {{ calls.push({{url, options}}); return {{task_id: 99}}; }}
function showToast() {{}}
function closeEmailChangeModal() {{}}
function loadAccounts() {{}}
function activateTab(tab) {{ calls.push({{tab}}); }}
{function_source}
(async () => {{
  await submitEmailChange({{preventDefault() {{}}}});
  const request = calls.find(item => item.url);
  const payload = JSON.parse(request.options.body);
  const opened = calls.some(item => item.tab === 'tasks');
  if (request.url !== '/api/accounts/7/email-change'
      || JSON.stringify(payload) !== JSON.stringify({{email_source: 'outlook'}})
      || nodes['#accountTaskTypeFilterV2'].value !== 'email_change'
      || PAGERS.accountTasks.page !== 1
      || !opened) {{
    throw new Error(JSON.stringify({{request, payload, type: nodes['#accountTaskTypeFilterV2'].value, page: PAGERS.accountTasks.page, opened}}));
  }}
  console.log('ok');
}})().catch(error => {{ console.error(error); process.exit(1); }});
"""
        result = subprocess.run(
            ["node", "--input-type=commonjs", "-e", harness],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)
        self.assertEqual("ok", result.stdout.strip())
