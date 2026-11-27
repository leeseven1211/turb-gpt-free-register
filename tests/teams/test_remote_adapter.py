"""Team 远端适配层的身份、工作区与分页边界。"""
from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
import unittest

from core.teams.remote import TeamRemoteAdapter, TeamRemoteError
from core.teams.auth import verify_identity


class Response:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return self.payload


class HttpBoundary:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def get_chatgpt_headers(self, **kwargs):
        return {"accept": "application/json"}

    def get(self, url, **kwargs):
        self.requests.append(("GET", url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def post(self, url, **kwargs):
        self.requests.append(("POST", url, kwargs))
        return self.responses.pop(0)


class AuthBoundary:
    def __init__(self, session, account_id=7, email="member@example.test", user_id="user-one"):
        self.session, self.account_id, self.email, self.user_id = session, account_id, email, user_id

    @contextmanager
    def open(self, account_id, workspace_id=None):
        yield SimpleNamespace(account_id=account_id, email=self.email, user_id=self.user_id,
            access_token="private-test-token", session=self.session, workspace_id=workspace_id, session_info={"account": {"id": "personal"}},
            context=lambda wid: {"account_id": account_id, "workspace_id": wid,
                "email": self.email, "user_id": self.user_id, "access_token": "private-test-token"})


def discovery():
    return {"accounts": {
        "personal": {"account": {"account_id": "personal", "structure": "personal", "plan_type": "free"}},
        "team-a": {"account": {"account_id": "team-a", "name": "团队甲", "structure": "workspace",
            "plan_type": "team", "account_user_role": "account-owner", "account_user_id": "user-one__team-a"},
            "can_access_with_session": True,
            "entitlement": {"has_active_subscription": True}},
        "default": {"account": {"account_id": "personal", "structure": "personal"}},
    }}


class TeamRemoteAdapterTests(unittest.TestCase):
    def adapter(self, *responses):
        self.http = HttpBoundary(responses)
        return TeamRemoteAdapter(auth=AuthBoundary(self.http))

    def test_discovery_deduplicates_default_and_does_not_promote_personal_owner(self):
        result = self.adapter(Response(discovery()), Response({}, 403)).discover(7)
        self.assertEqual(["team-a"], [w["workspace_id"] for w in result["workspaces"]])
        self.assertIsNone(result["workspaces"][0]["purchased_seats"])
        self.assertFalse(result["workspaces"][0]["can_manage"])

    def test_discovery_confirms_admin_read_permission_before_binding(self):
        a = self.adapter(Response(discovery()), Response({"items": [], "total": 0, "limit": 1, "offset": 0}),
            Response({"items": [], "total": 0, "limit": 1, "offset": 0}))
        result = a.discover(7)
        self.assertTrue(result["workspaces"][0]["can_manage"])
        self.assertEqual("remote_reads", result["workspaces"][0]["permission_evidence"]["source"])

    def test_real_remote_role_is_normalized_for_persisted_probe_contract(self):
        a = self.adapter(Response(discovery()), Response({"items": [], "total": 0, "limit": 1, "offset": 0}),
            Response({"items": [], "total": 0, "limit": 1, "offset": 0}))
        workspace = a.discover(7)["workspaces"][0]
        self.assertEqual("team", workspace["workspace_type"])
        self.assertEqual("owner", workspace["role"])
        self.assertEqual({"read_members": True, "read_invitations": True, "invite_members": None}, workspace["capabilities"])

    def test_targeted_probe_only_verifies_requested_workspace(self):
        payload = discovery()
        payload["accounts"]["team-b"] = {"account": {"account_id": "team-b", "structure": "workspace",
            "account_user_role": "account-owner", "account_user_id": "user-one__team-b"}}
        a = self.adapter(Response(payload), Response({"items": [], "total": 0, "limit": 1, "offset": 0}),
            Response({"items": [], "total": 0, "limit": 1, "offset": 0}))
        result = a.discover(7, "team-a")
        self.assertEqual(["team-a"], [w["workspace_id"] for w in result["workspaces"]])

    def test_snapshot_reads_all_pages_and_keeps_remote_unimported_member(self):
        a = self.adapter(Response(discovery()),
            Response({"items": [{"id": "user-one", "email": "member@example.test", "role": "account-owner"}], "total": 2, "offset": 0, "limit": 1}),
            Response({"items": [{"id": "external", "email": "outside@example.test", "role": "standard-user"}], "total": 2, "offset": 1, "limit": 1}),
            Response({"items": [], "total": 0, "offset": 0, "limit": 50}))
        result = a.snapshot(7, "team-a")
        self.assertTrue(result["members_complete"])
        self.assertTrue(result["invitations_complete"])
        self.assertEqual(2, result["confirmed_member_count"])
        self.assertEqual(0, result["pending_invite_count"])
        self.assertEqual("external", result["members"][1]["remote_user_id"])
        self.assertTrue(result["workspace"]["can_manage"])
        for _, _, kwargs in self.http.requests:
            self.assertEqual("team-a", kwargs["headers"].get("chatgpt-account-id"))

    def test_missing_total_never_claims_complete_or_zero_count(self):
        a = self.adapter(Response(discovery()), Response({"items": [], "limit": 100, "offset": 0}),
            Response({"items": [], "limit": 50, "offset": 0}))
        result = a.snapshot(7, "team-a")
        self.assertFalse(result["members_complete"])
        self.assertIsNone(result["confirmed_member_count"])
        self.assertIsNone(result["pending_invite_count"])

    def test_foreign_workspace_is_rejected_before_reading_its_members(self):
        a = self.adapter(Response(discovery()))
        with self.assertRaises(TeamRemoteError) as caught:
            a.snapshot(7, "team-elsewhere")
        self.assertEqual("team_workspace_unavailable", caught.exception.code)
        self.assertEqual(1, len(self.http.requests))

    def test_inconsistent_pagination_does_not_remove_missing_members(self):
        a = self.adapter(Response(discovery()),
            Response({"items": [{"id": "one"}], "total": 2, "offset": 0, "limit": 1}),
            Response({"items": [{"id": "one"}], "total": 2, "offset": 0, "limit": 1}),
            Response({"items": [], "total": 0, "offset": 0, "limit": 50}))
        result = a.snapshot(7, "team-a")
        self.assertFalse(result["members_complete"])
        self.assertIsNone(result["confirmed_member_count"])

    def test_member_verification_keeps_user_and_workspace_both_bound(self):
        a = self.adapter(Response(discovery()), Response({"items": [{"id": "user-one", "email": "member@example.test", "role": "standard-user"}]}))
        result = a.verify_member(7, "team-a")
        self.assertTrue(result["joined"])
        self.assertEqual("user-one", result["member"]["remote_user_id"])
        self.assertEqual("team-a", result["auth_context"]["workspace_id"])
        self.assertEqual(7, result["auth_context"]["account_id"])

    def test_invite_uses_regular_role_and_confirms_target_in_remote_list(self):
        a = self.adapter(Response(discovery()),
            Response({"items": [], "total": 0, "offset": 0, "limit": 100}),
            Response({"partial_success": False}),
            Response({"items": [{"id": "inv-1", "email_address": "new@example.test", "role": "standard-user", "status": "invited"}], "total": 1, "offset": 0, "limit": 100}))
        result = a.invite(7, "team-a", " New@example.test ")
        self.assertEqual("inv-1", result["invitation"]["remote_invitation_id"])
        self.assertEqual("invited", result["invitation"]["status"])
        self.assertEqual("pending", result["invitation"]["invitation_state"])
        self.assertEqual("member", result["invitation"]["role"])
        post = next(item for item in self.http.requests if item[0] == "POST")
        self.assertEqual("https://chatgpt.com/backend-api/accounts/team-a/invites", post[1])
        self.assertEqual({"email_addresses": ["new@example.test"], "role": "standard-user"}, post[2]["json"])

    def test_existing_invitation_resumes_without_sending_again(self):
        a = self.adapter(Response(discovery()), Response({"items": [
            {"id": "existing", "email_address": "new@example.test", "status": "invited"}],
            "total": 1, "offset": 0, "limit": 100}))
        result = a.invite(7, "team-a", "new@example.test")
        self.assertTrue(result["reused"])
        self.assertEqual("existing", result["invitation"]["remote_invitation_id"])
        self.assertTrue(all(request[0] == "GET" for request in self.http.requests))

    def test_success_status_without_target_receipt_remains_retryable(self):
        a = self.adapter(Response(discovery()),
            Response({"items": [], "total": 0, "offset": 0, "limit": 100}),
            Response({"partial_success": False}),
            Response({"items": [], "total": 0, "offset": 0, "limit": 100}))
        with self.assertRaises(TeamRemoteError) as caught:
            a.invite(7, "team-a", "new@example.test")
        self.assertEqual("team_invite_receipt_missing", caught.exception.code)
        self.assertTrue(caught.exception.retryable)

    def test_explicit_per_recipient_rejection_is_not_success(self):
        a = self.adapter(Response(discovery()),
            Response({"items": [], "total": 0, "offset": 0, "limit": 100}),
            Response({"partial_success": True, "rejected_emails": [
                {"email_address": "new@example.test", "reason": "seat_limit_exceeded"}]}))
        with self.assertRaises(TeamRemoteError) as caught:
            a.invite(7, "team-a", "new@example.test")
        self.assertEqual("team_invite_rejected", caught.exception.code)
        self.assertEqual("seat_limit_exceeded", caught.exception.details["remote_reason_code"])

    def test_pending_workspace_access_is_not_confirmed_membership(self):
        payload = discovery()
        payload["accounts"]["team-a"]["can_access_with_session"] = False
        a = self.adapter(Response(payload))
        result = a.verify_member(7, "team-a")
        self.assertFalse(result["joined"])
        self.assertIsNone(result["auth_context"])

    def test_unknown_workspace_name_remains_null(self):
        payload = discovery()
        payload["accounts"]["team-a"]["account"].pop("name")
        a = self.adapter(Response(payload), Response({}, 403))
        self.assertIsNone(a.discover(7)["workspaces"][0]["name"])

    def test_member_evidence_from_another_user_is_rejected(self):
        payload = discovery()
        payload["accounts"]["team-a"]["account"]["account_user_id"] = "other-user__team-a"
        a = self.adapter(Response(payload))
        with self.assertRaises(TeamRemoteError) as caught:
            a.verify_member(7, "team-a")
        self.assertEqual("account_identity_changed", caught.exception.code)

    def test_invitation_snapshot_only_requests_active_invites(self):
        a = self.adapter(Response(discovery()), Response({"items": [], "total": 0, "offset": 0, "limit": 100}),
            Response({"items": [], "total": 0, "offset": 0, "limit": 100}))
        a.snapshot(7, "team-a")
        self.assertIn("status=invited", self.http.requests[-1][1])

    def test_incomplete_invitation_read_does_not_blindly_send_duplicate(self):
        a = self.adapter(Response(discovery()), Response({"items": [], "offset": 0, "limit": 100}))
        with self.assertRaises(TeamRemoteError) as caught:
            a.invite(7, "team-a", "new@example.test")
        self.assertEqual("team_invite_receipt_missing", caught.exception.code)
        self.assertTrue(all(request[0] == "GET" for request in self.http.requests))

    def test_email_invite_accept_uses_member_identity_and_no_merge_payload(self):
        pending = discovery()
        pending["accounts"]["team-a"]["can_access_with_session"] = False
        a = self.adapter(Response(pending), Response({}), Response(discovery()), Response({"items": [{"id": "user-one", "email": "member@example.test", "role": "standard-user"}]}))
        result = a.accept(7, "team-a", {"email_snapshot": "member@example.test", "remote_invitation_id": "inv-1"})
        self.assertTrue(result["joined"])
        self.assertEqual("team-a", result["workspace_id"])
        post = next(item for item in self.http.requests if item[0] == "POST")
        self.assertEqual("https://chatgpt.com/backend-api/accounts/team-a/invites/accept", post[1])
        self.assertNotIn("json", post[2])
        self.assertEqual("personal", post[2]["headers"]["chatgpt-account-id"])

    def test_accept_classifies_pending_approval_from_http_response(self):
        pending = discovery()
        pending["accounts"]["team-a"]["can_access_with_session"] = False
        a = self.adapter(Response(pending), Response({"detail": {"code": "workspace_join_request_pending"}}, 409))
        with self.assertRaises(TeamRemoteError) as caught:
            a.accept(7, "team-a", {"email_snapshot": "member@example.test"})
        self.assertEqual("workspace_join_request_pending", caught.exception.code)
        self.assertTrue(caught.exception.retryable)

    def test_accept_workspace_mismatch_is_rejected_before_network(self):
        a = self.adapter()
        with self.assertRaises(TeamRemoteError) as caught:
            a.accept(7, "team-a", {"workspace_id": "team-other", "email": "member@example.test"})
        self.assertEqual("team_workspace_mismatch", caught.exception.code)
        self.assertEqual([], self.http.requests)

    def test_accept_target_email_must_match_authenticated_member(self):
        a = self.adapter()
        with self.assertRaises(TeamRemoteError) as caught:
            a.accept(7, "team-a", {"email_snapshot": "other@example.test"})
        self.assertEqual("account_identity_changed", caught.exception.code)
        self.assertEqual([], self.http.requests)

    def test_accept_success_response_still_requires_accessible_member_evidence(self):
        pending = discovery()
        pending["accounts"]["team-a"]["can_access_with_session"] = False
        a = self.adapter(Response(pending), Response({}), Response(pending))
        with self.assertRaises(TeamRemoteError) as caught:
            a.accept(7, "team-a", {"email_snapshot": "member@example.test"})
        self.assertEqual("team_member_unconfirmed", caught.exception.code)
        self.assertTrue(caught.exception.retryable)

    def test_accept_existing_member_verifies_without_reposting(self):
        a = self.adapter(Response(discovery()), Response({"items": [{"id": "user-one", "email": "member@example.test", "role": "standard-user"}]}))
        result = a.accept(7, "team-a", {"email_snapshot": "member@example.test"})
        self.assertTrue(result["joined"])
        self.assertTrue(result["reused"])
        self.assertTrue(all(request[0] == "GET" for request in self.http.requests))

    def test_invited_numeric_status_two_is_pending_and_resumes(self):
        a = self.adapter(Response(discovery()), Response({"items": [
            {"id": "real-invite", "email_address": "new@example.test", "status": 2,
             "role": "standard-user", "account_user_id": "user-two__team-a"}],
            "total": 1, "limit": 100, "offset": 0}))
        result = a.invite(7, "team-a", "new@example.test")
        self.assertTrue(result["reused"])
        self.assertEqual("pending", result["invitation"]["invitation_state"])
        self.assertTrue(all(request[0] == "GET" for request in self.http.requests))

    def test_pending_invite_can_be_accessible_without_being_a_member(self):
        a = self.adapter(Response(discovery()), Response({"items": []}))
        result = a.verify_member(7, "team-a")
        self.assertFalse(result["joined"])
        self.assertIsNone(result["auth_context"])

    def test_accept_empty_response_is_verified_from_remote_member_list(self):
        pending = discovery()
        pending["accounts"]["team-a"]["can_access_with_session"] = False
        a = self.adapter(Response(pending), Response(None, 204), Response(discovery()),
            Response({"items": [{"id": "user-one", "role": "standard-user"}]}))
        self.assertTrue(a.accept(7, "team-a", {"email_snapshot": "member@example.test"})["joined"])

    def test_malformed_remote_error_code_remains_classified_http_error(self):
        a = self.adapter(Response({"code": {"unexpected": "object"}}, 500))
        with self.assertRaises(TeamRemoteError) as caught:
            a.discover(7)
        self.assertEqual("team_remote_http_failed", caught.exception.code)

    def test_wrapped_operation_cancel_is_not_converted_to_network_failure(self):
        from core.operations.runtime import OperationCancelled
        cancelled = OperationCancelled("停止测试")
        wrapped = RuntimeError("传输包装")
        wrapped.__cause__ = cancelled
        a = self.adapter(wrapped)
        with self.assertRaises(OperationCancelled):
            a.discover(7)

    def test_remote_403_is_permissions_without_deactivation_inference(self):
        a = self.adapter(Response({}, 403))
        with self.assertRaises(TeamRemoteError) as caught:
            a.discover(7)
        self.assertEqual("team_permission_denied", caught.exception.code)
        self.assertTrue(caught.exception.retryable)

    def test_authentication_compares_person_identity_without_personal_workspace_equality(self):
        account = {"id": 7, "email": "member@example.test", "user_id": "user-one", "chatgpt_account_id": "personal"}
        info = {"user": {"id": "user-one", "email": "MEMBER@example.test"}, "account": {"id": "team-a"}}
        verify_identity(account, info)
        info["user"]["id"] = "other-user"
        with self.assertRaises(TeamRemoteError) as caught:
            verify_identity(account, info)
        self.assertEqual("account_identity_changed", caught.exception.code)
