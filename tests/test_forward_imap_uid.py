"""转发 IMAP 使用稳定 UID，并批量读取只读扫描邮件。"""
import unittest
from email.message import EmailMessage

from core import forward_imap_client as client


def message(uid, target="alias@icloud.com", code="012345"):
    item = EmailMessage()
    item["From"] = "OpenAI <noreply@openai.com>"
    item["To"] = target
    item["Subject"] = f"Your ChatGPT code is {code}"
    item.set_content(f"Your code is {code}")
    return (f'7 (UID {uid} INTERNALDATE "10-Oct-2026 12:00:00 +0000" BODY[] {{1}}'.encode(), item.as_bytes())


class UidMail:
    def __init__(self, ids, messages):
        self.ids = ids
        self.messages = messages
        self.fetches = []
        self.searches = []

    def noop(self):
        return "OK", []

    def uid(self, command, *args):
        if command == "search":
            self.searches.append(args)
            return "OK", [b" ".join(str(uid).encode() for uid in self.ids)]
        self.fetches.append(args)
        selected = args[0].split(b",")
        # 服务端响应顺序与请求顺序不同，且可省略已被删除的邮件。
        return "OK", [self.messages[int(uid)] for uid in sorted(selected, key=int) if int(uid) in self.messages]


class ForwardImapUidTests(unittest.TestCase):
    def test_bulk_uid_fetch_survives_deletion_and_does_not_mix_aliases(self):
        mail = UidMail([10, 11, 12], {10: message(10), 12: message(12, "other@icloud.com")})
        result = client._messages_for_recipients(mail, {"alias@icloud.com", "other@icloud.com"}, 0)
        self.assertEqual([row[2] for row in result["alias@icloud.com"]], ["10"])
        self.assertEqual([row[2] for row in result["other@icloud.com"]], ["12"])
        self.assertEqual(mail.fetches, [(b"12,11,10", "(UID INTERNALDATE BODY.PEEK[])")])
        self.assertEqual(len(mail.searches), 4)
        self.assertTrue(all("01-Jan-1970" in call[1] for call in mail.searches))

    def test_otp_keeps_progressive_early_exit_with_uid(self):
        mail = UidMail([10, 12, 11], {12: message(12)})
        self.assertEqual(client._latest_forwarded_otp(mail, "alias@icloud.com", 0), "012345")
        self.assertEqual(mail.fetches, [(b"12", "(INTERNALDATE BODY.PEEK[])")])

    def test_bulk_reads_are_bounded_and_keep_newest_order(self):
        mail = UidMail(list(range(1, 42)), {uid: message(uid) for uid in range(1, 42)})
        result = client._messages_for_recipients(mail, {"alias@icloud.com"}, 0)
        self.assertEqual([row[2] for row in result["alias@icloud.com"]], [str(uid) for uid in range(41, 0, -1)])
        self.assertEqual([len(call[0].split(b",")) for call in mail.fetches], [20, 20, 1])

    def test_failed_bulk_read_is_not_treated_as_empty_mailbox(self):
        class FailedMail(UidMail):
            def uid(self, command, *args):
                return ("NO", []) if command == "fetch" else super().uid(command, *args)

        with self.assertRaises(client.ForwardIMAPError):
            client._messages_for_recipients(FailedMail([1], {}), {"alias@icloud.com"}, 0)

    def test_uid_and_delivery_date_after_body_literal_are_respected(self):
        class SuffixMail(UidMail):
            def uid(self, command, *args):
                if command == "fetch":
                    return "OK", [(b"7 (BODY[] {1}", message(12)[1]),
                                  b' UID 12 INTERNALDATE "10-Oct-2026 12:00:00 +0000")']
                return super().uid(command, *args)

        result = client._messages_for_recipients(SuffixMail([12], {}), {"alias@icloud.com"}, 0)
        self.assertEqual(result["alias@icloud.com"][0][2], "12")
        self.assertEqual(result["alias@icloud.com"][0][0]["receivedDateTime"], "2026-10-10T12:00:00Z")
