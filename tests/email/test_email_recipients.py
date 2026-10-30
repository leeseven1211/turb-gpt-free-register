# -*- coding: utf-8 -*-
"""收件证据的完整地址匹配、HME 改写和母子隔离。"""
import unittest
import email
from email.message import EmailMessage

from core.email.recipients import candidate_match, extract_recipient_evidence


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


class OpenAISendGridSPFRecipientTests(unittest.TestCase):
    def envelope(self, recipient=CHILD_A, *, bounce_domain="em7877.tm.openai.com"):
        return f"bounces+1234567-a1b2-{recipient.replace('@', '=')}@{bounce_domain}"

    def message(self, recipient=CHILD_A, *, verdict="pass", authority="spf.icloud.com", domain="em7877.tm.openai.com"):
        msg = hme_message(None)
        msg["Authentication-Results"] = f"{authority}; spf={verdict} smtp.mailfrom={self.envelope(recipient, bounce_domain=domain)}"
        return msg

    def test_same_spf_pass_clause_restores_full_original_child(self):
        msg = self.message()
        evidence = extract_recipient_evidence(msg)
        self.assertEqual(evidence["original_recipients"], [CHILD_A])
        self.assertEqual(evidence["sources"], [{"kind": "openai_icloud_spf_verp", "addresses": [CHILD_A]}])
        self.assertTrue(candidate_match(CHILD_A, msg, forwarded=True))
        self.assertFalse(candidate_match(CHILD_B, msg, forwarded=True))
        self.assertFalse(candidate_match(PARENT, msg, forwarded=True))

    def test_spf_verp_can_prove_parent_for_strict_original_account(self):
        self.assertTrue(candidate_match(PARENT, self.message(PARENT), forwarded=True, strict_family=True))

    def test_full_local_and_domain_are_required_not_just_tag_substring(self):
        for other in (CHILD_A.replace("+a1b2c3", "+a1b2c3x"), "other+a1b2c3@icloud.com", CHILD_A.replace("icloud.com", "icloud.com.evil.test")):
            with self.subTest(recipient=other):
                self.assertFalse(candidate_match(CHILD_A, self.message(other), forwarded=True))

    def test_different_verified_siblings_are_conflicting_original_evidence(self):
        msg = self.message()
        msg["Authentication-Results"] = f"spf.icloud.com; spf=pass smtp.mailfrom={self.envelope(CHILD_B)}"
        for target in (PARENT, CHILD_A, CHILD_B):
            self.assertFalse(candidate_match(target, msg, forwarded=True))

    def test_conflicting_spf_verdicts_cannot_fall_back_to_displayed_child(self):
        for displayed in (PARENT, CHILD_A):
            for other, verdict in ((CHILD_B, "fail"), (CHILD_B, "softfail"), (CHILD_A, "fail")):
                msg = self.message()
                msg.replace_header("To", displayed)
                msg["Authentication-Results"] = f"spf.icloud.com; spf={verdict} smtp.mailfrom={self.envelope(other)}"
                with self.subTest(displayed=displayed, other=other, verdict=verdict):
                    for target in (PARENT, CHILD_A, CHILD_B):
                        self.assertFalse(candidate_match(target, msg, forwarded=True))

    def test_repeated_consistent_spf_pass_is_supported(self):
        msg = self.message()
        msg["Authentication-Results"] = f"spf.icloud.com; spf=pass smtp.mailfrom={self.envelope()}"
        self.assertTrue(candidate_match(CHILD_A, msg, forwarded=True))

    def test_explicit_hme_child_must_equal_provider_recipient(self):
        msg = self.message()
        msg.replace_header("X-ICLOUD-HME", CHILD_A)
        self.assertTrue(candidate_match(CHILD_A, msg, forwarded=True))
        msg.replace_header("X-ICLOUD-HME", CHILD_B)
        for displayed in (PARENT, CHILD_A):
            msg.replace_header("To", displayed)
            for target in (PARENT, CHILD_A, CHILD_B):
                self.assertFalse(candidate_match(target, msg, forwarded=True))

    def test_provider_and_received_conflict_never_fall_back(self):
        msg = self.message()
        msg["Received"] = f"by mx.icloud.com for <{CHILD_B}>; Tue, 20 Oct 2026 01:00:00 +0000"
        self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))
        self.assertFalse(candidate_match(CHILD_B, msg, forwarded=True))

    def test_authority_and_bounce_domains_are_anchored(self):
        for authority in ("spf.icloud.com.evil.test", "prefix.spf.icloud.com", "attacker.example (spf.icloud.com)"):
            with self.subTest(authority=authority):
                self.assertFalse(candidate_match(CHILD_A, self.message(authority=authority), forwarded=True))
        for domain in ("em7877.tm.openai.com.evil.test", "evil-em7877.tm.openai.com", "tm.openai.com", "em7877.openai.com", "sendgrid.net"):
            with self.subTest(domain=domain):
                self.assertFalse(candidate_match(CHILD_A, self.message(domain=domain), forwarded=True))

    def test_missing_or_wrong_hme_family_rejects_provider_evidence(self):
        msg = self.message()
        del msg["X-ICLOUD-HME"]
        self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))
        msg["X-ICLOUD-HME"] = "another@icloud.com"
        self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))

    def test_real_hme_parameter_header_only_uses_parent_field(self):
        msg = self.message()
        msg.replace_header("X-ICLOUD-HME", f"p={PARENT}; d=1; f=owner@gmail.com; s=sender@example.test")
        self.assertEqual(extract_recipient_evidence(msg)["hme_recipients"], [PARENT])
        self.assertTrue(candidate_match(CHILD_A, msg, forwarded=True))
        self.assertFalse(candidate_match(PARENT, msg, forwarded=True, strict_family=True))

    def test_folded_hme_parent_parameter_is_supported(self):
        msg = email.message_from_string(
            f"To: {PARENT}\nX-ICLOUD-HME: p={PARENT};\n"
            " d=1; f=owner@gmail.com; s=sender@example.test\n"
            f"Authentication-Results: spf.icloud.com; spf=pass smtp.mailfrom={self.envelope()}\n\n"
        )
        self.assertTrue(candidate_match(CHILD_A, msg, forwarded=True))

    def test_hme_forwarding_sender_comments_and_quoted_text_are_not_parent_evidence(self):
        values = [
            f"p=another@icloud.com; d=1; f={PARENT}; s={PARENT}",
            f"d=1; f={PARENT}; s=sender@example.test",
            f'd=1; s="text; p={PARENT}"',
            f"d=1 (p={PARENT}); f=owner@gmail.com",
            f"p={PARENT}; p=another@icloud.com; f=owner@gmail.com",
            f"p={PARENT},another@icloud.com; d=1",
        ]
        for value in values:
            msg = self.message()
            msg.replace_header("X-ICLOUD-HME", value)
            with self.subTest(value=value):
                self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))

    def test_multiple_hme_headers_require_one_consistent_parent(self):
        msg = self.message()
        msg.replace_header("X-ICLOUD-HME", f"p={PARENT}; d=1")
        msg["X-ICLOUD-HME"] = f"p={PARENT}; d=1"
        self.assertTrue(candidate_match(CHILD_A, msg, forwarded=True))
        msg["X-ICLOUD-HME"] = "p=another@icloud.com; d=1"
        self.assertEqual(extract_recipient_evidence(msg)["hme_recipients"], [])
        self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))

    def test_legacy_hme_value_must_be_one_entire_addr_spec(self):
        for value in (f"other@icloud.com, {PARENT}", f"unknown: {PARENT}", f"Name <{PARENT}>", f"{PARENT} (metadata)"):
            msg = self.message()
            msg.replace_header("X-ICLOUD-HME", value)
            with self.subTest(value=value):
                self.assertEqual(extract_recipient_evidence(msg)["hme_recipients"], [])
                self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))

    def test_spf_fail_cannot_borrow_dkim_or_another_clause_pass(self):
        values = [
            f"spf.icloud.com; spf=fail smtp.mailfrom={self.envelope()}; dkim=pass header.d=tm.openai.com",
            f"spf.icloud.com; spf=pass; spf=fail smtp.mailfrom={self.envelope()}",
            f"spf.icloud.com; spf=pass smtp.mailfrom=ordinary@example.test; spf=fail smtp.mailfrom={self.envelope()}",
            f"spf.icloud.com; spf=pass dkim=fail smtp.mailfrom={self.envelope()}",
            f"spf.icloud.com; spf=pass dmarc=pass smtp.mailfrom={self.envelope()}",
            f"spf.icloud.com; spf=pass auth=fail smtp.mailfrom={self.envelope()}",
            f"spf.icloud.com; spf=pass futuremethod=pass smtp.mailfrom={self.envelope()}",
        ]
        for value in values:
            msg = hme_message(None)
            msg["Authentication-Results"] = value
            with self.subTest(value=value):
                self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))

    def test_comments_cannot_create_pass_or_mailfrom_evidence(self):
        values = [
            f"spf.icloud.com; spf=fail (spf=pass) smtp.mailfrom={self.envelope()}",
            f"spf.icloud.com; spf=pass (smtp.mailfrom={self.envelope()})",
            f"spf.icloud.com; (spf=pass smtp.mailfrom={self.envelope()}); spf=fail",
        ]
        for value in values:
            msg = hme_message(None)
            msg["Authentication-Results"] = value
            with self.subTest(value=value):
                self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))

    def test_folded_quoted_mailfrom_and_normal_comments_are_supported(self):
        msg = email.message_from_string(
            f"To: {PARENT}\nX-ICLOUD-HME: {PARENT}\n"
            "Authentication-Results: spf.icloud.com;\n"
            f' spf=pass (trusted receiver result) smtp.mailfrom="{self.envelope()}"\n\n'
        )
        self.assertTrue(candidate_match(CHILD_A, msg, forwarded=True))

    def test_reason_text_cannot_be_confused_with_another_method(self):
        msg = hme_message(None)
        msg["Authentication-Results"] = f'spf.icloud.com; spf=pass reason="normal auth=fail text" smtp.mailfrom={self.envelope()}'
        self.assertTrue(candidate_match(CHILD_A, msg, forwarded=True))

    def test_quoted_reason_cannot_create_mailfrom_property(self):
        msg = hme_message(None)
        msg["Authentication-Results"] = f'spf.icloud.com; spf=pass reason="text smtp.mailfrom={self.envelope()} text"'
        self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))

    def test_quoted_fake_property_does_not_hide_external_real_property(self):
        msg = hme_message(None)
        msg["Authentication-Results"] = f'spf.icloud.com; spf=pass reason="text smtp.mailfrom={self.envelope(CHILD_B)} text" smtp.mailfrom={self.envelope()}'
        self.assertTrue(candidate_match(CHILD_A, msg, forwarded=True))
        self.assertFalse(candidate_match(CHILD_B, msg, forwarded=True))

    def test_ordinary_bounce_and_return_path_alone_are_not_recipient_proof(self):
        msg = hme_message(None)
        msg["Return-Path"] = self.envelope()
        self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))
        msg["Authentication-Results"] = f"spf.icloud.com; spf=pass smtp.mailfrom={CHILD_A}"
        self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))

    def test_multiple_return_paths_are_recall_only_and_cannot_override_spf(self):
        msg = self.message()
        msg["Return-Path"] = "owner@gmail.com"
        msg["Return-Path"] = self.envelope(CHILD_B)
        self.assertTrue(candidate_match(CHILD_A, msg, forwarded=True))
        self.assertFalse(candidate_match(CHILD_B, msg, forwarded=True))

    def test_duplicate_mailfrom_or_broken_comment_and_quotes_are_rejected(self):
        values = [
            f"spf.icloud.com; spf=pass smtp.mailfrom={self.envelope()} smtp.mailfrom={self.envelope(CHILD_B)}",
            f'spf.icloud.com; spf=pass smtp.mailfrom="{self.envelope()}".evil',
            f"spf.icloud.com; spf=pass smtp.mailfrom={self.envelope()} (unterminated",
        ]
        for value in values:
            msg = hme_message(None)
            msg["Authentication-Results"] = value
            with self.subTest(value=value):
                self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))


