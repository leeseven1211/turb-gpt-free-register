"""v2 验证码服务不能被当作封号邮件扫描成功。"""
from unittest import TestCase
from unittest.mock import Mock, patch

from config import email as email_config
from core.accounts.deactivation import mail_scan
from core.email.email_butler.client import EmailButlerClientError
from core.runtime import capabilities
from core.storage import records as store
from tests.support_pg import PostgresTestCase


class V2SignalContractTests(PostgresTestCase):
    def test_unsupported_code_is_permanent_and_does_not_claim_missing_email(self):
        error = EmailButlerClientError('v2 不提供邮件信号', error_code='signal_scan_unsupported')
        self.assertTrue(mail_scan._is_permanent_email_butler_scan_error(error))

    def test_manual_butler_scan_returns_unsupported_without_queuing(self):
        self.seed(store.ACCOUNTS, [{'id': 1, 'email': 'fixture@example.test', 'email_source': 'email_butler'}])
        with patch.object(mail_scan, '_submit_native_scan') as submit:
            result = mail_scan.enqueue(1)
        self.assertFalse(result['accepted'])
        self.assertTrue(result['unsupported'])
        self.assertEqual(result['error_code'], 'signal_scan_unsupported')
        self.assertEqual(store.get_row(store.ACCOUNTS, 1)['deactivation_mail_scan_status'], 'unsupported')
        submit.assert_not_called()

    def test_hme_unsupported_result_stays_unsupported_without_false_clear_result(self):
        context = Mock()
        context.is_cancel_requested.return_value = False
        result = {'ok': False, 'error_code': 'signal_scan_unsupported', 'error': 'v2 暂不提供封号邮件扫描'}
        self.seed(store.ACCOUNTS, [{'id': 1, 'email': 'fixture@icloud.com'}])
        with patch.object(mail_scan, 'scan_hme_deactivation_bulk', return_value={'fixture@icloud.com': result}):
            mail_scan._scan_hme_group(context, [{'account_id': 1, 'email': 'fixture@icloud.com'}], 'manual')
        row = store.get_row(store.ACCOUNTS, 1)
        self.assertEqual(row['deactivation_mail_scan_status'], 'unsupported')
        self.assertFalse(row.get('deactivation_mail_detected'))
        self.assertEqual(context.finish.call_args.kwargs['status'], 'unsupported')
        self.assertEqual(context.finish.call_args.kwargs['result_summary']['success_count'], 0)

    def test_scheduled_scan_skips_butler_without_requeue_or_repeated_projection(self):
        account = {'id': 1, 'email_source': 'email_butler', 'deactivation_mail_scan_status': 'unsupported',
                   'deactivation_mail_error': mail_scan._BUTLER_SCAN_ERROR}
        with patch.object(mail_scan, 'scheduler_enabled', return_value=True), patch.object(
                mail_scan.db, 'list_accounts', return_value=[account]), patch.object(
                mail_scan.db, 'update_account_deactivation_mail') as update, patch.object(
                mail_scan, 'enqueue_bulk') as enqueue, patch.object(
                mail_scan.mail_store, 'update_many') as update_many:
            result = mail_scan.enqueue_due_accounts()
        self.assertEqual(result, {'started': 0, 'skipped': 1})
        enqueue.assert_not_called()
        update.assert_not_called()
        update_many.assert_not_called()

    def test_scheduled_unsupported_projection_uses_bounded_collections(self):
        accounts = [
            {'id': number, 'email_source': 'email_butler', 'deactivation_mail_checked_at': 'old-check'}
            for number in range(1, 502)
        ]
        with patch.object(mail_scan, 'scheduler_enabled', return_value=True), patch.object(
                mail_scan.db, 'list_accounts', return_value=accounts), patch.object(
                mail_scan.db, 'update_account_deactivation_mail', side_effect=AssertionError('per-account write')), patch.object(
                mail_scan.mail_store, 'update_many', side_effect=lambda values: list(values)) as update_many, patch.object(
                mail_scan, 'enqueue_bulk') as enqueue:
            result = mail_scan.enqueue_due_accounts()
        self.assertEqual({'started': 0, 'skipped': 501}, result)
        self.assertEqual([500, 1], [len(call.args[0]) for call in update_many.call_args_list])
        self.assertTrue(all(payload['preserve_checked_at']
                            for call in update_many.call_args_list for payload in call.args[0].values()))
        enqueue.assert_not_called()

    def test_historical_imap_route_remains_scannable_after_global_butler_switch(self):
        rows = [{'id': 1, 'email_source': 'icloud_hide', 'email': 'direct@icloud.com'},
                {'id': 2, 'email_source': 'icloud_hide', 'email': 'butler@icloud.com'}]
        profiles = {'direct@icloud.com': {'connector': 'forward_imap'},
                    'butler@icloud.com': {'connector': 'forward_butler'}}
        with patch.object(email_config, 'ICLOUD_HME_INBOX_MODE', 'forward_butler'), patch(
                'core.email.email_butler.bridge.inbox_profiles_for_addresses', return_value=profiles):
            self.assertEqual(mail_scan._butler_scan_account_ids(rows), {2})

    def test_butler_credentials_do_not_enable_signal_capability(self):
        with patch.multiple(email_config, EMAIL_BUTLER_API_BASE='https://butler.example.test/v2',
                EMAIL_BUTLER_API_KEY='fixture-key', CLOUDFLARE_API_BASE='', CLOUDFLARE_API_KEY='',
                CLOUDFLARE_SIGNAL_API_KEY=''), patch(
                'core.storage.email.address_allocations.list_inbox_profiles', return_value=[]):
            self.assertFalse(capabilities._historical_mail_readable())
