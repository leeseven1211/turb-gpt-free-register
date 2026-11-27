"""本地预检的互斥分类与容量边界。"""
import unittest


class PreviewDomainTests(unittest.TestCase):
    def domain(self):
        from core.teams import domain
        return domain

    def test_categories_are_disjoint_and_identity_change_precedes_membership(self):
        domain = self.domain()
        cases = [
            ({}, "unavailable", "account_not_found"),
            ({"id": 1, "email": "new@example.test", "already_member": True},
             "unavailable", "account_identity_changed"),
            ({"id": 1, "other_teams": [{"id": "2"}], "already_member": True},
             "another_team", "already_in_another_team"),
            ({"id": 1, "already_member": True, "auth_capability": "missing"},
             "already_member", "already_member"),
            ({"id": 1, "active_invitation": {"id": 3}, "auth_capability": "missing"},
             "same_team_active", None),
            ({"id": 1, "auth_capability": "missing", "invitation": {"invitation_state": "pending"}},
             "missing_auth", "missing_auth_materials"),
            ({"id": 1, "invitation": {"invitation_state": "pending"}},
             "resume_invite", None),
            ({"id": 1, "auth_capability": "unknown"}, "new", None),
        ]
        for state, category, reason in cases:
            with self.subTest(category=category):
                expected = "old@example.test" if state.get("email") else None
                self.assertEqual((category, reason), domain.classify(state, expected))

    def test_zero_seats_does_not_fallback_and_unknown_counts_stay_unknown(self):
        domain = self.domain()
        result = domain.capacity({"purchased_seats": 0, "planned_member_limit": 20,
                                  "occupied_count": None}, additional_required=1,
                                 eligible_count=1)
        self.assertEqual(0, result["effective_limit"])
        self.assertEqual("purchased_seats", result["basis"])
        self.assertIsNone(result["occupied_count"])
        self.assertIsNone(result["available_count"])
        self.assertTrue(result["can_submit"])

    def test_join_requires_limit_even_when_existing_invite_needs_no_new_seat(self):
        result = self.domain().capacity({"purchased_seats": None,
                                        "planned_member_limit": None,
                                        "occupied_count": 3},
                                       additional_required=0, eligible_count=1)
        self.assertFalse(result["can_submit"])
        self.assertEqual("team_limit_required", result["blocking_reason_code"])

    def test_local_limit_includes_manager_and_uses_lower_known_limit(self):
        result = self.domain().capacity({"purchased_seats": 8, "planned_member_limit": 4,
                                        "occupied_count": 5}, additional_required=0,
                                       eligible_count=2)
        self.assertEqual(4, result["effective_limit"])
        self.assertEqual(0, result["available_count"])
        self.assertTrue(result["can_submit"])

    def test_incomplete_remote_facts_do_not_claim_exact_new_reservations(self):
        result = self.domain().preview(
            ["1"], {1: {"id": 1, "auth_capability": "unknown"}},
            {"purchased_seats": 4, "occupied_count": None},
        )
        self.assertTrue(result["requires_sync"])
        self.assertIsNone(result["capacity"]["additional_required"])

    def test_email_identity_uses_indexed_lowercase_rule_without_expanding_sharp_s(self):
        self.assertEqual(
            ("unavailable", "account_identity_changed"),
            self.domain().classify({"id": 1, "email": "Straße@example.test"}, "STRASSE@example.test"),
        )

    def test_preview_counts_unique_targets_without_counting_eligible_twice(self):
        result = self.domain().preview(
            ["1", "2", "1", "3", "4"],
            {1: {"id": 1, "already_member": True}, 2: {"id": 2},
             3: {"id": 3, "active_invitation": {"id": 33}, "reservation_active": True},
             4: {"id": 4, "other_teams": [{"id": "9"}]}},
            {"purchased_seats": 10, "planned_member_limit": None, "occupied_count": 4},
        )
        counts = result["counts"]
        self.assertEqual((5, 4, 1), (counts["requested_count"], counts["unique_count"],
                                     counts["duplicate_count"]))
        self.assertEqual(2, counts["eligible_count"])
        self.assertEqual(1, result["capacity"]["additional_required"])
        self.assertEqual(4, sum(counts[key] for key in (
            "unavailable_count", "another_team_count", "already_member_count",
            "same_team_active_count", "missing_auth_count", "resume_invite_count", "new_count")))
