"""开源 Roxy 来源、提取边界和原函数一致性。"""
import ast
from pathlib import Path

from core.registration.roxy_oss.upstream import browser_helpers


VENDOR = Path(__file__).resolve().parents[1] / "core/registration/roxy_oss/upstream"
HELPERS = {
    "_email_entry_state", "_find_visible_email_input_js", "_is_oauth_consent_like",
    "_click_email_entry_option", "_is_profile_like", "_set_element_value",
    "_select_or_type", "_fill_birthday_or_age", "_accept_profile_consents",
}


def test_vendor_pins_public_repository_commit_and_license():
    manifest = (VENDOR / "UPSTREAM.md").read_text(encoding="utf-8")
    assert "myfanhua/turb-gpt-free-register" in manifest
    assert "9a0c55baa9b7d2f9c09ba6eea8cdec200a44eb5e" in manifest
    assert (VENDOR / "LICENSE").read_text(encoding="utf-8").startswith("MIT License")
    assert "不运行完整上游注册入口" in manifest


def test_running_helpers_match_the_fixed_upstream_functions():
    def functions(path):
        return {
            node.name: ast.dump(node, include_attributes=False)
            for node in ast.parse(path.read_text(encoding="utf-8")).body
            if isinstance(node, ast.FunctionDef)
        }

    original = functions(VENDOR / "roxy_registration.py")
    extracted = functions(VENDOR / "browser_helpers.py")
    assert extracted.keys() == HELPERS
    assert extracted == {name: original[name] for name in HELPERS}


def test_running_module_excludes_upstream_credentials_storage_and_lifecycle():
    for name in (
        "run_roxy_registration", "wait_for_otp", "acquire_email_after_input",
        "save_account_data", "_fill_password_page_if_present", "_type_otp",
        "RoxyBrowserClient", "_build_driver",
    ):
        assert not hasattr(browser_helpers, name), name