class OpenAITM1SPFRecipientTests(unittest.TestCase):
    def message(self, recipient=CHILD_A, *, verdict="pass", domain="tm1.openai.com", prefix="bounce+12ab34.56cd78-"):
        msg = hme_message(None)
        msg["X-ICLOUD-HME"] = f"p={PARENT}; d=1; f=owner@gmail.com; s=sender@example.test"
        msg["Authentication-Results"] = f"spf.icloud.com; spf={verdict} smtp.mailfrom={prefix}{recipient.replace('@', '=')}@{domain}"
        return msg

    def test_exact_real_tm1_template_matches_only_full_child(self):
        msg = self.message()
        for target, expected in ((CHILD_A, True), (CHILD_B, False), (PARENT, False)):
            self.assertEqual(candidate_match(target, msg, forwarded=True), expected)
        self.assertEqual(extract_recipient_evidence(msg)["original_recipients"], [CHILD_A])

    def test_tm1_can_prove_original_parent(self):
        self.assertTrue(candidate_match(PARENT, self.message(PARENT), forwarded=True, strict_family=True))

    def test_similar_child_other_parent_and_domain_are_not_the_target(self):
        for recipient in (CHILD_A.replace("a1b2c3", "a1b2c3x"), "other+a1b2c3@icloud.com", CHILD_A.replace("icloud.com", "icloud.com.evil.test")):
            with self.subTest(recipient=recipient):
                self.assertFalse(candidate_match(CHILD_A, self.message(recipient), forwarded=True))

    def test_provider_domain_is_exact(self):
        for domain in ("tm2.openai.com", "tm1.openai.com.evil.test", "evil-tm1.openai.com", "openai.com", "tm1.openai.net"):
            with self.subTest(domain=domain):
                self.assertFalse(candidate_match(CHILD_A, self.message(domain=domain), forwarded=True))

    def test_unknown_same_domain_prefix_blocks_family_without_claiming_recipient(self):
        for prefix in ("bounce+12ab34.56cd7g-", "bounce+12ab3.56cd78-", "bounce+12ab34.56cd789-", "unknown-prefix-"):
            for displayed in (PARENT, CHILD_A):
                msg = self.message(prefix=prefix)
                msg.replace_header("To", displayed)
                with self.subTest(prefix=prefix, displayed=displayed):
                    self.assertEqual(extract_recipient_evidence(msg)["original_recipients"], [])
                    for target in (PARENT, CHILD_A, CHILD_B):
                        self.assertFalse(candidate_match(target, msg, forwarded=True))

    def test_spf_nonpass_blocks_child_and_mother_fallback(self):
        for verdict in ("fail", "softfail", "neutral", "none", "temperror", "permerror"):
            msg = self.message(verdict=verdict)
            for target in (PARENT, CHILD_A, CHILD_B):
                with self.subTest(verdict=verdict, target=target):
                    self.assertFalse(candidate_match(target, msg, forwarded=True))

    def test_tm1_and_other_provider_sibling_conflicts_reject_all(self):
        msg = self.message()
        msg["Authentication-Results"] = f"spf.icloud.com; spf=pass smtp.mailfrom=bounces+1234567-a1b2-{CHILD_B.replace('@', '=')}@em7877.tm.openai.com"
        for target in (PARENT, CHILD_A, CHILD_B):
            self.assertFalse(candidate_match(target, msg, forwarded=True))

    def test_missing_hme_and_fake_authserv_cannot_prove_tm1(self):
        msg = self.message()
        del msg["X-ICLOUD-HME"]
        self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))
        msg = self.message()
        msg.replace_header("Authentication-Results", str(msg["Authentication-Results"]).replace("spf.icloud.com", "spf.icloud.com.evil.test"))
        self.assertFalse(candidate_match(CHILD_A, msg, forwarded=True))
