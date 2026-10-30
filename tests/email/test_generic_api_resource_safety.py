"""Safety contracts for imported short-lived API inboxes; no real I/O."""

from __future__ import annotations

import json
from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import requests

from core.email.generic_api import client as client


ADDRESS = "imported@example.test"
CODE_URL = "https://inbox.example.test/read/private-fixture-token"
OTP = "654321"
START = 1_800_000_000.0


class FakeClock:
    def __init__(self):
        self.now = START

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def response(status=200, body="", *, payload=None):
    result = requests.Response()
    result.status_code = status
    result.url = CODE_URL
    result.encoding = "utf-8"
    result._content = (json.dumps(payload) if payload is not None else body).encode()
    return result


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        item = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(item, BaseException):
            raise item
        return item() if callable(item) else item

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


@pytest.fixture
def inbox():
    account = client.GenericApiEmailAccount(email=ADDRESS, code_url=CODE_URL)
    clock = FakeClock()

    def poll(session, **overrides):
        options = {"after_ts": START, "max_wait": 3, "poll_interval": 1, "settle_seconds": 0}
        options.update(overrides)
        with ExitStack() as stack:
            stack.enter_context(patch.object(client, "get_account_context", return_value=account))
            stack.enter_context(patch.object(client.requests, "Session", return_value=session))
            stack.enter_context(patch.object(client.time, "time", side_effect=clock.time))
            stack.enter_context(patch.object(client, "bounded_sleep", side_effect=clock.sleep))
            return client.fetch_latest_otp(ADDRESS, **options)

    return account, clock, poll


def assert_safe_error(exc, *, error_code, forbidden=()):
    assert getattr(exc.value, "error_code", None) == error_code
    rendered = str(exc.value)
    for secret in (CODE_URL, "private-fixture-token", OTP, *forbidden):
        assert secret not in rendered


@pytest.mark.parametrize("timestamp", [START - 300, 0, "2020-01-01T00:00:00Z", 'unparseable'])
def test_structured_old_code_is_not_recovered_by_plain_text_fallback(inbox, timestamp):
    _, _, poll = inbox
    session = FakeSession(response(payload={
        "code": OTP, "to": ADDRESS, "timestamp": timestamp,
        "subject": "Your verification code", "body": "Code " + OTP,
    }))
    with pytest.raises(client.GenericApiMailError):
        poll(session)


@pytest.mark.parametrize("recipient_key", ["to", "recipient", "email"])
def test_structured_wrong_recipient_is_not_recovered_by_plain_text_fallback(inbox, recipient_key):
    _, _, poll = inbox
    session = FakeSession(response(payload={
        "code": OTP, recipient_key: "someone-else@example.test", "timestamp": START,
        "subject": "Your verification code", "body": "Code " + OTP,
    }))
    with pytest.raises(client.GenericApiMailError):
        poll(session)


@pytest.mark.parametrize('key', ['time', 'date', 'received_at', 'receivedAt', 'created_at', 'createdAt'])
def test_zero_timestamp_constraint_is_not_treated_as_absent(inbox, key):
    _, _, poll = inbox
    with pytest.raises(client.GenericApiMailError):
        poll(FakeSession(response(payload={'code': OTP, key: 0, 'to': ADDRESS})))


@pytest.mark.parametrize('metadata', [{'timestamp': 1}, {'recipient': 'other@example.test'}, {'timestamp': 'invalid'}])
def test_nested_metadata_constrains_nested_code(inbox, metadata):
    _, _, poll = inbox
    with pytest.raises(client.GenericApiMailError):
        poll(FakeSession(response(payload={'data': {'code': OTP, **metadata}})))


@pytest.mark.parametrize("body", ["Your verification code is " + OTP, json.dumps({
    "code": OTP, "recipient": ADDRESS, "timestamp": START,
})])
def test_plain_text_and_matching_fresh_structured_code_remain_supported(inbox, body):
    _, _, poll = inbox
    assert poll(FakeSession(response(body=body))) == OTP


def test_http_410_invalidates_a_previously_locked_candidate(inbox):
    _, _, poll = inbox
    session = FakeSession(response(body="Your verification code is " + OTP),
                          response(410, "expired-body " + OTP + " " + CODE_URL))
    with pytest.raises(client.GenericApiMailError) as exc:
        poll(session, settle_seconds=2)
    assert_safe_error(exc, error_code="email_resource_expired", forbidden=("expired-body",))
    assert len(session.calls) == 2


@pytest.mark.parametrize("status", [401, 403, 404, 503])
def test_failed_reads_never_expose_response_body_or_private_url(inbox, status):
    _, _, poll = inbox
    session = FakeSession(response(status, "sensitive-response-body " + OTP + " " + CODE_URL))
    with pytest.raises(client.GenericApiMailError) as exc:
        poll(session)
    assert_safe_error(exc, error_code="email_resource_read_failed", forbidden=("sensitive-response-body",))


def test_transport_error_is_sanitized(inbox):
    _, _, poll = inbox
    session = FakeSession(requests.ConnectionError("private-transport-detail " + CODE_URL + " " + OTP))
    with pytest.raises(client.GenericApiMailError) as exc:
        poll(session)
    assert_safe_error(exc, error_code="email_resource_read_failed", forbidden=("private-transport-detail",))


def test_failed_read_discards_candidate_instead_of_returning_it_at_timeout(inbox):
    _, _, poll = inbox
    session = FakeSession(response(body="Your verification code is " + OTP), response(503, "unavailable"))
    with pytest.raises(client.GenericApiMailError) as exc:
        poll(session, settle_seconds=10, max_wait=2)
    assert_safe_error(exc, error_code="email_resource_read_failed")


