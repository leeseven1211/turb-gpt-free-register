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


def handoff_selected(candidate: dict, profile: dict, *, ownership: dict, client_id: str,
                     connection: dict | None = None) -> dict:
    """Replay one frozen candidate and ownership, without selecting or resolving."""
    from core.email.email_butler import client as client
    from core.email.derivation import _profile_credentials
    if profile.get('state') != 'active' or profile.get('connector') != 'forward_butler':
        raise ValueError('fixed_route_unavailable: 原固定收件配置不可用')
    connection = _profile_credentials(profile) if connection is None else connection
    original = validate_candidate(candidate, mailbox=connection['mailbox_email'])
    payload = client._request('POST', '/mailboxes', json={
        'requested_email': original['email'], 'provider': 'icloud_hme', **ownership},
        api_base=connection['api_base'], api_key=connection['api_key'])
    received = validate_candidate(payload.get('mailbox'), mailbox=connection['mailbox_email'])
    if received != original or not (payload.get('mailbox') or {}).get('lease_id'):
        raise ValueError('handoff_identity_mismatch: Butler 交接未确认原固定身份')
    return {**ownership, 'client_id': client_id, 'identity_id': original['identity_id'],
            'parent_email': original['parent_email'], 'state': 'issued', 'version': 1}


def _batch_handoff_error(code: str, detail: str, *, status_code: int | None = None) -> dict:
    definite = (status_code is not None and 400 <= status_code < 500
                and status_code not in {408, 425, 429})
    result = {'outcome': 'failed' if definite else 'unknown',
              'error_code': code, 'error_detail': detail}
    if status_code is not None:
        result['status_code'] = status_code
    return result


def handoff_selected_batch(items: list[dict], profile: dict, *, client_id: str,
                           connection: dict | None = None) -> dict[str, dict]:
    """批量重放已冻结身份，以 acquisition 和完整地址匹配每项回执。"""
    from core.email.email_butler import client
    from core.email.derivation import _profile_credentials
    from core.storage.email.local_imports import butler_forward_address
    from requests import Timeout

    if not items:
        return {}
    if len(items) > 25:
        raise ValueError('handoff_batch_too_large: Butler 单次最多交接 25 项')
    if profile.get('state') != 'active' or profile.get('connector') != 'forward_butler':
        raise ValueError('fixed_route_unavailable: 原固定收件配置不可用')
    connection = _profile_credentials(profile) if connection is None else connection
    originals = {}
    addresses = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('ownership'), dict):
            raise ValueError('handoff_identity_mismatch: 原交接归属缺失')
        original = validate_candidate(item.get('candidate'), mailbox=connection['mailbox_email'])
        ownership = item['ownership']
        acquisition_id = item.get('acquisition_id')
        if (not isinstance(acquisition_id, str) or not acquisition_id.strip()
                or ownership.get('acquisition_id') != acquisition_id
                or ownership.get('owner_kind') != 'local_inventory'
                or not isinstance(ownership.get('owner_id'), str) or not ownership['owner_id'].strip()
                or item.get('address_norm') != original['email']):
            raise ValueError('handoff_identity_mismatch: 原交接地址或持久归属不一致')
        if acquisition_id in originals or original['email'] in addresses:
            raise ValueError('handoff_response_invalid: 批次包含重复交接身份')
        originals[acquisition_id] = (original, {key: ownership[key] for key in
            ('owner_kind', 'owner_id', 'acquisition_id')})
        addresses[original['email']] = acquisition_id

    def all_errors(code, detail, *, status_code=None):
        return {key: _batch_handoff_error(code, detail, status_code=status_code) for key in originals}

    try:
        payload = client._request('POST', '/mailboxes/import-batch', json={'items': [
            {'requested_email': original['email'], 'provider': 'icloud_hme', **ownership}
            for original, ownership in originals.values()]},
            api_base=connection['api_base'], api_key=connection['api_key'])
    except Exception as exc:
        status_code = getattr(exc, 'status_code', None)
        status_code = status_code if type(status_code) is int else None
        timeout = isinstance(exc, (TimeoutError, Timeout)) or isinstance(exc.__cause__, (TimeoutError, Timeout))
        code = str(getattr(exc, 'error_code', '') or (
            'handoff_timeout' if timeout or status_code == 408 else
            'handoff_rate_limited' if status_code == 429 else
            'handoff_remote_unavailable' if status_code is not None and status_code >= 500 else
            'handoff_rejected' if status_code is not None and 400 <= status_code < 500 else
            'handoff_unconfirmed'))
        return all_errors(code, 'Butler 批量交接未确认，保留原地址与归属供重试', status_code=status_code)

    if (not isinstance(payload, dict) or type(payload.get('code')) is not int or payload['code'] != 200
            or not isinstance(payload.get('results'), list)):
        return all_errors('handoff_response_invalid', 'Butler 批量交接响应结构无效')
    responses = {}
    mismatched = {}
    for response in payload['results']:
        if (not isinstance(response, dict) or not isinstance(response.get('acquisition_id'), str)
                or response['acquisition_id'] not in originals):
            return all_errors('handoff_response_invalid', 'Butler 批量回执包含未知或缺失的交接身份')
        acquisition_id = response['acquisition_id']
        responses.setdefault(acquisition_id, []).append(response)
        try:
            requested = butler_forward_address(response.get('requested_email'))
        except ValueError:
            mismatched[acquisition_id] = _batch_handoff_error(
                'handoff_response_invalid', 'Butler 批量回执未提供有效原地址')
            continue
        if requested != originals[acquisition_id][0]['email']:
            mismatch = _batch_handoff_error('handoff_identity_mismatch', 'Butler 批量回执的原地址与归属不一致')
            mismatched[acquisition_id] = mismatch
            if requested in addresses:
                mismatched[addresses[requested]] = mismatch

    output = {}
    for acquisition_id, (original, ownership) in originals.items():
        results = responses.get(acquisition_id, [])
        if len(results) != 1:
            output[acquisition_id] = _batch_handoff_error(
                'handoff_response_invalid', 'Butler 批量回执缺失或重复，原交接结果未确认')
            continue
        if acquisition_id in mismatched:
            output[acquisition_id] = mismatched[acquisition_id]
            continue
        result = results[0]
        status = result.get('code')
        if type(status) is not int or status != 200 and not 400 <= status < 600:
            output[acquisition_id] = _batch_handoff_error(
                'handoff_response_invalid', 'Butler 批量回执缺少有效逐项状态')
            continue
        if status != 200:
            output[acquisition_id] = _batch_handoff_error(
                str(result.get('error_code') or 'handoff_rejected'),
                'Butler 未确认此项原地址交接', status_code=status)
            continue
        try:
            received = validate_candidate(result.get('mailbox'), mailbox=connection['mailbox_email'])
            mailbox = result['mailbox']
            if (received != original or not isinstance(mailbox.get('lease_id'), str)
                    or not mailbox['lease_id'].strip()
                    or any(key in source and source[key] != value
                           for source in (result, mailbox) for key, value in ownership.items())):
                raise ValueError('handoff_identity_mismatch: Butler 交接未确认原固定身份或归属')
        except (ValueError, TypeError, KeyError):
            output[acquisition_id] = _batch_handoff_error(
                'handoff_identity_mismatch', 'Butler 未确认原固定完整身份及持久归属')
            continue
        output[acquisition_id] = {'receipt': {
            **ownership, 'client_id': client_id, 'identity_id': original['identity_id'],
            'parent_email': original['parent_email'], 'state': 'issued', 'version': 1}}
    return output


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
