"""Registration supply reads only the local imported email pools."""
from core.email.provider import EMAIL_SOURCE_LABELS


def email_supply_summary(*, include_next_expiry: bool = False) -> dict:
    from core.email import inventory as local_email_inventory
    from config import email as cfg

    counts = local_email_inventory.summary(**({'include_next_expiry': True} if include_next_expiry else {}))
    sources = [{**row, 'label': EMAIL_SOURCE_LABELS.get(row['source'], row['source']),
                'status': 'known', 'scope': 'local_pool', 'kind': 'local_pool',
                'enabled': bool(cfg.USE_EMAIL_SERVICE and row['available'] > 0),
                'included': True, 'reason': ''}
               for row in counts.get('sources', [])]
    return {**counts, 'scope': 'local_pool', 'status': 'known', 'sources': sources,
            'reason': '', 'generation_mode': 'manual_import'}