def test_direct_api_requests_verify_tls_by_default(inbox):
    _, _, poll = inbox
    session = FakeSession(response(body="Your verification code is " + OTP))
    assert poll(session) == OTP
    assert session.calls
    assert all(kwargs.get("verify", True) is True for _, kwargs in session.calls)


def test_yangyang_detail_transport_failure_discards_locked_candidate(inbox):
    account, _, poll = inbox
    account.code_url = 'https://inbox.example.test/messages/fixture-token/' + ADDRESS
    listing = response(payload={'items': [{'id': 'fixture-message'}], 'has_more': False})
    detail = response(payload={'subject': 'Your verification code', 'body': 'Your code is ' + OTP})
    session = FakeSession(listing, detail, listing, requests.ConnectionError('private-token ' + OTP))
    with pytest.raises(client.GenericApiMailError) as exc:
        poll(session, settle_seconds=10, max_wait=2)
    assert_safe_error(exc, error_code='email_resource_read_failed')


def test_yangyang_expiry_after_list_prevents_detail_request(inbox):
    account, clock, poll = inbox
    account.code_url = 'https://inbox.example.test/messages/fixture-token/' + ADDRESS
    account.expires_at_epoch = START + 1
    def delayed_listing():
        clock.now = START + 2
        return response(payload={'items': [{'id': 'fixture-message'}], 'has_more': False})
    session = FakeSession(delayed_listing)
    with pytest.raises(client.GenericApiMailError) as exc:
        poll(session)
    assert_safe_error(exc, error_code='email_resource_expired')
    assert len(session.calls) == 1


def test_nested_fresh_code_with_sender_identity_stays_supported(inbox):
    _, _, poll = inbox
    assert poll(FakeSession(response(payload={'data': {
        'code': OTP, 'recipient': ADDRESS, 'timestamp': START,
        'sender': {'email': 'noreply@example.test'},
    }}))) == OTP


@pytest.mark.parametrize('metadata', [{'received_at': 0}, {'received_at': 'invalid'}, {'timestamp': 1}])
def test_yangyang_list_metadata_cannot_recover_old_or_invalid_otp(metadata):
    session = FakeSession(response(payload={'items': [{'id': 'fixture-message', **metadata}], 'has_more': False}),
                          response(payload={'subject': 'Your code', 'body': 'Your code is ' + OTP}))
    result = client._fetch_yangyang_otp(session, 'https://fixture.example.test/messages/token/' + ADDRESS,
                                      {}, after_ts=START, expected_email=ADDRESS)
    assert result is None
    assert len(session.calls) == 1


def test_yangyang_timestamp_honors_explicit_timezone():
    stamp = '2026-08-01T10:00:00+03:00'
    assert client._parse_yangyang_ts(stamp) == datetime.fromisoformat(stamp).timestamp()


@pytest.mark.parametrize("inline", [False, True])
def test_yangyang_list_detail_and_inline_requests_verify_tls_by_default(inline):
    page_url = "https://inbox.example.test/messages/fixture-token/imported@example.test"
    if inline:
        session = FakeSession(response(404, "Not Found"), response(body=(
            '<article class="mail-card"><span class="subject">Your verification code</span>'
            '<pre class="body">Your code is ' + OTP + "</pre></article>"
        )))
    else:
        session = FakeSession(response(payload={"items": [{"id": "fixture-message"}], "has_more": False}),
                              response(payload={"subject": "Your verification code", "body": "Your code is " + OTP}))
    result = client._fetch_yangyang_otp(session, page_url, {})
    assert result and result[0] == OTP
    assert len(session.calls) == 2
    assert all(kwargs.get("verify", True) is True for _, kwargs in session.calls)


def test_expired_resource_is_rejected_before_first_network_read(inbox):
    account, _, poll = inbox
    account.expires_at_epoch = START - 1
    session = FakeSession(response(body="Your verification code is " + OTP))
    with pytest.raises(client.GenericApiMailError) as exc:
        poll(session)
    assert_safe_error(exc, error_code="email_resource_expired")
    assert not session.calls


def test_resource_expiry_is_checked_again_before_next_poll(inbox):
    account, _, poll = inbox
    account.expires_at_epoch = START + 0.5
    session = FakeSession(response(body="No new messages"))
    with pytest.raises(client.GenericApiMailError) as exc:
        poll(session)
    assert_safe_error(exc, error_code="email_resource_expired")
    assert len(session.calls) == 1


def test_resource_expiry_is_checked_after_network_returns_before_otp_return(inbox):
    account, clock, poll = inbox
    account.expires_at = datetime.fromtimestamp(START + 1, timezone.utc).isoformat()

    def delayed_response():
        clock.now = START + 2
        return response(body="Your verification code is " + OTP)

    with pytest.raises(client.GenericApiMailError) as exc:
        poll(FakeSession(delayed_response))
    assert_safe_error(exc, error_code="email_resource_expired")


def test_resource_expiry_blocks_candidate_return_at_total_timeout(inbox):
    account, _, poll = inbox
    account.expires_at_epoch = START + 1
    session = FakeSession(response(body="Your verification code is " + OTP))
    with pytest.raises(client.GenericApiMailError) as exc:
        poll(session, max_wait=1, settle_seconds=10)
    assert_safe_error(exc, error_code="email_resource_expired")
