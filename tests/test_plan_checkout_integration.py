"""验证查套餐主动预检、优惠成功保留和逐国支付结果隔离。"""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import chatgpt_plan, plan_check_service, record_store
from core.operation_runtime import OperationCancelled
from core.storage import accounts as db
from tests.support_pg import PostgresTestCase
from tests.test_plan_country_check import offer_result


def checkout_answer(country='JP', status='success', amount=0):
    return {'checkout_status': status, 'checkout_checked_at': '2026-10-16T14:00:00',
            'checkout_country': country, 'session_type': 'oaics',
            'checkout_currency': 'JPY', 'checkout_currency_exponent': 0,
            'checkout_amount_due_minor': amount, 'checkout_amount_source': 'total.total',
            'payment_method_types': ['card', 'link'] if status == 'success' else [],
            'checkout_error': None if status == 'success' else '创建结账会话失败'}


class PlanCheckoutRequestTests(unittest.TestCase):
    def env(self, campaigns=None):
        payload = {'accounts': {'default': {'account': {'plan_type': 'free'},
                   'eligible_promo_campaigns': campaigns if campaigns is not None else {
                       'plus': {'id': 'actual-plus-trial', 'metadata': {'discount': {'percentage': 100}}}}}}}
        response = Mock(status_code=200, text='{}')
        response.json.return_value = payload
        env = Mock()
        env.get.return_value = response
        return env

    def query(self, env, **kwargs):
        with patch.object(chatgpt_plan, '_query_account_quota', return_value={}):
            return chatgpt_plan.check_account_plan('synthetic-token', proxy='JP', session=env,
                timezone_offset_min='-', max_attempts=1, timeout=15, **kwargs)

    def test_default_shared_query_never_creates_checkout(self):
        with patch('core.checkout_probe.query_checkout_details') as probe:
            result = self.query(self.env())
        self.assertTrue(result['ok'])
        probe.assert_not_called()

    def test_manual_query_binds_actual_campaign_country_and_same_session(self):
        env = self.env()
        with patch('core.checkout_probe.query_checkout_details', return_value=checkout_answer()) as probe:
            result = self.query(env, include_checkout=True, checkout_country='JP')
        self.assertTrue(result['ok'])
        self.assertEqual('success', result['account_promotions'][1]['checkout_status'])
        self.assertEqual('actual-plus-trial', probe.call_args.kwargs['campaign_id'])
        self.assertIs(env, probe.call_args.kwargs['session'])
        self.assertEqual('JP', probe.call_args.kwargs['country'])
        env.session.close.assert_not_called()

    def test_probe_failure_does_not_retry_checkout_or_clear_known_offer(self):
        with patch('core.checkout_probe.query_checkout_details', side_effect=RuntimeError('Bearer hidden-secret')) as probe:
            result = self.query(self.env(), include_checkout=True, checkout_country='JP')
        self.assertTrue(result['ok'])
        self.assertEqual('free_trial', result['plus_promo_kind'])
        self.assertEqual('failed', result['account_promotions'][1]['checkout_status'])
        self.assertNotIn('hidden-secret', str(result))
        self.assertEqual(1, probe.call_count)

    def test_checkout_transport_failure_is_internal_and_keeps_successful_offer(self):
        answer = {**checkout_answer(status='failed'), 'proxy_transport_failure': True}
        with patch('core.checkout_probe.query_checkout_details', return_value=answer) as probe:
            result = self.query(self.env(), include_checkout=True, checkout_country='JP')
        self.assertTrue(result['ok'])
        self.assertTrue(result['proxy_transport_failure'])
        self.assertEqual('free_trial', result['plus_promo_kind'])
        self.assertEqual('failed', result['account_promotions'][1]['checkout_status'])
        self.assertNotIn('proxy_transport_failure', result['account_promotions'][1])
        self.assertEqual(1, probe.call_count)

    def test_cancellation_before_checkout_is_not_converted_to_plan_failure(self):
        with patch('core.checkout_probe.query_checkout_details', side_effect=OperationCancelled('测试取消')):
            with self.assertRaises(OperationCancelled):
                self.query(self.env(), include_checkout=True, checkout_country='JP')

    def test_go_only_offer_does_not_start_plus_checkout(self):
        with patch('core.checkout_probe.query_checkout_details') as probe:
            self.query(self.env({'go': {'id': 'go-trial', 'metadata': {'discount': {'percentage': 100}}}}),
                       include_checkout=True, checkout_country='JP')
        probe.assert_not_called()

    def test_only_highest_plus_discount_is_probed(self):
        campaigns = {'plus': [
            {'id': 'half-one-month', 'metadata': {'discount': {'percentage': 50}, 'duration': {'num_periods': 1, 'period': 'month'}}},
            {'id': 'half-three-months', 'metadata': {'discount': {'percentage': 50}, 'duration': {'num_periods': 3, 'period': 'month'}}},
        ]}
        with patch('core.checkout_probe.query_checkout_details', return_value=checkout_answer(amount=1500)) as probe:
            result = self.query(self.env(campaigns), include_checkout=True, checkout_country='JP')
        self.assertEqual(1, probe.call_count)
        self.assertEqual('half-three-months', probe.call_args.kwargs['campaign_id'])
        self.assertNotIn('checkout_status', result['account_promotions'][1])
        self.assertEqual(1500, result['account_promotions'][2]['checkout_amount_due_minor'])

    def test_registration_auto_keeps_original_read_only_query(self):
        with patch.object(plan_check_service, 'check_account_plan', return_value={'ok': True, 'plus_promo_eligible': True}) as query, \
             patch.object(plan_check_service, '_wait_for_rate_slot'):
            plan_check_service._query_account_plan(email='synthetic@example.test', access_token='synthetic-token',
                trigger='registration_auto', proxy='JP', timezone_offset_min='-', checkout_country='JP',
                include_checkout=True, config_snapshot={'payment_methods_enabled': True})
        self.assertNotIn('include_checkout', query.call_args.kwargs)
        self.assertNotIn('checkout_country', query.call_args.kwargs)

    def test_oauth_followup_manual_trigger_does_not_opt_in_to_checkout(self):
        with patch.object(plan_check_service, 'check_account_plan', return_value={'ok': True}) as query, \
             patch.object(plan_check_service, '_wait_for_rate_slot'):
            plan_check_service._query_account_plan(email='synthetic@example.test', access_token='synthetic-token',
                trigger='manual_plan_check', proxy='JP', timezone_offset_min='-')
        self.assertNotIn('include_checkout', query.call_args.kwargs)
        self.assertNotIn('checkout_country', query.call_args.kwargs)

    def test_standalone_query_explicitly_opts_in_to_checkout(self):
        with patch.object(plan_check_service, 'check_account_plan', return_value={'ok': True}) as query, \
             patch.object(plan_check_service, '_wait_for_rate_slot'):
            plan_check_service._query_account_plan(email='synthetic@example.test', access_token='synthetic-token',
                trigger='manual_plan_check', proxy='JP', timezone_offset_min='-',
                include_checkout=True, checkout_country='JP')
        self.assertTrue(query.call_args.kwargs['include_checkout'])
        self.assertEqual('JP', query.call_args.kwargs['checkout_country'])

    def test_legacy_snapshot_without_payment_choice_uses_current_config(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled), \
                 patch.object(plan_check_service.proxy_cfg, 'PLAN_CHECK_PAYMENT_METHODS_ENABLED', enabled, create=True):
                self.assertIs(enabled, plan_check_service._payment_methods_enabled({}))
                self.assertIs(enabled, plan_check_service._payment_methods_enabled(None))


