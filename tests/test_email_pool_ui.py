from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_replaced_email_status_is_labeled_and_not_restorable_in_ui():
    common_js = (ROOT / "webui/static/js/modern/common.js").read_text(encoding="utf-8")
    email_js = (ROOT / "webui/static/js/modern/email.js").read_text(encoding="utf-8")

    assert "replaced:'换绑后邮箱'" in common_js
    assert "replaced: '换绑后邮箱'" in email_js
    assert "r.status !== 'replaced'" in email_js
