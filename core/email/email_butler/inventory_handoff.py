"""Manual HME inventory handoff. Registration never calls this network boundary.

Butler's acquisition ledger owns the address permanently even when its temporary
read lease expires. Replaying an uncertain import uses exactly the same owner
and acquisition; it cannot request a replacement address.
"""
from __future__ import annotations

import hashlib
import os
import uuid


def verify_client(who: dict, *, client_id: str = '') -> str:
    required = {'mailboxes.acquisition.v1', 'inbound.recipient_evidence.v1'}
    policy = who.get('policy') or {}
    if (not required.issubset(set(who.get('capabilities') or []))
            or not who.get('id') or not policy.get('consumer') or policy.get('service') != 'openai'
            or client_id and str(who['id']) != client_id):
        raise ValueError('handoff_contract_unsupported: Butler 持久归属或原消费身份不可用')
    return str(who['id'])


def ownership_for_import(address: str, api_base: str, client_id: str, consumer_id: str) -> dict:
    digest = hashlib.sha256(f'{consumer_id}:{api_base}:{client_id}:{address}'.encode()).hexdigest()
    return {'owner_kind': 'local_inventory', 'owner_id': consumer_id, 'acquisition_id': 'turb-import:' + digest}


def validate_candidate(item: dict, *, mailbox: str) -> dict:
    """Accept a complete permanent HME identity; never infer missing route fields."""
    from core.storage.email.local_imports import butler_forward_address
    if not isinstance(item, dict):
        raise ValueError('handoff_identity_mismatch: Butler 完整身份缺失')
    address = butler_forward_address(item.get('email'))
    parent = address.partition('@')[0].split('+', 1)[0] + '@icloud.com'
    identity_type = str(item.get('identity_type') or '')
    if (item.get('provider') != 'icloud_hme' or item.get('recipient_mode') != 'forwarded_exact_v1'
            or item.get('strict_family') is not True
            or str(item.get('mailbox_email') or '').strip().lower() != mailbox
            or not str(item.get('identity_id') or '').strip()
            or str(item.get('parent_email') or '').strip().lower() != parent
            or identity_type not in {'primary', 'plus_alias', 'plus_tag'}
            or ('+' in address.partition('@')[0]) != (identity_type != 'primary')):
        raise ValueError('handoff_identity_mismatch: Butler 未确认完整邮箱及固定收件身份')
    return {key: (address if key == 'email' else item[key]) for key in
            ('email', 'provider', 'identity_type', 'identity_id', 'parent_email',
             'mailbox_email', 'recipient_mode', 'strict_family')}


def handoff_selected(candidate: dict, profile: dict, *, ownership: dict, client_id: str) -> dict:
    """Replay one frozen candidate and ownership, without selecting or resolving."""
    from core.email.email_butler import client as client
    from core.email.derivation import _profile_credentials
    if profile.get('state') != 'active' or profile.get('connector') != 'forward_butler':
        raise ValueError('fixed_route_unavailable: 原固定收件配置不可用')
    connection = _profile_credentials(profile)
    original = validate_candidate(candidate, mailbox=connection['mailbox_email'])
    payload = client._request('POST', '/mailboxes', json={
        'requested_email': original['email'], 'provider': 'icloud_hme', **ownership},
        api_base=connection['api_base'], api_key=connection['api_key'])
    received = validate_candidate(payload.get('mailbox'), mailbox=connection['mailbox_email'])
    if received != original or not (payload.get('mailbox') or {}).get('lease_id'):
        raise ValueError('handoff_identity_mismatch: Butler 交接未确认原固定身份')
    return {**ownership, 'client_id': client_id, 'identity_id': original['identity_id'],
            'parent_email': original['parent_email'], 'state': 'issued', 'version': 1}


def _consumer_instance() -> str:
    from config.env_loader import env_file_lock
    from config.runtime import read_persisted_values, write_persisted_values

    name = 'TURB_MAIL_CONSUMER_ID'
    with env_file_lock():
        existing = str(os.environ.get(name) or read_persisted_values().get(name) or '').strip()
        if existing:
            return existing
        value = 'turb-' + uuid.uuid4().hex
        write_persisted_values({name: value})
        os.environ[name] = value
        return value


def handoff_for_import(email: str, profile: dict, *, conn=None) -> dict:
    """Bind one exact known HME identity to this deployment before local import.

    No lease token is saved: OTP uses the original fixed read profile, and the
    permanent acquisition is kept solely as the result-report ownership proof.
    A committed remote handoff survives a rolled-back local import by design.
    """
    from core.email.email_butler import client as client
    from core.email.derivation import _profile_credentials
    from core.storage.email.local_imports import butler_forward_address

    address = butler_forward_address(email)
    if profile.get('connector') != 'forward_butler':
        raise ValueError('handoff_contract_unsupported: 交接需要固定 Butler 收码连接')
    connection = _profile_credentials(profile)
    parameters = {'api_base': connection['api_base'], 'api_key': connection['api_key']}
    mailbox = str(connection.get('mailbox_email') or '').strip().lower()

    def verified(payload):
        item = payload.get('mailbox') or {}
        parent = address.partition('@')[0].split('+', 1)[0] + '@icloud.com'
        if (str(item.get('email') or '').strip().lower() != address
                or item.get('provider') != 'icloud_hme'
                or item.get('recipient_mode') != 'forwarded_exact_v1'
                or item.get('strict_family') is not True
                or str(item.get('mailbox_email') or '').strip().lower() != mailbox
                or not str(item.get('identity_id') or '').strip()
                or str(item.get('parent_email') or '').strip().lower() != parent
                or item.get('identity_type') not in {'primary', 'plus_alias', 'plus_tag'}):
            raise ValueError('handoff_identity_mismatch: Butler 未确认原完整邮箱及固定收件身份')
        return item

    try:
        who = client._request('GET', '/me', **parameters)
        required = {'mailboxes.acquisition.v1', 'inbound.recipient_evidence.v1'}
        policy = who.get('policy') or {}
        if (not required.issubset(set(who.get('capabilities') or []))
                or not who.get('id') or not policy.get('consumer') or policy.get('service') != 'openai'):
            raise ValueError('handoff_contract_unsupported: Butler 需要持久归属、严格收件及 OpenAI 消费策略')
        # Resolve-only is intentionally sent without any acquisition fields.
        original = verified(client._request('POST', '/mailboxes', json={
            'requested_email': address, 'provider': 'icloud_hme'}, **parameters))
        instance = _consumer_instance()
        digest = hashlib.sha256(f"{instance}:{connection['api_base']}:{who['id']}:{address}".encode()).hexdigest()
        ownership = {'owner_kind': 'local_inventory', 'owner_id': instance,
                     'acquisition_id': 'turb-import:' + digest}
        received = verified(client._request('POST', '/mailboxes', json={
            'requested_email': address, 'provider': 'icloud_hme', **ownership}, **parameters))
        if received['identity_id'] != original['identity_id'] or not received.get('lease_id'):
            raise ValueError('handoff_identity_mismatch: Butler 交接身份发生变化')
        return {**ownership, 'client_id': str(who['id']), 'identity_id': received['identity_id'],
                'parent_email': received['parent_email'], 'state': 'issued', 'version': 1}
    except ValueError:
        raise
    except Exception:
        # Upstream exception messages can contain headers, tokens or addresses.
        raise ValueError('handoff_unconfirmed: 邮箱库存交接未确认；请重试同一地址，禁止换号') from None
