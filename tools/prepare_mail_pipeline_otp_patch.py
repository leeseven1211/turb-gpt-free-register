#!/usr/bin/env python3
"""为 Oracle 已审计的独立 mail-pipeline 生成多语言取码源码，不连接生产数据。"""
from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
from pathlib import Path


BASELINE_SHA256 = "2c4531ee7fb51920744ede6aec4eb2cb1b135cb1c21db550e646974a6b3186b6"
ORIGINAL_MARKER = '''MARKER = (
    r"(?:验证码|校验码|验证代码|动态码|一次性(?:密码|代码)|安全代码|登录代码|确认代码|"
    r"(?:verification|security|login|authentication|auth)\\s+(?:code|password)|"
    r"one[-\\s]?time\\s+(?:code|password)|(?:2fa|otp)\\b)"
)'''

# 只添加完整的验证/登录语义，不把产品名加普通 code 当作 OTP。
MULTILINGUAL_MARKER = '''MARKER = (
    r"(?:验证码|校验码|验证代码|动态码|一次性(?:密码|代码)|安全代码|登录代码|确认代码|"
    r"驗證碼|校驗碼|驗證代碼|動態碼|一次性(?:密碼|代碼)|安全代碼|登入代碼|確認代碼|"
    r"(?:verification|security|login|authentication|auth)\\s+(?:code|password)|"
    r"one[-\\s]?time\\s+(?:code|password)|(?:2fa|otp)\\b|"
    # 越南语及东亚语言，不能单独匹配 mã。
    r"mã\\s+(?:xác\\s+(?:minh|thực)|đăng\\s+nhập|bảo\\s+mật|dùng\\s+một\\s+lần)|"
    r"(?:認証|確認|検証|セキュリティ|ワンタイム)\\s*コード|"
    r"(?:인증|확인|보안|로그인|일회용)\\s*코드|"
    # 西欧语言保留重音和自然词序。
    r"code\\s+(?:de\\s+(?:vérification|connexion|sécurité)|d['’]authentification)|"
    r"(?:Bestätigungs|Verifizierungs|Authentifizierungs|Sicherheits|Anmelde|Einmal)code|"
    r"código\\s+(?:(?:de|do)\\s+)?(?:verificación|verificação|autenticación|autenticação|"
    r"seguridad|segurança|acceso|acesso)|"
    r"codice\\s+di\\s+(?:verifica|autenticazione|sicurezza|accesso)|"
    r"(?:verificatie|bevestigings|beveiligings|inlog|eenmalige)code|"
    # 中东欧、北欧语言。
    r"kod\\s+(?:weryfikacyjny|potwierdzający|logowania|bezpieczeństwa)|"
    r"(?:doğrulama|güvenlik|giriş)\\s+kodu(?:nuz)?|"
    r"код\\s+(?:подтверждения|проверки|входа|безопасности|підтвердження|перевірки|входу|безпеки)|"
    r"(?:ověřovací|potvrzovací|bezpečnostní|přihlašovací)\\s+kód|"
    r"cod(?:ul)?\\s+de\\s+(?:verificare|autentificare|securitate)|"
    r"(?:ellenőrző|megerősítő|biztonsági|bejelentkezési)\\s+kód|"
    r"κωδικός\\s+(?:επαλήθευσης|επιβεβαίωσης|ασφαλείας|σύνδεσης)|"
    r"(?:verifierings|bekräftelse|säkerhets|inloggnings|bekreftelses|verifiserings|"
    r"sikkerhets|påloggings|bekræftelses|sikkerheds|engangs)kode?|"
    r"(?:vahvistus|varmennus|turva|kirjautumis)koodi(?:si)?|"
    # 东南亚、南亚及从右向左书写的语言；数字字形仍遵循现有代码规则。
    r"kode\\s+(?:verifikasi|autentikasi|keamanan|masuk|sekali\\s+pakai)|"
    r"kod\\s+(?:pengesahan|keselamatan|log\\s+masuk|sekali\\s+guna)|"
    r"รหัส\\s*(?:ยืนยัน(?:ตัวตน)?|ตรวจสอบ|ความปลอดภัย|เข้าสู่ระบบ|ใช้ครั้งเดียว)|"
    r"(?:सत्यापन|पुष्टि|सुरक्षा|प्रमाणीकरण|लॉगिन)\\s*कोड|"
    r"رمز\\s+(?:التحقق|التأكيد|المصادقة|الأمان|تسجيل\\s+الدخول)|"
    r"קוד\\s+(?:האימות|אימות|אבטחה|התחברות)|"
    r"(?:verification|beripikasyon)\\s+(?:code|kodigo))"
)'''

# 数字必须位于同一个候选码内，不能借用后面单词/数字满足前瞻后吞掉提示词。
ORIGINAL_CODE_TOKEN = 'CODE_TOKEN = r"((?=[A-Z0-9 -]{0,10}\\d)(?:[A-Z0-9]{4,8}|[A-Z0-9]{3}(?:[-\\s][A-Z0-9]{3})))"'
STRICT_CODE_TOKEN = 'CODE_TOKEN = r"((?=[A-Z0-9]{0,7}\\d)[A-Z0-9]{4,8}|(?=[A-Z0-9 -]{0,6}\\d)[A-Z0-9]{3}[-\\s][A-Z0-9]{3})"'

REPLACEMENTS = (
    ("import re\n", "import re\nimport unicodedata\n"),
    (ORIGINAL_MARKER, MULTILINGUAL_MARKER),
    (ORIGINAL_CODE_TOKEN, STRICT_CODE_TOKEN),
    ('    subject = str(subject or "")\n',
     '    subject = unicodedata.normalize("NFC", str(subject or ""))\n'),
    ('    body = re.sub(r"https?://\\S+", " ", str(body or ""))\n',
     '    body = re.sub(r"https?://\\S+", " ", unicodedata.normalize("NFC", str(body or "")))\n'),
)


class PreparationError(ValueError):
    """输入源码不属于已审计版本。"""


def _replace_once(source: str, before: str, after: str) -> str:
    if source.count(before) != 1:
        raise PreparationError("otp_parser_source_unsupported: 补丁定位点缺失或重复")
    return source.replace(before, after, 1)


def prepare_source(source: str) -> str:
    """只接受完整基线或本工具已生成的相同版本；未知漂移拒绝覆盖。"""
    if hashlib.sha256(source.encode()).hexdigest() != BASELINE_SHA256:
        original = source
        for before, after in reversed(REPLACEMENTS):
            original = _replace_once(original, after, before)
        if hashlib.sha256(original.encode()).hexdigest() != BASELINE_SHA256:
            raise PreparationError("otp_parser_source_unsupported: 源码 SHA256 不属于已审计基线")
        return source
    for before, after in REPLACEMENTS:
        source = _replace_once(source, before, after)
    ast.parse(source)
    return source


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="写入新的源码文件；不覆盖已有文件")
    args = parser.parse_args()
    try:
        original = args.source.read_bytes().decode("utf-8")
        modified = prepare_source(original)
        if args.output:
            with args.output.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(modified)
        else:
            print("".join(difflib.unified_diff(original.splitlines(True), modified.splitlines(True),
                                             fromfile="a/parse.py", tofile="b/parse.py")), end="")
    except (OSError, UnicodeError, PreparationError) as exc:
        parser.exit(1, f"otp_parser_prepare_failed: {exc}\n")


if __name__ == "__main__":
    main()
