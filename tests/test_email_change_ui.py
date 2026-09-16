from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_email_change_entrypoint_and_protocol_modal_are_present_in_both_ui_variants():
    modern = (ROOT / "webui/static/js/modern/accounts.js").read_text(encoding="utf-8")
    legacy = (ROOT / "webui/static/js/legacy/accounts.js").read_text(encoding="utf-8")
    modern_template = (ROOT / "webui/templates/index.html").read_text(encoding="utf-8")
    legacy_template = (ROOT / "webui/templates/index_legacy.html").read_text(encoding="utf-8")

    for source in (modern, legacy):
        assert "data-account-email-change" in source
        assert "/email-change" in source
        assert "email_source" in source
        assert "不会启动浏览器" in source

    for template in (modern_template, legacy_template):
        assert 'id="emailChangeModal"' in template
        assert 'id="emailChangeTarget"' in template
        assert 'id="emailChangeSource"' in template
        assert 'id="emailChangeForm"' in template


def test_modern_task_center_labels_email_change_and_protocol_steps():
    common = (ROOT / "webui/static/js/modern/common.js").read_text(encoding="utf-8")
    accounts = (ROOT / "webui/static/js/modern/accounts.js").read_text(encoding="utf-8")

    assert "email_change:'换绑邮箱'" in common
    assert "email_change_begin:'提交换绑请求'" in common
    assert "email_change_verify:'验证换绑验证码'" in common
    assert "'email_change'" in accounts
    assert "typeFilter.value = 'email_change'" in accounts
