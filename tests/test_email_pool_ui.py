from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_replaced_email_status_is_labeled_and_not_restorable_in_ui():
    common_js = (ROOT / "webui/static/js/modern/common.js").read_text(encoding="utf-8")
    email_js = (ROOT / "webui/static/js/modern/email.js").read_text(encoding="utf-8")

    assert "replaced:'换绑后邮箱'" in common_js
    assert "replaced: '换绑后邮箱'" in email_js
    assert "r.status !== 'replaced'" in email_js


def test_email_source_cards_default_to_enabled_and_dependency_sources():
    email_js = (ROOT / "webui/static/js/modern/email.js").read_text(encoding="utf-8")
    start = email_js.index("function _poolNoteCell")
    end = email_js.index("function renderButlerLeases", start)
    function_source = email_js[start:end]
    harness = r"""
const root = {innerHTML: '', parentNode: {insertBefore(node) { this.node = node; }}};
const POOL_SOURCE_LABELS = {outlook: 'Outlook 邮箱池', icloud_hide: 'iCloud 隐藏邮箱池'};
const controls = {
  id: 'mailSourceVisibilityControls', innerHTML: '',
  querySelector(selector) { return selector === '#btnShowDisabledMailSources' ? this.button : null; },
};
const targets = new Map([['#mailSourceCards', root]]);
function $(selector) { return targets.get(selector); }
function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
}
function attrEsc(value) { return esc(value); }
global.document = {
  getElementById(id) {
    if (id === 'mailSourceCards') return root;
    if (id === 'mailSourceVisibilityControls') return root.parentNode.node || null;
    return null;
  },
  createElement() {
    const node = {id: '', className: '', innerHTML: '', button: null, querySelector: controls.querySelector};
    return node;
  },
};
""" + function_source + r"""
renderMailSourceCards([
  {source: 'outlook', label: 'Outlook 邮箱池', kind: 'local_pool', enabled: false, total: 2, history_available: true, default_visible: false},
  {source: 'icloud_hide', label: 'iCloud 隐藏邮箱池', kind: 'local_pool', enabled: true, total: 1, default_visible: true},
  {source: 'email_butler', label: 'Email Butler', kind: 'on_demand', enabled: false, dependency: true, dependency_reason: '<script>alert(1)</script>', default_visible: true},
  {source: 'mailnest', label: '<img src=x onerror=alert(1)>', kind: 'on_demand', enabled: false, default_visible: false},
]);
if (!root.innerHTML.includes('iCloud 隐藏邮箱池') || !root.innerHTML.includes('Email Butler')) throw new Error('enabled/dependency source missing');
if (root.innerHTML.includes('Outlook 邮箱池') || root.innerHTML.includes('MailNest')) throw new Error('hidden source rendered by default');
const visibility = root.parentNode.node;
visibility.button = {addEventListener(_event, handler) { this.handler = handler; }};
visibility.querySelector = (selector) => selector === '#btnShowDisabledMailSources' ? visibility.button : null;
// 重新渲染会为新按钮绑定展开事件。
renderMailSourceCards([
  {source: 'outlook', label: 'Outlook 邮箱池', kind: 'local_pool', enabled: false, total: 2, history_available: true, default_visible: false},
  {source: 'icloud_hide', label: 'iCloud 隐藏邮箱池', kind: 'local_pool', enabled: true, total: 1, default_visible: true},
  {source: 'email_butler', label: 'Email Butler', kind: 'on_demand', enabled: false, dependency: true, dependency_reason: '<script>alert(1)</script>', default_visible: true},
  {source: 'mailnest', label: '<img src=x onerror=alert(1)>', kind: 'on_demand', enabled: false, default_visible: false},
]);
if (!visibility.button || typeof visibility.button.handler !== 'function') throw new Error('visibility toggle missing');
visibility.button.handler();
if (!root.innerHTML.includes('Outlook 邮箱池') || !root.innerHTML.includes('&lt;img src=x onerror=alert(1)&gt;')) throw new Error('show disabled did not reveal all sources');
if (!root.innerHTML.includes('历史/已停用') || !root.innerHTML.includes('未启用')) throw new Error('disabled labels missing');
if (root.innerHTML.includes('<img') || root.innerHTML.includes('<script>')) throw new Error('source metadata was not escaped');
if (!root.innerHTML.includes('&lt;script&gt;alert(1)&lt;/script&gt;')) throw new Error('dependency reason was not escaped');
console.log('ok');
"""
    result = subprocess.run(
        ["node", "--input-type=commonjs", "-e", harness],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.strip() == "ok"
