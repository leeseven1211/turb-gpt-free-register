"""旧交接入口只恢复本人已存在的 v2 长期租约，不重新分配地址。"""
from __future__ import annotations

import hashlib
import os
import uuid


def verify_client(who: dict, *, client_id: str = '') -> str:
    from core.email.email_butler.manual_import_v2 import verify_client as verify_v2
    return verify_v2(who, client_id=client_id, allocating=False)


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
    """按旧冻结地址和 acquisition 恢复，不调用随机租用。"""
    from core.storage.email.local_imports import _existing_v2_handoff, butler_forward_address
    if profile.get('state') != 'active' or profile.get('connector') != 'forward_butler':
        raise ValueError('fixed_route_unavailable: 原固定收件配置不可用')
    if (not isinstance(candidate, dict) or not isinstance(ownership, dict)
            or ownership.get('owner_kind') != 'local_inventory'
            or not all(ownership.get(key) for key in ('owner_id', 'acquisition_id'))):
        raise ValueError('handoff_identity_mismatch: 原完整身份与归属缺失')
    address = butler_forward_address(candidate.get('email'))
    receipt = _existing_v2_handoff(address, profile, client_id=client_id,
        acquisition_id=ownership['acquisition_id'], connection=connection)
    if candidate.get('provider') and receipt['provider'] != candidate['provider']:
        raise ValueError('handoff_identity_mismatch: 原邮箱来源不一致')
    return {**receipt, **{key: ownership[key] for key in ('owner_kind', 'owner_id', 'acquisition_id')}}


def handoff_selected_batch(items: list[dict], profile: dict, *, client_id: str,
                           connection: dict | None = None) -> dict[str, dict]:
    """逐项恢复旧归属；任何失败保留原意图，其他项目可以独立完成。"""
    from core.email.email_butler import v2
    from core.storage.email.local_imports import butler_forward_address
    if len(items) > 100:
        raise ValueError('handoff_batch_too_large: 单次最多恢复 100 项')
    seen, addresses = set(), set()
    for item in items:
        acquisition = item.get('acquisition_id') if isinstance(item, dict) else None
        ownership = item.get('ownership') if isinstance(item, dict) else None
        candidate = item.get('candidate') if isinstance(item, dict) else None
        if (not acquisition or not isinstance(ownership, dict)
                or ownership.get('acquisition_id') != acquisition or not isinstance(candidate, dict)):
            raise ValueError('handoff_identity_mismatch: 原交接地址或归属不一致')
        address = butler_forward_address(candidate.get('email'))
        if item.get('address_norm') != address or acquisition in seen or address in addresses:
            raise ValueError('handoff_identity_mismatch: 原交接身份重复或地址不一致')
        seen.add(acquisition)
        addresses.add(address)
    result = {}
    for item in items:
        try:
            result[item['acquisition_id']] = {'receipt': handoff_selected(item['candidate'], profile,
                ownership=item['ownership'], client_id=client_id, connection=connection)}
        except v2.ButlerV2Error as exc:
            result[item['acquisition_id']] = {'outcome': 'unknown', 'error_code': exc.error_code,
                'error_detail': '原租约尚未确认，保留原完整地址继续恢复', 'status_code': exc.status_code}
        except ValueError as exc:
            code = str(exc).partition(':')[0]
            result[item['acquisition_id']] = {'outcome': 'unknown', 'error_code': code,
                'error_detail': '原固定身份未确认，保留原完整地址继续恢复'}
    return result


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
    """粘贴完整地址只恢复本人已有长期租约，不调用退役交接接口。"""
    from core.storage.email.local_imports import _existing_v2_handoff, butler_forward_address
    if profile.get('state') != 'active' or profile.get('connector') != 'forward_butler':
        raise ValueError('fixed_route_unavailable: 原固定 Butler 配置不可用')
    return _existing_v2_handoff(butler_forward_address(email), profile, conn=conn)
