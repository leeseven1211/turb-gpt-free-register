# -*- coding: utf-8 -*-
"""收件证据的完整地址匹配、HME 改写和母子隔离。"""
import unittest
import email
from email.message import EmailMessage

from core.email_recipients import candidate_match, extract_recipient_evidence


PARENT = "alias@icloud.com"
CHILD_A = "alias+a1b2c3@icloud.com"
CHILD_B = "alias+d4e5f6@icloud.com"


def hme_message(target=CHILD_A, *, displayed=PARENT):
    msg = EmailMessage()
    msg["To"] = displayed
    msg["X-ICLOUD-HME"] = PARENT
    msg["Delivered-To"] = "owner@gmail.com"
    if target:
        msg["Received"] = f"from outbound.mr.icloud.com by p00-icloudmta-asmtp-us-west-2a-100-percent-10 for <{target}>; Tue, 20 Oct 2026 01:00:00 +0000"
    return msg


class EmailRecipientEvidenceTests(unittest.TestCase):
    def test_hme_for_is_original_but_final_delivery_is_separate(self):
        msg = hme_message()
        evidence = extract_recipient_evidence(msg)
        self.assertEqual(evidence["original_recipients"], [CHILD_A])
        self.assertEqual(evidence["displayed_recipients"], [PARENT])
        self.assertEqual(evidence["forwarding_destinations"], ["owner@gmail.com"])
        self.assertTrue(candidate_match(CHILD_A, msg, forwarded=True))
        self.assertFalse(candidate_match(CHILD_B, msg, forwarded=True))
        self.assertFalse(candidate_match(PARENT, msg, forwarded=True))

    def test_folded_received_header_is_parsed_without_scanning_unrelated_text(self):
        msg = email.message_from_string(
            f"To: {PARENT}\nReceived: from sender.example\n"
            f" by p00-icloudmta-asmtp-us-west-2a-100-percent-10\n"
            f" for <{CHILD_A}>; Tue, 20 Oct 2026 01:00:00 +0000\n\n"
        )
        self.assertTrue(candidate_match(CHILD_A, msg, forwarded=True))
        self.assertFalse(candidate_match(PARENT, msg, forwarded=True))

    def test_received_sender_email_is_not_a_recipient(self):
        msg = hme_message(None)
        msg["Received"] = f"from sender.example ({CHILD_A}) by mx.icloud.com; Tue, 20 Oct 2026 01:00:00 +0000"
        self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))
        self.assertEqual(extract_recipient_evidence(msg)["original_recipients"], [])

    def test_received_for_in_comments_is_not_a_recipient(self):
        msg = hme_message(None)
        msg["Received"] = f"from sender.example (for <{CHILD_A}>) by mx.icloud.com; Tue, 20 Oct 2026 01:00:00 +0000"
        self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))

    def test_untrusted_hop_does_not_prove_hme_child(self):
        msg = hme_message(None)
        msg["Received"] = f"from sender.example by not-icloud.example for <{CHILD_A}>; Tue, 20 Oct 2026 01:00:00 +0000"
        self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))
        self.assertEqual(extract_recipient_evidence(msg)["original_recipients"], [])

    def test_conflicting_original_siblings_never_fall_back_to_to(self):
        msg = hme_message(displayed=CHILD_A)
        msg["Received"] = f"from sender.example by mx.icloud.com for <{CHILD_B}>; Tue, 20 Oct 2026 01:00:00 +0000"
        for target in (PARENT, CHILD_A, CHILD_B):
            self.assertFalse(candidate_match(target, msg, forwarded=True))

    def test_original_parent_and_child_conflict_is_not_resolved_by_latest(self):
        msg = hme_message()
        msg["X-Original-To"] = PARENT
        self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))
        self.assertFalse(candidate_match(PARENT, msg, forwarded=True))

    def test_full_hme_child_to_requires_same_hme_family_without_for(self):
        msg = hme_message(None, displayed=CHILD_A)
        self.assertTrue(candidate_match(CHILD_A, msg, forwarded=True))
        self.assertFalse(candidate_match(CHILD_B, msg, forwarded=True))
        self.assertFalse(candidate_match(PARENT, msg, forwarded=True))
        msg.replace_header("X-ICLOUD-HME", "another@icloud.com")
        self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))

    def test_to_rewritten_to_parent_cannot_prove_child(self):
        msg = hme_message(None)
        self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))
        self.assertTrue(candidate_match(PARENT, msg, forwarded=True))
        self.assertFalse(candidate_match(PARENT, msg, forwarded=True, strict_family=True))

    def test_strict_family_accepts_original_parent(self):
        msg = hme_message(PARENT)
        self.assertTrue(candidate_match(PARENT, msg, forwarded=True, strict_family=True))

    def test_received_with_duplicate_for_clauses_is_rejected(self):
        msg = hme_message(None)
        msg["Received"] = f"by mx.icloud.com for <{CHILD_A}> for <{CHILD_B}>; Tue, 20 Oct 2026 01:00:00 +0000"
        self.assertEqual(extract_recipient_evidence(msg)["original_recipients"], [])

    def test_direct_to_and_cc_use_complete_addr_specs(self):
        item = {"to": "Another <prefixalias+a1b2c3@icloud.com>", "cc": f"Name <{CHILD_A}>"}
        self.assertTrue(candidate_match(CHILD_A.upper(), item))
        self.assertFalse(candidate_match(PARENT, item))
        self.assertFalse(candidate_match(CHILD_B, item))

    def test_graph_and_legacy_rest_fields_preserve_recipients(self):
        for key, address_key in (("toRecipients", "emailAddress"), ("ToRecipients", "EmailAddress")):
            item = {key: [{address_key: {"address": CHILD_A}}]}
            self.assertTrue(candidate_match(CHILD_A, item))
            self.assertFalse(candidate_match(PARENT, item))

    def test_missing_direct_evidence_is_not_a_match(self):
        self.assertFalse(candidate_match(CHILD_A, {"subject": "Your code is 123456"}))
        self.assertFalse(candidate_match(PARENT, {"subject": "Your code is 123456"}))

    def test_unrelated_original_recipients_keep_legacy_bulk_behavior(self):
        msg = EmailMessage()
        msg["To"] = "owner@gmail.com"
        msg["X-Original-To"] = PARENT
        msg["X-Original-To"] = "another@icloud.com"
        self.assertTrue(candidate_match(PARENT, msg, forwarded=True))
        self.assertTrue(candidate_match("another@icloud.com", msg, forwarded=True))
