"""Oracle 实际入库解析器的脱敏基线和多语言回归，不连接邮件或数据库。"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import types
import unittest
import unicodedata
from email.message import EmailMessage
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "tests/fixtures/mail_pipeline_parse_baseline.py.txt"
SAMPLES = {
    "简体中文": "您的验证码为：123456",
    "繁体中文": "您的驗證碼為：123456",
    "英语": "Your verification code is 123456",
    "越南语验证": "Mã xác minh của bạn là 123456",
    "越南语认证": "Mã xác thực của bạn là 123456",
    "越南语实际主题": "Mã đăng nhập ChatGPT tạm thời của bạn: 123456",
    "日语": "認証コードは123456です。",
    "日语确认": "確認コード：123456",
    "韩语": "인증 코드는 123456입니다.",
    "法语": "Votre code de vérification est : 123456",
    "法语弯引号": "Votre code d’authentification est : 123456",
    "德语": "Dein Bestätigungscode lautet 123456",
    "德语安全": "Ihr Sicherheitscode: 123456",
    "西班牙语": "Tu código de verificación es 123456",
    "葡萄牙语": "Seu código de verificação é 123456",
    "意大利语": "Il tuo codice di verifica è 123456",
    "荷兰语": "Uw verificatiecode is 123456",
    "波兰语": "Twój kod weryfikacyjny to 123456",
    "土耳其语": "Doğrulama kodunuz: 123456",
    "俄语": "Ваш код подтверждения: 123456",
    "乌克兰语": "Ваш код підтвердження: 123456",
    "捷克语": "Váš ověřovací kód je 123456",
    "罗马尼亚语": "Codul de verificare este 123456",
    "匈牙利语": "Az ellenőrző kód: 123456",
    "希腊语": "Ο κωδικός επαλήθευσης είναι 123456",
    "瑞典语": "Din verifieringskod är 123456",
    "挪威语": "Din bekreftelseskode er 123456",
    "丹麦语": "Din bekræftelseskode er 123456",
    "芬兰语": "Vahvistuskoodisi on 123456",
    "印尼语": "Kode verifikasi Anda adalah 123456",
    "马来语": "Kod pengesahan anda ialah 123456",
    "泰语": "รหัสยืนยันของคุณคือ 123456",
    "印地语": "आपका सत्यापन कोड है 123456",
    "印地语借词": "जारी रखने के लिए ये टेम्पररी वेरिफिकेशन कोड डालें: 123456",
    "印地语借词含nukta": "जारी रखने के लिए ये टेम्पररी वेरिफ़िकेशन कोड डालें: 123456",
    "阿拉伯语": "رمز التحقق الخاص بك هو \u200f123456\u200f",
    "希伯来语": "קוד האימות שלך הוא 123456",
    "菲律宾语": "Ang iyong verification code ay 123456",
}


def load_parser():
    override = os.environ.get("MAIL_PIPELINE_PARSE_SOURCE")
    source = Path(override).read_text() if override else BASELINE.read_text()
    if not override:
        from tools.maintenance.prepare_mail_pipeline_otp_patch import prepare_source
        source = prepare_source(source)
    module = types.ModuleType("mail_pipeline_parse_under_test")
    exec(compile(source, str(BASELINE), "exec"), module.__dict__)
    return module


class MailPipelineOtpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = load_parser()

    def test_language_templates_in_subject_and_body(self):
        for language, text in SAMPLES.items():
            for subject, body in ((text, ""), ("", text)):
                with self.subTest(language=language, subject=bool(subject)):
                    self.assertEqual(self.parser.extract_code_candidates(subject, body), ["123456"])

    def test_decomposed_unicode_and_mime(self):
        for language in ("越南语验证", "法语", "韩语", "印地语借词含nukta"):
            with self.subTest(language=language):
                message = EmailMessage()
                message["Subject"] = unicodedata.normalize("NFD", SAMPLES[language])
                message.set_content("<html><body>" + unicodedata.normalize("NFD", SAMPLES[language]) + "</body></html>", subtype="html", cte="base64")
                parsed = self.parser.BytesParser(policy=self.parser.policy.default).parsebytes(message.as_bytes())
                self.assertEqual(self.parser.extract_otp(str(parsed["Subject"]), self.parser.text_body(parsed)), "123456")

    def test_plain_mail_numbers_are_not_codes(self):
        samples = (
            ("订单确认", "订单号 123456，金额 1234 元，邮编 654321。"),
            ("Thông tin đơn hàng", "Mã đơn hàng: 123456. Giá: 654321 VND."),
            ("ご注文の確認", "注文番号 123456、郵便番号 654321"),
            ("주문 확인", "주문 번호 123456, 우편번호 654321"),
            ("Reçu de commande", "Code postal 123456, commande 654321."),
            ("Invoice", "Paid 123456. Ticket 654321. 2026-10-28."),
            ("वेरिफिकेशन स्थिति", "ऑर्डर नंबर 123456"),
            ("Mã giảm giá", "Mã giảm giá: 123456"),
            ("Votre code postal", "Code postal : 123456"),
            ("Mã nguồn ChatGPT", "Mã nguồn ChatGPT phiên bản 123456"),
            ("Utilisez le code OpenAI 123456 pour obtenir une remise de 20 %.", ""),
            ("Votre code ChatGPT 123456", "Remise 20 %. Unsubscribe."),
            ("Dein ChatGPT-Code lautet 123456", "Rabatt 20 %. Unsubscribe."),
            ("Codice di sconto", "Codice di sconto 123456"),
            ("Verification tutorial newsletter", "Example verification code: 123456. Unsubscribe."),
            ("Weekly digest", "Mã xác minh của bạn là 123456. Unsubscribe."),
            ("Weekly digest", "認証コードは123456です。 Unsubscribe."),
            ("Security update", "Your verification code: https://example.test/123456"),
            ("Your verification code", "123456789"),
            ("Your verification code", "hello123456world"),
            ("Your verification code", "PASSWORD"),
            ("Your verification code", "Use this in 10 minutes. Order: 123456"),
            ("رمز التحقق", "١٢٣٤٥٦"),
        )
        for subject, body in samples:
            with self.subTest(subject=subject):
                self.assertEqual(self.parser.extract_code_candidates(subject, body), [])

    def test_existing_code_formats_and_deduplication(self):
        for value, expected in (("123-456", "123456"), ("123 456", "123456"), ("AB12CD", "AB12CD")):
            with self.subTest(value=value):
                self.assertEqual(self.parser.extract_otp("Your security code", value), expected)
        self.assertEqual(self.parser.extract_code_candidates("OTP: 123456", "OTP: 123456"), ["123456"])

    def test_intervening_words_cannot_consume_the_real_code(self):
        for text in ("Your verification code will be 123456", "Your verification code: HERE 123456", "Your code: ABC DEF 123456"):
            with self.subTest(text=text):
                self.assertEqual(self.parser.extract_code_candidates("", text), ["123456"])
        self.assertEqual(self.parser.extract_code_candidates("OTP", "ABC-DEF"), [])

    def test_trusted_header_and_recipient_helpers_remain_available(self):
        message = EmailMessage()
        message["From"] = "noreply@openai.com"
        message["To"] = "alias@example.test"
        self.assertEqual(self.parser.openai_sender(message), "noreply@openai.com")
        self.assertEqual(self.parser.recipients(message), ["alias@example.test"])


class OtpPatchPreparationTest(unittest.TestCase):
    def test_upgrade_previous_deployed_parser_preserves_drift_protection(self):
        from tools.maintenance.prepare_mail_pipeline_otp_patch import PreparationError, prepare_source
        modified = prepare_source(BASELINE.read_text())
        previous = modified.replace("|वेरिफ़?िकेशन", "")
        self.assertEqual(hashlib.sha256(previous.encode()).hexdigest(),
                         "0244461e4e5aea5253056b05ef31574898c9e4e4a73cba384c47ad323756de04")
        for source in (previous, previous[:-1]):
            with self.subTest(ending=repr(source[-3:])):
                try:
                    upgraded = prepare_source(source)
                except PreparationError:
                    self.fail("已审计的上一部署版本应能升级")
                self.assertEqual(upgraded, modified)
                with self.assertRaises(PreparationError):
                    prepare_source(source + "# 未审计改动\n")

    def test_idempotence_and_source_drift(self):
        from tools.maintenance.prepare_mail_pipeline_otp_patch import PreparationError, prepare_source
        original = BASELINE.read_text()
        modified = prepare_source(original)
        self.assertNotEqual(modified, original)
        self.assertEqual(prepare_source(modified), modified)
        for source in (original + "# drift\n", modified + "# drift\n", original.replace("import re", "import re\nimport re"), original.replace("\n", "\r\n")):
            with self.subTest(length=len(source)), self.assertRaises(PreparationError):
                prepare_source(source)

    def test_cli_writes_new_file_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "parse.py"
            command = [sys.executable, str(ROOT / "tools/maintenance/prepare_mail_pipeline_otp_patch.py"), "--source", str(BASELINE), "--output", str(target)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            prepared = target.read_bytes()
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_bytes(), prepared)
            self.assertIn("otp_parser_prepare_failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