class PlanCheckoutCountryIntegrationTests(PostgresTestCase):
    def setUp(self):
        self.account_id = record_store.insert_row(record_store.ACCOUNTS, {
            'email': 'checkout-integration@example.test', 'access_token': 'synthetic-token',
            'plan_check_status': 'queued', 'current_plan_type': 'free'})
        self.context = SimpleNamespace(checkpoint=Mock(), report=Mock(return_value={}), finish=Mock())

    def test_default_disabled_single_and_multi_country_queries_never_probe_payment(self):
        for countries in (None, ['JP', 'VN']):
            with self.subTest(countries=countries):
                self._execute_with_real_plan_query(countries=countries, snapshot={}, enabled=False)

    def test_frozen_payment_choice_controls_single_and_multi_country_queries(self):
        for enabled in (False, True):
            for countries in (None, ['JP', 'VN']):
                with self.subTest(enabled=enabled, countries=countries):
                    self._execute_with_real_plan_query(
                        countries=countries, snapshot={'payment_methods_enabled': enabled},
                        enabled=enabled, current_enabled=not enabled,
                    )

    def test_queued_payment_choice_and_manual_retry_keep_original_snapshot(self):
        from config.schema import ConfigSnapshot
        from core.operations import task_gateway
        from core.storage import operation
        task_gateway.init()
        plan_check_service.register_operation_handlers()
        submit = task_gateway.submit_durable_operation
        def submit_without_dispatch(**kwargs):
            kwargs['dispatch'] = False
            return submit(**kwargs)
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                snapshot = ConfigSnapshot({
                    'PLAN_CHECK_COUNTRIES': ['JP'],
                    'ACCOUNT_PLAN_CHECK_PROXY_MODE': 'provider:1024proxy',
                    'PLAN_CHECK_PAYMENT_METHODS_ENABLED': enabled,
                    'PLAN_CHECK_COUNTRY_WAIT_TIMEOUT': 5,
                }, {'ACCOUNT_PLAN_CHECK_PROXY_MODE': 'env'}, revision=23)
                with patch.object(plan_check_service, 'get_config_snapshot', return_value=snapshot), \
                     patch.object(task_gateway, 'submit_durable_operation', side_effect=submit_without_dispatch):
                    submitted = plan_check_service.enqueue_account_plan_check(account_id=self.account_id,
                        email='checkout-integration@example.test', trigger='manual',
                        access_token='synthetic-token',
                        timezone_offset_min='-', batch_id=None, idempotency_key=None)
                task_id, run_id = submitted['task_id'], submitted['run_id']
                self.assertIs(enabled, operation.get_run(run_id)['data']['config_snapshot']['payment_methods_enabled'])
                route = SimpleNamespace(proxy_url='JP', region='JP', release=Mock(),
                    public_dict=lambda: {'proxy_region': 'JP', 'proxy_provider': '1024proxy'})
                with patch.object(plan_check_service.proxy_cfg, 'PLAN_CHECK_PAYMENT_METHODS_ENABLED', not enabled, create=True), \
                     patch('core.account_proxy.acquire_account_proxy', return_value=route), \
                     patch.object(plan_check_service, '_wait_for_rate_slot'), \
                     patch.object(plan_check_service, 'check_account_plan', return_value=offer_result('JP', 100)) as query:
                    first = task_gateway._execute_operation_handler('plan_check', run_id)
                    retry = operation.retry_runtime_task(task_id)
                    self.assertIs(enabled, retry['data']['config_snapshot']['payment_methods_enabled'])
                    second = task_gateway._execute_operation_handler('plan_check', int(retry['id']))
                self.assertEqual('success', first['status'])
                self.assertEqual('success', second['status'])
                self.assertEqual([enabled, enabled], [call.kwargs['include_checkout'] for call in query.call_args_list])

    def _execute_with_real_plan_query(self, *, countries, snapshot, enabled, current_enabled=False):
        mode = 'multi' if countries else 'single'
        account_id = record_store.insert_row(record_store.ACCOUNTS, {
            'email': f'payment-choice-{self.account_id}-{mode}-{enabled}@example.test',
            'access_token': 'synthetic-token', 'plan_check_status': 'queued',
        })
        request_tests = PlanCheckoutRequestTests()
        def acquire(**kwargs):
            country = kwargs.get('region') or 'JP'
            return SimpleNamespace(proxy_url=country, region=country, release=Mock(),
                public_dict=lambda: {'proxy_region': country, 'proxy_provider': '1024proxy'})
        def query(token, **kwargs):
            return chatgpt_plan.check_account_plan(token, session=request_tests.env(), **kwargs)
        with patch('core.account_proxy.acquire_account_proxy', side_effect=acquire), \
             patch.object(plan_check_service.proxy_cfg, 'PLAN_CHECK_PAYMENT_METHODS_ENABLED', current_enabled, create=True), \
             patch.object(plan_check_service, 'check_account_plan', side_effect=query), \
             patch.object(plan_check_service, '_wait_for_rate_slot'), \
             patch.object(chatgpt_plan, '_query_account_quota', return_value={}), \
             patch('core.checkout_probe.query_checkout_details', side_effect=lambda token, **kw: checkout_answer(kw['country'])) as probe:
            result = plan_check_service._run_plan_check(account_id=account_id,
                email='payment-choice@example.test', access_token='synthetic-token', trigger='manual',
                proxy=None, timezone_offset_min='-', countries=countries,
                operation_context=self.context, config_snapshot={'country_wait_timeout': 5, **snapshot})
        self.assertTrue(result['ok'])
        self.assertEqual((len(countries) if countries else 1) if enabled else 0, probe.call_count)
        account = db.get_account(account_id)
        self.assertEqual('free_trial', account['plus_promo_kind'])
        self.assertEqual('success', self.context.finish.call_args.kwargs['status'])
        if not enabled:
            self.assertNotIn('checkout_status', str(account['account_promotions']))
            self.assertEqual(0, self.context.finish.call_args.kwargs['result_summary']['checkout_check_count'])

    def test_payment_failure_is_partial_task_but_three_successful_plan_countries(self):
        routes = []
        def acquire(**kwargs):
            country = kwargs['region']
            route = SimpleNamespace(proxy_url=country, region=country, release=Mock(),
                public_dict=lambda: {'proxy_region': country, 'proxy_provider': '1024proxy'})
            routes.append(route)
            return route
        def query(token, **kwargs):
            country = kwargs['checkout_country']
            self.assertTrue(kwargs['include_checkout'])
            self.assertEqual(country, kwargs['proxy'])
            kwargs['checkout_checkpoint']('测试支付检查点')
            result = offer_result(country, 100 if country != 'IN' else 0)
            if country != 'IN':
                result['account_promotions'][1].update(checkout_answer(country, 'success' if country == 'JP' else 'failed'))
            if country == 'VN':
                result['proxy_transport_failure'] = True
            return result
        with patch('core.account_proxy.acquire_account_proxy', side_effect=acquire), \
             patch.object(plan_check_service, 'check_account_plan', side_effect=query), \
             patch.object(plan_check_service, '_wait_for_rate_slot'):
            result = plan_check_service._run_plan_check(account_id=self.account_id,
                email='checkout-integration@example.test', access_token='synthetic-token', trigger='manual_bulk',
                proxy=None, timezone_offset_min='-', countries=['JP', 'VN', 'IN'], operation_context=self.context,
                config_snapshot={'country_wait_timeout': 5, 'payment_methods_enabled': True})
        account = db.get_account(self.account_id)
        self.assertTrue(result['ok'])
        self.assertEqual(['success'] * 3, [r['status'] for r in account['plan_check_country_results']])
        self.assertEqual(['success', 'failed'], [r['result']['account_promotions'][1]['checkout_status']
                                              for r in account['plan_check_country_results'][:2]])
        self.assertEqual('free_trial', account['plus_promo_kind'])
        self.assertEqual('success', account['plan_check_status'])
        self.assertEqual('partial_success', self.context.finish.call_args.kwargs['status'])
        summary = self.context.finish.call_args.kwargs['result_summary']
        self.assertEqual(1, summary['checkout_failed_count'])
        self.assertEqual(1, summary['checkout_success_count'])
        self.assertIn('支付预检 1/2 成功', self.context.finish.call_args.kwargs['message'])
        self.assertTrue(all(route.release.call_count == 1 for route in routes))
        routes[0].release.assert_called_once_with(reason=f'plan-check-{self.account_id}-JP')
        routes[1].release.assert_called_once_with(reason=f'plan-check-{self.account_id}-VN', fault=True)
        routes[2].release.assert_called_once_with(reason=f'plan-check-{self.account_id}-IN')
        self.assertNotIn('proxy_transport_failure', str(account['plan_check_country_results']))

    def test_single_country_checkout_transport_failure_faults_route_and_keeps_offer(self):
        answer = offer_result('JP', 100)
        answer['account_promotions'][1].update(checkout_answer(status='failed'))
        answer['proxy_transport_failure'] = True
        route = SimpleNamespace(proxy_url='JP', region='JP', release=Mock(),
            public_dict=lambda: {'proxy_region': 'JP', 'proxy_provider': '1024proxy'})
        with patch('core.account_proxy.acquire_account_proxy', return_value=route), \
             patch.object(plan_check_service, '_query_account_plan', return_value=answer):
            result = plan_check_service._run_plan_check(account_id=self.account_id,
                email='checkout-integration@example.test', access_token='synthetic-token', trigger='manual',
                proxy=None, timezone_offset_min='-', operation_context=self.context)
        account = db.get_account(self.account_id)
        self.assertTrue(result['ok'])
        self.assertEqual('free_trial', account['plus_promo_kind'])
        self.assertEqual('success', account['plan_check_status'])
        self.assertEqual('partial_success', self.context.finish.call_args.kwargs['status'])
        route.release.assert_called_once_with(reason=f'plan-check-{self.account_id}', fault=True)
        self.assertNotIn('proxy_transport_failure', str(account['account_promotions']))
