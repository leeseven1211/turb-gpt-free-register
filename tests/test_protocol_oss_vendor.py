from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "core" / "registration" / "protocol_oss" / "upstream"


def test_vendor_manifest_pins_repository_commit_and_mit_license():
    manifest = (VENDOR / "UPSTREAM.md").read_text(encoding="utf-8")
    license_text = (VENDOR / "LICENSE").read_text(encoding="utf-8")

    assert "myfanhua/turb-gpt-free-register" in manifest
    assert "83721dc33a83b3e09dfdf7d91cc511b0124d9b4c" in manifest
    assert "MIT" in manifest
    assert license_text.startswith("MIT License")


def test_vendor_snapshot_contains_only_the_registration_protocol_sources():
    expected = (
        VENDOR / "main.py",
        VENDOR / "core" / "chatgpt_auth.py",
        VENDOR / "core" / "openai_auth.py",
        VENDOR / "config" / "openai_protocol.py",
    )
    missing = [str(path.relative_to(ROOT)) for path in expected if not path.is_file()]

    assert not missing, f"缺少固定上游协议文件: {missing}"
    assert "def run_registration(" in expected[0].read_text(encoding="utf-8")


def test_vendor_auth_helpers_import_from_the_isolated_snapshot():
    from core.registration.protocol_oss.upstream.core import chatgpt_auth, openai_auth

    assert callable(chatgpt_auth.signin_openai)
    assert callable(openai_auth.register_user)
    assert "protocol_oss/upstream" in chatgpt_auth.__file__.replace("\\", "/")
    assert "protocol_oss/upstream" in openai_auth.__file__.replace("\\", "/")
