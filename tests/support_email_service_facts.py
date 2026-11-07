"""旧库存测试显式确认合成中央事实，保持数据库与网络隔离。"""
from contextlib import contextmanager
from unittest.mock import patch

from core.email.email_butler import client, service_facts


@contextmanager
def confirmed_service_facts():
    def receipt(_method, _path, **kwargs):
        return {'code': 200, 'results': [{'code': 200, **item, 'ever_imported': True, 'permanent': True}
                                       for item in kwargs['json']['items']]}

    def acknowledge():
        while service_facts.dispatch_once():
            pass

    with patch.object(service_facts, '_new_route', return_value={
            'api_base': 'https://synthetic.test/v1', 'credential_ref': 'TEST_FACT_KEY'}), \
         patch('core.email.email_butler.inventory_handoff._consumer_instance', return_value='test-fact-instance'), \
         patch('config.runtime.read_persisted_values', return_value={'TEST_FACT_KEY': 'test-only'}), \
         patch.object(client, '_request', side_effect=receipt):
        yield acknowledge
