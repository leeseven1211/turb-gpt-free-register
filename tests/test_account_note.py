# -*- coding: utf-8 -*-
import unittest

from core import db
from core.record_store import ACCOUNTS
from tests.support_pg import PostgresTestCase


class AccountNoteTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        self.seed(ACCOUNTS, [
            {"id": 1, "email": "a@test.com"},
            {"id": 2, "email": "b@test.com"},
        ])

    def test_update_account_note_single_and_bulk(self):
        self.assertTrue(db.update_account_note(1, "备注A"))
        self.assertFalse(db.update_account_note(99, "不存在"))
        self.assertEqual(db.get_account(1)["note"], "备注A")
        self.assertTrue(db.get_account(1)["note_updated_at"])

        updated, skipped = db.update_accounts_note([1, 2, 99], "批量备注")
        self.assertEqual([x["id"] for x in updated], [1, 2])
        self.assertEqual(skipped, [{"id": 99, "reason": "账号不存在"}])
        self.assertEqual(db.get_account(1)["note"], "批量备注")
        self.assertEqual(db.get_account(2)["note"], "批量备注")


if __name__ == "__main__":
    unittest.main()
